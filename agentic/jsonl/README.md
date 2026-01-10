# Agentic Commentary (JSONL)

Purpose: text-only agentic commentary for the 2011 CWC final using `data/structured/jsonl/overs.jsonl`.

## What I built (step by step)
- Step 1: Created `Cri-CAN/agentic/common.py` with a shared, text-only pipeline (event classification, template generation, optional context lines, and timing helper).
- Step 2: Implemented JSONL loader in `Cri-CAN/agentic/jsonl/run_agentic_jsonl.py` to flatten `balls[]` from `overs.jsonl` in match order.
- Step 3: Wired the loader into the shared agentic pipeline and added CLI flags for input, limit, and output.
- Step 4: Generated a sample output file (`Cri-CAN/agentic/jsonl/sample_output.txt`) using the default limit.
- Step 5: Benchmarked load + full generation time and recorded results in `Cri-CAN/agentic/performance_report.md`.

## Tools used
- Python 3 standard library (`json`, `argparse`, `time`, `pathlib`).
- Shared agentic pipeline in `Cri-CAN/agentic/common.py`.

## Algorithm used (text-only agentic pipeline)
- Event classifier: determines `wicket`, `boundary`, `extra`, `run`, or `dot` using `event_token`, `token_type`, and `token_runs`.
- Template generator: produces a clean commentary line that always includes bowler, batsman, and the result.
- Context agent: attaches `commentary` text as a short "Context:" line when present.
- Lightweight fact-check: ensures bowler and batsman names appear in the line.
- State tracker: keeps per-innings runs/wickets/ball count (used for future extensions).

## LLM prompts
- System prompt: `Cri-CAN/agentic/jsonl/prompts/system.txt`
- User prompt: `Cri-CAN/agentic/jsonl/prompts/user.txt`

## LLM configuration
- Set `llm.command_template` in `Cri-CAN/config.toml` (default: `ollama run {model}`).
- Text model: `llm.model` (default: `gpt-oss:20b`).
- Multimodal model: `llm.multimodal_model` (default: `gemma3:27b`).
- If `llm.command`/`llm.command_template` is empty, the script falls back to template-based output.

## Agents (v1)
- PlannerAgent, StyleAgent, FactCheckAgent: `Cri-CAN/agentic/agents.py`

## How to run
Default:

```bash
python3 Cri-CAN/agentic/jsonl/run_agentic_jsonl.py
```

Custom:

```bash
python3 Cri-CAN/agentic/jsonl/run_agentic_jsonl.py --limit 200 --output Cri-CAN/agentic/jsonl/out.txt
```

LLM-ready v1:

```bash
python3 Cri-CAN/agentic/jsonl/run_agentic_v1.py --limit 50
```

Ollama model override:

```bash
python3 Cri-CAN/agentic/jsonl/run_agentic_v1.py --model gpt-oss:20b --limit 10
```

Timepoint control:

```bash
python3 Cri-CAN/agentic/jsonl/run_agentic_v1.py --start 12.3 --end 14.6
python3 Cri-CAN/agentic/jsonl/run_agentic_v1.py --start 120 --limit 10
```

Recent-overs context:

```bash
python3 Cri-CAN/agentic/jsonl/run_agentic_v1.py --context-overs 3 --limit 10
```

Config:
- Defaults come from `Cri-CAN/config.toml`.
- Override with `--config /path/to/config.toml`.

## Outputs
- `Cri-CAN/agentic/jsonl/sample_output.txt` (first 60 balls by default)
  - Header marks this as `v0-deterministic` output derived directly from the source commentary.
- `Cri-CAN/agentic/jsonl/sample_output_v1.txt` (LLM-ready, human-like output)
  - Header marks this as `v1-agentic-llm` and uses prompt templates with a fallback template generator.

## Performance (compared across all three options)
- CSV: total_seconds = 0.0058
- SQLite: total_seconds = 0.0056
- JSONL (this option): total_seconds = 0.0045

Source: `Cri-CAN/agentic/performance_report.md`

## Notes
- Runs are derived from `event_token` parsing (`token_runs`), which matches Cricinfo's per-ball totals but does not split off-bat vs extras.
- This is text-only and deterministic; audio/video can be layered later with alignment cues and multimodal features.
