#!/usr/bin/env python3
"""Validate per-chapter Codex mock exam output."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

BASE = Path('/home/james/projects/ipas-test')
LEVEL = '中級'


def load_json(path: Path) -> Any:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def validate_file(path: Path) -> list[str]:
    data = load_json(path)
    errors: list[str] = []

    level = data.get('level')
    subject_id = data.get('subject_id')
    chapter_id = data.get('chapter_id')
    chapter_title = data.get('chapter_title')
    target_count = data.get('target_count')
    questions = data.get('questions')

    if level != LEVEL:
        errors.append(f'level must be {LEVEL}, got {level!r}')
    if subject_id not in {'mid-s1', 'mid-s2', 'mid-s3'}:
        errors.append(f'invalid subject_id: {subject_id!r}')
    if not isinstance(chapter_id, str) or not chapter_id:
        errors.append('chapter_id is required')
    if not isinstance(chapter_title, str) or not chapter_title:
        errors.append('chapter_title is required')
    if not isinstance(target_count, int):
        errors.append('target_count must be an integer')
    if not isinstance(questions, list):
        errors.append('questions must be an array')
        return errors
    if isinstance(target_count, int) and len(questions) != target_count:
        errors.append(f'questions length {len(questions)} != target_count {target_count}')

    seen_ids: set[str] = set()
    expected_id = re.compile(rf'^{re.escape(chapter_id or "")}q\d{{3}}_codex100$')
    for index, question in enumerate(questions, start=1):
        prefix = f'questions[{index - 1}]'
        if not isinstance(question, dict):
            errors.append(f'{prefix} must be an object')
            continue

        question_id = question.get('id')
        if not isinstance(question_id, str) or not expected_id.match(question_id):
            errors.append(f'{prefix}.id has invalid format: {question_id!r}')
        elif question_id in seen_ids:
            errors.append(f'{prefix}.id duplicates {question_id}')
        else:
            seen_ids.add(question_id)

        expected_suffix = f'q{index:03d}_codex100'
        if isinstance(question_id, str) and not question_id.endswith(expected_suffix):
            errors.append(f'{prefix}.id should end with {expected_suffix}, got {question_id!r}')

        if question.get('chapter_id') != chapter_id:
            errors.append(f'{prefix}.chapter_id does not match root chapter_id')
        if question.get('chapter_title') != chapter_title:
            errors.append(f'{prefix}.chapter_title does not match root chapter_title')
        if not isinstance(question.get('question'), str) or not question['question'].strip():
            errors.append(f'{prefix}.question is required')

        options = question.get('options')
        if not isinstance(options, dict) or set(options) != {'A', 'B', 'C', 'D'}:
            errors.append(f'{prefix}.options must contain exactly A/B/C/D')
        else:
            for key, value in options.items():
                if not isinstance(value, str) or not value.strip():
                    errors.append(f'{prefix}.options.{key} is required')

        if question.get('answer') not in {'A', 'B', 'C', 'D'}:
            errors.append(f'{prefix}.answer must be A/B/C/D')
        if question.get('difficulty') not in {'易', '中', '難'}:
            errors.append(f'{prefix}.difficulty must be 易/中/難')
        for field in ('explanation', 'type'):
            if not isinstance(question.get(field), str) or not question[field].strip():
                errors.append(f'{prefix}.{field} is required')

        tags = question.get('tags')
        if not isinstance(tags, list) or not tags or not all(isinstance(tag, str) and tag.strip() for tag in tags):
            errors.append(f'{prefix}.tags must be a non-empty string array')

        source_refs = question.get('source_refs')
        if not isinstance(source_refs, dict):
            errors.append(f'{prefix}.source_refs is required')
        else:
            if source_refs.get('chapter_id') != chapter_id:
                errors.append(f'{prefix}.source_refs.chapter_id does not match root chapter_id')
            for field in ('guide_path', 'basis'):
                if not isinstance(source_refs.get(field), str) or not source_refs[field].strip():
                    errors.append(f'{prefix}.source_refs.{field} is required')

        card = question.get('card')
        if not isinstance(card, dict):
            errors.append(f'{prefix}.card is required')
        else:
            for field in ('concept', 'mnemonic', 'confusion'):
                if not isinstance(card.get(field), str) or not card[field].strip():
                    errors.append(f'{prefix}.card.{field} is required')
            if card.get('frequency') not in {'高', '中', '低'}:
                errors.append(f'{prefix}.card.frequency must be 高/中/低')

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths', nargs='+', type=Path)
    args = parser.parse_args()

    failed = False
    for raw_path in args.paths:
        path = raw_path if raw_path.is_absolute() else BASE / raw_path
        errors = validate_file(path)
        if errors:
            failed = True
            print(f'FAIL {path.relative_to(BASE)}')
            for error in errors:
                print(f'  - {error}')
        else:
            data = load_json(path)
            print(f'PASS {path.relative_to(BASE)}: {len(data["questions"])} questions')

    raise SystemExit(1 if failed else 0)


if __name__ == '__main__':
    main()
