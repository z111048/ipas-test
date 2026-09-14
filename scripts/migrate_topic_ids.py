#!/usr/bin/env python3
"""Inventory the topic vocabulary before stable ids exist. Read-only by design.

`data/topics/topics.json` is the single topic SSOT and still keys every reference by
its Chinese display name. LP-210A only has to make the move to stable ids *decidable*:
what the vocabulary contains, where names are already load-bearing, which candidate id
rules collide, and which consumers would have to change. Assigning the ids themselves
is a one-off curation that needs an independent review, so this command never writes
the vocabulary and never invents a slug.

Usage:
  python3 scripts/migrate_topic_ids.py --dry-run
  python3 scripts/migrate_topic_ids.py --dry-run --report /tmp/topic-id-migration.json

The report is deterministic: no timestamps, no absolute paths, stable ordering. Two
consecutive runs on unchanged sources produce byte-identical output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Iterator

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_topic_vocabulary import normalise, valid_identifier  # noqa: E402  (same rules as the builder)

REPO_ROOT = Path(__file__).resolve().parents[1]
VOCABULARY = "data/topics/topics.json"
LEDGER = "data/topics/topic_id_assignments.json"
ID_PREFIX = "topic-"
ID_HEX = 8  # 181 個概念一次性隨機指派，8 hex 的首次碰撞機率約 0；指派時仍逐一查重
CONTENT_ROOT = "content/learning"
ASCII_ONLY = re.compile(r"[\x20-\x7e]+")

# What makes a file a topic consumer. Matching on the file name rather than the full
# repo path also catches readers that build the path from parts (build_glossary.py does).
# The three annotation names nest as substrings — practice_question_topics.json contains
# question_topics.json contains topics.json — so each one subtracts the narrower count.
# Scanning keeps the inventory self-updating: a new reader shows up without a kept list.
MARKERS = {
    "vocabulary": lambda text: text.count("topics.json") > text.count("question_topics.json"),
    "officialAnnotations": lambda text: text.count("question_topics.json") > text.count("practice_question_topics.json"),
    "practiceAnnotations": lambda text: "practice_question_topics.json" in text,
    "topicHeat": lambda text: "topicHeat.json" in text,
    "conceptGraph": lambda text: "conceptGraph.json" in text,
    "topicRef": lambda text: "topicRef" in text,
    "topicQuota": lambda text: "dimension" in text and '"topic"' in text,
}
# Scanned recursively: a reader in a subdirectory nobody listed is exactly the kind of
# consumer this inventory exists to find. Authored content is reported separately, and
# generated output is a rebuild surface rather than a consumer.
SOURCE_ROOTS = ("scripts", "tests", "schemas", "frontend/src", "notebooks")
SOURCE_SUFFIXES = {".py", ".ts", ".tsx", ".json", ".ipynb"}
EXCLUDED_PARTS = {"node_modules", "__pycache__", "generated", "fixtures", ".venv", ".git"}
# Committed products that embed topic names and therefore need a rebuild, not an edit,
# once ids exist. Listed by path so the reviewer sees the surface without pinning bytes.
GENERATED = ("frontend/src/generated/topicHeat.json", "frontend/src/generated/conceptGraph.json",
             "data/topics/question_topics.json", "data/topics/practice_question_topics.json")


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def pointer(parent: str, key: Any) -> str:
    return parent + "/" + str(key).replace("~", "~0").replace("/", "~1")


def walk(node: Any, path: str = "") -> Iterator[tuple[str, dict[str, Any]]]:
    if isinstance(node, dict):
        yield path, node
        for key, value in node.items():
            yield from walk(value, pointer(path, key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from walk(value, pointer(path, index))


def vocabulary_facts(root: Path) -> dict[str, Any]:
    path = root / VOCABULARY
    raw = path.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    topics = data["topics"]
    names = [topic["name"] for topic in topics]
    return {
        "path": VOCABULARY,
        "hash": "sha256:" + hashlib.sha256(raw).hexdigest(),
        "status": data.get("status"),
        "signedOff": data.get("signedOff"),
        "topicCount": len(topics),
        "parentCount": len({topic.get("parent", "") for topic in topics}),
        "withStableId": sum(1 for topic in topics if "id" in topic),
        "aliasCount": sum(len(topic.get("aliases", [])) for topic in topics),
        "distinctAliasCount": len({normalise(alias) for topic in topics
                                   for alias in topic.get("aliases", [])}),
        "duplicateCanonicalNames": sorted(name for name, count in Counter(names).items() if count > 1),
        "_topics": topics,
    }


def collisions(topics: list[dict[str, Any]]) -> dict[str, Any]:
    """Every way the current display names could break a naive id assignment.

    ``normalise`` is the labelling pipeline's own alias rule (assign_question_topics's
    ``alias_quality`` uses it), so the two reports stay comparable.
    """
    owners: dict[str, list[str]] = {}
    folded: dict[str, list[str]] = {}
    for topic in topics:
        for alias in topic.get("aliases", []):
            owners.setdefault(normalise(alias), []).append(topic["name"])
            # A slug rule lowercases, so case-only differences collide there even
            # though the labelling pipeline's own rule keeps them apart.
            folded.setdefault(normalise(alias).casefold(), []).append(topic["name"])
    canonical = {normalise(topic["name"]): topic["name"] for topic in topics}
    normalised_names: dict[str, list[str]] = {}
    for topic in topics:
        normalised_names.setdefault(normalise(topic["name"]), []).append(topic["name"])
    identities: dict[str, list[str]] = {}
    folded_identities: dict[str, list[str]] = {}
    invalid = []
    for topic in topics:
        if "id" not in topic:
            continue
        identity = topic["id"]
        if not valid_identifier(identity):
            invalid.append({"name": topic["name"], "id": identity})
            continue
        identities.setdefault(identity, []).append(topic["name"])
        folded_identities.setdefault(identity.casefold(), []).append(topic["name"])
    return {
        "aliasOwnedByMultipleTopics": sorted(
            ({"alias": alias, "topics": sorted(set(names))}
             for alias, names in owners.items() if len(set(names)) > 1),
            key=lambda row: row["alias"]),
        "aliasCaseFoldedOwnedByMultipleTopics": sorted(
            ({"alias": alias, "topics": sorted(set(names))}
             for alias, names in folded.items() if len(set(names)) > 1),
            key=lambda row: row["alias"]),
        "canonicalNameUsedAsAnotherTopicAlias": sorted(
            ({"name": canonical[alias], "aliasOf": sorted(set(names) - {canonical[alias]})}
             for alias, names in owners.items()
             if alias in canonical and set(names) - {canonical[alias]}),
            key=lambda row: row["name"]),
        # The labelling pipeline looks topics up by normalise(name), so two names that
        # only differ before normalisation would silently become one lookup key.
        "duplicateNormalisedCanonicalNames": sorted(
            ({"normalised": key, "topics": sorted(names)}
             for key, names in normalised_names.items() if len(names) > 1),
            key=lambda row: row["normalised"]),
        "duplicateStableIds": sorted(
            ({"id": identity, "topics": sorted(names)}
             for identity, names in identities.items() if len(names) > 1),
            key=lambda row: row["id"]),
        "caseFoldedDuplicateStableIds": sorted(
            ({"id": key, "topics": sorted(names)}
             for key, names in folded_identities.items() if len(set(names)) > 1),
            key=lambda row: row["id"]),
        "invalidStableIds": sorted(invalid, key=lambda row: row["name"]),
    }


def ascii_alias_slug(topic: dict[str, Any]) -> str | None:
    candidates = sorted(alias for alias in topic.get("aliases", []) if ASCII_ONLY.fullmatch(alias or ""))
    if not candidates:
        return None
    return re.sub(r"[^a-z0-9]+", "-", candidates[0].lower()).strip("-") or None


def candidate_schemes(topics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Measured properties of each rule. Nothing here is an approved assignment."""
    ascii_slugs: dict[str, list[str]] = {}
    for topic in topics:
        slug = ascii_alias_slug(topic)
        if slug:
            ascii_slugs.setdefault(slug, []).append(topic["name"])
    digests: dict[str, list[str]] = {}
    for topic in topics:
        digest = hashlib.sha256(unicodedata.normalize("NFC", topic["name"]).encode("utf-8")).hexdigest()[:12]
        digests.setdefault(digest, []).append(topic["name"])
    curated: dict[str, list[str]] = {}
    for topic in topics:
        if valid_identifier(topic.get("id")):
            curated.setdefault(topic["id"].casefold(), []).append(topic["name"])
    ordinals = {f"{topic.get('parent', '')}-{index}": [topic["name"]]
                for index, topic in enumerate(sorted(topics, key=lambda item: (item.get("parent", ""), item["name"])))}
    return [
        {"scheme": "curated-slug", "covered": sum(len(names) for names in curated.values()),
         "collisions": sum(1 for names in curated.values() if len(names) > 1), "approved": False,
         "deterministicOffline": False, "survivesRename": True, "contractCompliant": True,
         "note": "一次策展的英文 slug（如 topic-data-leakage）；本包不產生，需獨立審查後由維護者指派"},
        {"scheme": "ascii-alias-slug", "covered": sum(len(names) for names in ascii_slugs.values()),
         "collisions": sum(1 for names in ascii_slugs.values() if len(names) > 1), "approved": False,
         "deterministicOffline": True, "survivesRename": False, "contractCompliant": False,
         "note": "取排序後第一個純 ASCII 別名；別名是自由文字且會隨 merge 改變，不能當永久主鍵"},
        {"scheme": "name-digest", "covered": len(topics),
         "collisions": sum(1 for names in digests.values() if len(names) > 1), "approved": False,
         "deterministicOffline": True, "survivesRename": False, "contractCompliant": False,
         "note": "sha256(NFC name)[:12]；data-contracts §3 明文禁止每次由當前名稱重算 id"},
        {"scheme": "parent-ordinal", "covered": len(topics),
         "collisions": sum(1 for names in ordinals.values() if len(names) > 1), "approved": False,
         "deterministicOffline": True, "survivesRename": False, "contractCompliant": False,
         "note": "依 (parent, name) 排序編號；data-contracts §3 明文禁止"},
    ]


TOPIC_REF_POINTER = re.compile(r"(?:/topicRefs/\d+|/measures/\d+/topic)$")


def is_topic_ref(node: Any, location: str) -> bool:
    """A TopicRef is identified by where it sits, not by guessing from its keys.

    ``{id, name}`` is far too generic a shape to match on; the pointer is not.
    A question mapping's ``target.ref`` can be either a topic or a guide anchor, and
    only the guide one carries ``anchorId`` — matching both would crash on a legal
    guide mapping.
    """
    if not isinstance(node, dict):
        return False
    if TOPIC_REF_POINTER.search(location):
        return True
    return location.endswith("/target/ref") and "anchorId" not in node


def authored_references(root: Path, names: set[str], aliases: dict[str, list[str]],
                        by_id: dict[str, str], unreadable: list[str]) -> list[dict[str, Any]]:
    """Every place authored source pins a topic, and how well that pin resolves."""
    rows = []
    content = root / CONTENT_ROOT
    for path in sorted(content.rglob("*.json")) if content.is_dir() else []:
        relative = path.relative_to(root).as_posix()
        try:
            document = load(path)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            # An unreadable authored file hides refs, so say so and block rather than skip.
            unreadable.append(relative)
            continue
        for location, node in walk(document):
            if is_topic_ref(node, location):
                # ``"id": null`` is a present-but-illegal id, not an absent field:
                # the resolver treats it as present too, so the inventory must agree.
                identity = node["id"] if "id" in node else None
                if "id" not in node:
                    id_state = "absent"
                elif not valid_identifier(identity) or identity not in by_id:
                    id_state = "unknown"
                elif by_id[identity] != node.get("name"):
                    id_state = "name_mismatch"
                else:
                    id_state = "resolved"
                kind, key, extra = "topicRef", node.get("name"), {
                    "hasStableId": "id" in node, "stableIdState": id_state,
                }
            elif node.get("dimension") == "topic" and "key" in node:
                kind, key, extra = "quotaKey", node["key"], {}
            else:
                continue
            if not isinstance(key, str):
                resolution = "unknown"
            elif key in names:
                resolution = "canonical"
            else:
                resolution = "alias" if normalise(key) in aliases else "unknown"
            rows.append({"path": relative, "pointer": location or "/", "kind": kind, "name": key,
                         "resolution": resolution, **extra})
    return sorted(rows, key=lambda row: (row["path"], row["pointer"]))


def consumers(root: Path) -> list[dict[str, Any]]:
    """Files that read topics by name, found by literal marker rather than a kept list."""
    rows = []
    for directory in SOURCE_ROOTS:
        base = root / directory
        for path in sorted(base.rglob("*")) if base.is_dir() else []:
            if path.suffix not in SOURCE_SUFFIXES or not path.is_file():
                continue
            if EXCLUDED_PARTS.intersection(path.parts):
                continue
            # This inventory tool names every marker, so counting it as a consumer
            # would inflate the migration surface it is meant to measure.
            if path.resolve() == Path(__file__).resolve():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            markers = sorted(name for name, matches in MARKERS.items() if matches(text))
            if markers:
                rows.append({"path": path.relative_to(root).as_posix(), "markers": markers})
    return sorted(rows, key=lambda row: row["path"])


def carries_stable_ids(path: Path) -> bool | None:
    """LP-210C 之後的衍生產物要在每個名稱旁帶 id；缺檔回 None，讀不動回 False。

    標註檔看每題的 ``topicIds``／``evidence[].topicId``，熱度與關聯圖看每列的 ``id``。
    這只回答「有沒有帶」，id 是否與詞彙表一致由 tests/test_resource_catalog.py 逐筆驗。
    """
    if not path.is_file():
        return None
    try:
        data = load(path)
    except (OSError, ValueError):
        return False
    if isinstance(data, dict) and isinstance(data.get("assignments"), dict):
        return all(isinstance(entry.get("topicIds"), list) and len(entry["topicIds"]) == len(entry.get("topics", []))
                   and all(isinstance(evidence.get("topicId"), str) for evidence in entry.get("evidence", []))
                   for entry in data["assignments"].values())
    rows = data.get("topics") if isinstance(data, dict) and "topics" in data else data.get("concepts") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return False
    return all(isinstance(row.get("id"), str) and row["id"] for row in rows)


def build_report(root: Path) -> dict[str, Any]:
    facts = vocabulary_facts(root)
    topics = facts.pop("_topics")
    names = {topic["name"] for topic in topics}
    aliases: dict[str, list[str]] = {}
    for topic in topics:
        for alias in topic.get("aliases", []):
            aliases.setdefault(normalise(alias), []).append(topic["name"])
    found = collisions(topics)
    unreadable: list[str] = []
    by_id = {topic["id"]: topic["name"] for topic in topics if valid_identifier(topic.get("id"))}
    references = authored_references(root, names, aliases, by_id, unreadable)
    blocking = (facts["duplicateCanonicalNames"] or found["duplicateStableIds"]
                or found["caseFoldedDuplicateStableIds"] or found["invalidStableIds"]
                or found["duplicateNormalisedCanonicalNames"] or unreadable
                or [row for row in references
                    if row["resolution"] != "canonical"
                    or row.get("stableIdState") in {"absent", "unknown", "name_mismatch"}])
    return {
        "schemaVersion": 1,
        "mode": "dry-run",
        "writesVocabulary": False,
        "decision": "pending_independent_review",
        "vocabulary": facts,
        "collisions": found,
        "candidateIdSchemes": candidate_schemes(topics),
        "topics": [{"name": topic["name"], "parent": topic.get("parent", ""),
                    "id": topic.get("id"), "aliasCount": len(topic.get("aliases", [])),
                    "asciiAliasSlug": ascii_alias_slug(topic),
                    "authoredRefCount": sum(1 for row in references if row["name"] == topic["name"])}
                   for topic in sorted(topics, key=lambda item: (item.get("parent", ""), item["name"]))],
        "authoredReferences": references,
        "authoredReferenceSummary": {
            "total": len(references),
            "withStableId": sum(1 for row in references if row.get("hasStableId")),
            "unresolvedStableIds": sum(1 for row in references
                                       if row.get("stableIdState") in {"unknown", "name_mismatch"}),
            "byKind": {kind: sum(1 for row in references if row["kind"] == kind)
                       for kind in ("topicRef", "quotaKey")},
            "nonCanonical": sum(1 for row in references if row["resolution"] != "canonical"),
            "unreadableFiles": sorted(unreadable),
        },
        "consumers": consumers(root),
        "generatedRebuildSurface": [{"path": path, "exists": (root / path).is_file(),
                                     "carriesStableIds": carries_stable_ids(root / path)}
                                    for path in GENERATED],
        "blocking": bool(blocking),
    }


def assign_ids(root: Path, seed: int | None = None) -> dict[str, Any]:
    """替還沒有 id 的概念補上一次性隨機代號，寫進帳本。既有指派永不改動。

    代號刻意不帶語意也刻意不可重算：`data-contracts.md` §3 同時禁止依排序編號與
    由當前名稱重算，所以帳本本身就是唯一權威。``seed`` 只給測試用，不代表代號可以
    從名稱推導出來。
    """
    ledger_path = root / LEDGER
    ledger = (json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.is_file()
              else {"schemaVersion": 1, "idFormat": f"{ID_PREFIX}<{ID_HEX} hex>",
                    "assignedAt": __import__("datetime").date.today().isoformat(),
                    "note": "一次性隨機指派；不得重算、不得重用。改名要補 previousNames，"
                            "合併或刪除要標 retiredAt，否則重建會擋下來。",
                    "assignments": []})
    entries = ledger["assignments"]
    known = {name: entry for entry in entries
             for name in [entry["canonicalName"], *entry.get("previousNames", [])]}
    taken = {entry["id"].casefold() for entry in entries}
    rng = __import__("random").Random(seed) if seed is not None else None

    def mint() -> str:
        while True:
            raw = (f"{rng.getrandbits(ID_HEX * 4):0{ID_HEX}x}" if rng is not None
                   else secrets.token_hex(ID_HEX // 2))
            identity = ID_PREFIX + raw
            if identity.casefold() not in taken and valid_identifier(identity):
                taken.add(identity.casefold())
                return identity

    added, adopted = [], []
    for topic in json.loads((root / VOCABULARY).read_text(encoding="utf-8"))["topics"]:
        entry = known.get(topic["name"])
        if entry is not None:
            # 帳本與詞彙表對同一個概念記了不同的 id：這是資料不一致，不是「已經指派過」。
            if valid_identifier(topic.get("id")) and topic["id"] != entry["id"]:
                raise SystemExit(
                    f'FAIL 概念「{topic["name"]}」在詞彙表是「{topic["id"]}」，帳本卻是「{entry["id"]}」。'
                    'id 一經指派不得改動；請先人工確認哪一個才是正確的指派。')
            continue
        if valid_identifier(topic.get("id")):
            # 詞彙表已經有 id，帳本卻漏了：收編既有代號，絕不重新指派——重新指派會讓
            # 每一筆引用它的 ref 變成孤兒，而重建的錯誤訊息正好會叫人來跑這個命令。
            if topic["id"].casefold() in taken:
                raise SystemExit(f'FAIL 詞彙表的「{topic["id"]}」與帳本既有代號重複，先人工處理')
            taken.add(topic["id"].casefold())
            entry = {"id": topic["id"], "canonicalName": topic["name"], "previousNames": [], "slug": None}
            adopted.append(entry)
        else:
            entry = {"id": mint(), "canonicalName": topic["name"], "previousNames": [], "slug": None}
            added.append(entry)
        entries.append(entry)
    entries.sort(key=lambda entry: entry["canonicalName"])
    ledger["assignments"] = entries
    return {"ledger": ledger, "path": ledger_path, "added": added, "adopted": adopted}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--dry-run", action="store_true", help="唯讀盤點，不寫任何檔案")
    parser.add_argument("--assign", action="store_true",
                        help=f"替還沒有 id 的概念補上代號，只寫 {LEDGER}；既有指派不動")
    parser.add_argument("--seed", type=int, help="只給測試用的亂數種子；代號不可由名稱推導")
    parser.add_argument("--report", type=Path, help="把 JSON 報告寫到這個路徑（預設印到 stdout）")
    args = parser.parse_args()
    if args.dry_run == args.assign:
        parser.error("請擇一：--dry-run（唯讀盤點）或 --assign（只寫指派帳本）")

    root = args.repo_root.resolve()
    if args.assign:
        if not (root / VOCABULARY).is_file():
            print(f"FAIL 找不到詞彙表：{VOCABULARY}", file=sys.stderr)
            return 1
        result = assign_ids(root, seed=args.seed)
        # 只寫帳本這一個固定路徑，不接受任意 --report 目標。
        result["path"].parent.mkdir(parents=True, exist_ok=True)
        result["path"].write_text(
            json.dumps(result["ledger"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        total = len(result["ledger"]["assignments"])
        print(f'指派 {len(result["added"])} 個新代號、收編 {len(result["adopted"])} 個詞彙表既有代號，'
              f'帳本共 {total} 筆 → {LEDGER}', file=sys.stderr)
        print("下一步：重建詞彙表讓 id 折進 topics.json"
              "（build_topic_vocabulary.py --apply-pairs）", file=sys.stderr)
        return 0

    if args.report is not None:
        # Without this, --report data/topics/topics.json would overwrite the very SSOT
        # this command promises never to touch, and still print that it wrote nothing.
        destination = args.report.resolve()
        for guarded in {REPO_ROOT, root}:
            if destination == guarded or destination.is_relative_to(guarded):
                parser.error(f"--report 不可寫進 repo（{guarded}）；唯讀盤點的報告請寫到 repo 之外")
    if not (root / VOCABULARY).is_file():
        print(f"FAIL 找不到詞彙表：{VOCABULARY}", file=sys.stderr)
        return 1
    report = build_report(root)
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)

    vocabulary, summary = report["vocabulary"], report["authoredReferenceSummary"]
    print(f'概念 {vocabulary["topicCount"]}（已有 stable id {vocabulary["withStableId"]}）'
          f'｜別名 {vocabulary["aliasCount"]}｜authored refs {summary["total"]}'
          f'（帶 id {summary["withStableId"]}、非 canonical {summary["nonCanonical"]}）'
          f'｜consumers {len(report["consumers"])}', file=sys.stderr)
    if report["blocking"]:
        print("FAIL 詞彙表或既有引用先有不一致，必須修好才能談遷移", file=sys.stderr)
        return 1
    print("PASS 唯讀盤點完成；未寫入詞彙表", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
