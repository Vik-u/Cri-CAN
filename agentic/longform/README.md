# Long-form Over Commentary

This module produces a continuous over-length commentary (previous over summary + 6 balls + end-of-over recap).
It uses KG-derived score context when available and falls back to deterministic text if the LLM output is invalid.

## Run
```bash
python3 Cri-CAN/agentic/longform/run_longform_over.py --innings 2 --over 4 --style broadcast
```

LLM override:
```bash
python3 Cri-CAN/agentic/longform/run_longform_over.py --model gpt-oss:20b --innings 2 --over 4
```

No LLM:
```bash
python3 Cri-CAN/agentic/longform/run_longform_over.py --no-llm --innings 2 --over 4
```

Outputs:
- `Cri-CAN/agentic/longform/outputs/run_YYYYMMDD_HHMMSS/longform_inningsX_overY.md`

## Inputs
- `data/structured/jsonl/overs.jsonl`
- `data/structured/kg/ball_state.csv` (preferred)
- `data/structured/csv/balls_enriched.csv` (fallback)

## Prompts
- `agentic/longform/prompts/longform_system.txt`
- `agentic/longform/prompts/longform_user.txt`
