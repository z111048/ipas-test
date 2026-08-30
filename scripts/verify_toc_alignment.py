#!/usr/bin/env python3
"""用學習指引 PDF 自帶的目錄，對帳 toc_manifest.json 的章節邊界與標題。

為什麼目錄是可信的來源：內文頁的章節標題在 PDF 文字層是**空的**（標題被畫成圖片，
這也是當初要跑 OCR 的原因），但目錄頁的標題與頁碼是真正的文字，中級三本還帶內部
跳頁連結。因此目錄是唯一可機讀的標題／邊界權威。

檢查四項：
  1. start_page 是否等於目錄印的頁碼（如 3-40）
  2. 章節標題是否與目錄一致（忽略空白與大小寫）
  3. page_range[0] 那一頁是否真的印著 start_page（直接驗證邊界頁本身）
  4. page_range[0] 是否等於目錄連結的目標頁（僅中級，初級 PDF 無連結）

已知例外見 KNOWN_EXCEPTIONS。用法：
    uv run python3 scripts/verify_toc_alignment.py --level 中級
    uv run python3 scripts/verify_toc_alignment.py --all-levels
不一致時 exit code 為 1，可當閘門用。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import fitz

BASE = Path(__file__).resolve().parents[1]
LEVELS = ('初級', '中級')

# 官方 PDF 自身的缺陷，不是我們解析錯：這條目錄連結指向封面 p1，
# 但同一行印的頁碼 3-9 與內文頁 p16 一致（p16 確實是「3.2 線性代數之機器學習基礎應用」）。
KNOWN_EXCEPTIONS = {
    ('中級', 'guide3', 'mid-s3c2', 'link_target'): 'PDF 目錄連結損壞（指向封面 p1），印刷頁碼與內文均正確',
}

# 目錄行："3.2 電腦視覺技術與應用 ......... 3-40"，行尾可能接著下一篇的「第四章」
TOC_LINE_RE = re.compile(r'(\d+\.\d+)\s+(.+?)[\.\s]{4,}(\d+\s*-\s*\d+)')
LABEL_RE = re.compile(r'\d+\s*-\s*\d+')


def squash(text: str) -> str:
    return re.sub(r'\s', '', text).lower()


def parse_toc(doc: fitz.Document) -> dict[str, dict]:
    """從目錄頁抽出 {正規化標題: {number, title, label}}。"""
    for page_index in range(min(8, len(doc))):
        entries: dict[str, dict] = {}
        for line in doc[page_index].get_text('text').split('\n'):
            match = TOC_LINE_RE.search(line)
            if not match:
                continue
            title = match.group(2).strip()
            entries[squash(title)] = {
                'number': match.group(1),
                'title': title,
                'label': re.sub(r'\s', '', match.group(3)),
            }
        if entries:
            return entries
    return {}


def parse_links(doc: fitz.Document) -> dict[str, int]:
    """從目錄頁的內部跳頁連結抽出 {印刷頁碼: 目標頁(1-indexed)}。"""
    targets: dict[str, int] = {}
    for page in doc:
        words = page.get_text('words')
        for link in page.get_links():
            if link.get('kind') != fitz.LINK_GOTO:
                continue
            rect = fitz.Rect(link['from'])
            line = ' '.join(
                w[4] for w in words if not (w[3] < rect.y0 - 2 or w[1] > rect.y1 + 2)
            )
            match = LABEL_RE.search(line)
            if match:
                targets[re.sub(r'\s', '', match.group(0))] = link['page'] + 1
    return targets


def check_level(level: str) -> list[str]:
    manifest = json.loads(
        (BASE / 'data' / level / 'toc_manifest.json').read_text(encoding='utf-8')
    )
    problems: list[str] = []
    checked = 0

    for subject in manifest['subjects']:
        pdf_path = BASE / 'data' / level / 'pdfs' / subject['pdf']
        if not pdf_path.exists():
            problems.append(f'{level}/{subject["key"]}: 找不到 PDF {subject["pdf"]}')
            continue

        doc = fitz.open(str(pdf_path))
        toc = parse_toc(doc)
        links = parse_links(doc)
        if not toc:
            problems.append(f'{level}/{subject["key"]}: 目錄頁解析不到任何條目')
            continue

        for chapter in subject['chapters']:
            checked += 1
            cid = chapter['id']
            where = f'{level}/{subject["key"]} {cid}'
            entry = toc.get(squash(chapter['title']))

            # 標題對不上時，改用 start_page 找同一條目，才能區分「標題不同」與「整條缺失」
            if entry is None:
                entry = next(
                    (e for e in toc.values() if e['label'] == chapter['start_page']), None
                )
                if entry is None:
                    problems.append(f'{where}: 目錄找不到對應條目（標題與頁碼皆無法匹配）')
                    continue
                problems.append(
                    f'{where}: 標題與目錄不符 我們={chapter["title"]!r} 目錄={entry["title"]!r}'
                )

            if chapter['start_page'] != entry['label']:
                problems.append(
                    f'{where}: start_page 與目錄不符 我們={chapter["start_page"]} 目錄={entry["label"]}'
                )

            first_page = chapter['page_range'][0]
            if not 0 <= first_page < len(doc):
                problems.append(f'{where}: page_range 起始頁 {first_page} 超出 PDF 頁數 {len(doc)}')
                continue

            # 邊界頁本身是否印著該章的頁碼
            printed = {
                re.sub(r'\s', '', m) for m in LABEL_RE.findall(doc[first_page].get_text('text'))
            }
            if chapter['start_page'] not in printed:
                problems.append(
                    f'{where}: 邊界頁 p{first_page + 1} 未印出 {chapter["start_page"]}（實際 {sorted(printed) or "無"}）'
                )

            target = links.get(entry['label'])
            if target is not None and target != first_page + 1:
                key = (level, subject['key'], cid, 'link_target')
                if key not in KNOWN_EXCEPTIONS:
                    problems.append(
                        f'{where}: 目錄連結目標 p{target} ≠ 我們的邊界 p{first_page + 1}'
                    )

    print(f'{level}: 檢查 {checked} 章，問題 {len(problems)} 項')
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--level', help='資料等級資料夾（初級/中級）')
    parser.add_argument('--all-levels', action='store_true', help='檢查所有等級')
    args = parser.parse_args()

    if not args.level and not args.all_levels:
        parser.error('請指定 --level LEVEL 或 --all-levels')

    problems: list[str] = []
    for level in (LEVELS if args.all_levels else [args.level]):
        problems.extend(check_level(level))

    if problems:
        print('\n不一致：')
        for problem in problems:
            print(f'  - {problem}')
        return 1

    print('\n全部章節與 PDF 目錄一致。')
    if KNOWN_EXCEPTIONS:
        print('已知例外（不列為問題）：')
        for (lv, key, cid, kind), why in KNOWN_EXCEPTIONS.items():
            print(f'  - {lv}/{key} {cid} [{kind}]：{why}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
