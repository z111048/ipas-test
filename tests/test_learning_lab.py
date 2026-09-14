#!/usr/bin/env python3
"""Contract and clean-kernel acceptance tests for the MVP learning lab."""

from __future__ import annotations

import csv
import json
import sys
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.learning.references import ReferenceResolver  # noqa: E402
from scripts.verify_learning_labs import independently_check_metrics, verify  # noqa: E402


class LearningLabTests(unittest.TestCase):
    maxDiff = None

    def load(self, relative: str):
        return json.loads((ROOT / relative).read_text(encoding="utf-8"))

    def documents(self):
        documents = {}
        rows = []
        for kind, pattern in (
            ("learning-unit", "content/learning/units/*.json"),
            ("project", "content/learning/projects/*.json"),
            ("lab", "content/learning/labs/*.json"),
            ("evidence", "content/learning/evidence/*.json"),
        ):
            for path in ROOT.glob(pattern):
                data = json.loads(path.read_text(encoding="utf-8"))
                documents[(kind, data["id"], data["revision"])] = data
                rows.append((kind, path, data))
        return documents, rows

    def test_authored_sources_have_valid_schema_references_and_hashes(self):
        documents, rows = self.documents()
        resolver = ReferenceResolver(ROOT, documents=documents, assessment_at="2026-09-07T12:00:00Z")
        for kind, path, document in rows:
            self.assertEqual(resolver.validate(kind, document), [], path)
            if "status" in document:
                self.assertEqual(document["status"], "in_review")
                self.assertEqual(document.get("reviewIds"), [])

    def test_fixture_and_split_contract(self):
        directory = ROOT / "notebooks/labs/lab-imbalanced-classification/fixtures"
        with (directory / "equipment_alerts_v1.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 2000)
        self.assertEqual(sum(int(row["is_anomaly"]) for row in rows), 100)
        self.assertEqual([key for key in rows[0] if key.startswith("feature_")], [f"feature_{i}" for i in range(1, 9)])
        self.assertEqual(len({row["row_id"] for row in rows}), 2000)
        split = self.load("notebooks/labs/lab-imbalanced-classification/fixtures/split_manifest_v1.json")
        sets = {name: set(ids) for name, ids in split["splits"].items()}
        self.assertEqual({name: len(ids) for name, ids in sets.items()}, {"train": 1200, "validation": 400, "test": 400})
        self.assertFalse(sets["train"] & sets["validation"])
        self.assertFalse(sets["train"] & sets["test"])
        self.assertFalse(sets["validation"] & sets["test"])
        self.assertEqual(set().union(*sets.values()), {row["row_id"] for row in rows})

    def test_diagnostic_draft_distribution_and_explanations(self):
        path = ROOT / "data/learning/pipeline/mvp-authoring/questions.json"
        if not path.exists():
            self.skipTest("authoring pipeline drafts are intentionally gitignored")
        draft = json.loads(path.read_text(encoding="utf-8"))
        questions = draft["questions"]
        self.assertEqual(len(questions), 10)
        self.assertEqual(Counter(row["unitId"] for row in questions), {
            "unit-split-before-fit": 3,
            "unit-imbalanced-classification": 4,
            "unit-threshold-decision": 3,
        })
        self.assertGreaterEqual(sum(row["kind"] == "scenario" for row in questions), 3)
        self.assertGreaterEqual(sum(row["kind"] == "calculation" for row in questions), 2)
        self.assertEqual(len({row["id"] for row in questions}), 10)
        for row in questions:
            self.assertEqual(len(row["options"]), 4)
            self.assertIn(row["correctOptionId"], {option["optionId"] for option in row["options"]})
            self.assertTrue(row["explanation"])
            self.assertTrue(all(option["explanation"] for option in row["options"]))
            self.assertEqual(row["difficulty"]["basis"], "editorial")

    def test_fault_fixture_matches_executable_checks(self):
        cases = self.load("tests/fixtures/learning/lab/fault-cases.json")["cases"]
        self.assertEqual([case["id"] for case in cases], ["all-data-fit", "test-as-validation", "precision-recall-swap"])
        self.assertTrue(all(case["expected"] == "rejected" for case in cases))

    def test_external_verifier_rejects_claim_only_exploits(self):
        split = self.load("notebooks/labs/lab-imbalanced-classification/fixtures/split_manifest_v1.json")
        data_path = ROOT / "notebooks/labs/lab-imbalanced-classification/fixtures/equipment_alerts_v1.csv"
        forged = {
            "fitRowIds": [],
            "dummyFitRowIds": [],
            "thresholdSelectionRowIds": split["splits"]["validation"],
            "threshold": 0.5,
            "validationTable": [{"threshold": 0.5, "tn": 0, "fp": 0, "fn": 0, "tp": 0,
                                 "accuracy": 0, "precision": 0, "recall": 99, "f1": 0, "average_cost": -100}],
            "sensitivityFn5": {"threshold": 0.5, "thresholdSelectionRowIds": split["splits"]["validation"], "validationTable": []},
            "test": {"rowIds": ["invented-a", "invented-b"], "yTrue": [0, 1], "yPred": [0, 1],
                     "threshold": 0.5, "tn": 1, "fp": 0, "fn": 0, "tp": 1,
                     "accuracy": 1, "precision": 1, "recall": 1, "f1": 1, "average_cost": 0,
                     "dummy": {"yPred": [0, 0], "tn": 1, "fp": 0, "fn": 1, "tp": 0,
                               "accuracy": 0.5, "precision": 0, "recall": 0, "f1": 0, "average_cost": 10}},
        }
        with self.assertRaises(AssertionError):
            independently_check_metrics(forged, split, data_path)

    def test_clean_kernel_solution_starter_and_manual_upload(self):
        report = verify(write_report=False)
        self.assertEqual({key: report["checks"][key] for key in ("L0", "L1", "L2", "L3")}, {key: "pass" for key in ("L0", "L1", "L2", "L3")})
        self.assertEqual(set(report["checks"]["faultInjections"].values()), {"rejected"})
        self.assertEqual(report["publicationGate"]["status"], "blocked")
        self.assertEqual(report["publicationGate"]["L5"], "not_run")


if __name__ == "__main__":
    unittest.main()
