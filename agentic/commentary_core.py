#!/usr/bin/env python3
import json
import re
import textwrap
from pathlib import Path

from agentic.agents import FactCheckAgent, PlannerAgent, StyleAgent
from agentic.llm_adapter import generate_with_llm
from agentic.style_guide import get_style_guidance
from agentic.over_summary import build_summary, summarize_over
from agentic.style_templates import render_style

EXTRA_TYPES = {"b", "lb", "nb", "w"}


def load_overs(path):
    rows = []
    over_summaries = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            payload = json.loads(line)
            match_id = payload.get("match_id")
            innings_index = payload.get("innings_index")
            over = payload.get("over")
            if isinstance(innings_index, str) and innings_index.isdigit():
                innings_index = int(innings_index)
            if isinstance(over, str) and over.isdigit():
                over = int(over)
            summary = payload.get("over_summary") or ""
            if summary:
                over_summaries[(match_id, innings_index, over)] = " ".join(summary.split())[:160]
            for ball in payload.get("balls", []):
                for key in ["ball_index", "innings_index", "over", "ball_in_over", "token_runs"]:
                    if key in ball and ball[key] is not None and str(ball[key]).isdigit():
                        ball[key] = int(ball[key])
                rows.append(ball)
    rows.sort(key=lambda r: (r.get("match_id"), r.get("innings_index"), r.get("over"), r.get("ball_in_over"), r.get("ball_index")))
    return rows, over_summaries


def event_type(row):
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


def filter_rows(rows, filters):
    selected = rows
    match_id = filters.get("match_id")
    innings = filters.get("innings")
    team = filters.get("team")
    over = filters.get("over")
    over_ordinal = filters.get("over_ordinal")
    bowler = filters.get("bowler")
    batsman = filters.get("batsman")
    boundary = filters.get("boundary")
    wicket = filters.get("wicket")
    event = filters.get("event")
    start = filters.get("start")
    end = filters.get("end")
    limit = filters.get("limit")

    if match_id:
        selected = [r for r in selected if r.get("match_id") == match_id]
    if innings is not None:
        selected = [r for r in selected if int(r.get("innings_index") or 0) == innings]
    if team:
        selected = [r for r in selected if (r.get("batting_team") or "").lower() == team.lower()]
    if over is not None:
        target_over = over - 1 if over_ordinal else over
        selected = [r for r in selected if int(r.get("over") or 0) == target_over]
    if bowler:
        selected = [r for r in selected if bowler.lower() in (r.get("bowler") or "").lower()]
    if batsman:
        selected = [r for r in selected if batsman.lower() in (r.get("batsman") or "").lower()]
    if boundary:
        selected = [r for r in selected if int(r.get("token_runs") or 0) >= 4]
    if wicket:
        selected = [r for r in selected if str(r.get("is_wicket") or "").lower() == "true" or (r.get("event_token") or "") == "W"]
    if event:
        selected = [r for r in selected if event_type(r) == event]

    if start:
        if "." in start:
            over_s, ball_s = start.split(".", 1)
            start_over = int(over_s)
            start_ball = int(ball_s)
            selected = [
                r
                for r in selected
                if (int(r.get("over") or 0), int(r.get("ball_in_over") or 0)) >= (start_over, start_ball)
            ]
        else:
            start_idx = int(start)
            selected = [r for r in selected if int(r.get("ball_index") or 0) >= start_idx]

    if end:
        if "." in end:
            over_e, ball_e = end.split(".", 1)
            end_over = int(over_e)
            end_ball = int(ball_e)
            selected = [
                r
                for r in selected
                if (int(r.get("over") or 0), int(r.get("ball_in_over") or 0)) <= (end_over, end_ball)
            ]
        else:
            end_idx = int(end)
            selected = [r for r in selected if int(r.get("ball_index") or 0) <= end_idx]

    if limit is not None:
        selected = selected[:limit]

    return selected


def build_style_agent(style):
    return StyleAgent(lambda plan, row: render_style(
        style=style,
        event_type=plan["event_type"],
        bowler=row.get("bowler", ""),
        batsman=row.get("batsman", ""),
        runs=int(row.get("token_runs") or 0),
        seed_key=f"{row.get('match_id')}|{row.get('innings_index')}|{row.get('ball_number')}|{style}",
    ))


def panel_style_for_event(plan, row):
    event_type = plan.get("event_type")
    runs = int(row.get("token_runs") or 0)
    if event_type == "wicket":
        return "energetic"
    if event_type == "boundary":
        return "energetic" if runs >= 6 else "funny"
    if event_type == "extra":
        return "roasting"
    if event_type == "dot":
        return "serious"
    return "broadcast"


def render_template_line(row, over_summaries, config, style, use_llm, model, planner, fact_agent):
    plan = planner.plan(row, [])
    event_style = style
    if style == "panel":
        event_style = panel_style_for_event(plan, row)

    if use_llm and config:
        style_guidance = get_style_guidance(event_style)
        prompts_dir = Path(config["_root"]) / config.get("prompts", {}).get("jsonl_dir", "agentic/jsonl/prompts")
        system_text = (prompts_dir / "system.txt").read_text(encoding="utf-8")
        user_template = (prompts_dir / "user.txt").read_text(encoding="utf-8")
        key = (row.get("match_id"), row.get("innings_index"), row.get("over"))
        over_summary = over_summaries.get(key, "")
        values = {
            "style": event_style,
            "style_guidance": style_guidance,
            "bowler": row.get("bowler", ""),
            "batsman": row.get("batsman", ""),
            "event_type": plan["event_type"],
            "result_raw": row.get("result_raw", ""),
            "commentary": " ".join((row.get("commentary") or "").split())[:120],
            "over_summary": over_summary,
            "recent_overs": "",
            "context_window": "",
        }
        user_text = user_template
        for k, v in values.items():
            user_text = user_text.replace("{{" + k + "}}", str(v))
        prompt = system_text.strip() + "\n\n" + user_text.strip()
        llm_text = generate_with_llm(prompt, config, model_override=model)
        if llm_text:
            return fact_agent.verify(llm_text, row)

    return render_style(
        style=event_style,
        event_type=plan["event_type"],
        bowler=row.get("bowler", ""),
        batsman=row.get("batsman", ""),
        runs=int(row.get("token_runs") or 0),
        seed_key=f"{row.get('match_id')}|{row.get('innings_index')}|{row.get('ball_number')}|{event_style}",
    )


def is_valid_over_llm(text, summary):
    lower = text.lower()
    over_num = summary.get("over_num")
    runs = summary.get("runs")
    if over_num is not None and not re.search(rf"\b{over_num}\b", text):
        return False
    if runs is not None and not re.search(rf"\b{runs}\b", text):
        return False
    if summary.get("wicket_count", 0) == 0:
        if re.search(r"\b(dismiss|dismissed|out|gone|lbw|bowled|caught|stumped)\b", lower):
            return False
        if "run out" in lower:
            return False
    mentions_four = _mentions_four(lower)
    mentions_six = _mentions_six(lower)
    if summary.get("boundary_count", 0) == 0:
        if mentions_four or mentions_six or any(word in lower for word in ["boundary", "rope", "fence", "stands"]):
            return False
    if summary.get("has_six") is False and mentions_six:
        return False
    if summary.get("has_six") is True and not mentions_six:
        return False
    if summary.get("has_four") is False and mentions_four:
        return False
    if summary.get("has_four") is True and not mentions_four:
        return False
    return True


def is_valid_over_conversation(text, summary, allowed_names=None):
    lower = text.lower()
    if summary.get("wicket_count", 0) == 0:
        if re.search(r"\b(dismiss|dismissed|out|gone|lbw|bowled|caught|stumped)\b", lower):
            return False
        if "run out" in lower:
            return False
    mentions_four = _mentions_four(lower)
    mentions_six = _mentions_six(lower)
    if summary.get("boundary_count", 0) == 0:
        if mentions_four or mentions_six or any(word in lower for word in ["boundary", "rope", "fence", "stands"]):
            return False
    if summary.get("has_six") is False and mentions_six:
        return False
    if summary.get("has_four") is False and mentions_four:
        return False
    if summary.get("has_six") is True and not mentions_six:
        return False
    if summary.get("has_four") is True and not mentions_four:
        return False
    if allowed_names:
        if not validate_names_in_text(text, allowed_names):
            return False
    return True


def is_valid_over_script(text, summary, allowed_names=None):
    over_num = summary.get("over_num")
    if over_num is not None:
        if f"End of over {over_num}" not in text:
            return False
    if "Previous over:" not in text:
        return False
    return is_valid_over_conversation(text, summary, allowed_names=allowed_names)


def _mentions_four(lower):
    if re.search(r"\bfour\b", lower):
        if re.search(r"\bfour (balls|deliveries)\b", lower):
            return False
        return True
    if re.search(r"\bboundary\b", lower):
        return True
    if any(word in lower for word in ["rope", "fence", "stands"]):
        return True
    return False


def _mentions_six(lower):
    if re.search(r"\bsix\b", lower):
        if re.search(r"\bsix (balls|deliveries)\b", lower):
            return False
        return True
    if "sixer" in lower:
        return True
    return False


def generate_template_lines(rows, over_summaries, config, filters, style, use_llm=False, model=None):
    selected = filter_rows(rows, filters)
    planner = PlannerAgent()
    fact_agent = FactCheckAgent()

    lines = []
    for row in selected:
        line = render_template_line(
            row,
            over_summaries,
            config,
            style,
            use_llm,
            model,
            planner,
            fact_agent,
        )
        lines.append(line)

    return lines


def render_over_summary(rows, style, config=None, use_llm=False, model=None):
    if not rows:
        return ""
    summary = build_summary(rows)
    if not summary:
        return ""

    match_id = rows[0].get("match_id")
    innings_index = rows[0].get("innings_index")
    over = rows[0].get("over")
    seed_key = f"{match_id}|{innings_index}|{over}|{style}"

    summary_style = style
    if style == "panel":
        if summary.get("wicket_count", 0) > 0:
            summary_style = "energetic"
        elif summary.get("boundary_count", 0) > 0:
            summary_style = "funny"
        else:
            summary_style = "methodical"

    if use_llm and config:
        prompts_dir = Path(config["_root"]) / config.get("prompts", {}).get("jsonl_dir", "agentic/jsonl/prompts")
        system_text = (prompts_dir / "over_system.txt").read_text(encoding="utf-8")
        user_template = (prompts_dir / "over_user.txt").read_text(encoding="utf-8")
        values = {
            "style": summary_style,
            "over_num": summary.get("over_num"),
            "runs": summary.get("runs"),
            "wickets": summary.get("wicket_count"),
            "boundary_count": summary.get("boundary_count"),
            "boundary_batsmen": summary.get("boundary_batsmen") or "",
            "has_four": summary.get("has_four"),
            "has_six": summary.get("has_six"),
            "extras_runs": summary.get("extras_runs"),
        }
        user_text = user_template
        for k, v in values.items():
            user_text = user_text.replace("{{" + k + "}}", str(v))
        prompt = system_text.strip() + "\n\n" + user_text.strip()
        llm_text = generate_with_llm(prompt, config, model_override=model)
        if llm_text and is_valid_over_llm(llm_text, summary):
            return llm_text

    return summarize_over(rows, summary_style, seed_key)


def generate_over_sequence(rows, over_summaries, config, filters, style, mode="template", use_llm=False, model=None, include_summary=True):
    selected = filter_rows(rows, filters)
    selected.sort(key=lambda r: (r.get("match_id"), r.get("innings_index"), r.get("over"), r.get("ball_in_over"), r.get("ball_index")))

    planner = PlannerAgent()
    fact_agent = FactCheckAgent()

    lines = []
    current_key = None
    current_rows = []
    for row in selected:
        key = (row.get("match_id"), row.get("innings_index"), row.get("over"))
        if current_key and key != current_key:
            if include_summary:
                summary_line = render_over_summary(current_rows, style, config=config, use_llm=use_llm, model=model)
                if summary_line:
                    lines.append(summary_line)
            current_rows = []
        current_key = key
        current_rows.append(row)

        if mode == "deterministic":
            over = row.get("over")
            ball = row.get("ball_in_over")
            bowler = row.get("bowler") or ""
            batsman = row.get("batsman") or ""
            result_raw = row.get("result_raw") or ""
            base = f"{over}.{ball} {bowler} to {batsman}, {result_raw}".strip()
            base = " ".join(base.split())
            lines.append(base)
            commentary = row.get("commentary") or ""
            if commentary.strip():
                lines.append("Context: " + " ".join(commentary.split()))
        else:
            line = render_template_line(
                row,
                over_summaries,
                config,
                style,
                use_llm,
                model,
                planner,
                fact_agent,
            )
            lines.append(line)

    if current_rows and include_summary:
        summary_line = render_over_summary(current_rows, style, config=config, use_llm=use_llm, model=model)
        if summary_line:
            lines.append(summary_line)

    return lines


def build_over_events(rows):
    events = []
    for row in rows:
        events.append(
            {
                "ball_in_over": row.get("ball_in_over"),
                "ball_number": row.get("ball_number") or f"{row.get('over')}.{row.get('ball_in_over')}",
                "batsman": row.get("batsman") or "",
                "bowler": row.get("bowler") or "",
                "result_raw": row.get("result_raw") or "",
                "event_token": row.get("event_token") or "",
                "is_wicket": str(row.get("is_wicket") or "").lower() == "true" or (row.get("event_token") or "") == "W",
                "runs": int(row.get("token_runs") or 0),
                "commentary": " ".join((row.get("commentary") or "").split())[:140],
            }
        )
    return events


def generate_over_conversation(rows, style, config=None, use_llm=False, model=None):
    if not rows:
        return ""
    summary = build_summary(rows)
    if not summary:
        return ""

    events = build_over_events(rows)
    bowler = next((e["bowler"] for e in events if e["bowler"]), "")
    batsmen = sorted({e["batsman"] for e in events if e["batsman"]})
    batsmen_text = ", ".join(batsmen[:3])
    allowed_names = build_allowed_names(events)

    if use_llm and config:
        style_guidance = get_style_guidance(style)
        prompts_dir = Path(config["_root"]) / config.get("prompts", {}).get("jsonl_dir", "agentic/jsonl/prompts")
        system_text = (prompts_dir / "over_conversation_system.txt").read_text(encoding="utf-8")
        user_template = (prompts_dir / "over_conversation_user.txt").read_text(encoding="utf-8")
        event_lines = []
        for e in events:
            line = f"ball {e['ball_in_over']}: {e['batsman']} - {e['result_raw']} [{e['event_token']}]"
            if e["commentary"]:
                line += f" ({e['commentary']})"
            event_lines.append(line)
        values = {
            "style": style,
            "style_guidance": style_guidance,
            "over_num": summary.get("over_num"),
            "runs": summary.get("runs"),
            "wickets": summary.get("wicket_count"),
            "boundary_count": summary.get("boundary_count"),
            "has_four": summary.get("has_four"),
            "has_six": summary.get("has_six"),
            "bowler": bowler,
            "batsmen": batsmen_text,
            "allowed_names": ", ".join(sorted(allowed_names)),
            "events": "\n".join(event_lines),
        }
        user_text = user_template
        for k, v in values.items():
            user_text = user_text.replace("{{" + k + "}}", str(v))
        prompt = system_text.strip() + "\n\n" + user_text.strip()
        llm_text = generate_with_llm(prompt, config, model_override=model)
        if llm_text and is_valid_over_conversation(llm_text, summary, allowed_names=allowed_names):
            return llm_text

    # Non-LLM fallback: compress events into a continuous play-by-play paragraph.
    return render_over_play_by_play(rows, style)


def shorten_commentary(text, limit=120):
    clean = " ".join((text or "").split())
    if not clean:
        return ""
    match = re.split(r"(?<=[.!?])\\s+", clean, maxsplit=1)
    first = match[0] if match else clean
    if len(first) > limit:
        return ""
    return normalize_commentary(first)


def normalize_commentary(text):
    clean = " ".join((text or "").split())
    if not clean:
        return ""
    return clean[:1].upper() + clean[1:]


def render_over_play_by_play(rows, style):
    if not rows:
        return ""
    bowler = rows[0].get("bowler") or ""
    style_key = (style or "broadcast").lower()
    style_phrases = {
        "broadcast": {
            "start": ["{bowler} starts the over."],
            "wicket": ["{bowler} strikes, {batsman} is out."],
            "four": ["{batsman} finds the boundary for four."],
            "six": ["{batsman} launches a six."],
            "dot_single": ["A dot ball keeps the pressure on."],
            "dot_multi": ["A couple of dots tighten the screws."],
            "single": ["{batsman} nudges a single."],
            "singles": ["Singles keep things ticking for {batsmen}."],
        },
        "energetic": {
            "start": ["{bowler} charges in to begin the over."],
            "wicket": ["Boom! {bowler} strikes, {batsman} is gone."],
            "four": ["Cracked! {batsman} smokes a four."],
            "six": ["Massive! {batsman} launches it for six."],
            "dot_single": ["Locked up tight, no run."],
            "dot_multi": ["Dots pile on the pressure."],
            "single": ["Quick single for {batsman}."],
            "singles": ["Busy singles for {batsmen}."],
        },
        "serious": {
            "start": ["{bowler} begins the over."],
            "wicket": ["{bowler} removes {batsman}."],
            "four": ["{batsman} finds four with control."],
            "six": ["{batsman} hits six."],
            "dot_single": ["Dot ball, good control."],
            "dot_multi": ["Two dots keep it tight."],
            "single": ["Single taken by {batsman}."],
            "singles": ["Singles rotate the strike for {batsmen}."],
        },
        "funny": {
            "start": ["{bowler} wanders in to start the over."],
            "wicket": ["That's a ticket! {bowler} sends {batsman} packing."],
            "four": ["{batsman} sends that for four, no return address."],
            "six": ["{batsman} launches a six, no luggage required."],
            "dot_single": ["Nothing doing, a dot."],
            "dot_multi": ["A couple of dots and the batters look bored."],
            "single": ["{batsman} steals a cheeky single."],
            "singles": ["Singles keep {batsmen} on a jog."],
        },
        "methodical": {
            "start": ["Over starts: {bowler}."],
            "wicket": ["Event: wicket. {bowler} dismisses {batsman}."],
            "four": ["Event: boundary four by {batsman}."],
            "six": ["Event: six by {batsman}."],
            "dot_single": ["Dot ball recorded."],
            "dot_multi": ["Multiple dot balls recorded."],
            "single": ["Single run by {batsman}."],
            "singles": ["Singles by {batsmen}."],
        },
        "roasting": {
            "start": ["{bowler} starts the over and means business."],
            "wicket": ["{batsman} is gone, {bowler} cashes in."],
            "four": ["{batsman} punishes the mistake for four."],
            "six": ["That one disappears for six from {batsman}."],
            "dot_single": ["No run, the bowler wins that one."],
            "dot_multi": ["Dots stack up and the batters stall."],
            "single": ["{batsman} scrapes a single."],
            "singles": ["Singles for {batsmen}, not much else."],
        },
    }
    phrases = style_phrases.get(style_key, style_phrases["broadcast"])

    events = []
    for row in rows:
        runs = int(row.get("token_runs") or 0)
        event_token = (row.get("event_token") or "").strip()
        batsman = row.get("batsman") or ""
        is_wicket = str(row.get("is_wicket") or "").lower() == "true" or event_token == "W"
        if is_wicket:
            events.append({"type": "wicket", "batsman": batsman, "runs": runs})
        elif runs >= 6:
            events.append({"type": "six", "batsman": batsman, "runs": runs})
        elif runs >= 4:
            events.append({"type": "four", "batsman": batsman, "runs": runs})
        elif runs == 0:
            events.append({"type": "dot", "batsman": batsman, "runs": runs})
        else:
            events.append({"type": "run", "batsman": batsman, "runs": runs})

    grouped = []
    for event in events:
        if not grouped or grouped[-1]["type"] != event["type"]:
            grouped.append({"type": event["type"], "batsmen": [event["batsman"]], "count": 1, "runs": event["runs"]})
        else:
            grouped[-1]["batsmen"].append(event["batsman"])
            grouped[-1]["count"] += 1
            grouped[-1]["runs"] += event["runs"]

    sentences = []
    if bowler:
        sentences.append(phrases["start"][0].format(bowler=bowler))

    for idx, group in enumerate(grouped):
        batsmen = [b for b in group["batsmen"] if b]
        batsmen_text = ", ".join(sorted(set(batsmen)))
        if group["type"] == "wicket":
            line = phrases["wicket"][idx % len(phrases["wicket"])].format(
                bowler=bowler,
                batsman=batsmen_text or "the batter",
            )
        elif group["type"] == "four":
            line = phrases["four"][idx % len(phrases["four"])].format(
                batsman=batsmen_text or "the batter"
            )
        elif group["type"] == "six":
            line = phrases["six"][idx % len(phrases["six"])].format(
                batsman=batsmen_text or "the batter"
            )
        elif group["type"] == "dot":
            count = group["count"]
            line = phrases["dot_single"][0] if count == 1 else phrases["dot_multi"][0]
        else:
            if group["count"] == 1:
                line = phrases["single"][0].format(batsman=batsmen_text or "the batter")
            else:
                line = phrases["singles"][0].format(batsmen=batsmen_text or "the batters")
        sentences.append(line)

    paragraph = " ".join(sentence for sentence in sentences if sentence)
    return textwrap.fill(paragraph, width=160)


def build_allowed_names(events):
    names = set()
    for event in events:
        for key in ["batsman", "bowler"]:
            name = (event.get(key) or "").strip()
            if not name:
                continue
            names.add(name)
            parts = name.split()
            if parts:
                names.add(parts[-1])
    return names


def validate_names_in_text(text, allowed_names):
    if not allowed_names:
        return True
    stopwords = {
        "Previous",
        "Over",
        "First",
        "Then",
        "After",
        "Next",
        "And",
        "Finally",
        "End",
        "Ball",
        "The",
        "A",
        "An",
        "No",
        "Not",
        "Yes",
        "Another",
        "Minimal",
        "Measured",
        "Steady",
        "Tidy",
        "Loose",
        "Solid",
        "Precise",
        "Quiet",
        "Soft",
        "Sharp",
        "Neat",
        "Smart",
        "Brisk",
        "Crisp",
        "Controlled",
        "Short",
        "Good",
        "Big",
        "Clean",
        "Easy",
        "Quick",
        "Cautious",
        "Calm",
        "Tight",
        "Full",
        "Driven",
        "Square",
        "Cover",
        "Point",
        "Deep",
        "Wide",
        "Outside",
        "Inside",
        "Back",
        "Front",
        "Middle",
        "Leg",
        "Off",
        "Edge",
        "Crowd",
        "Scoreboard",
        "Score",
        "Fielders",
        "Field",
        "Bowler",
        "Batter",
        "Batsman",
        "Batters",
        "That",
        "This",
        "He",
        "She",
        "It",
        "They",
        "His",
        "Her",
        "Their",
        "One",
        "Two",
        "Three",
        "Four",
        "Five",
        "Six",
        "Seven",
        "Eight",
        "Nine",
        "Ten",
        "Wicket",
        "Boundary",
        "FOUR",
        "SIX",
        "Runs",
        "Run",
    }
    sentences = re.split(r"(?<=[.!?])\\s+", text)
    for sentence in sentences:
        tokens = re.findall(r"[A-Z][a-zA-Z]+", sentence)
        for idx, token in enumerate(tokens):
            if idx == 0:
                continue
            if token in stopwords:
                continue
            if token not in allowed_names:
                return False
    return True


def build_previous_over_summary(rows, all_rows, style):
    if not rows:
        return ""
    match_id = rows[0].get("match_id")
    innings = int(rows[0].get("innings_index") or 0)
    over = int(rows[0].get("over") or 0)
    prev_over = over - 1
    if prev_over < 0:
        return ""
    prev_rows = [
        r
        for r in all_rows
        if r.get("match_id") == match_id
        and int(r.get("innings_index") or 0) == innings
        and int(r.get("over") or 0) == prev_over
    ]
    if not prev_rows:
        return ""
    seed_key = f"{match_id}|{innings}|{prev_over}|{style}"
    return summarize_over(prev_rows, style, seed_key)


def generate_over_script(rows, all_rows, style, config=None, use_llm=False, model=None):
    if not rows:
        return ""
    summary = build_summary(rows)
    if not summary:
        return ""

    events = build_over_events(rows)
    bowler = next((e["bowler"] for e in events if e["bowler"]), "")
    batsmen = sorted({e["batsman"] for e in events if e["batsman"]})
    batsmen_text = ", ".join(batsmen[:3])
    allowed_names = build_allowed_names(events)
    prev_summary = build_previous_over_summary(rows, all_rows, style)

    if use_llm and config:
        style_guidance = get_style_guidance(style)
        prompts_dir = Path(config["_root"]) / config.get("prompts", {}).get("jsonl_dir", "agentic/jsonl/prompts")
        system_text = (prompts_dir / "over_script_system.txt").read_text(encoding="utf-8")
        user_template = (prompts_dir / "over_script_user.txt").read_text(encoding="utf-8")
        event_lines = []
        for e in events:
            line = f"{e['batsman']} - {e['result_raw']} [{e['event_token']}]"
            if e["commentary"]:
                line += f" ({e['commentary']})"
            event_lines.append(line)
        values = {
            "style": style,
            "style_guidance": style_guidance,
            "over_num": summary.get("over_num"),
            "runs": summary.get("runs"),
            "wickets": summary.get("wicket_count"),
            "boundary_count": summary.get("boundary_count"),
            "has_four": summary.get("has_four"),
            "has_six": summary.get("has_six"),
            "bowler": bowler,
            "batsmen": batsmen_text,
            "previous_over": prev_summary,
            "allowed_names": ", ".join(sorted(allowed_names)),
            "events": "\n".join(event_lines),
        }
        user_text = user_template
        for k, v in values.items():
            user_text = user_text.replace("{{" + k + "}}", str(v))
        prompt = system_text.strip() + "\n\n" + user_text.strip()
        llm_text = generate_with_llm(prompt, config, model_override=model)
        if llm_text and is_valid_over_script(llm_text, summary, allowed_names=allowed_names):
            return llm_text

    # Deterministic fallback: previous-over summary + ball-by-ball + end summary.
    lines = []
    if prev_summary:
        lines.append(f"Previous over: {prev_summary}")
    opener = f"Over {summary.get('over_num')} begins."
    lines.append(opener)
    planner = PlannerAgent()
    fact_agent = FactCheckAgent()
    for idx, row in enumerate(rows):
        commentary = shorten_commentary(row.get("commentary") or "")
        if commentary:
            line = commentary
        else:
            line = render_template_line(
                row,
                {},
                config,
                style,
                use_llm=False,
                model=None,
                planner=planner,
                fact_agent=fact_agent,
            )
        lines.append(line.rstrip(".") + ".")
    wicket_phrase = summary.get("wicket_phrase") or ""
    end_line = f"End of over {summary.get('over_num')}: {summary.get('runs')} runs{wicket_phrase}."
    lines.append(end_line)
    paragraph = " ".join(line.strip() for line in lines if line.strip())
    return textwrap.fill(paragraph, width=160)


def generate_over_lines(rows, filters, style, config=None, use_llm=False, model=None):
    selected = filter_rows(rows, filters)
    grouped = {}
    for row in selected:
        key = (row.get("match_id"), row.get("innings_index"), row.get("over"))
        grouped.setdefault(key, []).append(row)

    lines = []
    for key in sorted(grouped.keys()):
        match_id, innings_index, over = key
        seed_key = f"{match_id}|{innings_index}|{over}|{style}"
        summary = build_summary(grouped[key])
        summary_style = style
        if style == "panel":
            if summary.get("wicket_count", 0) > 0:
                summary_style = "energetic"
            elif summary.get("boundary_count", 0) > 0:
                summary_style = "funny"
            else:
                summary_style = "methodical"

        if use_llm and config:
            style_guidance = get_style_guidance(summary_style)
            prompts_dir = Path(config["_root"]) / config.get("prompts", {}).get("jsonl_dir", "agentic/jsonl/prompts")
            system_text = (prompts_dir / "over_system.txt").read_text(encoding="utf-8")
            user_template = (prompts_dir / "over_user.txt").read_text(encoding="utf-8")
            values = {
                "style": summary_style,
                "style_guidance": style_guidance,
                "over_num": summary.get("over_num"),
                "runs": summary.get("runs"),
                "wickets": summary.get("wicket_count"),
                "boundary_count": summary.get("boundary_count"),
                "boundary_batsmen": summary.get("boundary_batsmen") or "",
                "has_four": summary.get("has_four"),
                "has_six": summary.get("has_six"),
                "extras_runs": summary.get("extras_runs"),
            }
            user_text = user_template
            for k, v in values.items():
                user_text = user_text.replace("{{" + k + "}}", str(v))
            prompt = system_text.strip() + "\n\n" + user_text.strip()
            llm_text = generate_with_llm(prompt, config, model_override=model)
            if llm_text and is_valid_over_llm(llm_text, summary):
                line = llm_text
            else:
                line = summarize_over(grouped[key], summary_style, seed_key)
        else:
            line = summarize_over(grouped[key], summary_style, seed_key)
        if line:
            lines.append(line)
    return lines


def generate_deterministic_lines(rows, filters):
    selected = filter_rows(rows, filters)
    lines = []
    for row in selected:
        over = row.get("over")
        ball = row.get("ball_in_over")
        bowler = row.get("bowler") or ""
        batsman = row.get("batsman") or ""
        result_raw = row.get("result_raw") or ""
        base = f"{over}.{ball} {bowler} to {batsman}, {result_raw}".strip()
        base = " ".join(base.split())
        lines.append(base)

        commentary = row.get("commentary") or ""
        if commentary.strip():
            lines.append("Context: " + " ".join(commentary.split()))
    return lines
