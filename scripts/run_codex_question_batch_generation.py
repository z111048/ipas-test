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

from verify_batch_answers import DEFAULT_VERIFIERS, verify_batch_answers
from question_dedupe import (
    find_similar_question_pairs,
    find_similar_question_pairs_between,
    question_label,
)

BASE = Path('/home/james/projects/ipas-test')
DEFAULT_RUN_DIR = BASE / 'data' / '中級' / 'pipeline' / 'codex_question_batch_prompts'
SCHEMA_PATH = BASE / 'schemas' / 'middle_mock_exam_chapter.schema.json'


def load_json(path: Path) -> Any:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def validate_batch(path: Path, batch: dict, level: str = '中級') -> list[str]:
    """level 由 summary.json 帶入。2026-08-09 之前硬編「中級」，
    初級出題會 6/6 全失敗在 subject_id/level mismatch——而且錯誤訊息看起來像
    模型不聽話，不像是我們自己只支援一個等級。"""
    data = load_json(path)
    errors: list[str] = []
    chapter_id = batch['chapter_id']
    first_question = batch['first_question']
    count = batch['count']

    if data.get('level') != level:
        errors.append(f'level must be {level}')
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
            for field in ('concept', 'mnemonic', 'confusion'):
                if not isinstance(card.get(field), str) or not card[field].strip():
                    errors.append(f'{prefix}.card.{field} is required')

    valid_questions = [question for question in questions if isinstance(question, dict)]
    for left_index, right_index, ratio, left, right in find_similar_question_pairs(valid_questions):
        errors.append(
            'near-duplicate question stem inside batch '
            f'{question_label(left, left_index)} <> {question_label(right, right_index)} '
            f'(similarity={ratio:.2f})'
        )

    return errors


def previous_batches(summary: dict[str, Any], batch: dict[str, Any]) -> list[dict[str, Any]]:
    by_output = {item['output']: item for item in summary.get('batches', [])}
    explicit_previous = [
        by_output[path]
        for path in batch.get('previous_outputs', [])
        if path in by_output
    ]
    if explicit_previous:
        return explicit_previous
    return [
        item
        for item in summary.get('batches', [])
        if item.get('chapter_id') == batch.get('chapter_id')
        and item.get('first_question', 0) < batch.get('first_question', 0)
    ]


def load_previous_questions(summary: dict[str, Any], batch: dict[str, Any],
                            level: str = '中級') -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    for previous in previous_batches(summary, batch):
        path = BASE / previous['output']
        if not path.exists() or validate_batch(path, previous, level):
            continue
        data = load_json(path)
        questions.extend(
            question for question in data.get('questions', [])
            if isinstance(question, dict)
        )
    return questions


def validate_against_previous(
    path: Path,
    previous_questions: list[dict[str, Any]],
) -> list[str]:
    if not previous_questions:
        return []
    data = load_json(path)
    current_questions = [
        question for question in data.get('questions', [])
        if isinstance(question, dict)
    ]
    errors = []
    for current_index, previous_index, ratio, current, previous in find_similar_question_pairs_between(
        current_questions, previous_questions
    ):
        errors.append(
            'near-duplicate question stem against previous batch '
            f'{question_label(current, current_index)} <> {question_label(previous, previous_index)} '
            f'(similarity={ratio:.2f})'
        )
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


def answer_errors(output_path: Path, level: str, args: Any) -> list[str]:
    """答案交叉驗證的結果轉成 validate 的錯誤字串。

    沒帶 --verify-answers 就完全不做（保持舊行為）；帶了就**驗不過即失敗**。
    """
    if not getattr(args, 'verify_answers', False):
        return []
    result = verify_batch_answers(output_path, level, args.verifiers,
                                  args.answer_threshold, timeout=args.timeout)
    if result['ok']:
        return []
    consensus = result.get('flaggedConsensus') or []
    detail = f"（其中 {consensus} 是不同意者共識，最可能真的錯）" if consensus else ''
    return [f"answer cross-check flagged {result['flagged']}{detail}"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument('--start-index', type=int, default=1)
    parser.add_argument('--limit', type=int, default=None)
    # 8 題一批在 180s 會 timeout（2026-08-09 實測），拉到 420s
    parser.add_argument('--timeout', type=int, default=420)
    parser.add_argument('--force', action='store_true')
    # 答案交叉驗證接成「批次的驗證條件之一」：不過的批次算失敗、重跑會重生，
    # export_generated_questions.py 也會拒絕寫出。稽核出來不阻擋等於沒稽核。
    parser.add_argument('--verify-answers', action='store_true',
                        help='每批通過 schema 驗證後再做答案交叉驗證（強烈建議）')
    parser.add_argument('--verifiers', default=DEFAULT_VERIFIERS)
    parser.add_argument('--answer-threshold', type=int, default=2)
    args = parser.parse_args()

    run_dir = args.run_dir if args.run_dir.is_absolute() else BASE / args.run_dir
    summary = load_json(run_dir / 'summary.json')
    level = summary.get('level', '中級')   # 2026-08-09：不要再假設中級
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
            errors = validate_batch(output_path, batch, level)
            errors.extend(validate_against_previous(
                output_path, load_previous_questions(summary, batch, level)))
            errors.extend(answer_errors(output_path, level, args))
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
            errors = validate_batch(output_path, batch, level)
            errors.extend(validate_against_previous(
                output_path, load_previous_questions(summary, batch, level)))
            errors.extend(answer_errors(output_path, level, args))
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
