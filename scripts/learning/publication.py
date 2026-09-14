"""Validate complete learning candidates and atomically enable immutable bundles."""

from __future__ import annotations

import copy
import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

from .contracts import canonical_json_bytes, blob_hash, validate_document, value_hash
from .references import (
    ENTITY_KINDS, SOURCE_DIRS, ReferenceError, ReferenceResolver, document_identity,
    graph_errors, question_payload_bytes, question_payload_path, safe_path,
)


EXPORTER_VERSION = "learning-publication-v1"
PUBLIC_KINDS = {"learning-unit": "units", "learning-path": "paths", "project": "projects",
                "lab": "labs", "mock-blueprint": "blueprints", "mock-pool": "pools", "exam-analysis": "analysis"}
STAGES = ("schema", "references", "review", "execution", "integrity", "commit")
LEARNING_ROOT = "frontend/src/generated/learning"


@dataclass(frozen=True)
class PublicationIssue:
    stage: str
    code: str
    path: str
    message: str
    evidence_ids: tuple[str, ...] = ()


@dataclass
class Candidate:
    documents: dict[tuple[str, str, int], dict[str, Any]]
    source_paths: dict[tuple[str, str, int], str]
    resolver: ReferenceResolver
    issues: list[PublicationIssue] = field(default_factory=list)


def load_candidate(repo_root: str | Path, *, assessment_at: str | None = None,
                   additional_documents: Mapping[tuple[str, str, int], Mapping[str, Any]] | None = None) -> Candidate:
    resolver = ReferenceResolver(repo_root, assessment_at=assessment_at)
    documents: dict[tuple[str, str, int], dict[str, Any]] = {}
    paths: dict[tuple[str, str, int], str] = {}
    issues: list[PublicationIssue] = []
    for kind, directory in SOURCE_DIRS.items():
        base = resolver.root / "content" / "learning" / directory
        for path in sorted(base.glob("*.json")):
            relative = path.relative_to(resolver.root).as_posix()
            try:
                document = resolver.read_json(relative)
                errors = validate_document(kind, document)
                if errors:
                    issues.extend(PublicationIssue("schema", error.code, relative + error.path, error.message)
                                  for error in errors)
                    continue
                key = document_identity(kind, document)
                if key in documents:
                    issues.append(PublicationIssue("references", "duplicate_entity_revision", relative, str(key)))
                    continue
                documents[key], paths[key] = document, relative
            except (ReferenceError, TypeError, ValueError) as exc:
                issues.append(PublicationIssue("schema", getattr(exc, "code", "invalid_document"), relative, str(exc)))
    for key, payload in (additional_documents or {}).items():
        if key in documents or key != document_identity(key[0], payload):
            issues.append(PublicationIssue("references", "duplicate_entity_revision", str(key), "Injected adapter identity conflicts with candidate"))
            continue
        errors = validate_document(key[0], payload)
        if errors:
            issues.extend(PublicationIssue("schema", error.code, f"adapter:{key}" + error.path, error.message)
                          for error in errors)
            continue
        documents[key] = dict(payload)
        paths[key] = f"adapter:{key[0]}/{key[1]}@{key[2]}"
        # Projection identity participates in reproducibility; source artifacts are
        # separately loaded and hash-bound by the reference resolver.
    resolver.documents = documents
    return Candidate(documents, paths, resolver, issues)


def dependency_hashes(document: Mapping[str, Any], resolver: ReferenceResolver) -> list[str]:
    """Exact source fingerprints a review must bind; order is not significant."""
    hashes: set[str] = set()

    def visit(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"hash", "sourceHash", "notebookHash", "lockHash", "artifactHash"} and isinstance(item, str):
                    hashes.add(item)
                elif key not in {"reviewIds", "artifacts", "contentHash"}:
                    visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(document)
    for field in ("unitRefs", "labRefs", "projectRefs"):
        for ref in document.get(field, []):
            hashes.add(resolver.entity(ref)["contentHash"])
    return sorted(hashes)


def _normal_kind(kind: str) -> str:
    return ENTITY_KINDS.get(kind, kind)


def validate_reviews(kind: str, document: Mapping[str, Any], resolver: ReferenceResolver,
                     policy: Mapping[str, Any]) -> list[PublicationIssue]:
    """Apply role/qualification/content-bound review policy without creating approvals."""
    subject_id = document.get("id", document.get("questionKey"))
    where = f"{kind}/{subject_id}"
    errors = []
    requirements = [requirement for requirement in policy["requirements"]
                    if _normal_kind(requirement["subjectKind"]) == kind]
    if not requirements:
        return [PublicationIssue("review", "missing_review_policy", where, "No requirements for this subject kind")]
    responsibilities = {requirement["responsibility"] for requirement in requirements}
    minimum = {"domain_content", "deterministic_contract"}
    if kind in {"question-revision", "mock-pool"}:
        minimum.add("assessment_answer")
    if kind == "lab":
        minimum.add("notebook_execution")
    if not minimum.issubset(responsibilities):
        return [PublicationIssue("review", "incomplete_review_policy", where,
                                 "Policy is missing required responsibilities: " + str(sorted(minimum - responsibilities)))]
    if kind == "lab" and not any(requirement["responsibility"] == "notebook_execution"
                                  and requirement["allowedReviewerRoles"] == ["human"]
                                  and "L5" in requirement["requiredCheckCodes"] for requirement in requirements):
        return [PublicationIssue("execution", "missing_human_colab_gate", where, "Lab policy requires a human L5 Colab smoke check")]
    expected = dependency_hashes(document, resolver)
    evidence_by_id = {}
    for (entry_kind, identity, _), payload in resolver.documents.items():
        if entry_kind == "evidence":
            evidence_by_id.setdefault(identity, []).append(payload)
    reviews_by_id = {identity: payload for (entry_kind, identity, _), payload in resolver.documents.items()
                     if entry_kind == "review"}
    provided = []
    invalid_reasons: dict[str, list[str]] = {}
    review_ids = document.get("reviewIds")
    if review_ids is None:
        review_ids = [identity for identity, review in reviews_by_id.items()
                      if _normal_kind(review["subject"]["kind"]) == kind and review["subject"]["id"] == subject_id]
    for review_id in review_ids:
        review = reviews_by_id.get(review_id)
        reasons = []
        if review is None:
            invalid_reasons[review_id] = ["missing review"]
            continue
        subject = review["subject"]
        if (_normal_kind(subject["kind"]), subject["id"], subject["revision"], subject["hash"]) != (
                kind, subject_id, document.get("revision", 1), document["contentHash"]):
            reasons.append("subject identity/revision/hash mismatch")
        if sorted(review["dependencyHashes"]) != expected:
            reasons.append("dependency fingerprints mismatch")
        if review["verdict"] != "approved":
            reasons.append("review is not approved")
        qualification = review["qualification"]
        if not qualification["grantedBy"] or qualification["grantedBy"] == review["reviewerId"]:
            reasons.append("qualification must be granted by a different maintainer")
        if not qualification["evidenceIds"]:
            reasons.append("qualification lacks evidence")
        refs = review["evidenceRefs"]
        if len({ref["id"] for ref in refs}) != len(refs):
            reasons.append("duplicate or conflicting evidence revisions")
        referenced_ids = {ref["id"] for ref in refs}
        required_ids = set(qualification["evidenceIds"]) | set(document.get("evidenceIds", []))
        for check in review["checks"]:
            required_ids.update(check["evidenceIds"])
        if not required_ids.issubset(referenced_ids):
            reasons.append("evidenceRefs do not cover all required evidence")
        for ref in refs:
            try:
                evidence = resolver.evidence(ref)
                if resolver.validate("evidence", evidence):
                    reasons.append("evidence source/artifact validation failed: " + ref["id"])
            except ReferenceError as exc:
                reasons.append(str(exc))
        if reasons:
            invalid_reasons[review_id] = reasons
        else:
            provided.append(review)
    for requirement in requirements:
        matching = []
        for review in provided:
            if review["responsibility"] != requirement["responsibility"]:
                continue
            if review["reviewerRole"] not in requirement["allowedReviewerRoles"]:
                continue
            if requirement["qualificationScope"] not in review["qualification"]["scope"]:
                continue
            if review["rubricVersion"] != requirement["rubricVersion"]:
                continue
            if requirement["independentFromAuthor"] and review["reviewerId"] == review["authorId"]:
                continue
            checks = {check["code"]: check for check in review["checks"]}
            if len(checks) != len(review["checks"]):
                continue
            required_codes = requirement["requiredCheckCodes"]
            if not required_codes or any(code not in checks or checks[code]["verdict"] != "pass"
                                         or not checks[code]["evidenceIds"] for code in required_codes):
                continue
            matching.append(review)
        if not matching:
            stage = "execution" if requirement["responsibility"] == "notebook_execution" else "review"
            message = (f"Missing valid {requirement['responsibility']} review with checks "
                       f"{requirement['requiredCheckCodes']}; invalid reviews: {invalid_reasons}")
            errors.append(PublicationIssue(stage, "missing_valid_review", where, message))
    return errors


def validate_candidate(candidate: Candidate, *, preview: bool = False) -> tuple[list[PublicationIssue], list[PublicationIssue]]:
    issues = list(candidate.issues)
    review_issues: list[PublicationIssue] = []
    resolver = candidate.resolver
    entities = [(key, document) for key, document in candidate.documents.items() if key[0] in PUBLIC_KINDS]
    if not entities:
        issues.append(PublicationIssue("references", "empty_bundle", "content/learning", "No publishable learning entities were supplied"))
    active_ids = set()
    for key, document in candidate.documents.items():
        kind, identity, _ = key
        for error in resolver.validate(kind, document):
            issues.append(PublicationIssue("references", error.code, candidate.source_paths[key] + error.path, error.message))
        if kind in PUBLIC_KINDS:
            if (kind, identity) in active_ids:
                issues.append(PublicationIssue("references", "multiple_active_revisions", identity, "Complete candidate must select one revision per entity"))
            active_ids.add((kind, identity))
            if "status" in document and document["status"] not in {"in_review", "published"}:
                issues.append(PublicationIssue("references", "invalid_candidate_state", identity, "Candidate requires in_review/published source; draft and retired are excluded"))
    unit_graph = {identity: [entry["ref"] for entry in document["prerequisites"] if entry["kind"] == "unit"]
                  for (kind, identity, _), document in entities if kind == "learning-unit"}
    issues.extend(PublicationIssue("references", code, "content/learning/units", message)
                  for code, message in graph_errors(unit_graph))
    try:
        policy = resolver.read_json("content/learning/review-policy.json")
        policy_errors = validate_document("review-policy", policy)
        if policy_errors:
            issues.extend(PublicationIssue("schema", error.code, "content/learning/review-policy.json" + error.path, error.message)
                          for error in policy_errors)
        elif not issues:
            for (kind, _, _), document in entities:
                review_issues.extend(validate_reviews(kind, document, resolver, policy))
            for (kind, _, _), document in candidate.documents.items():
                if kind != "question-revision":
                    continue
                findings = validate_reviews(kind, document, resolver, policy)
                if preview and document["answerStatus"] == "verified" and findings:
                    issues.extend(findings)
                else:
                    review_issues.extend(findings)
    except ReferenceError as exc:
        # Preview still reports the missing policy rather than inventing a pass.
        review_issues.append(PublicationIssue("review", exc.code, "content/learning/review-policy.json", str(exc)))
        if preview and any(kind == "question-revision" and document.get("answerStatus") == "verified"
                           for (kind, _, _), document in candidate.documents.items()):
            issues.append(PublicationIssue("review", "unverified_answer_promotion", "content/learning/review-policy.json",
                                            "Verified answers require a valid review policy even in preview"))
    if not preview:
        issues.extend(review_issues)
    return issues, review_issues


def _json_bytes(value: Any) -> bytes:
    return canonical_json_bytes(value) + b"\n"


def derive_lab_asset_bytes(candidate: Candidate) -> dict[str, bytes]:
    """Derive release bytes from committed sources without a kernel or optional deps.

    This is serialization, not nbformat/execution/semantic approval. The source
    was checked by the authoring validator; every variant must still match the
    exact artifact hash recorded in Lab metadata before it can enter a bundle.
    """
    output = {}
    resolver = candidate.resolver
    for (kind, identity, revision), lab in candidate.documents.items():
        if kind != "lab":
            continue
        source = resolver.read_json(lab["sourceNotebookRef"])
        if source.get("nbformat") != 4 or not isinstance(source.get("cells"), list):
            raise ReferenceError("unsupported_notebook_serialization", lab["sourceNotebookRef"])
        prefix = f"frontend/public/labs/{identity}/{revision}/"
        for artifact in lab["artifacts"]:
            variant = artifact["variant"]
            notebook = copy.deepcopy(source)
            kept = []
            for cell in notebook["cells"]:
                learning = cell["metadata"]["learning"]
                if variant == "starter" and learning["audience"] == "solution":
                    continue
                if variant == "starter" and "starterSource" in learning:
                    cell["source"] = learning.pop("starterSource").splitlines(True)
                else:
                    learning.pop("starterSource", None)
                if cell["cell_type"] == "code":
                    cell["outputs"], cell["execution_count"] = [], None
                kept.append(cell)
            notebook["cells"] = kept
            data = (json.dumps(notebook, ensure_ascii=False, sort_keys=True, indent=1, separators=(",", ": ")) + "\n").encode()
            if blob_hash(data) != artifact["hash"] or len(data) != artifact["size"]:
                raise ReferenceError("lab_derivation_drift", "Re-run the versioned lab generator/review; serialization differs: " + artifact["path"])
            output[artifact["path"]] = data
        for dataset in lab["datasets"]:
            resource = resolver.resource(dataset["resource"])
            fixture = resource["fixtureRef"]
            output[prefix + Path(fixture).name] = resolver.read_bytes(fixture)
            # Split membership is a teaching-specific asset, not source provenance.
            split = str(Path(fixture).with_name("split_manifest_v1.json"))
            if (resolver.root / split).exists():
                output[prefix + "split_manifest_v1.json"] = resolver.read_bytes(split)
        output[prefix + "uv.lock"] = resolver.read_bytes(lab["environment"]["lockRef"])
    return output


def prepare_bundle(candidate: Candidate, *, preview: bool, review_issues: list[PublicationIssue],
                   asset_bytes: Mapping[str, bytes] | None = None,
                   additional_artifacts: Mapping[str, Mapping[str, Any]] | None = None) -> tuple[str, dict[str, bytes], dict[str, bytes]]:
    """Prepare all release bytes and required versioned assets before any mutation."""
    resolver = candidate.resolver
    availability = "preview" if preview else "published"
    selected = sorted((key, document) for key, document in candidate.documents.items() if key[0] in PUBLIC_KINDS)
    identity_preimage = {"exporterVersion": EXPORTER_VERSION, "availability": availability,
                        "inputHashes": resolver.input_hashes,
                        "documents": [{"kind": key[0], "payload": document} for key, document in sorted(candidate.documents.items())],
                        "artifacts": additional_artifacts or {}}
    release_id = "learning-" + value_hash(identity_preimage).removeprefix("sha256:")[:24]
    files: dict[str, bytes] = {}
    assets: dict[str, bytes] = {}
    index: dict[str, Any] = {"schemaVersion": 1, "releaseId": release_id, "availability": availability,
                             **{directory: [] for directory in PUBLIC_KINDS.values()}, "assemblies": []}
    entities = []
    for (kind, identity, revision), document in selected:
        directory = PUBLIC_KINDS[kind]
        path = f"{directory}/{identity}.json"
        safe_path(Path("/"), path)
        runtime_document = copy.deepcopy(document)
        if kind in {"mock-pool", "exam-analysis"}:
            runtime_document["releaseId"] = release_id
        elif kind == "mock-blueprint":
            runtime_document["poolRef"]["releaseId"] = release_id
        item = {"releaseId": release_id, "availability": availability, "kind": kind, "document": runtime_document}
        if kind == "learning-unit":
            item["bodyMarkdown"] = resolver.body_bytes(document).decode("utf-8")
        meta = {"id": identity, "revision": revision, "title": document.get("title", identity),
                "chapterRefs": document.get("chapterRefs", []), "path": path}
        if "summary" in document:
            meta["summary"] = document["summary"]
        index[directory].append(meta)
        entities.append({"kind": kind, "id": identity, "revision": revision,
                         "contentHash": document["contentHash"], "path": path})
        if kind == "lab":
            item["assetLocations"] = []
            item["supportAssets"] = []
            if not preview and {artifact["variant"] for artifact in document["artifacts"]} != {"starter", "solution"}:
                raise ReferenceError("missing_lab_variants", "Published lab requires both versioned notebook variants")
            for artifact in document["artifacts"]:
                target = artifact["path"]
                prefix = f"frontend/public/labs/{identity}/{revision}/"
                if not target.startswith(prefix) or artifact["revision"] != revision:
                    raise ReferenceError("unsafe_lab_artifact", "Lab output must use its immutable ID/revision directory")
                data = asset_bytes[target] if asset_bytes and target in asset_bytes else resolver.read_bytes(target)
                if blob_hash(data) != artifact["hash"] or len(data) != artifact["size"]:
                    raise ReferenceError("lab_artifact_mismatch", "Lab artifact bytes do not match metadata")
                if preview:
                    relative = "assets/" + target.removeprefix("frontend/public/")
                    files[relative] = data
                    location = relative
                else:
                    assets[target] = data
                    location = "/" + target.removeprefix("frontend/public/")
                item["assetLocations"].append({"variant": artifact["variant"], "path": location,
                                                "hash": artifact["hash"], "size": artifact["size"]})
            variant_paths = {artifact["path"] for artifact in document["artifacts"]}
            prefix = f"frontend/public/labs/{identity}/{revision}/"
            for target, data in sorted((asset_bytes or {}).items()):
                if target in variant_paths or not target.startswith(prefix):
                    continue
                safe_path(resolver.root, target)
                name = target.removeprefix(prefix)
                if "/" in name or name not in {"equipment_alerts_v1.csv", "split_manifest_v1.json", "uv.lock"}:
                    raise ReferenceError("unsupported_lab_support_asset", "Unknown support file must be explicitly specified: " + target)
                location = "assets/" + target.removeprefix("frontend/public/") if preview else "/" + target.removeprefix("frontend/public/")
                if preview:
                    files[location] = data
                else:
                    assets[target] = data
                label = {"equipment_alerts_v1.csv": "下載資料", "split_manifest_v1.json": "下載切分清單", "uv.lock": "下載環境鎖定檔"}[name]
                item["supportAssets"].append({"label": label, "path": location, "hash": blob_hash(data), "size": len(data)})
        files[path] = _json_bytes(item)
    question_index = []
    for (kind, identity, revision), document in sorted(candidate.documents.items()):
        if kind != "question-revision":
            continue
        # File names do not use raw qids; canonical IDs stay inside each payload.
        path = question_payload_path(identity, revision)
        files[path] = question_payload_bytes(document)
        question_index.append({"questionKey": identity, "revision": revision, "contentHash": document["contentHash"], "path": path})
    files["question-index.json"] = _json_bytes({"releaseId": release_id, "questions": question_index})
    _prepare_assessment_artifacts(candidate, additional_artifacts or {}, files, index, release_id, availability)
    files["index.json"] = _json_bytes(index)
    # The manifest's file list can audit this release-local map of public assets.
    files["asset-index.json"] = _json_bytes({"assets": [{"path": path, "hash": blob_hash(data), "size": len(data)}
                                                        for path, data in sorted(assets.items())]})
    # Exact source-bound review evidence is included for fresh-checkout auditing.
    audit = {"reviews": [document for (kind, _, _), document in sorted(candidate.documents.items()) if kind == "review"],
             "evidence": [document for (kind, _, _), document in sorted(candidate.documents.items()) if kind == "evidence"]}
    files["review-summary.json"] = _json_bytes(audit)
    gates = [{"stage": stage, "status": "not_run" if stage == "commit" or preview and stage in {"review", "execution"} else "passed",
              "evidenceIds": []} for stage in STAGES]
    manifest = {"schemaVersion": 1, "releaseId": release_id, "availability": availability,
                "exporterVersion": EXPORTER_VERSION, "inputHashes": dict(sorted(resolver.input_hashes.items())),
                "entities": entities,
                "files": [{"path": path, "hash": blob_hash(data), "size": len(data)} for path, data in sorted(files.items())],
                "gates": gates}
    validation = validate_document("release-manifest", manifest)
    if validation:
        raise ReferenceError("invalid_release_manifest", "; ".join(error.message for error in validation))
    files["manifest.json"] = _json_bytes(manifest)
    return release_id, files, assets


def _prepare_assessment_artifacts(candidate, supplied, files, index, release_id, availability):
    """Only validated frozen annotations and recomputable assembly results are accepted."""
    from .assessment import assemble_mock_exam
    annotations_by_pool = {}
    for path, payload in supplied.items():
        safe_path(candidate.resolver.root, path)
        if path.startswith("annotations/") and path.endswith(".json"):
            pool_id = path.removeprefix("annotations/").removesuffix(".json")
            pool = candidate.documents.get(("mock-pool", pool_id, 1))
            if pool is None or value_hash(payload.get("annotations")) != pool["annotationSnapshotHash"]:
                raise ReferenceError("stale_annotations", "Frozen annotation snapshot must bind its pool")
            for identity in payload.get("identities", {}).values():
                errors = candidate.resolver.validate("question-identity", identity)
                if errors:
                    raise ReferenceError("invalid_annotation_identity", str(errors))
            annotations_by_pool[pool_id] = payload
            files[path] = _json_bytes({"releaseId": release_id, "availability": availability,
                                       "kind": "annotation-snapshot", **payload})
        elif path.startswith("analysis-examples/") and path.endswith(".json"):
            identity = path.removeprefix("analysis-examples/").removesuffix(".json")
            target = f"analysis/{identity}.json"
            if target not in files:
                raise ReferenceError("missing_analysis", identity)
            for example in payload.get("examples", []):
                question = candidate.resolver.question(example["question"])
                raw = candidate.resolver.legacy_question(question["questionKey"])
                source = example["source"]
                if (example["stem"] != raw["question"] or source["pageIndex"] != raw["source_ref"]["page_index"]
                        or source["pageNumber"] != source["pageIndex"] + 1
                        or source["route"] != "/exam/" + source["examKey"]
                        or example["questionPath"] != question_payload_path(question["questionKey"], question["revision"])
                        or not any(kind == "learning-unit" and unit_id == example["unitId"] for kind, unit_id, _ in candidate.documents)):
                    raise ReferenceError("invalid_source_example", question["questionKey"])
            wrapper = json.loads(files[target])
            wrapper["sourceExamples"] = payload["examples"]
            files[target] = _json_bytes(wrapper)
        elif not (path.startswith("assemblies/") and path.endswith(".json")):
            raise ReferenceError("unsupported_additional_artifact", path)
    for path, payload in supplied.items():
        if not path.startswith("assemblies/"):
            continue
        blueprint_id = path.removeprefix("assemblies/").removesuffix(".json")
        blueprint = next((doc for (kind, identity, _), doc in candidate.documents.items()
                          if kind == "mock-blueprint" and identity == blueprint_id), None)
        result = payload.get("document", {})
        if blueprint is None or validate_document("assembly-result", result) or result.get("status") != "ready":
            raise ReferenceError("invalid_assembly", "A ready assembly for the candidate blueprint is required")
        pool_id = blueprint["poolRef"]["id"]
        pool = candidate.documents[("mock-pool", pool_id, 1)]
        frozen = annotations_by_pool.get(pool_id)
        if frozen is None:
            raise ReferenceError("missing_annotations", pool_id)
        questions = {(identity, revision): doc for (kind, identity, revision), doc in candidate.documents.items() if kind == "question-revision"}
        expected = assemble_mock_exam(blueprint, pool, questions=questions, identities=frozen["identities"],
                                      annotations=frozen["annotations"], seed=result["seed"])
        if result != expected:
            raise ReferenceError("assembly_mismatch", "Supplied form does not reproduce from exact frozen inputs")
        runtime_result = copy.deepcopy(result)
        runtime_result["poolRef"]["releaseId"] = release_id
        question_paths = {ref["questionKey"]: question_payload_path(ref["questionKey"], ref["revision"])
                          for ref in result["selectedQuestionRevisions"]}
        files[path] = _json_bytes({"releaseId": release_id, "availability": availability, "kind": "assembly-result",
                                   "document": runtime_result, "questionPaths": question_paths})
        index["assemblies"].append({"id": blueprint_id, "revision": blueprint["revision"], "title": blueprint["title"], "chapterRefs": [], "path": path})


def _write_immutable(path: Path, data: bytes) -> None:
    """Create once; identical retry is valid, conflicting bytes never overwrite."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".immutable-", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.read_bytes() != data:
                raise ReferenceError("immutable_conflict", f"Existing immutable artifact differs: {path.name}")
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _atomic_pointer(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".pointer-", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def build_learning_content(repo_root: Path | str, *, preview: bool = False, check: bool = False,
                           dry_run: bool = False, assessment_at: str | None = None,
                           before_pointer: Callable[[], None] | None = None,
                           additional_documents: Mapping[tuple[str, str, int], Mapping[str, Any]] | None = None,
                           asset_bytes: Mapping[str, bytes] | None = None,
                           additional_artifacts: Mapping[str, Mapping[str, Any]] | None = None,
                           lab_assets_manifest: str | None = None,
                           additional_inputs: Mapping[str, str] | None = None) -> dict[str, Any]:
    """No network/LLMs. Check and dry-run never mutate any repository file."""
    candidate = load_candidate(repo_root, assessment_at=assessment_at, additional_documents=additional_documents)
    try:
        for path, digest in (additional_inputs or {}).items():
            if blob_hash(candidate.resolver.read_bytes(path)) != digest:
                raise ReferenceError("stale_adapter_input", path)
        if lab_assets_manifest and safe_path(candidate.resolver.root, lab_assets_manifest).exists():
            manifest = candidate.resolver.read_json(lab_assets_manifest)
            resolved_assets = dict(asset_bytes or {})
            lab = candidate.documents.get(("lab", manifest["labId"], manifest["revision"]))
            if lab is None:
                raise ReferenceError("unknown_lab_asset_manifest", "Asset manifest has no matching candidate Lab")
            for entry in manifest["assets"]:
                data = candidate.resolver.read_bytes(entry["sourcePath"])
                if blob_hash(data) != entry["hash"] or len(data) != entry["bytes"]:
                    raise ReferenceError("lab_support_hash_mismatch", entry["sourcePath"])
                if not entry["finalPath"].startswith(f"frontend/public/labs/{lab['id']}/{lab['revision']}/"):
                    raise ReferenceError("unsafe_lab_asset", entry["finalPath"])
                resolved_assets[entry["finalPath"]] = data
            asset_bytes = resolved_assets
        elif lab_assets_manifest is not None:
            asset_bytes = {**derive_lab_asset_bytes(candidate), **dict(asset_bytes or {})}
    except (ReferenceError, KeyError, TypeError, ValueError) as exc:
        candidate.issues.append(PublicationIssue("references", getattr(exc, "code", "invalid_asset_manifest"), "", str(exc)))
    issues, review_issues = validate_candidate(candidate, preview=preview)
    report: dict[str, Any] = {"status": "blocked" if issues else "checked", "availability": "preview" if preview else "published",
                              "entities": len([key for key in candidate.documents if key[0] in PUBLIC_KINDS]),
                              "issues": [asdict(issue) for issue in issues],
                              "unmetReviews": [asdict(issue) for issue in review_issues],
                              "wrotePointer": False}
    if issues:
        return report
    try:
        release_id, files, assets = prepare_bundle(candidate, preview=preview, review_issues=review_issues,
                                                  asset_bytes=asset_bytes, additional_artifacts=additional_artifacts)
        report["releaseId"] = release_id
        root = candidate.resolver.root
        subtree = "previews" if preview else "releases"
        base = safe_path(root, LEARNING_ROOT)
        destination = base / subtree / release_id
        pointer_name = "preview.json" if preview else "current.json"
        pointer = {"schemaVersion": 1, "availability": report["availability"], "releaseId": release_id,
                   "manifestPath": f"{subtree}/{release_id}/manifest.json"}
        for path, data in assets.items():
            existing = safe_path(root, path)
            if existing.exists() and existing.read_bytes() != data:
                raise ReferenceError("immutable_conflict", "Versioned lab asset already has different bytes")
        for path, data in files.items():
            existing = safe_path(destination, path)
            if existing.exists() and existing.read_bytes() != data:
                raise ReferenceError("immutable_conflict", "Versioned release already has different bytes")
        if check or dry_run:
            report["status"] = "dry_run" if dry_run else "checked"
            return report
        # Assets first. A failure can leave orphan immutable files, never a mixed active release.
        for path, data in sorted(assets.items()):
            _write_immutable(safe_path(root, path), data)
        for path, data in sorted(files.items()):
            _write_immutable(safe_path(destination, path), data)
        for path, data in files.items():
            if safe_path(destination, path).read_bytes() != data:
                raise ReferenceError("release_integrity_error", "Release changed while preparing activation")
        if before_pointer is not None:
            before_pointer()
        # Recheck all source bytes immediately before the only mutable pointer commit.
        for path, digest in candidate.resolver.input_hashes.items():
            if blob_hash(safe_path(root, path).read_bytes()) != digest:
                raise ReferenceError("source_changed_during_build", "Source changed during build: " + path)
        _atomic_pointer(base / pointer_name, _json_bytes(pointer))
        report.update(status="preview_ready" if preview else "published", wrotePointer=True)
    except (ReferenceError, OSError, UnicodeDecodeError) as exc:
        report["status"] = "blocked"
        report["issues"].append(asdict(PublicationIssue("commit", getattr(exc, "code", "write_failed"), "", str(exc))))
    return report
