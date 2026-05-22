#!/usr/bin/env python3
"""Validate Codex-generated middle mock exam JSON."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

BASE = Path('/home/james/projects/ipas-test')
LEVEL = '中級'
TOTAL = 100


def load_json(path: Path) -> Any:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def expected_allocation(subject: dict) -> dict[str, int]:
    chapters = subject['chapters']
    base = TOTAL // len(chapters)
    remainder = TOTAL % len(chapters)
    return {
        chapter['id']: base + (1 if index < remainder else 0)
        for index, chapter in enumerate(chapters)
    }


def normalize_text(value: str) -> str:
    return re.sub(r'\s+', '', value).lower()


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    data = load_json(path)
    manifest = load_json(BASE / 'data' / LEVEL / 'toc_manifest.json')
    subjects = {subject['id']: subject for subject in manifest['subjects']}

    subject_id = data.get('subject_id')
    subject = subjects.get(subject_id)
    if not subject:
        errors.append(f'unknown subject_id: {subject_id!r}')
        return errors

    questions = data.get('questions')
    if not isinstance(questions, list):
        errors.append('questions is not a list')
        return errors
    if len(questions) != TOTAL:
        errors.append(f'questions length is {len(questions)}, expected {TOTAL}')

    expected = expected_allocation(subject)
    actual = Counter(q.get('chapter_id') for q in questions)
    for chapter_id, count in expected.items():
        if actual[chapter_id] != count:
            errors.append(f'{chapter_id} has {actual[chapter_id]} questions, expected {count}')
    for chapter_id in actual:
        if chapter_id not in expected:
            errors.append(f'unexpected chapter_id: {chapter_id!r}')

    ids = set()
    stems = set()
    for index, q in enumerate(questions):
        where = f'questions[{index}]'
        qid = q.get('id')
        chapter_id = q.get('chapter_id')
        if not isinstance(qid, str) or not re.fullmatch(r'mid-s[123]c\d+q\d{3}_codex100', qid):
            errors.append(f'{where} invalid id: {qid!r}')
        if isinstance(qid, str) and qid in ids:
            errors.append(f'{where} duplicate id: {qid}')
        ids.add(qid)
        if isinstance(qid, str) and isinstance(chapter_id, str) and not qid.startswith(f'{chapter_id}q'):
            errors.append(f'{where} id does not match chapter_id: {qid} vs {chapter_id}')

        question = q.get('question')
        if not isinstance(question, str) or not question.strip():
            errors.append(f'{where} missing question')
        else:
            normalized = normalize_text(question)
            if normalized in stems:
                errors.append(f'{where} duplicate question stem')
            stems.add(normalized)

        options = q.get('options')
        if not isinstance(options, dict) or set(options) != {'A', 'B', 'C', 'D'}:
            errors.append(f'{where} options must be exactly A/B/C/D')
        elif any(not isinstance(options[key], str) or not options[key].strip() for key in 'ABCD'):
            errors.append(f'{where} has empty option')

        if q.get('answer') not in {'A', 'B', 'C', 'D'}:
            errors.append(f'{where} invalid answer: {q.get("answer")!r}')

        for key in ['explanation', 'difficulty', 'type']:
            if not isinstance(q.get(key), str) or not q[key].strip():
                errors.append(f'{where} missing {key}')
        if q.get('difficulty') not in {'易', '中', '難'}:
            errors.append(f'{where} invalid difficulty: {q.get("difficulty")!r}')
        if not isinstance(q.get('tags'), list) or not q['tags']:
            errors.append(f'{where} missing tags')

        source_refs = q.get('source_refs')
        if not isinstance(source_refs, dict) or not source_refs.get('basis'):
            errors.append(f'{where} missing source_refs.basis')
        card = q.get('card')
        if not isinstance(card, dict):
            errors.append(f'{where} missing card')
        else:
            for key in ['concept', 'mnemonic', 'confusion', 'frequency']:
                if not isinstance(card.get(key), str) or not card[key].strip():
                    errors.append(f'{where} missing card.{key}')
            if card.get('frequency') not in {'高', '中', '低'}:
                errors.append(f'{where} invalid card.frequency: {card.get("frequency")!r}')

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', help='Codex-generated subject JSON path')
    args = parser.parse_args()

    path = Path(args.path)
    if not path.is_absolute():
        path = BASE / path
    errors = validate(path)
    if errors:
        print(f'Validation failed: {path.relative_to(BASE)}')
        for error in errors:
            print(f'  - {error}')
        sys.exit(1)
    print(f'Validation passed: {path.relative_to(BASE)}')


if __name__ == '__main__':
    main()
