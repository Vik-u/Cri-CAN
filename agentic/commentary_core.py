#!/usr/bin/env python3
import json
from pathlib import Path

from agents import FactCheckAgent, PlannerAgent, StyleAgent
from llm_adapter import generate_with_llm
from over_summary import summarize_over
from style_templates import render_style

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


def generate_template_lines(rows, over_summaries, config, filters, style, use_llm=False, model=None):
    selected = filter_rows(rows, filters)
    planner = PlannerAgent()
    fact_agent = FactCheckAgent()
    style_agent = build_style_agent(style)

    lines = []
    for row in selected:
        plan = planner.plan(row, [])
        if use_llm:
            prompts_dir = Path(config["_root"]) / config.get("prompts", {}).get("jsonl_dir", "agentic/jsonl/prompts")
            system_text = (prompts_dir / "system.txt").read_text(encoding="utf-8")
            user_template = (prompts_dir / "user.txt").read_text(encoding="utf-8")
            key = (row.get("match_id"), row.get("innings_index"), row.get("over"))
            over_summary = over_summaries.get(key, "")
            values = {
                "style": style,
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
                line = fact_agent.verify(llm_text, row)
            else:
                line = style_agent.render(plan, row)
        else:
            line = style_agent.render(plan, row)

        lines.append(line)

    return lines


def generate_over_lines(rows, filters, style):
    selected = filter_rows(rows, filters)
    grouped = {}
    for row in selected:
        key = (row.get("match_id"), row.get("innings_index"), row.get("over"))
        grouped.setdefault(key, []).append(row)

    lines = []
    for key in sorted(grouped.keys()):
        match_id, innings_index, over = key
        seed_key = f"{match_id}|{innings_index}|{over}|{style}"
        line = summarize_over(grouped[key], style, seed_key)
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
