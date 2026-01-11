#!/usr/bin/env python3
import sys
from pathlib import Path

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parent
sys.path.append(str(ROOT_DIR))

from config import get_path, load_config
from agentic.commentary_core import generate_over_script, load_overs


@st.cache_data
def load_data(path):
    return load_overs(path)


def main():
    st.set_page_config(page_title="Cri-CAN Commentary", layout="centered")
    st.title("Cri-CAN Commentary Studio")
    st.caption("Choose over, innings, style, and LLM. We generate a live-sounding over commentary.")

    config = load_config(None)
    overs_path = get_path(config, "overs_jsonl", section="files")
    rows, over_summaries = load_data(overs_path)

    match_id = next((r.get("match_id") for r in rows if r.get("match_id")), None)
    innings = st.selectbox("Which innings?", options=[1, 2], index=1)
    over = st.number_input("Which over? (1-50)", min_value=1, max_value=50, value=11, step=1)
    style = st.selectbox(
        "Style",
        options=["broadcast", "funny", "serious", "methodical", "energetic", "roasting", "panel"],
        index=0,
    )
    use_llm = st.checkbox("Use LLM (Ollama)", value=True)
    model = st.text_input("Model override (optional)", value="")

    if st.button("Generate commentary"):
        use_llm_flag = bool(use_llm)
        over_rows = [
            r
            for r in rows
            if r.get("match_id") == match_id
            and int(r.get("innings_index") or 0) == innings
            and int(r.get("over") or 0) == int(over) - 1
        ]
        script = generate_over_script(
            over_rows,
            rows,
            style,
            config=config,
            use_llm=use_llm_flag,
            model=model or None,
        )
        if not script:
            st.warning("No rows matched that over/innings. Try a different over.")
        else:
            st.subheader("Live over commentary")
            st.text(script)

    st.markdown("---")
    st.caption("This view is intentionally minimal. Over numbers are 1-50 (ordinal).")


if __name__ == "__main__":
    main()
