#!/usr/bin/env python3
"""Extract text from all iPAS PDF files."""

import os
import sys
import json
import logging
from pathlib import Path
import pdfplumber
import fitz  # PyMuPDF

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('/home/james/projects/ipas-test/logs/extraction.log'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

BASE = Path('/home/james/projects/ipas-test')
LEVEL = '初級'
OUT = BASE / 'data' / LEVEL / 'extracted'
PDF_DIR = BASE / 'data' / LEVEL / 'pdfs'

PDFS = {
    'guide1': PDF_DIR / 'AI應用規劃師(初級)-學習指引-科目1_人工智慧基礎概論1141203_20251222172144.pdf',
    'guide2': PDF_DIR / 'AI應用規劃師(初級)-學習指引-科目2_生成式AI應用與規劃114123_20251222172159.pdf',
    'exam1': PDF_DIR / '114年第四梯次初級AI應用規劃師第一科人工智慧基礎概論(當次試題公告114_20251226000442.pdf',
    'exam2': PDF_DIR / '114年第四梯次初級AI應用規劃師第二科生成式AI應用與規劃(當次試題公告114_20251226000507.pdf',
    'sample': PDF_DIR / 'iPAS AI應用規劃師初級能力鑑定-考試樣題(114年9月版)_20251226162246.pdf',
}


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


def save_text_file(key: str, pages: list[dict]):
    """Save extracted pages to a plain text file."""
    out_path = OUT / f'{key}.txt'
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


def save_json(key: str, pages: list[dict]):
    """Save structured data as JSON."""
    out_path = OUT / f'{key}.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({'key': key, 'pages': pages}, f, ensure_ascii=False, indent=2)
    log.info(f"Saved {out_path}")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    log.info("Starting PDF extraction")
    results = {}
    for key, pdf_path in PDFS.items():
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
        save_text_file(key, pages)
        save_json(key, pages)
        results[key] = {'pages': len(pages), 'chars': total_chars}
    
    summary_path = OUT / 'extraction_summary.json'
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    log.info(f"Extraction complete. Summary: {results}")


if __name__ == '__main__':
    main()
