#!/usr/bin/env python3
"""Export Codex exam reference answers for the frontend."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "frontend/src/generated/examReferenceAnswers"
ROUTES_BY_LEVEL = {
    "初級": {
        "exam1": "mock1",
        "exam2": "mock2",
        "sample": "sample",
    },
    "中級": {
        "exam1": "mid1",
        "exam2": "mid2",
        "exam3": "mid3",
        "sample": "midSample",
    },
}
STATS_KEYS = {
    "初級": "elementary",
    "中級": "middle",
}
KEEP_FIELDS = [
    "answer",
    "reference_answer",
    "option_analysis",
    "key_concepts",
    "citations",
    "confidence",
    "notes",
]


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def question_sort_key(path: Path) -> tuple[str, int, str]:
    stem = path.stem
    prefix, _, number = stem.rpartition("_q")
    try:
        return prefix, int(number), stem
    except ValueError:
        return prefix, 0, stem


def compact_answer(raw: dict[str, Any]) -> dict[str, Any]:
    return {field: raw[field] for field in KEEP_FIELDS if field in raw}


def export_reference_answers(level: str, output_path: Path) -> dict[str, Any]:
    run_root = ROOT / f"data/{level}/pipeline/exam_reference_answers"
    if not run_root.exists():
        raise SystemExit(f"Reference answer directory does not exist: {run_root}")

    route_map = ROUTES_BY_LEVEL.get(level)
    if not route_map:
        raise SystemExit(f"Unsupported level: {level}")

    exams: dict[str, dict[str, Any]] = {}
    stats: dict[str, int] = {}
    for source_key, route_key in route_map.items():
        outputs_dir = run_root / source_key / "outputs"
        if not outputs_dir.exists():
            continue

        answers: dict[str, Any] = {}
        for path in sorted(outputs_dir.glob("*.json"), key=question_sort_key):
            raw = load_json(path)
            question_id = str(raw.get("question_id") or path.stem)
            answers[question_id] = compact_answer(raw)

        exams[route_key] = answers
        stats[route_key] = len(answers)

    output_path.mkdir(parents=True, exist_ok=True)
    for route_key, answers in exams.items():
        (output_path / f"{route_key}.json").write_text(
            json.dumps(answers, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    stats_path = output_path / "stats.json"
    payload = load_json(stats_path) if stats_path.exists() else {}
    payload[STATS_KEYS[level]] = stats
    (output_path / "stats.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--level", default="中級")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    output_path = args.output
    if not output_path.is_absolute():
        output_path = ROOT / output_path
    payload = export_reference_answers(args.level, output_path)
    total = sum(payload[STATS_KEYS[args.level]].values())
    print(f"Exported {total} reference answers to {output_path}")


if __name__ == "__main__":
    main()
