# CrewAI Commentary Pipeline

This folder uses CrewAI agents (planner → writer → critic) to generate a full over commentary.
KG ball_state context and style guidance are injected into the prompts to reduce hallucinations and improve tone.

## Setup
- Use the shared venv: `Cri-CAN/.venv-agents`
- Ollama must be running (default OpenAI-compatible endpoint: `http://localhost:11434/v1`)

## Run (example)
```bash
Cri-CAN/.venv-agents/bin/python Cri-CAN/agentic/crewai/run_crewai_over.py --innings 2 --over 4 --style broadcast
```

Output is written to `Cri-CAN/agentic/outputs/crewai/run_YYYYMMDD_HHMMSS/`.
