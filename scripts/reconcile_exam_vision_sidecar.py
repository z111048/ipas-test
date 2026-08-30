#!/usr/bin/env python3
# 2026-08-30: 樣題補題後同步 production 分母為 14 卷／715 題；coverage 仍為診斷 sidecar。
"""Build a verified overlay for the review-only exam Vision sidecar.

Raw ``exam_pages_cache`` files are immutable OCR evidence and are never edited.
For every cached question this script preserves the Vision candidates, then
overlays the question, options, and official answer from the production JSON
that was checked against the PDF. The resulting file is the only safe input for
a future sidecar-promotion experiment.

``--promotion-gate`` additionally requires cache coverage for every catalogued
production question. It intentionally fails while coverage is incomplete: a
fresh checkout has 0/715 because ``exam_pages_cache`` is gitignored, while the
2026-08-30 maintainer snapshot covers three 115-year middle-level exams
(150/715), which is diagnostic only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

from resource_catalog import exam_entries, level_entry


ROOT = Path(__file__).resolve().parents[1]
FIELD_NAMES = ('question', 'option_A', 'option_B', 'option_C', 'option_D', 'answer')


def normalize(value: Any) -> str:
    """Normalize layout-only differences while preserving semantic symbols."""
    text = unicodedata.normalize('NFKC', str(value or '')).lower()
    return re.sub(r'[\s\u3000；;，,。．:：()（）「」『』\-—_]+', '', text)


def load_production_questions(entry: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    level = level_entry(level_id=entry['levelId'])['dataLevel']
    path = ROOT / 'data' / level / 'questions' / entry['questionFile']
    payload = json.loads(path.read_text(encoding='utf-8'))
    questions = payload.get('questions')
    if not isinstance(questions, list):
        raise ValueError(f'{path}: questions must be an array')
    expected = int(entry['expectedQuestions'])
    if len(questions) != expected:
        raise ValueError(f'{path}: {len(questions)} questions; catalog expects {expected}')
    return level, questions


def load_raw_candidates(
    level: str,
    exam_key: str,
) -> tuple[dict[int, list[dict[str, Any]]], dict[int, list[dict[str, Any]]], list[str]]:
    cache_dir = ROOT / 'data' / level / 'exam_pages_cache' / exam_key
    questions: dict[int, list[dict[str, Any]]] = defaultdict(list)
    answers: dict[int, list[dict[str, Any]]] = defaultdict(list)
    cache_files: list[str] = []
    if not cache_dir.exists():
        return questions, answers, cache_files

    for path in sorted(cache_dir.glob('page_*.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        page_index = int(data.get('idx', int(path.stem.rsplit('_', 1)[-1])))
        cache_files.append(str(path.relative_to(ROOT)))
        for raw in data.get('questions') or []:
            number = raw.get('number')
            if isinstance(number, int):
                questions[number].append({'page_index': page_index, 'value': raw})
        for raw in data.get('answers') or []:
            number = raw.get('number')
            answer = raw.get('answer')
            if isinstance(number, int) and answer:
                answers[number].append({'page_index': page_index, 'value': str(answer)})
    return questions, answers, cache_files


def merge_question_candidates(
    candidates: list[dict[str, Any]],
    answer_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Merge split-page OCR candidates without discarding the raw variants."""
    ordered = sorted(candidates, key=lambda item: item['page_index'])
    question_parts: list[str] = []
    options: dict[str, str] = {}
    answer_candidates: list[str] = []

    for item in ordered:
        raw = item['value']
        text = str(raw.get('question') or '').strip()
        normalized = normalize(text)
        if normalized:
            # Prefer a longer candidate when one fully contains another;
            # otherwise retain both page fragments in page order.
            replaced = False
            for index, existing in enumerate(question_parts):
                existing_normalized = normalize(existing)
                if normalized in existing_normalized:
                    replaced = True
                    break
                if existing_normalized in normalized:
                    question_parts[index] = text
                    replaced = True
                    break
            if not replaced:
                question_parts.append(text)
        for key, value in (raw.get('options') or {}).items():
            if key not in {'A', 'B', 'C', 'D'} or value is None:
                continue
            candidate = str(value).strip()
            if len(normalize(candidate)) > len(normalize(options.get(key, ''))):
                options[key] = candidate
        raw_answer = raw.get('answer')
        if raw_answer and str(raw_answer) not in answer_candidates:
            answer_candidates.append(str(raw_answer))

    for row in sorted(answer_rows, key=lambda item: item['page_index']):
        answer = row['value']
        if answer not in answer_candidates:
            answer_candidates.append(answer)

    return {
        'question': ' '.join(question_parts).strip(),
        'options': options,
        'answer_candidates': answer_candidates,
        'cache_pages': sorted({item['page_index'] + 1 for item in ordered + answer_rows}),
        'raw_candidates': ordered,
        'raw_answer_rows': sorted(answer_rows, key=lambda item: item['page_index']),
    }


def mismatch_fields(verified: dict[str, Any], vision: dict[str, Any]) -> list[str]:
    mismatches: list[str] = []
    if normalize(verified['question']) != normalize(vision['question']):
        mismatches.append('question')
    for key in 'ABCD':
        if normalize(verified['options'].get(key)) != normalize(vision['options'].get(key)):
            mismatches.append(f'option_{key}')
    answers = vision['answer_candidates']
    if not answers or any(answer != verified['answer'] for answer in answers):
        mismatches.append('answer')
    return mismatches


def build_overlay(selected_entries: list[dict[str, Any]]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    missing: list[str] = []
    unexpected_cache_numbers: list[str] = []
    raw_diff_fields = 0
    production_questions = 0
    cached_questions = 0
    cache_files = 0

    for entry in selected_entries:
        level, questions = load_production_questions(entry)
        production_questions += len(questions)
        raw_by_number, answers_by_number, files = load_raw_candidates(level, entry['key'])
        cache_files += len(files)
        expected_numbers = set(range(1, len(questions) + 1))
        for number in sorted(set(raw_by_number) - expected_numbers):
            unexpected_cache_numbers.append(f'{level}/{entry["key"]}_q{number}')

        for number, production in enumerate(questions, 1):
            candidates = raw_by_number.get(number, [])
            if not candidates:
                missing.append(f'{level}/{entry["key"]}/{production["id"]}')
                continue
            cached_questions += 1
            vision = merge_question_candidates(candidates, answers_by_number.get(number, []))
            verified = {
                'question': production['question'],
                'options': {key: production['options'][key] for key in 'ABCD'},
                'answer': production['answer'],
            }
            mismatches = mismatch_fields(verified, vision)
            raw_diff_fields += len(mismatches)
            records.append({
                'id': production['id'],
                'level': level,
                'exam_key': entry['key'],
                'production_file': f'data/{level}/questions/{entry["questionFile"]}',
                'source_ref': production.get('source_ref'),
                'field_source': 'production_json_verified_against_official_pdf',
                'verified': verified,
                'vision_merged': {
                    key: value for key, value in vision.items()
                    if key not in {'raw_candidates', 'raw_answer_rows'}
                },
                'raw_mismatch_fields': mismatches,
                'vision_candidates': vision['raw_candidates'],
                'vision_answer_rows': vision['raw_answer_rows'],
            })

    # ``verified`` is copied from production by construction, but perform a
    # separate read-back comparison so the report can be used as a real gate.
    production_by_scope: dict[tuple[str, str, str], dict[str, Any]] = {}
    for entry in selected_entries:
        level, questions = load_production_questions(entry)
        production_by_scope.update({
            (level, entry['key'], question['id']): question for question in questions
        })
    overlay_field_mismatches: list[dict[str, str]] = []
    for record in records:
        scope = (record['level'], record['exam_key'], record['id'])
        production = production_by_scope[scope]
        for field in FIELD_NAMES:
            if field.startswith('option_'):
                key = field[-1]
                actual = record['verified']['options'][key]
                expected = production['options'][key]
            else:
                actual = record['verified'][field]
                expected = production[field]
            if actual != expected:
                overlay_field_mismatches.append({'id': record['id'], 'field': field})

    q12 = next((
        record for record in records
        if record['exam_key'] == 'mid_1151_s2' and record['id'] == 'mid_1151_s2_q12'
    ), None)
    q12_verified_answer = q12['verified']['answer'] if q12 else None
    summary = {
        'production_questions': production_questions,
        'cached_questions': cached_questions,
        'missing_cache_questions': len(missing),
        'cache_files': cache_files,
        'raw_mismatch_fields': raw_diff_fields,
        'overlay_field_mismatches': len(overlay_field_mismatches),
        'q12_verified_answer': q12_verified_answer,
        'unexpected_cache_numbers': len(unexpected_cache_numbers),
        'promotion_ready': (
            not missing
            and not overlay_field_mismatches
            and not unexpected_cache_numbers
            and (q12 is None or q12_verified_answer == 'C')
        ),
    }
    return {
        'schema_version': 1,
        'purpose': 'verified overlay; raw exam_pages_cache remains immutable audit evidence',
        'summary': summary,
        'missing_cache_question_ids': missing,
        'unexpected_cache_question_ids': unexpected_cache_numbers,
        'overlay_field_mismatches': overlay_field_mismatches,
        'records': records,
    }


def write_overlay(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f'.{path.name}.tmp')
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    json.loads(temp_path.read_text(encoding='utf-8'))
    temp_path.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--level', choices=['all', '初級', '中級'], default='all')
    parser.add_argument('--output', type=Path, help='Optional verified-overlay JSON output path')
    parser.add_argument(
        '--promotion-gate', action='store_true',
        help='Exit nonzero unless every production question has cache and the overlay is exact',
    )
    args = parser.parse_args()

    entries = exam_entries() if args.level == 'all' else exam_entries(level=args.level)
    payload = build_overlay(entries)
    if args.output:
        write_overlay(args.output, payload)
        print(f'Wrote {args.output}')
    print(json.dumps(payload['summary'], ensure_ascii=False, indent=2))

    if args.promotion_gate and not payload['summary']['promotion_ready']:
        print(
            'PROMOTION BLOCKED: sidecar coverage or verified-field gate failed; '
            'do not route raw exam_pages_cache into production.',
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
