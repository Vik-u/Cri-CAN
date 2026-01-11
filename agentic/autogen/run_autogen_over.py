#!/usr/bin/env python3
import argparse
import sys
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
    generate_over_script,
    is_valid_over_script,
    load_overs,
)
from agentic.agent_helpers import extract_ball_lines, format_ball_lines_with_llm, force_ball_lines
from agentic.kg_context import build_pressure_hint, format_ball_state_lines, load_ball_state_rows
from agentic.style_guide import get_style_guidance
import autogen
import re


def load_over_rows(rows, match_id, innings, over_ordinal):
    target_over = over_ordinal - 1
    return [
        row
        for row in rows
        if row.get("match_id") == match_id
        and int(row.get("innings_index") or 0) == innings
        and int(row.get("over") or 0) == target_over
    ]


def build_context(rows, all_rows, style, state_rows):
    summary = build_summary(rows)
    events = build_over_events(rows)
    prev_summary = build_previous_over_summary(rows, all_rows, style)
    allowed_names = build_allowed_names(events)
    style_guidance = get_style_guidance(style)
    ball_state = format_ball_state_lines(state_rows)
    pressure_hint = build_pressure_hint(state_rows)
    event_lines = []
    for event in events:
        line = f"{event['batsman']} - {event['result_raw']} [{event['event_token']}]"
        snippet = extract_snippet(event.get("commentary") or "")
        if snippet:
            line += f" ({snippet})"
        event_lines.append(line)
    return {
        "summary": summary,
        "events": event_lines,
        "previous_over": prev_summary,
        "allowed_names": sorted(allowed_names),
        "style_guidance": style_guidance,
        "ball_state": ball_state,
        "pressure_hint": pressure_hint,
    }


def extract_snippet(text, limit=160):
    clean = " ".join((text or "").split())
    if not clean:
        return ""
    parts = re.split(r"(?<=[.!?])\\s+", clean)
    first = parts[0] if parts else clean
    if len(first) < 20 and len(parts) > 1:
        first = parts[1]
    if len(first) > limit:
        trimmed = first[:limit].rsplit(" ", 1)[0].rstrip(".")
        return trimmed + "..."
    return first


def normalize_reply(reply):
    if isinstance(reply, dict):
        return reply.get("content") or ""
    return reply or ""


def run_autogen(rows, all_rows, match_id, innings, over_ordinal, style, model, base_url, config):
    over_rows = load_over_rows(rows, match_id, innings, over_ordinal)
    if not over_rows:
        return None, "No rows matched the requested over."

    kg_state_path = get_path(config, "kg_ball_state_csv", section="files")
    if not kg_state_path.exists():
        kg_state_path = get_path(config, "balls_enriched_csv", section="files")
    state_rows = load_ball_state_rows(kg_state_path, match_id, innings, over_ordinal)

    context = build_context(over_rows, all_rows, style, state_rows)
    summary = context["summary"]
    allowed_names = context["allowed_names"]

    llm_config = {
        "config_list": [
            {
                "model": model,
                "api_key": "ollama",
                "base_url": base_url,
                "timeout": 60,
            }
        ],
        "temperature": 0.7,
    }

    planner = autogen.AssistantAgent(
        name="planner",
        llm_config=llm_config,
        system_message="You plan the key beats of an over without inventing details.",
    )
    writer = autogen.AssistantAgent(
        name="writer",
        llm_config=llm_config,
        system_message="You write a smooth, live-sounding over commentary.",
    )
    critic = autogen.AssistantAgent(
        name="critic",
        llm_config=llm_config,
        system_message="You verify accuracy and fix any factual errors.",
    )

    plan_prompt = (
        "List each delivery's key beat in order using the events below.\n"
        "For each ball, include one short phrase from the commentary in parentheses (verbatim).\n"
        f"Previous over summary: {context['previous_over']}\n"
        f"Events:\n- " + "\n- ".join(context["events"])
    )
    plan = normalize_reply(planner.generate_reply(messages=[{"role": "user", "content": plan_prompt}]))

    write_prompt = (
        "Write SIX short sentences, one per ball, in order.\n"
        "Do NOT include previous over summary or end-of-over summary.\n"
        "Label each line as: Ball 1: ..., Ball 2: ..., etc.\n"
        "Use at least one phrase from each ball's commentary snippet; avoid generic template lines.\n"
        "Each line should be 18-30 words and feel like live commentary.\n"
        f"Allowed player names: {', '.join(allowed_names)}\n"
        f"Over: {summary.get('over_num')} | Runs: {summary.get('runs')} | Wickets: {summary.get('wicket_count')}\n"
        f"Style: {style}. Guidance: {context['style_guidance']}\n"
        f"Pressure hint: {context['pressure_hint']}\n"
        f"Score context by ball:\n{context['ball_state']}\n"
        f"Plan:\n{plan}\n"
    )
    draft = normalize_reply(writer.generate_reply(messages=[{"role": "user", "content": write_prompt}]))

    critic_prompt = (
        "Check the draft for incorrect names, invented details, or generic filler. If any issues, rewrite the six lines.\n"
        f"Allowed names: {', '.join(allowed_names)}\n"
        f"Style: {style}. Guidance: {context['style_guidance']}\n"
        f"Draft:\n{draft}\n"
        "Keep the Ball 1..Ball 6 labels."
    )
    raw_lines = normalize_reply(critic.generate_reply(messages=[{"role": "user", "content": critic_prompt}]))
    ball_lines = extract_ball_lines(raw_lines)
    if len(ball_lines) != 6:
        ball_lines = format_ball_lines_with_llm(context["events"], load_config(None), model=model)
    if len(ball_lines) != 6:
        ball_lines = force_ball_lines(context["events"])
    if len(ball_lines) != 6:
        final_text = generate_over_script(
            over_rows,
            all_rows,
            style,
            config=load_config(None),
            use_llm=False,
        )
        return final_text, raw_lines

    combined = build_full_script(summary, context["previous_over"], ball_lines)
    if not is_valid_over_script(combined, summary, allowed_names=allowed_names):
        combined = generate_over_script(
            over_rows,
            all_rows,
            style,
            config=load_config(None),
            use_llm=False,
        )
    return combined, raw_lines


def main():
    parser = argparse.ArgumentParser(description="AutoGen over commentary demo.")
    parser.add_argument("--match", default=None, help="Match id (default: first match)")
    parser.add_argument("--innings", type=int, default=2, help="Innings number")
    parser.add_argument("--over", type=int, default=4, help="Over (ordinal, 1-50)")
    parser.add_argument("--style", default="broadcast", help="Style")
    parser.add_argument("--model", default="gpt-oss:20b", help="Ollama model")
    parser.add_argument("--base-url", default="http://localhost:11434/v1", help="Ollama OpenAI base URL")
    args = parser.parse_args()

    config = load_config(None)
    overs_path = get_path(config, "overs_jsonl", section="files")
    rows, _ = load_overs(Path(overs_path))
    match_id = args.match or (rows[0].get("match_id") if rows else None)

    output, raw_lines = run_autogen(
        rows,
        rows,
        match_id,
        args.innings,
        args.over,
        args.style,
        args.model,
        args.base_url,
        config,
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT_DIR / "agentic" / "outputs" / "autogen" / f"run_{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"autogen_innings{args.innings}_over{args.over}.md"

    lines = [
        "# AutoGen over commentary",
        f"match_id: {match_id}",
        f"innings: {args.innings}",
        f"over: {args.over}",
        f"style: {args.style}",
        "",
    ]
    if raw_lines is not None:
        lines.append("## raw_lines")
        lines.append(raw_lines)
        lines.append("")
    lines.append("## final")
    lines.append(output)

    out_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    print(out_path)


def build_full_script(summary, prev_summary, ball_lines):
    pieces = []
    if prev_summary:
        pieces.append(f"Previous over: {prev_summary}")
    pieces.append(f"Over {summary.get('over_num')} begins.")
    cleaned_lines = [strip_ball_prefix(line) for line in ball_lines]
    pieces.extend(cleaned_lines)
    wicket_phrase = summary.get("wicket_phrase") or ""
    pieces.append(f"End of over {summary.get('over_num')}: {summary.get('runs')} runs{wicket_phrase}.")
    return " ".join(piece.strip() for piece in pieces if piece.strip())


def strip_ball_prefix(line):
    clean = re.sub(r"Ball\s*\d+\s*[:\-]\s*", "", line, flags=re.IGNORECASE).strip()
    return clean or line


if __name__ == "__main__":
    main()
