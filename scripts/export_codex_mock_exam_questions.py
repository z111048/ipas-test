#!/usr/bin/env python3
"""Export generated Codex mock questions to the frontend question schema."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

BASE = Path('/home/james/projects/ipas-test')
LEVEL = '中級'
SOURCE_DIR = BASE / 'data' / LEVEL / 'pipeline' / 'codex_mock_exam_generated'
TARGET_DIR = BASE / 'data' / LEVEL / 'questions'
SUBJECT_NUMBERS = {'mid-s1': 1, 'mid-s2': 2, 'mid-s3': 3}


def load_json(path: Path) -> Any:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def normalize_question(question: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(question)
    normalized['source'] = 'codex100'
    normalized['level'] = LEVEL
    return normalized


def export_subject(subject_id: str, manifest_subject: dict[str, Any]) -> Path:
    subject_no = SUBJECT_NUMBERS[subject_id]
    source_path = SOURCE_DIR / f'subject{subject_no}_codex100_partial.json'
    generated = load_json(source_path)
    if not generated.get('complete'):
        raise ValueError(f'{source_path.relative_to(BASE)} is not complete')

    questions_by_chapter: dict[str, list[dict[str, Any]]] = {}
    for question in generated['questions']:
        questions_by_chapter.setdefault(question['chapter_id'], []).append(normalize_question(question))

    chapters = []
    for chapter in manifest_subject['chapters']:
        chapter_questions = questions_by_chapter.get(chapter['id'], [])
        chapters.append({
            'id': chapter['id'],
            'title': chapter['title'],
            'questions': chapter_questions,
        })

    total = sum(len(chapter['questions']) for chapter in chapters)
    if total != 100:
        raise ValueError(f'{subject_id} expected 100 questions, got {total}')

    payload = {
        'level': LEVEL,
        'subject': manifest_subject['subject'],
        'source': 'codex100',
        'description': 'Codex CLI 依官方考古題、樣題與學習指引產生的中級章節模擬題',
        'chapters': chapters,
    }
    target_path = TARGET_DIR / f'subject{subject_no}_codex100_questions.json'
    write_json(target_path, payload)
    return target_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    manifest = load_json(BASE / 'data' / LEVEL / 'toc_manifest.json')
    subjects = {subject['id']: subject for subject in manifest['subjects']}
    for subject_id in ('mid-s1', 'mid-s2', 'mid-s3'):
        path = export_subject(subject_id, subjects[subject_id])
        print(f'Wrote {path.relative_to(BASE)}')


if __name__ == '__main__':
    main()
