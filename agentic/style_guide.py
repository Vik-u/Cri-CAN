#!/usr/bin/env python3

STYLE_GUIDANCE = {
    "broadcast": "Polished broadcast tone, vivid but factual, no slang overload.",
    "funny": "Playful and witty, light humor, keep facts intact.",
    "serious": "Analytical and restrained, no jokes, focus on match context.",
    "methodical": "Structured and technical, pace-by-pace detail, crisp phrasing.",
    "energetic": "High energy, momentum-driven, short emphatic phrases.",
    "roasting": "Light roast with respect, witty but not abusive.",
    "panel": "Alternate tones per ball; keep it lively and varied.",
}


def get_style_guidance(style):
    if not style:
        return STYLE_GUIDANCE["broadcast"]
    return STYLE_GUIDANCE.get(style, STYLE_GUIDANCE["broadcast"])
