#!/usr/bin/env python3
"""Export past-exam annotations for guide content blocks."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_DIR = ROOT / "frontend/src/generated/examReferenceAnswers"
GUIDE_CONTENT_DIR = ROOT / "frontend/src/generated/guideContent"
DEFAULT_OUTPUT = ROOT / "frontend/src/generated/guideExamAnnotations"


OFFICIAL_EXAMS_BY_LEVEL: dict[str, dict[str, dict[str, str]]] = {
    "初級": {
        "jr_1141_s1": {
            "question_file": "mock_jr_1141_s1.json",
            "label": "科目一 公告試題（114年第四梯次）",
        },
        "jr_1141_s2": {
            "question_file": "mock_jr_1141_s2.json",
            "label": "科目二 公告試題（114年第四梯次）",
        },
        "jr_1151_s1": {
            "question_file": "mock_jr_1151_s1.json",
            "label": "科目一 公告試題（115年第一次）",
        },
        "jr_1151_s2": {
            "question_file": "mock_jr_1151_s2.json",
            "label": "科目二 公告試題（115年第一次）",
        },
        "jr_1152_s1": {
            "question_file": "mock_jr_1152_s1.json",
            "label": "科目一 公告試題（115年第二次）",
        },
        "jr_1152_s2": {
            "question_file": "mock_jr_1152_s2.json",
            "label": "科目二 公告試題（115年第二次）",
        },
    },
    "中級": {
        "mid_1141_s1": {
            "question_file": "mock_mid_1141_s1.json",
            "label": "科目一 公告試題（114年第二梯次）",
        },
        "mid_1141_s2": {
            "question_file": "mock_mid_1141_s2.json",
            "label": "科目二 公告試題（114年第二梯次）",
        },
        "mid_1141_s3": {
            "question_file": "mock_mid_1141_s3.json",
            "label": "科目三 公告試題（114年第二梯次）",
        },
        "mid_1151_s1": {
            "question_file": "mock_mid_1151_s1.json",
            "label": "科目一 公告試題（115年第一次）",
        },
        "mid_1151_s2": {
            "question_file": "mock_mid_1151_s2.json",
            "label": "科目二 公告試題（115年第一次）",
        },
        "mid_1151_s3": {
            "question_file": "mock_mid_1151_s3.json",
            "label": "科目三 公告試題（115年第一次）",
        },
    },
}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def question_number(question_id: str, fallback_index: int | None = None) -> int | None:
    match = re.search(r"_q(\d+)$", question_id)
    if match:
        return int(match.group(1))
    return fallback_index


def guide_block_index() -> dict[str, dict[str, set[str]]]:
    index: dict[str, dict[str, set[str]]] = {}
    for guide_dir in sorted(GUIDE_CONTENT_DIR.glob("*")):
        if not guide_dir.is_dir():
            continue
        guide_key = guide_dir.name
        by_node: dict[str, set[str]] = {}
        for path in sorted(guide_dir.glob("*.json")):
            content = load_json(path)
            block_ids = {
                str(block.get("id"))
                for block in content.get("blocks") or []
                if block.get("id")
            }
            by_node[path.stem] = block_ids
        index[guide_key] = by_node
    return index


def question_lookup(level: str, question_file: str) -> tuple[dict[str, dict[str, Any]], dict[int, dict[str, Any]], str]:
    path = ROOT / "data" / level / "questions" / question_file
    data = load_json(path)
    questions = data.get("questions") or []
    by_id = {str(question.get("id")): question for question in questions if question.get("id")}
    by_number: dict[int, dict[str, Any]] = {}
    for index, question in enumerate(questions, start=1):
        qid = str(question.get("id") or "")
        number = question_number(qid, index)
        if number is not None:
            by_number[number] = question
    return by_id, by_number, str(data.get("exam") or "")


def append_reason(entry: dict[str, Any], reason: str | None) -> None:
    if not reason:
        return
    reasons = entry.setdefault("reasons", [])
    if reason not in reasons:
        reasons.append(reason)


def block_sort_key(value: str) -> int | str:
    suffix = value.removeprefix("block-")
    if value.startswith("block-") and suffix.isdigit():
        return int(suffix)
    return value


def clear_json_output_dir(output_dir: Path) -> None:
    if not output_dir.exists():
        return
    if not output_dir.is_dir():
        raise SystemExit(f"Output path exists and is not a directory: {output_dir}")
    for path in sorted(output_dir.rglob("*.json"), reverse=True):
        path.unlink()
    for path in sorted((p for p in output_dir.rglob("*") if p.is_dir()), reverse=True):
        try:
            path.rmdir()
        except OSError:
            pass


def write_split_output(
    output_dir: Path,
    compact_by_guide: dict[str, dict[str, dict[str, list[dict[str, Any]]]]],
    stats: dict[str, int],
) -> dict[str, Any]:
    clear_json_output_dir(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    index_by_guide: dict[str, dict[str, dict[str, int]]] = {}
    for guide_key, nodes in compact_by_guide.items():
        guide_dir = output_dir / guide_key
        guide_dir.mkdir(parents=True, exist_ok=True)
        index_by_guide[guide_key] = {}
        for node_id, blocks in nodes.items():
            node_questions = {
                entry["id"]
                for entries in blocks.values()
                for entry in entries
            }
            node_payload = {
                "guideKey": guide_key,
                "nodeId": node_id,
                "stats": {
                    "questions": len(node_questions),
                    "guideBlocks": len(blocks),
                    "annotations": sum(len(entries) for entries in blocks.values()),
                },
                "blocks": blocks,
            }
            (guide_dir / f"{node_id}.json").write_text(
                json.dumps(node_payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            index_by_guide[guide_key][node_id] = node_payload["stats"]

    index_payload = {
        "source": "frontend/src/generated/examReferenceAnswers citations",
        "scope": "officialPastExams",
        "stats": stats,
        "byGuide": index_by_guide,
    }
    (output_dir / "index.json").write_text(
        json.dumps(index_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return index_payload


def export_annotations(output_path: Path, fail_on_missing: bool = True) -> dict[str, Any]:
    block_index = guide_block_index()
    by_guide: dict[str, dict[str, dict[str, dict[str, dict[str, Any]]]]] = {}
    missing_blocks: list[dict[str, Any]] = []
    missing_questions: list[dict[str, Any]] = []
    question_ids: set[str] = set()
    exam_count = 0

    for level, exams in OFFICIAL_EXAMS_BY_LEVEL.items():
        for exam_key, config in exams.items():
            reference_path = REFERENCE_DIR / f"{exam_key}.json"
            if not reference_path.exists():
                continue

            exam_count += 1
            references = load_json(reference_path)
            questions_by_id, questions_by_number, exam_title = question_lookup(level, config["question_file"])

            for reference_question_id, reference in sorted(references.items()):
                number = question_number(str(reference_question_id))
                question = questions_by_id.get(str(reference_question_id))
                if question is None and number is not None:
                    question = questions_by_number.get(number)
                if question is None:
                    missing_questions.append({
                        "examKey": exam_key,
                        "referenceQuestionId": reference_question_id,
                    })
                    continue

                actual_question_id = str(question.get("id") or reference_question_id)
                actual_number = question_number(actual_question_id, number) or number or 0
                annotation_id = f"{exam_key}:{actual_question_id}"
                question_ids.add(annotation_id)

                base_entry = {
                    "id": annotation_id,
                    "examKey": exam_key,
                    "examLabel": config["label"],
                    "examTitle": exam_title,
                    "route": f"/exam/{exam_key}",
                    "questionId": actual_question_id,
                    "questionNumber": actual_number,
                    "question": str(question.get("question") or ""),
                    "answer": str(reference.get("answer") or question.get("answer") or ""),
                    "confidence": reference.get("confidence"),
                }
                if actual_question_id != reference_question_id:
                    base_entry["referenceQuestionId"] = reference_question_id

                for citation in reference.get("citations") or []:
                    source_guide_key = citation.get("guide_key")
                    node_id = citation.get("node_id")
                    if not source_guide_key or not node_id:
                        continue
                    guide_key = f"{level}-{source_guide_key}"
                    valid_blocks = block_index.get(guide_key, {}).get(str(node_id), set())
                    for block_id in citation.get("block_ids") or []:
                        if block_id not in valid_blocks:
                            missing_blocks.append({
                                "examKey": exam_key,
                                "referenceQuestionId": reference_question_id,
                                "guideKey": guide_key,
                                "nodeId": node_id,
                                "blockId": block_id,
                            })
                            continue

                        guide_bucket = by_guide.setdefault(guide_key, {})
                        node_bucket = guide_bucket.setdefault(str(node_id), {})
                        block_bucket = node_bucket.setdefault(str(block_id), {})
                        entry = block_bucket.setdefault(annotation_id, dict(base_entry))
                        append_reason(entry, citation.get("why_relevant"))

    if fail_on_missing and (missing_blocks or missing_questions):
        raise SystemExit(
            f"Missing guide blocks: {len(missing_blocks)}; missing questions: {len(missing_questions)}"
        )

    compact_by_guide: dict[str, dict[str, dict[str, list[dict[str, Any]]]]] = {}
    for guide_key in sorted(by_guide):
        compact_by_guide[guide_key] = {}
        for node_id in sorted(by_guide[guide_key]):
            compact_by_guide[guide_key][node_id] = {}
            for block_id in sorted(
                by_guide[guide_key][node_id],
                key=block_sort_key,
            ):
                entries = sorted(
                    by_guide[guide_key][node_id][block_id].values(),
                    key=lambda item: (item["examKey"], item["questionNumber"], item["questionId"]),
                )
                compact_by_guide[guide_key][node_id][block_id] = entries

    block_count = sum(
        len(blocks)
        for nodes in compact_by_guide.values()
        for blocks in nodes.values()
    )
    annotation_count = sum(
        len(entries)
        for nodes in compact_by_guide.values()
        for blocks in nodes.values()
        for entries in blocks.values()
    )
    node_count = sum(len(nodes) for nodes in compact_by_guide.values())
    stats = {
        "exams": exam_count,
        "questions": len(question_ids),
        "guideNodes": node_count,
        "guideBlocks": block_count,
        "annotations": annotation_count,
        "missingQuestions": len(missing_questions),
        "missingBlocks": len(missing_blocks),
    }

    if output_path.suffix == ".json":
        payload = {
            "source": "frontend/src/generated/examReferenceAnswers citations",
            "scope": "officialPastExams",
            "stats": stats,
            "byGuide": compact_by_guide,
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return payload

    return write_split_output(output_path, compact_by_guide, stats)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args()

    output_path = args.output
    if not output_path.is_absolute():
        output_path = ROOT / output_path
    payload = export_annotations(output_path, fail_on_missing=not args.allow_missing)
    stats = payload["stats"]
    print(
        "Exported "
        f"{stats['annotations']} annotations from {stats['questions']} questions "
        f"to {output_path}"
    )


if __name__ == "__main__":
    main()
