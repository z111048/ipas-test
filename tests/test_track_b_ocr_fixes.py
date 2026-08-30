#!/usr/bin/env python3
"""Regression contract for reviewed Track B semantic corrections."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import apply_track_b_ocr_fixes as track_b_fixes  # noqa: E402
import apply_errata  # noqa: E402
import build_codex_section_prompts  # noqa: E402
import export_guide_sections  # noqa: E402
import generate_questions  # noqa: E402
import ocr_extract  # noqa: E402
import parse_guides  # noqa: E402


class TrackBCorrectionRegistryTest(unittest.TestCase):
    @staticmethod
    def copy_committed_canonical(destination: Path) -> None:
        for (level, _key), review in track_b_fixes.REVIEWED_CANONICAL.items():
            source = ROOT / "data" / level / review["path"]
            target = destination / "data" / level / review["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    def test_inventory_coverage_and_responsibility_are_explicit(self) -> None:
        track_b_fixes.validate_registry()
        semantic_ids = {entry["id"] for entry in track_b_fixes.PATCHES}
        source_math_ids = {
            entry["id"]
            for entry in track_b_fixes.PATCHES
            if entry["classification"] == "source_math_correction"
        }
        provenance_ids = {
            entry["id"] for entry in track_b_fixes.PROVENANCE_CORRECTIONS
        }

        self.assertEqual(len(semantic_ids), 73)
        self.assertEqual(source_math_ids, {"TB-002", "TB-007"})
        self.assertEqual(len(semantic_ids - source_math_ids), 71)
        self.assertEqual(provenance_ids, {f"TB-{number:03d}" for number in range(74, 79)})

    def test_page_type_overrides_are_committed_and_backup_independent(self) -> None:
        expected = {
            ("初級", "guide1", 4): "skip",
            ("初級", "guide1", 69): "skip",
            ("初級", "guide2", 4): "skip",
            ("初級", "guide2", 60): "skip",
            ("中級", "guide3", 0): "content",
        }
        self.assertEqual(ocr_extract.TYPE_OVERRIDES, expected)

        for level, key, page_count in ocr_extract.BOOKS:
            with mock.patch.object(ocr_extract, "load_backup_types", return_value={}):
                without_backup = ocr_extract.convert_book(level, key, page_count, dry_run=True)
            with mock.patch.object(
                ocr_extract,
                "load_backup_types",
                return_value={index: "practice" for index in range(page_count)},
            ):
                with_conflicting_backup = ocr_extract.convert_book(
                    level, key, page_count, dry_run=True,
                )

            self.assertEqual(
                [entry["type"] for entry in without_backup["entries"]],
                [entry["type"] for entry in with_conflicting_backup["entries"]],
                f"{level}/{key}",
            )

        for (level, key, index), expected_type in expected.items():
            page_count = next(
                count for book_level, book_key, count in ocr_extract.BOOKS
                if (book_level, book_key) == (level, key)
            )
            with mock.patch.object(ocr_extract, "load_backup_types", return_value={}):
                result = ocr_extract.convert_book(level, key, page_count, dry_run=True)
            actual = next(entry["type"] for entry in result["entries"] if entry["idx"] == index)
            self.assertEqual(actual, expected_type)

    def test_guide_sections_exactly_rebuild_from_current_canonical(self) -> None:
        summary, errors = export_guide_sections.verify_outputs()
        self.assertEqual(errors, [])
        self.assertEqual(summary["files"], summary["expected_files"])
        self.assertEqual(summary["chapters"], summary["expected_chapters"])
        self.assertGreater(summary["sections"], 0)
        self.assertGreater(summary["chunks"], 0)

        serialized = "".join(
            path.read_text(encoding="utf-8")
            for path in sorted((ROOT / "data").glob("*/guide_sections/subject*.json"))
        )
        self.assertNotIn("X_{man}", serialized)
        self.assertNotIn("𝑿𝒎𝒂𝒏", serialized)
        self.assertNotIn("公式：Recall = 𝑇𝑃+𝐹𝑃", serialized)

    def test_guide_sections_mutation_fails_exact_rebuild_contract(self) -> None:
        path = ROOT / "data/初級/guide_sections/subject1.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["chapters"][0]["chunks"][0]["content"] += "\n未審核舊快照"
        errors = export_guide_sections.payload_errors("初級", 1, payload)
        self.assertTrue(errors)
        self.assertIn("differs from deterministic canonical rebuild", errors[0])

    def test_question_generator_refuses_stale_section_payload(self) -> None:
        chunks = generate_questions.load_section_chunks("初級", 1)
        self.assertTrue(chunks)
        with mock.patch.object(
            generate_questions,
            "guide_section_payload_errors",
            return_value=["forced stale fixture"],
        ):
            with self.assertRaisesRegex(RuntimeError, "Stale or invalid guide_sections"):
                generate_questions.load_section_chunks("初級", 1)

    def test_codex_prompt_builder_refuses_stale_section_payload(self) -> None:
        payload = build_codex_section_prompts.load_section_payload("初級", 1)
        self.assertTrue(payload.get("chapters"))
        with mock.patch.object(
            build_codex_section_prompts,
            "guide_section_payload_errors",
            return_value=["forced stale fixture"],
        ):
            with self.assertRaisesRegex(RuntimeError, "Stale or invalid guide_sections"):
                build_codex_section_prompts.load_section_payload("初級", 1)

    def test_replacement_containing_source_fragment_is_idempotent(self) -> None:
        operation = track_b_fixes.replace("個典型", "一個典型")
        corrected, changed = track_b_fixes._apply_operation(
            "這是個典型的流程。", operation, "TEST",
        )
        self.assertTrue(changed)
        self.assertEqual(corrected, "這是一個典型的流程。")

        second, changed_again = track_b_fixes._apply_operation(
            corrected, operation, "TEST",
        )
        self.assertFalse(changed_again)
        self.assertEqual(second, corrected)

        mixed = "這是一個典型的流程；那是個典型的流程。"
        repaired, mixed_changed = track_b_fixes._apply_operation(
            mixed, operation, "TEST",
        )
        self.assertTrue(mixed_changed)
        self.assertEqual(repaired, "這是一個典型的流程；那是一個典型的流程。")
        track_b_fixes._verify_operation(repaired, operation, "TEST")

    def test_tb006_rebuild_repairs_ambiguous_official_errata_span(self) -> None:
        raw_path = (
            ROOT / "data" / "中級" / "guide_ocr" / "guide3" / "pages"
            / "page_0155" / "page_0155.md"
        )
        markdown, _headings = ocr_extract.normalize_markdown(
            raw_path.read_text(encoding="utf-8"),
        )

        official_entries = json.loads(
            (ROOT / "data" / "中級" / "errata_corrections.json").read_text(
                encoding="utf-8",
            ),
        )
        official = next(
            entry for entry in official_entries
            if entry["key"] == "guide3" and entry["page_label"] == "5-21"
        )
        official_pairs = apply_errata.context_pairs(
            official["original"], official["corrected"],
        )
        markdown, applied, satisfied = apply_errata.apply_pairs(
            markdown, official_pairs,
        )
        self.assertEqual(len(applied), 1)
        self.assertEqual(len(satisfied), 1)
        self.assertEqual(
            markdown.count(r"Precision =  $ \frac{TP}{TP+FN} $"), 1,
        )
        self.assertEqual(
            markdown.count(r"Recall =  $ \frac{TP}{TP+FP} $"), 1,
        )

        manual_entries = json.loads(
            (ROOT / "data" / "中級" / "errata_manual.json").read_text(
                encoding="utf-8",
            ),
        )
        tb006_manual = [
            entry for entry in manual_entries
            if entry.get("correction_id") == "TB-006"
        ]
        self.assertEqual(len(tb006_manual), 2)
        for entry in tb006_manual:
            markdown, applied, satisfied = apply_errata.apply_pairs(
                markdown, [(entry["find"], entry["replace"])],
            )
            self.assertEqual(len(applied), 1, entry["note"])
            self.assertEqual(len(satisfied), 1, entry["note"])

        self.assertEqual(
            markdown.count(r"Precision =  $ \frac{TP}{TP+FP} $"), 1,
        )
        self.assertEqual(
            markdown.count(r"Precision =  $ \frac{TP}{TP+FN} $"), 0,
        )
        self.assertEqual(
            markdown.count(r"Recall =  $ \frac{TP}{TP+FN} $"), 1,
        )
        self.assertEqual(
            markdown.count(r"Recall =  $ \frac{TP}{TP+FP} $"), 0,
        )

        tb006 = next(entry for entry in track_b_fixes.PATCHES if entry["id"] == "TB-006")
        for operation in tb006["operations"]:
            track_b_fixes._verify_operation(markdown, operation, "TB-006")

    def test_insertion_errata_is_idempotent_and_repairs_only_genuine_old_span(self) -> None:
        old = "的組合係數"
        supplement = "\n■ 補充說明：此處為非負矩陣的元素級限制。"
        new = old + supplement
        pair = (old, new)

        once, applied, satisfied = apply_errata.apply_pairs(
            f"前文 {old} 後文", [pair],
        )
        self.assertEqual(applied, [pair])
        self.assertEqual(satisfied, [pair])
        self.assertEqual(once.count(supplement), 1)

        twice, applied_again, satisfied_again = apply_errata.apply_pairs(once, [pair])
        self.assertEqual(applied_again, [])
        self.assertEqual(satisfied_again, [pair])
        self.assertEqual(twice, once)

        mixed = f"{once}\n另一處 {old} 結尾"
        repaired, mixed_applied, mixed_satisfied = apply_errata.apply_pairs(mixed, [pair])
        self.assertEqual(mixed_applied, [pair])
        self.assertEqual(mixed_satisfied, [pair])
        self.assertTrue(repaired.startswith(once))
        self.assertEqual(repaired.count(supplement), 2)
        self.assertEqual(repaired.count(old), 2)

    def test_immutable_nonnegative_matrix_errata_supplement_is_not_duplicated(self) -> None:
        entries = json.loads(
            (ROOT / "data" / "中級" / "errata_corrections.json").read_text(
                encoding="utf-8",
            ),
        )
        official = next(
            entry for entry in entries
            if entry["key"] == "guide3" and entry["page_label"] == "3-15"
        )
        pairs = apply_errata.context_pairs(official["original"], official["corrected"])
        self.assertEqual(len(pairs), 1)
        self.assertIn(apply_errata.normalize(pairs[0][0]), apply_errata.normalize(pairs[0][1]))

        raw_path = (
            ROOT / "data" / "中級" / "guide_ocr" / "guide3" / "pages"
            / "page_0022" / "page_0022.md"
        )
        markdown, _headings = ocr_extract.normalize_markdown(
            raw_path.read_text(encoding="utf-8"),
        )
        once, applied, satisfied = apply_errata.apply_pairs(markdown, pairs)
        self.assertEqual(applied, pairs)
        self.assertEqual(satisfied, pairs)
        self.assertEqual(once.count("■ 補充說明："), 1)

        twice, applied_again, satisfied_again = apply_errata.apply_pairs(once, pairs)
        self.assertEqual(applied_again, [])
        self.assertEqual(satisfied_again, pairs)
        self.assertEqual(twice, once)
        self.assertEqual(twice.count("■ 補充說明："), 1)

    def test_nonnegative_matrix_supplement_occurs_once_in_each_direct_publication(self) -> None:
        prefix = "■ 補充說明：上述公式中所標示的"
        canonical = json.loads(
            (ROOT / "data" / "中級" / "guide" / "subject3_guide.json").read_text(
                encoding="utf-8",
            ),
        )
        chapter = next(
            entry for entry in canonical["chapters"] if entry["id"] == "mid-s3c2"
        )
        self.assertEqual(chapter["content"].count(prefix), 1)

        publication = json.loads(
            (
                ROOT / "frontend" / "src" / "generated" / "guideContent"
                / "中級-guide3" / "mid-s3c2.json"
            ).read_text(encoding="utf-8"),
        )
        self.assertEqual(publication["content"].count(prefix), 1)
        self.assertEqual(
            sum(str(block.get("text") or "").count(prefix) for block in publication["blocks"]),
            1,
        )

    def test_full_cache_canonical_and_provenance_gate(self) -> None:
        report = track_b_fixes.audit_track_b_state(ROOT)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["canonical_files"], 5)
        self.assertEqual(report["ocr_or_extraction_corrections"], 71)
        self.assertEqual(report["source_math_corrections"], 2)
        self.assertEqual(report["provenance_corrections"], 5)
        self.assertEqual(report["verified_inventory_ids"], 78)
        self.assertEqual(report["remaining"], 0)
        self.assertEqual(report["committed_canonical"]["status"], "verified")
        if report["cache"]["available"]:
            self.assertEqual(report["cache"]["changed"], 0)
            self.assertTrue(report["cache"]["extended_rebuild_check"])

    def test_fresh_clone_without_gitignored_cache_passes_committed_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            checkout = Path(temp)
            self.copy_committed_canonical(checkout)

            report = track_b_fixes.audit_track_b_state(checkout)

            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["verified_inventory_ids"], 78)
            self.assertEqual(report["committed_canonical"]["fixed_content_sha256"], 5)
            self.assertEqual(report["cache"]["status"], "not_available")
            self.assertFalse(report["cache"]["available"])
            self.assertFalse(report["cache"]["extended_rebuild_check"])

    def test_partial_local_cache_cannot_downgrade_to_committed_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            checkout = Path(temp)
            self.copy_committed_canonical(checkout)
            (checkout / "data" / "初級" / "pages_cache" / "guide1").mkdir(
                parents=True,
            )

            with self.assertRaisesRegex(ValueError, "Partial local Track B cache"):
                track_b_fixes.audit_track_b_state(checkout)

    def test_complete_cache_contract_rejects_missing_page_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            cache_dir = Path(temp) / "pages_cache" / "guide1"
            cache_dir.mkdir(parents=True)
            (cache_dir / "page_001.json").write_text(
                json.dumps({"idx": 1, "type": "skip"}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, r"missing page indices=\[0\]"):
                track_b_fixes._validate_complete_cache(cache_dir, total_pages=2)

    def test_coordinated_content_and_embedded_hash_tampering_fails_reviewed_sha(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            checkout = Path(temp)
            self.copy_committed_canonical(checkout)
            review = track_b_fixes.REVIEWED_CANONICAL[("初級", "guide1")]
            path = checkout / "data" / "初級" / review["path"]
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["chapters"][0]["content"] += "\n未審核變更"
            payload["source_content_sha256"] = track_b_fixes._chapter_content_sha256(
                payload["chapters"],
            )
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "reviewed committed SHA-256"):
                track_b_fixes.audit_track_b_state(checkout)

    def test_moving_page_level_correction_id_fails_provenance_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            checkout = Path(temp)
            self.copy_committed_canonical(checkout)
            review = track_b_fixes.REVIEWED_CANONICAL[("初級", "guide1")]
            path = checkout / "data" / "初級" / review["path"]
            payload = json.loads(path.read_text(encoding="utf-8"))
            source_pages = [
                page
                for chapter in payload["chapters"]
                for page in chapter["source_pages"]
            ]
            source = next(
                page for page in source_pages
                if "TB-001" in page.get("semantic_correction_ids", [])
            )
            destination = next(
                page for page in source_pages
                if not page.get("semantic_correction_ids")
            )
            source["semantic_correction_ids"].remove("TB-001")
            destination["semantic_correction_ids"] = ["TB-001"]
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "correction provenance"):
                track_b_fixes.audit_track_b_state(checkout)

    @unittest.skipUnless(parse_guides._FITZ_AVAILABLE, "PyMuPDF required")
    def test_one_scan_display_labels_match_legacy_lookup(self) -> None:
        data_dir = ROOT / "data" / "初級"
        guide = parse_guides._load_manifest(data_dir)[1]
        pdf_path = data_dir / "pdfs" / guide["pdf"]
        _boundaries, display_labels = parse_guides._build_page_label_maps(pdf_path)
        for page_index in (6, 32, 54, 70):
            self.assertEqual(
                display_labels.get(page_index, ""),
                parse_guides._page_label(pdf_path, page_index),
            )


if __name__ == "__main__":
    unittest.main()
