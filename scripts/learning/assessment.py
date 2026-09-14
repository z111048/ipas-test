"""Deterministic mock selection and transparent, explicitly scoped topic counts."""

from __future__ import annotations

import copy
import re
from collections import Counter
from typing import Any, Mapping

from .contracts import blob_hash, content_hash, value_hash, require_valid
from .references import ReferenceError, parse_question_key, question_payload_bytes


ALGORITHM = "mock-selector-v1"
SEARCH_LIMIT = 100_000


def adapt_source_question(resolver, question_key: str, *, reviewed: bool = False,
                          review_ids: list[str] | None = None) -> tuple[dict, dict]:
    """Read either legacy producer through its exact catalog/manifest namespace.

    The default preserves uncertainty. Promotion requires actual bound review IDs;
    the publication gate independently verifies their evidence and qualifications.
    """
    raw = resolver.legacy_question(question_key)
    level_id, source_key, legacy_id = parse_question_key(question_key)
    if raw.get("images") or raw.get("context_id") or raw.get("contextGroupId"):
        raise ReferenceError("unsupported_source_question", "This adapter requires standalone text questions; assets/context need explicit mapping")
    if reviewed and not review_ids:
        raise ReferenceError("missing_answer_review", "A source read is not an answer review")
    identity = {"questionKey": question_key, "levelId": level_id, "sourceKey": source_key,
                "legacyId": legacy_id, "sourcePath": raw["_sourcePath"],
                "familyId": "family-" + value_hash(question_key).removeprefix("sha256:")[:24],
                "identityReview": "verified" if reviewed else "legacy_unverified"}
    if "_chapterId" in raw:
        manifest = resolver.read_json(f"data/{resolver.level(level_id)['dataLevel']}/toc_manifest.json")
        subjects = [subject for subject in manifest["subjects"]
                    if any(chapter["id"] == raw["_chapterId"] for chapter in subject["chapters"])]
        if len(subjects) != 1:
            raise ReferenceError("ambiguous_question_chapter", question_key)
        identity["kind"] = "guide_exercise" if source_key.endswith("guide_exercises") else "chapter_practice"
        identity["chapterRef"] = {"levelId": level_id, "subjectId": subjects[0]["id"], "chapterId": raw["_chapterId"]}
    else:
        row = resolver.resource({"namespace": "exam", "levelId": level_id, "key": source_key})
        identity["kind"] = row["kind"]
        number = raw.get("number", raw.get("question_number"))
        if isinstance(number, int) and number > 0:
            identity["sourceNumber"] = number
    question = {"questionKey": question_key, "revision": 1, "contentHash": "sha256:" + "0" * 64,
                "format": "single_choice", "stem": raw["question"],
                "options": [{"optionId": "opt-" + code, "text": text} for code, text in raw["options"].items()],
                "correctOptionId": "opt-" + raw["answer"], "explanation": raw.get("explanation", ""),
                "answerStatus": "verified" if reviewed else "legacy_unverified", "assets": [],
                "reviewIds": list(review_ids or []), "sourceHashes": [resolver.input_hashes[raw["_sourcePath"]]]}
    question["contentHash"] = content_hash("question-revision", question)
    require_valid("question-identity", identity)
    require_valid("question-revision", question)
    return identity, question


def _failure(status: str, rule: str, required: int, eligible: int, *, reason: str | None = None) -> dict:
    return {"status": status, "reason": reason or (status if status != "insufficient_pool" else "unsatisfied_constraints"),
            "unmet": [{"rule": rule, "required": required, "eligible": eligible}],
            "suggestions": ["Review the reported source or constraint; change the blueprint explicitly before retrying."]}


def assemble_mock_exam(blueprint: Mapping[str, Any], pool: Mapping[str, Any], *,
                       questions: Mapping[tuple[str, int], Mapping[str, Any]],
                       identities: Mapping[str, Mapping[str, Any]],
                       annotations: Mapping[str, Mapping[str, Any]], seed: str,
                       search_limit: int = SEARCH_LIMIT) -> dict[str, Any]:
    """Select a source-bound, already reviewed pool; never generate/fix questions.

    Annotations are a frozen adapter projection with ``topics``, ``chapters`` and
    ``difficulty``. Their release eligibility belongs to the publication adapter.
    The selector rechecks identity, payload hashes, answers, and frozen pool hash.
    """
    if not re.fullmatch(r"[0-9a-f]{32}", seed):
        raise ValueError("seed must contain exactly 32 lowercase hexadecimal characters")
    if search_limit < 1 or search_limit > SEARCH_LIMIT:
        raise ValueError("search_limit must be between 1 and 100000")
    if blueprint.get("algorithmVersion") != ALGORITHM or blueprint.get("format") != "single_choice":
        return _failure("unsupported_format", "algorithm_or_format", 1, 0)
    pool_hash = content_hash("mock-pool", pool)
    blueprint_hash = content_hash("mock-blueprint", blueprint)
    if (pool_hash != pool["contentHash"] or blueprint_hash != blueprint["contentHash"]
            or blueprint["poolRef"] != {"id": pool["id"], "releaseId": pool["releaseId"], "hash": pool_hash}):
        return _failure("stale_pool", "pool_binding", 1, 0)
    if value_hash(annotations) != pool["annotationSnapshotHash"]:
        return _failure("stale_pool", "annotation_snapshot", 1, 0)
    entries, eligible = {}, {}
    for entry in pool["questions"]:
        ref = entry["question"]
        key = (ref["questionKey"], ref["revision"])
        if key in entries:
            return _failure("stale_pool", "duplicate_question_revision", 1, 2)
        entries[key] = entry
        question = questions.get(key)
        identity = identities.get(key[0])
        if question is None or identity is None:
            return _failure("stale_pool", "missing_question_payload_or_identity", 1, 0)
        if (question.get("format") != "single_choice" or len(question.get("options", [])) < 2):
            return _failure("unsupported_format", "question_format", 1, 0)
        if (question["contentHash"] != ref["hash"] or content_hash("question-revision", question) != ref["hash"]
                or blob_hash(question_payload_bytes(question)) != entry["fileHash"]):
            return _failure("stale_pool", "question_payload_hash", 1, 0)
        if (entry["identityReview"] != "verified" or identity.get("identityReview") != "verified"
                or question["answerStatus"] != "verified"):
            continue
        if identity["levelId"] != blueprint["levelId"] or identity["kind"] not in blueprint["kinds"]:
            continue
        subject = identity.get("chapterRef", {}).get("subjectId", identity.get("subjectId"))
        if subject not in blueprint["subjectIds"]:
            continue
        if question["assets"] and not all(asset.get("answerLeakReviewId") for asset in question["assets"]):
            continue
        eligible[key] = question
    groups, grouped = [], set()
    for group in pool["groups"]:
        keys = [(ref["questionKey"], ref["revision"]) for ref in group["members"]]
        if len(set(keys)) != len(keys) or any(key in grouped for key in keys):
            return _failure("stale_pool", "overlapping_context_members", len(keys), len(set(keys)))
        grouped.update(keys)
        if not all(key in eligible for key in keys):
            continue
        ordered = sorted(keys, key=lambda key: eligible[key].get("sourceOrder", -1))
        if any(eligible[key].get("contextGroupId") != group["id"]
               or eligible[key].get("contextGroupRevision") != group["revision"]
               or eligible[key].get("contextHash") != group["hash"] for key in keys):
            return _failure("stale_pool", "context_reverse_reference", len(keys), 0)
        orders = [eligible[key].get("sourceOrder") for key in ordered]
        if None in orders or len(set(orders)) != len(orders):
            return _failure("stale_pool", "context_source_order", len(keys), len(set(orders)))
        groups.append((f"context:{group['id']}:{group['revision']}", ordered))
    for key in eligible:
        if key not in grouped and not eligible[key].get("contextGroupId"):
            groups.append((key[0], [key]))
    groups.sort(key=lambda item: (value_hash(["question", seed, pool_hash, blueprint_hash, ALGORITHM, item[0]]), item[0]))
    count = blueprint["questionCount"]
    total_eligible = sum(len(keys) for _, keys in groups)
    if total_eligible < count:
        return _failure("insufficient_pool", "question_count", count, total_eligible)
    quotas = sorted(blueprint["quotas"], key=lambda quota: (-quota["priority"], quota["id"]))
    quota_by_id = {quota["id"]: quota for quota in quotas}
    if len(quota_by_id) != len(quotas) or any(quota["min"] > quota["max"] for quota in quotas):
        return _failure("insufficient_pool", "invalid_quotas", len(quotas), len(quota_by_id))
    soft_priorities = sorted({quota["priority"] for quota in quotas if quota["mode"] == "soft"}, reverse=True)
    dimensions = sorted({quota["dimension"] for quota in quotas})

    def matches(key, quota):
        annotation = annotations.get(key[0], {})
        if quota["dimension"] == "topic":
            return quota["key"] in annotation.get("topics", [])
        if quota["dimension"] == "chapter":
            return quota["key"] in annotation.get("chapters", [])
        return annotation.get("difficulty") is not None and quota["key"] == annotation["difficulty"]

    nodes = 0
    exceeded = False
    best = None
    best_score = None

    def tick():
        nonlocal nodes, exceeded
        nodes += 1
        if nodes > search_limit:
            exceeded = True
            return False
        return True

    def evaluate(selected):
        nonlocal best, best_score
        slots = [(key, dimension) for key in selected for dimension in dimensions]
        assignments = []
        counts = Counter()

        def assign(index):
            nonlocal best, best_score
            if not tick():
                return
            if index == len(slots):
                if any(quota["mode"] == "hard" and not quota["min"] <= counts[quota["id"]] <= quota["max"] for quota in quotas):
                    return
                losses = tuple(sum(max(quota["min"] - counts[quota["id"]], 0) + max(counts[quota["id"]] - quota["max"], 0)
                                   for quota in quotas if quota["mode"] == "soft" and quota["priority"] == priority)
                               for priority in soft_priorities)
                score = (losses, tuple(key[0] for key in selected), tuple(item[2] for item in assignments))
                if best_score is None or score < best_score:
                    best_score = score
                    best = (list(selected), list(assignments), counts.copy())
                return
            key, dimension = slots[index]
            choices = [quota for quota in quotas if quota["dimension"] == dimension and matches(key, quota)]
            if not choices:
                assign(index + 1)
                return
            for quota in choices:
                if quota["mode"] == "hard" and counts[quota["id"]] >= quota["max"]:
                    continue
                counts[quota["id"]] += 1
                assignments.append((key, dimension, quota["id"]))
                assign(index + 1)
                assignments.pop()
                counts[quota["id"]] -= 1
                if exceeded:
                    return

        assign(0)

    remaining = [sum(len(keys) for _, keys in groups[index:]) for index in range(len(groups) + 1)]

    def choose(index, selected, families):
        if not tick():
            return
        if len(selected) == count:
            evaluate(selected)
            return
        if index == len(groups) or len(selected) + remaining[index] < count:
            return
        _, keys = groups[index]
        new_families = [identities[key[0]]["familyId"] for key in keys]
        if (len(selected) + len(keys) <= count and len(set(new_families)) == len(new_families)
                and not families.intersection(new_families)):
            choose(index + 1, selected + keys, families | set(new_families))
        if not exceeded:
            choose(index + 1, selected, families)

    choose(0, [], set())
    if exceeded:
        return _failure("insufficient_pool", "search_nodes", count, total_eligible, reason="search_limit")
    if best is None:
        unmet = [{"rule": quota["id"], "required": quota["min"],
                  "eligible": sum(matches(key, quota) for key in eligible)} for quota in quotas if quota["mode"] == "hard"]
        return {"status": "insufficient_pool", "reason": "unsatisfied_constraints", "unmet": unmet or [{"rule": "unique_family_or_context", "required": count, "eligible": total_eligible}],
                "suggestions": ["Review family/context membership and hard quotas; no constraints were weakened."]}
    selected, assignments, counts = best
    refs = [copy.deepcopy(entries[key]["question"]) for key in selected]
    options = []
    for key, ref in zip(selected, refs):
        option_ids = [option["optionId"] for option in eligible[key]["options"]]
        if blueprint["optionOrder"] == "seeded":
            option_ids.sort(key=lambda option_id: (value_hash(["option", seed, pool_hash, blueprint_hash, ALGORITHM, key[0], key[1], option_id]), option_id))
        options.append({"question": ref, "optionIds": option_ids})
    positions = {key: index for index, key in enumerate(selected)}
    assignments.sort(key=lambda item: (positions[item[0]], item[1], item[2]))
    slot_assignments = [{"question": copy.deepcopy(entries[key]["question"]), "dimension": dimension, "quotaId": quota_id}
                        for key, dimension, quota_id in assignments]
    form_id = "form-" + value_hash([blueprint_hash, pool_hash, seed, ALGORITHM, refs, options, slot_assignments]).removeprefix("sha256:")
    return {"status": "ready", "formId": form_id, "seed": seed, "blueprintHash": blueprint_hash,
            "poolRef": copy.deepcopy(blueprint["poolRef"]), "poolHash": pool_hash,
            "selectedQuestionRevisions": refs, "slotAssignments": slot_assignments,
            "displayedOptionIds": options,
            "softMisses": [quota["id"] for quota in quotas if quota["mode"] == "soft" and not quota["min"] <= counts[quota["id"]] <= quota["max"]]}


def topic_measures(population: set[str], reviewed: set[str], mappings: list[Mapping[str, Any]],
                   topic_names: list[str]) -> list[dict[str, Any]]:
    """A topic filter selects rows, never the denominator; duplicate edges collapse."""
    reviewed = reviewed & population
    n, r = len(population), len(reviewed)
    output = []
    for topic in topic_names:
        matched = {mapping["questionKey"] for mapping in mappings
                   if mapping["questionKey"] in reviewed and mapping["topic"] == topic
                   and mapping["relation"] == "assesses" and mapping["verdict"] == "correct"}
        m, unknown = len(matched), n - r
        output.append({"topic": topic, "population": n, "reviewed": r, "matched": m, "unknown": unknown,
                       "prevalence": m / n if n and n == r else None,
                       "reviewedPrevalence": m / r if r else None,
                       "lowerBound": m / n if n else None, "upperBound": (m + unknown) / n if n else None})
    return output
