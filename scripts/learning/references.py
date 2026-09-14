"""Resolve learning references against repository sources without rewriting them."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import quote, unquote

from .contracts import (
    ValidationIssue, blob_hash, canonical_json_bytes, content_hash, identifier_pattern,
    notebook_content_hash, validate_document, value_hash,
)


ENTITY_KINDS = {"unit": "learning-unit", "path": "learning-path",
                "project": "project", "lab": "lab"}
SOURCE_DIRS = {"learning-unit": "units", "learning-path": "paths",
               "project": "projects", "lab": "labs", "evidence": "evidence",
               "review": "reviews", "mock-blueprint": "mock-blueprints",
               "analysis-policy": "analysis-policies"}


class ReferenceError(ValueError):
    """A missing, ambiguous, unsafe, or changed source reference."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def canonical_question_key(level_id: str, source_key: str, legacy_id: str) -> str:
    if not all(isinstance(part, str) and part for part in (level_id, source_key, legacy_id)):
        raise ReferenceError("invalid_question_key", "Question identity requires three nonempty strings")
    return "q:" + ":".join(quote(part, safe="-_.~") for part in (level_id, source_key, legacy_id))


def parse_question_key(key: str) -> tuple[str, str, str]:
    parts = key.split(":")
    if len(parts) != 4 or parts[0] != "q":
        raise ReferenceError("invalid_question_key", "Use q:<levelId>:<sourceKey>:<escaped legacyId>")
    decoded = tuple(unquote(part) for part in parts[1:])
    if canonical_question_key(*decoded) != key:
        raise ReferenceError("invalid_question_key", "Question key is not canonically escaped")
    return decoded


def question_payload_path(question_key: str, revision: int) -> str:
    parse_question_key(question_key)
    return f"questions/{value_hash(question_key).removeprefix('sha256:')[:24]}/{revision}.json"


def question_payload_bytes(document: Mapping[str, Any]) -> bytes:
    """Release-independent payload bytes avoid a pool/hash/releaseId cycle."""
    return canonical_json_bytes(document) + b"\n"


def pointer(parent: str, key: Any) -> str:
    return parent + "/" + str(key).replace("~", "~0").replace("/", "~1")


def safe_path(root: Path, relative: str) -> Path:
    root = root.resolve()
    path = Path(relative)
    if path.is_absolute() or not relative or ".." in path.parts or "\\" in relative:
        raise ReferenceError("unsafe_path", f"Expected repository relative path: {relative!r}")
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root):
        raise ReferenceError("unsafe_path", f"Path escapes repository: {relative!r}")
    return resolved


def _unique(items: Iterable[Mapping[str, Any]], key: str, label: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in items:
        identity = item.get(key)
        if not isinstance(identity, str) or not identity or identity in result:
            raise ReferenceError("ambiguous_reference", f"Duplicate/missing {label}: {identity!r}")
        result[identity] = item
    return result


def _valid_topic_id(name: str, identity: Any) -> bool:
    """A vocabulary id must be usable as ``TopicRef.id``; reuse that exact rule.

    ``fullmatch`` is the anchored half: the schema's ``pattern`` alone would accept
    ``"topic-a\n"`` and the resolver would then treat it as a different id than the
    inventory does.
    """
    if not isinstance(identity, str) or not identifier_pattern().fullmatch(identity):
        return False
    return not any(issue.path == "/id"
                   for issue in validate_document("topic-ref", {"name": name, "id": identity}))


def _time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ReferenceError("invalid_time", f"Invalid UTC timestamp: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
        raise ReferenceError("invalid_time", "Timestamp must have an explicit UTC offset")
    return parsed


def document_identity(kind: str, document: Mapping[str, Any]) -> tuple[str, str, int]:
    return (kind, str(document.get("id", document.get("questionKey", ""))),
            int(document.get("revision", 1)))


class ReferenceResolver:
    """An injectable, lazy reader. Existing source files remain the only authority.

    ``documents`` supplies the complete candidate's versioned authored objects;
    reading external URLs, rebuilding OCR, and guessing aliases are never allowed.
    """

    def __init__(self, repo_root: Path | str, *,
                 documents: Mapping[tuple[str, str, int], Mapping[str, Any]] | None = None,
                 assessment_at: str | None = None):
        self.root = Path(repo_root).resolve()
        self.documents = dict(documents or {})
        self.assessment_at = _time(assessment_at) if assessment_at else datetime.now(timezone.utc)
        self.input_hashes: dict[str, str] = {}
        self._json_cache: dict[str, Any] = {}
        self._topic_index: tuple[dict[str, Any], dict[str, Any], str] | None = None

    def read_bytes(self, relative: str) -> bytes:
        path = safe_path(self.root, relative)
        try:
            result = path.read_bytes()
        except OSError as exc:
            raise ReferenceError("missing_artifact", f"Cannot read {relative}: {exc.strerror}") from exc
        self.input_hashes[relative] = blob_hash(result)
        return result

    def read_json(self, relative: str) -> Any:
        if relative not in self._json_cache:
            try:
                self._json_cache[relative] = json.loads(self.read_bytes(relative))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise ReferenceError("invalid_source_json", f"Invalid JSON: {relative}") from exc
        return self._json_cache[relative]

    def catalog(self) -> Mapping[str, Any]:
        catalog = self.read_json("data/resource_catalog.json")
        _unique(catalog["levels"], "id", "catalog level")
        # Resource keys are namespaced. Level-less shared resources stay level-less.
        seen = set()
        for namespace, field in (("exam", "exams"), ("resource", "resources")):
            for item in catalog[field]:
                key = (namespace, item.get("levelId"), item["key"])
                if key in seen:
                    raise ReferenceError("ambiguous_reference", f"Duplicate catalog identity: {key}")
                seen.add(key)
        return catalog

    def level(self, level_id: str) -> Mapping[str, Any]:
        levels = _unique(self.catalog()["levels"], "id", "catalog level")
        if level_id not in levels:
            raise ReferenceError("unknown_level", f"Unknown level: {level_id}")
        return levels[level_id]

    def chapter(self, ref: Mapping[str, Any]) -> Mapping[str, Any]:
        level = self.level(ref["levelId"])
        manifest = self.read_json(f"data/{level['dataLevel']}/toc_manifest.json")
        subjects = _unique(manifest["subjects"], "id", "subject")
        subject = subjects.get(ref["subjectId"])
        if subject is None:
            raise ReferenceError("unknown_subject", f"Unknown manifest subject: {ref['subjectId']}")
        chapters = _unique(subject["chapters"], "id", "chapter")
        chapter = chapters.get(ref["chapterId"])
        if chapter is None:
            raise ReferenceError("unknown_chapter", f"Unknown manifest chapter: {ref['chapterId']}")
        return chapter

    def topic_vocabulary(self) -> tuple[dict[str, Any], dict[str, Any]]:
        """Index the one topic SSOT by canonical name and by immutable stable id.

        ``id`` is the key; ``name`` is the human-readable half of every ref and is
        cross-checked against it. Both indexes fail closed on duplicates, so a
        half-migrated vocabulary resolves nothing rather than an arbitrary entry.
        """
        if self._topic_index is not None:
            return self._topic_index
        data = self.read_json("data/topics/topics.json")
        by_name = _unique(data["topics"], "name", "canonical topic name")
        by_id: dict[str, Any] = {}
        folded: set[str] = set()
        for topic in data["topics"]:
            if "id" not in topic:
                continue
            identity = topic["id"]
            if not _valid_topic_id(topic["name"], identity):
                raise ReferenceError("invalid_topic_id", f"Topic id is not a contract identifier: {identity!r}")
            if identity in by_id or identity.casefold() in folded:
                # Case-only twins collide in URLs and on case-insensitive filesystems.
                raise ReferenceError("ambiguous_reference", f"Duplicate topic id: {identity!r}")
            by_id[identity] = topic
            folded.add(identity.casefold())
        # Reading the vocabulary is already cached; index it once too, so a migrated
        # vocabulary does not revalidate 181 ids for every single ref.
        self._topic_index = (by_name, by_id)
        return self._topic_index

    def topic(self, ref: Mapping[str, Any]) -> Mapping[str, Any]:
        """Resolve by immutable id; the display name is the integrity check.

        There is deliberately no vocabulary hash here. Adding or editing an unrelated
        topic must not invalidate refs, and a rename cannot slip through unnoticed
        because the name below stops matching and the author has to re-review.
        """
        by_name, by_id = self.topic_vocabulary()
        topic = by_id.get(ref["id"])
        if topic is None:
            raise ReferenceError("unknown_topic_id", "Topic id is absent from this vocabulary")
        if ref["name"] not in by_name:
            raise ReferenceError("unknown_topic", "Topic name is not canonical any more; it was renamed, merged, or is an alias")
        if by_name[ref["name"]] is not topic:
            raise ReferenceError("stale_topic_id", "Topic name/id pair does not match the vocabulary")
        return topic

    def resource(self, ref: Mapping[str, Any]) -> Mapping[str, Any]:
        if ref["namespace"] not in {"exam", "resource"}:
            raise ReferenceError("unknown_namespace", "Unknown resource namespace")
        if "levelId" in ref:
            self.level(ref["levelId"])
        field = "exams" if ref["namespace"] == "exam" else "resources"
        found = [item for item in self.catalog()[field]
                 if item["key"] == ref["key"] and item.get("levelId") == ref.get("levelId")]
        if len(found) != 1:
            raise ReferenceError("unknown_resource" if not found else "ambiguous_reference",
                                 f"Resource requires an exact namespace/level/key: {dict(ref)}")
        if found[0].get("status") in {"retired", "revoked", "withdrawn"}:
            raise ReferenceError("revoked_resource", f"Resource withdrawn: {ref['key']}")
        return found[0]

    def resource_paths(self, ref: Mapping[str, Any], resource: Mapping[str, Any]) -> set[str]:
        paths = {resource[key] for key in ("artifactPath", "fixtureRef", "path", "lockRef")
                 if isinstance(resource.get(key), str)}
        if ref["namespace"] == "exam":
            data_level = self.level(ref["levelId"])["dataLevel"]
            paths.add(f"data/{data_level}/questions/{resource['questionFile']}")
            if "pdf" in resource:
                paths.add(f"data/{data_level}/pdfs/{resource['pdf']}")
        elif resource.get("kind") == "pdf":
            paths.add(f"data/{resource['sourceLevel']}/pdfs/{resource['pdf']}")
        return paths

    def snapshot(self, snapshot: Mapping[str, Any]) -> Mapping[str, Any]:
        resource = self.resource(snapshot["resource"])
        revision = str(resource.get("revision", resource.get("version", "1")))
        if str(snapshot["revision"]) != revision:
            raise ReferenceError("stale_resource_revision", "Snapshot revision does not match catalog")
        if snapshot["kind"] == "repository":
            path = snapshot["artifactPath"]
            if path not in self.resource_paths(snapshot["resource"], resource):
                raise ReferenceError("resource_path_mismatch", "Snapshot artifact is not owned by that resource")
            digest = blob_hash(self.read_bytes(path))
        elif snapshot["kind"] == "external":
            if not resource.get("url"):
                raise ReferenceError("missing_external_url", "External URL must be owned by resource catalog")
            retrieved, due = _time(snapshot["retrievedAt"]), _time(snapshot["reviewDueAt"])
            if retrieved > due or retrieved > self.assessment_at:
                raise ReferenceError("invalid_review_interval", "External capture dates are inconsistent")
            if due < self.assessment_at:
                raise ReferenceError("expired_source", "External capture needs a new review")
            preimage = {key: snapshot[key] for key in ("resource", "revision", "capture")}
            if "selector" in snapshot:
                preimage["selector"] = snapshot["selector"]
            digest = value_hash(preimage)
        else:
            raise ReferenceError("unknown_snapshot_kind", "Unsupported snapshot kind")
        if digest != snapshot["hash"]:
            raise ReferenceError("stale_source_hash", "Source snapshot hash does not match its content")
        return resource

    def _guide_records(self) -> dict[str, Any]:
        data = self.read_json("content/learning/identity/guide-anchors.json")
        if isinstance(data, dict):
            data = data.get("anchors", data.get("records", []))
        return _unique(data, "anchorId", "guide anchor")

    def guide(self, ref: Mapping[str, Any], *, require_registry: bool = True) -> Mapping[str, Any]:
        if require_registry:
            registry = self._guide_records().get(ref["anchorId"])
            if registry is None or registry.get("status") != "resolved":
                raise ReferenceError("unresolved_anchor", f"Anchor is not resolved: {ref['anchorId']}")
            if registry["current"] != ref:
                raise ReferenceError("stale_anchor_mapping", "Guide ref differs from the reviewed current mapping")
        level = self.level(ref["levelId"])
        outlines = self.read_json("frontend/src/generated/guideOutlines.json")
        candidates = [guide for guide in outlines["guides"].values()
                      if guide["key"] == ref["guideKey"] and guide["level"] == level["dataLevel"]]
        if len(candidates) != 1:
            raise ReferenceError("unknown_guide", "Guide key/level is missing or ambiguous")
        outline = candidates[0]
        node = outline["nodesById"].get(ref["nodeId"])
        if node is None:
            raise ReferenceError("unknown_guide_node", "Guide node is not in this outline")
        self.chapter({"levelId": ref["levelId"], "subjectId": outline["subjectId"],
                      "chapterId": ref["nodeId"]})
        path = f"frontend/src/generated/guideContent/{ref['guideKey']}/{node['contentRef']}"
        data = self.read_json(path)
        if self.input_hashes[path] != ref["sourceHash"]:
            raise ReferenceError("stale_guide_hash", "Guide artifact changed; block IDs must not be guessed")
        blocks = _unique(data.get("blocks", []), "id", "guide block")
        if len(set(ref["blockIds"])) != len(ref["blockIds"]):
            raise ReferenceError("duplicate_block_reference", "Guide block references must be unique")
        try:
            selected = [blocks[identity] for identity in ref["blockIds"]]
        except KeyError as exc:
            raise ReferenceError("unknown_guide_block", f"Missing block: {exc.args[0]}") from exc
        actual_pages = {block.get("pageIndex") for block in selected}
        source_pages = {page["index"] for page in data.get("sourcePages", [])}
        if (None in actual_pages or set(ref["pageIndexes"]) != actual_pages
                or not actual_pages.issubset(source_pages)):
            raise ReferenceError("guide_page_mismatch", "Referenced page indices must match actual selected blocks/sourcePages")
        text = "\n".join(str(block.get("text", block.get("title", ""))) for block in selected)
        if not ref["quote"] or ref["quote"] not in text:
            raise ReferenceError("guide_quote_mismatch", "Quote is not present in the selected source blocks")
        if ref["anchor"] is not None and ref["anchor"] not in {block.get("anchor") for block in data["blocks"]}:
            raise ReferenceError("unknown_dom_anchor", "Anchor is not rendered by a source block")
        expected_route = f"/guide/{outline['subjectId']}/{ref['nodeId']}"
        if ref["fallbackRoute"] != expected_route or node.get("route") != expected_route:
            raise ReferenceError("guide_route_mismatch", "Fallback route does not match the existing outline route")
        return {"content": data, "blocks": selected, "route": expected_route}

    def source_questions(self, level_id: str, source_key: str) -> list[dict[str, Any]]:
        level = self.level(level_id)
        exams = [entry for entry in self.catalog()["exams"]
                 if entry["levelId"] == level_id and entry["key"] == source_key]
        if len(exams) > 1:
            raise ReferenceError("ambiguous_reference", "Duplicate canonical exam source")
        chapter_source = False
        if exams:
            filename = exams[0]["questionFile"]
        else:
            # Enumerate actual manifest subjects; never infer a chapter from a qid.
            manifest = self.read_json(f"data/{level['dataLevel']}/toc_manifest.json")
            allowed = set()
            for subject in manifest["subjects"]:
                suffix = subject["id"].rsplit("s", 1)[-1]
                for ending in ("questions", "guide_exercises"):
                    allowed.add(f"subject{suffix}_{ending}")
            if source_key not in allowed:
                raise ReferenceError("unknown_question_source", "Use catalog canonical key or existing chapter source stem")
            filename, chapter_source = source_key + ".json", True
        path = f"data/{level['dataLevel']}/questions/{filename}"
        data = self.read_json(path)
        rows: list[dict[str, Any]] = []
        if chapter_source:
            for chapter in data.get("chapters", []):
                rows.extend(dict(question, _chapterId=chapter["id"], _sourcePath=path)
                            for question in chapter.get("questions", []))
        else:
            rows = [dict(question, _sourcePath=path) for question in data.get("questions", [])]
        _unique(rows, "id", "source question ID")
        return rows

    def legacy_question(self, key: str) -> dict[str, Any]:
        level_id, source_key, legacy_id = parse_question_key(key)
        rows = _unique(self.source_questions(level_id, source_key), "id", "source question ID")
        if legacy_id not in rows:
            raise ReferenceError("unknown_question", "Question is absent; legacy aliases require an explicit verified decision")
        return rows[legacy_id]

    def question(self, ref: Mapping[str, Any]) -> Mapping[str, Any]:
        raw = self.legacy_question(ref["questionKey"])
        key = ("question-revision", ref["questionKey"], ref["revision"])
        document = self.documents.get(key)
        if document is None:
            raise ReferenceError("unversioned_question", "A source-bound canonical QuestionRevision is required")
        self.check_hash("question-revision", document)
        if document["contentHash"] != ref["hash"]:
            raise ReferenceError("stale_question_hash", "Question ref does not match the requested revision")
        source_hash = self.input_hashes[raw["_sourcePath"]]
        if source_hash not in document["sourceHashes"]:
            raise ReferenceError("stale_question_source", "Canonical question revision is not bound to current production source bytes")
        if (document["stem"] != raw["question"] or document["explanation"] != raw.get("explanation", "")):
            raise ReferenceError("question_content_mismatch", "Canonical question differs from its production source")
        options = {option["optionId"]: option["text"] for option in document["options"]}
        if sorted(options.values()) != sorted(raw["options"].values()):
            raise ReferenceError("question_options_mismatch", "Canonical options differ from production")
        if options.get(document["correctOptionId"]) != raw["options"].get(raw["answer"]):
            raise ReferenceError("question_answer_mismatch", "Canonical answer differs from production")
        if document["answerStatus"] in {"disputed", "withdrawn"}:
            raise ReferenceError("ineligible_question", "Disputed/withdrawn question cannot be used")
        if raw.get("images") and not document["assets"]:
            raise ReferenceError("missing_question_assets", "Image-based question requires mapped source assets")
        return document

    def alias(self, legacy_namespace: str, legacy_id: str) -> str:
        data = self.read_json("content/learning/identity/question-aliases.json")
        entries = data.get("aliases", []) if isinstance(data, dict) else data
        matches = [item for item in entries if item["legacyNamespace"] == legacy_namespace and item["legacyId"] == legacy_id]
        if len(matches) != 1 or matches[0]["decision"] != "verified" or not matches[0]["evidenceIds"]:
            raise ReferenceError("ambiguous_alias", "Legacy alias needs one verified, evidenced mapping")
        self.legacy_question(matches[0]["questionKey"])
        return matches[0]["questionKey"]

    def entity(self, ref: Mapping[str, Any]) -> Mapping[str, Any]:
        kind = ENTITY_KINDS.get(ref["kind"], ref["kind"])
        key = (kind, ref["id"], ref["revision"])
        document = self.documents.get(key)
        if document is None:
            raise ReferenceError("unknown_entity", f"Entity/revision not in complete candidate: {key}")
        if document.get("status") == "retired":
            raise ReferenceError("retired_entity", f"Entity has been retired: {key}")
        if "hash" in ref and ref["hash"] != document["contentHash"]:
            raise ReferenceError("stale_entity_hash", f"Entity hash mismatch: {key}")
        return document

    def evidence(self, ref: Mapping[str, Any]) -> Mapping[str, Any]:
        document = self.entity({"kind": "evidence", **ref})
        self.check_hash("evidence", document)
        if document["contentHash"] != ref["hash"]:
            raise ReferenceError("stale_evidence_hash", "Evidence bytes changed")
        return document

    def body_bytes(self, document: Mapping[str, Any]) -> bytes:
        path = document["bodyRef"]
        base = safe_path(self.root, "content/learning/units")
        resolved = safe_path(self.root, path)
        if not resolved.is_relative_to(base) or resolved.suffix != ".md":
            raise ReferenceError("unsafe_body_path", "Unit body must be Markdown inside its source subtree")
        return self.read_bytes(path)

    def check_hash(self, kind: str, document: Mapping[str, Any]) -> None:
        if "contentHash" not in document:
            return
        kwargs = {"body_bytes": self.body_bytes(document)} if kind == "learning-unit" else {}
        if content_hash(kind, document, **kwargs) != document["contentHash"]:
            raise ReferenceError("content_hash_mismatch", f"{kind} contentHash does not match source content")

    def validate(self, kind: str, document: Mapping[str, Any]) -> list[ValidationIssue]:
        structural = validate_document(kind, document)
        if structural:
            return structural
        issues: list[ValidationIssue] = []

        def check(path: str, operation, *args, **kwargs):
            try:
                return operation(*args, **kwargs)
            except ReferenceError as exc:
                issues.append(ValidationIssue(exc.code, path, str(exc)))
            except (KeyError, TypeError, ValueError) as exc:
                issues.append(ValidationIssue("invalid_source_shape", path, str(exc)))
            return None

        check("/contentHash", self.check_hash, kind, document)
        if kind == "guide-ref":
            check("", self.guide, document)
        elif kind == "guide-anchor-record":
            check("/current", self.guide, document["current"], require_registry=False)
        elif kind == "question-revision":
            check("", self.question, {"questionKey": document["questionKey"], "revision": document["revision"], "hash": document["contentHash"]})
        elif kind == "question-identity":
            raw = check("/questionKey", self.legacy_question, document["questionKey"])
            if raw is not None:
                parts = parse_question_key(document["questionKey"])
                if parts != (document["levelId"], document["sourceKey"], document["legacyId"]) or raw["_sourcePath"] != document["sourcePath"]:
                    issues.append(ValidationIssue("question_identity_mismatch", "/questionKey", "Identity differs from exact producer namespace"))
                if "_chapterId" in raw:
                    ref = document.get("chapterRef", {})
                    check("/chapterRef", self.chapter, ref)
                    if ref.get("chapterId") != raw["_chapterId"]:
                        issues.append(ValidationIssue("question_chapter_mismatch", "/chapterRef", "Identity chapter differs from producer"))
                else:
                    row = check("/sourceKey", self.resource, {"namespace": "exam", "levelId": parts[0], "key": parts[1]})
                    if row and document["kind"] != row["kind"]:
                        issues.append(ValidationIssue("question_kind_mismatch", "/kind", "Identity kind differs from catalog"))
        elif kind == "question-alias":
            check("/questionKey", self.legacy_question, document["questionKey"])
        for field, operation in (("chapterRefs", self.chapter), ("topicRefs", self.topic),
                                 ("guideRefs", self.guide), ("dependencies", self.snapshot),
                                 ("unitRefs", self.entity), ("labRefs", self.entity),
                                 ("projectRefs", self.entity), ("evidenceRefs", self.evidence)):
            for index, ref in enumerate(document.get(field, [])):
                check(f"/{field}/{index}", operation, ref)
        if "source" in document and isinstance(document["source"], dict):
            check("/source", self.snapshot, document["source"])
        if "guideRef" in document:
            check("/guideRef", self.guide, document["guideRef"])
        if "question" in document and isinstance(document["question"], dict):
            check("/question", self.question, document["question"])
        if kind == "question-mapping":
            target = document["target"]
            check("/target/ref", self.topic if target["kind"] == "topic" else self.guide, target["ref"])
        if document.get("artifactRef") and document.get("artifactHash"):
            artifact = check("/artifactRef", self.read_bytes, document["artifactRef"])
            if artifact is not None and blob_hash(artifact) != document["artifactHash"]:
                issues.append(ValidationIssue("artifact_hash_mismatch", "/artifactHash", "Evidence artifact changed"))
        if kind == "learning-unit":
            check("", self._validate_unit, document, check, issues)
        if kind == "lab":
            check("", self._validate_lab, document, check, issues)
        if kind in {"project", "learning-path"}:
            check("", self._validate_sequence, kind, document, check, issues)
        if kind == "mock-pool":
            seen_questions = set()
            for index, entry in enumerate(document.get("questions", [])):
                ref = entry.get("question", entry)
                if "questionKey" in ref and "revision" in ref:
                    ref = {"questionKey": ref["questionKey"], "revision": ref["revision"],
                           "hash": ref.get("hash", ref.get("contentHash"))}
                    question = check(f"/questions/{index}", self.question, ref)
                    key = (ref["questionKey"], ref["revision"])
                    if key in seen_questions:
                        issues.append(ValidationIssue("duplicate_pool_question", f"/questions/{index}", "Pool question revision is duplicated"))
                    seen_questions.add(key)
                    if question is not None and (entry["payloadPath"] != question_payload_path(*key)
                                                  or entry["fileHash"] != blob_hash(question_payload_bytes(question))):
                        issues.append(ValidationIssue("pool_payload_mismatch", f"/questions/{index}", "Pool payload path/fileHash does not match its canonical question file"))
        if kind == "mock-blueprint":
            ref = document["poolRef"]
            pool = self.documents.get(("mock-pool", ref["id"], 1))
            if pool is None or pool["contentHash"] != ref["hash"] or pool["releaseId"] != ref["releaseId"]:
                issues.append(ValidationIssue("stale_pool_reference", "/poolRef", "Blueprint must reference the candidate's exact pool binding/hash"))
            # A topic quota key stays a readable canonical name — annotations are keyed by
            # name too — but it is checked against the vocabulary, so a rename fails the
            # build instead of silently matching nothing.
            for index, quota in enumerate(document.get("quotas", [])):
                if quota.get("dimension") != "topic":
                    continue
                check(f"/quotas/{index}/key", self.topic_quota_key, quota["key"])
        return issues

    def topic_quota_key(self, key: str) -> Mapping[str, Any]:
        by_name, _ = self.topic_vocabulary()
        topic = by_name.get(key)
        if topic is None:
            raise ReferenceError("unknown_topic", "A topic quota key must be a canonical topic name")
        return topic

    def _validate_unit(self, document, check, issues):
        objectives = _unique(document["objectives"], "id", "objective")
        assessments = _unique(document["assessments"], "id", "assessment")
        rubrics = _unique(document["rubrics"], "id", "rubric")
        claims = _unique(document["claims"], "id", "claim")
        for index, objective in enumerate(document["objectives"]):
            if not objective["id"].startswith(document["id"] + "::"):
                issues.append(ValidationIssue("unqualified_objective", f"/objectives/{index}/id", "Objective must be qualified by its unit ID"))
            for identity in objective["assessmentIds"]:
                if identity not in assessments:
                    issues.append(ValidationIssue("unknown_assessment", f"/objectives/{index}/assessmentIds", identity))
        for field in ("sections", "assessments"):
            for index, item in enumerate(document[field]):
                for identity in item["objectiveIds"]:
                    if identity not in objectives:
                        issues.append(ValidationIssue("unknown_objective", f"/{field}/{index}/objectiveIds", identity))
                for identity in item.get("claimIds", []):
                    if identity not in claims:
                        issues.append(ValidationIssue("unknown_claim", f"/{field}/{index}/claimIds", identity))
        for index, assessment in enumerate(document["assessments"]):
            if assessment["rubricId"] not in rubrics:
                issues.append(ValidationIssue("unknown_rubric", f"/assessments/{index}/rubricId", assessment["rubricId"]))
        for index, claim in enumerate(document["claims"]):
            for source_index, snapshot in enumerate(claim["sourceRefs"]):
                check(f"/claims/{index}/sourceRefs/{source_index}", self.snapshot, snapshot)

    def _validate_lab(self, document, check, issues):
        data = check("/sourceNotebookRef", self.read_json, document["sourceNotebookRef"])
        if data is not None:
            if notebook_content_hash(data) != document["notebookHash"]:
                issues.append(ValidationIssue("stale_notebook_hash", "/notebookHash", "Notebook source changed"))
            cell_ids = [cell.get("metadata", {}).get("learning", {}).get("cellId") for cell in data["cells"]]
            step_ids = [cell_id for step in document["steps"] for cell_id in step["cellIds"]]
            if None in cell_ids or len(set(cell_ids)) != len(cell_ids) or sorted(cell_ids) != sorted(step_ids):
                issues.append(ValidationIssue("lab_cell_mismatch", "/steps", "Notebook and steps must cover each cell exactly once"))
        lock = check("/environment/lockRef", self.read_bytes, document["environment"]["lockRef"])
        if lock is not None and blob_hash(lock) != document["environment"]["lockHash"]:
            issues.append(ValidationIssue("stale_lock_hash", "/environment/lockHash", "Dependency lock changed"))
        allowed = set()
        for ref in document["unitRefs"]:
            unit = check("/unitRefs", self.entity, ref)
            if unit:
                allowed.update(objective["id"] for objective in unit["objectives"])
        for location, identities in [("/objectiveIds", document["objectiveIds"]),
                                     *[(f"/steps/{i}/objectiveIds", step["objectiveIds"]) for i, step in enumerate(document["steps"])],
                                     *[(f"/checks/{i}/objectiveIds", step["objectiveIds"]) for i, step in enumerate(document["checks"])]]:
            for identity in identities:
                if identity not in allowed:
                    issues.append(ValidationIssue("unknown_objective", location, "Objective must belong to a referenced unit: " + identity))
        for index, dataset in enumerate(document["datasets"]):
            resource = check(f"/datasets/{index}/resource", self.resource, dataset["resource"])
            if resource:
                required = {"license", "licenseRef", "provenance", "sha256", "bytes", "fixtureRef", "schema", "version"}
                if not required.issubset(resource):
                    issues.append(ValidationIssue("incomplete_dataset_resource", f"/datasets/{index}", "Dataset metadata belongs in the resource catalog"))
                elif str(resource["version"]) != dataset["version"] or resource["sha256"] != dataset["hash"]:
                    issues.append(ValidationIssue("stale_dataset", f"/datasets/{index}", "Dataset version/hash differs from catalog"))
                else:
                    fixture = check(f"/datasets/{index}", self.read_bytes, resource["fixtureRef"])
                    if fixture is not None and (blob_hash(fixture) != dataset["hash"] or len(fixture) != resource["bytes"]):
                        issues.append(ValidationIssue("stale_dataset_bytes", f"/datasets/{index}", "Dataset fixture changed"))

    def _validate_sequence(self, kind, document, check, issues):
        rows = document["milestones"] if kind == "project" else document["steps"]
        key, prerequisite = ("id", "prerequisiteIds") if kind == "project" else ("stepId", "prerequisiteStepIds")
        graph = {row[key]: row[prerequisite] for row in rows}
        for code, message in graph_errors(graph):
            issues.append(ValidationIssue(code, "/milestones" if kind == "project" else "/steps", message))
        if kind == "project":
            if sum(item["weight"] for item in document["rubric"]) != 100:
                issues.append(ValidationIssue("invalid_rubric_total", "/rubric", "Project rubric weights must total 100"))
            return
        for index, step in enumerate(rows):
            target = step["target"]
            if target["kind"] in ENTITY_KINDS:
                check(f"/steps/{index}/target", self.entity, target)
            elif target["kind"] == "guide":
                check(f"/steps/{index}/target/ref", self.guide, target["ref"])


def graph_errors(graph: Mapping[str, Iterable[str]]) -> list[tuple[str, str]]:
    errors: list[tuple[str, str]] = []
    active, complete = set(), set()

    def visit(node):
        if node in active:
            errors.append(("reference_cycle", f"Dependency cycle at {node}"))
            return
        if node in complete:
            return
        if node not in graph:
            errors.append(("dangling_prerequisite", f"Unknown prerequisite {node}"))
            return
        active.add(node)
        for parent in graph[node]:
            visit(parent)
        active.remove(node)
        complete.add(node)

    for identity in graph:
        visit(identity)
    return errors


def validate_references(kind: str, payload: Mapping[str, Any], *, repo_root: Path | str,
                        resolver: ReferenceResolver | None = None) -> list[ValidationIssue]:
    return (resolver or ReferenceResolver(repo_root)).validate(kind, payload)
