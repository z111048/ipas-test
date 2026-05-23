#!/usr/bin/env python3
"""Run small Codex question batches with validation and resume support."""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
from pathlib import Path
from typing import Any

BASE = Path('/home/james/projects/ipas-test')
DEFAULT_RUN_DIR = BASE / 'data' / '中級' / 'pipeline' / 'codex_question_batch_prompts'
SCHEMA_PATH = BASE / 'schemas' / 'middle_mock_exam_chapter.schema.json'


def load_json(path: Path) -> Any:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def validate_batch(path: Path, batch: dict) -> list[str]:
    data = load_json(path)
    errors: list[str] = []
    chapter_id = batch['chapter_id']
    first_question = batch['first_question']
    count = batch['count']

    if data.get('level') != '中級':
        errors.append('level must be 中級')
    if data.get('subject_id') != batch['subject_id']:
        errors.append('subject_id mismatch')
    if data.get('chapter_id') != chapter_id:
        errors.append('chapter_id mismatch')
    if data.get('chapter_title') != batch['title']:
        errors.append('chapter_title mismatch')
    if data.get('target_count') != count:
        errors.append('target_count mismatch')

    questions = data.get('questions')
    if not isinstance(questions, list):
        errors.append('questions must be an array')
        return errors
    if len(questions) != count:
        errors.append(f'questions length {len(questions)} != {count}')

    id_pattern = re.compile(rf'^{re.escape(chapter_id)}q\d{{3}}_codex100$')
    seen: set[str] = set()
    for offset, question in enumerate(questions):
        prefix = f'questions[{offset}]'
        expected_id = f'{chapter_id}q{first_question + offset:03d}_codex100'
        if not isinstance(question, dict):
            errors.append(f'{prefix} must be an object')
            continue
        question_id = question.get('id')
        if question_id != expected_id:
            errors.append(f'{prefix}.id must be {expected_id}, got {question_id!r}')
        if isinstance(question_id, str) and not id_pattern.match(question_id):
            errors.append(f'{prefix}.id has invalid pattern: {question_id!r}')
        if isinstance(question_id, str) and question_id in seen:
            errors.append(f'{prefix}.id duplicates {question_id}')
        if isinstance(question_id, str):
            seen.add(question_id)
        if question.get('chapter_id') != chapter_id:
            errors.append(f'{prefix}.chapter_id mismatch')
        if question.get('chapter_title') != batch['title']:
            errors.append(f'{prefix}.chapter_title mismatch')
        if question.get('answer') not in {'A', 'B', 'C', 'D'}:
            errors.append(f'{prefix}.answer must be A/B/C/D')
        options = question.get('options')
        if not isinstance(options, dict) or set(options) != {'A', 'B', 'C', 'D'}:
            errors.append(f'{prefix}.options must contain exactly A/B/C/D')
        for field in ('question', 'explanation', 'type'):
            if not isinstance(question.get(field), str) or not question[field].strip():
                errors.append(f'{prefix}.{field} is required')
        card = question.get('card')
        if not isinstance(card, dict):
            errors.append(f'{prefix}.card is required')
        else:
            for field in ('concept', 'mnemonic', 'confusion', 'frequency'):
                if not isinstance(card.get(field), str) or not card[field].strip():
                    errors.append(f'{prefix}.card.{field} is required')

    return errors


def run_codex(prompt_path: Path, output_path: Path, timeout_seconds: int) -> tuple[bool, bool]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with prompt_path.open(encoding='utf-8') as prompt_file:
        proc = subprocess.Popen(
            [
                'codex',
                'exec',
                '--cd',
                BASE.as_posix(),
                '--sandbox',
                'read-only',
                '--output-schema',
                SCHEMA_PATH.as_posix(),
                '-o',
                output_path.as_posix(),
                '-',
            ],
            stdin=prompt_file,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            cwd=BASE,
            start_new_session=True,
        )
        try:
            proc.wait(timeout=timeout_seconds)
            return proc.returncode == 0 or output_path.exists(), False
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            return output_path.exists(), True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument('--start-index', type=int, default=1)
    parser.add_argument('--limit', type=int, default=None)
    parser.add_argument('--timeout', type=int, default=180)
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()

    run_dir = args.run_dir if args.run_dir.is_absolute() else BASE / args.run_dir
    summary = load_json(run_dir / 'summary.json')
    batches = summary['batches']
    selected = batches[max(args.start_index - 1, 0):]
    if args.limit is not None:
        selected = selected[:args.limit]

    completed = 0
    skipped = 0
    failed = 0
    for batch in selected:
        output_path = BASE / batch['output']
        prompt_path = BASE / batch['prompt']
        label = (
            f'{batch["batch_index"]:03d}/{len(batches):03d} {batch["chapter_id"]} '
            f'q{batch["first_question"]:03d}-{batch["first_question"] + batch["count"] - 1:03d}'
        )

        if output_path.exists() and not args.force:
            errors = validate_batch(output_path, batch)
            if not errors:
                skipped += 1
                print(f'SKIP {label}')
                continue
            print(f'RETRY {label}: invalid existing output')

        print(f'RUN {label}: {batch["count"]} questions')
        ok, timed_out = run_codex(prompt_path, output_path, args.timeout)
        if timed_out:
            print(f'WARN {label}: timeout after {args.timeout}s')

        if ok and output_path.exists():
            errors = validate_batch(output_path, batch)
            if errors:
                failed += 1
                print(f'FAIL {label}: validation errors')
                for error in errors:
                    print(f'  - {error}')
            else:
                completed += 1
                print(f'PASS {label}')
        else:
            failed += 1
            print(f'FAIL {label}: no output')

    print(f'Done: completed={completed}, skipped={skipped}, failed={failed}')
    raise SystemExit(1 if failed else 0)


if __name__ == '__main__':
    main()
