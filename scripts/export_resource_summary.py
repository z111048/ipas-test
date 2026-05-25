"""Export lightweight frontend resource summary data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_GENERATED = ROOT / "frontend" / "src" / "generated"

LEVELS = {
    "junior": {
        "level": "初級",
        "data_dir": ROOT / "data" / "初級",
        "subject_ids": ["s1", "s2"],
        "exam_keys": ["mock1", "mock2"],
        "sample_key": "sample",
    },
    "middle": {
        "level": "中級",
        "data_dir": ROOT / "data" / "中級",
        "subject_ids": ["mid-s1", "mid-s2", "mid-s3"],
        "exam_keys": ["mid1", "mid2", "mid3"],
        "sample_key": "midSample",
    },
}

PRACTICE_FILES = {
    "ai": "subject{n}_questions.json",
    "guide": "subject{n}_guide_exercises.json",
    "codex100": "subject{n}_codex100_questions.json",
}

EXAM_FILES = {
    "junior": {
        "mock1": "mock_exam1.json",
        "mock2": "mock_exam2.json",
        "sample": "sample_exam.json",
    },
    "middle": {
        "mid1": "mock_exam1.json",
        "mid2": "mock_exam2.json",
        "mid3": "mock_exam3.json",
        "midSample": "sample_exam.json",
    },
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def subject_number(subject_id: str) -> int:
    return int(subject_id.rsplit("s", 1)[1])


def summarize_questions(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "available": False,
            "total": 0,
            "firstChapterId": None,
            "chapterCounts": {},
        }
    data = read_json(path)
    chapter_counts = {
        chapter["id"]: len(chapter.get("questions", []))
        for chapter in data.get("chapters", [])
    }
    first_chapter_id = next(
        (chapter_id for chapter_id, count in chapter_counts.items() if count > 0),
        None,
    )
    total = sum(chapter_counts.values())
    return {
        "available": total > 0,
        "total": total,
        "firstChapterId": first_chapter_id,
        "chapterCounts": chapter_counts,
    }


def summarize_exam(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"available": False, "total": 0}
    data = read_json(path)
    total = data.get("total")
    if not isinstance(total, int):
        total = len(data.get("questions", []))
    return {"available": total > 0, "total": total}


def build_summary() -> dict[str, Any]:
    output: dict[str, Any] = {"levels": {}}
    for level_id, config in LEVELS.items():
        data_dir = config["data_dir"]
        subjects: dict[str, Any] = {}
        for subject_id in config["subject_ids"]:
            number = subject_number(subject_id)
            subjects[subject_id] = {
                practice_type: summarize_questions(
                    data_dir / "questions" / filename.format(n=number)
                )
                for practice_type, filename in PRACTICE_FILES.items()
                if practice_type != "codex100" or level_id == "middle"
            }

        exams = {
            exam_key: summarize_exam(data_dir / "questions" / filename)
            for exam_key, filename in EXAM_FILES[level_id].items()
        }

        output["levels"][level_id] = {
            "level": config["level"],
            "subjects": subjects,
            "exams": exams,
        }
    return output


def main() -> None:
    FRONTEND_GENERATED.mkdir(parents=True, exist_ok=True)
    target = FRONTEND_GENERATED / "resourceSummary.json"
    target.write_text(
        json.dumps(build_summary(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {target.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
