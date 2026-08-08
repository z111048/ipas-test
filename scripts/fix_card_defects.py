#!/usr/bin/env python3
"""修 §7-6 抽樣驗收查出的兩類 card／解析缺陷。冪等，可重複執行。

1. **`frequency` 值域外**：2 題把 `difficulty` 的詞彙（易／難）寫進 `frequency`。
   前端 `FreqBar` 遇到非法值會 `?? 1` 靜默退回「低」——顯示錯了但看不出來。
   改成依「該題所在章的實際考古題數」分三段給值（初級/中級各自分段），
   理由：這是唯一有客觀依據的來源；`frequency` 全欄位的可信度是另一個未決問題
   （抽樣報告顯示它與章熱度秩相關 −0.174，見 `08-topic-labeling.md` §7-6）。

2. **解析尾端黏上學習指引「參考書目」附件**：2 題（s1c4gq010、s2c3gq010）
   的 `explanation` 與被複製過去的 `card.confusion` 都含數百字書單。
   從「附件 本學習指引參考書目」處切掉。

用法：python3 scripts/fix_card_defects.py [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterator

BASE = Path(__file__).resolve().parents[1]
MINDMAP_DIR = BASE / 'frontend' / 'src' / 'generated' / 'guideMindmap'
VALID_FREQUENCY = ('高', '中', '低')
BLEED = re.compile(r'附件\s*本學習指引參考書目.*$', re.S)
CHAPTER_ID = re.compile(r'^(mid-)?(s\d+c\d+)')


def walk(data: Any) -> Iterator[dict]:
    if isinstance(data, list):
        yield from data
        return
    if isinstance(data, dict):
        yield from data.get('questions') or []
        for chapter in data.get('chapters') or []:
            yield from chapter.get('questions') or []


def chapter_heat() -> dict[str, tuple[int, str]]:
    """章 id → (該章考古題數, 級別)。級別用來讓初級與中級各自分段。"""
    heat = {}
    for path in sorted(MINDMAP_DIR.glob('*.json')):
        if path.name == 'index.json':
            continue
        with path.open(encoding='utf-8') as f:
            data = json.load(f)
        for node in data['nodes']:
            if node['q'] is not None:
                heat[node['i']] = (node['q'], data['level'])
    return heat


def frequency_from_heat(question_id: str, heat: dict[str, tuple[int, str]]) -> str | None:
    match = CHAPTER_ID.match(question_id)
    if not match:
        return None
    key = (match.group(1) or '') + match.group(2)
    if key not in heat:
        return None
    count, level = heat[key]
    peers = sorted(c for c, lv in heat.values() if lv == level)
    low, high = peers[len(peers) // 3], peers[2 * len(peers) // 3]
    return '低' if count <= low else ('高' if count >= high else '中')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    heat = chapter_heat()
    changed_files = 0
    fixes: list[str] = []

    for path in sorted((BASE / 'data').glob('*/questions/*.json')):
        with path.open(encoding='utf-8') as f:
            data = json.load(f)
        dirty = False
        for question in walk(data):
            qid = str(question.get('id') or '')
            card = question.get('card')

            explanation = str(question.get('explanation') or '')
            if BLEED.search(explanation):
                question['explanation'] = BLEED.sub('', explanation).strip()
                fixes.append(f'{qid}: explanation 切掉參考書目附件 '
                             f'（{len(explanation)} → {len(question["explanation"])} 字）')
                dirty = True
            if isinstance(card, dict):
                confusion = str(card.get('confusion') or '')
                if BLEED.search(confusion):
                    card['confusion'] = BLEED.sub('', confusion).strip()
                    fixes.append(f'{qid}: card.confusion 切掉參考書目附件')
                    dirty = True

                current = str(card.get('frequency') or '').strip()
                if current not in VALID_FREQUENCY:
                    replacement = frequency_from_heat(qid, heat)
                    if replacement is None:
                        fixes.append(f'{qid}: frequency={current!r} 非法但對不到章節，未動')
                        continue
                    card['frequency'] = replacement
                    fixes.append(f'{qid}: frequency {current!r} → {replacement!r}'
                                 f'（依所在章考古題數分段）')
                    dirty = True

        if dirty and not args.dry_run:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n',
                            encoding='utf-8')
            changed_files += 1
        elif dirty:
            changed_files += 1

    for line in fixes:
        print(('[dry-run] ' if args.dry_run else '') + line)
    print(f'\n{len(fixes)} 處修正，{changed_files} 個檔案'
          + ('（dry-run，未寫入）' if args.dry_run else ''))


if __name__ == '__main__':
    main()
