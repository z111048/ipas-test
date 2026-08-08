#!/usr/bin/env python3
"""抽樣驗收題目的 `card` 欄位（§7-6）。

`card` 有四個欄位，錯的代價不一樣：
    concept    這題考什麼觀念——錯了會把使用者導向錯的複習方向
    confusion  易混淆點——**寫錯等於直接教錯**，風險最高
    mnemonic   記憶法——主觀，但不得包含錯誤陳述
    （frequency 已於 2026-08-08 移除：與該章實際考古題數秩相關 −0.173）

`audit_resources.py` 只檢查這四個欄位非空，內容正確性從未驗過（689 題 × 4 欄位）。
本腳本只負責**抽樣與出工作表**，判定由人／模型逐筆填 `verdict`，因此：

- 抽樣是確定性的（固定 seed + 排序後抽），同樣參數重跑會拿到同一批題，
  才能「改完再驗同一批」比較前後。
- 依檔案分層抽（proportional），避免整批集中在同一個科目或同一支生成腳本。

用法：
    python3 scripts/sample_card_review.py --size 40            # 出工作表
    python3 scripts/sample_card_review.py --size 40 --tally    # 讀回工作表算錯誤率
輸出：data/audit/card_sample_review.json
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterator

BASE = Path(__file__).resolve().parents[1]
OUT_PATH = BASE / 'data' / 'audit' / 'card_sample_review.json'
CARD_FIELDS = ('concept', 'mnemonic', 'confusion')


def walk(data: Any) -> Iterator[dict]:
    """題目 JSON 有三種容器：頂層 list、`questions`、`chapters[].questions`。"""
    if isinstance(data, list):
        yield from data
        return
    if isinstance(data, dict):
        yield from data.get('questions') or []
        for chapter in data.get('chapters') or []:
            yield from chapter.get('questions') or []


def collect() -> list[dict]:
    rows = []
    for path in sorted((BASE / 'data').glob('*/questions/*.json')):
        with path.open(encoding='utf-8') as f:
            data = json.load(f)
        for question in walk(data):
            card = question.get('card')
            if not isinstance(card, dict):
                continue
            rows.append({
                'file': str(path.relative_to(BASE)),
                'id': question.get('id'),
                'question': question.get('question'),
                'options': question.get('options'),
                'answer': question.get('answer'),
                'explanation': question.get('explanation'),
                'card': {field: card.get(field) for field in CARD_FIELDS},
            })
    return rows


def stratified(rows: list[dict], size: int, seed: int) -> list[dict]:
    """依檔案分層、按比例配額；餘額給「已抽比例最低」的層，結果與字典序無關。"""
    by_file: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_file[row['file']].append(row)
    total = len(rows)
    quota = {name: int(size * len(group) / total) for name, group in by_file.items()}
    while sum(quota.values()) < size:
        name = min(by_file, key=lambda n: (quota[n] / len(by_file[n]), n))
        if quota[name] >= len(by_file[name]):
            del by_file[name]
            continue
        quota[name] += 1

    rng = random.Random(seed)
    picked = []
    for name in sorted(by_file):
        group = sorted(by_file[name], key=lambda r: str(r['id']))
        picked.extend(rng.sample(group, min(quota[name], len(group))))
    return picked


def tally() -> None:
    if not OUT_PATH.exists():
        raise SystemExit(f'FAIL 找不到 {OUT_PATH.relative_to(BASE)}，先不帶 --tally 產生工作表')
    with OUT_PATH.open(encoding='utf-8') as f:
        payload = json.load(f)
    counts = {field: Counter() for field in CARD_FIELDS}
    unjudged = 0
    for row in payload['samples']:
        verdict = row.get('verdict')
        if not isinstance(verdict, dict) or not verdict:
            unjudged += 1
            continue
        for field in CARD_FIELDS:
            counts[field][verdict.get(field, '未判定')] += 1
    n = len(payload['samples']) - unjudged
    print(f"樣本 {len(payload['samples'])}｜已判定 {n}｜未判定 {unjudged}")
    for field in CARD_FIELDS:
        if not counts[field]:
            continue
        line = '  '.join(f'{k} {v}（{v / n:.0%}）'
                         for k, v in counts[field].most_common())
        print(f'  {field:10} {line}')
    payload['tally'] = {f: dict(counts[f]) for f in CARD_FIELDS}
    payload['judged'] = n
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'→ 統計寫回 {OUT_PATH.relative_to(BASE)}')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--size', type=int, default=40)
    parser.add_argument('--seed', type=int, default=20260808)
    parser.add_argument('--tally', action='store_true', help='讀回工作表算錯誤率')
    args = parser.parse_args()

    if args.tally:
        tally()
        return

    rows = collect()
    samples = stratified(rows, args.size, args.seed)
    payload = {
        'population': len(rows),
        'size': len(samples),
        'seed': args.seed,
        'countingRule': 'verdict 逐欄位填：正確／可疑／錯誤；confusion 錯誤即等於教錯',
        'samples': [dict(row, verdict={}, note='') for row in samples],
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    spread = Counter(row['file'] for row in samples)
    print(f'母體 {len(rows)} 題有 card｜抽出 {len(samples)} 題（seed {args.seed}）')
    for name, count in sorted(spread.items()):
        print(f'  {count:>3}  {name}')
    print(f'→ {OUT_PATH.relative_to(BASE)}')


if __name__ == '__main__':
    main()
