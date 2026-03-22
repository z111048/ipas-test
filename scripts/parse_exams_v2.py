#!/usr/bin/env python3
"""Parse exam questions from JSON tables (accurate extraction)."""

import json
import re
from pathlib import Path

BASE = Path('/home/james/projects/ipas-test')

FW_MAP = {'Ａ': 'A', 'Ｂ': 'B', 'Ｃ': 'C', 'Ｄ': 'D', '（': '(', '）': ')'}


def normalize(s: str) -> str:
    for fw, hw in FW_MAP.items():
        s = s.replace(fw, hw)
    return s


def parse_question_cell(answer: str, cell_text: str, qnum: int, source_key: str) -> dict | None:
    """Parse a single question from table cell text."""
    answer = normalize(answer.strip())
    if answer not in ('A', 'B', 'C', 'D'):
        return None

    text = cell_text.strip()
    # Remove embedded question number (e.g. "\n1.\n" or "1.")
    text = re.sub(r'\n\d+[\.\．]\n', '\n', text)
    text = re.sub(r'^\d+[\.\．]\s*', '', text)

    # Extract options
    opts = {}
    opt_pattern = re.compile(r'\(([A-D])\)(.*?)(?=\([A-D]\)|\Z)', re.DOTALL)
    for m in opt_pattern.finditer(text):
        opt_text = m.group(2).strip()
        opt_text = re.sub(r'[；;]\s*$', '', opt_text)
        opt_text = re.sub(r'\s+', ' ', opt_text).strip()
        opts[m.group(1)] = opt_text

    if len(opts) < 4:
        return None

    # Question text = everything before first option
    q_match = re.match(r'^(.*?)(?=\([A-D]\))', text, re.DOTALL)
    q_text = q_match.group(1).strip() if q_match else ''
    q_text = re.sub(r'\s+', ' ', q_text).strip()

    if not q_text or not opts:
        return None

    return {
        'id': f'{source_key}_q{qnum}',
        'question': q_text,
        'options': opts,
        'answer': answer,
        'explanation': f'正確答案為({answer})。',
        'source': source_key,
    }


def parse_exam_json(key: str, data_dir: Path) -> list[dict]:
    """Parse questions from exam JSON using table data."""
    with open(data_dir / 'extracted' / f'{key}.json', encoding='utf-8') as f:
        data = json.load(f)
    questions = []
    qnum = 0

    for page in data['pages']:
        for table in page.get('tables', []):
            for row in table:
                if not row or len(row) < 2:
                    continue
                answer = str(row[0] or '').strip()
                cell = str(row[1] or '').strip()
                if not cell or not answer:
                    continue
                # Skip header rows
                if answer in ('答案', '題號', '題 目', ''):
                    continue
                if not re.match(r'^[A-DＡＢＣＤ]$', normalize(answer)):
                    continue
                qnum += 1
                q = parse_question_cell(answer, cell, qnum, key)
                if q:
                    questions.append(q)
                else:
                    print(f"  WARN: {key} row {qnum} skipped (answer={answer!r}, cell={cell[:40]!r})")

    print(f"  {key}: {len(questions)} questions parsed")
    return questions


def parse_sample_json(data_dir: Path) -> list[dict]:
    """Parse sample exam from JSON — has different table format."""
    with open(data_dir / 'extracted' / 'sample.json', encoding='utf-8') as f:
        data = json.load(f)
    questions = []

    for page in data['pages']:
        for table in page.get('tables', []):
            for row in table:
                if not row or len(row) < 4:
                    continue
                # Sample format: [qnum, '', '', answer, '', '', question_text, '']
                # or: ['1.', '', '', 'B', '', '', 'question...', '']
                # Find answer (A/B/C/D) and question text
                answer = None
                q_text_cell = None
                for cell in row:
                    s = normalize(str(cell or '').strip())
                    if re.match(r'^[ABCD]$', s) and answer is None:
                        answer = s
                    elif s and len(s) > 10 and '(A)' in s and answer is not None:
                        q_text_cell = s

                if answer and q_text_cell:
                    qnum = len(questions) + 1
                    q = parse_question_cell(answer, q_text_cell, qnum, 'sample')
                    if q:
                        questions.append(q)

    print(f"  sample: {len(questions)} questions parsed")
    return questions


def save_mock(filename: str, title: str, questions: list[dict], questions_dir: Path):
    mock = {
        'exam': title,
        'total': len(questions),
        'time_limit': '90分鐘',
        'passing_score': 60,
        'questions': questions,
    }
    path = questions_dir / filename
    path.write_text(json.dumps(mock, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Saved {path} ({len(questions)} questions)")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Parse exam questions from extracted JSON')
    parser.add_argument('--level', default='初級',
                        help='資料等級資料夾（預設: 初級）')
    args = parser.parse_args()

    data_dir = BASE / 'data' / args.level
    questions_dir = data_dir / 'questions'
    questions_dir.mkdir(exist_ok=True)

    q1 = parse_exam_json('exam1', data_dir)
    save_mock('mock_exam1.json', '科目一 模擬考試：人工智慧基礎概論（114年第四梯次公告試題）', q1, questions_dir)

    q2 = parse_exam_json('exam2', data_dir)
    save_mock('mock_exam2.json', '科目二 模擬考試：生成式AI應用與規劃（114年第四梯次公告試題）', q2, questions_dir)

    qs = parse_sample_json(data_dir)
    save_mock('sample_exam.json', '考試樣題（114年9月版）', qs, questions_dir)

    print("\nAll mock exams saved.")


if __name__ == '__main__':
    main()
