#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
AGENTIC_DIR = Path(__file__).resolve().parent

sys.path.append(str(ROOT_DIR))

from config import get_path, load_config
from agents import FactCheckAgent, PlannerAgent, StyleAgent
from llm_adapter import generate_with_llm
from style_templates import render_style

EXTRA_TYPES = {"b", "lb", "nb", "w"}


def load_overs(path):
    rows = []
    over_summaries = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            payload = json.loads(line)
            match_id = payload.get("match_id")
            innings_index = payload.get("innings_index")
            over = payload.get("over")
            if isinstance(innings_index, str) and innings_index.isdigit():
                innings_index = int(innings_index)
            if isinstance(over, str) and over.isdigit():
                over = int(over)
            summary = payload.get("over_summary") or ""
            if summary:
                over_summaries[(match_id, innings_index, over)] = " ".join(summary.split())[:160]
            for ball in payload.get("balls", []):
                for key in ["ball_index", "innings_index", "over", "ball_in_over", "token_runs"]:
                    if key in ball and ball[key] is not None and str(ball[key]).isdigit():
                        ball[key] = int(ball[key])
                rows.append(ball)
    rows.sort(key=lambda r: (r.get("match_id"), r.get("innings_index"), r.get("over"), r.get("ball_in_over"), r.get("ball_index")))
    return rows, over_summaries


def event_type(row):
    token_type = (row.get("token_type") or "").lower()
    token_runs = int(row.get("token_runs") or 0)
    event_token = (row.get("event_token") or "").strip()
    is_wicket = str(row.get("is_wicket") or "").lower() == "true"

    if is_wicket or event_token == "W":
        return "wicket"
    if token_type in EXTRA_TYPES:
        return "extra"
    if token_runs >= 4:
        return "boundary"
    if token_runs == 0:
        return "dot"
    return "run"


def filter_rows(rows, args):
    selected = rows
    if args.match:
        selected = [r for r in selected if r.get("match_id") == args.match]
    if args.innings is not None:
        selected = [r for r in selected if int(r.get("innings_index") or 0) == args.innings]
    if args.team:
        selected = [r for r in selected if (r.get("batting_team") or "").lower() == args.team.lower()]
    if args.over is not None:
        over = args.over - 1 if args.over_ordinal else args.over
        selected = [r for r in selected if int(r.get("over") or 0) == over]
    if args.bowler:
        selected = [r for r in selected if args.bowler.lower() in (r.get("bowler") or "").lower()]
    if args.batsman:
        selected = [r for r in selected if args.batsman.lower() in (r.get("batsman") or "").lower()]
    if args.boundary:
        selected = [r for r in selected if int(r.get("token_runs") or 0) >= 4]
    if args.wicket:
        selected = [r for r in selected if str(r.get("is_wicket") or "").lower() == "true" or (r.get("event_token") or "") == "W"]
    if args.event:
        selected = [r for r in selected if event_type(r) == args.event]

    if args.start:
        if "." in args.start:
            over_s, ball_s = args.start.split(".", 1)
            start_over = int(over_s)
            start_ball = int(ball_s)
            selected = [
                r
                for r in selected
                if (int(r.get("over") or 0), int(r.get("ball_in_over") or 0)) >= (start_over, start_ball)
            ]
        else:
            start_idx = int(args.start)
            selected = [r for r in selected if int(r.get("ball_index") or 0) >= start_idx]

    if args.end:
        if "." in args.end:
            over_e, ball_e = args.end.split(".", 1)
            end_over = int(over_e)
            end_ball = int(ball_e)
            selected = [
                r
                for r in selected
                if (int(r.get("over") or 0), int(r.get("ball_in_over") or 0)) <= (end_over, end_ball)
            ]
        else:
            end_idx = int(args.end)
            selected = [r for r in selected if int(r.get("ball_index") or 0) <= end_idx]

    if args.limit is not None:
        selected = selected[: args.limit]

    return selected


def main():
    parser = argparse.ArgumentParser(description="CLI for chunked commentary generation.")
    parser.add_argument("--config", default=None, help="Path to config.toml")
    parser.add_argument("--match", default=None, help="Match id to filter")
    parser.add_argument("--innings", type=int, default=None, help="Innings index")
    parser.add_argument("--team", default=None, help="Batting team code, e.g., IND")
    parser.add_argument("--over", type=int, default=None, help="Over number (as in ball_number, e.g., 10 for 10.x)")
    parser.add_argument("--over-ordinal", action="store_true", help="Treat --over as ordinal (11th over -> 10)")
    parser.add_argument("--start", default=None, help="Start ball (ball_index or over.ball)")
    parser.add_argument("--end", default=None, help="End ball (ball_index or over.ball)")
    parser.add_argument("--bowler", default=None, help="Filter by bowler name substring")
    parser.add_argument("--batsman", default=None, help="Filter by batsman name substring")
    parser.add_argument("--boundary", action="store_true", help="Filter boundaries (runs >= 4)")
    parser.add_argument("--wicket", action="store_true", help="Filter wickets")
    parser.add_argument("--event", default=None, help="Event type: dot|run|boundary|extra|wicket")
    parser.add_argument("--style", default=None, help="Style: broadcast|funny|serious|methodical|energetic|roasting")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of balls")
    parser.add_argument("--llm", action="store_true", help="Use LLM for generation")
    parser.add_argument("--model", default=None, help="Override LLM model")
    parser.add_argument("--output", default=None, help="Output file (stdout if omitted)")
    args = parser.parse_args()

    config = load_config(args.config)
    input_path = get_path(config, "overs_jsonl", section="files")
    rows, over_summaries = load_overs(input_path)

    if not args.match and rows:
        args.match = rows[0].get("match_id")

    style = args.style or config.get("agentic", {}).get("default_style", "broadcast")

    selected = filter_rows(rows, args)
    planner = PlannerAgent()
    fact_agent = FactCheckAgent()
    style_agent = StyleAgent(lambda plan, row: render_style(
        style=style,
        event_type=plan["event_type"],
        bowler=row.get("bowler", ""),
        batsman=row.get("batsman", ""),
        runs=int(row.get("token_runs") or 0),
        seed_key=f"{row.get('match_id')}|{row.get('innings_index')}|{row.get('ball_number')}|{style}",
    ))

    lines = [
        f"# commentary-cli",
        f"# match_id: {args.match or 'unknown'}",
        f"# style: {style}",
    ]

    for row in selected:
        plan = planner.plan(row, [])
        key = (row.get("match_id"), row.get("innings_index"), row.get("over"))
        over_summary = over_summaries.get(key, "")

        if args.llm:
            prompts_dir = get_path(config, "jsonl_dir", section="prompts")
            system_text = (prompts_dir / "system.txt").read_text(encoding="utf-8")
            user_template = (prompts_dir / "user.txt").read_text(encoding="utf-8")
            values = {
                "style": style,
                "bowler": row.get("bowler", ""),
                "batsman": row.get("batsman", ""),
                "event_type": plan["event_type"],
                "result_raw": row.get("result_raw", ""),
                "commentary": " ".join((row.get("commentary") or "").split())[:120],
                "over_summary": over_summary,
                "recent_overs": "",
                "context_window": "",
            }
            user_text = user_template
            for k, v in values.items():
                user_text = user_text.replace("{{" + k + "}}", str(v))
            prompt = system_text.strip() + "\n\n" + user_text.strip()
            llm_text = generate_with_llm(prompt, config, model_override=args.model)
            if llm_text:
                line = fact_agent.verify(llm_text, row)
            else:
                line = style_agent.render(plan, row)
        else:
            line = style_agent.render(plan, row)

        lines.append(line)

    output = "\n".join(lines) + "\n"
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
