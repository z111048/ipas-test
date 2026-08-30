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

BASE = Path(__file__).resolve().parents[1]

CONTEXT_CHARS = 5
PAGE_LABEL_NUMERIC = re.compile(r'^\d+-\d+$')


def normalize(text: str) -> str:
    # 比對時一併忽略大小寫：中級的文字層印的是「chatGTP」，勘誤表寫「ChatGTP」，
    # 只差一個字母大小寫就會整筆定位失敗。替換文字取自勘誤表，大小寫會一併修正。
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', text)).casefold()


def build_page_label_map(level: str, key: str) -> dict[str, int]:
    pages_dir = BASE / 'data' / level / 'page_extract' / key / 'pages'
    out: dict[str, int] = {}
    for path in sorted(pages_dir.glob('page_[0-9]*.json')):
        page = json.loads(path.read_text(encoding='utf-8'))
        label = (page.get('page_label') or '').strip()
        if label:
            out.setdefault(label, page['page_index'])
    return out


def unique_page_for_text(level: str, key: str, needle: str) -> int | None:
    """在整本書裡找 needle，只有恰好一頁命中才回傳頁序，否則 None。

    給「『職能基準』頁」這種沒有印刷頁碼的勘誤用。唯一性是安全閥——
    命中多頁就代表定位不明確，寧可交給人工也不要改錯地方。
    """
    pages_dir = BASE / 'data' / level / 'page_extract' / key / 'pages'
    hits: list[int] = []
    for path in sorted(pages_dir.glob('page_[0-9]*.json')):
        page = json.loads(path.read_text(encoding='utf-8'))
        joined = '\n'.join(b.get('text') or '' for b in page.get('blocks') or [])
        for table in page.get('tables') or []:
            for row in table.get('rows') or []:
                joined += '\n' + '\n'.join(str(c) for c in row)
        if find_span(joined, needle) is not None:
            hits.append(page['page_index'])
        if len(hits) > 1:
            return None
    return hits[0] if len(hits) == 1 else None


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
        for c in folded.casefold():
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


def mask_normalized_spans(text: str, needle: str) -> tuple[str, int]:
    """Mask every normalized ``needle`` match without changing raw indices.

    In insertion-style errata the damaged text is a prefix of the corrected
    text.  Searching the corrected page for the damaged text would therefore
    find it *inside the correction* and append the supplement again.  An
    equal-length, non-whitespace mask keeps ``find_span()`` offsets aligned
    with the original text while making completed spans unavailable to the
    subsequent damaged-text search.
    """
    marker = next(
        (
            candidate
            for candidate in ("\x00", "\x01", "\ue000", "\uf8ff")
            if candidate not in text and candidate not in needle
        ),
        None,
    )
    if marker is None:
        raise ValueError("Unable to allocate a normalized-span mask marker")

    protected = text
    count = 0
    while True:
        span = find_span(protected, needle)
        if span is None:
            return protected, count
        start, end = span
        protected = protected[:start] + marker * (end - start) + protected[end:]
        count += 1


# 純刪除超過這個字數就視為不安全。「多模態多模態→多模態」這種去重複只刪 3 字，
# 是合法的；初級 3-27 那筆是勘誤表巢狀表格 OCR 壞掉，會一口氣刪掉近百字的表格內容。
UNSAFE_DELETION_CHARS = 30


def is_pure_deletion(old: str, new: str) -> bool:
    """更正後的文字只是原文的開頭、且刪掉的量大到不像是單純的錯字修正。"""
    old_n, new_n = normalize(old), normalize(new)
    return (bool(new_n) and old_n.startswith(new_n)
            and len(old_n) - len(new_n) > UNSAFE_DELETION_CHARS)


def apply_pairs(text: str, pairs: list[tuple[str, str]]
                ) -> tuple[str, list[tuple[str, str]], list[tuple[str, str]]]:
    """一次掃描把多個片段套進同一段文字。

    先在**原始文字**上把所有片段的位置找齊，再由後往前替換：
    這樣前面的替換不會動到後面片段的比對基準，也不必擔心片段之間上下文重疊。
    位置重疊的片段只採用第一個（勘誤表本來就不該對同一段文字給兩種改法）。

    回傳 (新文字, 這次真的改到的片段, 已滿足的片段)。**已滿足 ⊇ 這次改到的**——
    「已經是更正後的樣子」也算滿足，否則重跑時「全有或全無」會把冪等跳過誤判成失敗。
    """
    if not text:
        return text, [], []

    already: list[tuple[str, str]] = []
    located: list[tuple[int, int, tuple[str, str]]] = []
    for pair in pairs:
        old, new = pair
        if is_pure_deletion(old, new):
            # 只刪不增的片段幾乎都是勘誤表本身的表格 OCR 壞掉造成的，照套會把講義
            # 內容整段刪掉。而且它的「更正後文字」是原文的開頭，冪等檢查一定命中，
            # 會把「還沒改」誤判成「已改好」（初級 3-27 就踩到）。一律不套、也不算已滿足。
            continue
        search_text = text
        corrected_count = 0
        normalized_old = normalize(old)
        normalized_new = normalize(new)
        if normalized_old and normalized_old in normalized_new:
            search_text, corrected_count = mask_normalized_spans(text, new)

        span = find_span(search_text, old)
        if span is None:
            # 原文不在、更正後的文字在 → 早就套好了
            if corrected_count or find_span(text, new) is not None:
                already.append(pair)
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
    applied = [pair for _s, _e, pair in accepted]
    return text, applied, already + applied


def apply_across_blocks(blocks: list[dict], pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """處理跨 block 邊界的片段：整頁串接後定位，再把替換分攤回受影響的 block。

    做法是把新文字整段塞進第一個受影響的 block，其餘受影響的部分刪掉。
    這會讓那幾個 block 的文字重新分配（bbox 不變），但 `positioned_page_items`
    是照 y 座標排序後串接，讀起來的結果一樣。
    """
    applied: list[tuple[str, str]] = []
    for old, new in pairs:
        # 用換行串接才不會讓相鄰 block 的頭尾黏成不存在的詞
        joined = '\n'.join(b.get('text') or '' for b in blocks)
        if find_span(joined, new) is not None:
            continue
        span = find_span(joined, old)
        if span is None:
            continue
        start, end = span

        cursor = 0
        first = True
        for block in blocks:
            text = block.get('text') or ''
            block_start, block_end = cursor, cursor + len(text)
            cursor = block_end + 1  # +1 是串接用的換行
            if block_end <= start or block_start >= end:
                continue
            local_start = max(0, start - block_start)
            local_end = min(len(text), end - block_start)
            block['text'] = text[:local_start] + (new if first else '') + text[local_end:]
            first = False
        applied.append((old, new))
    return applied


def apply_to_ocr_formulas(level: str, key: str, idx: int, pairs: list[tuple[str, str]]) -> int:
    """公式的更正要改在 ocr_formulas，不是 page_extract。

    Track A 的公式在 page_extract 裡是被文字層攤平的亂碼，LaTeX 是由
    `merge_guide_ocr.py` 抽出 `ocr_formulas/` 之後再注入的。所以像
    「Recall 的分母 TP+FP 應為 TP+FN」這種勘誤，改 page_extract 是改不到的。
    """
    path = BASE / 'data' / level / 'ocr_formulas' / key / f'page_{idx:03d}.json'
    if not path.exists():
        return 0
    page = json.loads(path.read_text(encoding='utf-8'))
    changed = 0
    for formula in page.get('blocks') or []:
        latex = formula.get('latex') or ''
        new_latex, applied, _satisfied = apply_pairs(latex, pairs)
        if applied:
            formula['latex'] = new_latex
            changed += len(applied)
    if changed:
        path.write_text(json.dumps(page, ensure_ascii=False, indent=2), encoding='utf-8')
    return changed


def apply_to_pages_cache(level: str, key: str, idx: int, pairs: list[tuple[str, str]]) -> int:
    path = BASE / 'data' / level / 'pages_cache' / key / f'page_{idx:03d}.json'
    if not path.exists():
        return 0
    page = json.loads(path.read_text(encoding='utf-8'))
    markdown, applied, satisfied = apply_pairs(page['markdown'], pairs)
    if len(satisfied) != len(pairs):
        # 全有或全無：只套用一部分會讓段落變成新舊混雜，比不動更糟
        return 0
    if applied:
        page['markdown'] = markdown
        path.write_text(json.dumps(page, ensure_ascii=False, indent=2), encoding='utf-8')
    # 回傳「已滿足」而不是「這次改了幾處」，重跑時報表才會一致（冪等）
    return len(satisfied)


def apply_to_page_extract(level: str, key: str, idx: int, pairs: list[tuple[str, str]]) -> int:
    path = BASE / 'data' / level / 'page_extract' / key / 'pages' / f'page_{idx:03d}.json'
    if not path.exists():
        return 0
    page = json.loads(path.read_text(encoding='utf-8'))

    # blocks 與 tables 要**各自**套一次，不能套到其中一邊就算完。
    # 表格內的文字在 page_extract 裡有兩份（文字層的 block、還原後的 tables[].rows），
    # 而 `positioned_page_items` 會跳過與表格重疊的 block、改渲染 tables——
    # 只改 block 等於改在看不見的地方，畫面上還是舊字（實測中級職能基準頁）。
    # 同一容器內則只套一次，否則同一處更正會在每個 block 各套一次。
    done_pairs: set[tuple[str, str]] = set()

    remaining = list(pairs)
    for block in page.get('blocks') or []:
        if not remaining:
            break
        block['text'], _done, done = apply_pairs(block.get('text') or '', remaining)
        done_pairs.update(done)
        remaining = [p for p in remaining if p not in done]

    # page_extract 的一個段落常被切成好幾個 block（PDF 的斷行），勘誤片段跨了 block
    # 邊界就找不到。剩下的片段改用「整頁串接」再定位，然後把替換分攤回受影響的 block。
    if remaining:
        crossed = apply_across_blocks(page.get('blocks') or [], remaining)
        done_pairs.update(crossed)

    remaining = list(pairs)
    for table in page.get('tables') or []:
        for row in table.get('rows') or []:
            for i, cell in enumerate(row):
                if not remaining:
                    break
                row[i], _done, done = apply_pairs(str(cell), remaining)
                done_pairs.update(done)
                remaining = [p for p in remaining if p not in done]

    applied = len(done_pairs)

    if applied != len(pairs):
        return 0  # 全有或全無，同 apply_to_pages_cache
    if applied:
        # `text` 是整頁串接，同步更新才不會與 blocks 不一致
        page['text'] = '\n'.join(b.get('text') or '' for b in page.get('blocks') or [])
        path.write_text(json.dumps(page, ensure_ascii=False, indent=2), encoding='utf-8')
    return applied


def manual_entry_tracks(level: str, key: str, idx: int, replacement: str,
                        original: str = '') -> tuple[bool, bool]:
    """更正後的文字分別是否已出現在 Track B（pages_cache）與 Track A（page_extract）。

    只看「更正後的文字在不在」是不夠的——當更正是刪字（`多模態多模態`→`多模態`）時，
    更正後的文字本來就是原文的一部分，永遠會命中，於是還沒改也被判成已改。
    所以同時要求**原文已經不在**。
    """
    in_b = in_a = False
    pc = BASE / 'data' / level / 'pages_cache' / key / f'page_{idx:03d}.json'
    if pc.exists():
        page = json.loads(pc.read_text(encoding='utf-8'))
        text = page.get('markdown') or ''
        in_b = (find_span(text, replacement) is not None
                and (not original or find_span(text, original) is None))

    pe = BASE / 'data' / level / 'page_extract' / key / 'pages' / f'page_{idx:03d}.json'
    if pe.exists():
        page = json.loads(pe.read_text(encoding='utf-8'))
        joined = '\n'.join(b.get('text') or '' for b in page.get('blocks') or [])
        for table in page.get('tables') or []:
            for row in table.get('rows') or []:
                joined += '\n' + '\n'.join(str(c) for c in row)
        in_a = (find_span(joined, replacement) is not None
                and (not original or find_span(joined, original) is None))

    of = BASE / 'data' / level / 'ocr_formulas' / key / f'page_{idx:03d}.json'
    if not in_a and of.exists():
        page = json.loads(of.read_text(encoding='utf-8'))
        in_a = any(find_span(f.get('latex') or '', replacement) is not None
                   for f in page.get('blocks') or [])
    return in_b, in_a


def apply_manual_overrides(level: str, dry_run: bool) -> tuple[int, int, set[tuple[str, str]]]:
    """套用人工判讀出來的勘誤（`data/{level}/errata_manual.json`）。

    有些勘誤自動比對定不了位——勘誤表對「原內容」的轉錄與講義原文有出入、
    原文落在表格儲存格裡、或一筆勘誤同時要改題目頁與解析頁。這些只能人看過原文再指定
    精確的 find/replace，但**結論要落成資料而不是直接手改**，否則重跑轉接層就沒了。

    每筆需要 key + page_label（或 page_index）+ find + replace，
    沿用自動流程的同一套定位與冪等機制。
    """
    path = BASE / 'data' / level / 'errata_manual.json'
    if not path.exists():
        return 0, 0, set()

    entries = json.loads(path.read_text(encoding='utf-8'))
    label_maps: dict[str, dict[str, int]] = {}
    applied = failed = 0
    # 人工覆寫涵蓋了哪些自動流程解不了的勘誤（用 errata 的 key + page_label 標記），
    # 這樣未處理清單才不會把已經人工解掉的又列一次
    resolved: set[tuple[str, str]] = set()

    for entry in entries:
        key = entry['key']
        if key not in label_maps:
            label_maps[key] = build_page_label_map(level, key)
        idx = entry.get('page_index')
        if idx is None:
            idx = label_maps[key].get(entry.get('page_label') or '')
        if idx is None:
            print(f'  ⚠ 人工勘誤定位失敗（{key} {entry.get("page_label")}）：{entry.get("note", "")}')
            failed += 1
            continue

        pairs = [(entry['find'], entry['replace'])]
        if dry_run:
            pc = BASE / 'data' / level / 'pages_cache' / key / f'page_{idx:03d}.json'
            text = json.loads(pc.read_text(encoding='utf-8'))['markdown'] if pc.exists() else ''
            ok = find_span(text, entry['find']) is not None or find_span(text, entry['replace']) is not None
        else:
            apply_to_pages_cache(level, key, idx, pairs)
            apply_to_page_extract(level, key, idx, pairs)
            apply_to_ocr_formulas(level, key, idx, pairs)
            # 用「更正後的文字是否在位」判定成功，而不是「這次改了幾處」——
            # 重跑時已經改好的會被冪等跳過，改動數是 0 但結果是對的。
            in_b, in_a = manual_entry_tracks(level, key, idx, entry['replace'], entry['find'])
            ok = in_b or in_a
            # track 欄位標明這筆只負責哪一軌（兩軌的原文格式不同時要各寫一筆）。
            # 沒標就代表預期兩軌都要改到，只改到一軌會示警。
            expects_both = entry.get('track') is None
            if ok and expects_both and not (in_b and in_a):
                # 只有一軌命中通常代表 find 綁了該軌專屬的格式（markdown 前綴、
                # 條列符號…），另一軌就漏改了。這種漏網以前是靜默的。
                missing = 'Track A（前端閱讀頁）' if in_b else 'Track B（出題）'
                print(f'  ⚠ 人工勘誤只改到一軌，{missing} 沒改到（{key} p{entry.get("page_label")}）：'
                      f'{entry["find"][:36]}')
        if ok:
            applied += 1
            for label in entry.get('resolves') or []:
                resolved.add((key, label))
        else:
            failed += 1
            print(f'  ⚠ 人工勘誤沒命中（{key} p{entry.get("page_label")}）：{entry["find"][:40]}')
    return applied, failed, resolved


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
        if not key:
            report['entries_skipped'] += 1
            unresolved.append({**entry, 'reason': '沒有對應的 guide key'})
            continue

        if key not in label_maps:
            label_maps[key] = build_page_label_map(level, key)

        idx = label_maps[key].get(label) if PAGE_LABEL_NUMERIC.match(label) else None
        if idx is None:
            # 「職能基準」頁這種非印刷頁碼的定位：改在全書搜尋原文，
            # **只在全書恰好出現一次時**才採用，避免改到別頁的同樣文字。
            idx = unique_page_for_text(level, key, entry['original'])
            if idx is None:
                # 重跑時原文已經被改掉了，改找更正後的文字——找得到就代表早就套好了
                idx = unique_page_for_text(level, key, entry['corrected'])
            if idx is None:
                report['entries_skipped'] += 1
                unresolved.append({
                    **entry,
                    'reason': f'無法定位（頁碼欄「{label}」不是印刷頁碼，全書搜尋也不唯一）',
                })
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
            a = a or apply_to_ocr_formulas(level, key, idx, pairs)

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

    manual_applied, manual_failed, manual_resolved = apply_manual_overrides(level, dry_run)

    print(f'=== {level}（共 {len(entries)} 筆勘誤）')
    print(f'  全部片段套用成功 {report["entries_ok"]} 筆 / 部分 {report["entries_partial"]} 筆 / '
          f'完全未命中 {report["entries_none"]} 筆 / 無法自動定位 {report["entries_skipped"]} 筆')
    print(f'  片段層級：Track B 套用 {report["applied_b"]} 處、Track A 套用 {report["applied_a"]} 處')

    if manual_applied or manual_failed:
        print(f'  人工勘誤（errata_manual.json）：套用 {manual_applied} 筆、未命中 {manual_failed} 筆')

    if not dry_run:
        remaining_unresolved = [
            e for e in unresolved
            if (e.get('key'), (e.get('page_label') or '').strip()) not in manual_resolved
        ]
        covered = len(unresolved) - len(remaining_unresolved)
        out = BASE / 'data' / level / 'errata_unresolved.json'
        out.write_text(json.dumps(remaining_unresolved, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'  需人工處理的 {len(remaining_unresolved)} 筆 → {out.relative_to(BASE)}'
              + (f'（另有 {covered} 筆已由 errata_manual.json 解決）' if covered else ''))


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
