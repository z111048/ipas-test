"""Build the reviewed MVP diagnostic and explicitly incomplete official-question analysis."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from curate_learning_questions import CANONICAL_PATH, DRAFT_PATH, REVIEW_PATH, canonical_question, reviewed_draft
from learning.assessment import adapt_source_question, assemble_mock_exam, topic_measures
from learning.contracts import blob_hash, content_hash, require_valid, value_hash
from learning.publication import build_learning_content, dependency_hashes
from learning.references import ReferenceError, ReferenceResolver, document_identity, question_payload_bytes, question_payload_path

SEED = "0123456789abcdef0123456789abcdef"
POOL_ID = "pool-imbalanced-classification-v1"
BLUEPRINT_ID = "diagnostic-imbalanced-classification-v1"
ANALYSIS_ID = "analysis-imbalanced-source-examples-v1"
SELECTION_PATH = "content/learning/evidence/assessment/official-source-selection.json"
DELEGATION_PATH = "content/learning/qualifications/assessment-delegation.json"
TOPICS = {"unit-split-before-fit": "資料洩漏", "unit-imbalanced-classification": "評估指標", "unit-threshold-decision": "模型評估"}
REVIEWED_AT = "2026-09-07T12:01:50Z"


def _review_ids(key):
    suffix = value_hash(key).removeprefix("sha256:")[:20]
    return [f"review-{role}-{suffix}" for role in ("domain", "answer", "contract")]


def _evidence(identity, path, resolver, claim):
    evidence = {"id": identity, "revision": 1, "contentHash": "sha256:" + "0" * 64,
                "kind": "editorial_reasoning", "claim": claim, "artifactRef": path,
                "artifactHash": blob_hash(resolver.read_bytes(path)), "observedAt": REVIEWED_AT}
    evidence["contentHash"] = content_hash("evidence", evidence)
    require_valid("evidence", evidence)
    return evidence


def review_policy():
    requirements = []
    for kind in ["learning-unit", "project", "lab", "mock-blueprint", "mock-pool", "exam-analysis", "question-revision"]:
        responsibilities = ["domain_content", "deterministic_contract"]
        if kind in {"question-revision", "mock-pool"}:
            responsibilities.append("assessment_answer")
        for responsibility in responsibilities:
            code, scope = {"domain_content": ("D1", "mvp-domain-content"),
                           "assessment_answer": ("A1", "mvp-assessment-answer"),
                           "deterministic_contract": ("C1", "mvp-source-contract")}[responsibility]
            requirements.append({"subjectKind": kind, "responsibility": responsibility,
                                 "allowedReviewerRoles": ["automated_check"] if responsibility == "deterministic_contract" else ["independent_model", "human"],
                                 "qualificationScope": scope, "rubricVersion": "mvp-review-v1", "requiredCheckCodes": [code],
                                 "independentFromAuthor": responsibility != "deterministic_contract"})
    requirements.extend([
        {"subjectKind": "lab", "responsibility": "notebook_execution", "allowedReviewerRoles": ["automated_check"],
         "qualificationScope": "lab-local-execution", "rubricVersion": "lab-v1", "requiredCheckCodes": ["L0", "L1", "L2", "L3"], "independentFromAuthor": False},
        {"subjectKind": "lab", "responsibility": "notebook_execution", "allowedReviewerRoles": ["human"],
         "qualificationScope": "human-colab-smoke", "rubricVersion": "lab-v1", "requiredCheckCodes": ["L5"], "independentFromAuthor": True}])
    return {"schemaVersion": 1, "id": "learning-mvp-review-policy", "version": 1, "requirements": requirements}


def assessment_inputs(root: Path | str, *, record_reviews: bool = False) -> dict:
    """Adapt reviewed source snapshots; never generate content or upgrade unreviewed answers."""
    root = Path(root).resolve()
    draft, receipt = reviewed_draft(root)
    resolver = ReferenceResolver(root)
    for path in (DRAFT_PATH, REVIEW_PATH, DELEGATION_PATH):
        resolver.read_bytes(path)
    if blob_hash(resolver.read_bytes(CANONICAL_PATH)) != receipt.get("canonicalSourceHash"):
        raise ReferenceError("stale_curated_source", "The independent receipt must bind the exact curated source file")
    delegation = resolver.read_json(DELEGATION_PATH)
    if (delegation.get("grantedBy") != "root-coordinator" or delegation.get("grantedTo") != "agent-content-labs"
            or delegation.get("humanApproval") is not False):
        raise ReferenceError("invalid_delegation", "This review is restricted to the recorded model delegation")
    evidence = [_evidence("ev-mvp-review-report", receipt["reportPath"], resolver, "獨立模型逐題推算、唯一正解與誘答審查；不是人類簽核。"),
                _evidence("ev-mvp-model-delegation", DELEGATION_PATH, resolver, "Root coordinator 本次專案的 machine-role 限域委派。"),
                _evidence("ev-mvp-curated-source", CANONICAL_PATH, resolver, "已審十題刻意追加，原102題與cards保持不變。")]
    documents = {document_identity("evidence", item): item for item in evidence}
    questions, identities, annotations, entries = {}, {}, {}, []
    selected = resolver.read_json(SELECTION_PATH)["candidates"]
    keys = ["q:middle:subject3_questions:" + question["id"] for question in draft["questions"]]
    official_keys = [item["candidateQuestionKey"] for item in selected]
    if len(set(official_keys)) != 5:
        raise ReferenceError("source_selection_count", "Five independently checked source examples are required")
    for item in selected:
        if blob_hash(resolver.read_bytes(item["sourcePath"])) != item["sourceFileHash"]:
            raise ReferenceError("stale_official_source", item["candidateQuestionKey"])
        raw = resolver.legacy_question(item["candidateQuestionKey"])
        if raw["_sourcePath"] != item["sourcePath"]:
            raise ReferenceError("source_namespace_mismatch", item["candidateQuestionKey"])
    evidence.append(_evidence("ev-mvp-official-selection", SELECTION_PATH, resolver,
                              "五題 source-bound 選讀清單；直接讀 canonical 原文、選項與答案，未宣稱人類 PDF 審查。"))
    documents.update({document_identity("evidence", item): item for item in evidence})
    evidence_refs = [{"id": item["id"], "revision": 1, "hash": item["contentHash"]} for item in evidence]
    records = {}
    for key in keys + official_keys:
        ids = _review_ids(key)
        identity, question = adapt_source_question(resolver, key, reviewed=True, review_ids=ids)
        identities[key] = identity
        questions[(key, 1)] = question
        documents[document_identity("question-revision", question)] = question
        documents[document_identity("question-identity", identity)] = identity
        resolver.documents = documents
        errors = resolver.validate("question-revision", question)
        if errors:
            raise ReferenceError("question_contract_check_failed", str(errors))
        for index, (responsibility, code, scope) in enumerate([
                ("domain_content", "D1", "mvp-domain-content"), ("assessment_answer", "A1", "mvp-assessment-answer"),
                ("deterministic_contract", "C1", "mvp-source-contract")]):
            record = {"id": ids[index], "subject": {"kind": "question-revision", "id": key, "revision": 1, "hash": question["contentHash"]},
                      "dependencyHashes": dependency_hashes(question, resolver), "rubricVersion": "mvp-review-v1",
                      "reviewerId": "script-learning-assessment" if index == 2 else "agent-content-labs",
                      "reviewerRole": "automated_check" if index == 2 else "independent_model",
                      "authorId": "official-source" if key in official_keys else "agent-p0-baseline",
                      "responsibility": responsibility, "qualification": {"scope": [scope], "evidenceIds": ["ev-mvp-model-delegation"],
                      "grantedBy": "root-coordinator", "grantedAt": REVIEWED_AT}, "evidenceRefs": evidence_refs,
                      "verdict": "approved", "checks": [{"code": code, "verdict": "pass", "evidenceIds": [item["id"] for item in evidence]}],
                      "createdAt": REVIEWED_AT,
                      "rationale": "C1 實際執行 schema、來源 namespace/raw hash、選項及答案一致檢查。" if index == 2 else "見逐題獨立審查報告；scope 僅本次 model 內容/答案查核，不是人類批准。"}
            require_valid("review", record)
            records[f"content/learning/reviews/{record['id']}.json"] = record
    for authored, key in zip(draft["questions"], keys):
        raw = resolver.legacy_question(key)
        if {name: value for name, value in raw.items() if not name.startswith("_")} != canonical_question(authored, raw["chapter_title"]):
            raise ReferenceError("curated_projection_mismatch", key)
        question = questions[(key, 1)]
        annotations[key] = {"topics": [TOPICS[authored["unitId"]]], "chapters": ["mid-s3c9"], "difficulty": None}
        entries.append({"question": {"questionKey": key, "revision": 1, "hash": question["contentHash"]},
                        "payloadPath": question_payload_path(key, 1), "fileHash": blob_hash(question_payload_bytes(question)),
                        "identityReview": "verified", "mappingReviewIds": [_review_ids(key)[0]], "difficultyReviewIds": []})
    pool = {"schemaVersion": 1, "id": POOL_ID, "releaseId": "candidate", "contentHash": "sha256:" + "0" * 64,
            "policyHash": value_hash(review_policy()), "annotationSnapshotHash": value_hash(annotations), "questions": entries, "groups": []}
    pool["contentHash"] = content_hash("mock-pool", pool)
    blueprint = resolver.read_json(f"content/learning/mock-blueprints/{BLUEPRINT_ID}.json")
    require_valid("mock-blueprint", blueprint)
    if blueprint["poolRef"] != {"id": pool["id"], "releaseId": pool["releaseId"], "hash": pool["contentHash"]}:
        raise ReferenceError("stale_authored_blueprint", "Curated blueprint must bind the exact reviewed pool")
    if content_hash("mock-blueprint", blueprint) != blueprint["contentHash"]:
        raise ReferenceError("stale_authored_blueprint", "Authored blueprint content changed without a new hash/review")
    assembly = assemble_mock_exam(blueprint, pool, questions=questions, identities=identities, annotations=annotations, seed=SEED)
    if assembly["status"] != "ready":
        raise ReferenceError("unavailable_diagnostic", str(assembly))
    analysis, mappings = _official_analysis(resolver, selected, questions)
    source_examples = []
    for index, entry in enumerate(selected):
        key = entry["candidateQuestionKey"]
        raw = resolver.legacy_question(key)
        level, exam_key = key.split(":")[1:3]
        page_index = raw["source_ref"]["page_index"]
        source_examples.append({"question": {"questionKey": key, "revision": 1, "hash": questions[(key, 1)]["contentHash"]},
                                "questionPath": question_payload_path(key, 1), "stem": raw["question"], "unitId": entry["unitId"],
                                "relation": "prerequisite" if index == 4 else "explained_by",
                                "reason": "F1 的調和平均是後續比較指標與閾值決策的先備概念；本題沒有直接考成本閾值。" if index == 4 else entry["reason"],
                                "source": {"levelId": level, "examKey": exam_key, "pageIndex": page_index,
                                           "pageNumber": page_index + 1, "route": "/exam/" + exam_key}})
    documents.update({document_identity("mock-pool", pool): pool, document_identity("exam-analysis", analysis): analysis})
    for mapping in mappings:
        documents[document_identity("question-mapping", mapping)] = mapping
    for kind, document in (("mock-pool", pool), ("mock-blueprint", blueprint), ("exam-analysis", analysis)):
        require_valid(kind, document)
    records["content/learning/review-policy.json"] = review_policy()
    for path, record in records.items():
        target = root / path
        if record_reviews and not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
        if resolver.read_json(path) != record:
            raise ReferenceError("stale_recorded_review", path + ": changed sources require explicit independent re-review")
    return {"additional_documents": documents,
            "additional_artifacts": {f"annotations/{POOL_ID}.json": {"annotations": annotations, "identities": {key: identities[key] for key in keys}},
                                     f"assemblies/{BLUEPRINT_ID}.json": {"document": assembly},
                                     f"analysis-examples/{ANALYSIS_ID}.json": {"examples": source_examples}},
            "additional_inputs": dict(resolver.input_hashes), "assembly": assembly, "analysis": analysis}


def _official_analysis(resolver, selected, questions):
    catalog = resolver.read_json("data/resource_catalog.json")
    # taxonomyHash 仍記整份詞彙表的版本（analysis 要的是整體快照 provenance）；
    # 個別 TopicRef 則改用不可變 id，新增概念不再讓既有引用失效。
    vocabulary = blob_hash(resolver.read_bytes("data/topics/topics.json"))
    topic_ids = {name: entry["id"] for name, entry in resolver.topic_vocabulary()[0].items()}
    sources = sorted({(item["candidateQuestionKey"].split(":")[1], item["candidateQuestionKey"].split(":")[2]) for item in selected})
    policy = resolver.read_json("content/learning/analysis-policies/analysis-selected-three-volumes-v1.json")
    require_valid("analysis-policy", policy)
    if sorted((entry["levelId"], entry["key"]) for entry in policy["examKeys"]) != sources:
        raise ReferenceError("analysis_source_scope_mismatch", "The authored policy must match this reviewed source selection")
    catalog_subjects = {resolver.resource({"namespace": "exam", "levelId": level, "key": key})["subjectId"] for level, key in sources}
    if set(policy["levelIds"]) != {level for level, _ in sources} or set(policy["subjectIds"]) != catalog_subjects:
        raise ReferenceError("analysis_source_scope_mismatch", "Policy levels/subjects must match catalog-owned source metadata")
    if (policy["kinds"] != ["official"] or policy["mappingPolicy"] != "source_bound_strict_v1"
            or policy["unit"] != "occurrence" or policy["answerPolicy"] != "include_with_status"):
        raise ReferenceError("unsupported_analysis_policy", "This adapter implements the explicit occurrence/official selection policy")
    inventory, population, mappings, raw_edges = [], set(), [], []
    reviewed = {item["candidateQuestionKey"] for item in selected}
    for level, key in sources:
        row = resolver.resource({"namespace": "exam", "levelId": level, "key": key})
        rows = resolver.source_questions(level, key)
        prefix = f"q:{level}:{key}:"
        population.update(prefix + item["id"] for item in rows)
        inventory.append({"levelId": level, "examKey": key, "kind": "official", "expected": row.get("expectedQuestions"),
                          "present": len(rows), "labelReviewed": sum(key_.startswith(prefix) for key_ in reviewed), "answerDisputed": 0})
    for index, item in enumerate(selected):
        key = item["candidateQuestionKey"]
        topics = ["資料洩漏"] if index == 0 else ["評估指標"]
        if index in {1, 2}:
            topics.append("類別不平衡")
        for topic in topics:
            question = questions[(key, 1)]
            mapping = {"id": "map-" + value_hash([key, topic]).removeprefix("sha256:")[:24],
                       "question": {"questionKey": key, "revision": 1, "hash": question["contentHash"]},
                       "target": {"kind": "topic", "ref": {"id": topic_ids[topic], "name": topic}},
                       "relation": "assesses", "verdict": "correct", "evidenceIds": ["ev-mvp-review-report", "ev-mvp-official-selection"],
                       "reviewIds": [_review_ids(key)[0]], "origin": "editorial"}
            require_valid("question-mapping", mapping)
            mappings.append(mapping)
            raw_edges.append({"questionKey": key, "topic": topic, "relation": "assesses", "verdict": "correct"})
    rows = topic_measures(population, reviewed, raw_edges, ["資料洩漏", "評估指標", "類別不平衡"])
    for row in rows:
        row["scopeKey"] = policy["id"]
        row["topic"] = {"id": topic_ids[row["topic"]], "name": row["topic"]}
    analysis = {"schemaVersion": 1, "id": ANALYSIS_ID, "policy": policy, "policyHash": value_hash(policy),
                "catalogHash": resolver.input_hashes["data/resource_catalog.json"], "contentHash": "sha256:" + "0" * 64,
                "taxonomyHash": vocabulary, "labelReviewHash": value_hash(mappings), "releaseId": "candidate", "inventory": inventory,
                "publicationCoverage": {"sessionsKnown": [], "sessionsIncluded": [], "missingSessions": [], "exhaustive": False,
                                        "evidenceIds": ["ev-mvp-official-selection"]}, "measures": rows,
                "exclusions": [{"reason": "其他試卷不在本次明確選讀範圍；本結果不代表全部歷屆或命題預測。", "count": 0},
                               {"reason": "範圍內尚未逐題審查主題標記，保留為 unknown 並仍計入母體。", "count": len(population) - len(reviewed)}]}
    analysis["contentHash"] = content_hash("exam-analysis", analysis)
    return analysis, mappings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--record-reviews", action="store_true", help="Materialize this already completed review once; differing records are never overwritten")
    parser.add_argument("--lab-assets-manifest", default="", help="Optional staging manifest; default derives exact bytes from committed notebook source")
    args = parser.parse_args()
    try:
        if args.record_reviews and (args.check or args.dry_run):
            raise ReferenceError("conflicting_modes", "Record creation cannot be combined with read-only modes")
        prepared = assessment_inputs(args.repo_root, record_reviews=args.record_reviews)
        report = build_learning_content(args.repo_root, preview=args.preview, check=args.check, dry_run=args.dry_run,
                                       additional_documents=prepared["additional_documents"], additional_artifacts=prepared["additional_artifacts"],
                                       additional_inputs=prepared["additional_inputs"], lab_assets_manifest=args.lab_assets_manifest)
        report["diagnostic"] = {"questionCount": 10, "distribution": [3, 4, 3], "seed": SEED, "formId": prepared["assembly"]["formId"]}
        report["sourceAnalysis"] = {"volumes": len(prepared["analysis"]["inventory"]), "reviewed": 5,
                                    "population": sum(row["present"] for row in prepared["analysis"]["inventory"]), "exhaustive": False}
    except (ReferenceError, KeyError, ValueError, OSError) as exc:
        report = {"status": "blocked", "reason": str(exc)}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(report["status"] == "blocked")


if __name__ == "__main__":
    raise SystemExit(main())
