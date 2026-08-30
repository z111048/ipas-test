"""Load and validate the shared exam/resource catalog."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data" / "resource_catalog.json"
REQUIRED_EXAM_FIELDS = {
    "key", "routeKey", "levelId", "kind", "pdf", "questionFile",
    "title", "label", "expectedQuestions", "guideKeys",
}


@lru_cache(maxsize=1)
def load_resource_catalog() -> dict[str, Any]:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return validate_resource_catalog(catalog)


def validate_resource_catalog(catalog: dict[str, Any]) -> dict[str, Any]:
    """Validate schema plus every identifier used by Python and frontend lookups."""
    if catalog.get("schemaVersion") != 1:
        raise ValueError(f"Unsupported resource catalog schema: {catalog.get('schemaVersion')!r}")

    levels = catalog.get("levels")
    exams = catalog.get("exams")
    resources = catalog.get("resources")
    if not isinstance(levels, list) or not isinstance(exams, list) or not isinstance(resources, list):
        raise ValueError("resource catalog levels/exams/resources must be arrays")

    level_ids: set[str] = set()
    data_levels: set[str] = set()
    for level in levels:
        level_id = str(level.get("id") or "")
        data_level = str(level.get("dataLevel") or "")
        if not level_id or level_id in level_ids:
            raise ValueError(f"Duplicate or empty catalog level id: {level_id!r}")
        if not data_level or data_level in data_levels:
            raise ValueError(f"Duplicate or empty catalog data level: {data_level!r}")
        level_ids.add(level_id)
        data_levels.add(data_level)

    canonical: set[tuple[str, str]] = set()
    routes: set[str] = set()
    question_files: set[tuple[str, str]] = set()
    identifier_owners: dict[tuple[str, str], tuple[str, str]] = {}
    for exam in exams:
        missing = REQUIRED_EXAM_FIELDS - set(exam)
        if missing:
            raise ValueError(f"Catalog exam is missing {sorted(missing)}: {exam!r}")
        level_id = str(exam["levelId"])
        if level_id not in level_ids:
            raise ValueError(f"Catalog exam has unknown levelId {level_id!r}")
        key = str(exam["key"])
        identity = (level_id, key)
        if identity in canonical:
            raise ValueError(f"Duplicate catalog exam key within level: {identity}")
        canonical.add(identity)
        route_key = str(exam["routeKey"])
        if not route_key or route_key in routes:
            raise ValueError(f"Duplicate or empty catalog routeKey: {route_key!r}")
        routes.add(route_key)
        question_identity = (level_id, str(exam["questionFile"]))
        if question_identity in question_files:
            raise ValueError(f"Duplicate catalog questionFile within level: {question_identity}")
        question_files.add(question_identity)
        if exam.get("kind") not in {"official", "sample"}:
            raise ValueError(f"Unsupported catalog exam kind: {exam.get('kind')!r}")
        subject_id = exam.get("subjectId")
        if exam["kind"] == "official" and not isinstance(subject_id, str):
            raise ValueError(f"Official catalog exam has no subjectId: {identity}")
        if subject_id is not None and not isinstance(subject_id, str):
            raise ValueError(f"Invalid subjectId for {identity}: {subject_id!r}")
        guide_keys = exam.get("guideKeys")
        if (
            not isinstance(guide_keys, list)
            or not guide_keys
            or any(not isinstance(guide_key, str) or not guide_key for guide_key in guide_keys)
        ):
            raise ValueError(f"Invalid guideKeys for {identity}: {guide_keys!r}")
        if not isinstance(exam.get("expectedQuestions"), int) or exam["expectedQuestions"] <= 0:
            raise ValueError(f"Invalid expectedQuestions for {identity}")

        raw_aliases = exam.get("aliases") or []
        if not isinstance(raw_aliases, list):
            raise ValueError(f"Catalog aliases must be an array for {identity}")
        for token in [key, route_key, *map(str, raw_aliases)]:
            if not token:
                raise ValueError(f"Empty catalog exam identifier for {identity}")
            lookup = (level_id, token)
            owner = identifier_owners.get(lookup)
            if owner is not None and owner != identity:
                raise ValueError(
                    f"Ambiguous catalog identifier {lookup}: owned by {owner} and {identity}"
                )
            identifier_owners[lookup] = identity

    resource_keys: set[str] = set()
    for resource in resources:
        resource_key = str(resource.get("key") or "")
        if not resource_key or resource_key in resource_keys:
            raise ValueError(f"Duplicate or empty catalog resource key: {resource_key!r}")
        resource_keys.add(resource_key)
        visible_in = resource.get("visibleIn")
        if not isinstance(visible_in, list) or not visible_in:
            raise ValueError(f"Catalog resource has no visibleIn levels: {resource_key}")
        unknown_levels = set(map(str, visible_in)) - level_ids
        if unknown_levels:
            raise ValueError(
                f"Catalog resource {resource_key} has unknown levels: {sorted(unknown_levels)}"
            )

    return catalog


def level_entries() -> list[dict[str, Any]]:
    return list(load_resource_catalog()["levels"])


def level_entry(*, level_id: str | None = None, data_level: str | None = None) -> dict[str, Any]:
    for entry in level_entries():
        if level_id is not None and entry["id"] == level_id:
            return entry
        if data_level is not None and entry["dataLevel"] == data_level:
            return entry
    requested = level_id if level_id is not None else data_level
    raise KeyError(f"Unknown catalog level: {requested}")


def exam_entries(*, level: str | None = None, kind: str | None = None) -> list[dict[str, Any]]:
    entries = load_resource_catalog()["exams"]
    if level is not None:
        level_id = level_entry(data_level=level)["id"]
        entries = [entry for entry in entries if entry["levelId"] == level_id]
    if kind is not None:
        entries = [entry for entry in entries if entry["kind"] == kind]
    return list(entries)


def exam_entry(level: str, key_or_alias: str) -> dict[str, Any]:
    entries = exam_entries(level=level)
    for entry in entries:
        if key_or_alias in {entry["key"], entry["routeKey"], *(entry.get("aliases") or [])}:
            return entry
    raise KeyError(f"Unknown exam for {level}: {key_or_alias}")


def exam_pdf_maps() -> dict[str, dict[str, str]]:
    return {
        level["dataLevel"]: {
            entry["key"]: entry["pdf"]
            for entry in exam_entries(level=level["dataLevel"])
        }
        for level in level_entries()
    }


def reference_pdf_maps() -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for resource in load_resource_catalog()["resources"]:
        if resource.get("kind") != "pdf":
            continue
        result.setdefault(resource["sourceLevel"], {})[resource["sourceKey"]] = resource["pdf"]
    return result


def question_file_maps(*, route_keys: bool = False) -> dict[str, dict[str, str]]:
    return {
        level["dataLevel"]: {
            entry["routeKey" if route_keys else "key"]: entry["questionFile"]
            for entry in exam_entries(level=level["dataLevel"])
        }
        for level in level_entries()
    }


def question_path(level: str, key_or_alias: str) -> Path:
    """Resolve a catalog exam identifier to its canonical question JSON path."""
    entry = exam_entry(level, key_or_alias)
    return ROOT / "data" / level / "questions" / entry["questionFile"]


def iter_question_paths(entries: Iterable[dict[str, Any]] | None = None) -> Iterable[tuple[dict[str, Any], Path]]:
    selected = exam_entries() if entries is None else entries
    for entry in selected:
        data_level = level_entry(level_id=entry["levelId"])["dataLevel"]
        yield entry, ROOT / "data" / data_level / "questions" / entry["questionFile"]
