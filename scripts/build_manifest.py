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
                    'id': 's1c2', 'title': '資料處理與分析概念', 'start_page': '3-24',
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
        1: {
            'id': 'mid-s1',
            'key': 'guide1',
            'pdf': 'AI應用規劃師(中級)-學習指引-科目1人工智慧技術應用規劃_20251222101833.pdf',
            'subject': '中級科目一：人工智慧技術應用與規劃',
            'chapters': [
                {
                    'id': 'mid-s1c1', 'title': '自然語言處理技術與應用', 'start_page': '3-3',
                    'subtopics': ['NLP基礎概念', '自然語言理解與生成', '詞向量與語言模型', '文本分類與情感分析'],
                },
                {
                    'id': 'mid-s1c2', 'title': '電腦視覺技術與應用', 'start_page': '3-40',
                    'subtopics': ['影像處理與辨識', 'CNN與物件偵測', '影像分割', '電腦視覺實務應用'],
                },
                {
                    'id': 'mid-s1c3', 'title': '生成式AI技術與應用', 'start_page': '3-59',
                    'subtopics': ['生成模型', '大型語言模型', '擴散模型', '生成式AI應用情境'],
                },
                {
                    'id': 'mid-s1c4', 'title': '多模態人工智慧應用', 'start_page': '3-73',
                    'subtopics': ['多模態資料整合', '圖文模型', '語音與影像融合', '多模態應用規劃'],
                },
                {
                    'id': 'mid-s1c5', 'title': 'AI導入評估', 'start_page': '4-3',
                    'subtopics': ['需求盤點', '導入可行性', '資料與技術成熟度', '效益與風險評估'],
                },
                {
                    'id': 'mid-s1c6', 'title': 'AI導入規劃', 'start_page': '4-15',
                    'subtopics': ['導入路徑', 'POC規劃', '資源與時程', '組織協作'],
                },
                {
                    'id': 'mid-s1c7', 'title': 'AI風險管理', 'start_page': '4-29',
                    'subtopics': ['模型風險', '資料隱私', '資安與合規', '治理與監控'],
                },
                {
                    'id': 'mid-s1c8', 'title': '數據準備與模型選擇', 'start_page': '5-2',
                    'subtopics': ['資料準備', '特徵工程', '模型選型', '評估指標'],
                },
                {
                    'id': 'mid-s1c9', 'title': 'AI技術系統集成與部署', 'start_page': '5-14',
                    'subtopics': ['系統整合', '模型部署', 'MLOps', '監控與維運'],
                },
            ],
        },
        2: {
            'id': 'mid-s2',
            'key': 'guide2',
            'pdf': 'AI應用規劃師(中級)-學習指引-科目2大數據處理分析與應用_20251222101850.pdf',
            'subject': '中級科目二：大數據處理分析與應用',
            'chapters': [
                {
                    'id': 'mid-s2c1', 'title': '敘述性統計與資料摘要技術', 'start_page': '3-2',
                    'subtopics': ['集中趨勢', '離散量度', '分佈形狀', '資料摘要'],
                },
                {
                    'id': 'mid-s2c2', 'title': '機率分佈與資料分佈模型', 'start_page': '3-13',
                    'subtopics': ['機率模型', '常見分佈', '抽樣分佈', '參數估計'],
                },
                {
                    'id': 'mid-s2c3', 'title': '假設檢定與統計推論', 'start_page': '3-23',
                    'subtopics': ['假設檢定', '信賴區間', 'p值', '統計推論'],
                },
                {
                    'id': 'mid-s2c4', 'title': '數據收集與清理', 'start_page': '4-2',
                    'subtopics': ['資料來源', '資料品質', '清理流程', '缺失與異常處理'],
                },
                {
                    'id': 'mid-s2c5', 'title': '數據儲存與管理', 'start_page': '4-9',
                    'subtopics': ['資料庫', '資料倉儲', '資料湖', '資料治理'],
                },
                {
                    'id': 'mid-s2c6', 'title': '數據處理技術與工具', 'start_page': '4-20',
                    'subtopics': ['批次處理', '串流處理', 'ETL/ELT', '大數據工具'],
                },
                {
                    'id': 'mid-s2c7', 'title': '統計學在大數據中的應用', 'start_page': '5-2',
                    'subtopics': ['統計建模', '推論應用', '抽樣與估計', '不確定性分析'],
                },
                {
                    'id': 'mid-s2c8', 'title': '常見的大數據分析方法', 'start_page': '5-10',
                    'subtopics': ['分類', '分群', '關聯分析', '預測分析'],
                },
                {
                    'id': 'mid-s2c9', 'title': '數據可視化工具', 'start_page': '5-29',
                    'subtopics': ['視覺化原則', '圖表選擇', '儀表板', '分析工具'],
                },
                {
                    'id': 'mid-s2c10', 'title': '大數據與機器學習', 'start_page': '6-2',
                    'subtopics': ['機器學習資料需求', '特徵工程', '資料管線', '模型訓練'],
                },
                {
                    'id': 'mid-s2c11', 'title': '大數據在鑑別式AI中的應用', 'start_page': '6-14',
                    'subtopics': ['分類模型', '迴歸模型', '鑑別式模型資料應用', '評估與部署'],
                },
                {
                    'id': 'mid-s2c12', 'title': '大數據在生成式AI中的應用', 'start_page': '6-25',
                    'subtopics': ['生成模型資料需求', '語料處理', '向量資料', '生成式AI資料管線'],
                },
                {
                    'id': 'mid-s2c13', 'title': '大數據隱私保護、安全與合規', 'start_page': '6-30',
                    'subtopics': ['隱私保護', '資料安全', '合規管理', '資料治理'],
                },
            ],
        },
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
