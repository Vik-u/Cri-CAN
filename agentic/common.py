#!/usr/bin/env python3
import time
from pathlib import Path


def _shorten(text, limit=240):
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3].rstrip() + "..."


def _event_type(row):
    token_type = (row.get("token_type") or "").lower()
    token_runs = int(row.get("token_runs") or 0)
    event_token = (row.get("event_token") or "").strip()
    is_wicket = str(row.get("is_wicket") or "").lower() == "true"

    if is_wicket or event_token == "W":
        return "wicket"
    if token_type in {"b", "lb", "nb", "w"}:
        return "extra"
    if token_runs >= 4:
        return "boundary"
    if token_runs == 0:
        return "dot"
    return "run"


def _compose_line(row, state):
    over = row.get("over")
    ball = row.get("ball_in_over")
    bowler = row.get("bowler") or ""
    batsman = row.get("batsman") or ""
    token_runs = int(row.get("token_runs") or 0)
    result_raw = row.get("result_raw") or ""
    event = _event_type(row)

    if event == "wicket":
        line = f"{over}.{ball} {bowler} to {batsman}, OUT. {result_raw}".strip()
    elif event == "boundary":
        line = f"{over}.{ball} {bowler} to {batsman}, {token_runs} runs. {result_raw}".strip()
    elif event == "extra":
        line = f"{over}.{ball} {bowler} to {batsman}, {token_runs} extra(s). {result_raw}".strip()
    elif event == "dot":
        line = f"{over}.{ball} {bowler} to {batsman}, no run. {result_raw}".strip()
    else:
        line = f"{over}.{ball} {bowler} to {batsman}, {token_runs} run(s). {result_raw}".strip()

    # Fact-check style: ensure bowler and batsman are present.
    if bowler and bowler not in line:
        line = f"{bowler} {line}"
    if batsman and batsman not in line:
        line = f"{line} ({batsman})"

    return " ".join(line.split())


def _update_state(row, state):
    innings = int(row.get("innings_index") or 1)
    token_runs = int(row.get("token_runs") or 0)
    is_wicket = str(row.get("is_wicket") or "").lower() == "true"

    if state["innings"] != innings:
        state["innings"] = innings
        state["runs"] = 0
        state["wickets"] = 0
        state["balls"] = 0

    state["runs"] += token_runs
    if is_wicket:
        state["wickets"] += 1
    state["balls"] += 1


def generate_commentary(rows, limit=None, header_lines=None):
    lines = []
    if header_lines:
        lines.extend(header_lines)
    state = {"innings": None, "runs": 0, "wickets": 0, "balls": 0}

    for idx, row in enumerate(rows):
        if limit is not None and idx >= limit:
            break
        _update_state(row, state)
        line = _compose_line(row, state)
        lines.append(line)

        commentary = row.get("commentary") or ""
        if commentary.strip():
            lines.append("Context: " + _shorten(commentary))

    return lines


def write_output(lines, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def timer(fn, *args, **kwargs):
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    elapsed = time.perf_counter() - start
    return result, elapsed
