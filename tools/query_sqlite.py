#!/usr/bin/env python3
import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from config import get_path, load_config


def main():
    parser = argparse.ArgumentParser(description="Query SQLite commentary database.")
    parser.add_argument("--config", default=None, help="Path to config.toml")
    parser.add_argument("--view", default=None, help="View/table name to query")
    parser.add_argument("--where", default=None, help="Optional WHERE clause")
    parser.add_argument("--limit", type=int, default=20, help="Row limit")
    parser.add_argument("--sql", default=None, help="Raw SQL to execute")
    args = parser.parse_args()

    config = load_config(args.config)
    db_path = get_path(config, "sqlite_db", section="files")

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        if args.sql:
            query = args.sql
        else:
            if not args.view:
                raise SystemExit("Provide --view or --sql")
            query = f"SELECT * FROM {args.view}"
            if args.where:
                query += f" WHERE {args.where}"
            if args.limit:
                query += f" LIMIT {args.limit}"
        cur.execute(query)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        print("\t".join(cols))
        for row in rows:
            print("\t".join(str(v) if v is not None else "" for v in row))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
