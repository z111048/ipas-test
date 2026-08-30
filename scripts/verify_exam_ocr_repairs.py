#!/usr/bin/env python3
"""Verify production exam OCR repairs and documented source-PDF issues."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from annotate_exam_code_images import MID_1151_S2_Q41_OUTPUT
from apply_exam_explanations import QUESTION_OVERRIDES, SOURCE_ISSUES
from parse_exams_v2 import QUESTION_LAYOUT_REPAIRS
from resource_catalog import exam_entries, level_entry


ROOT = Path(__file__).resolve().parents[1]
Q18_OPTIONS = {
    'A': '信賴度=P(A∩B)，即A與B 同時出現的機率，範圍[0,1]',
    'B': '支援度=P(B|A)，即 A出現時 B 也出現的條件機率，範圍[0,1]',
    'C': '提升度=P(A∩B) / [P(A)×P(B)]，範圍固定在[0,1]之間',
}
Q42_STEM = '觀察程式中行(A)將所有既有權重的梯度計算關閉，這在遷移學習中屬於哪一種標準策略？'
HEADER_NOISE_RE = re.compile(r'^\s*(?:題目\s*答案|答案\s*題目)\s*')


def compact_space(value: str) -> str:
    return re.sub(r'\s+', '', value)


QuestionScope = tuple[str, str, str]


def load_all_questions() -> tuple[dict[QuestionScope, dict[str, Any]], int, list[str]]:
    by_scope: dict[QuestionScope, dict[str, Any]] = {}
    total = 0
    errors: list[str] = []
    for entry in exam_entries():
        level = level_entry(level_id=entry['levelId'])['dataLevel']
        path = ROOT / 'data' / level / 'questions' / entry['questionFile']
        data = json.loads(path.read_text(encoding='utf-8'))
        questions = data.get('questions') or []
        expected = int(entry['expectedQuestions'])
        if len(questions) != expected:
            errors.append(f'{path}: {len(questions)} questions, expected {expected}')
        total += len(questions)
        for question in questions:
            qid = question.get('id')
            if not isinstance(qid, str):
                errors.append(f'{path}: question without string id')
            else:
                scope = (level, entry['key'], qid)
                if scope in by_scope:
                    errors.append(f'duplicate question id within exam: {scope}')
                else:
                    by_scope[scope] = question
    return by_scope, total, errors


def verify() -> tuple[dict[str, int], list[str]]:
    questions, total, errors = load_all_questions()

    q18 = questions.get(('中級', 'mid_1151_s2', 'mid_1151_s2_q18'), {})
    for key, expected in Q18_OPTIONS.items():
        actual = (q18.get('options') or {}).get(key)
        if compact_space(str(actual or '')) != compact_space(expected):
            errors.append(f'mid_1151_s2_q18 option {key} is not the verified formula text')

    q3 = questions.get(('中級', 'mid_1151_s3', 'mid_1151_s3_q3'), {})
    if q3.get('question') != QUESTION_LAYOUT_REPAIRS['mid_1151_s3_q3']:
        errors.append('mid_1151_s3_q3 matrix/subscript stem repair is missing')

    q42 = questions.get(('中級', 'mid_1151_s3', 'mid_1151_s3_q42'), {})
    if compact_space(str(q42.get('question') or '')) != compact_space(Q42_STEM):
        errors.append('mid_1151_s3_q42 stem is incomplete')

    noisy_contexts = []
    for scope, question in questions.items():
        context = question.get('context')
        if isinstance(context, str) and HEADER_NOISE_RE.search(context):
            noisy_contexts.append('/'.join(scope))
    if noisy_contexts:
        errors.append(f'exam context contains table header noise: {sorted(noisy_contexts)}')

    q41 = questions.get(('中級', 'mid_1151_s2', 'mid_1151_s2_q41'), {})
    output_blocks = [
        block for block in q41.get('context_blocks') or []
        if block.get('title') == '執行結果'
    ]
    if len(output_blocks) != 1 or output_blocks[0].get('markdown') != MID_1151_S2_Q41_OUTPUT:
        errors.append('mid_1151_s2_q41 output block differs from the PDF')
    if 'Name: daily_earnings' in json.dumps(q41, ensure_ascii=False):
        errors.append('mid_1151_s2_q41 still contains the non-source pandas footer')

    # The raw Vision sidecar once read this official answer as A.  The sidecar
    # cache is intentionally gitignored, so the committed publication gate must
    # also lock the verified production answer on a fresh checkout.
    q12 = questions.get(('中級', 'mid_1151_s2', 'mid_1151_s2_q12'), {})
    if q12.get('answer') != 'C':
        errors.append('mid_1151_s2_q12 verified official answer must remain C')

    q46 = questions.get(('中級', 'mid_1151_s3', 'mid_1151_s3_q46'), {})
    if q46.get('question') != QUESTION_OVERRIDES['mid_1151_s3_q46']:
        errors.append('mid_1151_s3_q46 image-statement transcription is not source-faithful')
    if '避免像素值過大導致梯度爆炸' in str(q46.get('question') or ''):
        errors.append('mid_1151_s3_q46 still contains the unsupported parenthetical')

    issue_count = 0
    for scope, expected_issue in SOURCE_ISSUES.items():
        question = questions.get(scope)
        scoped_id = '/'.join(scope)
        if not question:
            errors.append(f'missing source-issue question: {scoped_id}')
            continue
        issue_count += 1
        if question.get('answer') != expected_issue['official_answer']:
            errors.append(f'{scoped_id}: official answer was changed')
        if question.get('source_issue') != expected_issue:
            errors.append(f'{scoped_id}: machine-readable source issue is missing or stale')
        if question.get('explanation') != expected_issue['note']:
            errors.append(f'{scoped_id}: visible source-issue explanation is missing or stale')

    unexpected_issue_ids = sorted(
        '/'.join(scope) for scope, question in questions.items()
        if 'source_issue' in question and scope not in SOURCE_ISSUES
    )
    if unexpected_issue_ids:
        errors.append(f'undocumented source_issue fields: {unexpected_issue_ids}')

    summary = {
        'catalog_exams': len(exam_entries()),
        'production_questions': total,
        'source_issues_visible': issue_count,
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
    print('PASS: production exam OCR repairs and source-issue notices are current.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
