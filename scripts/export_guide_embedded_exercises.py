#!/usr/bin/env python3
"""Extract embedded guide exercises from cleaned PDF pages."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]

QUESTION_RE = re.compile(r'^(\d{1,2})\.\s+(?!Ans\b)(.+)$', re.IGNORECASE)
ANSWER_RE = re.compile(r'^(\d{1,2})\.\s*Ans[（(]([A-D])[）)]?\s*(.*)$', re.IGNORECASE)
OPTION_RE = re.compile(r'[（(]([A-D])[）)]')


def load_json(path: Path) -> Any:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def compact_text(value: str) -> str:
    value = re.sub(r'\s*\n\s*', '', value.strip())
    value = re.sub(r'[ \t]+', ' ', value)
    return value


def page_index(path: Path) -> int:
    return int(path.stem.split('_')[-1])


def chapter_for_page(subject: dict[str, Any], page: int) -> dict[str, Any] | None:
    for chapter in subject['chapters']:
        page_range = chapter.get('page_range')
        if page_range and page_range[0] <= page <= page_range[1]:
            return chapter
    return None


def read_page_lines(page_path: Path) -> list[tuple[int, str]]:
    page = page_index(page_path)
    data = load_json(page_path)
    text = data.get('cleaned_text') or ''
    return [(page, line.strip()) for line in text.splitlines() if line.strip()]


def parse_question_block(lines: list[str]) -> tuple[str, dict[str, str]] | None:
    text = compact_text('\n'.join(lines))
    matches = list(OPTION_RE.finditer(text))
    if len(matches) < 4:
        return None

    question = compact_text(text[:matches[0].start()])
    options: dict[str, str] = {}
    for index, match in enumerate(matches):
        key = match.group(1)
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        options[key] = compact_text(text[start:end])

    if set(options) != {'A', 'B', 'C', 'D'}:
        return None
    return question, options


def parse_questions(page_paths: list[Path], subject: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    def flush() -> None:
        nonlocal current
        if not current:
            return
        parsed = parse_question_block(current['lines'])
        if parsed:
            question, options = parsed
            chapter = chapter_for_page(subject, current['page'])
            if chapter:
                records.append({
                    'number': current['number'],
                    'page': current['page'],
                    'chapter_id': chapter['id'],
                    'chapter_title': chapter['title'],
                    'question': question,
                    'options': options,
                })
        current = None

    for page_path in page_paths:
        for page, line in read_page_lines(page_path):
            answer_match = ANSWER_RE.match(line)
            question_match = QUESTION_RE.match(line)
            if answer_match:
                flush()
                continue
            if question_match:
                flush()
                current = {
                    'number': int(question_match.group(1)),
                    'page': page,
                    'lines': [question_match.group(2)],
                }
            elif current:
                current['lines'].append(line)
    flush()
    return records


def parse_answers(page_paths: list[Path], subject: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    def flush() -> None:
        nonlocal current
        if not current:
            return
        chapter = chapter_for_page(subject, current['page'])
        if chapter:
            explanation = compact_text('\n'.join(current['explanation']))
            records.append({
                'number': current['number'],
                'page': current['page'],
                'chapter_id': chapter['id'],
                'chapter_title': chapter['title'],
                'answer': current['answer'],
                'answer_text': compact_text(current['answer_text']),
                'explanation': explanation,
            })
        current = None

    for page_path in page_paths:
        for page, line in read_page_lines(page_path):
            answer_match = ANSWER_RE.match(line)
            question_match = QUESTION_RE.match(line)
            if answer_match:
                flush()
                current = {
                    'number': int(answer_match.group(1)),
                    'page': page,
                    'answer': answer_match.group(2).upper(),
                    'answer_text': answer_match.group(3),
                    'explanation': [],
                }
                continue
            if question_match:
                flush()
                continue
            if current:
                current['explanation'].append(line)
    flush()
    return records


def merge_records(questions: list[dict[str, Any]], answers: list[dict[str, Any]], subject: dict[str, Any]) -> dict[str, Any]:
    answer_map = {
        (answer['chapter_id'], answer['number']): answer
        for answer in answers
    }
    by_chapter: dict[str, list[dict[str, Any]]] = {chapter['id']: [] for chapter in subject['chapters']}
    unmatched: list[dict[str, Any]] = []

    chapter_counts: dict[str, int] = {}
    for question in questions:
        key = (question['chapter_id'], question['number'])
        answer = answer_map.get(key)
        if not answer:
            unmatched.append(question)
            continue
        chapter_id = question['chapter_id']
        chapter_counts[chapter_id] = chapter_counts.get(chapter_id, 0) + 1
        local_index = chapter_counts[chapter_id]
        by_chapter[chapter_id].append({
            'id': f'{chapter_id}gq{local_index:03d}',
            'question': question['question'],
            'options': question['options'],
            'answer': answer['answer'],
            'explanation': answer['explanation'],
            'difficulty': '中',
            'type': '學習指引章節練習',
            'tags': ['學習指引', '章節練習'],
            'source': 'guide_exercise',
            'level': '中級' if subject['id'].startswith('mid-') else '初級',
            'source_ref': {
                'question_page': question['page'],
                'answer_page': answer['page'],
                'original_number': question['number'],
            },
            'card': {
                'concept': answer['answer_text'] or question['options'][answer['answer']],
                'mnemonic': '依學習指引原題複習',
                'confusion': answer['explanation'],
                'frequency': '中',
            },
        })

    return {
        'chapters': [
            {
                'id': chapter['id'],
                'title': chapter['title'],
                'questions': by_chapter[chapter['id']],
            }
            for chapter in subject['chapters']
        ],
        'unmatched_questions': unmatched,
    }


def export_level(level: str) -> None:
    manifest = load_json(BASE / 'data' / level / 'toc_manifest.json')
    subject_by_key = {subject['key']: subject for subject in manifest['subjects']}
    page_clean_dir = BASE / 'data' / level / 'page_clean'

    for key, subject in subject_by_key.items():
        pages_dir = page_clean_dir / key / 'pages'
        if not pages_dir.exists():
            continue
        page_paths = sorted(pages_dir.glob('page_*.json'), key=page_index)
        questions = parse_questions(page_paths, subject)
        answers = parse_answers(page_paths, subject)
        merged = merge_records(questions, answers, subject)
        payload = {
            'level': level,
            'subject': subject['subject'],
            'source': 'guide_exercise',
            'description': '從學習指引 PDF 內嵌章節練習題抽取',
            'chapters': merged['chapters'],
        }
        subject_number = key.replace('guide', '')
        out_path = BASE / 'data' / level / 'questions' / f'subject{subject_number}_guide_exercises.json'
        write_json(out_path, payload)
        total = sum(len(chapter['questions']) for chapter in payload['chapters'])
        print(f'Wrote {out_path.relative_to(BASE)}: {total} questions')
        if merged['unmatched_questions']:
            print(f'  WARN unmatched questions: {len(merged["unmatched_questions"])}')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--level', choices=['初級', '中級', 'all'], default='all')
    args = parser.parse_args()

    levels = ['初級', '中級'] if args.level == 'all' else [args.level]
    for level in levels:
        export_level(level)


if __name__ == '__main__':
    main()
