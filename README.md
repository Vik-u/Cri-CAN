# Cri-CAN

Cricket Commentary Agentic Network (CWC 2011 Final). This repo turns Cricinfo-style ball-by-ball text into structured datasets, a match knowledge graph, and agentic commentary outputs (deterministic v0 + LLM-ready v1).

## Overview
- Inputs: raw commentary text in `Cri-CAN/data/raw`.
- Outputs: CSV/JSONL/SQLite datasets, QA reports, knowledge graph, and text commentary.
- Commentary modes: deterministic, template, LLM, and long-form over scripts.

## Data pipeline
1) Structured data:
```bash
make -C Cri-CAN build
```
2) Derived stats + QA (CSV path):
```bash
make -C Cri-CAN derive
```
3) SQLite views:
```bash
make -C Cri-CAN sqlite-views
```
4) Match KG:
```bash
make -C Cri-CAN kg
```

## Agentic commentary
### v0 deterministic (exact from parsed data)
- CSV:
```bash
make -C Cri-CAN agentic-csv
```
- SQLite:
```bash
make -C Cri-CAN agentic-sqlite
```
- JSONL:
```bash
make -C Cri-CAN agentic-jsonl
```
Outputs are labeled `v0-deterministic`.

### v1 human-style (LLM-ready)
```bash
make -C Cri-CAN agentic-jsonl-v1
```

Timepoint control:
```bash
python3 Cri-CAN/agentic/jsonl/run_agentic_v1.py --start 12.3 --end 14.6
python3 Cri-CAN/agentic/jsonl/run_agentic_v1.py --start 120 --limit 10
```

Recent overs context:
```bash
python3 Cri-CAN/agentic/jsonl/run_agentic_v1.py --context-overs 3 --limit 10
```

Ollama model override:
```bash
python3 Cri-CAN/agentic/jsonl/run_agentic_v1.py --model gpt-oss:20b --limit 10
```

### Commentary CLI (chunked output)
```bash
python3 Cri-CAN/agentic/commentary_cli.py --innings 2 --over 10 --style energetic
python3 Cri-CAN/agentic/commentary_cli.py --team IND --event boundary --style funny
python3 Cri-CAN/agentic/commentary_cli.py --bowler Malinga --over 20 --style serious
```

Modes:
- `--mode deterministic` (exact, per-ball)
- `--mode template` (template per-ball)
- `--mode llm` (LLM per-ball)
- `--granularity over` (smooth over summary, template or LLM)
- `--over-format ball` (ball-by-ball, no summary)
- `--over-format ball+summary` (ball-by-ball plus end-of-over summary)
- Style `panel` switches style per ball dynamically.

### Long-form over commentary
```bash
python3 Cri-CAN/agentic/longform/run_longform_over.py --innings 2 --over 4 --style broadcast
```
Outputs:
- `Cri-CAN/agentic/longform/outputs/run_YYYYMMDD_HHMMSS/longform_inningsX_overY.md`

## Match knowledge graph (KG)
Built from `balls_enriched.csv` into:
- `Cri-CAN/data/structured/kg/nodes.csv`
- `Cri-CAN/data/structured/kg/edges.csv`
- `Cri-CAN/data/structured/kg/ball_state.csv`

KG schema:
- `Cri-CAN/data/structured/kg/schema.md`

## LLM agent pipelines (CrewAI / AutoGen)
Install and run using the separate agents venv (Python 3.11):
```bash
python3.11 -m venv Cri-CAN/.venv-agents
Cri-CAN/.venv-agents/bin/python -m pip install crewai==0.11.2 pyautogen==0.2.0
```

CrewAI:
```bash
Cri-CAN/.venv-agents/bin/python Cri-CAN/agentic/crewai/run_crewai_over.py --innings 2 --over 4 --style broadcast
```

AutoGen:
```bash
Cri-CAN/.venv-agents/bin/python Cri-CAN/agentic/autogen/run_autogen_over.py --innings 2 --over 4 --style broadcast
```

Comparison report:
```bash
cat Cri-CAN/agentic/agents_compare.md
```

## Streamlit UI
```bash
Cri-CAN/.venv/bin/python -m streamlit run Cri-CAN/streamlit_app.py --server.headless true
```
Then open `http://localhost:8501` in your browser.

## Applications
- Live-style commentary generation from ball-by-ball feeds.
- Retrieval-based highlight clips (timepoint control + event filters).
- Analytics dashboards (over totals, partnerships, wickets, boundaries).
- Training/evaluation dataset for sports-commentary models.
- Broadcast tooling: style variants and tone control.

## Reference docs
- End-to-end walkthrough: `Cri-CAN/README_GLOBAL.md`
- Performance report: `Cri-CAN/agentic/performance_report.md`

## Requirements + setup
- Python 3.11+ (stdlib only).
- Optional: Ollama for local LLM generation.
- Optional: Streamlit (installed in local venv at `Cri-CAN/.venv`).

Config:
- Default config: `Cri-CAN/config.toml`
- Override with `CRI_CONFIG` or `--config /path/to/config.toml`.

Key LLM settings in config:
- `llm.command_template = "ollama run {model}"`
- `llm.model = "gpt-oss:20b"`
- `llm.multimodal_model = "gemma3:27b"`

LLM usage (Ollama):
- Default command: `ollama run {model}`
- Set `llm.model` to `gpt-oss:20b` for text generation.
- `llm.multimodal_model` is reserved for later audio/video use.
- The adapter cleans any preamble (e.g., "Thinking...") and keeps only the final line.

LLM demo audio (5 diverse overs):
```bash
python3 Cri-CAN/tools/generate_llm_over_demo.py --match CWC_2011_final_ALL
```

## GitHub
Repo: https://github.com/Vik-u/Cri-CAN.git
