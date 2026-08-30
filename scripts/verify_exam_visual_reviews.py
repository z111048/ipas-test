#!/usr/bin/env python3
"""Verify committed, page-by-page manual reviews of every published exam PDF."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import fitz

from resource_catalog import exam_entries, level_entry


ROOT = Path(__file__).resolve().parents[1]
REVIEW_DIR = ROOT / 'data' / 'exam_visual_review'


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _load_review_records(errors: list[str]) -> list[tuple[Path, dict[str, Any]]]:
    records: list[tuple[Path, dict[str, Any]]] = []
    if not REVIEW_DIR.is_dir():
        errors.append(f'{REVIEW_DIR}: manual visual-review directory is missing')
        return records

    for path in sorted(REVIEW_DIR.glob('*.json')):
        try:
            payload = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f'{path}: cannot load review report: {exc}')
            continue
        if payload.get('schemaVersion') != 1:
            errors.append(f'{path}: unsupported schemaVersion {payload.get("schemaVersion")!r}')
        if payload.get('method') != 'manual_visual':
            errors.append(f'{path}: method must be manual_visual')
        if not payload.get('reviewedAt'):
            errors.append(f'{path}: reviewedAt is missing')
        exams = payload.get('exams')
        if not isinstance(exams, list):
            errors.append(f'{path}: exams must be an array')
            continue
        records.extend((path, record) for record in exams if isinstance(record, dict))
        if len(exams) != sum(isinstance(record, dict) for record in exams):
            errors.append(f'{path}: every exams entry must be an object')
    return records


def verify() -> tuple[dict[str, int], list[str]]:
    errors: list[str] = []
    records = _load_review_records(errors)
    by_identity: dict[tuple[str, str], tuple[Path, dict[str, Any]]] = {}
    for report_path, record in records:
        identity = (str(record.get('levelId') or ''), str(record.get('key') or ''))
        if not all(identity):
            errors.append(f'{report_path}: review record has an empty levelId/key')
        elif identity in by_identity:
            errors.append(f'{report_path}: duplicate exam review {identity}')
        else:
            by_identity[identity] = (report_path, record)

    expected_identities = {
        (str(entry['levelId']), str(entry['key'])) for entry in exam_entries()
    }
    missing = sorted(expected_identities - set(by_identity))
    unexpected = sorted(set(by_identity) - expected_identities)
    if missing:
        errors.append(f'missing manual exam reviews: {missing}')
    if unexpected:
        errors.append(f'unexpected manual exam reviews: {unexpected}')

    reviewed_pages = 0
    reviewed_questions = 0
    for entry in exam_entries():
        identity = (str(entry['levelId']), str(entry['key']))
        located = by_identity.get(identity)
        if located is None:
            continue
        report_path, record = located
        level = str(level_entry(level_id=entry['levelId'])['dataLevel'])
        pdf_path = ROOT / 'data' / level / 'pdfs' / str(entry['pdf'])
        question_path = ROOT / 'data' / level / 'questions' / str(entry['questionFile'])
        label = f'{report_path}:{identity[0]}/{identity[1]}'

        for field in ('pdf', 'questionFile'):
            if record.get(field) != entry[field]:
                errors.append(f'{label}: {field} does not match the resource catalog')
        if not pdf_path.is_file():
            errors.append(f'{label}: source PDF is missing: {pdf_path}')
            continue
        if not question_path.is_file():
            errors.append(f'{label}: production question file is missing: {question_path}')
            continue

        pdf_digest = sha256(pdf_path)
        question_digest = sha256(question_path)
        if record.get('pdfSha256') != pdf_digest:
            errors.append(f'{label}: PDF changed after manual review')
        if record.get('questionFileSha256') != question_digest:
            errors.append(f'{label}: question JSON changed after manual review')

        with fitz.open(pdf_path) as document:
            page_count = len(document)
        payload = json.loads(question_path.read_text(encoding='utf-8'))
        questions = payload.get('questions') or []
        question_ids = [question.get('id') for question in questions]
        question_count = len(questions)

        if record.get('pageCount') != page_count:
            errors.append(f'{label}: pageCount is {record.get("pageCount")!r}, expected {page_count}')
        if record.get('questionCount') != question_count:
            errors.append(
                f'{label}: questionCount is {record.get("questionCount")!r}, expected {question_count}'
            )
        if question_count != int(entry['expectedQuestions']):
            errors.append(
                f'{label}: production has {question_count} questions, '
                f'catalog expects {entry["expectedQuestions"]}'
            )
        if record.get('reviewedPages') != list(range(page_count)):
            errors.append(f'{label}: reviewedPages is not the complete ordered page inventory')
        if record.get('reviewedQuestionIds') != question_ids:
            errors.append(f'{label}: reviewedQuestionIds is not the current ordered question inventory')
        if record.get('verdict') != 'pass':
            errors.append(f'{label}: verdict must be pass')
        if record.get('issues') != []:
            errors.append(f'{label}: unresolved issues remain: {record.get("issues")!r}')
        if record.get('uncertain') != []:
            errors.append(f'{label}: uncertain observations remain: {record.get("uncertain")!r}')

        reviewed_pages += page_count
        reviewed_questions += question_count

    summary = {
        'catalog_exams': len(expected_identities),
        'reviewed_exams': len(expected_identities & set(by_identity)),
        'reviewed_pages': reviewed_pages,
        'reviewed_questions': reviewed_questions,
        'errors': len(errors),
    }
    return summary, errors


def main() -> int:
    summary, errors = verify()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if errors:
        for error in errors:
            print(f'FAIL: {error}')
        return 1
    print('PASS: every published exam page and question has a current manual visual review.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
