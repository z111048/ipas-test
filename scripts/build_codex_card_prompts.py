#!/usr/bin/env python3
"""為「card 欄位是複製／佔位」的題目產 codex prompt（§7-6）。

抽樣驗收查出 179 題 `guide_exercises` 的 `card.confusion` 是 `explanation` 全文
複製、`mnemonic` 是同一句佔位字串（見 `08-topic-labeling.md` §7-6）。這支腳本
只挑**確實有缺陷**的題目重生，不動已經寫得好的 510 題。

判定缺陷（與 `audit_resources.py` 的閘門同一組規則）：
    confusion 正規化後等於 explanation ／ mnemonic 在佔位清單裡
    ／ concept 正規化後等於答案選項原句

沿用 `build_codex_section_prompts.py` 的慣例：prompt 與 summary.json 放
`data/{level}/pipeline/`（**gitignored**），由 runner 讀 summary 逐批跑。

用法：
    python3 scripts/build_codex_card_prompts.py [--batch-size 10] [--level 初級]
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

INSTRUCTIONS = """\
你要為 iPAS AI 應用規劃師考試的練習題補寫「解說圖卡」的三個欄位。
使用者答完題後會看到這張圖卡，所以內容必須正確、精簡、可直接閱讀。

每題輸出三個欄位：

- concept：這題考的**核心觀念**，一句話說清楚。
  ⛔ 不要抄答案選項的原句（例如答案是「目標偵測」就只寫「目標偵測」等於沒說明）。
  ✅ 要點出「是什麼、用在哪、和什麼並列」，例如
     「目標偵測同時輸出類別與邊界框位置，處理一張圖中的多個物件」。

- mnemonic：好記的口訣或聯想，一句話。
  ⛔ 不要寫「依學習指引原題複習」這類沒有內容的話。
  ⛔ 不要為英文縮寫編造錯誤的字面拆解（例如把 CBOW 說成 Context Before One Word，
     它其實是 Continuous Bag-of-Words）。不確定縮寫全稱就不要拆。
  ✅ 例如「分類看類別，偵測還要框位置」。

- confusion：**最容易混淆的一組概念，以及它們的差別**。
  ⛔ 絕對不要複製或改寫「解析」欄的內容——那是另一格，重複等於這格沒有內容。
  ✅ 句型是「X 是…；Y 是…」，明確對比。例如
     「影像分類只回答整張圖是什麼；目標偵測要回答有幾個、各在哪裡」。

全部用**繁體中文**。不要提到「AI 生成」、「模型產生」之類的字眼，也不要提到
題目來源或這是練習題。每個欄位不要超過 60 個字。

輸出必須符合給定的 JSON schema：`items` 陣列，每個元素的 `id` 與下方題目的
id 完全一致，順序也一致。只輸出 JSON，不要有其他文字。

以下是這一批的題目：
"""


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
            for question in chapter.get('questions') or []:
                question.setdefault('_chapter_title', chapter.get('title'))
                yield question


def defects(question: dict) -> list[str]:
    card = question.get('card')
    if not isinstance(card, dict):
        return []
    found = []
    explanation = normalize(question.get('explanation'))
    if explanation and normalize(card.get('confusion')) == explanation:
        found.append('confusion＝解析複製')
    if str(card.get('mnemonic', '')).strip() in PLACEHOLDERS:
        found.append('mnemonic＝佔位字串')
    options = question.get('options') or {}
    answer_text = normalize(options.get(str(question.get('answer'))))
    if answer_text and normalize(card.get('concept')) == answer_text:
        found.append('concept＝答案選項原句')
    return found


def render(batch: list[dict]) -> str:
    lines = [INSTRUCTIONS]
    for row in batch:
        lines.append(f"\n### id: {row['id']}")
        if row.get('chapter_title'):
            lines.append(f"章節：{row['chapter_title']}")
        lines.append(f"題目：{row['question']}")
        for key in sorted(row.get('options') or {}):
            lines.append(f"  {key}. {row['options'][key]}")
        lines.append(f"正確答案：{row['answer']}")
        lines.append(f"解析（**不要複製到 confusion**）：{row['explanation']}")
    return '\n'.join(lines) + '\n'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--batch-size', type=int, default=10)
    parser.add_argument('--level', choices=['初級', '中級'], action='append',
                        help='預設兩級都做')
    args = parser.parse_args()
    levels = args.level or ['初級', '中級']

    targets: dict[str, list[dict]] = {}
    for level in levels:
        rows: list[dict] = []
        for path in sorted((BASE / 'data' / level / 'questions').glob('*.json')):
            with path.open(encoding='utf-8') as f:
                data = json.load(f)
            for question in walk(data):
                found = defects(question)
                if not found:
                    continue
                rows.append({
                    'id': question.get('id'),
                    'file': str(path.relative_to(BASE)),
                    'chapter_title': question.pop('_chapter_title', None),
                    'question': question.get('question'),
                    'options': question.get('options'),
                    'answer': question.get('answer'),
                    'explanation': question.get('explanation'),
                    'defects': found,
                })
        targets[level] = rows

    for level, rows in targets.items():
        if not rows:
            print(f'{level}：沒有需要重生的題目')
            continue
        run_dir = BASE / 'data' / level / RUN_SUBDIR
        (run_dir / 'prompts').mkdir(parents=True, exist_ok=True)
        batches = []
        for index in range(0, len(rows), args.batch_size):
            batch = rows[index:index + args.batch_size]
            number = index // args.batch_size + 1
            prompt_path = run_dir / 'prompts' / f'batch_{number:03d}.md'
            prompt_path.write_text(render(batch), encoding='utf-8')
            batches.append({
                'batch': number,
                'prompt': str(prompt_path.relative_to(BASE)),
                'output': str((run_dir / 'outputs' / f'batch_{number:03d}.json')
                              .relative_to(BASE)),
                'ids': [row['id'] for row in batch],
                'files': sorted({row['file'] for row in batch}),
            })
        summary = {
            'level': level,
            'schema': 'schemas/card_fields.schema.json',
            'population': len(rows),
            'batchSize': args.batch_size,
            'defectTally': {name: sum(name in row['defects'] for row in rows)
                            for name in ('confusion＝解析複製', 'mnemonic＝佔位字串',
                                         'concept＝答案選項原句')},
            'batches': batches,
        }
        (run_dir / 'summary.json').write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'{level}：{len(rows)} 題有缺陷 → {len(batches)} 批')
        for name, count in summary['defectTally'].items():
            print(f'    {name}: {count}')
        print(f'  → {(run_dir / "summary.json").relative_to(BASE)}')


if __name__ == '__main__':
    main()
