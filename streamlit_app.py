#!/usr/bin/env python3
import sys
from pathlib import Path

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parent
sys.path.append(str(ROOT_DIR))

from config import get_path, load_config
from agentic.commentary_core import generate_deterministic_lines, generate_over_lines, generate_template_lines, load_overs


@st.cache_data
def load_data(path):
    return load_overs(path)


def main():
    st.set_page_config(page_title="Cri-CAN Commentary", layout="wide")
    st.title("Cri-CAN Commentary Studio")
    st.caption("Deterministic commentary chunks from match data, with optional LLM output.")

    config = load_config(None)
    overs_path = get_path(config, "overs_jsonl", section="files")
    rows, over_summaries = load_data(overs_path)

    matches = sorted({r.get("match_id") for r in rows if r.get("match_id")})
    teams = sorted({r.get("batting_team") for r in rows if r.get("batting_team")})

    with st.sidebar:
        st.header("Filters")
        match_id = st.selectbox("Match", options=matches, index=0)
        innings = st.selectbox("Innings", options=[1, 2], index=1)
        team = st.selectbox("Team (batting)", options=[""] + teams, index=0)
        over = st.number_input("Over", min_value=0, max_value=50, value=11, step=1)
        over_ordinal = st.checkbox("Interpret over as ordinal (11th over -> 10)", value=False)
        start = st.text_input("Start ball (over.ball or ball_index)", value="")
        end = st.text_input("End ball (over.ball or ball_index)", value="")
        bowler = st.text_input("Bowler contains", value="")
        batsman = st.text_input("Batsman contains", value="")
        event = st.selectbox("Event", options=["", "dot", "run", "boundary", "extra", "wicket"], index=0)
        boundary = st.checkbox("Boundary only", value=False)
        wicket = st.checkbox("Wicket only", value=False)
        limit = st.number_input("Limit", min_value=1, max_value=120, value=6, step=1)

        st.header("Output")
        mode = st.selectbox(
            "Mode",
            options=["deterministic", "template", "llm"],
            index=1,
        )
        granularity = st.selectbox(
            "Granularity",
            options=["ball", "over"],
            index=0,
        )

        st.header("Style")
        style = st.selectbox(
            "Tone",
            options=["broadcast", "funny", "serious", "methodical", "energetic", "roasting"],
            index=0,
        )

        st.header("LLM")
        use_llm = st.checkbox("Use LLM (template mode)", value=False)
        model = st.text_input("Model override", value="")

    filters = {
        "match_id": match_id,
        "innings": innings,
        "team": team or None,
        "over": over if over != 0 else None,
        "over_ordinal": over_ordinal,
        "bowler": bowler or None,
        "batsman": batsman or None,
        "boundary": boundary,
        "wicket": wicket,
        "event": event or None,
        "start": start or None,
        "end": end or None,
        "limit": int(limit) if limit else None,
    }

    if st.button("Generate commentary"):
        if mode == "deterministic":
            lines = generate_deterministic_lines(rows, filters)
        elif granularity == "over":
            lines = generate_over_lines(rows, filters, style)
        else:
            lines = generate_template_lines(
                rows,
                over_summaries,
                config,
                filters,
                style,
                use_llm=(mode == "llm" or use_llm),
                model=model or None,
            )
        if not lines:
            st.warning("No rows matched the filters. Try a different over or filter set.")
        else:
            st.subheader("Output")
            st.text("\n".join(lines))

    st.markdown("---")
    st.caption("This interface is deterministic by default. Toggle LLM for Ollama output.")


if __name__ == "__main__":
    main()
