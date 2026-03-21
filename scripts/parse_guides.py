#!/usr/bin/env python3
"""Parse study guide PDFs into chapter-structured JSON."""

import json
import re
from pathlib import Path

BASE = Path('/home/james/projects/ipas-test')
OUT = BASE / 'data' / '初級'

# Chapter definitions with known in-document start page numbers from TOC.
# Split boundary = last page of previous chapter = next chapter's start_page - 1.
GUIDES = {
    1: {
        'key': 'guide1',
        'subject': '科目一：人工智慧基礎概論',
        'chapters': [
            {
                'id': 's1c1',
                'title': '人工智慧概念',
                'start_page': '3-1',
                'subtopics': [
                    'AI定義與分類(分析型/預測型/生成型)',
                    'AI應用領域',
                    'AI治理概念',
                    'EU AI Act風險層級',
                    'Human-in/over/out-of-the-loop',
                ],
            },
            {
                'id': 's1c2',
                'title': '資料處理與分析概念',
                'start_page': '3-24',
                'subtopics': [
                    '資料類型(結構化/半結構化/非結構化)',
                    'Big Data 5V',
                    'ETL流程',
                    '資料清洗(遺缺值/離群值/重複值)',
                    '資料正規化',
                    '統計分析方法',
                    '資料隱私(GDPR/PDPA)',
                ],
            },
            {
                'id': 's1c3',
                'title': '機器學習概念',
                'start_page': '3-33',
                'subtopics': [
                    '監督/非監督/半監督/強化學習',
                    'Overfitting/Underfitting',
                    'Bias-Variance Tradeoff',
                    'Regularization L1/L2',
                    '決策樹/KNN/SVM/K-means/PCA',
                    '特徵工程(One-hot/正規化/特徵交叉)',
                    '神經網路與深度學習',
                    '損失函數',
                ],
            },
            {
                'id': 's1c4',
                'title': '鑑別式AI與生成式AI概念',
                'start_page': '3-48',
                'subtopics': [
                    '鑑別式AI基本原理',
                    '生成式AI基本原理',
                    'LLM與Transformer',
                    '擴散模型',
                    'RAG檢索增強生成',
                    '幻覺問題(Hallucination)',
                    '可解釋AI(XAI)',
                    '模型優化(剪枝/量化/蒸餾)',
                ],
            },
        ],
    },
    2: {
        'key': 'guide2',
        'subject': '科目二：生成式AI應用與規劃',
        'chapters': [
            {
                'id': 's2c1',
                'title': 'No Code / Low Code概念',
                'start_page': '3-1',
                'subtopics': [
                    'No Code平台特性與應用',
                    'Low Code平台特性',
                    'AI民主化',
                    '優勢與限制',
                    '平台範例(Bubble/Power Apps/Zapier)',
                ],
            },
            {
                'id': 's2c2',
                'title': '生成式AI應用領域與工具使用',
                'start_page': '3-17',
                'subtopics': [
                    '文字/圖像/語音生成工具',
                    '提示工程(Zero-shot/Few-shot/CoT/Role Prompting)',
                    'RAG架構',
                    'AI Agent設計',
                    'APE自動提示工程',
                    'MCP協議',
                    'A2A架構',
                ],
            },
            {
                'id': 's2c3',
                'title': '生成式AI導入評估規劃',
                'start_page': '3-31',
                'subtopics': [
                    '業務需求評估',
                    'ROI評估方法',
                    '導入規劃步驟',
                    '聯邦學習與隱私保護',
                    'AI風險管理(幻覺/偏見/安全)',
                    'AI治理框架',
                    'Guardrails防護機制',
                    'Fine-tuning vs RAG策略',
                ],
            },
        ],
    },
}


def load_guide_text(key: str) -> str:
    """Concatenate all page texts from guide JSON (skip blank pages)."""
    with open(OUT / 'extracted' / f'{key}.json', encoding='utf-8') as f:
        data = json.load(f)
    parts = []
    for p in data['pages']:
        text = p.get('text', '').strip()
        if text:
            parts.append(text)
    return '\n'.join(parts)


def prev_page_label(start_page: str) -> str:
    """Given '3-24', return '3-23' (last page of the preceding chapter)."""
    prefix, num_str = start_page.rsplit('-', 1)
    return f'{prefix}-{int(num_str) - 1}'


def split_into_chapters(raw_text: str, chapters: list[dict]) -> list[str]:
    """
    Split raw_text at chapter boundaries.

    Each boundary is the in-document page label of the last page of the
    preceding chapter (i.e. next chapter's start page minus 1).
    """
    # Find split positions: right after each boundary label
    split_positions = []
    for ch in chapters[1:]:
        boundary = prev_page_label(ch['start_page'])
        pattern = r'\b' + re.escape(boundary) + r'\b'
        m = re.search(pattern, raw_text)
        if m:
            split_positions.append(m.end())
        else:
            print(f"  WARN: boundary '{boundary}' not found in text")
            split_positions.append(None)

    segments = []
    prev = 0
    for pos in split_positions:
        if pos is None:
            segments.append(raw_text[prev:])
            prev = len(raw_text)
        else:
            segments.append(raw_text[prev:pos])
            prev = pos
    segments.append(raw_text[prev:])
    return segments


def clean_segment(text: str) -> str:
    """Remove structural noise from a chapter text segment."""
    lines = []
    for line in text.split('\n'):
        # Strip Unicode Private Use Area chars (e.g. \uf07d from PDF font artifacts)
        stripped = re.sub(r'[\ue000-\uf8ff]', '', line).strip()
        s = stripped
        # Drop TOC dot-leader lines
        if re.search(r'\.{5,}', s):
            continue
        # Drop in-document page number lines like "3-1", "A-1"
        if re.match(r'^[A-Z\d]+-\d+$', s):
            continue
        # Drop repeated chapter running headers (may have PUA prefix chars)
        if re.search(r'第[一二三四五六七八九十]+章', s):
            continue
        # Drop [TABLES] markers
        if s == '[TABLES]':
            continue
        # Drop short separator-like lines (|, =====, -----)
        if re.match(r'^[|\-=]{3,}$', s):
            continue
        # Use the PUA-stripped version as the clean line content
        # Drop standalone section-number/heading lines like "3.1", "3.2 No code / Low code"
        if re.match(r'^3\.\d', s) and len(s) < 40:
            continue
        # Drop isolated short PUA-stripped lines that are clearly garbled headers
        # (e.g. standalone "AI" or "1. AI" left after stripping chapter titles)
        if re.match(r'^(?:AI|MCP|LLM|RAG)\s*$', s):
            continue
        if re.match(r'^\d+\.\s+AI\s*$', s):
            continue
        lines.append(stripped)

    cleaned = '\n'.join(lines)
    # Collapse runs of 3+ blank lines to 2
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()


def parse_guide(subject_num: int) -> dict:
    cfg = GUIDES[subject_num]
    key = cfg['key']
    print(f'Processing {key}...')

    raw_text = load_guide_text(key)
    chapters = cfg['chapters']
    segments = split_into_chapters(raw_text, chapters)

    result_chapters = []
    for i, (ch, seg) in enumerate(zip(chapters, segments)):
        # For the first chapter, skip the preface/TOC intro pages that
        # appear before the actual chapter content (intro ends at page '2-1').
        if i == 0:
            # Find the standalone page number '2-1' (on its own line),
            # not the one embedded in TOC dot-leader lines.
            m = re.search(r'(?:^|\n)(2-1)\n', seg)
            if m:
                seg = seg[m.end():]
        content = clean_segment(seg)
        result_chapters.append({
            'id': ch['id'],
            'title': ch['title'],
            'subtopics': ch['subtopics'],
            'content': content,
        })
        print(f"  {ch['id']} ({ch['title']}): {len(content)} chars")

    return {
        'subject': cfg['subject'],
        'chapters': result_chapters,
    }


def main():
    guide_dir = OUT / 'guide'
    guide_dir.mkdir(exist_ok=True)

    for n in [1, 2]:
        data = parse_guide(n)
        out_path = guide_dir / f'subject{n}_guide.json'
        out_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8'
        )
        print(f'Saved {out_path}')


if __name__ == '__main__':
    main()
