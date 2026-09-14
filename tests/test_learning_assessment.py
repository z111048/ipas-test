"""Deterministic selection, hard quotas, qualification, and analysis denominators."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

from learning.assessment import assemble_mock_exam, topic_measures  # noqa: E402
from learning.contracts import blob_hash, content_hash, value_hash, validate_document  # noqa: E402
from learning.references import question_payload_path, question_payload_bytes  # noqa: E402
from learning.references import ReferenceResolver, ReferenceError  # noqa: E402
from test_learning_references import fixture_tree, write_json  # noqa: E402
from curate_learning_questions import curate, DRAFT_PATH, REVIEW_PATH, CANONICAL_PATH  # noqa: E402
from build_learning_assessment import assessment_inputs  # noqa: E402
from learning.publication import build_learning_content, load_candidate, validate_candidate, derive_lab_asset_bytes  # noqa: E402


def example_inputs():
    questions, identities, annotations, entries = {}, {}, {}, []
    groups = ["資料洩漏"] * 3 + ["評估指標"] * 4 + ["模型評估"] * 3
    for index, topic in enumerate(groups, 1):
        key = f"q:middle:subject3_questions:test-q{index:02}"
        question = {"questionKey": key, "revision": 1, "contentHash": "sha256:" + "0" * 64,
                    "format": "single_choice", "stem": f"測試題 {index}",
                    "options": [{"optionId": "opt-A", "text": "甲"}, {"optionId": "opt-B", "text": "乙"}],
                    "correctOptionId": "opt-A", "explanation": "測试fixture", "answerStatus": "verified",
                    "assets": [], "reviewIds": ["fixture-answer-review"], "sourceHashes": [value_hash("source")]}
        question["contentHash"] = content_hash("question-revision", question)
        questions[(key, 1)] = question
        identities[key] = {"questionKey": key, "levelId": "middle", "sourceKey": "subject3_questions", "legacyId": f"test-q{index:02}",
                           "kind": "chapter_practice", "sourcePath": "data/中級/questions/subject3_questions.json",
                           "chapterRef": {"levelId": "middle", "subjectId": "mid-s3", "chapterId": "mid-s3c9"},
                           "familyId": f"family-{index}", "identityReview": "verified"}
        annotations[key] = {"topics": [topic], "chapters": ["mid-s3c9"], "difficulty": None}
        entries.append({"question": {"questionKey": key, "revision": 1, "hash": question["contentHash"]},
                        "payloadPath": question_payload_path(key, 1), "fileHash": blob_hash(question_payload_bytes(question)),
                        "identityReview": "verified", "mappingReviewIds": ["fixture-mapping"], "difficultyReviewIds": []})
    pool = {"schemaVersion": 1, "id": "pool-fixture", "releaseId": "test-release", "contentHash": "sha256:" + "0" * 64,
            "policyHash": value_hash("policy"), "annotationSnapshotHash": value_hash(annotations), "questions": entries, "groups": []}
    pool["contentHash"] = content_hash("mock-pool", pool)
    blueprint = {"schemaVersion": 1, "id": "blueprint-fixture", "revision": 1, "contentHash": "sha256:" + "0" * 64,
                 "status": "in_review", "reviewIds": [], "dependencies": [], "title": "測試診斷", "levelId": "middle", "subjectIds": ["mid-s3"],
                 "questionCount": 10, "timeLimitSeconds": 600, "poolRef": {"id": pool["id"], "releaseId": pool["releaseId"], "hash": pool["contentHash"]},
                 "kinds": ["chapter_practice"], "format": "single_choice",
                 "quotas": [{"id": f"quota-{index}", "dimension": "topic", "key": topic, "min": count, "max": count, "mode": "hard", "priority": 1}
                            for index, (topic, count) in enumerate([( "資料洩漏", 3), ("評估指標", 4), ("模型評估", 3)])],
                 "seedPolicy": "user_or_generated", "algorithmVersion": "mock-selector-v1", "uniqueFamily": True,
                 "contextPolicy": "atomic_keep_order", "optionOrder": "seeded",
                 "scoring": {"correct": 1, "incorrect": 0, "unanswered": 0, "passingPercent": 60}}
    blueprint["contentHash"] = content_hash("mock-blueprint", blueprint)
    return blueprint, pool, questions, identities, annotations


def run_example(blueprint, pool, questions, identities, annotations, **kwargs):
    return assemble_mock_exam(blueprint, pool, questions=questions, identities=identities,
                              annotations=annotations, seed=kwargs.pop("seed", "0123456789abcdef0123456789abcdef"), **kwargs)


class AssessmentTests(unittest.TestCase):
    def test_ten_questions_three_four_three_and_determinism(self):
        args = example_inputs()
        first, second = run_example(*args), run_example(*args)
        self.assertEqual(first, second)
        self.assertEqual(first["status"], "ready", first)
        self.assertEqual(validate_document("assembly-result", first), [])
        self.assertEqual(len(first["selectedQuestionRevisions"]), 10)
        self.assertEqual(len({ref["questionKey"] for ref in first["selectedQuestionRevisions"]}), 10)
        self.assertEqual([sum(slot["quotaId"] == f"quota-{i}" for slot in first["slotAssignments"]) for i in range(3)], [3, 4, 3])
        golden = ROOT / "tests/fixtures/learning/references/assembly-golden.json"
        self.assertEqual(first, json.loads(golden.read_text())["expected"])

    def test_missing_question_does_not_weaken_count(self):
        blueprint, pool, questions, identities, annotations = example_inputs()
        pool["questions"].pop()
        pool["contentHash"] = content_hash("mock-pool", pool)
        blueprint["poolRef"]["hash"] = pool["contentHash"]
        blueprint["contentHash"] = content_hash("mock-blueprint", blueprint)
        result = run_example(blueprint, pool, questions, identities, annotations)
        self.assertEqual(result["status"], "insufficient_pool")
        self.assertEqual(result["unmet"][0], {"rule": "question_count", "required": 10, "eligible": 9})

    def test_disputed_answer_and_duplicate_family_cannot_enter(self):
        for mode in ["disputed", "family"]:
            blueprint, pool, questions, identities, annotations = example_inputs()
            key = pool["questions"][0]["question"]["questionKey"]
            if mode == "disputed":
                question = questions[(key, 1)]
                question["answerStatus"] = "disputed"
                question["contentHash"] = content_hash("question-revision", question)
                pool["questions"][0]["question"]["hash"] = question["contentHash"]
                pool["questions"][0]["fileHash"] = blob_hash(question_payload_bytes(question))
            else:
                other = pool["questions"][1]["question"]["questionKey"]
                identities[key]["familyId"] = identities[other]["familyId"]
            pool["contentHash"] = content_hash("mock-pool", pool)
            blueprint["poolRef"]["hash"] = pool["contentHash"]
            blueprint["contentHash"] = content_hash("mock-blueprint", blueprint)
            self.assertEqual(run_example(blueprint, pool, questions, identities, annotations)["status"], "insufficient_pool")

    def test_stale_hash_and_pool_change(self):
        args = example_inputs()
        first = run_example(*args)
        changed = copy.deepcopy(args)
        changed[1]["questions"][0]["fileHash"] = value_hash("bad")
        self.assertEqual(run_example(*changed)["status"], "stale_pool")
        changed = copy.deepcopy(args)
        changed[1]["policyHash"] = value_hash("new policy")
        changed[1]["contentHash"] = content_hash("mock-pool", changed[1])
        changed[0]["poolRef"]["hash"] = changed[1]["contentHash"]
        changed[0]["contentHash"] = content_hash("mock-blueprint", changed[0])
        second = run_example(*changed)
        self.assertEqual(second["status"], "ready", second)
        self.assertNotEqual(first["formId"], second["formId"])
        changed = copy.deepcopy(args)
        changed[4][next(iter(changed[4]))]["topics"] = ["changed without re-review"]
        self.assertEqual(run_example(*changed)["status"], "stale_pool")

    def test_search_limit_and_invalid_seed(self):
        self.assertEqual(run_example(*example_inputs(), search_limit=1)["reason"], "search_limit")
        with self.assertRaises(ValueError):
            run_example(*example_inputs(), seed="arbitrary text")

    def test_multi_topic_cannot_fill_two_slots_in_same_dimension(self):
        args = example_inputs()
        for annotation in args[4].values():
            annotation["topics"] = ["資料洩漏", "評估指標", "模型評估"]
        args[1]["annotationSnapshotHash"] = value_hash(args[4])
        args[1]["contentHash"] = content_hash("mock-pool", args[1])
        args[0]["poolRef"]["hash"] = args[1]["contentHash"]
        args[0]["contentHash"] = content_hash("mock-blueprint", args[0])
        result = run_example(*args)
        self.assertEqual(result["status"], "ready", result)
        keys = [(item["question"]["questionKey"], item["dimension"]) for item in result["slotAssignments"]]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(len(keys), 10)

    def test_denominator_preserves_unknowns_and_duplicate_edges_collapse(self):
        mappings = [{"questionKey": "q1", "topic": "評估", "relation": "assesses", "verdict": "correct"}] * 2
        row = topic_measures({"q1", "q2", "q3"}, {"q1", "q2"}, mappings, ["評估"])[0]
        self.assertEqual((row["population"], row["reviewed"], row["matched"], row["unknown"]), (3, 2, 1, 1))
        self.assertIsNone(row["prevalence"])
        self.assertEqual((row["reviewedPrevalence"], row["lowerBound"], row["upperBound"]), (1 / 2, 1 / 3, 2 / 3))
        self.assertIsNone(topic_measures(set(), set(), [], ["評估"])[0]["prevalence"])

    def test_curation_preserves_cards_and_rejects_stale_or_conflicting_drafts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture_tree(root)
            draft = json.loads((ROOT / DRAFT_PATH).read_text())
            write_json(root, DRAFT_PATH, draft)
            report = root / "review.md"
            report.write_text("Synthetic fixture review; never used for real approvals.\n")
            receipt = {"draftHash": blob_hash((root / DRAFT_PATH).read_bytes()), "reviewerId": "fixture-reviewer",
                       "reviewerRole": "independent_model", "verdict": "approved", "reportPath": "review.md",
                       "reportHash": blob_hash(report.read_bytes()), "questions": [
                           {"id": q["id"], "hash": value_hash(q), "correctOptionId": q["correctOptionId"], "verdict": "approved"} for q in draft["questions"]]}
            write_json(root, REVIEW_PATH, receipt)
            for unit in {q["unitId"] for q in draft["questions"]}:
                write_json(root, f"content/learning/units/{unit}.json", {"objectives": [{"id": obj} for q in draft["questions"] if q["unitId"] == unit for obj in q["objectiveIds"]]})
            original = {"id": "old-Q1", "question": "Original", "card": {"concept": "Preserve every byte-value", "custom": [1, 2]}}
            write_json(root, CANONICAL_PATH, {"chapters": [{"id": "mid-s3c9", "title": "模型訓練、評估與驗證", "questions": [original]}]})
            before = (root / CANONICAL_PATH).read_bytes()
            self.assertEqual(len(curate(root, check=True)["added"]), 10)
            self.assertEqual((root / CANONICAL_PATH).read_bytes(), before)
            self.assertEqual(len(curate(root)["added"]), 10)
            canonical = json.loads((root / CANONICAL_PATH).read_text())
            self.assertEqual(canonical["chapters"][0]["questions"][0], original)
            self.assertEqual(curate(root)["added"], [])
            canonical["chapters"][0]["questions"][1]["answer"] = "Z"
            write_json(root, CANONICAL_PATH, canonical)
            conflict = (root / CANONICAL_PATH).read_bytes()
            with self.assertRaises(ReferenceError):
                curate(root)
            self.assertEqual((root / CANONICAL_PATH).read_bytes(), conflict)
            draft["questions"][0]["stem"] = "Changed after review"
            write_json(root, DRAFT_PATH, draft)
            with self.assertRaises(ReferenceError):
                curate(root)

    def test_real_reviewed_sources_make_isolated_preview_and_corruption_keeps_pointer(self):
        prepared = assessment_inputs(ROOT)
        self.assertEqual(prepared["assembly"]["status"], "ready")
        self.assertEqual(sum(row["present"] for row in prepared["analysis"]["inventory"]), 150)
        self.assertEqual([row["reviewed"] for row in prepared["analysis"]["measures"]], [5, 5, 5])
        candidate = load_candidate(ROOT, additional_documents=prepared["additional_documents"])
        self.assertEqual(validate_candidate(candidate, preview=True)[0], [])
        derive_lab_asset_bytes(candidate)
        inputs = {**prepared["additional_inputs"], **candidate.resolver.input_hashes}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for path in inputs:
                destination = root / path
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes((ROOT / path).read_bytes())
            arguments = {key: prepared[key] for key in ("additional_documents", "additional_artifacts", "additional_inputs")}
            report = build_learning_content(root, preview=True, lab_assets_manifest="", **arguments)
            self.assertEqual(report["status"], "preview_ready", report)
            pointer = root / "frontend/src/generated/learning/preview.json"
            before = pointer.read_bytes()
            release = pointer.parent / "previews" / report["releaseId"]
            manifest = json.loads((release / "manifest.json").read_text())
            for entry in manifest["files"]:
                self.assertEqual(blob_hash((release / entry["path"]).read_bytes()), entry["hash"])
            self.assertFalse((root / "frontend/public/labs").exists())
            self.assertFalse((root / "data/learning/pipeline").exists())
            self.assertFalse((pointer.parent / "current.json").exists())
            artifacts = copy.deepcopy(prepared["additional_artifacts"])
            assembly_path = next(path for path in artifacts if path.startswith("assemblies/"))
            artifacts[assembly_path]["document"]["displayedOptionIds"][0]["optionIds"].reverse()
            arguments["additional_artifacts"] = artifacts
            rejected = build_learning_content(root, preview=True, lab_assets_manifest="", **arguments)
            self.assertEqual(rejected["status"], "blocked", rejected)
            self.assertEqual(pointer.read_bytes(), before)
            self.assertTrue(any(issue["code"] == "assembly_mismatch" for issue in rejected["issues"]))


if __name__ == "__main__":
    unittest.main()
