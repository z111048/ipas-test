#!/usr/bin/env python3
"""把官方學習指引勘誤表的 OCR 結果解析成結構化 JSON。

    來源  data/{level}/guide_ocr/errata/pages/page_NNNN/page_NNNN.md
    輸出  data/{level}/errata_corrections.json

勘誤表每頁一張四欄表：頁碼 / 行數段落 / 原內容 / 更正後內容。
「科目：…」標題出現在某一頁，之後的表格都屬於該科目，直到下一個標題為止。

欄位對齊要靠表頭的 colspan 決定邊界——初級科目1 那張表的「原內容」「更正後內容」
各佔 3 欄（因為裡面塞了一個 Type I/II 錯誤的巢狀表），直接按索引取欄位會全部錯位。

輸出的 `page_label` 是學習指引 PDF 的印刷頁碼（如 3-25），不是 PDF 實體頁序；
`scripts/apply_errata.py` 靠它定位要修哪一頁。
"""

from __future__ import annotations

import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]

# 勘誤表的「科目」標題 → 本專案的 guide key
SUBJECT_TO_KEY = {
    '人工智慧基礎概論': 'guide1',
    '生成式AI應用與規劃': 'guide2',
    '人工智慧技術應用與規劃': 'guide1',
    '大數據處理分析與應用': 'guide2',
    '機器學習技術與應用': 'guide3',
}

SUBJECT_RE = re.compile(r'科目[一二三]?[：:]\s*([^<\n]{4,30})')

# 合法的頁碼欄：學習指引的印刷頁碼「3-25」，或非頁碼的指代如「「職能基準」頁」。
PAGE_LABEL_RE = re.compile(r'^\s*(\d+\s*-\s*\d+|.{0,12}頁)\s*$')


class SpanTableParser(HTMLParser):
    """解析 <table>，保留每格的 colspan/rowspan（欄位邊界要靠 colspan 判斷）。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[dict]] = []
        self._row: list[dict] | None = None
        self._cell: list[str] | None = None
        self._attrs: dict[str, int] = {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'tr':
            self._row = []
        elif tag in ('td', 'th') and self._row is not None:
            self._cell = []
            self._attrs = {
                'colspan': int(a.get('colspan') or 1),
                'rowspan': int(a.get('rowspan') or 1),
            }

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self._cell is not None and self._row is not None:
            text = ''.join(self._cell).replace('\\n', '\n')
            text = re.sub(r'[ \t]+', ' ', text)
            text = re.sub(r'\s*\n\s*', '\n', text).strip()
            self._row.append({'text': text, **self._attrs})
            self._cell = None
        elif tag == 'tr' and self._row is not None:
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def column_groups(header: list[dict]) -> list[tuple[int, int]]:
    """由表頭的 colspan 算出每個欄位群組佔用的欄位範圍 [start, end)。"""
    groups = []
    cursor = 0
    for cell in header:
        span = cell.get('colspan') or 1
        groups.append((cursor, cursor + span))
        cursor += span
    return groups


def cells_to_columns(row: list[dict], groups: list[tuple[int, int]]) -> list[str]:
    """把一列的儲存格攤平到欄位索引，再依表頭群組合併。"""
    flat: list[str] = []
    for cell in row:
        span = cell.get('colspan') or 1
        flat.extend([cell['text']] + [''] * (span - 1))

    out = []
    for start, end in groups:
        parts = [p for p in flat[start:end] if p]
        out.append(' '.join(parts).strip())
    # 欄位數不足（rowspan 造成的短列）就補空字串
    while len(out) < len(groups):
        out.append('')
    return out


def parse_level(level: str) -> list[dict]:
    pages_dir = BASE / 'data' / level / 'guide_ocr' / 'errata' / 'pages'
    if not pages_dir.exists():
        raise SystemExit(f'找不到勘誤表 OCR：{pages_dir}')

    entries: list[dict] = []
    current_key: str | None = None

    for md_path in sorted(pages_dir.glob('page_[0-9]*/page_[0-9]*.md')):
        page_no = int(re.search(r'page_(\d+)\.md$', md_path.name).group(1))
        raw = md_path.read_text(encoding='utf-8')

        found = SUBJECT_RE.search(raw)
        if found:
            name = re.sub(r'\s+', '', found.group(1))
            key = SUBJECT_TO_KEY.get(name)
            if key is None:
                raise SystemExit(f'{level} 勘誤表第 {page_no} 頁出現未知科目「{name}」——'
                                 f'請更新 SUBJECT_TO_KEY')
            current_key = key

        for table_html in re.findall(r'<table.*?</table>', raw, re.S):
            parser = SpanTableParser()
            parser.feed(table_html)
            if not parser.rows:
                continue
            header, *body = parser.rows
            head_text = [c['text'] for c in header]
            if '頁碼' not in ' '.join(head_text):
                continue  # 不是勘誤表格
            groups = column_groups(header)
            if len(groups) < 4:
                continue

            last_page_label = ''
            last_locator = ''
            for row in body:
                cols = cells_to_columns(row, groups)
                page_label, locator, original, corrected = cols[0], cols[1], cols[2], cols[3]

                # 勘誤內容本身可能是一張巢狀表（初級 3-27 的 Type I/II 錯誤表），
                # 它的子列會被攤成「頁碼欄不是頁碼」的假列——併回上一筆，不要當新勘誤。
                if not PAGE_LABEL_RE.match(page_label) and entries:
                    tail = entries[-1]
                    for field, value in (('original', ' '.join(c for c in cols if c)),):
                        if value:
                            tail[field] = f'{tail[field]}\n{value}'.strip()
                    continue

                # rowspan 讓後續列少了前兩欄，沿用上一列的值
                page_label = page_label or last_page_label
                locator = locator or last_locator
                last_page_label, last_locator = page_label, locator
                if not original and not corrected:
                    continue
                entries.append({
                    'level': level,
                    'key': current_key,
                    'errata_page': page_no,
                    'page_label': page_label,
                    'locator': locator,
                    'original': original,
                    'corrected': corrected,
                })
    return entries


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--level', choices=['初級', '中級'], help='預設兩級都跑')
    args = ap.parse_args()

    levels = [args.level] if args.level else ['初級', '中級']
    for level in levels:
        entries = parse_level(level)
        out = BASE / 'data' / level / 'errata_corrections.json'
        out.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding='utf-8')
        by_key: dict[str, int] = {}
        for e in entries:
            by_key[e['key'] or '?'] = by_key.get(e['key'] or '?', 0) + 1
        print(f'{level}: {len(entries)} 筆勘誤 → {out.relative_to(BASE)}  {by_key}')


if __name__ == '__main__':
    main()
