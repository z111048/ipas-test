#!/usr/bin/env python3
"""Export guide/question seed files used by the question generation pipeline."""

import argparse
import json
import re
from pathlib import Path
from typing import Any

BASE = Path('/home/james/projects/ipas-test')


def load_json(path: Path) -> dict:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def strip_title_heading(content: str, title: str) -> str:
    lines = content.splitlines()
    if lines and re.sub(r'\s+', '', lines[0].lstrip('#').strip()) == re.sub(r'\s+', '', title):
        lines = lines[1:]
        while lines and not lines[0].strip():
            lines = lines[1:]
    return '\n'.join(lines).strip()


def merge_existing_questions(path: Path, seed: dict) -> dict:
    if not path.exists():
        return seed

    existing = load_json(path)
    existing_chapters = {
        chapter.get('id'): chapter
        for chapter in existing.get('chapters', [])
    }
    for chapter in seed['chapters']:
        previous = existing_chapters.get(chapter['id'])
        if previous:
            chapter['questions'] = previous.get('questions', [])
    return seed


def guide_content_path(guide_key: str, content_ref: str) -> Path:
    return BASE / 'frontend' / 'src' / 'generated' / 'guideContent' / guide_key / content_ref


def build_subject_seed(level: str, subject_index: int, manifest_subject: dict, guide_outline: dict) -> dict:
    chapters = []
    for chapter in manifest_subject.get('chapters', []):
        node = guide_outline['nodesById'].get(chapter['id'])
        if not node:
            raise ValueError(f'{level} subject{subject_index} missing guide node for {chapter["id"]}')

        content_data = load_json(guide_content_path(guide_outline['key'], node['contentRef']))
        content = strip_title_heading(content_data.get('content') or '', chapter['title'])
        chapters.append({
            'id': chapter['id'],
            'title': chapter['title'],
            'subtopics': chapter.get('subtopics', []),
            'content': content,
            'content_format': content_data.get('contentFormat') or 'markdown',
            'page_range': chapter.get('page_range'),
            'source_pages': content_data.get('sourcePages', []),
        })

    return {
        'level': level,
        'subject': manifest_subject['subject'],
        'chapters': chapters,
    }


def build_question_seed(level: str, manifest_subject: dict, existing_path: Path) -> dict:
    seed = {
        'level': level,
        'subject': manifest_subject['subject'],
        'chapters': [
            {
                'id': chapter['id'],
                'title': chapter['title'],
                'questions': [],
            }
            for chapter in manifest_subject.get('chapters', [])
        ],
    }
    return merge_existing_questions(existing_path, seed)


def export_level(level: str) -> None:
    manifest = load_json(BASE / 'data' / level / 'toc_manifest.json')
    guide_outlines = load_json(BASE / 'frontend' / 'src' / 'generated' / 'guideOutlines.json')['guides']
    guide_dir = BASE / 'data' / level / 'guide'
    questions_dir = BASE / 'data' / level / 'questions'

    for subject_index, manifest_subject in enumerate(manifest.get('subjects', []), start=1):
        subject_id = manifest_subject['id']
        guide_outline = guide_outlines.get(subject_id)
        if not guide_outline:
            raise ValueError(f'{level} subject{subject_index} missing guide outline for {subject_id}')

        guide_seed = build_subject_seed(level, subject_index, manifest_subject, guide_outline)
        guide_path = guide_dir / f'subject{subject_index}_guide.json'
        write_json(guide_path, guide_seed)

        questions_path = questions_dir / f'subject{subject_index}_questions.json'
        question_seed = build_question_seed(level, manifest_subject, questions_path)
        write_json(questions_path, question_seed)

        total_questions = sum(len(chapter.get('questions', [])) for chapter in question_seed['chapters'])
        print(
            f'{level}/subject{subject_index}: '
            f'{len(guide_seed["chapters"])} guide chapters, {total_questions} questions'
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--level', default='中級', help='資料等級資料夾（預設: 中級）')
    parser.add_argument('--all-levels', action='store_true', help='匯出初級與中級')
    args = parser.parse_args()

    levels = ['初級', '中級'] if args.all_levels else [args.level]
    for level in levels:
        export_level(level)


if __name__ == '__main__':
    main()
