#!/usr/bin/env python3
import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from config import get_path, load_config

EXTRA_TYPES = {"b", "lb", "nb", "w"}
NON_LEGAL_TYPES = {"nb", "w"}


def classify_event(row):
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


def parse_token_runs(token):
    token = (token or "").strip()
    if token == "\u2022":
        return 0
    if token == "W":
        return 0
    if token and token[0].isdigit():
        digits = ""
        for ch in token:
            if ch.isdigit():
                digits += ch
            else:
                break
        return int(digits) if digits else 0
    return None


def load_balls(path):
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


def write_csv(path, fieldnames, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(description="Derive stats and QA checks for balls.csv")
    parser.add_argument("--config", default=None, help="Path to config.toml")
    args = parser.parse_args()

    config = load_config(args.config)
    balls_path = get_path(config, "balls_csv", section="files")
    out_path = get_path(config, "balls_enriched_csv", section="files")
    qa_path = get_path(config, "qa_report", section="files")

    rows = load_balls(balls_path)

    innings_totals = defaultdict(int)
    for row in rows:
        innings_totals[(row.get("match_id"), row.get("innings_index"))] += int(row.get("token_runs") or 0)

    inning_state = defaultdict(lambda: {"runs": 0, "wickets": 0, "ball_index": 0, "legal_balls": 0, "last_over": None, "last_ball_index": None})
    qa = {
        "total_rows": len(rows),
        "missing_bowler": 0,
        "missing_batsman": 0,
        "missing_result": 0,
        "invalid_ball_in_over": 0,
        "invalid_token_type": 0,
        "missing_ball_number": 0,
        "invalid_ball_number": 0,
        "missing_event_token": 0,
        "token_runs_mismatch": 0,
        "non_monotonic_over": 0,
        "non_monotonic_ball_index": 0,
    }

    valid_token_types = {"run", "dot", "wicket", "nb", "lb", "b", "w", ""}

    enriched = []
    for row in rows:
        key = (row.get("match_id"), row.get("innings_index"))
        state = inning_state[key]
        state["ball_index"] += 1

        token_runs = int(row.get("token_runs") or 0)
        token_type = (row.get("token_type") or "").lower()
        event_type = classify_event(row)
        is_extra = token_type in EXTRA_TYPES
        is_legal = token_type not in NON_LEGAL_TYPES
        extras_runs = token_runs if is_extra else 0
        bat_runs = token_runs if token_type in {"run", ""} else 0
        is_boundary = token_runs >= 4

        state["runs"] += token_runs
        if str(row.get("is_wicket") or "").lower() == "true":
            state["wickets"] += 1
        if is_legal:
            state["legal_balls"] += 1

        if state["last_over"] is not None and row.get("over") is not None:
            if int(row.get("over")) < int(state["last_over"]):
                qa["non_monotonic_over"] += 1
        state["last_over"] = row.get("over")

        if state["last_ball_index"] is not None and row.get("ball_index") is not None:
            if int(row.get("ball_index")) < int(state["last_ball_index"]):
                qa["non_monotonic_ball_index"] += 1
        state["last_ball_index"] = row.get("ball_index")

        ball_in_over = row.get("ball_in_over")
        if ball_in_over is None or not (1 <= int(ball_in_over) <= 6):
            qa["invalid_ball_in_over"] += 1

        if token_type not in valid_token_types:
            qa["invalid_token_type"] += 1

        ball_number = row.get("ball_number") or ""
        if not ball_number:
            qa["missing_ball_number"] += 1
        elif "." not in ball_number:
            qa["invalid_ball_number"] += 1

        if not (row.get("event_token") or "").strip():
            qa["missing_event_token"] += 1

        expected_runs = parse_token_runs(row.get("event_token"))
        if expected_runs is not None and expected_runs != token_runs:
            qa["token_runs_mismatch"] += 1

        if not (row.get("bowler") or "").strip():
            qa["missing_bowler"] += 1
        if not (row.get("batsman") or "").strip():
            qa["missing_batsman"] += 1
        if not (row.get("result_raw") or "").strip():
            qa["missing_result"] += 1

        legal_balls = state["legal_balls"]
        overs = legal_balls / 6 if legal_balls else 0
        crr = round(state["runs"] / overs, 2) if overs else ""

        target_runs = ""
        runs_remaining = ""
        balls_remaining = ""
        rrr = ""
        if row.get("innings_index") and int(row.get("innings_index")) > 1:
            target_runs = innings_totals.get((row.get("match_id"), 1), 0) + 1
            runs_remaining = max(0, target_runs - state["runs"])
            balls_remaining = max(0, 300 - legal_balls)
            overs_remaining = balls_remaining / 6 if balls_remaining else 0
            if overs_remaining:
                rrr = round(runs_remaining / overs_remaining, 2)

        over_number = int(row.get("over") or 0)
        if over_number < 10:
            phase = "powerplay"
        elif over_number < 40:
            phase = "middle"
        else:
            phase = "death"

        new_row = dict(row)
        new_row.update(
            {
                "innings_ball_index": state["ball_index"],
                "innings_runs": state["runs"],
                "innings_wickets": state["wickets"],
                "innings_legal_balls": legal_balls,
                "innings_overs": round(overs, 2) if overs else "",
                "crr": crr,
                "target_runs": target_runs,
                "runs_remaining": runs_remaining,
                "balls_remaining": balls_remaining,
                "rrr": rrr,
                "phase": phase,
                "event_type": event_type,
                "is_boundary": str(is_boundary).lower(),
                "is_extra": str(is_extra).lower(),
                "is_legal_ball": str(is_legal).lower(),
                "extras_runs": extras_runs,
                "bat_runs": bat_runs,
            }
        )
        enriched.append(new_row)

    fieldnames = list(enriched[0].keys()) if enriched else []
    write_csv(out_path, fieldnames, enriched)

    qa_lines = [
        "# QA Report\n",
        f"- total_rows: {qa['total_rows']}",
        f"- missing_bowler: {qa['missing_bowler']}",
        f"- missing_batsman: {qa['missing_batsman']}",
        f"- missing_result: {qa['missing_result']}",
        f"- invalid_ball_in_over: {qa['invalid_ball_in_over']}",
        f"- invalid_token_type: {qa['invalid_token_type']}",
        f"- missing_ball_number: {qa['missing_ball_number']}",
        f"- invalid_ball_number: {qa['invalid_ball_number']}",
        f"- missing_event_token: {qa['missing_event_token']}",
        f"- token_runs_mismatch: {qa['token_runs_mismatch']}",
        f"- non_monotonic_over: {qa['non_monotonic_over']}",
        f"- non_monotonic_ball_index: {qa['non_monotonic_ball_index']}",
        "",
        "Notes:",
        "- ball_in_over duplicates are expected for no-ball/wide cases in the source feed.",
        "- RRR is only populated for the second innings; target is innings1 total + 1.",
    ]
    qa_path.write_text("\n".join(qa_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
