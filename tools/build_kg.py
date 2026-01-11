#!/usr/bin/env python3
import argparse
import csv
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR))

from config import get_path, load_config


def safe_int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def add_node(nodes, node_id, node_type, name="", match_id="", innings_index="", over="", ball_in_over=""):
    if not node_id:
        return
    if node_id in nodes:
        return
    nodes[node_id] = {
        "node_id": node_id,
        "node_type": node_type,
        "name": name,
        "match_id": match_id,
        "innings_index": innings_index,
        "over": over,
        "ball_in_over": ball_in_over,
    }


def add_edge(edges, source_id, relation, target_id):
    if not source_id or not target_id:
        return
    edges.add((source_id, relation, target_id))


def build_kg(config):
    balls_path = get_path(config, "balls_enriched_csv", section="files")
    kg_dir = get_path(config, "kg_dir", section="paths")
    kg_dir.mkdir(parents=True, exist_ok=True)
    nodes_path = get_path(config, "kg_nodes_csv", section="files")
    edges_path = get_path(config, "kg_edges_csv", section="files")
    state_path = get_path(config, "kg_ball_state_csv", section="files")

    nodes = {}
    edges = set()
    ball_state_rows = []

    with balls_path.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            match_id = row.get("match_id") or ""
            innings = safe_int(row.get("innings_index")) or 0
            over = safe_int(row.get("over")) or 0
            ball_in_over = safe_int(row.get("ball_in_over")) or 0
            batting_team = (row.get("batting_team") or "").strip()
            batsman = (row.get("batsman") or "").strip()
            bowler = (row.get("bowler") or "").strip()
            event_type = (row.get("event_type") or "").strip()
            phase = (row.get("phase") or "").strip()

            match_node = f"match:{match_id}"
            innings_node = f"innings:{match_id}:{innings}"
            over_node = f"over:{match_id}:{innings}:{over}"
            ball_id = f"ball:{match_id}:{innings}:{over}.{ball_in_over}"
            team_node = f"team:{match_id}:{batting_team}" if batting_team else ""

            add_node(nodes, match_node, "match", name=match_id, match_id=match_id)
            add_node(nodes, innings_node, "innings", name=str(innings), match_id=match_id, innings_index=str(innings))
            add_node(nodes, over_node, "over", name=str(over), match_id=match_id, innings_index=str(innings), over=str(over))
            add_node(
                nodes,
                ball_id,
                "ball",
                name=row.get("ball_number") or f"{over}.{ball_in_over}",
                match_id=match_id,
                innings_index=str(innings),
                over=str(over),
                ball_in_over=str(ball_in_over),
            )
            if team_node:
                add_node(nodes, team_node, "team", name=batting_team, match_id=match_id)
            if batsman:
                player_id = f"player:{batsman}"
                add_node(nodes, player_id, "player", name=batsman)
            if bowler:
                player_id = f"player:{bowler}"
                add_node(nodes, player_id, "player", name=bowler)
            if event_type:
                event_node = f"event:{event_type}"
                add_node(nodes, event_node, "event_type", name=event_type)
            if phase:
                phase_node = f"phase:{phase}"
                add_node(nodes, phase_node, "phase", name=phase)

            add_edge(edges, match_node, "has_innings", innings_node)
            add_edge(edges, innings_node, "has_over", over_node)
            add_edge(edges, over_node, "has_ball", ball_id)
            if team_node:
                add_edge(edges, innings_node, "batting_team", team_node)
            if batsman:
                add_edge(edges, ball_id, "batsman", f"player:{batsman}")
                if team_node:
                    add_edge(edges, team_node, "has_player", f"player:{batsman}")
            if bowler:
                add_edge(edges, ball_id, "bowler", f"player:{bowler}")
                if team_node:
                    add_edge(edges, team_node, "has_player", f"player:{bowler}")
            if event_type:
                add_edge(edges, ball_id, "event_type", f"event:{event_type}")
            if phase:
                add_edge(edges, ball_id, "phase", f"phase:{phase}")

            ball_state_rows.append(
                {
                    "ball_id": ball_id,
                    "match_id": match_id,
                    "innings_index": row.get("innings_index"),
                    "over": row.get("over"),
                    "ball_in_over": row.get("ball_in_over"),
                    "ball_number": row.get("ball_number"),
                    "ball_index": row.get("ball_index"),
                    "batting_team": batting_team,
                    "batsman": batsman,
                    "bowler": bowler,
                    "event_type": event_type,
                    "event_token": row.get("event_token"),
                    "result_raw": row.get("result_raw"),
                    "is_wicket": row.get("is_wicket"),
                    "is_boundary": row.get("is_boundary"),
                    "bat_runs": row.get("bat_runs"),
                    "extras_runs": row.get("extras_runs"),
                    "innings_runs": row.get("innings_runs"),
                    "innings_wickets": row.get("innings_wickets"),
                    "innings_overs": row.get("innings_overs"),
                    "crr": row.get("crr"),
                    "target_runs": row.get("target_runs"),
                    "runs_remaining": row.get("runs_remaining"),
                    "balls_remaining": row.get("balls_remaining"),
                    "rrr": row.get("rrr"),
                    "phase": phase,
                }
            )

    with nodes_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["node_id", "node_type", "name", "match_id", "innings_index", "over", "ball_in_over"],
        )
        writer.writeheader()
        for node in nodes.values():
            writer.writerow(node)

    with edges_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["source_id", "relation", "target_id"])
        for source_id, relation, target_id in sorted(edges):
            writer.writerow([source_id, relation, target_id])

    with state_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "ball_id",
                "match_id",
                "innings_index",
                "over",
                "ball_in_over",
                "ball_number",
                "ball_index",
                "batting_team",
                "batsman",
                "bowler",
                "event_type",
                "event_token",
                "result_raw",
                "is_wicket",
                "is_boundary",
                "bat_runs",
                "extras_runs",
                "innings_runs",
                "innings_wickets",
                "innings_overs",
                "crr",
                "target_runs",
                "runs_remaining",
                "balls_remaining",
                "rrr",
                "phase",
            ],
        )
        writer.writeheader()
        writer.writerows(ball_state_rows)

    return nodes_path, edges_path, state_path


def main():
    parser = argparse.ArgumentParser(description="Build a match knowledge graph from balls_enriched.csv")
    parser.add_argument("--config", default=None, help="Path to config.toml")
    args = parser.parse_args()

    config = load_config(args.config)
    nodes_path, edges_path, state_path = build_kg(config)
    print(nodes_path)
    print(edges_path)
    print(state_path)


if __name__ == "__main__":
    main()
