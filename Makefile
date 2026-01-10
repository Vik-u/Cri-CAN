PY ?= python3
CONFIG ?= config.toml

.PHONY: build structured legacy derive qa sqlite-views sqlite-query agentic-csv agentic-sqlite agentic-jsonl agentic-jsonl-v1 agentic-all compare rebuild

build: structured

structured:
	$(PY) tools/build_structured.py --config $(CONFIG)

legacy:
	$(PY) tools/parse_cricinfo.py --config $(CONFIG)

derive:
	$(PY) tools/derive_stats.py --config $(CONFIG)

qa: derive

sqlite-views:
	$(PY) tools/build_sqlite_views.py --config $(CONFIG)

sqlite-query:
	$(PY) tools/query_sqlite.py --config $(CONFIG) --view ball_summary --limit 5

agentic-csv:
	$(PY) agentic/csv/run_agentic_csv.py --config $(CONFIG)

agentic-sqlite:
	$(PY) agentic/sqlite/run_agentic_sqlite.py --config $(CONFIG)

agentic-jsonl:
	$(PY) agentic/jsonl/run_agentic_jsonl.py --config $(CONFIG)

agentic-jsonl-v1:
	$(PY) agentic/jsonl/run_agentic_v1.py --config $(CONFIG)

agentic-all: agentic-csv agentic-sqlite agentic-jsonl

compare:
	$(PY) agentic/compare.py --config $(CONFIG)

rebuild: structured derive sqlite-views agentic-all compare
