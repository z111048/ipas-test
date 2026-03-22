#!/usr/bin/env python3
"""Build toc_manifest.json — the single source of truth for chapter definitions.

Embeds all subject/chapter metadata and resolves PDF page ranges via PyMuPDF.
Run whenever chapter definitions or PDFs change.

Usage:
  uv run python3 scripts/build_manifest.py                    # default: 初級
  uv run python3 scripts/build_manifest.py --level 初級
  uv run python3 scripts/build_manifest.py --level 中級
  uv run python3 scripts/build_manifest.py --dry-run          # print manifest, don't write
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

# ── Single source of truth for chapter definitions ────────────────────────────
# This is the ONLY place in the codebase where chapter metadata is hardcoded.
# All other scripts load toc_manifest.json at runtime.
#
# To add a new level (e.g. '中級'):
#   1. Fill in the subjects dict below with the correct PDF names and chapters.
#   2. Run: uv run python3 scripts/build_manifest.py --level 中級

GUIDES_BY_LEVEL: dict[str, dict[int, dict]] = {
    '初級': {
        1: {
            'id': 's1',
            'key': 'guide1',
            'pdf': 'AI應用規劃師(初級)-學習指引-科目1_人工智慧基礎概論1141203_20251222172144.pdf',
            'subject': '科目一：人工智慧基礎概論',
            'chapters': [
                {
                    'id': 's1c1', 'title': '人工智慧概念', 'start_page': '3-1',
                    'subtopics': ['AI定義與分類(分析型/預測型/生成型)', 'AI應用領域',
                                  'AI實現的多層次架構(技術底層/開發應用/實際運用)',
                                  '演算法基礎與決策支援'],
                },
                {
                    'id': 's1c2', 'title': '資料處理與分析概念', 'start_page': '3-5',
                    'subtopics': ['資料類型(結構化/半結構化/非結構化)', '資料蒐集方法',
                                  '資料清洗(遺缺值/離群值/重複值)', '資料正規化與標準化',
                                  '統計分析指標(平均數/中位數/標準差)', '探索性資料分析(EDA)',
                                  '異常值檢測'],
                },
                {
                    'id': 's1c3', 'title': '機器學習概念', 'start_page': '3-33',
                    'subtopics': ['監督式/非監督式/強化學習', '迴歸與分類任務',
                                  '聚類與降維技術(K-means/PCA)', '模型解釋性與透明性',
                                  '資料品質與偏見問題'],
                },
                {
                    'id': 's1c4', 'title': '鑑別式AI與生成式AI概念', 'start_page': '3-48',
                    'subtopics': ['鑑別式AI原理與模型(SVM/邏輯迴歸/神經網路)',
                                  '生成對抗網路(GAN)原理', '擴散模型',
                                  '生成式AI多模態內容生成', '提示工程基礎',
                                  '鑑別式AI與生成式AI的協同應用'],
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
                    'subtopics': ['AI民主化與應用普及', 'No Code與Low Code的適用場景區分',
                                  '視覺化介面與拖放操作特性', '生成式AI對No/Low Code的增強功能',
                                  '平台選擇與評估的關鍵因素', '導入風險與挑戰管理'],
                },
                {
                    'id': 's2c2', 'title': '生成式AI應用領域與工具使用', 'start_page': '3-17',
                    'subtopics': ['生成式AI技術架構與核心機制', '訓練資料處理(標記化/向量化)',
                                  '推理機制與採樣策略(溫度/Top-k/Nucleus)',
                                  '技術演進(GAN/VAE/Transformer/RLHF)',
                                  '大型語言模型與多模態生成', '提示工程與生成內容控制'],
                },
                {
                    'id': 's2c3', 'title': '生成式AI導入評估規劃', 'start_page': '3-31',
                    'subtopics': ['業務痛點識別與應用場景分析', '資料品質與基礎設施評估',
                                  '分階段導入策略與試點驗證(POC)',
                                  '員工技能培訓與數位轉型文化',
                                  '風險評估與合規管理', 'ROI評估方法'],
                },
            ],
        },
    },
    '中級': {
        # 等 PDF 到位後填入，格式與初級相同：
        # 1: { 'id': 's1', 'key': 'guide1', 'pdf': '...', 'subject': '...', 'chapters': [...] },
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

def build_manifest(level: str) -> dict:
    guides = GUIDES_BY_LEVEL.get(level, {})
    if not guides:
        print(f'  [WARN] No chapter definitions for level "{level}" — writing empty manifest')
        return {
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'subjects': [],
        }

    pdf_dir = BASE / 'data' / level / 'pdfs'
    subjects = []

    for subject_num in sorted(guides.keys()):
        cfg = guides[subject_num]
        pdf_path = pdf_dir / cfg['pdf']

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
    parser.add_argument('--level', default='初級',
                        choices=list(GUIDES_BY_LEVEL),
                        help='資料等級（預設: 初級）')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print manifest JSON without writing to disk')
    args = parser.parse_args()

    manifest_path = BASE / 'data' / args.level / 'toc_manifest.json'

    print(f'Building toc_manifest.json for level "{args.level}"...')
    manifest = build_manifest(args.level)

    if args.dry_run:
        print('\n--- toc_manifest.json (dry run) ---')
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    else:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                 encoding='utf-8')
        total_chapters = sum(len(s['chapters']) for s in manifest['subjects'])
        print(f'\nSaved {manifest_path}')
        print(f'  {len(manifest["subjects"])} subjects, {total_chapters} chapters')


if __name__ == '__main__':
    main()
