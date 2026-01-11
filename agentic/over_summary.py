#!/usr/bin/env python3
from agentic.style_templates import render_over

EXTRA_TYPES = {"b", "lb", "nb", "w"}


def build_summary(rows):
    if not rows:
        return {}

    over = int(rows[0].get("over") or 0)
    over_num = over + 1
    runs = sum(int(r.get("token_runs") or 0) for r in rows)

    wickets = [r.get("batsman") for r in rows if str(r.get("is_wicket") or "").lower() == "true" or (r.get("event_token") or "") == "W"]
    unique = []
    for w in wickets:
        if w and w not in unique:
            unique.append(w)

    wicket_phrase = ""
    if unique:
        if len(unique) == 1:
            wicket_phrase = f", 1 wicket ({unique[0]})"
        else:
            wicket_phrase = f", {len(unique)} wickets"

    boundary_batsmen = []
    has_four = False
    has_six = False
    for r in rows:
        ball_runs = int(r.get("token_runs") or 0)
        if ball_runs == 4:
            has_four = True
        if ball_runs >= 6:
            has_six = True
        if ball_runs >= 4:
            name = r.get("batsman")
            if name and name not in boundary_batsmen:
                boundary_batsmen.append(name)

    boundary_batsmen_text = " and ".join(boundary_batsmen)

    extras_runs = sum(int(r.get("token_runs") or 0) for r in rows if (r.get("token_type") or "").lower() in EXTRA_TYPES)

    return {
        "over_num": over_num,
        "runs": runs,
        "wicket_phrase": wicket_phrase,
        "wicket_count": len(unique),
        "boundary_batsmen_list": boundary_batsmen,
        "boundary_batsmen": boundary_batsmen_text if boundary_batsmen_text else "",
        "boundary_count": len(boundary_batsmen),
        "has_four": has_four,
        "has_six": has_six,
        "extras_runs": extras_runs,
    }


def summarize_over(rows, style, seed_key):
    summary = build_summary(rows)
    if not summary:
        return ""
    return render_over(style, summary, seed_key)
