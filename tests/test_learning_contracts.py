#!/usr/bin/env python3
"""Executable contract tests for learning-platform JSON and content hashes."""

from __future__ import annotations

import copy
import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.learning.contracts import (
    DocumentValidationError,
    SCHEMA_TARGETS,
    canonical_json_bytes,
    content_hash,
    notebook_content_hash,
    require_valid,
    validate_document,
    value_hash,
)


FIXTURES = ROOT / "tests" / "fixtures" / "learning" / "contracts"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class LearningContractTests(unittest.TestCase):
    def test_registered_schemas_are_draft_2020_12_and_loadable(self) -> None:
        schemas = list((ROOT / "schemas" / "learning").glob("*.schema.json"))
        self.assertGreaterEqual(len(schemas), 8)
        for path in schemas:
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self.assertTrue(payload["$id"].endswith(path.name))
        self.assertGreaterEqual(len(SCHEMA_TARGETS), 30)

    def test_small_positive_fixtures_validate(self) -> None:
        require_valid("question-revision", fixture("question-revision.json"))
        require_valid("review-policy", fixture("review-policy.json"))
        require_valid("release-manifest", fixture("release-manifest.json"))

    def test_invalid_enum_missing_field_and_unexpected_property_fail(self) -> None:
        question = fixture("question-revision.json")
        question["format"] = "free_text"
        question.pop("explanation")
        question["answer"] = "A"
        issues = validate_document("question-revision", question)
        self.assertTrue(any(issue.code == "schema.const" and issue.path == "/format" for issue in issues))
        self.assertTrue(any(issue.code == "schema.required" and issue.path == "" for issue in issues))
        self.assertTrue(any(issue.code == "schema.additionalProperties" and issue.path == "" for issue in issues))

    def test_hash_option_path_and_utc_formats_are_strict(self) -> None:
        question = fixture("question-revision.json")
        question["contentHash"] = "TODO"
        question["options"][0]["optionId"] = "A"
        self.assertTrue(any(issue.code == "schema.pattern" for issue in validate_document("question-revision", question)))

        source = {
            "resource": {"namespace": "resource", "key": "reference"},
            "revision": "v1",
            "hash": "sha256:" + "a" * 64,
            "kind": "external",
            "hashScope": "reviewed_capture",
            "retrievedAt": "2026-09-08T00:00:00+08:00",
            "reviewDueAt": "2026-09-07T00:00:00Z",
            "capture": {"mode": "authored_summary", "text": "Reviewed summary"},
            "artifactPath": "../escape.txt",
        }
        issues = validate_document("source-snapshot", source)
        self.assertTrue(any(issue.path == "/retrievedAt" for issue in issues))
        self.assertTrue(any(issue.path == "/artifactPath" for issue in issues))
        source["retrievedAt"] = "not-a-date"
        self.assertTrue(any(issue.code in {"schema.format", "schema.pattern"} for issue in validate_document("source-snapshot", source)))

    def test_topic_ref_requires_a_stable_id_and_carries_no_vocabulary_hash(self) -> None:
        ref = {"id": "topic-7f3a9c11", "name": "資料洩漏"}
        self.assertEqual(validate_document("topic-ref", ref), [])
        require_valid("topic-ref", ref)
        # 中文顯示名、空白與空字串都不是 contract identifier；別名不是可攜欄位；
        # 整份詞彙表的 hash 已退出這個契約（新增概念不該讓既有引用失效）；id 與 name 都必填。
        for payload, path in (({**ref, "id": "資料洩漏"}, "/id"),
                              ({**ref, "id": "topic data leakage"}, "/id"),
                              ({**ref, "id": ""}, "/id"),
                              ({**ref, "alias": "data leakage"}, ""),
                              ({**ref, "vocabularyHash": "sha256:" + "a" * 64}, ""),
                              ({"name": "資料洩漏"}, ""),
                              ({"id": "topic-7f3a9c11"}, "")):
            with self.subTest(payload=payload):
                issues = validate_document("topic-ref", payload)
                self.assertTrue(any(issue.path == path for issue in issues), issues)

    def test_local_question_and_lifecycle_invariants_fail_closed(self) -> None:
        question = fixture("question-revision.json")
        question["options"][1]["optionId"] = "opt-A"
        question["correctOptionId"] = "opt-C"
        codes = {issue.code for issue in validate_document("question-revision", question)}
        self.assertIn("contract.duplicate_option_id", codes)
        self.assertIn("contract.unknown_correct_option", codes)

        event = {
            "id": "event-1",
            "subject": {"kind": "unit", "id": "unit-1", "revision": 1, "hash": "sha256:" + "a" * 64},
            "from": "draft",
            "to": "published",
            "reason": "skip review",
            "reviewIds": [],
            "createdAt": "2026-09-07T00:00:00Z",
        }
        self.assertEqual(validate_document("lifecycle-event", event)[0].code, "contract.invalid_transition")

    def test_require_valid_exposes_structured_issues(self) -> None:
        with self.assertRaises(DocumentValidationError) as caught:
            require_valid("resource-ref", {"namespace": "unknown", "key": "x"})
        self.assertEqual(caught.exception.kind, "resource-ref")
        self.assertEqual(caught.exception.issues[0].path, "/namespace")

    def test_structurally_invalid_local_fields_return_issues_without_crashing(self) -> None:
        cases = [
            ("question-revision", {"options": [{"optionId": []}]}),
            ("source-snapshot", {"kind": "external", "retrievedAt": "2026-09-07T00:00:00Z", "reviewDueAt": "2026-09-08"}),
            ("lifecycle-event", {"from": [], "to": "in_review"}),
        ]
        for kind, payload in cases:
            with self.subTest(kind=kind):
                issues = validate_document(kind, payload)
                self.assertTrue(issues)
                self.assertTrue(any(issue.code.startswith("schema.") for issue in issues))

    def test_canonical_json_and_hash_projections_are_stable(self) -> None:
        self.assertEqual(canonical_json_bytes({"繁": "體", "a": [2, 1]}), b'{"a":[2,1],"\xe7\xb9\x81":"\xe9\xab\x94"}')
        self.assertEqual(value_hash({"b": 2, "a": 1}), value_hash({"a": 1, "b": 2}))
        with self.assertRaises(ValueError):
            canonical_json_bytes({"bad": math.nan})

        unit = {"id": "unit-1", "contentHash": "old", "status": "draft", "reviewIds": []}
        first = content_hash("learning-unit", unit, body_bytes=b"body")
        unit.update({"contentHash": "new", "status": "in_review", "reviewIds": ["review-1"]})
        self.assertEqual(first, content_hash("learning-unit", unit, body_bytes=b"body"))
        self.assertNotEqual(first, content_hash("learning-unit", unit, body_bytes=b"changed"))

    def test_notebook_hash_excludes_runtime_outputs(self) -> None:
        notebook = {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {"kernelspec": {"name": "python3"}},
            "cells": [{"id": "cell-1", "cell_type": "code", "source": ["x = 1"], "metadata": {"tags": ["exercise"]}, "outputs": [], "execution_count": None}],
        }
        changed = copy.deepcopy(notebook)
        changed["cells"][0]["outputs"] = [{"output_type": "stream", "text": ["1"]}]
        changed["cells"][0]["execution_count"] = 9
        self.assertEqual(notebook_content_hash(notebook), notebook_content_hash(changed))
        changed["cells"][0]["source"] = ["x = 2"]
        self.assertNotEqual(notebook_content_hash(notebook), notebook_content_hash(changed))

    def test_mock_hashes_exclude_release_identity_without_losing_pool_identity(self) -> None:
        blueprint = {"poolRef": {"id": "pool-1", "releaseId": "candidate", "hash": "sha256:" + "a" * 64}}
        original = content_hash("mock-blueprint", blueprint)
        blueprint["poolRef"]["releaseId"] = "release-final"
        self.assertEqual(original, content_hash("mock-blueprint", blueprint))
        blueprint["poolRef"]["hash"] = "sha256:" + "b" * 64
        self.assertNotEqual(original, content_hash("mock-blueprint", blueprint))

        analysis = {"releaseId": "candidate", "catalogHash": "sha256:" + "c" * 64}
        analysis_hash = content_hash("exam-analysis", analysis)
        analysis["releaseId"] = "release-final"
        self.assertEqual(analysis_hash, content_hash("exam-analysis", analysis))


if __name__ == "__main__":
    unittest.main()
