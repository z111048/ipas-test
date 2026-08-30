#!/usr/bin/env python3
"""Extract text from all iPAS PDF files."""

import os
import sys
import json
import logging
from pathlib import Path
import pdfplumber
import fitz  # PyMuPDF

from resource_catalog import exam_pdf_maps, reference_pdf_maps

BASE = Path(__file__).resolve().parents[1]
(BASE / 'logs').mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(BASE / 'logs' / 'extraction.log'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# Compatibility exports for scripts that historically imported these names.
# The committed data/resource_catalog.json is the only metadata source.
EXAM_PDFS_BY_LEVEL: dict[str, dict[str, str]] = exam_pdf_maps()
REFERENCE_PDFS_BY_LEVEL: dict[str, dict[str, str]] = reference_pdf_maps()


def all_pdf_names_for_level(level: str) -> dict[str, str]:
    result = dict(EXAM_PDFS_BY_LEVEL.get(level, {}))
    result.update(REFERENCE_PDFS_BY_LEVEL.get(level, {}))
    return result


def extract_with_pdfplumber(pdf_path: Path) -> list[dict]:
    """Extract pages with pdfplumber (better layout)."""
    pages = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text(x_tolerance=3, y_tolerance=3) or ''
                # Try table extraction
                tables = []
                try:
                    for tbl in page.extract_tables():
                        if tbl:
                            tables.append(tbl)
                except Exception:
                    pass
                pages.append({
                    'page': i + 1,
                    'text': text.strip(),
                    'tables': tables,
                    'width': float(page.width),
                    'height': float(page.height),
                })
    except Exception as e:
        log.error(f"pdfplumber failed on {pdf_path.name}: {e}")
    return pages


def extract_with_pymupdf(pdf_path: Path) -> list[dict]:
    """Fallback extraction using PyMuPDF."""
    pages = []
    try:
        doc = fitz.open(str(pdf_path))
        for i, page in enumerate(doc):
            text = page.get_text('text')
            blocks = page.get_text('blocks')
            pages.append({
                'page': i + 1,
                'text': text.strip(),
                'blocks': [
                    {'x0': b[0], 'y0': b[1], 'x1': b[2], 'y1': b[3], 'text': b[4].strip()}
                    for b in blocks if b[4].strip()
                ],
            })
        doc.close()
    except Exception as e:
        log.error(f"PyMuPDF failed on {pdf_path.name}: {e}")
    return pages


def save_text_file(key: str, pages: list[dict], out_dir: Path):
    """Save extracted pages to a plain text file."""
    out_path = out_dir / f'{key}.txt'
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(f"=== {key} ===\n\n")
        for p in pages:
            f.write(f"\n{'='*60}\n")
            f.write(f"PAGE {p['page']}\n")
            f.write(f"{'='*60}\n\n")
            f.write(p['text'])
            f.write('\n')
            if p.get('tables'):
                f.write('\n[TABLES]\n')
                for tbl in p['tables']:
                    for row in tbl:
                        if row:
                            f.write(' | '.join(str(c) if c else '' for c in row) + '\n')
                    f.write('\n')
    log.info(f"Saved {out_path} ({len(pages)} pages)")
    return out_path


def save_json(key: str, pages: list[dict], out_dir: Path):
    """Save structured data as JSON."""
    out_path = out_dir / f'{key}.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({'key': key, 'pages': pages}, f, ensure_ascii=False, indent=2)
    log.info(f"Saved {out_path}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Extract text from iPAS PDF files')
    parser.add_argument('--level', default='初級',
                        help='資料等級資料夾（預設: 初級）')
    args = parser.parse_args()

    pdf_dir = BASE / 'data' / args.level / 'pdfs'
    out_dir = BASE / 'data' / args.level / 'extracted'
    out_dir.mkdir(parents=True, exist_ok=True)

    # Build PDFs dict: guide PDFs from toc_manifest + exam/reference PDFs.
    pdfs: dict[str, Path] = {}
    manifest_path = BASE / 'data' / args.level / 'toc_manifest.json'
    if manifest_path.exists():
        with open(manifest_path, encoding='utf-8') as f:
            manifest = json.load(f)
        for subj in manifest['subjects']:
            pdfs[subj['key']] = pdf_dir / subj['pdf']
    for key, name in all_pdf_names_for_level(args.level).items():
        pdfs[key] = pdf_dir / name

    log.info(f"Starting PDF extraction for level '{args.level}'")
    results = {}
    for key, pdf_path in pdfs.items():
        if not pdf_path.exists():
            log.warning(f"File not found: {pdf_path}")
            continue
        log.info(f"Processing {key}: {pdf_path.name}")
        pages = extract_with_pdfplumber(pdf_path)
        if not pages or all(not p['text'] for p in pages):
            log.warning(f"pdfplumber got no text for {key}, trying PyMuPDF")
            pages = extract_with_pymupdf(pdf_path)
        total_chars = sum(len(p['text']) for p in pages)
        log.info(f"  {key}: {len(pages)} pages, {total_chars} chars")
        save_text_file(key, pages, out_dir)
        save_json(key, pages, out_dir)
        results[key] = {'pages': len(pages), 'chars': total_chars}

    summary_path = out_dir / 'extraction_summary.json'
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    log.info(f"Extraction complete. Summary: {results}")


if __name__ == '__main__':
    main()
