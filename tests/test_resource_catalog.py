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
import assign_question_topics as topic_assigner  # noqa: E402
import export_concept_graph as concept_graph_exporter  # noqa: E402
import export_topic_heat as topic_heat_exporter  # noqa: E402
import migrate_topic_ids as topic_id_migration  # noqa: E402
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

    def test_stable_topic_ids_cannot_be_silently_lost_on_rebuild(self) -> None:
        """隨機代號掉了就救不回來，所以重建必須擋，不能安靜地產出零個 id。"""
        ledger = json.loads(
            (ROOT / "data/topics/topic_id_assignments.json").read_text(encoding="utf-8")
        )
        vocabulary = json.loads((ROOT / "data/topics/topics.json").read_text(encoding="utf-8"))
        # 每個 case 綁定它**自己**那道防線的訊息；只斷言「有 SystemExit」的話，
        # 拿掉 identifier 或 casefold 檢查仍會被別的防線擋住而測不出退化。
        cases = {
            "找不到 id 指派帳本": None,
            "沒有 id 指派": lambda data: data["assignments"].pop(0),
            "只差大小寫": lambda data: data["assignments"][1].__setitem__(
                "id", data["assignments"][0]["id"].upper()),
            "不是合法 identifier": lambda data: data["assignments"][0].__setitem__("id", "bad/id"),
            "帳本卻指派": lambda data: data["assignments"][0].__setitem__("id", "topic-00000000"),
        }
        for label, mutate in cases.items():
            with self.subTest(case=label), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "topics.json"
                output.write_text(json.dumps(vocabulary, ensure_ascii=False), encoding="utf-8")
                assignments = Path(directory) / "topic_id_assignments.json"
                if mutate is not None:
                    data = copy.deepcopy(ledger)
                    mutate(data)
                    assignments.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                with (
                    patch.object(topic_vocabulary_builder, "FINAL_PATH", output),
                    patch.object(topic_vocabulary_builder, "ID_ASSIGNMENTS_PATH", assignments),
                    redirect_stdout(StringIO()),
                ):
                    with self.assertRaises(SystemExit) as raised:
                        topic_vocabulary_builder.apply_merge_pairs()
                self.assertIn(label, str(raised.exception))
                # 擋下來的時候不可以已經把舊檔覆寫掉。
                self.assertEqual(json.loads(output.read_text(encoding="utf-8")), vocabulary)

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


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class TopicStableIdArtifactTests(unittest.TestCase):
    """LP-210C：衍生產物在每個概念名稱旁同時帶詞彙表的穩定 id，且仍能精確重建。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.vocabulary = load_json(ROOT / "data/topics/topics.json")
        cls.ids = topic_assigner.topic_ids(cls.vocabulary)
        cls.by_id = {identity: name for name, identity in cls.ids.items()}
        cls.valid = {topic_vocabulary_builder.normalise(name): name for name in cls.ids}
        cls.stable_ids = topic_assigner.stable_ids_of(cls.vocabulary)

    def test_topic_annotations_carry_ids_that_match_the_vocabulary(self) -> None:
        for name in ("question_topics.json", "practice_question_topics.json"):
            with self.subTest(file=name):
                data = load_json(ROOT / "data/topics" / name)
                self.assertEqual(data["stableIds"], self.vocabulary["stableIds"])
                labels = 0
                for key, entry in data["assignments"].items():
                    self.assertEqual(entry["topicIds"], [self.ids[n] for n in entry["topics"]], key)
                    for evidence in entry["evidence"]:
                        self.assertEqual(evidence["topicId"], self.ids[evidence["topic"]], key)
                        # id 緊跟在名稱後面，讀 diff 時一眼看得到兩者是一對
                        self.assertEqual(list(evidence)[:2], ["topic", "topicId"], key)
                    self.assertEqual(entry.get("droppedAsWrongIds", []),
                                     [self.ids[n] for n in entry.get("droppedAsWrong", [])], key)
                    labels += len(entry["evidence"])
                self.assertGreater(labels, 0)
                # 拆掉 id 之後就是回填前的檔案；再套一次也不會變（冪等）
                attached = topic_assigner.attach_topic_ids(data, self.ids, self.by_id, self.stable_ids)
                self.assertEqual(attached, data)
                self.assertEqual(
                    topic_assigner.attach_topic_ids(topic_assigner.strip_topic_ids(data), self.ids,
                                                    self.by_id, self.stable_ids),
                    data)

    def test_attach_topic_ids_fails_closed_on_unknown_names_and_renames_by_id(self) -> None:
        payload = {"vocabulary": "x", "assignments": {"p:q1": {
            "topics": ["生成式AI"], "evidence": [{"topic": "生成式AI", "source": "alias"}]}}}
        attached = topic_assigner.attach_topic_ids(payload, self.ids, self.by_id, self.stable_ids)
        self.assertEqual(list(attached), ["vocabulary", "stableIds", "assignments"])
        self.assertEqual(attached["assignments"]["p:q1"]["topicIds"], [self.ids["生成式AI"]])
        # 不在詞彙表的名稱不能帶著走，也不能寫成 null
        broken = {"assignments": {"p:q1": {"topics": ["不存在的概念"], "evidence": []}}}
        with self.assertRaises(SystemExit) as raised:
            topic_assigner.attach_topic_ids(broken, self.ids, self.by_id, self.stable_ids)
        self.assertIn("不存在的概念", str(raised.exception))
        # 概念改名後，帶 id 的舊標註重跑回填會自動換成新名稱——這才是 id 存在的理由
        identity = self.ids["生成式AI"]
        renamed_vocab = {**self.ids}
        del renamed_vocab["生成式AI"]
        renamed_vocab["生成式人工智慧"] = identity
        renamed_by_id = {**self.by_id, identity: "生成式人工智慧"}
        stale = {"assignments": {"p:q1": {
            "topics": ["生成式AI"], "topicIds": [identity],
            "evidence": [{"topic": "生成式AI", "topicId": identity, "verdict": "正確"}],
            "droppedAsWrong": ["生成式AI"], "droppedAsWrongIds": [identity]}}}
        fixed = topic_assigner.attach_topic_ids(stale, renamed_vocab, renamed_by_id, self.stable_ids)
        row = fixed["assignments"]["p:q1"]
        self.assertEqual(row["topics"], ["生成式人工智慧"])
        self.assertEqual(row["evidence"][0]["topic"], "生成式人工智慧")
        self.assertEqual(row["droppedAsWrong"], ["生成式人工智慧"])
        self.assertEqual(row["topicIds"], [identity])

    def test_cache_upgrade_is_lossless_and_alignment_prefers_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            assign = Path(directory) / "_assign_cache.json"
            # 舊格式：模型原話（含空白變體與自創名稱）
            legacy_assign = {"glm|p:q1": ["生成式 AI", "自創概念", "評估指標"]}
            assign.write_text(json.dumps(legacy_assign, ensure_ascii=False), encoding="utf-8")
            entries = topic_assigner.load_cache(assign, "assign", self.ids, self.by_id, self.valid)
            self.assertEqual([r["topicId"] for r in entries["glm|p:q1"]],
                             [self.ids["生成式AI"], None, self.ids["評估指標"]])
            upgraded = {"format": topic_assigner.CACHE_FORMAT, "kind": "assign",
                        "stableIds": self.stable_ids, "entries": entries}
            self.assertEqual(topic_assigner.legacy_cache_view("assign", upgraded), legacy_assign)
            topic_assigner.save_cache(assign, "assign", entries, self.stable_ids)
            self.assertEqual(load_json(assign)["format"], topic_assigner.CACHE_FORMAT)
            # 讀回 v2 要得到同一批紀錄；kind 不符要擋
            self.assertEqual(topic_assigner.load_cache(assign, "assign", self.ids, self.by_id, self.valid), entries)
            with self.assertRaises(SystemExit):
                topic_assigner.load_cache(assign, "verify", self.ids, self.by_id, self.valid)

            verify = Path(directory) / "_verify_cache.json"
            legacy_verify = {"p:q1": {"生成式 AI": "正確", "評估指標": "過廣"}}
            verify.write_text(json.dumps(legacy_verify, ensure_ascii=False), encoding="utf-8")
            entries = topic_assigner.load_cache(verify, "verify", self.ids, self.by_id, self.valid)
            upgraded = {"format": topic_assigner.CACHE_FORMAT, "kind": "verify",
                        "stableIds": self.stable_ids, "entries": entries}
            self.assertEqual(topic_assigner.legacy_cache_view("verify", upgraded), legacy_verify)
            self.assertEqual(topic_assigner.legacy_cache_view("verify", legacy_verify), legacy_verify)
        # 改名後：這題的標籤現在叫「生成式人工智慧」，快取紀錄還寫舊名但帶著 id → 判定要跟過去
        identity = self.ids["生成式AI"]
        renamed = {**self.ids, "生成式人工智慧": identity}
        aligned = topic_assigner.align_cached(
            ["生成式人工智慧", "評估指標"],
            [{"topic": "生成式AI", "topicId": identity, "verdict": "正確"},
             {"topic": "評估 指標", "topicId": None, "verdict": "過廣"},
             {"topic": "不在這題上的標籤", "topicId": None, "verdict": "正確"}],
            renamed)
        self.assertEqual(aligned, {"生成式人工智慧": "正確", "評估指標": "過廣"})

    def test_topic_heat_rebuild_is_exact_and_carries_ids(self) -> None:
        committed_path = ROOT / "frontend/src/generated/topicHeat.json"
        committed = load_json(committed_path)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "topicHeat.json"
            with patch.object(topic_heat_exporter, "OUT_PATH", output), redirect_stdout(StringIO()):
                topic_heat_exporter.main()
            # 比 bytes，不比 dict：committed 產物要位元可重現，欄位重排也算退化
            self.assertEqual(output.read_bytes(), committed_path.read_bytes())
        self.assertEqual(committed["stableIds"], self.vocabulary["stableIds"])
        for row in committed["topics"]:
            self.assertEqual(row["id"], self.ids[row["name"]])
            self.assertEqual(list(row)[:2], ["id", "name"])
        self.assertEqual(len({row["id"] for row in committed["topics"]}), len(committed["topics"]))

    def test_concept_graph_rebuild_is_exact_keys_by_id_and_carries_previous_names(self) -> None:
        committed_path = ROOT / "frontend/src/generated/conceptGraph.json"
        committed = load_json(committed_path)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "conceptGraph.json"
            with (patch.object(concept_graph_exporter, "OUT_PATH", output),
                  patch.object(sys, "argv", ["export_concept_graph.py"]),
                  redirect_stdout(StringIO())):
                concept_graph_exporter.main()
            self.assertEqual(output.read_bytes(), committed_path.read_bytes())
        self.assertNotIn("generatedAt", committed)   # committed 產物要位元可重現
        self.assertEqual(committed["stableIds"], self.vocabulary["stableIds"])
        ledger = {entry["id"]: entry for entry in
                  load_json(ROOT / "data/topics/topic_id_assignments.json")["assignments"]}
        for concept in committed["concepts"]:
            self.assertEqual(concept["id"], self.ids[concept["name"]])
            self.assertEqual(list(concept)[:3], ["id", "name", "previousNames"])
            self.assertEqual(concept["previousNames"], ledger[concept["id"]]["previousNames"])
            for related in concept["related"]:
                self.assertEqual(related["id"], self.ids[related["name"]])
        self.assertEqual(len({c["id"] for c in committed["concepts"]}), len(committed["concepts"]))

    def test_exports_refuse_a_vocabulary_with_duplicate_or_missing_ids(self) -> None:
        """id 會變成 React key 與 ?c= 的值，兩個概念撞同一個 id 就是撞號；缺 id 是半套遷移。"""
        vocabulary = copy.deepcopy(self.vocabulary)
        vocabulary["topics"][1]["id"] = vocabulary["topics"][0]["id"]
        with tempfile.TemporaryDirectory() as directory:
            broken = Path(directory) / "topics.json"
            broken.write_text(json.dumps(vocabulary, ensure_ascii=False), encoding="utf-8")
            output = Path(directory) / "topicHeat.json"
            with (patch.object(topic_heat_exporter, "TOPICS_PATH", broken),
                  patch.object(topic_heat_exporter, "OUT_PATH", output),
                  redirect_stdout(StringIO())):
                with self.assertRaises(SystemExit) as raised:
                    topic_heat_exporter.main()
            self.assertIn("同時屬於", str(raised.exception))
            self.assertFalse(output.exists())
            with self.assertRaises(SystemExit):
                topic_assigner.topic_ids(vocabulary)
            del vocabulary["topics"][1]["id"]
            broken.write_text(json.dumps(vocabulary, ensure_ascii=False), encoding="utf-8")
            with (patch.object(topic_heat_exporter, "TOPICS_PATH", broken),
                  patch.object(topic_heat_exporter, "OUT_PATH", output),
                  redirect_stdout(StringIO())):
                with self.assertRaises(SystemExit) as raised:
                    topic_heat_exporter.main()
            self.assertIn("沒有穩定 id", str(raised.exception))

    def test_verify_all_refuses_partial_runs_and_stale_names_before_spending(self) -> None:
        """全量驗收只跑一部分會把其他題洗成「未評」；名稱過期要在花 API 錢之前擋下，不能裸 KeyError。"""
        from types import SimpleNamespace
        with self.assertRaises(SystemExit) as raised:
            topic_assigner.verify_all(SimpleNamespace(limit=5), {}, self.ids, self.by_id, self.valid, self.stable_ids)
        self.assertIn("--limit", str(raised.exception))
        stale = load_json(ROOT / "data/topics/question_topics.json")
        key, entry = next(iter(stale["assignments"].items()))
        entry["topics"][0] = "已改名但標註沒回填的概念"
        del entry["topicIds"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "question_topics.json"
            path.write_text(json.dumps(stale, ensure_ascii=False), encoding="utf-8")
            with patch.object(topic_assigner, "OUT_PATH", path), redirect_stdout(StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    topic_assigner.verify_all(SimpleNamespace(limit=0), {key: {}}, self.ids, self.by_id,
                                              self.valid, self.stable_ids)
        self.assertIn("已改名但標註沒回填的概念", str(raised.exception))

    def test_concept_graph_refuses_labels_whose_id_and_name_disagree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            stale = load_json(ROOT / "data/topics/practice_question_topics.json")
            first = next(iter(stale["assignments"].values()))
            first["evidence"][0]["topic"] = "改過名字的概念"
            path = Path(directory) / "practice_question_topics.json"
            path.write_text(json.dumps(stale, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(SystemExit) as raised:
                concept_graph_exporter.correct_labels(path, self.by_id)
            self.assertIn("--backfill-ids", str(raised.exception))
            del first["evidence"][0]["topicId"]
            path.write_text(json.dumps(stale, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(SystemExit):
                concept_graph_exporter.correct_labels(path, self.by_id)

    def test_migration_inventory_reports_that_derived_artifacts_carry_ids(self) -> None:
        for relative in topic_id_migration.GENERATED:
            self.assertIs(topic_id_migration.carries_stable_ids(ROOT / relative), True, relative)
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.json"
            self.assertIsNone(topic_id_migration.carries_stable_ids(missing))
            bare = Path(directory) / "topicHeat.json"
            bare.write_text(json.dumps({"topics": [{"name": "x"}]}), encoding="utf-8")
            self.assertIs(topic_id_migration.carries_stable_ids(bare), False)


if __name__ == "__main__":
    unittest.main()
