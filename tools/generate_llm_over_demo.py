#!/usr/bin/env python3
import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR))

from config import get_path, load_config
from agentic.commentary_core import generate_over_script, load_overs
from agentic.over_summary import build_summary


def group_rows(rows):
    grouped = {}
    for row in rows:
        key = (
            row.get("match_id"),
            int(row.get("innings_index") or 0),
            int(row.get("over") or 0),
        )
        grouped.setdefault(key, []).append(row)
    return grouped


def summarize_over_rows(rows):
    summary = build_summary(rows)
    runs_list = [int(r.get("token_runs") or 0) for r in rows]
    has_four = any(r == 4 for r in runs_list)
    has_six = any(r >= 6 for r in runs_list)
    summary.update(
        {
            "has_four": has_four,
            "has_six": has_six,
            "over": int(rows[0].get("over") or 0),
            "innings": int(rows[0].get("innings_index") or 0),
            "match_id": rows[0].get("match_id"),
        }
    )
    return summary


def select_demo_overs(grouped, match_id):
    summaries = []
    for key, rows in grouped.items():
        if match_id and key[0] != match_id:
            continue
        summary = summarize_over_rows(rows)
        summaries.append(summary)

    summaries.sort(key=lambda r: (r["innings"], r["over"]))

    def pick(predicate):
        return next((s for s in summaries if predicate(s)), None)

    selections = [
        ("wicket_only", pick(lambda s: s["wicket_count"] > 0 and s["boundary_count"] == 0)),
        ("boundary_four_only", pick(lambda s: s["boundary_count"] > 0 and s["has_four"] and not s["has_six"] and s["wicket_count"] == 0)),
        ("boundary_six_only", pick(lambda s: s["boundary_count"] > 0 and s["has_six"] and not s["has_four"] and s["wicket_count"] == 0)),
        ("wicket_and_boundary", pick(lambda s: s["wicket_count"] > 0 and s["boundary_count"] > 0)),
        ("four_and_six", pick(lambda s: s["has_four"] and s["has_six"] and s["wicket_count"] == 0)),
    ]

    return [(label, summary) for label, summary in selections if summary]


def build_commentary(rows, over_summaries, config, selection, style, model, llm_per_ball=False):
    label, summary = selection
    filters = {
        "match_id": summary["match_id"],
        "innings": summary["innings"],
        "over": summary["over"],
        "over_ordinal": False,
    }
    over_rows = [
        r
        for r in rows
        if r.get("match_id") == summary["match_id"]
        and int(r.get("innings_index") or 0) == summary["innings"]
        and int(r.get("over") or 0) == summary["over"]
    ]
    text = generate_over_script(
        over_rows,
        rows,
        style,
        config=config,
        use_llm=True,
        model=model,
    )
    return {
        "label": label,
        "match_id": summary["match_id"],
        "innings": summary["innings"],
        "over": summary["over"],
        "text": text,
    }


def list_voices():
    say = shutil.which("say")
    if not say:
        return []
    result = subprocess.run([say, "-v", "?"], text=True, capture_output=True, check=False)
    voices = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if parts:
            voices.append(parts[0])
    return voices


def pick_voice(preferred=None):
    voices = list_voices()
    if preferred and preferred in voices:
        return preferred
    for voice in ["Aman", "Rishi", "Tara"]:
        if voice in voices:
            return voice
    return preferred


def write_audio(text, output_path, voice=None, rate=None):
    say = shutil.which("say")
    if not say:
        return False
    command = [say, "-o", str(output_path)]
    if voice:
        command += ["-v", voice]
    if rate:
        command += ["-r", str(rate)]
    command += [text]
    subprocess.run(command, check=True)
    return True


def main():
    parser = argparse.ArgumentParser(description="Generate LLM over demo text + audio.")
    parser.add_argument("--config", default=None, help="Path to config.toml")
    parser.add_argument("--match", default="CWC_2011_final_ALL", help="Match id to filter")
    parser.add_argument("--style", default="broadcast", help="Style to request")
    parser.add_argument("--model", default=None, help="Override LLM model")
    parser.add_argument("--voice", default=None, help="Optional say voice")
    parser.add_argument("--rate", type=int, default=175, help="Optional say rate (wpm)")
    parser.add_argument("--output-dir", default="agentic/demo/llm_audio", help="Output directory")
    args = parser.parse_args()

    config = load_config(args.config)
    overs_path = get_path(config, "overs_jsonl", section="files")
    rows, over_summaries = load_overs(Path(overs_path))

    grouped = group_rows(rows)
    selections = select_demo_overs(grouped, args.match)
    if not selections:
        raise SystemExit("No demo overs found for requested match.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir) / f"run_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    voice = pick_voice(args.voice)

    demo_records = []
    for selection in selections:
        record = build_commentary(rows, over_summaries, config, selection, args.style, args.model)
        demo_records.append(record)
        audio_path = output_dir / f"{record['label']}_innings{record['innings']}_over{record['over']}.aiff"
        if record["text"]:
            audio_text = " ".join(record["text"].splitlines())
            write_audio(audio_text, audio_path, voice=voice, rate=args.rate)
            record["audio_file"] = audio_path.name
        else:
            record["audio_file"] = ""

    out_md = output_dir / "demo_output.md"
    lines = [
        "# LLM commentary demo (overs)",
        f"match_id: {args.match}",
        f"style: {args.style}",
        f"voice: {voice or 'default'}",
        f"rate: {args.rate}",
        "",
    ]
    for record in demo_records:
        lines.extend(
            [
                f"## {record['label']}",
                f"match_id: {record['match_id']}",
                f"innings: {record['innings']}",
                f"over: {record['over']}",
                f"text: {record['text']}",
                f"audio: {record['audio_file']}",
                "",
            ]
        )
    out_md.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")

    out_json = output_dir / "demo_output.json"
    out_json.write_text(json.dumps(demo_records, indent=2), encoding="utf-8")

    print(f"Wrote {out_md}")


if __name__ == "__main__":
    main()
