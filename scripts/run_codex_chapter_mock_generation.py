#!/usr/bin/env python3
"""Run per-chapter Codex mock exam generation with validation and resume support."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from validate_codex_chapter_mock_output import validate_file

BASE = Path('/home/james/projects/ipas-test')
DEFAULT_RUN_DIR = BASE / 'data' / '中級' / 'pipeline' / 'codex_chapter_mock_prompts'
SCHEMA_PATH = BASE / 'schemas' / 'middle_mock_exam_chapter.schema.json'


def load_json(path: Path) -> dict:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def run_codex(prompt_path: Path, output_path: Path, timeout_seconds: int) -> bool:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with prompt_path.open(encoding='utf-8') as prompt_file:
        proc = subprocess.run(
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
            text=True,
            cwd=BASE,
            timeout=timeout_seconds,
            check=False,
        )

    if proc.returncode == 0:
        return True
    if output_path.exists():
        print(f'WARN codex exited {proc.returncode}, but output exists: {output_path.relative_to(BASE)}')
        return True
    print(f'FAIL codex exited {proc.returncode}: {output_path.relative_to(BASE)}')
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument('--start-index', type=int, default=1, help='1-based chapter index from summary.json')
    parser.add_argument('--limit', type=int, default=None)
    parser.add_argument('--timeout', type=int, default=300)
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()

    run_dir = args.run_dir if args.run_dir.is_absolute() else BASE / args.run_dir
    summary = load_json(run_dir / 'summary.json')
    chapters = summary['chapters']
    start = max(args.start_index - 1, 0)
    selected = chapters[start:]
    if args.limit is not None:
        selected = selected[:args.limit]

    completed = 0
    failed = 0
    skipped = 0
    for offset, chapter in enumerate(selected, start=start + 1):
        output_path = BASE / chapter['output']
        prompt_path = BASE / chapter['prompt']
        label = f'{offset:02d}/{len(chapters):02d} {chapter["chapter_id"]} {chapter["title"]}'

        if output_path.exists() and not args.force:
            errors = validate_file(output_path)
            if not errors:
                skipped += 1
                print(f'SKIP {label}: valid output exists')
                continue
            print(f'RETRY {label}: existing output failed validation')

        print(f'RUN {label}: target {chapter["count"]} questions')
        try:
            ok = run_codex(prompt_path, output_path, args.timeout)
        except subprocess.TimeoutExpired:
            ok = output_path.exists()
            print(f'WARN timeout after {args.timeout}s: {output_path.relative_to(BASE)}')

        if ok and output_path.exists():
            errors = validate_file(output_path)
            if errors:
                failed += 1
                print(f'FAIL {label}: validation errors')
                for error in errors:
                    print(f'  - {error}')
            else:
                completed += 1
                print(f'PASS {label}: {chapter["count"]} questions')
        else:
            failed += 1

    print(f'Done: completed={completed}, skipped={skipped}, failed={failed}')
    raise SystemExit(1 if failed else 0)


if __name__ == '__main__':
    main()
