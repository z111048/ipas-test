"""Source-bound identity tests; no OCR cache, network, or API credentials required."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import migrate_topic_ids  # noqa: E402
from learning.contracts import blob_hash, content_hash, value_hash  # noqa: E402
from learning.references import ReferenceError, ReferenceResolver, canonical_question_key, graph_errors  # noqa: E402


def write_json(root: Path, relative: str, value) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def fixture_tree(root: Path) -> dict:
    tree = json.loads((ROOT / "tests/fixtures/learning/references/source-tree.json").read_text())
    for path, value in tree.items():
        write_json(root, path, value)
    (root / "data/source.txt").write_text("source bytes\n", encoding="utf-8")
    guide_path = "frontend/src/generated/guideContent/中級-guide3/mid-s3c9.json"
    ref = {"anchorId": "anchor-metrics", "levelId": "middle", "guideKey": "中級-guide3",
           "nodeId": "mid-s3c9", "blockIds": ["block-2"], "sourceHash": blob_hash((root / guide_path).read_bytes()),
           "pageIndexes": [154], "quote": "不平衡資料不能只看準確率。", "anchor": "metrics",
           "precision": "exact", "fallbackRoute": "/guide/mid-s3/mid-s3c9"}
    write_json(root, "content/learning/identity/guide-anchors.json", {"anchors": [
        {"anchorId": ref["anchorId"], "current": ref, "history": [], "status": "resolved", "evidenceIds": ["ev-location"]}]})
    return ref


def question_document(root: Path, level: str, key: str = "Q1") -> dict:
    canonical = canonical_question_key(level, "sample", key)
    resolver = ReferenceResolver(root)
    raw = resolver.legacy_question(canonical)
    document = {"questionKey": canonical, "revision": 1, "contentHash": "sha256:" + "0" * 64,
                "format": "single_choice", "stem": raw["question"],
                "options": [{"optionId": "opt-" + letter, "text": text} for letter, text in raw["options"].items()],
                "correctOptionId": "opt-" + raw["answer"], "explanation": raw["explanation"],
                "answerStatus": "legacy_unverified", "assets": [], "reviewIds": [],
                "sourceHashes": [blob_hash((root / raw["_sourcePath"]).read_bytes())]}
    document["contentHash"] = content_hash("question-revision", document)
    return document


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.guide_ref = fixture_tree(self.root)

    def tearDown(self):
        self.temporary.cleanup()

    def assert_ref_error(self, code, callback):
        with self.assertRaises(ReferenceError) as raised:
            callback()
        self.assertEqual(code, raised.exception.code)

    def test_exact_guide_and_manifest_chapter(self):
        resolver = ReferenceResolver(self.root)
        self.assertEqual(resolver.guide(self.guide_ref)["blocks"][0]["id"], "block-2")
        self.assertEqual(resolver.chapter({"levelId": "middle", "subjectId": "mid-s3", "chapterId": "mid-s3c9"})["title"], "模型訓練、評估與驗證")
        self.assert_ref_error("unknown_chapter", lambda: resolver.chapter({"levelId": "middle", "subjectId": "mid-s3", "chapterId": "mid-s3pdf-c1"}))

    def test_reordered_blocks_do_not_silently_retarget(self):
        path = "frontend/src/generated/guideContent/中級-guide3/mid-s3c9.json"
        data = json.loads((self.root / path).read_text())
        data["blocks"][1]["text"] = "新版同序號的完全不同段落。"
        write_json(self.root, path, data)
        self.assert_ref_error("stale_guide_hash", lambda: ReferenceResolver(self.root).guide(self.guide_ref))
        repaired = {**self.guide_ref, "sourceHash": blob_hash((self.root / path).read_bytes())}
        self.assert_ref_error("stale_anchor_mapping", lambda: ReferenceResolver(self.root).guide(repaired))
        # Even replacing a registry hash cannot hide a quotation mismatch.
        write_json(self.root, "content/learning/identity/guide-anchors.json", {"anchors": [{"anchorId": repaired["anchorId"], "current": repaired, "status": "resolved"}]})
        self.assert_ref_error("guide_quote_mismatch", lambda: ReferenceResolver(self.root).guide(repaired))

    def test_guide_page_anchor_and_registry_ambiguity(self):
        for field, value, code in (("pageIndexes", [155], "guide_page_mismatch"),
                                    ("anchor", "invented-heading", "unknown_dom_anchor"),
                                    ("quote", "不存在的引文", "guide_quote_mismatch")):
            ref = {**self.guide_ref, field: value}
            self.assert_ref_error(code, lambda: ReferenceResolver(self.root).guide(ref, require_registry=False))
        record = {"anchorId": "anchor-metrics", "status": "resolved", "current": self.guide_ref}
        write_json(self.root, "content/learning/identity/guide-anchors.json", {"anchors": [record, record]})
        self.assert_ref_error("ambiguous_reference", lambda: ReferenceResolver(self.root).guide(self.guide_ref))

    def test_topic_id_is_the_key_and_the_name_is_the_check(self):
        """LP-210B：id 是鍵，name 是完整性檢查；不再有整份詞彙表的 hash。"""
        resolver = ReferenceResolver(self.root)
        ref = {"id": "topic-22222222", "name": "資料洩漏"}
        self.assertEqual(resolver.topic(ref)["name"], "資料洩漏")
        # id 不在詞彙表、id 指向另一筆、name 不是 canonical（別名或已改名）：全部 fail closed。
        self.assert_ref_error("unknown_topic_id", lambda: resolver.topic({**ref, "id": "topic-99999999"}))
        self.assert_ref_error("stale_topic_id", lambda: resolver.topic({**ref, "id": "topic-33333333"}))
        self.assert_ref_error("unknown_topic", lambda: resolver.topic({**ref, "name": "data leakage"}))

    def test_adding_a_topic_leaves_existing_refs_alone_but_renaming_breaks_them(self):
        """這一包的重點：新增概念不再讓既有引用失效，改名則一定要被抓到。"""
        path = self.root / "data/topics/topics.json"
        ref = {"id": "topic-22222222", "name": "資料洩漏"}
        data = json.loads(path.read_text(encoding="utf-8"))
        data["topics"].append({"id": "topic-44444444", "name": "全新概念", "aliases": []})
        data["topics"][0]["aliases"].append("另一個別名")
        write_json(self.root, "data/topics/topics.json", data)
        self.assertEqual(ReferenceResolver(self.root).topic(ref)["name"], "資料洩漏")

        data["topics"][1]["name"] = "資料外洩"
        write_json(self.root, "data/topics/topics.json", data)
        self.assert_ref_error("unknown_topic", lambda: ReferenceResolver(self.root).topic(ref))
        # 改名之後作者更新 name，同一個 id 仍然指向同一個概念。
        self.assertEqual(ReferenceResolver(self.root).topic({**ref, "name": "資料外洩"})["id"], "topic-22222222")

    def test_duplicate_or_malformed_vocabulary_ids_block_every_topic(self):
        """半套遷移不能只壞掉受影響的 ref；整份詞彙表要先修好。"""
        path = self.root / "data/topics/topics.json"
        unrelated = "評估指標"
        for identity, code in (("topic-22222222", "ambiguous_reference"),
                               ("資料/洩漏", "invalid_topic_id"),
                               ("", "invalid_topic_id")):
            data = json.loads(path.read_text(encoding="utf-8"))
            data["topics"][2]["id"] = identity
            write_json(self.root, "data/topics/topics.json", data)
            ref = {"id": "topic-11111111", "name": unrelated}
            self.assert_ref_error(code, lambda: ReferenceResolver(self.root).topic(ref))

    def authored_topic_fixture(self, extra=None):
        write_json(self.root, "content/learning/units/unit-fixture.json", {"id": "unit-fixture", "topicRefs": [
            {"id": "topic-22222222", "name": "資料洩漏"},
            {"id": "topic-11111111", "name": "評估指標"},
            *([extra] if extra else [])]})
        write_json(self.root, "content/learning/mock-blueprints/bp-fixture.json",
                   {"id": "bp-fixture", "quotas": [{"id": "quota-0", "dimension": "topic", "key": "交叉驗證"}]})

    def test_migration_inventory_reports_refs_and_never_writes_the_vocabulary(self):
        self.authored_topic_fixture()
        before = (self.root / "data/topics/topics.json").read_bytes()
        report = migrate_topic_ids.build_report(self.root)
        self.assertEqual(before, (self.root / "data/topics/topics.json").read_bytes())
        self.assertEqual((report["writesVocabulary"], report["decision"], report["blocking"]),
                         (False, "pending_independent_review", False))
        self.assertEqual((report["vocabulary"]["topicCount"], report["vocabulary"]["withStableId"]), (3, 3))
        self.assertEqual(report["authoredReferenceSummary"],
                         {"total": 3, "withStableId": 2, "unresolvedStableIds": 0,
                          "byKind": {"topicRef": 2, "quotaKey": 1},
                          "nonCanonical": 0, "unreadableFiles": []})
        # 讀不動的 authored 檔會藏住引用，必須擋下而不是跳過。
        (self.root / "content/learning/units/broken.json").write_text("{not json", encoding="utf-8")
        broken = migrate_topic_ids.build_report(self.root)
        self.assertEqual(broken["authoredReferenceSummary"]["unreadableFiles"],
                         ["content/learning/units/broken.json"])
        self.assertTrue(broken["blocking"])
        self.assertEqual([row["pointer"] for row in report["authoredReferences"] if row["kind"] == "quotaKey"], ["/quotas/0"])
        self.assertEqual({row["name"]: row["authoredRefCount"] for row in report["topics"]},
                         {"資料洩漏": 1, "評估指標": 1, "交叉驗證": 1})
        # 每個 candidate scheme 都只是量測，沒有一個被本包核准；欄位必須真的存在。
        self.assertEqual([scheme["approved"] for scheme in report["candidateIdSchemes"]], [False] * 4)

    def test_migration_inventory_flags_alias_and_id_less_refs(self):
        self.authored_topic_fixture(extra={"id": "topic-22222222", "name": "data leakage"})
        report = migrate_topic_ids.build_report(self.root)
        self.assertEqual(report["authoredReferenceSummary"]["nonCanonical"], 1)
        self.assertEqual([row["resolution"] for row in report["authoredReferences"]
                          if row["name"] == "data leakage"], ["alias"])
        self.assertTrue(report["blocking"])
        # 契約已要求 id 必填，所以沒有 id 的 ref 也要擋下來，不能算成「還沒遷移」。
        self.authored_topic_fixture(extra={"name": "交叉驗證"})
        legacy = migrate_topic_ids.build_report(self.root)
        self.assertEqual([row["stableIdState"] for row in legacy["authoredReferences"]
                          if row["name"] == "交叉驗證" and row["kind"] == "topicRef"], ["absent"])
        self.assertTrue(legacy["blocking"])

    def test_trailing_newline_id_is_rejected_by_resolver_and_inventory_alike(self):
        """jsonschema 的 `$` 會放過尾端換行；resolver 與盤點必須用同一條 anchored 規則。"""
        path = self.root / "data/topics/topics.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["topics"][1]["id"] = "topic-22222222\n"
        write_json(self.root, "data/topics/topics.json", data)
        ref = {"id": "topic-11111111", "name": "評估指標"}
        self.assert_ref_error("invalid_topic_id", lambda: ReferenceResolver(self.root).topic(ref))
        report = migrate_topic_ids.build_report(self.root)
        self.assertEqual([row["id"] for row in report["collisions"]["invalidStableIds"]],
                         ["topic-22222222\n"])
        # identifier 的約束不只 pattern：長度超標時兩邊也必須同時拒絕。
        data["topics"][1]["id"] = "t" * 161
        write_json(self.root, "data/topics/topics.json", data)
        self.assert_ref_error("invalid_topic_id", lambda: ReferenceResolver(self.root).topic(ref))
        self.assertEqual([len(row["id"]) for row in
                          migrate_topic_ids.build_report(self.root)["collisions"]["invalidStableIds"]], [161])

    def test_case_only_twin_ids_are_not_two_ids(self):
        path = self.root / "data/topics/topics.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["topics"][2]["id"] = "Topic-22222222"
        write_json(self.root, "data/topics/topics.json", data)
        ref = {"id": "topic-11111111", "name": "評估指標"}
        self.assert_ref_error("ambiguous_reference", lambda: ReferenceResolver(self.root).topic(ref))
        report = migrate_topic_ids.build_report(self.root)
        self.assertEqual([row["id"] for row in report["collisions"]["caseFoldedDuplicateStableIds"]],
                         ["topic-22222222"])
        self.assertTrue(report["blocking"])
        # curated-slug 的覆蓋與碰撞必須跟著實際 id 走，不能是寫死的 0。
        curated = next(s for s in report["candidateIdSchemes"] if s["scheme"] == "curated-slug")
        self.assertEqual((curated["covered"], curated["collisions"], curated["approved"]), (3, 1, False))

    def test_inventory_blocks_authored_ids_that_do_not_resolve(self):
        vocabulary = blob_hash((self.root / "data/topics/topics.json").read_bytes())
        for identity, state in (("topic-not-in-vocabulary", "unknown"),
                                ("topic-33333333", "name_mismatch"),
                                (None, "unknown")):
            with self.subTest(identity=identity):
                write_json(self.root, "content/learning/units/unit-fixture.json",
                           {"id": "unit-fixture", "topicRefs": [
                               {"id": identity, "name": "資料洩漏"}]})
                report = migrate_topic_ids.build_report(self.root)
                self.assertEqual([row["stableIdState"] for row in report["authoredReferences"]], [state])
                self.assertEqual(report["authoredReferenceSummary"]["unresolvedStableIds"], 1)
                self.assertTrue(report["blocking"])

    def test_inventory_reports_a_canonical_name_borrowed_as_another_topics_alias(self):
        write_json(self.root, "data/topics/topics.json", {"topics": [
            {"name": "A", "aliases": ["A"]}, {"name": "B", "aliases": ["A"]}]})
        found = migrate_topic_ids.build_report(self.root)["collisions"]
        self.assertEqual(found["canonicalNameUsedAsAnotherTopicAlias"], [{"name": "A", "aliasOf": ["B"]}])
        self.assertEqual(found["aliasOwnedByMultipleTopics"], [{"alias": "A", "topics": ["A", "B"]}])

    def test_assign_adopts_an_existing_vocabulary_id_instead_of_minting_a_new_one(self):
        """重建失敗時的錯誤訊息會叫人來跑 --assign；它絕不能把既有代號換掉。"""
        write_json(self.root, "data/topics/topic_id_assignments.json", {
            "schemaVersion": 1, "idFormat": "topic-<8 hex>", "assignedAt": "2026-09-09",
            "note": "fixture", "assignments": [
                {"id": "topic-11111111", "canonicalName": "評估指標", "previousNames": [], "slug": None}]})
        result = migrate_topic_ids.assign_ids(self.root, seed=42)
        by_name = {entry["canonicalName"]: entry["id"] for entry in result["ledger"]["assignments"]}
        # 詞彙表已有的兩個代號要被收編，不是重新指派。
        self.assertEqual((by_name["資料洩漏"], by_name["交叉驗證"]), ("topic-22222222", "topic-33333333"))
        self.assertEqual([entry["canonicalName"] for entry in result["added"]], [])
        self.assertEqual(sorted(entry["canonicalName"] for entry in result["adopted"]), ["交叉驗證", "資料洩漏"])

    def test_assign_refuses_a_ledger_that_disagrees_with_the_vocabulary(self):
        write_json(self.root, "data/topics/topic_id_assignments.json", {
            "schemaVersion": 1, "idFormat": "topic-<8 hex>", "assignedAt": "2026-09-09",
            "note": "fixture", "assignments": [
                {"id": "topic-deadbeef", "canonicalName": "評估指標", "previousNames": [], "slug": None}]})
        with self.assertRaises(SystemExit) as raised:
            migrate_topic_ids.assign_ids(self.root, seed=42)
        self.assertIn("帳本卻是", str(raised.exception))

    def test_inventory_survives_a_guide_mapping_and_sees_analysis_measures(self):
        """question mapping 的 target.ref 可能是 guide；把它當 TopicRef 會直接崩潰。"""
        write_json(self.root, "content/learning/reviews/mapping-guide.json", {
            "id": "map-guide", "target": {"kind": "guide", "ref": {"anchorId": "anchor-metrics"}}})
        write_json(self.root, "content/learning/analysis/analysis-fixture.json", {
            "id": "analysis-fixture", "measures": [{"topic": {"id": "topic-11111111", "name": "評估指標"}}]})
        report = migrate_topic_ids.build_report(self.root)
        pointers = {row["pointer"] for row in report["authoredReferences"]}
        self.assertIn("/measures/0/topic", pointers)
        self.assertNotIn("/target/ref", pointers)

    def test_migration_cli_refuses_apply_mode_and_repeats_byte_identically(self):
        self.authored_topic_fixture()
        with tempfile.TemporaryDirectory() as outside:
            report = Path(outside) / "report.json"
            self.assert_cli_contract(report)

    def assert_cli_contract(self, report: Path):
        script = str(ROOT / "scripts/migrate_topic_ids.py")
        command = [sys.executable, script, "--repo-root", str(self.root), "--report", str(report)]
        refused = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(refused.returncode, 2)
        self.assertFalse(report.exists())
        # 報告不得寫回受審的來源樹，否則 --report 就是一條覆寫 SSOT 的路。
        inside = subprocess.run([sys.executable, script, "--repo-root", str(self.root), "--dry-run",
                                 "--report", str(self.root / "data/topics/topics.json")],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(inside.returncode, 2)
        self.assertIn("不可寫進 repo", inside.stderr)
        first = subprocess.run([*command, "--dry-run"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        payload = report.read_bytes()
        second = subprocess.run([*command, "--dry-run"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(payload, report.read_bytes())
        self.assertEqual(first.stdout, "")

    def test_cross_level_same_legacy_id_keeps_answers_and_pages(self):
        resolver = ReferenceResolver(self.root)
        junior = resolver.legacy_question("q:junior:sample:Q1")
        middle = resolver.legacy_question("q:middle:sample:Q1")
        self.assertEqual((junior["answer"], middle["answer"]), ("A", "D"))
        self.assertEqual((junior["source_ref"]["page_index"], middle["source_ref"]["page_index"]), (0, 1))
        self.assert_ref_error("unknown_question_source", lambda: resolver.legacy_question("q:middle:midSample:Q1"))

    def test_question_revision_binds_actual_production(self):
        document = question_document(self.root, "middle")
        key = ("question-revision", document["questionKey"], 1)
        ref = {"questionKey": document["questionKey"], "revision": 1, "hash": document["contentHash"]}
        resolver = ReferenceResolver(self.root, documents={key: document})
        self.assertEqual(resolver.question(ref)["correctOptionId"], "opt-D")
        reordered = copy.deepcopy(document)
        reordered["options"].reverse()
        reordered["contentHash"] = content_hash("question-revision", reordered)
        resolver = ReferenceResolver(self.root, documents={key: reordered})
        self.assertEqual(resolver.question({**ref, "hash": reordered["contentHash"]})["correctOptionId"], "opt-D")
        path = "data/中級/questions/sample_exam.json"
        changed = json.loads((self.root / path).read_text())
        changed["questions"][0]["answer"] = "A"
        write_json(self.root, path, changed)
        self.assert_ref_error("stale_question_source", lambda: ReferenceResolver(self.root, documents={key: document}).question(ref))

    def test_resource_namespace_hash_and_authorized_path(self):
        resolver = ReferenceResolver(self.root)
        ref = {"namespace": "resource", "key": "reading"}
        snapshot = {"resource": ref, "revision": "1", "kind": "repository", "hashScope": "full_artifact",
                    "artifactPath": "data/source.txt", "hash": blob_hash((self.root / "data/source.txt").read_bytes())}
        self.assertEqual(resolver.snapshot(snapshot)["key"], "reading")
        self.assert_ref_error("unknown_resource", lambda: resolver.resource({**ref, "namespace": "exam", "levelId": "middle"}))
        self.assert_ref_error("resource_path_mismatch", lambda: resolver.snapshot({**snapshot, "artifactPath": "data/resource_catalog.json"}))
        self.assert_ref_error("stale_source_hash", lambda: resolver.snapshot({**snapshot, "hash": "sha256:" + "0" * 64}))

    def test_external_snapshot_expiry(self):
        path = "data/resource_catalog.json"
        catalog = json.loads((self.root / path).read_text())
        catalog["resources"].append({"key": "external", "version": "1", "url": "https://example.invalid/official", "visibleIn": ["middle"]})
        write_json(self.root, path, catalog)
        snap = {"resource": {"namespace": "resource", "key": "external"}, "revision": "1", "kind": "external",
                "hashScope": "reviewed_capture", "retrievedAt": "2026-09-01T00:00:00Z", "reviewDueAt": "2026-10-01T00:00:00Z",
                "capture": {"mode": "authored_summary", "text": "A reviewed summary."}}
        snap["hash"] = value_hash({key: snap[key] for key in ("resource", "revision", "capture")})
        ReferenceResolver(self.root, assessment_at="2026-09-07T00:00:00Z").snapshot(snap)
        self.assert_ref_error("expired_source", lambda: ReferenceResolver(self.root, assessment_at="2026-10-02T00:00:00Z").snapshot(snap))

    def test_alias_is_explicit_and_never_guessed(self):
        alias = {"legacyNamespace": "middle:sample", "legacyId": "exam1_q1", "questionKey": "q:middle:sample:Q1",
                 "decision": "verified", "evidenceIds": ["proof-1"]}
        write_json(self.root, "content/learning/identity/question-aliases.json", {"aliases": [alias]})
        self.assertEqual(ReferenceResolver(self.root).alias("middle:sample", "exam1_q1"), "q:middle:sample:Q1")
        write_json(self.root, "content/learning/identity/question-aliases.json", {"aliases": [alias, alias]})
        self.assert_ref_error("ambiguous_alias", lambda: ReferenceResolver(self.root).alias("middle:sample", "exam1_q1"))

    def test_dependency_cycle_and_unknown_prerequisite(self):
        codes = {code for code, _ in graph_errors({"first": ["second"], "second": ["first", "missing"]})}
        self.assertEqual(codes, {"reference_cycle", "dangling_prerequisite"})


if __name__ == "__main__":
    unittest.main()
