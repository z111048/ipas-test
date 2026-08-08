#!/usr/bin/env python3
"""跑 `build_codex_card_prompts.py` 產的批次，逐批驗證、可續跑（§7-6）。

驗證的是「這批輸出能不能用」，而不是「codex 有沒有回東西」——這條線踩過三次
「失敗看不見」的坑（批次回一半當成功、輸出被截斷、id 對不上被靜默丟棄，
見 `08-topic-labeling.md` §6），所以每批都檢查：

    id 集合與 prompt 完全一致（不多不少、不改名）
    confusion 不等於該題的 explanation（重生的目的就是擺脫複製）
    mnemonic 不在佔位清單裡
    concept 不等於答案選項原句
    沒有「AI 生成」之類的字眼（不變量 2：對外文案不得透露生成方式）

任一項不過就**不算這批完成**，下次重跑會重做這批。

用法：
    python3 scripts/run_codex_card_generation.py --level 初級 [--limit N] [--force]
    python3 scripts/run_codex_card_generation.py --level 初級 --check   # 只驗不跑
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
from pathlib import Path
from typing import Any, Iterator

BASE = Path(__file__).resolve().parents[1]
SCHEMA_PATH = BASE / 'schemas' / 'card_fields.schema.json'
RUN_SUBDIR = Path('pipeline') / 'codex_card_prompts'
PLACEHOLDERS = ('依學習指引原題複習',)
FORBIDDEN = ('AI 生成', 'AI生成', '模型產生', '模型生成', '本題由', 'AI 產生')
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


def source_questions(level: str) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for path in sorted((BASE / 'data' / level / 'questions').glob('*.json')):
        for question in walk(load_json(path)):
            qid = question.get('id')
            if qid:
                index[str(qid)] = question
    return index


def validate(output_path: Path, batch: dict, originals: dict[str, dict]) -> list[str]:
    if not output_path.exists():
        return ['輸出檔不存在']
    try:
        data = load_json(output_path)
    except json.JSONDecodeError as exc:
        return [f'JSON 解析失敗：{exc}']

    items = data.get('items')
    if not isinstance(items, list):
        return ['items 不是陣列']

    errors: list[str] = []
    expected = list(batch['ids'])
    got = [str(item.get('id')) for item in items if isinstance(item, dict)]
    if sorted(got) != sorted(expected):
        missing = sorted(set(expected) - set(got))
        extra = sorted(set(got) - set(expected))
        errors.append(f'id 對不上（缺 {missing}／多 {extra}）')

    for item in items:
        if not isinstance(item, dict):
            errors.append('items 內有非物件元素')
            continue
        qid = str(item.get('id'))
        original = originals.get(qid)
        for field in FIELDS:
            value = str(item.get(field) or '').strip()
            if not value:
                errors.append(f'{qid}.{field} 是空的')
            for word in FORBIDDEN:
                if word in value:
                    errors.append(f'{qid}.{field} 含禁用字眼「{word}」')
        if str(item.get('mnemonic', '')).strip() in PLACEHOLDERS:
            errors.append(f'{qid}.mnemonic 還是佔位字串')
        if original is None:
            errors.append(f'{qid} 在題庫裡找不到')
            continue
        explanation = normalize(original.get('explanation'))
        if explanation and normalize(item.get('confusion')) == explanation:
            errors.append(f'{qid}.confusion 還是解析的複製')
        options = original.get('options') or {}
        answer_text = normalize(options.get(str(original.get('answer'))))
        if answer_text and normalize(item.get('concept')) == answer_text:
            errors.append(f'{qid}.concept 還是答案選項原句')
    return errors


def run_codex(prompt_path: Path, output_path: Path, timeout_seconds: int) -> bool:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with prompt_path.open(encoding='utf-8') as prompt_file:
        proc = subprocess.Popen(
            ['codex', 'exec', '--cd', BASE.as_posix(), '--sandbox', 'read-only',
             '--output-schema', SCHEMA_PATH.as_posix(),
             '-o', output_path.as_posix(), '-'],
            stdin=prompt_file, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            text=True, cwd=BASE, start_new_session=True)
        try:
            proc.wait(timeout=timeout_seconds)
            return output_path.exists()
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            return output_path.exists()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--level', choices=['初級', '中級'], required=True)
    parser.add_argument('--limit', type=int, default=None)
    parser.add_argument('--timeout', type=int, default=420)
    parser.add_argument('--force', action='store_true', help='已通過的批次也重跑')
    parser.add_argument('--check', action='store_true', help='只驗證現有輸出')
    args = parser.parse_args()

    run_dir = BASE / 'data' / args.level / RUN_SUBDIR
    summary_path = run_dir / 'summary.json'
    if not summary_path.exists():
        raise SystemExit(f'FAIL 找不到 {summary_path.relative_to(BASE)}，'
                         '先跑 build_codex_card_prompts.py')
    summary = load_json(summary_path)
    originals = source_questions(args.level)

    done = failed = skipped = 0
    for batch in summary['batches']:
        output_path = BASE / batch['output']
        label = f"batch {batch['batch']:03d}（{len(batch['ids'])} 題）"

        if not args.force and not args.check:
            if not validate(output_path, batch, originals):
                skipped += 1
                continue
        if args.check:
            errors = validate(output_path, batch, originals)
            print(f"{'OK  ' if not errors else 'FAIL'} {label}"
                  + ('' if not errors else f"  {errors[:3]}"))
            done += not errors
            failed += bool(errors)
            continue
        if args.limit is not None and done + failed >= args.limit:
            break

        run_codex(BASE / batch['prompt'], output_path, args.timeout)
        errors = validate(output_path, batch, originals)
        if errors:
            failed += 1
            print(f'FAIL {label}')
            for error in errors[:5]:
                print(f'       {error}')
        else:
            done += 1
            print(f'OK   {label}')

    print(f'\n完成 {done}｜失敗 {failed}｜已通過而跳過 {skipped}'
          f'｜共 {len(summary["batches"])} 批')
    if failed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
