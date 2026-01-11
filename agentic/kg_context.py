#!/usr/bin/env python3
import csv
from math import isfinite
from pathlib import Path


def safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_ball_state_rows(path, match_id, innings, over_ordinal):
    if not path or not Path(path).exists():
        return []
    target_over = over_ordinal - 1
    rows = []
    with Path(path).open(encoding="utf-8") as handle:
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


def format_ball_state_lines(state_rows):
    lines = []
    for row in state_rows:
        score = f"{row.get('innings_runs')}/{row.get('innings_wickets')}"
        bits = []
        if score.strip("/"):
            bits.append(f"score {score}")
        balls = row.get("balls_remaining")
        if balls:
            bits.append(f"balls left {balls}")
        rrr = row.get("rrr")
        if rrr and rrr != "nan":
            bits.append(f"rrr {rrr}")
        crr = row.get("crr")
        if crr and crr != "nan":
            bits.append(f"crr {crr}")
        phase = row.get("phase")
        if phase:
            bits.append(f"phase {phase}")
        label = row.get("ball_number") or f"{row.get('over')}.{row.get('ball_in_over')}"
        if bits:
            lines.append(f"{label}: {', '.join(bits)}")
    return "\n".join(lines)


def build_pressure_hint(state_rows):
    if not state_rows:
        return ""
    last = state_rows[-1]
    rrr = safe_float(last.get("rrr"))
    crr = safe_float(last.get("crr"))
    if rrr is None or crr is None or not isfinite(rrr) or not isfinite(crr):
        return ""
    diff = round(rrr - crr, 2)
    if diff >= 1.5:
        return f"Pressure rising: required rate is {diff} higher than current."
    if diff <= -1.5:
        return f"Chase comfortable: required rate is {-diff} lower than current."
    return "Even tempo: required and current rates are close."
