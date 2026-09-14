"""Complete-candidate publication, review qualification, and pointer rollback tests."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

from learning.contracts import blob_hash, content_hash, value_hash, notebook_content_hash  # noqa: E402
from learning.publication import build_learning_content, load_candidate, dependency_hashes, validate_reviews  # noqa: E402
from learning.references import ReferenceResolver, question_payload_path, question_payload_bytes  # noqa: E402
from test_learning_references import fixture_tree, question_document, write_json  # noqa: E402


def learning_unit(root: Path, guide_ref: dict) -> dict:
    unit_id = "unit-metrics"
    phases = ["context", "concept_bridge", "worked_example", "guided_practice", "independent_practice", "misconceptions", "assessment_reflection"]
    body = "# 指標決策\n\n" + "\n\n".join(f"## {phase}\n\n可核對的教學內容。" for phase in phases) + "\n"
    body_ref = "content/learning/units/unit-metrics.md"
    (root / body_ref).parent.mkdir(parents=True, exist_ok=True)
    (root / body_ref).write_text(body, encoding="utf-8")
    objectives = [f"{unit_id}::calculate", f"{unit_id}::decide"]
    unit = {"schemaVersion": 1, "id": unit_id, "revision": 1, "contentHash": "sha256:" + "0" * 64,
            "status": "in_review", "reviewIds": [], "dependencies": [], "title": "指標決策", "summary": "根據資料決定指標。",
            "bodyRef": body_ref, "levelIds": ["middle"],
            "chapterRefs": [{"levelId": "middle", "subjectId": "mid-s3", "chapterId": "mid-s3c9"}],
            "topicRefs": [{"id": "topic-11111111", "name": "評估指標"}],
            "guideRefs": [guide_ref], "gapStatement": "把指標計算轉成決策練習。",
            "objectives": [{"id": identity, "action": "計算並解釋", "condition": "給定混淆矩陣", "criterion": "誤差小於0.001", "assessmentIds": ["assess-1"]} for identity in objectives],
            "prerequisites": [], "estimatedMinutes": 20,
            "sections": [{"id": phase, "kind": phase, "bodyAnchor": phase, "objectiveIds": objectives, "claimIds": []} for phase in phases],
            "claims": [], "assessments": [{"id": "assess-1", "kind": "calculation", "prompt": "計算指標並說明選擇。", "objectiveIds": objectives,
                                               "expectedEvidence": "計算與理由。", "rubricId": "rubric-1"}],
            "rubrics": [{"id": "rubric-1", "criteria": [{"criterion": "計算正確", "passEvidence": "誤差小於0.001"}]}],
            "evidenceIds": [], "labRefs": [], "projectRefs": []}
    unit["contentHash"] = content_hash("learning-unit", unit, body_bytes=body.encode())
    write_json(root, "content/learning/units/unit-metrics.json", unit)
    return unit


def policy_for_unit() -> dict:
    return {"schemaVersion": 1, "id": "test-policy", "version": 1, "requirements": [
        {"subjectKind": "learning-unit", "responsibility": responsibility,
         "allowedReviewerRoles": roles, "qualificationScope": "metrics", "rubricVersion": "test-v1",
         "requiredCheckCodes": codes, "independentFromAuthor": independent}
        for responsibility, roles, codes, independent in [
            ("domain_content", ["human", "independent_model"], ["source_fidelity", "objective_alignment", "practical_accuracy"], True),
            ("deterministic_contract", ["automated_check"], ["schema", "references", "hash_integrity"], False)]]}


def approve_fixture(root: Path, unit: dict) -> None:
    """Only synthetic fixture approvals, never applied to repository content."""
    policy = policy_for_unit()
    write_json(root, "content/learning/review-policy.json", policy)
    proof = {"id": "fixture-proof", "revision": 1, "contentHash": "sha256:" + "0" * 64,
             "kind": "editorial_reasoning", "claim": "Synthetic test qualification and check evidence."}
    proof["contentHash"] = content_hash("evidence", proof)
    write_json(root, "content/learning/evidence/fixture-proof.json", proof)
    hashes = dependency_hashes(unit, ReferenceResolver(root))
    unit["reviewIds"] = []
    for i, requirement in enumerate(policy["requirements"]):
        identity = f"fixture-review-{i}"
        review = {"id": identity, "subject": {"kind": "learning-unit", "id": unit["id"], "revision": 1, "hash": unit["contentHash"]},
                  "dependencyHashes": hashes, "rubricVersion": "test-v1", "reviewerId": f"fixture-reviewer-{i}",
                  "reviewerRole": requirement["allowedReviewerRoles"][0], "authorId": "fixture-author",
                  "responsibility": requirement["responsibility"],
                  "qualification": {"scope": ["metrics"], "evidenceIds": [proof["id"]], "grantedBy": "fixture-maintainer", "grantedAt": "2026-09-01T00:00:00Z"},
                  "evidenceRefs": [{"id": proof["id"], "revision": 1, "hash": proof["contentHash"]}],
                  "verdict": "approved", "checks": [{"code": code, "verdict": "pass", "evidenceIds": [proof["id"]]} for code in requirement["requiredCheckCodes"]],
                  "createdAt": "2026-09-07T00:00:00Z", "rationale": "Only a unit-test fixture."}
        write_json(root, f"content/learning/reviews/{identity}.json", review)
        unit["reviewIds"].append(identity)
    write_json(root, "content/learning/units/unit-metrics.json", unit)


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.ref = fixture_tree(self.root)
        self.unit = learning_unit(self.root, self.ref)
        write_json(self.root, "content/learning/review-policy.json", policy_for_unit())

    def tearDown(self):
        self.temporary.cleanup()

    def pointer(self, name="current.json") -> Path:
        return self.root / "frontend/src/generated/learning" / name

    def test_unreviewed_cannot_publish_but_preview_is_explicit(self):
        rejected = build_learning_content(self.root)
        self.assertEqual(rejected["status"], "blocked", rejected)
        self.assertFalse(self.pointer().exists())
        report = build_learning_content(self.root, preview=True)
        self.assertEqual(report["status"], "preview_ready", report)
        self.assertTrue(report["unmetReviews"])
        pointer = json.loads(self.pointer("preview.json").read_text())
        self.assertEqual(pointer["availability"], "preview")
        self.assertTrue(pointer["manifestPath"].startswith("previews/"))
        self.assertFalse(self.pointer().exists())
        source = json.loads((self.root / "content/learning/units/unit-metrics.json").read_text())
        self.assertEqual(source["status"], "in_review")
        self.assertFalse((self.root / "frontend/public/labs").exists())

    def test_check_and_dry_run_are_read_only(self):
        before = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        for option in ({"check": True}, {"dry_run": True}):
            report = build_learning_content(self.root, preview=True, **option)
            self.assertNotEqual(report["status"], "blocked", report)
        after = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(before, after)

    def test_identical_source_produces_identical_release_bytes(self):
        first = build_learning_content(self.root, preview=True)
        self.assertEqual(first["status"], "preview_ready", first)
        directory = self.pointer().parent / "previews" / first["releaseId"]
        before = {path.relative_to(directory): path.read_bytes() for path in directory.rglob("*") if path.is_file()}
        second = build_learning_content(self.root, preview=True)
        after = {path.relative_to(directory): path.read_bytes() for path in directory.rglob("*") if path.is_file()}
        self.assertEqual(first["releaseId"], second["releaseId"])
        self.assertEqual(before, after)

    def test_source_edit_blocks_and_preserves_previous_release(self):
        approve_fixture(self.root, self.unit)
        first = build_learning_content(self.root)
        self.assertEqual(first["status"], "published", first)
        old_pointer = self.pointer().read_bytes()
        body = self.root / self.unit["bodyRef"]
        body.write_text(body.read_text() + "改變教學結論。\n", encoding="utf-8")
        report = build_learning_content(self.root)
        self.assertEqual(report["status"], "blocked", report)
        self.assertTrue(any(issue["code"] == "content_hash_mismatch" for issue in report["issues"]))
        self.assertEqual(self.pointer().read_bytes(), old_pointer)

    def test_review_cannot_be_reused_after_rehash_or_self_qualification(self):
        approve_fixture(self.root, self.unit)
        path = self.root / "content/learning/reviews/fixture-review-0.json"
        review = json.loads(path.read_text())
        for mutate in [lambda row: row["subject"].update(hash="sha256:" + "f" * 64),
                       lambda row: row.update(reviewerId=row["authorId"]),
                       lambda row: row["qualification"].update(grantedBy=row["reviewerId"]),
                       lambda row: row["checks"][0].update(verdict="not_run"),
                       lambda row: row.update(evidenceRefs=[])]:
            modified = copy.deepcopy(review)
            mutate(modified)
            write_json(self.root, path.relative_to(self.root).as_posix(), modified)
            report = build_learning_content(self.root, check=True)
            self.assertEqual(report["status"], "blocked", report)
        write_json(self.root, path.relative_to(self.root).as_posix(), review)

    def test_pointer_replace_failure_keeps_previous_pointer(self):
        approve_fixture(self.root, self.unit)
        first = build_learning_content(self.root)
        self.assertEqual(first["status"], "published", first)
        old_pointer = self.pointer().read_bytes()
        with patch("learning.publication.os.replace", side_effect=OSError("injected commit failure")):
            report = build_learning_content(self.root)
        self.assertEqual(report["status"], "blocked", report)
        self.assertEqual(self.pointer().read_bytes(), old_pointer)
        self.assertEqual(list(self.pointer().parent.glob(".pointer-*")), [])

    def test_source_mutation_during_staging_cannot_activate_candidate(self):
        first = build_learning_content(self.root, preview=True)
        self.assertEqual(first["status"], "preview_ready", first)
        old_pointer = self.pointer("preview.json").read_bytes()

        def mutate_source():
            path = self.root / "data/topics/topics.json"
            path.write_text(path.read_text() + " ", encoding="utf-8")

        result = build_learning_content(self.root, preview=True, before_pointer=mutate_source)
        self.assertEqual(result["status"], "blocked", result)
        self.assertEqual(result["issues"][-1]["code"], "source_changed_during_build")
        self.assertEqual(self.pointer("preview.json").read_bytes(), old_pointer)

    def test_existing_immutable_release_is_never_overwritten(self):
        first = build_learning_content(self.root, preview=True)
        self.assertEqual(first["status"], "preview_ready", first)
        pointer = self.pointer("preview.json").read_bytes()
        index = self.pointer().parent / "previews" / first["releaseId"] / "index.json"
        index.write_text("corrupted", encoding="utf-8")
        report = build_learning_content(self.root, preview=True)
        self.assertEqual(report["status"], "blocked", report)
        self.assertEqual(index.read_text(), "corrupted")
        self.assertEqual(self.pointer("preview.json").read_bytes(), pointer)

    def test_empty_bundle_is_not_a_success(self):
        (self.root / "content/learning/units/unit-metrics.json").unlink()
        report = build_learning_content(self.root, preview=True)
        self.assertEqual(report["status"], "blocked", report)
        self.assertTrue(any(issue["code"] == "empty_bundle" for issue in report["issues"]))

    def test_question_adapter_injection_exports_actual_payload_and_rejects_collision(self):
        question = question_document(self.root, "middle")
        key = ("question-revision", question["questionKey"], question["revision"])
        report = build_learning_content(self.root, preview=True, additional_documents={key: question})
        self.assertEqual(report["status"], "preview_ready", report)
        directory = self.pointer().parent / "previews" / report["releaseId"]
        index = json.loads((directory / "question-index.json").read_text())
        self.assertEqual(index["questions"][0]["questionKey"], "q:middle:sample:Q1")
        payload = json.loads((directory / index["questions"][0]["path"]).read_text())
        self.assertEqual(payload["correctOptionId"], "opt-D")
        self.assertEqual(payload["answerStatus"], "legacy_unverified")
        bad_key = ("question-revision", "q:junior:sample:Q1", 1)
        bad = build_learning_content(self.root, preview=True, additional_documents={bad_key: question})
        self.assertEqual(bad["status"], "blocked", bad)

    def test_mock_pool_injection_binds_real_payload_bytes(self):
        question = question_document(self.root, "middle")
        key = ("question-revision", question["questionKey"], question["revision"])
        pool = {"schemaVersion": 1, "id": "pool-metrics", "releaseId": "candidate",
                "contentHash": "sha256:" + "0" * 64, "policyHash": value_hash("test-policy"),
                "annotationSnapshotHash": value_hash("test-annotations"), "groups": [],
                "questions": [{"question": {"questionKey": question["questionKey"], "revision": 1, "hash": question["contentHash"]},
                               "payloadPath": question_payload_path(question["questionKey"], 1),
                               "fileHash": blob_hash(question_payload_bytes(question)), "identityReview": "verified",
                               "mappingReviewIds": [], "difficultyReviewIds": []}]}
        pool["contentHash"] = content_hash("mock-pool", pool)
        additional = {key: question, ("mock-pool", pool["id"], 1): pool}
        report = build_learning_content(self.root, preview=True, additional_documents=additional)
        self.assertEqual(report["status"], "preview_ready", report)
        directory = self.pointer().parent / "previews" / report["releaseId"]
        payload = json.loads((directory / "pools/pool-metrics.json").read_text())
        self.assertEqual(payload["document"]["questions"][0]["fileHash"], blob_hash((directory / pool["questions"][0]["payloadPath"]).read_bytes()))
        corrupted = copy.deepcopy(pool)
        corrupted["questions"][0]["fileHash"] = "sha256:" + "0" * 64
        corrupted["contentHash"] = content_hash("mock-pool", corrupted)
        report = build_learning_content(self.root, preview=True, additional_documents={key: question, ("mock-pool", pool["id"], 1): corrupted})
        self.assertEqual(report["status"], "blocked", report)
        self.assertTrue(any(issue["code"] == "pool_payload_mismatch" for issue in report["issues"]))

    def test_preview_lab_assets_stay_out_of_production_public_directory(self):
        lab_id = "lab-metrics"
        objective = self.unit["objectives"][0]["id"]
        notebook = {"nbformat": 4, "nbformat_minor": 5, "metadata": {"learning": {"labId": lab_id, "revision": 1}},
                    "cells": [{"id": "setup", "cell_type": "code", "source": ["assert 2 + 2 == 4\n"], "outputs": [], "execution_count": None,
                               "metadata": {"learning": {"labId": lab_id, "revision": 1, "cellId": "setup", "phase": "setup", "objectiveIds": [objective], "audience": "both"}}}]}
        notebook_path = f"notebooks/labs/{lab_id}.ipynb"
        write_json(self.root, notebook_path, notebook)
        lock_path = f"notebooks/labs/{lab_id}/requirements.lock"
        (self.root / lock_path).parent.mkdir(parents=True, exist_ok=True)
        (self.root / lock_path).write_text("# dependency-free test fixture\n", encoding="utf-8")
        asset_data = json.dumps(notebook).encode()
        artifacts = [{"variant": variant, "path": f"frontend/public/labs/{lab_id}/1/{variant}.ipynb",
                      "hash": blob_hash(asset_data), "size": len(asset_data), "revision": 1} for variant in ("starter", "solution")]
        lab = {"schemaVersion": 1, "id": lab_id, "revision": 1, "contentHash": "sha256:" + "0" * 64,
               "status": "in_review", "reviewIds": [], "dependencies": [], "title": "CPU指標練習",
               "unitRefs": [{"kind": "unit", "id": self.unit["id"], "revision": 1}],
               "chapterRefs": self.unit["chapterRefs"], "topicRefs": self.unit["topicRefs"], "objectiveIds": [objective],
               "sourceNotebookRef": notebook_path, "notebookHash": notebook_content_hash(notebook),
               "environment": {"pythonVersion": "3.12", "lockRef": lock_path, "lockHash": blob_hash((self.root / lock_path).read_bytes()),
                               "kernelName": "python3", "runtimeProfile": "cpu", "seed": 42},
               "executionPolicy": {"cpuOnly": True, "maxMemoryMb": 4096, "cellTimeoutSeconds": 60, "totalTimeoutSeconds": 300, "networkPolicy": "offline"},
               "datasets": [], "steps": [{"id": "step-setup", "phase": "setup", "cellIds": ["setup"], "objectiveIds": [objective], "estimatedMinutes": 1, "expectedArtifacts": []}],
               "checks": [{"id": "sum-check", "objectiveIds": [objective], "artifactRef": "metrics.json", "predicate": "sum equals 4", "severity": "block"}],
               "rubric": [{"criterion": "計算", "passEvidence": "結果4"}], "reflectionPrompts": ["為什麼？"], "artifacts": artifacts}
        lab["contentHash"] = content_hash("lab", lab)
        write_json(self.root, "content/learning/labs/lab-metrics.json", lab)
        report = build_learning_content(self.root, preview=True, asset_bytes={entry["path"]: asset_data for entry in artifacts})
        self.assertEqual(report["status"], "preview_ready", report)
        self.assertFalse((self.root / "frontend/public").exists())
        directory = self.pointer().parent / "previews" / report["releaseId"]
        item = json.loads((directory / "labs/lab-metrics.json").read_text())
        self.assertEqual(len(item["assetLocations"]), 2)
        for entry in item["assetLocations"]:
            self.assertTrue(entry["path"].startswith("assets/labs/"))
            self.assertEqual((directory / entry["path"]).read_bytes(), asset_data)


if __name__ == "__main__":
    unittest.main()
