"""Append independently reviewed learning diagnostics without replacing old questions."""

from __future__ import annotations

import argparse
import copy
import json
import os
import tempfile
from collections import Counter
from pathlib import Path

from learning.contracts import blob_hash, value_hash
from learning.references import ReferenceError, ReferenceResolver, safe_path

DRAFT_PATH = "content/learning/evidence/assessment/reviewed-diagnostic-source.json"
REVIEW_PATH = "content/learning/evidence/assessment/mvp-question-review.json"
CANONICAL_PATH = "data/中級/questions/subject3_questions.json"
CHAPTER = {"levelId": "middle", "subjectId": "mid-s3", "chapterId": "mid-s3c9"}


def canonical_question(question: dict, chapter_title: str) -> dict:
    option_codes = {option["optionId"]: chr(65 + index) for index, option in enumerate(question["options"])}
    explanation = question["explanation"] + "\n\n" + "\n".join(
        f"{option_codes[option['optionId']]}：{option['explanation']}" for option in question["options"])
    return {"id": question["id"], "chapter_id": CHAPTER["chapterId"], "chapter_title": chapter_title,
            "question": question["stem"],
            "options": {option_codes[option["optionId"]]: option["text"] for option in question["options"]},
            "answer": option_codes[question["correctOptionId"]], "explanation": explanation,
            "difficulty": {"easy": "易", "medium": "中", "hard": "難"}[question["difficulty"]["value"]],
            "type": {"scenario": "情境型", "calculation": "計算型", "concept": "觀念型", "decision": "應用型"}[question["kind"]],
            "tags": ["主題診斷", question["unitId"]],
            "source_refs": {"unit_id": question["unitId"], "objective_ids": question["objectiveIds"],
                            "draft_path": DRAFT_PATH, "review_receipt": REVIEW_PATH}}


def reviewed_draft(root: Path | str) -> tuple[dict, dict]:
    resolver = ReferenceResolver(root)
    draft = resolver.read_json(DRAFT_PATH)
    receipt = resolver.read_json(REVIEW_PATH)
    if (receipt["draftHash"] != resolver.input_hashes[DRAFT_PATH]
            or receipt["reviewerId"] == draft["authorId"] or receipt["reviewerRole"] != "independent_model"
            or receipt["verdict"] != "approved"):
        raise ReferenceError("stale_or_unapproved_draft", "A current independent review is required before curation")
    if blob_hash(resolver.read_bytes(receipt["reportPath"])) != receipt["reportHash"]:
        raise ReferenceError("stale_review_report", "Independent review report changed")
    decisions = {item["id"]: item for item in receipt["questions"]}
    questions = draft["questions"]
    if len(questions) != 10 or len({question["id"] for question in questions}) != 10 or len(decisions) != 10:
        raise ReferenceError("diagnostic_count", "MVP requires exactly ten individually reviewed unique questions")
    distribution = Counter(question["unitId"] for question in questions)
    expected = {"unit-split-before-fit": 3, "unit-imbalanced-classification": 4, "unit-threshold-decision": 3}
    if distribution != expected or draft["distribution"] != expected:
        raise ReferenceError("diagnostic_distribution", "MVP unit distribution must be 3/4/3")
    kinds = Counter(question["kind"] for question in questions)
    if kinds["scenario"] < 3 or kinds["calculation"] < 2:
        raise ReferenceError("diagnostic_authenticity", "At least three scenarios and two calculations are required")
    for question in questions:
        decision = decisions.get(question["id"], {})
        if (decision.get("hash") != value_hash(question) or decision.get("verdict") != "approved"
                or decision.get("correctOptionId") != question["correctOptionId"]):
            raise ReferenceError("question_review_mismatch", question["id"])
        options = question["options"]
        if (len(options) != 4 or len({option["optionId"] for option in options}) != 4
                or len({option["text"] for option in options}) != 4
                or not all(option.get("explanation") for option in options)):
            raise ReferenceError("invalid_draft_options", question["id"])
        unit = resolver.read_json(f"content/learning/units/{question['unitId']}.json")
        if not set(question["objectiveIds"]).issubset({objective["id"] for objective in unit["objectives"]}):
            raise ReferenceError("unknown_objective", question["id"])
    return draft, receipt


def curate(root: Path | str, *, check: bool = False) -> dict:
    root = Path(root).resolve()
    draft, receipt = reviewed_draft(root)
    resolver = ReferenceResolver(root)
    resolver.chapter(CHAPTER)
    target = safe_path(root, CANONICAL_PATH)
    before = target.read_bytes()
    original = json.loads(before)
    candidate = copy.deepcopy(original)
    chapters = [chapter for chapter in candidate["chapters"] if chapter["id"] == CHAPTER["chapterId"]]
    if len(chapters) != 1:
        raise ReferenceError("ambiguous_chapter", "Exactly one target chapter is required")
    chapter = chapters[0]
    old = [question for item in candidate["chapters"] for question in item["questions"]]
    ids = [question["id"] for question in old]
    if len(ids) != len(set(ids)):
        raise ReferenceError("existing_qid_collision", "Existing source IDs are ambiguous")
    existing = {question["id"]: question for question in old}
    added = []
    for question in draft["questions"]:
        projected = canonical_question(question, chapter["title"])
        if question["id"] in existing:
            if existing[question["id"]] != projected:
                raise ReferenceError("curation_conflict", "Refusing to replace existing question: " + question["id"])
            continue
        chapter["questions"].append(projected)
        added.append(question["id"])
    # All pre-existing values, including cards and source refs, must be unchanged.
    after_by_id = {question["id"]: question for item in candidate["chapters"] for question in item["questions"]}
    if any(after_by_id[question["id"]] != question for question in old):
        raise ReferenceError("existing_content_changed", "Curation must preserve every existing question")
    output = json.dumps(candidate, ensure_ascii=False, indent=2).encode() + b"\n"
    if added and not check:
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".curation-", delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(output)
                handle.flush()
                os.fsync(handle.fileno())
            if target.read_bytes() != before:
                raise ReferenceError("source_changed_during_curation", "Source changed; no curation was committed")
            os.replace(temporary, target)
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)
    return {"status": "checked" if check else "curated", "path": CANONICAL_PATH, "added": added,
            "preserved": len(old), "beforeHash": blob_hash(before), "afterHash": blob_hash(output if added else before),
            "reviewerId": receipt["reviewerId"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        report = curate(args.repo_root, check=args.check)
    except (ReferenceError, KeyError, ValueError, OSError) as exc:
        report = {"status": "blocked", "reason": str(exc)}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(report["status"] == "blocked")


if __name__ == "__main__":
    raise SystemExit(main())
