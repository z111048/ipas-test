"""Export lightweight frontend resource summary data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from resource_catalog import exam_entries, level_entries


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_GENERATED = ROOT / "frontend" / "src" / "generated"

# 2026-08-09：移除 codex100（對外名稱「精選 100 題」）。題庫改為每科一份
# 熱度配額題庫（ai）＋ 學習指引抽取題（guide），不再有第二份重疊的生成題庫。
PRACTICE_FILES = {
    "ai": "subject{n}_questions.json",
    "guide": "subject{n}_guide_exercises.json",
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


def summarize_visuals() -> dict[str, Any]:
    """Count concept-card images per level from generated guideImages.json."""
    path = FRONTEND_GENERATED / "guideImages.json"
    if not path.exists():
        return {"total": 0, "byLevel": {}}
    data = read_json(path)
    images = data.get("images", [])
    by_level: dict[str, int] = {}
    for image in images:
        level = image.get("level") or "其他"
        by_level[level] = by_level.get(level, 0) + 1
    return {"total": len(images), "byLevel": by_level}


def build_summary() -> dict[str, Any]:
    output: dict[str, Any] = {"levels": {}, "visuals": summarize_visuals()}
    for level in level_entries():
        level_id = level["id"]
        data_level = level["dataLevel"]
        data_dir = ROOT / "data" / data_level
        manifest = read_json(data_dir / "toc_manifest.json")
        subjects: dict[str, Any] = {}
        for subject in manifest.get("subjects", []):
            subject_id = subject["id"]
            number = subject_number(subject_id)
            subjects[subject_id] = {
                practice_type: summarize_questions(
                    data_dir / "questions" / filename.format(n=number)
                )
                for practice_type, filename in PRACTICE_FILES.items()
            }

        # Stable output order keeps the generated file reviewable while the catalog
        # remains free to order exams for navigation (newest first).
        exams = {}
        for exam in sorted(
            exam_entries(level=data_level),
            key=lambda item: (item["kind"] == "sample", item["routeKey"]),
        ):
            exams[exam["routeKey"]] = summarize_exam(
                data_dir / "questions" / exam["questionFile"]
            )

        output["levels"][level_id] = {
            "level": data_level,
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
