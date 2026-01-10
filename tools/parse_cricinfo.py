#!/usr/bin/env python3
import argparse
import csv
import re
import sys
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


def main():
    parser = argparse.ArgumentParser(description="Legacy CSV parser for raw commentary files.")
    parser.add_argument("--config", default=None, help="Path to config.toml")
    args = parser.parse_args()

    config = load_config(args.config)
    raw_dir = get_path(config, "raw_dir")
    out_dir = get_path(config, "legacy_csv_dir")
    raw_glob = config.get("build", {}).get("raw_glob", "*.txt")
    out_dir.mkdir(exist_ok=True)

    all_ball_rows = []
    all_meta_rows = []

    for path in sorted(raw_dir.glob(raw_glob)):
        ball_rows, meta_rows = parse_file(path)
        match_id = path.stem
        for row in ball_rows:
            row["source_file"] = path.name
            row["match_id"] = match_id
        for row in meta_rows:
            row["source_file"] = path.name
            row["match_id"] = match_id
        all_ball_rows.extend(ball_rows)
        all_meta_rows.extend(meta_rows)

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

    write_csv(out_dir / "balls.csv", ball_cols, all_ball_rows)
    write_csv(out_dir / "meta.csv", meta_cols, all_meta_rows)

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


if __name__ == "__main__":
    main()
