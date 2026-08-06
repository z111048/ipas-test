#!/usr/bin/env python3
"""把官方勘誤表的更正套用到兩條軌的頁面資料。

    輸入  data/{level}/errata_corrections.json（scripts/build_errata.py 產生）
    套用  data/{level}/pages_cache/{key}/page_NNN.json   （Track B：出題用）
          data/{level}/page_extract/{key}/pages/page_NNN.json（Track A：前端閱讀頁）

## 為什麼不改 guide_ocr

`data/{level}/guide_ocr/` 是 OCR 的忠實紀錄，要能對得回原稿印的內容——原稿印錯也照實還原
（這是 2026-08-06 的既定原則）。勘誤是「官方事後更正」，屬於**疊加層**，所以套在兩條軌的
轉接產物上，不動 SSOT。這樣重跑 OCR 轉接時勘誤會被沖掉，因此執行順序是：

    ocr_extract.py      → apply_errata.py → parse_guides.py          （Track B）
    merge_guide_ocr.py  → apply_errata.py → clean_pdf_page_text.py
                                          → export_guide_outline_data.py（Track A）

本腳本是**冪等**的：更正後的文字已經在位就跳過，可以重複執行。

## 定位方式

勘誤表給的是學習指引的**印刷頁碼**（如 3-25），先用 page_extract 的 `page_label`
換成 0-based 頁序，把替換範圍限縮在那一頁——這是安全的關鍵。
像「反饋→回饋」這種單字更正若全書套用會誤傷（例如原本就正確的其他段落），
限縮在勘誤指定的頁面才不會。

替換片段由 `原內容` 與 `更正後內容` 逐字 diff 產生，並向左右各展開 5 個字的上下文，
避免「反→回」這種一個字的片段在頁內誤命中。
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import unicodedata
from pathlib import Path

BASE = Path('/home/james/projects/ipas-test')

CONTEXT_CHARS = 5
PAGE_LABEL_NUMERIC = re.compile(r'^\d+-\d+$')


def normalize(text: str) -> str:
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', text))


def build_page_label_map(level: str, key: str) -> dict[str, int]:
    pages_dir = BASE / 'data' / level / 'page_extract' / key / 'pages'
    out: dict[str, int] = {}
    for path in sorted(pages_dir.glob('page_[0-9]*.json')):
        page = json.loads(path.read_text(encoding='utf-8'))
        label = (page.get('page_label') or '').strip()
        if label:
            out.setdefault(label, page['page_index'])
    return out


def context_pairs(original: str, corrected: str) -> list[tuple[str, str]]:
    """逐字 diff 後向兩側展開上下文，回傳 (要找的片段, 換成的片段)。

    相鄰的兩處更正各自展開上下文後會咬到對方。重疊代表它們屬於**同一處編輯**，
    必須合併成一段；不合併的話 `apply_pairs()` 會因為位置重疊而只採用其中一個，
    在「全有或全無」策略下整筆勘誤就被判定為不可套用。
    """
    matcher = difflib.SequenceMatcher(None, original, corrected, autojunk=False)
    spans: list[list[int]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            continue
        span = [
            max(0, i1 - CONTEXT_CHARS), min(len(original), i2 + CONTEXT_CHARS),
            max(0, j1 - CONTEXT_CHARS), min(len(corrected), j2 + CONTEXT_CHARS),
        ]
        if spans and span[0] <= spans[-1][1]:
            spans[-1][1] = max(spans[-1][1], span[1])
            spans[-1][3] = max(spans[-1][3], span[3])
        else:
            spans.append(span)

    pairs: list[tuple[str, str]] = []
    for a1, a2, b1, b2 in spans:
        old, new = original[a1:a2], corrected[b1:b2]
        if old.strip() and new.strip() and old != new:
            pairs.append((old, new))
    return pairs


def normalize_with_map(text: str) -> tuple[str, list[int]]:
    """回傳 (正規化後字串, 每個字元對應的原字串索引)。

    比對一定要兩邊都正規化：這些 PDF 大量使用全形標點與 CJK 相容字
    （「數」是 U+F969），只正規化其中一邊會全部落空。但替換又必須動到**原字串**，
    所以要保留索引對照才能把比對結果映射回去。
    """
    out: list[str] = []
    index_map: list[int] = []
    for i, ch in enumerate(text):
        folded = unicodedata.normalize('NFKC', ch)
        for c in folded:
            if c.isspace():
                continue
            out.append(c)
            index_map.append(i)
    return ''.join(out), index_map


def find_span(haystack: str, needle: str) -> tuple[int, int] | None:
    """在 haystack 中找 needle（兩邊皆正規化、忽略空白），回傳原字串的 [start, end)。"""
    norm_hay, index_map = normalize_with_map(haystack)
    norm_needle, _ = normalize_with_map(needle)
    if not norm_needle:
        return None
    pos = norm_hay.find(norm_needle)
    if pos < 0:
        return None
    start = index_map[pos]
    end = index_map[pos + len(norm_needle) - 1] + 1
    return start, end


def apply_pairs(text: str, pairs: list[tuple[str, str]]) -> tuple[str, list[tuple[str, str]]]:
    """一次掃描把多個片段套進同一段文字。

    先在**原始文字**上把所有片段的位置找齊，再由後往前替換：
    這樣前面的替換不會動到後面片段的比對基準，也不必擔心片段之間上下文重疊。
    位置重疊的片段只採用第一個（勘誤表本來就不該對同一段文字給兩種改法）。
    """
    if not text:
        return text, []

    located: list[tuple[int, int, tuple[str, str]]] = []
    for pair in pairs:
        old, new = pair
        if find_span(text, new) is not None:
            continue  # 已經是更正後的樣子，冪等跳過
        span = find_span(text, old)
        if span is None:
            continue
        located.append((span[0], span[1], pair))

    located.sort(key=lambda item: item[0])
    accepted: list[tuple[int, int, tuple[str, str]]] = []
    for start, end, pair in located:
        if accepted and start < accepted[-1][1]:
            continue
        accepted.append((start, end, pair))

    for start, end, (_old, new) in reversed(accepted):
        text = text[:start] + new + text[end:]
    return text, [pair for _s, _e, pair in accepted]


def apply_to_pages_cache(level: str, key: str, idx: int, pairs: list[tuple[str, str]]) -> int:
    path = BASE / 'data' / level / 'pages_cache' / key / f'page_{idx:03d}.json'
    if not path.exists():
        return 0
    page = json.loads(path.read_text(encoding='utf-8'))
    markdown, applied = apply_pairs(page['markdown'], pairs)
    if len(applied) != len(pairs):
        # 全有或全無：只套用一部分會讓段落變成新舊混雜，比不動更糟
        return 0
    if applied:
        page['markdown'] = markdown
        path.write_text(json.dumps(page, ensure_ascii=False, indent=2), encoding='utf-8')
    return len(applied)


def apply_to_page_extract(level: str, key: str, idx: int, pairs: list[tuple[str, str]]) -> int:
    path = BASE / 'data' / level / 'page_extract' / key / 'pages' / f'page_{idx:03d}.json'
    if not path.exists():
        return 0
    page = json.loads(path.read_text(encoding='utf-8'))
    applied = 0

    # 片段可能落在不同 block，逐個 block 掃描；套用過的片段要從待辦移除，
    # 否則同一處更正會在每個 block 各套一次。
    remaining = list(pairs)
    for block in page.get('blocks') or []:
        if not remaining:
            break
        block['text'], done = apply_pairs(block.get('text') or '', remaining)
        applied += len(done)
        remaining = [p for p in remaining if p not in done]
    for table in page.get('tables') or []:
        for row in table.get('rows') or []:
            for i, cell in enumerate(row):
                if not remaining:
                    break
                row[i], done = apply_pairs(str(cell), remaining)
                applied += len(done)
                remaining = [p for p in remaining if p not in done]

    if applied != len(pairs):
        return 0  # 全有或全無，同 apply_to_pages_cache
    if applied:
        # `text` 是整頁串接，同步更新才不會與 blocks 不一致
        page['text'] = '\n'.join(b.get('text') or '' for b in page.get('blocks') or [])
        path.write_text(json.dumps(page, ensure_ascii=False, indent=2), encoding='utf-8')
    return applied


def run(level: str, dry_run: bool) -> None:
    src = BASE / 'data' / level / 'errata_corrections.json'
    if not src.exists():
        raise SystemExit(f'找不到 {src.relative_to(BASE)}——先跑 scripts/build_errata.py')
    entries = json.loads(src.read_text(encoding='utf-8'))

    label_maps: dict[str, dict[str, int]] = {}
    report = {'applied_b': 0, 'applied_a': 0, 'entries_ok': 0, 'entries_partial': 0,
              'entries_none': 0, 'entries_skipped': 0}
    unresolved: list[dict] = []

    for entry in entries:
        key = entry.get('key')
        label = (entry.get('page_label') or '').strip()
        if not key or not PAGE_LABEL_NUMERIC.match(label):
            # 「職能基準」頁這種非頁碼定位，自動化定不了位
            report['entries_skipped'] += 1
            unresolved.append({**entry, 'reason': '頁碼欄不是印刷頁碼，需人工處理'})
            continue

        if key not in label_maps:
            label_maps[key] = build_page_label_map(level, key)
        idx = label_maps[key].get(label)
        if idx is None:
            report['entries_skipped'] += 1
            unresolved.append({**entry, 'reason': f'page_extract 找不到頁碼 {label}'})
            continue

        pairs = context_pairs(entry['original'], entry['corrected'])
        if not pairs:
            report['entries_skipped'] += 1
            continue

        if dry_run:
            b = a = 0
            pc = BASE / 'data' / level / 'pages_cache' / key / f'page_{idx:03d}.json'
            pe = BASE / 'data' / level / 'page_extract' / key / 'pages' / f'page_{idx:03d}.json'
            pc_text = json.loads(pc.read_text(encoding='utf-8'))['markdown'] if pc.exists() else ''
            pe_text = ' '.join(
                blk.get('text') or ''
                for blk in (json.loads(pe.read_text(encoding='utf-8')).get('blocks') or [])
            ) if pe.exists() else ''
            for old, _new in pairs:
                b += find_span(pc_text, old) is not None
                a += find_span(pe_text, old) is not None
        else:
            b = apply_to_pages_cache(level, key, idx, pairs)
            a = apply_to_page_extract(level, key, idx, pairs)

        report['applied_b'] += b
        report['applied_a'] += a
        if b == len(pairs) and a == len(pairs):
            report['entries_ok'] += 1
        elif b or a:
            report['entries_partial'] += 1
            unresolved.append({**entry, 'reason': f'部分片段未命中（B {b}/{len(pairs)}、A {a}/{len(pairs)}）'})
        else:
            report['entries_none'] += 1
            unresolved.append({**entry, 'reason': '片段完全未命中，需人工處理'})

    print(f'=== {level}（共 {len(entries)} 筆勘誤）')
    print(f'  全部片段套用成功 {report["entries_ok"]} 筆 / 部分 {report["entries_partial"]} 筆 / '
          f'完全未命中 {report["entries_none"]} 筆 / 無法自動定位 {report["entries_skipped"]} 筆')
    print(f'  片段層級：Track B 套用 {report["applied_b"]} 處、Track A 套用 {report["applied_a"]} 處')

    if not dry_run:
        out = BASE / 'data' / level / 'errata_unresolved.json'
        out.write_text(json.dumps(unresolved, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'  需人工處理的 {len(unresolved)} 筆 → {out.relative_to(BASE)}')


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--level', choices=['初級', '中級'], help='預設兩級都跑')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    for level in ([args.level] if args.level else ['初級', '中級']):
        run(level, args.dry_run)
    if args.dry_run:
        print('\n(dry-run，未寫檔)')


if __name__ == '__main__':
    main()
