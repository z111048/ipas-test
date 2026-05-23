#!/usr/bin/env python3
"""Merge available Codex mock exam outputs into reviewable subject files."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from run_codex_question_batch_generation import validate_batch
from validate_codex_chapter_mock_output import validate_file

BASE = Path('/home/james/projects/ipas-test')
LEVEL = '中級'
SUBJECT_NUMBER = {'mid-s1': 1, 'mid-s2': 2, 'mid-s3': 3}
DEFAULT_BATCH_DIR = BASE / 'data' / LEVEL / 'pipeline' / 'codex_question_batch_prompts'
DEFAULT_CHAPTER_DIR = BASE / 'data' / LEVEL / 'pipeline' / 'codex_chapter_mock_prompts'
DEFAULT_OUT_DIR = BASE / 'data' / LEVEL / 'pipeline' / 'codex_mock_exam_generated'


def load_json(path: Path) -> Any:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def full_chapter_output(chapter_dir: Path, subject_order: int, chapter_order: int, chapter_id: str) -> Path:
    return chapter_dir / 'results' / f'{subject_order:02d}_{chapter_order:02d}_{chapter_id}.json'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch-dir', type=Path, default=DEFAULT_BATCH_DIR)
    parser.add_argument('--chapter-dir', type=Path, default=DEFAULT_CHAPTER_DIR)
    parser.add_argument('--out-dir', type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    batch_dir = args.batch_dir if args.batch_dir.is_absolute() else BASE / args.batch_dir
    chapter_dir = args.chapter_dir if args.chapter_dir.is_absolute() else BASE / args.chapter_dir
    out_dir = args.out_dir if args.out_dir.is_absolute() else BASE / args.out_dir
    summary = load_json(batch_dir / 'summary.json')
    manifest = load_json(BASE / 'data' / LEVEL / 'toc_manifest.json')
    subjects = {subject['id']: subject for subject in manifest['subjects']}

    by_chapter: dict[str, list[dict]] = defaultdict(list)
    for batch in summary['batches']:
        by_chapter[batch['chapter_id']].append(batch)

    report = {'level': LEVEL, 'subjects': []}
    subject_order_by_id = {
        subject_id: index
        for index, subject_id in enumerate(summary['generation_order'], start=1)
    }

    for subject_id in summary['generation_order']:
        subject = subjects[subject_id]
        subject_no = SUBJECT_NUMBER[subject_id]
        merged_questions: list[dict] = []
        chapters_status = []

        for chapter_order, chapter in enumerate(subject['chapters'], start=1):
            chapter_id = chapter['id']
            batches = sorted(by_chapter[chapter_id], key=lambda item: item['first_question'])
            expected_count = sum(batch['count'] for batch in batches)
            chapter_questions: list[dict] = []
            source = None
            errors: list[str] = []

            batch_outputs = [BASE / batch['output'] for batch in batches]
            if batch_outputs and all(path.exists() and not validate_batch(path, batch) for path, batch in zip(batch_outputs, batches)):
                source = 'batch'
                for path in batch_outputs:
                    chapter_questions.extend(load_json(path)['questions'])
            else:
                path = full_chapter_output(chapter_dir, subject_order_by_id[subject_id], chapter_order, chapter_id)
                if path.exists():
                    errors = validate_file(path)
                    if not errors:
                        source = 'chapter'
                        chapter_questions = load_json(path)['questions']

            complete = len(chapter_questions) == expected_count
            if complete:
                merged_questions.extend(chapter_questions)
            chapters_status.append({
                'chapter_id': chapter_id,
                'title': chapter['title'],
                'expected_count': expected_count,
                'actual_count': len(chapter_questions),
                'complete': complete,
                'source': source,
                'errors': errors,
            })

        payload = {
            'level': LEVEL,
            'subject_id': subject_id,
            'subject': subject['subject'],
            'target_total': 100,
            'actual_total': len(merged_questions),
            'complete': len(merged_questions) == 100,
            'questions': merged_questions,
            'chapters': chapters_status,
        }
        out_path = out_dir / f'subject{subject_no}_codex100_partial.json'
        write_json(out_path, payload)
        report['subjects'].append({
            'subject_id': subject_id,
            'output': out_path.relative_to(BASE).as_posix(),
            'actual_total': len(merged_questions),
            'complete': payload['complete'],
            'missing_chapters': [item['chapter_id'] for item in chapters_status if not item['complete']],
        })
        print(f'Wrote {out_path.relative_to(BASE)}: {len(merged_questions)}/100 questions')

    write_json(out_dir / 'merge_report.json', report)


if __name__ == '__main__':
    main()
