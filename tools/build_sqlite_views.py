#!/usr/bin/env python3
import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from config import get_path, load_config


def main():
    parser = argparse.ArgumentParser(description="Build SQLite views for commentary database.")
    parser.add_argument("--config", default=None, help="Path to config.toml")
    args = parser.parse_args()

    config = load_config(args.config)
    db_path = get_path(config, "sqlite_db", section="files")
    views_path = get_path(config, "sqlite_views_sql", section="files")

    sql = views_path.read_text(encoding="utf-8")
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(sql)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
