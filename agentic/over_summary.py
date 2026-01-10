#!/usr/bin/env python3
from style_templates import render_over

EXTRA_TYPES = {"b", "lb", "nb", "w"}


def summarize_over(rows, style, seed_key):
    if not rows:
        return ""

    over = int(rows[0].get("over") or 0)
    over_num = over + 1
    runs = sum(int(r.get("token_runs") or 0) for r in rows)

    wickets = [r.get("batsman") for r in rows if str(r.get("is_wicket") or "").lower() == "true" or (r.get("event_token") or "") == "W"]
    wicket_phrase = ""
    if wickets:
        unique = []
        for w in wickets:
            if w and w not in unique:
                unique.append(w)
        if len(unique) == 1:
            wicket_phrase = f", 1 wicket ({unique[0]})"
        else:
            wicket_phrase = f", {len(unique)} wickets"

    boundary_batsmen = []
    for r in rows:
        if int(r.get("token_runs") or 0) >= 4:
            name = r.get("batsman")
            if name and name not in boundary_batsmen:
                boundary_batsmen.append(name)

    boundary_batsmen_text = " and ".join(boundary_batsmen)

    extras_runs = sum(int(r.get("token_runs") or 0) for r in rows if (r.get("token_type") or "").lower() in EXTRA_TYPES)

    summary = {
        "over_num": over_num,
        "runs": runs,
        "wicket_phrase": wicket_phrase,
        "boundary_batsmen_list": boundary_batsmen,
        "boundary_batsmen": boundary_batsmen_text if boundary_batsmen_text else "",
        "extras_runs": extras_runs,
    }

    return render_over(style, summary, seed_key)
