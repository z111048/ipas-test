#!/usr/bin/env python3
"""（已退場，2026-08-29）把 guide JSON 的 source_pages 渲染成 PNG。

產物 `frontend/public/guide-pages/`（89 檔 12.5 MB）經窮舉比對確認**前端從未引用**
（`parse_guides.py:369-373` 的註解自己就寫明了），已從版控刪除。
前端讀的是 `guideContent` 與 `pdfGallery`，兩者都指向 `pdf-assets/`。

保留檔案是為了保留歷史與 `_page_asset_path` 那段慣例說明，**但 main() 會直接拒絕執行**——
README.md 與 AGENTS.md 曾把它列為現役步驟，照著跑一次就會把刪掉的 89 檔全部長回來。
真的要重新啟用，先確認前端有消費者，再把下面的 sys.exit 拿掉。
"""

import argparse
import json
import sys
from pathlib import Path

import fitz  # PyMuPDF

BASE = Path(__file__).resolve().parents[1]


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
    print(
        '這支腳本已於 2026-08-29 退場，不會執行。\n'
        '\n'
        '原因：產物 frontend/public/guide-pages/ 前端從未引用，89 檔 12.5 MB 已從版控刪除。\n'
        '前端的學習指引原頁截圖走的是 pdf-assets/（由 export_pdf_image_gallery.py 產生）。\n'
        '\n'
        '若你是照 README.md 或 AGENTS.md 的步驟跑到這裡：那兩份文件的該段已過期，\n'
        '以 playbook/pipeline-reference.md 為準（CLAUDE.md 有寫明衝突時的優先序）。',
        file=sys.stderr,
    )
    sys.exit(2)


def _retired_main() -> None:
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
