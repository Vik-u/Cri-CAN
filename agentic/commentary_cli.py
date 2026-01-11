#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR))

from config import get_path, load_config
from agentic.commentary_core import (
    generate_deterministic_lines,
    generate_over_lines,
    generate_over_sequence,
    generate_template_lines,
    load_overs,
)


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
    parser.add_argument("--style", default=None, help="Style: broadcast|funny|serious|methodical|energetic|roasting|panel")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of balls")
    parser.add_argument("--llm", action="store_true", help="Use LLM for generation")
    parser.add_argument("--model", default=None, help="Override LLM model")
    parser.add_argument("--mode", default="template", help="Mode: deterministic|template|llm")
    parser.add_argument("--granularity", default="ball", help="Granularity: ball|over")
    parser.add_argument("--over-format", default="summary", help="Over format: summary|ball|ball+summary")
    parser.add_argument("--output", default=None, help="Output file (stdout if omitted)")
    args = parser.parse_args()

    config = load_config(args.config)
    input_path = get_path(config, "overs_jsonl", section="files")
    rows, over_summaries = load_overs(input_path)

    if not args.match and rows:
        args.match = rows[0].get("match_id")

    style = args.style or config.get("agentic", {}).get("default_style", "broadcast")

    filters = {
        "match_id": args.match,
        "innings": args.innings,
        "team": args.team,
        "over": args.over,
        "over_ordinal": args.over_ordinal,
        "bowler": args.bowler,
        "batsman": args.batsman,
        "boundary": args.boundary,
        "wicket": args.wicket,
        "event": args.event,
        "start": args.start,
        "end": args.end,
        "limit": args.limit,
    }

    lines = [
        f"# commentary-cli",
        f"# match_id: {args.match or 'unknown'}",
        f"# style: {style}",
        f"# mode: {args.mode}",
        f"# granularity: {args.granularity}",
    ]

    if args.mode == "deterministic":
        lines.extend(generate_deterministic_lines(rows, filters))
    elif args.granularity == "over":
        use_llm = args.mode == "llm" or args.llm
        if args.over_format == "summary":
            lines.extend(generate_over_lines(rows, filters, style, config=config, use_llm=use_llm, model=args.model))
        else:
            include_summary = args.over_format == "ball+summary"
            lines.extend(
                generate_over_sequence(
                    rows,
                    over_summaries,
                    config,
                    filters,
                    style,
                    mode=args.mode,
                    use_llm=use_llm,
                    model=args.model,
                    include_summary=include_summary,
                )
            )
    else:
        use_llm = args.mode == "llm" or args.llm
        lines.extend(generate_template_lines(rows, over_summaries, config, filters, style, use_llm=use_llm, model=args.model))

    output = "\n".join(lines) + "\n"
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
