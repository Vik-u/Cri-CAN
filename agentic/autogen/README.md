# AutoGen Commentary Pipeline

This folder uses AutoGen agents (planner → writer → critic) to generate a full over commentary.

## Setup
- Use the shared venv: `Cri-CAN/.venv-agents`
- Ollama must be running (default OpenAI-compatible endpoint: `http://localhost:11434/v1`)

## Run (example)
```bash
Cri-CAN/.venv-agents/bin/python Cri-CAN/agentic/autogen/run_autogen_over.py --innings 2 --over 4 --style broadcast
```

Output is written to `Cri-CAN/agentic/autogen/outputs/run_YYYYMMDD_HHMMSS/`.
