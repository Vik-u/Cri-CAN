#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
AGENTIC_DIR = Path(__file__).resolve().parents[1]

sys.path.append(str(ROOT_DIR))
sys.path.append(str(AGENTIC_DIR))

from config import get_path, load_config
from agents import FactCheckAgent, PlannerAgent, StyleAgent
from llm_adapter import generate_with_llm
from style_templates import render_style

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
                over_summaries[(match_id, innings_index, over)] = shorten(summary, limit=160)
            for ball in payload.get("balls", []):
                for key in ["ball_index", "innings_index", "over", "ball_in_over", "token_runs"]:
                    if key in ball and ball[key] is not None and str(ball[key]).isdigit():
                        ball[key] = int(ball[key])
                rows.append(ball)
    rows.sort(key=lambda r: (r.get("match_id"), r.get("innings_index"), r.get("over"), r.get("ball_in_over"), r.get("ball_index")))
    return rows, over_summaries


def shorten(text, limit=90):
    clean = " ".join((text or "").split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3].rstrip() + "..."


def select_rows(rows, match_id=None, start=None, end=None, limit=None):
    selected = rows
    if match_id:
        selected = [r for r in selected if r.get("match_id") == match_id]

    if start:
        if "." in start:
            over_s, ball_s = start.split(".", 1)
            start_over = int(over_s)
            start_ball = int(ball_s)
            selected = [
                r
                for r in selected
                if (int(r.get("over") or 0), int(r.get("ball_in_over") or 0)) >= (start_over, start_ball)
            ]
        else:
            start_idx = int(start)
            selected = [r for r in selected if int(r.get("ball_index") or 0) >= start_idx]

    if end:
        if "." in end:
            over_e, ball_e = end.split(".", 1)
            end_over = int(over_e)
            end_ball = int(ball_e)
            selected = [
                r
                for r in selected
                if (int(r.get("over") or 0), int(r.get("ball_in_over") or 0)) <= (end_over, end_ball)
            ]
        else:
            end_idx = int(end)
            selected = [r for r in selected if int(r.get("ball_index") or 0) <= end_idx]

    if limit is not None:
        selected = selected[:limit]
    return selected


def build_prompt(system_text, user_template, row, plan, style, context_window, recent_overs, current_over_summary):
    values = {
        "style": style,
        "ball_number": row.get("ball_number", ""),
        "bowler": row.get("bowler", ""),
        "batsman": row.get("batsman", ""),
        "event_type": plan["event_type"],
        "result_raw": row.get("result_raw", ""),
        "commentary": shorten(row.get("commentary", "")),
        "context_window": " | ".join(context_window),
        "recent_overs": " | ".join(recent_overs),
        "over_summary": current_over_summary or "",
    }

    user_text = user_template
    for key, val in values.items():
        user_text = user_text.replace("{{" + key + "}}", str(val))

    return system_text.strip() + "\n\n" + user_text.strip()


def fallback_commentary(row, plan, style_agent, fact_agent, context_window):
    snippet = ""
    commentary = shorten(row.get("commentary", ""))
    if plan["event_type"] in {"wicket", "boundary"}:
        snippet = commentary

    line = style_agent.render(plan, row, snippet=snippet if snippet else None)
    return fact_agent.verify(line, row)


def main():
    parser = argparse.ArgumentParser(description="Generate human-like commentary with LLM-ready agents.")
    parser.add_argument("--config", default=None, help="Path to config.toml")
    parser.add_argument("--match", default=None, help="Match id to filter")
    parser.add_argument("--start", default=None, help="Start ball (ball_index or over.ball)")
    parser.add_argument("--end", default=None, help="End ball (ball_index or over.ball)")
    parser.add_argument("--limit", type=int, default=None, help="Number of balls to generate")
    parser.add_argument("--context", type=int, default=3, help="Number of prior lines to pass as context")
    parser.add_argument("--context-overs", type=int, default=2, help="Number of prior over summaries to pass as context")
    parser.add_argument("--output", default=None, help="Output text file")
    parser.add_argument("--model", default=None, help="Override model for LLM command")
    parser.add_argument("--style", default=None, help="Style: broadcast|funny|serious|methodical|energetic|roasting")
    args = parser.parse_args()

    config = load_config(args.config)
    input_path = get_path(config, "overs_jsonl", section="files")
    output_path = Path(args.output) if args.output else get_path(config, "output_jsonl_v1", section="agentic")

    prompts_dir = get_path(config, "jsonl_dir", section="prompts")
    system_text = (prompts_dir / "system.txt").read_text(encoding="utf-8")
    user_template = (prompts_dir / "user.txt").read_text(encoding="utf-8")

    rows, over_summaries = load_overs(input_path)
    if not args.match and rows:
        args.match = rows[0].get("match_id")

    selected = select_rows(rows, match_id=args.match, start=args.start, end=args.end, limit=args.limit)

    style = args.style or config.get("agentic", {}).get("default_style", "broadcast")
    planner = PlannerAgent()
    style_agent = StyleAgent(lambda plan, row: render_style(
        style=style,
        event_type=plan["event_type"],
        bowler=row.get("bowler", ""),
        batsman=row.get("batsman", ""),
        runs=int(row.get("token_runs") or 0),
        seed_key=f\"{row.get('match_id')}|{row.get('innings_index')}|{row.get('ball_number')}|{style}\",
    ))
    fact_agent = FactCheckAgent()

    header_lines = [
        f"# {config.get('agentic', {}).get('v1_label', 'v1-agentic-llm')}",
        "# llm: uses external command when configured; falls back to style templates",
        f"# match_id: {args.match or 'unknown'}",
        f"# style: {style}",
    ]

    output_lines = list(header_lines)
    context_window = []

    for row in selected:
        plan = planner.plan(row, context_window[-args.context :])
        key = (row.get("match_id"), row.get("innings_index"), row.get("over"))
        recent_overs = []
        for i in range(1, args.context_overs + 1):
            prev_key = (row.get("match_id"), row.get("innings_index"), row.get("over") - i)
            if prev_key in over_summaries:
                recent_overs.append(over_summaries[prev_key])
        recent_overs = list(reversed(recent_overs))
        current_over_summary = over_summaries.get(key, "")

        prompt = build_prompt(
            system_text,
            user_template,
            row,
            plan,
            style,
            context_window[-args.context :],
            recent_overs,
            current_over_summary,
        )
        llm_text = generate_with_llm(prompt, config, model_override=args.model)
        if llm_text:
            line = fact_agent.verify(llm_text, row)
        else:
            line = fallback_commentary(row, plan, style_agent, fact_agent, context_window[-args.context :])
        output_lines.append(line)

        if line:
            context_window.append(line)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(output_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
