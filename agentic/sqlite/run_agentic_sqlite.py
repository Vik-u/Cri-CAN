#!/usr/bin/env python3
import argparse
import sqlite3
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
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM balls
        ORDER BY match_id, innings_index, over, ball_in_over, ball_index
        """
    )
    for row in cur.fetchall():
        rows.append(dict(row))
    conn.close()
    return rows


def main():
    parser = argparse.ArgumentParser(description="Generate text-only agentic commentary from SQLite.")
    parser.add_argument("--config", default=None, help="Path to config.toml")
    parser.add_argument("--input", default=None, help="Path to commentary.sqlite")
    parser.add_argument("--limit", type=int, default=None, help="Number of balls to generate")
    parser.add_argument("--output", default=None, help="Output text file")
    args = parser.parse_args()

    config = load_config(args.config)
    default_input = get_path(config, "sqlite_db", section="files")
    default_output = get_path(config, "output_sqlite", section="agentic")
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
