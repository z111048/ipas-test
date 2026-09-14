"""Draft 2020-12 validation and deterministic hashes for learning data."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_ROOT = REPO_ROOT / "schemas" / "learning"
SCHEMA_BASE = "https://ipas.example/schemas/learning/"

SCHEMA_TARGETS: dict[str, tuple[str, str]] = {
    "source-snapshot": ("common.schema.json", "sourceSnapshot"),
    "resource-ref": ("common.schema.json", "resourceRef"),
    "chapter-ref": ("common.schema.json", "chapterRef"),
    "topic-ref": ("common.schema.json", "topicRef"),
    "entity-ref": ("common.schema.json", "entityRef"),
    "question-ref": ("common.schema.json", "questionRef"),
    "evidence-ref": ("common.schema.json", "evidenceRef"),
    "question-identity": ("identity.schema.json", "questionIdentity"),
    "question-revision": ("identity.schema.json", "questionRevision"),
    "question-alias": ("identity.schema.json", "questionAlias"),
    "context-group": ("identity.schema.json", "contextGroup"),
    "question-difficulty": ("identity.schema.json", "questionDifficulty"),
    "guide-ref": ("identity.schema.json", "guideRef"),
    "guide-anchor-record": ("identity.schema.json", "guideAnchorRecord"),
    "learning-unit": ("content.schema.json", "learningUnit"),
    "learning-path": ("content.schema.json", "learningPath"),
    "project": ("content.schema.json", "project"),
    "lab": ("content.schema.json", "lab"),
    "learning-cell-metadata": ("content.schema.json", "learningCellMetadata"),
    "evidence": ("review.schema.json", "evidence"),
    "review": ("review.schema.json", "review"),
    "question-mapping": ("review.schema.json", "questionMapping"),
    "review-policy": ("review.schema.json", "reviewPolicy"),
    "lifecycle-event": ("publication.schema.json", "lifecycleEvent"),
    "publication-result": ("publication.schema.json", "publicationResult"),
    "release-manifest": ("publication.schema.json", "releaseManifest"),
    "release-pointer": ("publication.schema.json", "releasePointer"),
    "analysis-policy": ("analysis.schema.json", "analysisPolicy"),
    "exam-analysis": ("analysis.schema.json", "examAnalysis"),
    "mock-pool": ("mock.schema.json", "mockPool"),
    "mock-blueprint": ("mock.schema.json", "mockBlueprint"),
    "assembly-result": ("mock.schema.json", "assemblyResult"),
    "attempt-snapshot": ("attempt.schema.json", "attemptSnapshot"),
    "learner-progress": ("attempt.schema.json", "learnerProgress"),
    "attempt-storage-envelope": ("attempt.schema.json", "attemptStorageEnvelope"),
    "score-amendment": ("attempt.schema.json", "scoreAmendment"),
}


@lru_cache(maxsize=1)
def identifier_pattern() -> re.Pattern[str]:
    """The contract identifier rule, taken from the schema so it cannot drift.

    Callers must use ``fullmatch``: jsonschema evaluates ``pattern`` with ``re.search``
    and Python's ``$`` also matches before a trailing newline, so ``"topic-a\n"``
    satisfies the schema while being a different string from ``"topic-a"``.
    """

    schema = json.loads((SCHEMA_ROOT / "common.schema.json").read_text(encoding="utf-8"))
    return re.compile(schema["$defs"]["identifier"]["pattern"])


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """A stable, transport-safe contract validation finding."""

    code: str
    path: str
    message: str
    schema_path: str = ""


class DocumentValidationError(ValueError):
    """Raised when a document does not satisfy its registered contract."""

    def __init__(self, kind: str, issues: list[ValidationIssue]) -> None:
        self.kind = kind
        self.issues = tuple(issues)
        super().__init__(f"{kind} failed validation with {len(issues)} issue(s)")


def _json_pointer(parts: Any) -> str:
    escaped = [str(part).replace("~", "~0").replace("/", "~1") for part in parts]
    return "" if not escaped else "/" + "/".join(escaped)


@lru_cache(maxsize=1)
def _load_schemas(schema_root: Path = SCHEMA_ROOT) -> tuple[dict[str, Any], Registry]:
    schemas: dict[str, Any] = {}
    registry: Registry = Registry()
    for path in sorted(schema_root.glob("*.schema.json")):
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        schema_id = schema.get("$id")
        if not isinstance(schema_id, str):
            raise ValueError(f"schema has no $id: {path}")
        schemas[path.name] = schema
        registry = registry.with_resource(schema_id, Resource.from_contents(schema))
    return schemas, registry


@lru_cache(maxsize=None)
def _validator(kind: str) -> Draft202012Validator:
    try:
        filename, definition = SCHEMA_TARGETS[kind]
    except KeyError as error:
        supported = ", ".join(sorted(SCHEMA_TARGETS))
        raise ValueError(f"unknown document kind {kind!r}; expected one of: {supported}") from error
    schemas, registry = _load_schemas()
    if filename not in schemas:
        raise RuntimeError(f"registered schema file is missing: {filename}")
    wrapper = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$ref": f"{SCHEMA_BASE}{filename}#/$defs/{definition}",
    }
    return Draft202012Validator(wrapper, registry=registry, format_checker=FormatChecker())


def _local_issues(kind: str, payload: object) -> list[ValidationIssue]:
    if not isinstance(payload, Mapping):
        return []
    issues: list[ValidationIssue] = []
    if kind == "source-snapshot" and payload.get("kind") == "external":
        retrieved = payload.get("retrievedAt")
        due = payload.get("reviewDueAt")
        if isinstance(retrieved, str) and isinstance(due, str):
            try:
                out_of_order = datetime.fromisoformat(retrieved.replace("Z", "+00:00")) > datetime.fromisoformat(due.replace("Z", "+00:00"))
            except (TypeError, ValueError):
                out_of_order = False
            if out_of_order:
                issues.append(ValidationIssue("contract.date_order", "/reviewDueAt", "reviewDueAt must not be earlier than retrievedAt"))
    if kind == "question-revision":
        options = payload.get("options")
        if isinstance(options, list):
            option_ids = [item.get("optionId") for item in options if isinstance(item, Mapping) and isinstance(item.get("optionId"), str)]
            if len(option_ids) != len(set(option_ids)):
                issues.append(ValidationIssue("contract.duplicate_option_id", "/options", "optionId values must be unique"))
            correct = payload.get("correctOptionId")
            if isinstance(correct, str) and correct not in option_ids:
                issues.append(ValidationIssue("contract.unknown_correct_option", "/correctOptionId", "correctOptionId must identify one of options"))
    if kind == "lifecycle-event":
        before, after = payload.get("from"), payload.get("to")
        if not isinstance(before, str) or not isinstance(after, str):
            return issues
        transition = (before, after)
        allowed = {("draft", "in_review"), ("in_review", "draft"), ("in_review", "published"), ("published", "retired")}
        if transition not in allowed:
            issues.append(ValidationIssue("contract.invalid_transition", "/to", f"lifecycle transition {transition[0]!r} -> {transition[1]!r} is not allowed"))
    return issues


def validate_document(kind: str, payload: object) -> list[ValidationIssue]:
    """Validate one document structurally, without resolving cross-file references."""

    errors = sorted(_validator(kind).iter_errors(payload), key=lambda error: (tuple(map(str, error.absolute_path)), error.message))
    issues = [
        ValidationIssue(
            code=f"schema.{error.validator or 'validation'}",
            path=_json_pointer(error.absolute_path),
            message=error.message,
            schema_path=_json_pointer(error.absolute_schema_path),
        )
        for error in errors
    ]
    issues.extend(_local_issues(kind, payload))
    return sorted(issues, key=lambda issue: (issue.path, issue.code, issue.message))


def require_valid(kind: str, payload: object) -> None:
    """Raise :class:`DocumentValidationError` when validation fails."""

    issues = validate_document(kind, payload)
    if issues:
        raise DocumentValidationError(kind, issues)


def canonical_json_bytes(value: object) -> bytes:
    """Return canonical UTF-8 JSON: sorted keys and original array order."""

    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def blob_hash(value: bytes | bytearray | memoryview) -> str:
    """Hash exact bytes with the contract's tagged SHA-256 representation."""

    return "sha256:" + hashlib.sha256(bytes(value)).hexdigest()


def value_hash(value: object) -> str:
    """Hash a structured value after canonical JSON encoding."""

    return blob_hash(canonical_json_bytes(value))


def project_for_hash(kind: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return the version-1 content projection for a structured document."""

    value = copy.deepcopy(dict(payload))
    if kind == "source-snapshot" and value.get("kind") == "external":
        return {key: value[key] for key in ("resource", "revision", "selector", "capture") if key in value}
    if kind == "question-revision":
        keys = ("questionKey", "format", "stem", "options", "correctOptionId", "explanation", "contextGroupId", "contextGroupRevision", "contextHash", "sourceOrder", "assets", "sourceHashes")
        return {key: value[key] for key in keys if key in value}
    if kind == "context-group":
        return {key: value[key] for key in ("text", "assets", "sourceHashes") if key in value}
    if kind in {"mock-pool", "exam-analysis"}:
        value.pop("releaseId", None)
    if kind == "mock-blueprint" and isinstance(value.get("poolRef"), dict):
        value["poolRef"].pop("releaseId", None)
    if kind == "attempt-storage-envelope":
        return copy.deepcopy(value.get("snapshot", {}))
    value.pop("contentHash", None)
    value.pop("status", None)
    value.pop("reviewIds", None)
    if kind == "lab":
        value.pop("executionReviewId", None)
        value.pop("semanticReviewId", None)
    return value


def content_hash(kind: str, payload: Mapping[str, Any], *, body_bytes: bytes | None = None) -> str:
    """Hash a document's explicit version-1 content projection."""

    projection = project_for_hash(kind, payload)
    if kind == "learning-unit":
        if body_bytes is None:
            raise ValueError("learning-unit content_hash requires body_bytes")
        preimage: object = ["learning-unit-content-v1", projection, {"bodyHash": blob_hash(body_bytes)}]
    else:
        if body_bytes is not None:
            raise ValueError("body_bytes is only valid for learning-unit")
        preimage = [f"{kind}-content-v1", projection]
    return value_hash(preimage)


def notebook_projection(notebook: Mapping[str, Any]) -> dict[str, Any]:
    """Project notebook cell identity/source and execution-affecting metadata."""

    metadata = notebook.get("metadata", {})
    root_metadata = {key: copy.deepcopy(metadata[key]) for key in ("kernelspec", "language_info", "learning") if key in metadata}
    cells: list[dict[str, Any]] = []
    for cell in notebook.get("cells", []):
        cell_metadata = cell.get("metadata", {})
        effective_metadata = {key: copy.deepcopy(cell_metadata[key]) for key in ("learning", "tags") if key in cell_metadata}
        cells.append({
            "id": cell.get("id"),
            "cell_type": cell.get("cell_type"),
            "source": copy.deepcopy(cell.get("source", [])),
            "metadata": effective_metadata,
        })
    return {"nbformat": notebook.get("nbformat"), "nbformat_minor": notebook.get("nbformat_minor"), "metadata": root_metadata, "cells": cells}


def notebook_content_hash(notebook: Mapping[str, Any]) -> str:
    """Hash a notebook while excluding outputs and execution counters."""

    return value_hash(["notebook-content-v1", notebook_projection(notebook)])
