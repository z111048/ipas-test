#!/usr/bin/env python3
"""Render source PDF pages referenced by guide JSON into frontend/public."""

import argparse
import json
from pathlib import Path

import fitz  # PyMuPDF

BASE = Path('/home/james/projects/ipas-test')


def load_manifest(level: str) -> dict:
    path = BASE / 'data' / level / 'toc_manifest.json'
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def referenced_pages(level: str, subject_num: int) -> set[int]:
    path = BASE / 'data' / level / 'guide' / f'subject{subject_num}_guide.json'
    with path.open(encoding='utf-8') as f:
        guide = json.load(f)
    pages: set[int] = set()
    for chapter in guide.get('chapters', []):
        for page in chapter.get('source_pages', []):
            pages.add(page['index'])
    return pages


def render_subject(level: str, subject_num: int, scale: float, force: bool) -> None:
    manifest = load_manifest(level)
    subject = manifest['subjects'][subject_num - 1]
    key = subject['key']
    pdf_path = BASE / 'data' / level / 'pdfs' / subject['pdf']
    out_dir = BASE / 'frontend' / 'public' / 'guide-pages' / level / key
    out_dir.mkdir(parents=True, exist_ok=True)

    pages = referenced_pages(level, subject_num)
    doc = fitz.open(str(pdf_path))
    matrix = fitz.Matrix(scale, scale)
    rendered = skipped = 0
    for idx in sorted(pages):
        out_path = out_dir / f'page_{idx:03d}.png'
        if out_path.exists() and not force:
            skipped += 1
            continue
        pix = doc[idx].get_pixmap(matrix=matrix, alpha=False)
        pix.save(str(out_path))
        rendered += 1
    doc.close()
    print(f'{key}: rendered {rendered}, skipped {skipped}, output {out_dir}')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--level', default='初級', help='資料等級資料夾（預設: 初級）')
    parser.add_argument('--subject', type=int, help='只處理指定科目')
    parser.add_argument('--all', action='store_true', help='處理所有科目')
    parser.add_argument('--scale', type=float, default=1.2, help='render scale (default: 1.2)')
    parser.add_argument('--force', action='store_true', help='overwrite existing images')
    args = parser.parse_args()

    if not args.subject and not args.all:
        parser.error('Specify --subject N or --all')

    manifest = load_manifest(args.level)
    subjects = range(1, len(manifest.get('subjects', [])) + 1) if args.all else [args.subject]
    for subject_num in subjects:
        render_subject(args.level, subject_num, args.scale, args.force)


if __name__ == '__main__':
    main()
