#!/usr/bin/env python3
"""Extract embedded guide exercises from cleaned PDF pages."""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]

QUESTION_RE = re.compile(r'^(\d{1,2})\.\s+(?!Ans\b)(.+)$', re.IGNORECASE)
ANSWER_RE = re.compile(r'^(\d{1,2})\.\s*Ans[（(]([A-D])[）)]?\s*(.*)$', re.IGNORECASE)
OPTION_RE = re.compile(r'[（(]([A-D])[）)]')
STRONG_BIBLIOGRAPHY_BOUNDARIES = {
    '附件本學習指引參考書目',
    '本學習指引參考書目',
    '附件參考書目',
}


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


def normalized_structural_line(value: str) -> str:
    """Normalize one complete source line for structural comparisons only."""
    value = unicodedata.normalize('NFKC', value or '').strip()
    value = re.sub(r'^#{1,6}\s*', '', value)
    return re.sub(r'\s+', '', value).strip('：:')


def is_bibliography_boundary(line: str, *, first_content_line: bool = False) -> bool:
    """Recognize a standalone appendix heading, never an in-sentence mention.

    The supplied guides use the strong ``附件 本學習指引參考書目`` label.
    A bare ``參考書目`` is accepted only as the first content line of a page,
    which covers a conventional appendix heading without truncating an option
    or explanation that merely discusses reference material.
    """
    normalized = normalized_structural_line(line)
    return (
        normalized in STRONG_BIBLIOGRAPHY_BOUNDARIES
        or (first_content_line and normalized == '參考書目')
    )


def has_bibliography_bleed(value: str) -> bool:
    """Detect a strong appendix marker in an already assembled field."""
    normalized = normalized_structural_line(value)
    return any(marker in normalized for marker in STRONG_BIBLIOGRAPHY_BOUNDARIES)


def page_index(path: Path) -> int:
    return int(path.stem.split('_')[-1])


def chapter_for_page(subject: dict[str, Any], page: int) -> dict[str, Any] | None:
    for chapter in subject['chapters']:
        page_range = chapter.get('page_range')
        if page_range and page_range[0] <= page <= page_range[1]:
            return chapter
    return None


def page_lines(page_path: Path) -> list[str]:
    data = load_json(page_path)
    text = data.get('cleaned_text') or ''
    return [line.strip() for line in text.splitlines() if line.strip()]


def collect_running_headers(page_paths: list[Path]) -> set[str]:
    """找出頁眉（重複出現在多頁首行的章名）。

    題塊跨頁時，下一頁的頁眉會被當成選項內文吃進去（例如選項 D 變成
    「迭代次數第三章 人工智慧基礎概論」）。頁眉不寫死，靠出現頻率認。
    """
    counts: dict[str, int] = {}
    for path in page_paths:
        lines = page_lines(path)
        if lines:
            counts[lines[0]] = counts.get(lines[0], 0) + 1
    threshold = max(3, len(page_paths) // 20)
    return {line for line, count in counts.items()
            if count >= threshold and len(line) <= 40}


def read_page_lines(page_path: Path, headers: set[str] | None = None) -> list[tuple[int, str]]:
    page = page_index(page_path)
    lines = page_lines(page_path)
    if headers and lines and lines[0] in headers:
        lines = lines[1:]          # 只剝首行，避免誤刪正文裡同名的標題
    return [(page, line) for line in lines]


def continues_to_next(page_path: Path) -> bool:
    """這一頁的內容是否接續到下一頁（clean_pdf_page_text.py 判定的）。

    最後一題的解析沒有結束標記，會一路吃到下一頁的新章正文；本頁沒有續接
    時就在頁尾收束，可擋掉這種尾端污染。
    """
    return bool(load_json(page_path).get('continues_to_next'))


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


def parse_questions(page_paths: list[Path], subject: dict[str, Any],
                    headers: set[str]) -> list[dict[str, Any]]:
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
        source_lines = read_page_lines(page_path, headers)
        for line_index, (page, line) in enumerate(source_lines):
            if is_bibliography_boundary(line, first_content_line=line_index == 0):
                flush()
                return records
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
        # 題目區塊只在四個選項都齊了才於頁尾收束；沒齊表示選項真的跨頁，
        # 這時提前收束會整題掉題（中級 mid-s3c6gq010 就是這種）。
        if current and parse_question_block(current['lines']):
            flush()
    flush()
    return records


def parse_answers(page_paths: list[Path], subject: dict[str, Any],
                  headers: set[str]) -> list[dict[str, Any]]:
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
        source_lines = read_page_lines(page_path, headers)
        for line_index, (page, line) in enumerate(source_lines):
            if is_bibliography_boundary(line, first_content_line=line_index == 0):
                flush()
                return records
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
        if not continues_to_next(page_path):
            flush()
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
            # 這裡刻意**不產生 `card`**。舊版塞的是佔位內容——concept 抄答案選項、
            # mnemonic 寫死「依學習指引原題複習」、confusion 直接複製 explanation
            # ——179 題全部如此，前端卻把它顯示成「常見混淆」與「記憶口訣」。
            # 真正的 card 由 build_codex_card_prompts.py → run_codex_card_generation.py
            # → apply_codex_card_fields.py 產生；`export_level` 會保留既有的，
            # 所以重跑這支腳本不會蓋掉已重生的內容。見 08-topic-labeling.md §7-6。
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


def carry_over_cards(out_path: Path, chapters: list[dict[str, Any]]) -> int:
    """把已 committed 的 `card` 依 id 帶回新產出，避免重跑抹掉重生過的圖卡內容。"""
    if not out_path.exists():
        return 0
    existing: dict[str, Any] = {}
    for chapter in load_json(out_path).get('chapters') or []:
        for question in chapter.get('questions') or []:
            if isinstance(question.get('card'), dict) and question.get('id'):
                existing[str(question['id'])] = question['card']
    kept = 0
    for chapter in chapters:
        for question in chapter.get('questions') or []:
            card = existing.get(str(question.get('id')))
            if card is not None:
                question['card'] = card
                kept += 1
    if kept:
        print(f'  carried over {kept} existing cards')
    return kept


def payload_questions(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        question
        for chapter in payload.get('chapters') or []
        for question in chapter.get('questions') or []
    ]


def validate_export_payload(
    payload: dict[str, Any],
    previous_payload: dict[str, Any] | None = None,
) -> None:
    """Fail before writing on appendix bleed or silent production data loss."""
    questions = payload_questions(payload)
    by_id = {str(question.get('id') or ''): question for question in questions}
    if '' in by_id or len(by_id) != len(questions):
        raise ValueError('guide exercise output has missing or duplicate question IDs')

    for question_id, question in by_id.items():
        fields = {
            'question': question.get('question'),
            'explanation': question.get('explanation'),
            **{
                f'option.{key}': value
                for key, value in (question.get('options') or {}).items()
            },
            **{
                f'card.{key}': value
                for key, value in (question.get('card') or {}).items()
                if isinstance(value, str)
            },
        }
        for field, value in fields.items():
            if has_bibliography_bleed(str(value or '')):
                raise ValueError(f'{question_id}.{field} contains bibliography appendix bleed')

    if previous_payload is None:
        return
    previous_questions = payload_questions(previous_payload)
    previous_by_id = {
        str(question.get('id') or ''): question for question in previous_questions
    }
    if '' in previous_by_id or len(previous_by_id) != len(previous_questions):
        raise ValueError('existing guide exercise output has missing or duplicate question IDs')
    if set(by_id) != set(previous_by_id):
        missing = sorted(set(previous_by_id) - set(by_id))
        added = sorted(set(by_id) - set(previous_by_id))
        raise ValueError(
            f'guide exercise question IDs changed; missing={missing}, added={added}'
        )
    for question_id, previous in previous_by_id.items():
        previous_card = previous.get('card')
        if isinstance(previous_card, dict) and by_id[question_id].get('card') != previous_card:
            raise ValueError(f'{question_id} existing card was not preserved exactly')


def export_level(level: str) -> None:
    manifest = load_json(BASE / 'data' / level / 'toc_manifest.json')
    subject_by_key = {subject['key']: subject for subject in manifest['subjects']}
    page_clean_dir = BASE / 'data' / level / 'page_clean'

    for key, subject in subject_by_key.items():
        pages_dir = page_clean_dir / key / 'pages'
        if not pages_dir.exists():
            continue
        page_paths = sorted(pages_dir.glob('page_*.json'), key=page_index)
        headers = collect_running_headers(page_paths)
        questions = parse_questions(page_paths, subject, headers)
        answers = parse_answers(page_paths, subject, headers)
        merged = merge_records(questions, answers, subject)
        subject_number = key.replace('guide', '')
        out_path = (BASE / 'data' / level / 'questions'
                    / f'subject{subject_number}_guide_exercises.json')
        previous_payload = load_json(out_path) if out_path.exists() else None
        carry_over_cards(out_path, merged['chapters'])
        payload = {
            'level': level,
            'subject': subject['subject'],
            'source': 'guide_exercise',
            'description': '從學習指引 PDF 內嵌章節練習題抽取',
            'chapters': merged['chapters'],
        }
        validate_export_payload(payload, previous_payload)
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
