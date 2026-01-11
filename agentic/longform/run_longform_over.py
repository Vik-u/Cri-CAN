#!/usr/bin/env python3
import argparse
import csv
import re
import sys
import textwrap
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT_DIR))

from config import get_path, load_config
from agentic.commentary_core import (
    build_allowed_names,
    build_over_events,
    build_previous_over_summary,
    build_summary,
    load_overs,
    validate_names_in_text,
)
from agentic.llm_adapter import generate_with_llm


def extract_snippet(text, limit=140):
    clean = " ".join((text or "").split())
    if not clean:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", clean)
    first = parts[0] if parts else clean
    if len(first) < 25 and len(parts) > 1:
        first = parts[1]
    if len(first) > limit:
        trimmed = first[:limit].rsplit(" ", 1)[0].rstrip(".")
        return trimmed + "..."
    return first


def load_ball_state(path, match_id, innings, over_ordinal):
    target_over = over_ordinal - 1
    rows = []
    with path.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if match_id and row.get("match_id") != match_id:
                continue
            if int(row.get("innings_index") or 0) != innings:
                continue
            if int(row.get("over") or 0) != target_over:
                continue
            rows.append(row)
    rows.sort(key=lambda r: int(r.get("ball_in_over") or 0))
    return rows


def build_ball_state_lines(state_rows):
    lines = []
    for row in state_rows:
        score = f"{row.get('innings_runs')}/{row.get('innings_wickets')}"
        balls = row.get("balls_remaining")
        rrr = row.get("rrr")
        phase = row.get("phase")
        context_bits = []
        if score.strip("/"):
            context_bits.append(f"score {score}")
        if balls:
            context_bits.append(f"balls left {balls}")
        if rrr and rrr != "nan":
            context_bits.append(f"rrr {rrr}")
        if phase:
            context_bits.append(f"phase {phase}")
        context = ", ".join(context_bits)
        label = row.get("ball_number") or f"{row.get('over')}.{row.get('ball_in_over')}"
        lines.append(f"{label}: {context}")
    return "\n".join(line for line in lines if line.strip())


def build_event_lines(events, state_rows):
    state_by_ball = {int(r.get("ball_in_over") or 0): r for r in state_rows}
    lines = []
    for event in events:
        ball_in_over = int(event.get("ball_in_over") or 0)
        snippet = extract_snippet(event.get("commentary") or "")
        line = f"{event.get('ball_number')} {event.get('batsman')} - {event.get('result_raw')} [{event.get('event_token')}]"
        if snippet:
            line += f" ({snippet})"
        state = state_by_ball.get(ball_in_over)
        if state:
            score = f"{state.get('innings_runs')}/{state.get('innings_wickets')}"
            line += f" | score {score}"
        lines.append(line)
    return "\n".join(lines)


def is_valid_longform(text, summary, allowed_names=None):
    if not text:
        return False
    over_num = summary.get("over_num")
    if over_num is not None and f"End of over {over_num}" not in text:
        return False
    if "Previous over:" not in text:
        return False
    if allowed_names and not validate_names_in_text(text, allowed_names):
        return False
    return True


def build_longform_fallback(events, summary, prev_summary):
    lines = []
    if prev_summary:
        lines.append(f"Previous over: {prev_summary}")
    over_num = summary.get("over_num")
    lines.append(f"Over {over_num} begins.")
    for event in events:
        snippet = extract_snippet(event.get("commentary") or "")
        base = f"{event.get('batsman')} on strike, {event.get('result_raw')}."
        if snippet:
            base += f" {snippet}"
        lines.append(base.rstrip(".") + "..." )
    wicket_phrase = summary.get("wicket_phrase") or ""
    lines.append(f"End of over {over_num}: {summary.get('runs')} runs{wicket_phrase}.")
    paragraph = " ".join(line.strip() for line in lines if line.strip())
    return textwrap.fill(paragraph, width=160)


def generate_longform_over(rows, all_rows, state_rows, style, config, use_llm=True, model=None):
    if not rows:
        return ""
    summary = build_summary(rows)
    if not summary:
        return ""
    events = build_over_events(rows)
    prev_summary = build_previous_over_summary(rows, all_rows, style)
    allowed_names = build_allowed_names(events)
    bowler = next((e.get("bowler") for e in events if e.get("bowler")), "")
    batsmen = sorted({e.get("batsman") for e in events if e.get("batsman")})
    batsmen_text = ", ".join(batsmen[:3])

    if use_llm and config:
        prompts_dir = Path(__file__).resolve().parent / "prompts"
        system_text = (prompts_dir / "longform_system.txt").read_text(encoding="utf-8")
        user_template = (prompts_dir / "longform_user.txt").read_text(encoding="utf-8")
        values = {
            "style": style,
            "over_num": summary.get("over_num"),
            "runs": summary.get("runs"),
            "wickets": summary.get("wicket_count"),
            "wicket_phrase": summary.get("wicket_phrase"),
            "bowler": bowler,
            "batsmen": batsmen_text,
            "allowed_names": ", ".join(sorted(allowed_names)),
            "previous_over": prev_summary,
            "events": build_event_lines(events, state_rows),
            "ball_state": build_ball_state_lines(state_rows),
        }
        user_text = user_template
        for key, value in values.items():
            user_text = user_text.replace("{{" + key + "}}", str(value))
        prompt = system_text.strip() + "\n\n" + user_text.strip()
        llm_text = generate_with_llm(prompt, config, model_override=model)
        if llm_text and is_valid_longform(llm_text, summary, allowed_names=allowed_names):
            return llm_text
    return build_longform_fallback(events, summary, prev_summary)


def main():
    parser = argparse.ArgumentParser(description="Generate long-form over commentary using KG context.")
    parser.add_argument("--config", default=None, help="Path to config.toml")
    parser.add_argument("--match", default=None, help="Match id (default: first match)")
    parser.add_argument("--innings", type=int, default=2, help="Innings number")
    parser.add_argument("--over", type=int, default=4, help="Over (ordinal, 1-50)")
    parser.add_argument("--style", default="broadcast", help="Style")
    parser.add_argument("--model", default=None, help="Override LLM model")
    parser.add_argument("--no-llm", action="store_true", help="Disable LLM and use fallback")
    parser.add_argument("--output-dir", default="agentic/longform/outputs", help="Output directory")
    args = parser.parse_args()

    config = load_config(args.config)
    overs_path = get_path(config, "overs_jsonl", section="files")
    rows, _ = load_overs(Path(overs_path))
    match_id = args.match or (rows[0].get("match_id") if rows else None)

    target_over = args.over - 1
    over_rows = [
        row
        for row in rows
        if row.get("match_id") == match_id
        and int(row.get("innings_index") or 0) == args.innings
        and int(row.get("over") or 0) == target_over
    ]

    kg_state_path = get_path(config, "kg_ball_state_csv", section="files")
    if not kg_state_path.exists():
        kg_state_path = get_path(config, "balls_enriched_csv", section="files")

    state_rows = load_ball_state(kg_state_path, match_id, args.innings, args.over)

    output = generate_longform_over(
        over_rows,
        rows,
        state_rows,
        args.style,
        config,
        use_llm=not args.no_llm,
        model=args.model,
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.output_dir) / f"run_{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"longform_innings{args.innings}_over{args.over}.md"

    llm_label = "disabled" if args.no_llm else "enabled"
    lines = [
        "# Long-form over commentary",
        f"match_id: {match_id}",
        f"innings: {args.innings}",
        f"over: {args.over}",
        f"style: {args.style}",
        f"llm: {llm_label}",
        "",
        output,
    ]
    out_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")

    print(out_path)


if __name__ == "__main__":
    main()
