#!/usr/bin/env python3
import re
from pathlib import Path

from agentic.llm_adapter import generate_with_llm


def extract_ball_lines(text):
    if not text:
        return []
    text = text.replace("Final Answer:", "").strip()
    lines = []
    for raw in text.splitlines():
        clean = raw.strip()
        if not clean:
            continue
        clean = re.sub(r"^[-*\d.\s]*Ball\s*\d+\s*[:\-]\s*", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"Ball\s*\d+\s*[:\-]\s*", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"^[-*\d.\s]*\d+\s*[:\-]\s*", "", clean)
        if clean:
            clean = clean.lstrip("*").strip()
            lines.append(clean)
    if len(lines) < 6 and "|" in text:
        parts = [part.strip() for part in text.split("|") if part.strip()]
        lines.extend(parts)
    return [line.rstrip(".") + "." for line in lines][:6]


def format_ball_lines_with_llm(events, config, model=None):
    if not events:
        return []
    prompt = build_format_prompt(events)
    output = generate_with_llm(prompt, config, model_override=model)
    lines = extract_ball_lines(output or "")
    if len(lines) == 6:
        return lines
    return []


def force_ball_lines(events):
    if not events:
        return []
    lines = []
    for event in events[:6]:
        line = build_line_from_event(event)
        if line:
            lines.append(line.rstrip(".") + ".")
    return lines


def build_line_from_event(event):
    text = str(event or "").strip()
    if not text:
        return ""
    snippet = ""
    if "(" in text and ")" in text:
        snippet = text[text.find("(") + 1 : text.rfind(")")].strip()
    cleaned = re.sub(r"\s*\[.*?\]\s*", " ", text).strip()
    cleaned = cleaned.replace(" - ", ": ").strip()
    if snippet:
        return snippet
    if cleaned:
        return cleaned
    return text


def build_format_prompt(events):
    lines = [
        "You are formatting ball-by-ball commentary lines.",
        "Output exactly six lines in this format:",
        "Ball 1: ...",
        "Ball 2: ...",
        "Ball 3: ...",
        "Ball 4: ...",
        "Ball 5: ...",
        "Ball 6: ...",
        "Use the commentary snippets in parentheses verbatim when possible.",
        "Do not add new players or facts.",
        "",
        "Events:",
    ]
    for idx, event in enumerate(events, start=1):
        lines.append(f"{idx}. {event}")
    return "\n".join(lines)
