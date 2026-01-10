#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

AGENTIC_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.append(str(AGENTIC_DIR))
sys.path.append(str(ROOT_DIR))

from common import generate_commentary, timer, write_output
from config import get_path, load_config


def load_balls(path):
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            payload = json.loads(line)
            for ball in payload.get("balls", []):
                rows.append(ball)
    rows.sort(key=lambda r: (r.get("match_id"), r.get("innings_index"), r.get("over"), r.get("ball_in_over"), r.get("ball_index")))
    return rows


def main():
    parser = argparse.ArgumentParser(description="Generate text-only agentic commentary from JSONL.")
    parser.add_argument("--config", default=None, help="Path to config.toml")
    parser.add_argument("--input", default=None, help="Path to overs.jsonl")
    parser.add_argument("--limit", type=int, default=None, help="Number of balls to generate")
    parser.add_argument("--output", default=None, help="Output text file")
    args = parser.parse_args()

    config = load_config(args.config)
    default_input = get_path(config, "overs_jsonl", section="files")
    default_output = get_path(config, "output_jsonl", section="agentic")
    default_limit = config.get("agentic", {}).get("default_limit", 60)

    input_path = Path(args.input) if args.input else default_input
    output_path = Path(args.output) if args.output else default_output
    limit = args.limit if args.limit is not None else default_limit

    header_lines = [
        f"# {config.get('agentic', {}).get('v0_label', 'v0-deterministic')}",
        "# deterministic: derived directly from parsed source commentary",
    ]

    rows, load_seconds = timer(load_balls, input_path)
    lines, gen_seconds = timer(generate_commentary, rows, limit, header_lines=header_lines)
    write_output(lines, output_path)

    print(f"rows={len(rows)} load_seconds={load_seconds:.4f} gen_seconds={gen_seconds:.4f} output={output_path}")


if __name__ == "__main__":
    main()
