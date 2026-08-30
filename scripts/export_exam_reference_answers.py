#!/usr/bin/env python3
"""Export Codex exam reference answers for the frontend."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from resource_catalog import exam_entries
from run_codex_exam_reference_answers import (
    current_question_fingerprint_index,
    output_question_fingerprint,
    question_content_fingerprint,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "frontend/src/generated/examReferenceAnswers"
OVERLAY_PATH = ROOT / "data/exam_reference_answer_overlays.json"
OVERLAY_SCHEMA_VERSION = 2
STATS_KEYS = {
    "初級": "elementary",
    "中級": "middle",
}
KEEP_FIELDS = [
    "answer",
    "reference_answer",
    "option_analysis",
    "key_concepts",
    "citations",
    "confidence",
    "notes",
]


def question_fingerprint_index(
    questions: list[dict[str, Any]],
    *,
    label: str,
) -> tuple[
    dict[str, dict[str, Any] | None],
    dict[str, dict[str, Any]],
]:
    """Index v2 plus migratable legacy identities and canonical ids."""
    by_id: dict[str, dict[str, Any]] = {}
    for question in questions:
        question_id = str(question.get('id') or '')
        if not question_id or question_id in by_id:
            raise ValueError(f'Duplicate or missing question id in {label}: {question_id!r}')
        by_id[question_id] = question
    by_fingerprint = current_question_fingerprint_index(questions, label=label)
    return by_fingerprint, by_id


def canonical_question_for_output(
    output_path: Path,
    prompt_path: Path,
    questions_by_fingerprint: dict[str, dict[str, Any] | None],
    *,
    label: str,
) -> dict[str, Any]:
    """Resolve legacy or current output by its generation-time question content."""
    fingerprint = output_question_fingerprint(output_path, prompt_path)
    if fingerprint is None:
        raise ValueError(
            f'Missing trusted question-content provenance for {label}/{output_path.name}; '
            'rerun the producer with --run (or --force)'
        )
    if fingerprint not in questions_by_fingerprint:
        raise ValueError(
            f'Reference answer no longer matches any current question: '
            f'{label}/{output_path.name}'
        )
    question = questions_by_fingerprint[fingerprint]
    if question is None:
        raise ValueError(
            f'Legacy reference-answer identity is ambiguous after content repair: '
            f'{label}/{output_path.name}; rerun this complete paper'
        )
    return question


def load_overlays() -> dict[str, dict[str, dict[str, Any]]]:
    if not OVERLAY_PATH.exists():
        return {}
    payload = load_json(OVERLAY_PATH)
    if (
        payload.get('schemaVersion') != OVERLAY_SCHEMA_VERSION
        or not isinstance(payload.get('exams'), dict)
    ):
        raise ValueError(f'Invalid reference-answer overlay schema: {OVERLAY_PATH}')
    return payload['exams']


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def question_sort_key(path: Path) -> tuple[str, int, str]:
    stem = path.stem
    prefix, _, number = stem.rpartition("_q")
    try:
        return prefix, int(number), stem
    except ValueError:
        return prefix, 0, stem


def exported_question_id(raw_question_id: str, canonical_question_id: str) -> str:
    """Preserve stable legacy prefixes unless content actually moved position."""
    _, raw_separator, raw_number = raw_question_id.rpartition('_q')
    _, canonical_separator, canonical_number = canonical_question_id.rpartition('_q')
    if (
        raw_separator
        and canonical_separator
        and raw_number.isdigit()
        and canonical_number.isdigit()
        and int(raw_number) == int(canonical_number)
    ):
        return raw_question_id
    return canonical_question_id


def compact_answer(raw: dict[str, Any]) -> dict[str, Any]:
    return {field: raw[field] for field in KEEP_FIELDS if field in raw}


def export_reference_answers(level: str, output_path: Path) -> dict[str, Any]:
    run_root = ROOT / f"data/{level}/pipeline/exam_reference_answers"
    if not run_root.exists():
        raise SystemExit(f"Reference answer directory does not exist: {run_root}")

    try:
        catalog_exams = {
            exam["key"]: exam
            for exam in exam_entries(level=level)
        }
    except KeyError:
        raise SystemExit(f"Unsupported level: {level}")

    exams: dict[str, dict[str, Any]] = {}
    stats: dict[str, int] = {}
    overlays = load_overlays()
    for source_key, exam_config in catalog_exams.items():
        route_key = exam_config['routeKey']
        outputs_dir = run_root / source_key / "outputs"
        if not outputs_dir.exists():
            continue

        question_path = ROOT / 'data' / level / 'questions' / exam_config['questionFile']
        question_payload = load_json(question_path)
        questions_by_fingerprint, questions_by_id = question_fingerprint_index(
            question_payload.get('questions') or [],
            label=f'{level}/{source_key}',
        )

        answers: dict[str, Any] = {}
        candidates_by_question_id: dict[str, list[dict[str, Any]]] = {}
        for path in sorted(outputs_dir.glob("*.json"), key=question_sort_key):
            raw = load_json(path)
            raw_question_id = str(raw.get('question_id') or path.stem)
            if raw_question_id != path.stem:
                raise ValueError(
                    f'Reference-answer filename/id mismatch: '
                    f'{level}/{source_key}/{path.name} != {raw_question_id}'
                )
            if raw.get('level') != level:
                raise ValueError(
                    f'Reference-answer source mismatch: {level}/{source_key}/{path.name}'
                )
            prompt_path = outputs_dir.parent / 'prompts' / f'{path.stem}.md'
            question = canonical_question_for_output(
                path,
                prompt_path,
                questions_by_fingerprint,
                label=f'{level}/{source_key}',
            )
            canonical_question_id = str(question['id'])
            allowed_exam_keys = {
                source_key,
                str(exam_config.get('legacyReferencePrefix') or source_key),
            }
            if raw.get('exam_key') not in allowed_exam_keys:
                raise ValueError(
                    f'Reference-answer exam key mismatch: '
                    f'{level}/{source_key}/{path.name}'
                )
            if raw.get('answer') != question.get('answer'):
                raise ValueError(
                    f'Reference-answer official answer mismatch: '
                    f'{level}/{source_key}/{path.name}'
                )
            candidates_by_question_id.setdefault(canonical_question_id, []).append({
                'path': path,
                'raw_question_id': raw_question_id,
                'canonical_question_id': canonical_question_id,
                'is_canonical': raw_question_id == canonical_question_id,
                'answer': raw.get('answer'),
                'question_fingerprint': question_content_fingerprint(question),
                'compact_answer': compact_answer(raw),
            })

        replaced_legacy = 0
        for canonical_question_id, candidates in candidates_by_question_id.items():
            canonical_candidates = [item for item in candidates if item['is_canonical']]
            if len(candidates) == 1:
                chosen = candidates[0]
            elif len(canonical_candidates) == 1:
                chosen = canonical_candidates[0]
                fingerprints = {item['question_fingerprint'] for item in candidates}
                answers_seen = {item['answer'] for item in candidates}
                if len(fingerprints) != 1 or len(answers_seen) != 1:
                    raise ValueError(
                        f'Legacy/canonical reference-answer conflict: '
                        f'{level}/{source_key}/{canonical_question_id}'
                    )
                replaced_legacy += len(candidates) - 1
            else:
                paths = ', '.join(item['path'].name for item in candidates)
                raise ValueError(
                    f'Duplicate reference answers without one canonical winner: '
                    f'{level}/{source_key}/{canonical_question_id}: {paths}'
                )

            question_id = exported_question_id(
                chosen['raw_question_id'], canonical_question_id
            )
            if question_id in answers:
                raise ValueError(
                    f'Duplicate exported reference answer: {level}/{source_key}/{question_id}'
                )
            answers[question_id] = chosen['compact_answer']

        resolved_question_ids = set(candidates_by_question_id)
        published_question_ids = set(resolved_question_ids)
        if replaced_legacy:
            print(
                f'INFO {level}/{source_key}: canonical outputs replaced '
                f'{replaced_legacy} legacy duplicate(s)'
            )

        for question_id, raw in overlays.get(f'{level}/{source_key}', {}).items():
            question = questions_by_id.get(question_id)
            if question is None:
                raise ValueError(
                    f'Reference-answer overlay targets a missing question: '
                    f'{level}/{source_key}/{question_id}'
                )
            expected_fingerprint = question_content_fingerprint(question)
            if raw.get('questionFingerprint') != expected_fingerprint:
                raise ValueError(
                    f'Reference-answer overlay content fingerprint mismatch: '
                    f'{level}/{source_key}/{question_id}'
                )
            if raw.get('answer') != question.get('answer'):
                raise ValueError(
                    f'Reference-answer overlay answer mismatch: '
                    f'{level}/{source_key}/{question_id}'
                )
            if question_id in resolved_question_ids:
                # A complete canonical rerun supersedes the temporary repair overlay.
                continue
            answers[question_id] = compact_answer(raw)
            published_question_ids.add(question_id)

        expected_question_ids = set(questions_by_id)
        if published_question_ids != expected_question_ids:
            missing = sorted(
                expected_question_ids - published_question_ids,
                key=lambda item: question_sort_key(Path(item)),
            )
            extra = sorted(published_question_ids - expected_question_ids)
            raise ValueError(
                f'Incomplete reference-answer publication for {level}/{source_key}: '
                f'published={len(published_question_ids)}, '
                f'production={len(expected_question_ids)}, missing={missing}, extra={extra}'
            )
        if len(answers) != len(expected_question_ids):
            raise ValueError(
                f'Reference-answer key collision for {level}/{source_key}: '
                f'answers={len(answers)}, production={len(expected_question_ids)}'
            )

        exams[route_key] = dict(
            sorted(answers.items(), key=lambda item: question_sort_key(Path(item[0])))
        )
        stats[route_key] = len(answers)

    output_path.mkdir(parents=True, exist_ok=True)
    for route_key, answers in exams.items():
        (output_path / f"{route_key}.json").write_text(
            json.dumps(answers, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    stats_path = output_path / "stats.json"
    payload = load_json(stats_path) if stats_path.exists() else {}
    payload[STATS_KEYS[level]] = stats
    (output_path / "stats.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--level", default="中級")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    output_path = args.output
    if not output_path.is_absolute():
        output_path = ROOT / output_path
    payload = export_reference_answers(args.level, output_path)
    total = sum(payload[STATS_KEYS[args.level]].values())
    print(f"Exported {total} reference answers to {output_path}")


if __name__ == "__main__":
    main()
