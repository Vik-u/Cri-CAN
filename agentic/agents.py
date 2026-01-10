#!/usr/bin/env python3
import random

EXTRA_TYPES = {"b", "lb", "nb", "w"}


class PlannerAgent:
    def plan(self, row, context_window):
        token_type = (row.get("token_type") or "").lower()
        token_runs = int(row.get("token_runs") or 0)
        event_token = (row.get("event_token") or "").strip()
        is_wicket = str(row.get("is_wicket") or "").lower() == "true"

        if is_wicket or event_token == "W":
            event_type = "wicket"
        elif token_type in EXTRA_TYPES:
            event_type = "extra"
        elif token_runs >= 4:
            event_type = "boundary"
        elif token_runs == 0:
            event_type = "dot"
        else:
            event_type = "run"

        tone = "excited" if event_type in {"wicket", "boundary"} else "calm"
        focus = "batsman" if event_type in {"boundary", "run"} else "bowler"

        return {
            "event_type": event_type,
            "tone": tone,
            "focus": focus,
        }


class StyleAgent:
    def __init__(self, renderer):
        self.renderer = renderer

    def render(self, plan, row, snippet=None):
        base = self.renderer(plan, row)
        if snippet:
            return base + " " + snippet
        return base


class FactCheckAgent:
    def verify(self, line, row):
        bowler = row.get("bowler") or ""
        batsman = row.get("batsman") or ""
        fixed = line
        if bowler and bowler not in fixed:
            fixed = f"From {bowler}, {fixed}"
        if batsman:
            last_name = batsman.split()[-1]
            if batsman not in fixed and last_name not in fixed:
                fixed = fixed + f" ({batsman})"
        return fixed
