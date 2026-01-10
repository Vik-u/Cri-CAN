#!/usr/bin/env python3
import random
import subprocess


STYLE_TEMPLATES = {
    "wicket": [
        "Gone! {batsman} is out, {bowler} strikes.",
        "Big moment: {bowler} removes {batsman}.",
        "Wicket! {batsman} departs, and {bowler} has the breakthrough.",
        "Oh dear, {batsman} has to go. {bowler} nails it.",
        "That's a gift, and {bowler} grabs it. {batsman} is out.",
        "{bowler} wins that round - {batsman} walks.",
        "That one had trouble written all over it. {batsman} is gone.",
        "Short stay for {batsman}. {bowler} is on the money.",
    ],
    "boundary": [
        "Cracked away for {runs} - {batsman} times it nicely.",
        "That's {runs}! {batsman} finds the rope off {bowler}.",
        "Clean hit for {runs}, {batsman} cashes in.",
        "That is smoked. {runs} more for {batsman}.",
        "Asking to be hit and {batsman} accepts. {runs}.",
        "Short, wide, punished. {runs} off it.",
        "Free hit, and {batsman} cashes the cheque. {runs}.",
        "{bowler} misses his mark and pays for it. {runs}.",
    ],
    "extra": [
        "Extras added there, {bowler} strays a touch.",
        "A bonus run for the batting side.",
        "That one slips down the leg side, extras on offer.",
        "That's free money for the batting side.",
        "Sloppy from {bowler} - extras again.",
        "Wayward from {bowler}, and the scoreboard moves.",
    ],
    "dot": [
        "Good ball from {bowler}, {batsman} can't score.",
        "Dot ball - {bowler} keeps it tight.",
        "No run, tidy from {bowler}.",
        "Locked up tight by {bowler}.",
        "{batsman} goes nowhere. Good control from {bowler}.",
        "Nothing off it. {bowler} wins that exchange.",
        "No freebies there. {bowler} on the money.",
    ],
    "run": [
        "They sneak {runs}, good rotation of strike.",
        "{runs} run(s) there, {batsman} keeps it moving.",
        "Easy {runs}, keeps the scoreboard ticking.",
        "Busy running, {runs} added.",
        "{batsman} nudges {runs} and moves on.",
        "Neat placement and {runs} more.",
        "Soft hands, quick feet. {runs}.",
    ],
}


PREFIXES = [
    "",
    "Listen to that. ",
    "Crowd loves it. ",
    "Oh, wow. ",
    "Here we go. ",
]

SUFFIXES = [
    "",
    " Plenty of energy out there.",
    " That will get the crowd going.",
    " This is heating up.",
]


def render_template(event_type, bowler, batsman, runs):
    template = random.choice(STYLE_TEMPLATES.get(event_type, STYLE_TEMPLATES["run"]))
    prefix = random.choice(PREFIXES)
    suffix = random.choice(SUFFIXES) if event_type in {"wicket", "boundary"} else ""
    return prefix + template.format(bowler=bowler, batsman=batsman, runs=runs) + suffix


def build_command(config, model_override=None):
    llm_cfg = config.get("llm", {})
    command = (llm_cfg.get("command") or "").strip()
    template = (llm_cfg.get("command_template") or "").strip()
    model = model_override or llm_cfg.get("model")
    provider = (llm_cfg.get("provider") or "").strip().lower()

    if command:
        if "{model}" in command:
            return command.format(model=model)
        return command
    if template:
        return template.format(model=model)
    if provider == "ollama" and model:
        return f"ollama run {model}"
    return ""


def normalize_ascii(text):
    replacements = {
        "\u201c": "\"",
        "\u201d": "\"",
        "\u2019": "'",
        "\u2018": "'",
        "\u2014": "-",
        "\u2013": "-",
        "\u2011": "-",
        "\u2026": "...",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text


def clean_llm_output(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    filtered = []
    for line in lines:
        lower = line.lower()
        if lower.startswith("thinking") or lower.startswith("analysis"):
            continue
        if lower.startswith("we need") or lower.startswith("let's"):
            continue
        if "done thinking" in lower:
            continue
        if line == "...":
            continue
        filtered.append(line)
    if not filtered:
        filtered = lines
    result = filtered[-1] if filtered else ""
    return normalize_ascii(result)


def generate_with_llm(prompt, config, model_override=None):
    command = build_command(config, model_override=model_override)
    if not command:
        return None

    result = subprocess.run(
        command,
        input=prompt,
        text=True,
        shell=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    output = result.stdout.strip()
    if not output:
        return None
    return clean_llm_output(output)
