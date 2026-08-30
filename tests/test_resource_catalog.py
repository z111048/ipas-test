#!/usr/bin/env python3
"""Regression contract for the committed exam/resource catalog."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from collections import Counter
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from resource_catalog import (  # noqa: E402
    exam_entries,
    exam_entry,
    exam_pdf_maps,
    iter_question_paths,
    load_resource_catalog,
    question_path,
    reference_pdf_maps,
    validate_resource_catalog,
)
import build_codex_chapter_mock_prompts as chapter_prompt_builder  # noqa: E402
import build_codex_mock_exam_prompts as exam_prompt_builder  # noqa: E402
import build_codex_question_batch_prompts as batch_prompt_builder  # noqa: E402
import build_topic_vocabulary as topic_vocabulary_builder  # noqa: E402
from extract_pdf_pages_structured import pdf_map  # noqa: E402
from annotate_exam_code_images import annotation_exam_entries  # noqa: E402
from parse_exams_v2 import asset_key_for_exam  # noqa: E402
from verify_data_alignment import check_exam_pdfs  # noqa: E402


EXPECTED_ROUTES = {
    "jr_1141_s1", "jr_1141_s2", "jr_1151_s1", "jr_1151_s2",
    "jr_1152_s1", "jr_1152_s2", "sample",
    "mid_1141_s1", "mid_1141_s2", "mid_1141_s3",
    "mid_1151_s1", "mid_1151_s2", "mid_1151_s3", "midSample",
}


def asset_directory_errors(root: Path) -> list[str]:
    """Validate committed assets, plus local extraction sources when present.

    ``data/*/page_extract`` is intentionally gitignored, so a fresh checkout
    must not require it.  When a maintainer has a local extraction tree, its
    catalog keys are still checked to catch stale legacy/canonical mappings.
    """
    errors: list[str] = []
    for level in ("初級", "中級"):
        source_root = root / "data" / level / "page_extract"
        public_root = root / "frontend/public/pdf-assets" / level
        for exam in exam_entries(level=level):
            if not (exam.get("legacyAssetKey") or exam["key"].startswith("mid_1141_")):
                continue
            asset_key = asset_key_for_exam(exam)
            if source_root.is_dir() and not (source_root / asset_key).is_dir():
                errors.append(f"missing optional local source: {level}/{asset_key}")
            if not (public_root / asset_key).is_dir():
                errors.append(f"missing committed public asset: {level}/{asset_key}")
    return errors


class ResourceCatalogTests(unittest.TestCase):
    def test_signed_off_topic_vocabulary_rebuild_is_exact(self) -> None:
        expected = json.loads(
            (ROOT / "data/topics/topics.json").read_text(encoding="utf-8")
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "topics.json"
            with (
                patch.object(topic_vocabulary_builder, "FINAL_PATH", output),
                redirect_stdout(StringIO()),
            ):
                topic_vocabulary_builder.apply_merge_pairs()
            actual = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(actual, expected)

    def test_every_reference_answer_has_a_signed_off_topic(self) -> None:
        vocabulary = json.loads(
            (ROOT / "data/topics/topics.json").read_text(encoding="utf-8")
        )
        assignments = json.loads(
            (ROOT / "data/topics/question_topics.json").read_text(encoding="utf-8")
        )
        topic_names = [topic["name"] for topic in vocabulary["topics"]]
        self.assertEqual(vocabulary["status"], "signed-off")
        self.assertEqual(len(topic_names), len(set(topic_names)))

        rows = assignments["assignments"]
        self.assertEqual(assignments["questionCount"], 565)
        self.assertEqual(assignments["assignedCount"], len(rows))
        self.assertEqual(assignments["coverage"], 1.0)
        self.assertEqual(assignments["unassigned"], [])
        self.assertEqual(assignments["questionsLeftWithNoTopic"], [])
        self.assertTrue(all(row["topics"] for row in rows.values()))
        self.assertEqual(
            {
                topic
                for row in rows.values()
                for topic in row["topics"]
            } - set(topic_names),
            set(),
        )

    def test_existing_frontend_routes_and_question_counts(self) -> None:
        exams = exam_entries()
        self.assertEqual(len(exams), 14)
        self.assertEqual({exam["routeKey"] for exam in exams}, EXPECTED_ROUTES)

        for exam, path in iter_question_paths(exams):
            self.assertTrue(path.is_file(), path)
            payload = json.loads(path.read_text(encoding="utf-8"))
            total = payload.get("total")
            if not isinstance(total, int):
                total = len(payload.get("questions") or [])
            self.assertEqual(total, exam["expectedQuestions"], exam["routeKey"])

        summary = json.loads(
            (ROOT / "frontend/src/generated/resourceSummary.json").read_text(encoding="utf-8")
        )
        summary_routes = {
            route
            for level in summary["levels"].values()
            for route in level["exams"]
        }
        self.assertEqual(summary_routes, EXPECTED_ROUTES)

    def test_pdf_maps_and_resource_files_are_catalog_derived(self) -> None:
        catalog = load_resource_catalog()
        exam_maps = exam_pdf_maps()
        self.assertEqual(sum(len(entries) for entries in exam_maps.values()), 14)
        self.assertIn("jr_1141_s1", exam_maps["初級"])
        self.assertNotIn("exam1", exam_maps["初級"])
        for level, entries in exam_maps.items():
            for filename in entries.values():
                self.assertTrue((ROOT / "data" / level / "pdfs" / filename).is_file())

        resource_maps = reference_pdf_maps()
        self.assertEqual(sum(len(entries) for entries in resource_maps.values()), 3)
        self.assertEqual(
            resource_maps["初級"]["errata"],
            "AI應用規劃師(初級)學習指引勘誤表11404_20251222101819.pdf",
        )
        for level, entries in resource_maps.items():
            for filename in entries.values():
                self.assertTrue((ROOT / "data" / level / "pdfs" / filename).is_file())
        self.assertEqual(catalog["schemaVersion"], 1)

    def test_pdf_resources_have_complete_committed_galleries(self) -> None:
        expected = {
            "junior_errata": (("初級", "errata"), {"page": 3, "table": 5}),
            "middle_errata": (("中級", "errata"), {"page": 7, "table": 7}),
            "briefing": (("共用", "briefing"), {"page": 28, "table": 42, "image": 3}),
        }
        catalog_resources = {
            resource["key"]: resource
            for resource in load_resource_catalog()["resources"]
            if resource.get("kind") == "pdf"
        }
        self.assertEqual(set(catalog_resources), set(expected))

        gallery = json.loads(
            (ROOT / "frontend/src/generated/pdfGallery.json").read_text(encoding="utf-8")
        )
        self.assertEqual(gallery["total"], len(gallery["items"]))
        items_by_source: dict[tuple[str, str], list[dict]] = {}
        for item in gallery["items"]:
            items_by_source.setdefault((item["level"], item["key"]), []).append(item)

        public_root = (ROOT / "frontend/public").resolve()
        for resource_key, (source, expected_types) in expected.items():
            resource = catalog_resources[resource_key]
            self.assertEqual(
                (resource.get("sourceLevel"), resource.get("sourceKey")),
                source,
            )
            items = items_by_source.get(source)
            self.assertIsNotNone(items, f"catalog resource has no gallery: {resource_key}")
            assert items is not None
            self.assertEqual(Counter(item["type"] for item in items), expected_types)
            self.assertEqual(len({item["id"] for item in items}), len(items))
            self.assertEqual(len({item["path"] for item in items}), len(items))
            for item in items:
                self.assertEqual(item["pdf"], resource["pdf"])
                asset = (public_root / item["path"].lstrip("/")).resolve()
                self.assertTrue(asset.is_relative_to(public_root), item["path"])
                self.assertTrue(asset.is_file(), asset)
                self.assertGreater(asset.stat().st_size, 0, asset)

    def test_every_key_route_and_alias_resolves_without_ambiguity(self) -> None:
        for exam in exam_entries():
            level = next(
                item["dataLevel"]
                for item in load_resource_catalog()["levels"]
                if item["id"] == exam["levelId"]
            )
            for token in {exam["key"], exam["routeKey"], *(exam.get("aliases") or [])}:
                self.assertIs(exam_entry(level, token), exam)

        bad = copy.deepcopy(load_resource_catalog())
        bad["exams"][0]["aliases"] = [bad["exams"][1]["key"]]
        with self.assertRaisesRegex(ValueError, "Ambiguous catalog identifier"):
            validate_resource_catalog(bad)

    def test_empty_path_iteration_stays_empty(self) -> None:
        self.assertEqual(list(iter_question_paths([])), [])

    def test_image_annotation_scope_is_catalog_derived(self) -> None:
        selected = annotation_exam_entries()
        self.assertEqual(len(selected), 8)
        self.assertTrue(all(
            exam['levelId'] == 'middle' or exam['kind'] == 'sample'
            for exam in selected
        ))
        self.assertEqual(
            {exam['routeKey'] for exam in selected if exam['levelId'] == 'middle'},
            {exam['routeKey'] for exam in exam_entries(level='中級')},
        )

    def test_codex_prompt_builders_resolve_exam_aliases_through_catalog(self) -> None:
        sample_relative = question_path('中級', 'sample').relative_to(ROOT).as_posix()
        for subject_no in (1, 2, 3):
            subject_id = f'mid-s{subject_no}'
            subject = {'id': subject_id, 'subject': subject_id}
            chapter = {'id': f'{subject_id}c1', 'title': 'chapter'}
            official = question_path('中級', f'mock_exam{subject_no}')
            official_relative = official.relative_to(ROOT).as_posix()
            self.assertTrue(official.is_file())

            prompts = (
                exam_prompt_builder.build_prompt(subject, [], ROOT / 'out.json'),
                chapter_prompt_builder.build_prompt(subject, chapter, 1, ROOT / 'out.json'),
                batch_prompt_builder.build_prompt(
                    subject, chapter, 1, 1, ROOT / 'out.json', [],
                ),
            )
            for prompt in prompts:
                self.assertIn(official_relative, prompt)
                self.assertIn(sample_relative, prompt)
                self.assertNotIn(
                    f'data/中級/questions/mock_exam{subject_no}.json', prompt,
                )

    def test_legacy_asset_keys_are_used_only_for_page_assets(self) -> None:
        self.assertEqual(asset_key_for_exam(exam_entry("初級", "jr_1141_s1")), "exam1")
        self.assertEqual(asset_key_for_exam(exam_entry("初級", "jr_1141_s2")), "exam2")
        self.assertEqual(
            asset_key_for_exam(exam_entry("中級", "mid_1141_s1")),
            "mid_1141_s1",
        )

        for level in ("初級", "中級"):
            extracted_assets = pdf_map(level)
            for exam in exam_entries(level=level):
                asset_key = asset_key_for_exam(exam)
                self.assertEqual(extracted_assets[asset_key], exam["pdf"])
        self.assertEqual(asset_directory_errors(ROOT), [])

    def test_fresh_checkout_does_not_require_gitignored_page_extract(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            checkout = Path(temp)
            for level in ("初級", "中級"):
                for exam in exam_entries(level=level):
                    if not (
                        exam.get("legacyAssetKey")
                        or exam["key"].startswith("mid_1141_")
                    ):
                        continue
                    asset_key = asset_key_for_exam(exam)
                    (
                        checkout / "frontend/public/pdf-assets" / level / asset_key
                    ).mkdir(parents=True, exist_ok=True)

            self.assertEqual(asset_directory_errors(checkout), [])

    def test_alignment_verifier_reads_catalog_without_source_ast(self) -> None:
        for level in ("初級", "中級"):
            errors: list[str] = []
            manifest = json.loads(
                (ROOT / "data" / level / "toc_manifest.json").read_text(encoding="utf-8")
            )
            check_exam_pdfs(level, manifest, errors)
            self.assertEqual(errors, [], f"{level}: {errors}")

            broken_manifest = copy.deepcopy(manifest)
            broken_manifest["subjects"] = broken_manifest["subjects"][:-1]
            broken_errors: list[str] = []
            check_exam_pdfs(level, broken_manifest, broken_errors)
            self.assertTrue(
                any("subjectId" in error for error in broken_errors),
                broken_errors,
            )
            self.assertTrue(
                any("guideKeys" in error for error in broken_errors),
                broken_errors,
            )


if __name__ == "__main__":
    unittest.main()
