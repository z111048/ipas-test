#!/usr/bin/env python3
"""Build toc_manifest.json — the single source of truth for chapter definitions.

Embeds all subject/chapter metadata and resolves PDF page ranges via PyMuPDF.
Run whenever chapter definitions or PDFs change.

Usage:
  uv run python3 scripts/build_manifest.py
  uv run python3 scripts/build_manifest.py --dry-run   # print manifest, don't write
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit('PyMuPDF not found. Run: uv sync')

BASE = Path('/home/james/projects/ipas-test')
DATA = BASE / 'data' / '初級'
PDF_DIR = DATA / 'pdfs'
MANIFEST_PATH = DATA / 'toc_manifest.json'

# ── Single source of truth for chapter definitions ────────────────────────────
# This is the ONLY place in the codebase where chapter metadata is hardcoded.
# All other scripts load toc_manifest.json at runtime.

GUIDES = {
    1: {
        'id': 's1',
        'key': 'guide1',
        'pdf': 'AI應用規劃師(初級)-學習指引-科目1_人工智慧基礎概論1141203_20251222172144.pdf',
        'subject': '科目一：人工智慧基礎概論',
        'chapters': [
            {
                'id': 's1c1', 'title': '人工智慧概念', 'start_page': '3-1',
                'subtopics': ['AI定義與分類(分析型/預測型/生成型)', 'AI應用領域', 'AI治理概念',
                              'EU AI Act風險層級', 'Human-in/over/out-of-the-loop'],
            },
            {
                'id': 's1c2', 'title': '資料處理與分析概念', 'start_page': '3-24',
                'subtopics': ['資料類型(結構化/半結構化/非結構化)', 'Big Data 5V', 'ETL流程',
                              '資料清洗(遺缺值/離群值/重複值)', '資料正規化', '統計分析方法',
                              '資料隱私(GDPR/PDPA)'],
            },
            {
                'id': 's1c3', 'title': '機器學習概念', 'start_page': '3-33',
                'subtopics': ['監督/非監督/半監督/強化學習', 'Overfitting/Underfitting',
                              'Bias-Variance Tradeoff', 'Regularization L1/L2',
                              '決策樹/KNN/SVM/K-means/PCA', '特徵工程(One-hot/正規化/特徵交叉)',
                              '神經網路與深度學習', '損失函數'],
            },
            {
                'id': 's1c4', 'title': '鑑別式AI與生成式AI概念', 'start_page': '3-48',
                'subtopics': ['鑑別式AI基本原理', '生成式AI基本原理', 'LLM與Transformer',
                              '擴散模型', 'RAG檢索增強生成', '幻覺問題(Hallucination)',
                              '可解釋AI(XAI)', '模型優化(剪枝/量化/蒸餾)'],
            },
        ],
    },
    2: {
        'id': 's2',
        'key': 'guide2',
        'pdf': 'AI應用規劃師(初級)-學習指引-科目2_生成式AI應用與規劃114123_20251222172159.pdf',
        'subject': '科目二：生成式AI應用與規劃',
        'chapters': [
            {
                'id': 's2c1', 'title': 'No Code / Low Code概念', 'start_page': '3-1',
                'subtopics': ['No Code平台特性與應用', 'Low Code平台特性', 'AI民主化',
                              '優勢與限制', '平台範例(Bubble/Power Apps/Zapier)'],
            },
            {
                'id': 's2c2', 'title': '生成式AI應用領域與工具使用', 'start_page': '3-17',
                'subtopics': ['文字/圖像/語音生成工具', '提示工程(Zero-shot/Few-shot/CoT/Role Prompting)',
                              'RAG架構', 'AI Agent設計', 'APE自動提示工程', 'MCP協議', 'A2A架構'],
            },
            {
                'id': 's2c3', 'title': '生成式AI導入評估規劃', 'start_page': '3-31',
                'subtopics': ['業務需求評估', 'ROI評估方法', '導入規劃步驟',
                              '聯邦學習與隱私保護', 'AI風險管理(幻覺/偏見/安全)',
                              'AI治理框架', 'Guardrails防護機制', 'Fine-tuning vs RAG策略'],
            },
        ],
    },
}


# ── Page mapping helpers ──────────────────────────────────────────────────────

def build_page_label_map(pdf_path: Path) -> dict[str, int]:
    """Map in-document page labels (e.g. '3-1') to 0-based page indices.

    Uses last occurrence so actual content pages win over TOC references.
    """
    doc = fitz.open(str(pdf_path))
    mapping: dict[str, int] = {}
    for i, page in enumerate(doc):
        for m in re.finditer(r'\b(\d+-\d+)\b', page.get_text()):
            mapping[m.group(1)] = i
    doc.close()
    return mapping


def find_page_index(label: str, label_map: dict[str, int]) -> int:
    if label in label_map:
        return label_map[label]
    prefix, num_str = label.rsplit('-', 1)
    next_label = f'{prefix}-{int(num_str) + 1}'
    if next_label in label_map:
        return label_map[next_label] - 1
    raise ValueError(f"Cannot find page index for '{label}'")


def resolve_page_ranges(
    chapters: list[dict], label_map: dict[str, int], total_pages: int
) -> list[tuple[int, int]]:
    """Return (start_idx, end_idx) inclusive 0-based for each chapter."""
    start_indices = [find_page_index(ch['start_page'], label_map) for ch in chapters]
    ranges = []
    for i, start in enumerate(start_indices):
        end = start_indices[i + 1] - 1 if i + 1 < len(start_indices) else total_pages - 1
        ranges.append((start, end))
    return ranges


# ── Manifest builder ──────────────────────────────────────────────────────────

def build_manifest() -> dict:
    subjects = []
    for subject_num in sorted(GUIDES.keys()):
        cfg = GUIDES[subject_num]
        pdf_path = PDF_DIR / cfg['pdf']

        if not pdf_path.exists():
            print(f'  [WARN] PDF not found, page_range will be null: {pdf_path.name}')
            page_ranges = [None] * len(cfg['chapters'])
        else:
            doc = fitz.open(str(pdf_path))
            total_pages = len(doc)
            doc.close()
            label_map = build_page_label_map(pdf_path)
            try:
                ranges = resolve_page_ranges(cfg['chapters'], label_map, total_pages)
                page_ranges = [[s, e] for s, e in ranges]
            except ValueError as exc:
                print(f'  [WARN] {exc} — page_range will be null for subject {subject_num}')
                page_ranges = [None] * len(cfg['chapters'])

        chapters_out = []
        for ch, pr in zip(cfg['chapters'], page_ranges):
            chapters_out.append({
                'id': ch['id'],
                'title': ch['title'],
                'start_page': ch['start_page'],
                'page_range': pr,
                'subtopics': ch['subtopics'],
            })
            range_str = f'{pr[0]}–{pr[1]}' if pr else 'N/A'
            print(f'  {ch["id"]} ({ch["title"]}): pages {range_str}')

        subjects.append({
            'id': cfg['id'],
            'key': cfg['key'],
            'pdf': cfg['pdf'],
            'subject': cfg['subject'],
            'chapters': chapters_out,
        })

    return {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'subjects': subjects,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Build toc_manifest.json from embedded chapter definitions'
    )
    parser.add_argument('--dry-run', action='store_true',
                        help='Print manifest JSON without writing to disk')
    args = parser.parse_args()

    print('Building toc_manifest.json...')
    manifest = build_manifest()

    if args.dry_run:
        print('\n--- toc_manifest.json (dry run) ---')
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    else:
        MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                 encoding='utf-8')
        total_chapters = sum(len(s['chapters']) for s in manifest['subjects'])
        print(f'\nSaved {MANIFEST_PATH}')
        print(f'  {len(manifest["subjects"])} subjects, {total_chapters} chapters')


if __name__ == '__main__':
    main()
