#!/usr/bin/env python3
"""把 codex 重生的 card 欄位寫回題庫（§7-6）。冪等，可重複執行。

只套用**通過 runner 驗證**的批次，只覆寫 `concept`／`mnemonic`／`confusion`
三個欄位，且只動 prompt 當初挑出來的那些 id——已經寫得好的題目不會被碰到。

寫回前再驗一次（不信任「上游驗過了」，這條線踩過三次靜默失敗）：
    confusion 不等於該題 explanation
    mnemonic 不在佔位清單
    concept 不等於答案選項原句
任一項不過就跳過該題並回報，不寫進去。

用法：python3 scripts/apply_codex_card_fields.py --level 初級 [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterator

BASE = Path(__file__).resolve().parents[1]
RUN_SUBDIR = Path('pipeline') / 'codex_card_prompts'
PLACEHOLDERS = ('依學習指引原題複習',)
FIELDS = ('concept', 'mnemonic', 'confusion')


def load_json(path: Path) -> Any:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def normalize(value: Any) -> str:
    text = re.sub(r'^\s*解析\s*[：:]\s*', '', str(value or ''))
    return re.sub(r'\s+', '', text)


def walk(data: Any) -> Iterator[dict]:
    if isinstance(data, list):
        yield from data
        return
    if isinstance(data, dict):
        yield from data.get('questions') or []
        for chapter in data.get('chapters') or []:
            yield from chapter.get('questions') or []


def acceptable(question: dict, item: dict) -> str | None:
    for field in FIELDS:
        if not str(item.get(field) or '').strip():
            return f'{field} 是空的'
    explanation = normalize(question.get('explanation'))
    if explanation and normalize(item.get('confusion')) == explanation:
        return 'confusion 還是解析的複製'
    if str(item.get('mnemonic', '')).strip() in PLACEHOLDERS:
        return 'mnemonic 還是佔位字串'
    options = question.get('options') or {}
    answer_text = normalize(options.get(str(question.get('answer'))))
    if answer_text and normalize(item.get('concept')) == answer_text:
        return 'concept 還是答案選項原句'
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--level', choices=['初級', '中級'], action='append')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    total_applied = total_skipped = 0
    for level in args.level or ['初級', '中級']:
        summary_path = BASE / 'data' / level / RUN_SUBDIR / 'summary.json'
        if not summary_path.exists():
            print(f'{level}：沒有 summary.json，略過')
            continue
        summary = load_json(summary_path)

        replacements: dict[str, dict] = {}
        missing_batches = []
        for batch in summary['batches']:
            output_path = BASE / batch['output']
            if not output_path.exists():
                missing_batches.append(batch['batch'])
                continue
            for item in load_json(output_path).get('items', []):
                if isinstance(item, dict) and item.get('id') in batch['ids']:
                    replacements[str(item['id'])] = item
        if missing_batches:
            print(f'{level}：⚠️ 批次 {missing_batches} 還沒有輸出，這次不會套用那些題')

        applied = skipped = 0
        for path in sorted((BASE / 'data' / level / 'questions').glob('*.json')):
            data = load_json(path)
            dirty = False
            for question in walk(data):
                item = replacements.get(str(question.get('id')))
                card = question.get('card')
                if item is None or not isinstance(card, dict):
                    continue
                reason = acceptable(question, item)
                if reason:
                    print(f"   跳過 {question['id']}：{reason}")
                    skipped += 1
                    continue
                for field in FIELDS:
                    card[field] = str(item[field]).strip()
                applied += 1
                dirty = True
            if dirty and not args.dry_run:
                path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n',
                                encoding='utf-8')
        print(f'{level}：套用 {applied} 題，跳過 {skipped} 題'
              f'（可用替換 {len(replacements)} 筆）'
              + ('（dry-run，未寫入）' if args.dry_run else ''))
        total_applied += applied
        total_skipped += skipped

    print(f'\n合計套用 {total_applied}，跳過 {total_skipped}')


if __name__ == '__main__':
    main()
