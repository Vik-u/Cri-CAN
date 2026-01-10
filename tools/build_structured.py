#!/usr/bin/env python3
import argparse
import csv
import json
import re
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from config import get_path, load_config

BALL_RE = re.compile(r"^(\d+)\.(\d+)$")
END_OVER_RE = re.compile(r"^end of over\s+(\d+)", re.IGNORECASE)
INNING_RE = re.compile(r"^##\s+Inning", re.IGNORECASE)
SCORE_RE = re.compile(r"^([A-Z]{2,3}):\s*(\d+)/(\d+)")
DELIVERY_RE = re.compile(r"^(.*?) to (.*?), (.*)$")
TOKEN_RE = re.compile(r"^(•|W|\d+(?:nb|lb|b|w)?)$")


def parse_token(token):
    if token == "•":
        return 0, "dot"
    if token == "W":
        return 0, "wicket"
    m = re.match(r"^(\d+)(nb|lb|b|w)?$", token)
    if not m:
        return 0, ""
    runs = int(m.group(1))
    kind = m.group(2) or "run"
    return runs, kind


def next_nonempty(lines, start):
    i = start
    while i < len(lines) and not lines[i].strip():
        i += 1
    return i


def parse_file(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    ball_rows = []
    meta_rows = []
    innings_idx = 0
    innings_team = {}
    ball_index = 0

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        if INNING_RE.match(line):
            innings_idx += 1
            meta_rows.append(
                {
                    "innings_index": innings_idx,
                    "meta_type": "innings_header",
                    "over": "",
                    "text": line,
                }
            )
            i += 1
            continue

        m_ball = BALL_RE.match(line)
        if m_ball:
            if innings_idx == 0:
                innings_idx = 1
            over = int(m_ball.group(1))
            ball_in_over = int(m_ball.group(2))
            token = ""
            desc = ""

            j = next_nonempty(lines, i + 1)
            if j < len(lines) and TOKEN_RE.match(lines[j].strip()):
                token = lines[j].strip()
                j = next_nonempty(lines, j + 1)
            if j < len(lines):
                desc = lines[j].strip()
            bowler = ""
            batsman = ""
            result_raw = desc
            m_desc = DELIVERY_RE.match(desc)
            if m_desc:
                bowler, batsman, result_raw = m_desc.groups()

            k = j + 1
            commentary_lines = []
            while k < len(lines):
                nxt = lines[k].strip()
                if not nxt:
                    k += 1
                    continue
                if BALL_RE.match(nxt) or END_OVER_RE.match(nxt) or INNING_RE.match(nxt):
                    break
                commentary_lines.append(nxt)
                m_score = SCORE_RE.match(nxt)
                if m_score and innings_team.get(innings_idx) is None:
                    innings_team[innings_idx] = m_score.group(1)
                k += 1

            token_runs, token_type = parse_token(token)
            is_wicket = False
            if token == "W":
                is_wicket = True
            else:
                lowered = result_raw.lower()
                if "out" in lowered and "not out" not in lowered:
                    is_wicket = True

            ball_index += 1
            ball_rows.append(
                {
                    "ball_index": ball_index,
                    "innings_index": innings_idx,
                    "batting_team": "",
                    "over": over,
                    "ball_in_over": ball_in_over,
                    "ball_number": line,
                    "event_token": token,
                    "token_runs": token_runs,
                    "token_type": token_type,
                    "bowler": bowler,
                    "batsman": batsman,
                    "result_raw": result_raw,
                    "is_wicket": str(is_wicket).lower(),
                    "commentary": "\n".join(commentary_lines),
                }
            )
            i = k
            continue

        m_over = END_OVER_RE.match(line)
        if m_over:
            if innings_idx == 0:
                innings_idx = 1
            over = int(m_over.group(1))
            j = i + 1
            summary_lines = []
            while j < len(lines):
                nxt = lines[j].strip()
                if not nxt:
                    j += 1
                    continue
                if BALL_RE.match(nxt) or INNING_RE.match(nxt):
                    break
                summary_lines.append(nxt)
                m_score = SCORE_RE.match(nxt)
                if m_score and innings_team.get(innings_idx) is None:
                    innings_team[innings_idx] = m_score.group(1)
                j += 1
            meta_rows.append(
                {
                    "innings_index": innings_idx,
                    "meta_type": "over_summary",
                    "over": over,
                    "text": "\n".join(summary_lines),
                }
            )
            i = j
            continue

        m_score = SCORE_RE.match(line)
        if m_score and innings_team.get(innings_idx) is None:
            innings_team[innings_idx] = m_score.group(1)

        meta_rows.append(
            {
                "innings_index": innings_idx or 1,
                "meta_type": "meta",
                "over": "",
                "text": line,
            }
        )
        i += 1

    for row in ball_rows:
        team = innings_team.get(row["innings_index"], "")
        row["batting_team"] = team

    return ball_rows, meta_rows


def write_csv(path, fieldnames, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def build_csv(out_dir, ball_rows, meta_rows):
    out_dir.mkdir(exist_ok=True)

    ball_cols = [
        "match_id",
        "source_file",
        "ball_index",
        "innings_index",
        "batting_team",
        "over",
        "ball_in_over",
        "ball_number",
        "event_token",
        "token_runs",
        "token_type",
        "bowler",
        "batsman",
        "result_raw",
        "is_wicket",
        "commentary",
    ]

    meta_cols = [
        "match_id",
        "source_file",
        "innings_index",
        "meta_type",
        "over",
        "text",
    ]

    write_csv(out_dir / "balls.csv", ball_cols, ball_rows)
    write_csv(out_dir / "meta.csv", meta_cols, meta_rows)

    schema = out_dir / "schema.md"
    schema.write_text(
        "# Structured Commentary Schema\n\n"
        "## balls.csv\n"
        "- match_id: file stem\n"
        "- source_file: original txt file name\n"
        "- ball_index: sequential id per file\n"
        "- innings_index: 1-based inning index within file\n"
        "- batting_team: inferred from score lines (e.g., SL, IND)\n"
        "- over: over number\n"
        "- ball_in_over: ball number within over\n"
        "- ball_number: raw over.ball string\n"
        "- event_token: raw token line (e.g., •, 4, 1lb, W)\n"
        "- token_runs: numeric runs parsed from token\n"
        "- token_type: run|dot|wicket|nb|lb|b|w\n"
        "- bowler: parsed bowler name\n"
        "- batsman: parsed striker name\n"
        "- result_raw: raw result text after the comma\n"
        "- is_wicket: true/false derived from token or result text\n"
        "- commentary: extra lines between this ball and next event\n\n"
        "## meta.csv\n"
        "- match_id: file stem\n"
        "- source_file: original txt file name\n"
        "- innings_index: 1-based inning index within file\n"
        "- meta_type: innings_header|over_summary|meta\n"
        "- over: over number for over_summary rows\n"
        "- text: raw meta block or narrative line\n",
        encoding="utf-8",
    )


def build_sqlite(out_dir, ball_rows, meta_rows):
    out_dir.mkdir(exist_ok=True)
    db_path = out_dir / "commentary.sqlite"
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE balls (
            match_id TEXT,
            source_file TEXT,
            ball_index INTEGER,
            innings_index INTEGER,
            batting_team TEXT,
            over INTEGER,
            ball_in_over INTEGER,
            ball_number TEXT,
            event_token TEXT,
            token_runs INTEGER,
            token_type TEXT,
            bowler TEXT,
            batsman TEXT,
            result_raw TEXT,
            is_wicket TEXT,
            commentary TEXT
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE meta (
            match_id TEXT,
            source_file TEXT,
            innings_index INTEGER,
            meta_type TEXT,
            over INTEGER,
            text TEXT
        );
        """
    )

    cur.executemany(
        """
        INSERT INTO balls VALUES (
            :match_id, :source_file, :ball_index, :innings_index, :batting_team,
            :over, :ball_in_over, :ball_number, :event_token, :token_runs,
            :token_type, :bowler, :batsman, :result_raw, :is_wicket, :commentary
        )
        """,
        ball_rows,
    )
    cur.executemany(
        """
        INSERT INTO meta VALUES (
            :match_id, :source_file, :innings_index, :meta_type, :over, :text
        )
        """,
        meta_rows,
    )

    cur.execute("CREATE INDEX idx_balls_over ON balls(match_id, innings_index, over, ball_in_over)")
    cur.execute("CREATE INDEX idx_meta_over ON meta(match_id, innings_index, over)")
    conn.commit()
    conn.close()

    (out_dir / "schema.md").write_text(
        "# SQLite Schema\n\n"
        "Tables: balls, meta\n\n"
        "## balls\n"
        "- match_id: file stem\n"
        "- source_file: original txt file name\n"
        "- ball_index: sequential id per file\n"
        "- innings_index: 1-based inning index within file\n"
        "- batting_team: inferred from score lines (e.g., SL, IND)\n"
        "- over: over number\n"
        "- ball_in_over: ball number within over\n"
        "- ball_number: raw over.ball string\n"
        "- event_token: raw token line (e.g., •, 4, 1lb, W)\n"
        "- token_runs: numeric runs parsed from token\n"
        "- token_type: run|dot|wicket|nb|lb|b|w\n"
        "- bowler: parsed bowler name\n"
        "- batsman: parsed striker name\n"
        "- result_raw: raw result text after the comma\n"
        "- is_wicket: true/false derived from token or result text\n"
        "- commentary: extra lines between this ball and next event\n\n"
        "## meta\n"
        "- match_id: file stem\n"
        "- source_file: original txt file name\n"
        "- innings_index: 1-based inning index within file\n"
        "- meta_type: innings_header|over_summary|meta\n"
        "- over: over number for over_summary rows\n"
        "- text: raw meta block or narrative line\n\n"
        "Indexes:\n"
        "- idx_balls_over on balls(match_id, innings_index, over, ball_in_over)\n"
        "- idx_meta_over on meta(match_id, innings_index, over)\n",
        encoding="utf-8",
    )


def build_jsonl(out_dir, ball_rows, meta_rows):
    out_dir.mkdir(exist_ok=True)

    overs = defaultdict(list)
    for row in ball_rows:
        key = (row["match_id"], row["source_file"], row["innings_index"], row["over"])
        overs[key].append(row)

    over_summaries = {}
    narrative_lines = []
    for row in meta_rows:
        if row["meta_type"] == "over_summary" and row["over"] != "":
            key = (row["match_id"], row["source_file"], row["innings_index"], row["over"])
            over_summaries[key] = row["text"]
        elif row["meta_type"] != "over_summary":
            narrative_lines.append(row)

    overs_path = out_dir / "overs.jsonl"
    with overs_path.open("w", encoding="utf-8") as f:
        for key in sorted(overs.keys()):
            match_id, source_file, innings_index, over = key
            balls = sorted(overs[key], key=lambda r: r["ball_in_over"])
            payload = {
                "match_id": match_id,
                "source_file": source_file,
                "innings_index": innings_index,
                "over": over,
                "batting_team": balls[0].get("batting_team", "") if balls else "",
                "over_summary": over_summaries.get(key, ""),
                "balls": balls,
            }
            f.write(json.dumps(payload, ensure_ascii=True) + "\n")

    narrative_path = out_dir / "narrative.jsonl"
    with narrative_path.open("w", encoding="utf-8") as f:
        for row in narrative_lines:
            f.write(json.dumps(row, ensure_ascii=True) + "\n")

    (out_dir / "schema.md").write_text(
        "# JSONL Schema\n\n"
        "## overs.jsonl\n"
        "Each line is one over with a balls[] array and optional over_summary.\n"
        "- match_id: file stem\n"
        "- source_file: original txt file name\n"
        "- innings_index: 1-based inning index within file\n"
        "- over: over number\n"
        "- batting_team: inferred from score lines (e.g., SL, IND)\n"
        "- over_summary: raw over summary block (may be empty)\n"
        "- balls: array of ball objects with fields:\n"
        "  - match_id: file stem\n"
        "  - source_file: original txt file name\n"
        "  - ball_index: sequential id per file\n"
        "  - innings_index: 1-based inning index within file\n"
        "  - batting_team: inferred from score lines (e.g., SL, IND)\n"
        "  - over: over number\n"
        "  - ball_in_over: ball number within over\n"
        "  - ball_number: raw over.ball string\n"
        "  - event_token: raw token line (e.g., •, 4, 1lb, W)\n"
        "  - token_runs: numeric runs parsed from token\n"
        "  - token_type: run|dot|wicket|nb|lb|b|w\n"
        "  - bowler: parsed bowler name\n"
        "  - batsman: parsed striker name\n"
        "  - result_raw: raw result text after the comma\n"
        "  - is_wicket: true/false derived from token or result text\n"
        "  - commentary: extra lines between this ball and next event\n\n"
        "## narrative.jsonl\n"
        "Non-over-summary meta lines (innings headers, narrative blocks).\n"
        "- match_id: file stem\n"
        "- source_file: original txt file name\n"
        "- innings_index: 1-based inning index within file\n"
        "- meta_type: innings_header|meta\n"
        "- over: empty unless present in source\n"
        "- text: raw meta block or narrative line\n",
        encoding="utf-8",
    )


def benchmark_csv(path):
    start = time.perf_counter()
    rows = []
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    elapsed = time.perf_counter() - start
    return elapsed, len(rows)


def benchmark_jsonl(path):
    start = time.perf_counter()
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    elapsed = time.perf_counter() - start
    return elapsed, len(rows)


def benchmark_sqlite(path):
    start = time.perf_counter()
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM balls")
    balls = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM meta")
    meta = cur.fetchone()[0]
    conn.close()
    elapsed = time.perf_counter() - start
    return elapsed, balls, meta


def file_size(path):
    return path.stat().st_size


def main():
    parser = argparse.ArgumentParser(description="Build structured outputs from raw commentary.")
    parser.add_argument("--config", default=None, help="Path to config.toml")
    args = parser.parse_args()

    config = load_config(args.config)
    raw_dir = get_path(config, "raw_dir")
    raw_glob = config.get("build", {}).get("raw_glob", "*.txt")
    ball_rows = []
    meta_rows = []

    for path in sorted(raw_dir.glob(raw_glob)):
        balls, meta = parse_file(path)
        match_id = path.stem
        for row in balls:
            row["source_file"] = path.name
            row["match_id"] = match_id
        for row in meta:
            row["source_file"] = path.name
            row["match_id"] = match_id
        ball_rows.extend(balls)
        meta_rows.extend(meta)

    csv_dir = get_path(config, "structured_csv_dir")
    json_dir = get_path(config, "structured_jsonl_dir")
    sqlite_dir = get_path(config, "structured_sqlite_dir")

    build_csv(csv_dir, ball_rows, meta_rows)
    build_sqlite(sqlite_dir, ball_rows, meta_rows)
    build_jsonl(json_dir, ball_rows, meta_rows)

    report = []

    csv_time, csv_rows = benchmark_csv(csv_dir / "balls.csv")
    csv_meta_time, csv_meta_rows = benchmark_csv(csv_dir / "meta.csv")
    report.append({
        "format": "csv",
        "balls_rows": csv_rows,
        "meta_rows": csv_meta_rows,
        "load_seconds": round(csv_time + csv_meta_time, 4),
        "total_bytes": file_size(csv_dir / "balls.csv") + file_size(csv_dir / "meta.csv"),
    })

    json_time, json_rows = benchmark_jsonl(json_dir / "overs.jsonl")
    narrative_time, narrative_rows = benchmark_jsonl(json_dir / "narrative.jsonl")
    report.append({
        "format": "jsonl",
        "overs_rows": json_rows,
        "narrative_rows": narrative_rows,
        "load_seconds": round(json_time + narrative_time, 4),
        "total_bytes": file_size(json_dir / "overs.jsonl") + file_size(json_dir / "narrative.jsonl"),
    })

    sqlite_time, balls_count, meta_count = benchmark_sqlite(sqlite_dir / "commentary.sqlite")
    report.append({
        "format": "sqlite",
        "balls_rows": balls_count,
        "meta_rows": meta_count,
        "load_seconds": round(sqlite_time, 4),
        "total_bytes": file_size(sqlite_dir / "commentary.sqlite"),
    })

    report_path = get_path(config, "structured_report")
    with report_path.open("w", encoding="utf-8") as f:
        f.write("# Structured Data Report\n\n")
        f.write("All metrics measured locally by reading full datasets into memory.\n\n")
        for row in report:
            f.write("## {format}\n".format(**row))
            for k, v in row.items():
                if k == "format":
                    continue
                f.write(f"- {k}: {v}\n")
            f.write("\n")


if __name__ == "__main__":
    main()
