# Agentic Commentary (CSV)

Purpose: text-only agentic commentary for the 2011 CWC final using `data/structured/csv/balls.csv`.

## What I built (step by step)
- Step 1: Created `Cri-CAN/agentic/common.py` with a shared, text-only pipeline (event classification, template generation, optional context lines, and timing helper).
- Step 2: Implemented CSV loader in `Cri-CAN/agentic/csv/run_agentic_csv.py` to read `data/structured/csv/balls.csv` with correct ordering.
- Step 3: Wired the loader into the shared agentic pipeline and added CLI flags for input, limit, and output.
- Step 4: Generated a sample output file (`Cri-CAN/agentic/csv/sample_output.txt`) using the default limit.
- Step 5: Benchmarked load + full generation time and recorded results in `Cri-CAN/agentic/performance_report.md`.

## Tools used
- Python 3 standard library (`csv`, `argparse`, `time`, `pathlib`).
- Shared agentic pipeline in `Cri-CAN/agentic/common.py`.

## Algorithm used (text-only agentic pipeline)
- Event classifier: determines `wicket`, `boundary`, `extra`, `run`, or `dot` using `event_token`, `token_type`, and `token_runs`.
- Template generator: produces a clean commentary line that always includes bowler, batsman, and the result.
- Context agent: attaches `commentary` text as a short "Context:" line when present.
- Lightweight fact-check: ensures bowler and batsman names appear in the line.
- State tracker: keeps per-innings runs/wickets/ball count (used for future extensions).

## How to run
Default:

```bash
python3 Cri-CAN/agentic/csv/run_agentic_csv.py
```

Custom:

```bash
python3 Cri-CAN/agentic/csv/run_agentic_csv.py --limit 200 --output Cri-CAN/agentic/csv/out.txt
```

Config:
- Defaults come from `Cri-CAN/config.toml`.
- Override with `--config /path/to/config.toml`.

## Outputs
- `Cri-CAN/agentic/csv/sample_output.txt` (first 60 balls by default)
  - Header marks this as `v0-deterministic` output derived directly from the source commentary.

## Performance (compared across all three options)
- CSV (this option): total_seconds = 0.0058
- SQLite: total_seconds = 0.0056
- JSONL: total_seconds = 0.0045

Source: `Cri-CAN/agentic/performance_report.md`

## Notes
- Runs are derived from `event_token` parsing (`token_runs`), which matches Cricinfo's per-ball totals but does not split off-bat vs extras.
- This is text-only and deterministic; audio/video can be layered later with alignment cues and multimodal features.
