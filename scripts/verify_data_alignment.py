#!/usr/bin/env python3
"""Verify that PDF references, manifest metadata, and app data stay aligned."""

import argparse
import ast
import contextlib
import io
import json
import sys
from pathlib import Path

import fitz  # PyMuPDF

BASE = Path('/home/james/projects/ipas-test')


def load_json(path: Path) -> dict:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def load_exam_pdf_map() -> dict[str, dict[str, str]]:
    """Read EXAM_PDFS_BY_LEVEL from extract_pdfs.py without importing it."""
    source = (BASE / 'scripts' / 'extract_pdfs.py').read_text(encoding='utf-8')
    module = ast.parse(source)
    for node in module.body:
        if (
            isinstance(node, ast.AnnAssign)
            and getattr(node.target, 'id', None) == 'EXAM_PDFS_BY_LEVEL'
        ):
            return ast.literal_eval(node.value)
    raise RuntimeError('EXAM_PDFS_BY_LEVEL not found in scripts/extract_pdfs.py')


def comparable_manifest(manifest: dict) -> dict:
    return {k: v for k, v in manifest.items() if k != 'generated_at'}


def compare_manifest(level: str, stored: dict, errors: list[str]) -> None:
    sys.path.insert(0, str(BASE / 'scripts'))
    import build_manifest  # noqa: PLC0415

    with contextlib.redirect_stdout(io.StringIO()):
        generated = build_manifest.build_manifest(level)
    if comparable_manifest(stored) != comparable_manifest(generated):
        errors.append(
            f'data/{level}/toc_manifest.json does not match current PDFs and '
            'scripts/build_manifest.py definitions. Run build_manifest.py and review the diff.'
        )


def check_pdf_bounds(level: str, manifest: dict, errors: list[str]) -> None:
    pdf_dir = BASE / 'data' / level / 'pdfs'
    for subject in manifest.get('subjects', []):
        pdf_path = pdf_dir / subject['pdf']
        if not pdf_path.exists():
            errors.append(f'Missing guide PDF for {subject["key"]}: {pdf_path.name}')
            continue

        with fitz.open(str(pdf_path)) as doc:
            total_pages = len(doc)
        for chapter in subject.get('chapters', []):
            page_range = chapter.get('page_range')
            if not page_range:
                errors.append(f'{chapter["id"]} has null page_range in toc_manifest.json')
                continue
            start, end = page_range
            if start < 0 or end < start or end >= total_pages:
                errors.append(
                    f'{chapter["id"]} page_range {page_range} is outside '
                    f'{subject["pdf"]} ({total_pages} pages)'
                )


def check_exam_pdfs(level: str, errors: list[str]) -> None:
    pdf_dir = BASE / 'data' / level / 'pdfs'
    for key, name in load_exam_pdf_map().get(level, {}).items():
        if not (pdf_dir / name).exists():
            errors.append(f'Missing exam PDF for {key}: {name}')


def check_chapter_file(
    path: Path,
    expected_subject: dict,
    errors: list[str],
    *,
    require_questions: bool = False,
) -> None:
    if not path.exists():
        errors.append(f'Missing data file: {path.relative_to(BASE)}')
        return

    data = load_json(path)
    chapters = data.get('chapters', [])
    expected_chapters = expected_subject.get('chapters', [])
    actual_ids = [chapter.get('id') for chapter in chapters]
    expected_ids = [chapter.get('id') for chapter in expected_chapters]
    if actual_ids != expected_ids:
        errors.append(
            f'{path.relative_to(BASE)} chapter IDs {actual_ids} do not match '
            f'toc_manifest.json {expected_ids}'
        )
        return

    for chapter, expected in zip(chapters, expected_chapters):
        if chapter.get('title') != expected.get('title'):
            errors.append(
                f'{path.relative_to(BASE)} title for {chapter["id"]!r} is '
                f'{chapter.get("title")!r}; expected {expected.get("title")!r}'
            )
        if path.parts[-2] == 'guide':
            for page in chapter.get('source_pages', []):
                image = page.get('image', '')
                if not image.startswith('/'):
                    errors.append(
                        f'{path.relative_to(BASE)} chapter {chapter["id"]} has '
                        f'invalid image path: {image}'
                    )
                    continue
                image_path = BASE / 'frontend' / 'public' / image.lstrip('/')
                if not image_path.exists():
                    errors.append(
                        f'{path.relative_to(BASE)} chapter {chapter["id"]} references '
                        f'missing PDF screenshot: {image_path.relative_to(BASE)}'
                    )
        if require_questions and not chapter.get('questions'):
            errors.append(f'{path.relative_to(BASE)} chapter {chapter["id"]} has no questions')


def check_app_data(level: str, manifest: dict, errors: list[str]) -> None:
    data_dir = BASE / 'data' / level
    for index, subject in enumerate(manifest.get('subjects', []), start=1):
        check_chapter_file(data_dir / 'guide' / f'subject{index}_guide.json', subject, errors)
        check_chapter_file(
            data_dir / 'questions' / f'subject{index}_questions.json',
            subject,
            errors,
            require_questions=level == '初級',
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Verify PDF references and generated app data against toc_manifest.json'
    )
    parser.add_argument('--level', default='初級', help='資料等級資料夾（預設: 初級）')
    args = parser.parse_args()

    manifest_path = BASE / 'data' / args.level / 'toc_manifest.json'
    if not manifest_path.exists():
        sys.exit(f'Missing manifest: {manifest_path}')

    manifest = load_json(manifest_path)
    errors: list[str] = []
    compare_manifest(args.level, manifest, errors)
    check_pdf_bounds(args.level, manifest, errors)
    check_exam_pdfs(args.level, errors)
    check_app_data(args.level, manifest, errors)

    if errors:
        print(f'Data alignment check failed for level "{args.level}":')
        for error in errors:
            print(f'  - {error}')
        sys.exit(1)

    total_chapters = sum(
        len(subject.get('chapters', [])) for subject in manifest.get('subjects', [])
    )
    print(
        f'Data alignment check passed for level "{args.level}": '
        f'{len(manifest.get("subjects", []))} subjects, {total_chapters} chapters.'
    )


if __name__ == '__main__':
    main()
