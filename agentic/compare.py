#!/usr/bin/env python3
import argparse
import csv
import json
import sqlite3
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR))

from common import generate_commentary
from config import get_path, load_config


def load_csv(path):
    rows = []
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            for key in ["ball_index", "innings_index", "over", "ball_in_over", "token_runs"]:
                if key in row and row[key] != "":
                    row[key] = int(row[key])
            rows.append(row)
    rows.sort(key=lambda r: (r.get("match_id"), r.get("innings_index"), r.get("over"), r.get("ball_in_over"), r.get("ball_index")))
    return rows


def load_sqlite(path):
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


def load_jsonl(path):
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


def time_it(fn, *args):
    start = time.perf_counter()
    result = fn(*args)
    elapsed = time.perf_counter() - start
    return result, elapsed


def main():
    parser = argparse.ArgumentParser(description="Compare agentic pipeline performance.")
    parser.add_argument("--config", default=None, help="Path to config.toml")
    args = parser.parse_args()

    config = load_config(args.config)
    csv_path = get_path(config, "balls_csv", section="files")
    sqlite_path = get_path(config, "sqlite_db", section="files")
    jsonl_path = get_path(config, "overs_jsonl", section="files")

    report = []

    rows, load_s = time_it(load_csv, csv_path)
    _, gen_s = time_it(generate_commentary, rows, None)
    report.append({"format": "csv", "rows": len(rows), "load_s": load_s, "gen_s": gen_s, "total_s": load_s + gen_s})

    rows, load_s = time_it(load_sqlite, sqlite_path)
    _, gen_s = time_it(generate_commentary, rows, None)
    report.append({"format": "sqlite", "rows": len(rows), "load_s": load_s, "gen_s": gen_s, "total_s": load_s + gen_s})

    rows, load_s = time_it(load_jsonl, jsonl_path)
    _, gen_s = time_it(generate_commentary, rows, None)
    report.append({"format": "jsonl", "rows": len(rows), "load_s": load_s, "gen_s": gen_s, "total_s": load_s + gen_s})

    out = get_path(config, "agentic_report")
    with out.open("w", encoding="utf-8") as f:
        f.write("# Agentic Commentary Performance\n\n")
        f.write("Load + full generation timings (text-only).\n\n")
        for row in report:
            f.write(f"## {row['format']}\n")
            f.write(f"- rows: {row['rows']}\n")
            f.write(f"- load_seconds: {row['load_s']:.4f}\n")
            f.write(f"- generate_seconds: {row['gen_s']:.4f}\n")
            f.write(f"- total_seconds: {row['total_s']:.4f}\n\n")


if __name__ == "__main__":
    main()
