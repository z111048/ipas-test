#!/usr/bin/env python3
"""檢查概念圖卡上的中文文字是否真的正確（§7-6）。

為什麼需要這支：727 張圖卡的**內容**全對（抽 30 張零錯），但約三分之一的標題或標籤
有字形變形，4/30 有真缺陷（非中文詞、截斷、術語與考綱不符）。`generate_images.py`
的重試只處理技術失敗（timeout、抓不到 session id），**從不因文字品質重試**——
偵測不到就等於沒有偵測。這支把「圖上的字對不對」變成可判定的閘門。

作法：`codex exec --image <webp>` 讀回圖中每一串文字並逐條判定。用 codex 自己是因為
它已認證可用，且同一支 CLI 既能產圖也能看圖（`gemini` CLI 已死、`.env` 金鑰是假的）。

官方用詞從既有權威來源組出來，不另建清單：
    data/{level}/toc_manifest.json   章節名稱（SSOT）
    data/topics/topics.json          181 個定案概念名稱

用法：
    python3 scripts/verify_generated_images.py --sample 30      # 驗抽樣那批
    python3 scripts/verify_generated_images.py --all            # 全量
    python3 scripts/verify_generated_images.py --ids a,b,c
    python3 scripts/verify_generated_images.py --report         # 只讀既有結果
輸出：data/audit/image_text_review.json（逐張 verdict，可重跑續驗）
"""

from __future__ import annotations

import argparse
import json
import os
import random
import signal
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
IMAGES_JSON = BASE / 'frontend' / 'src' / 'generated' / 'guideImages.json'
IMAGE_DIR = BASE / 'frontend' / 'public' / 'images'
SCHEMA_PATH = BASE / 'schemas' / 'image_text_check.schema.json'
OUT_PATH = BASE / 'data' / 'audit' / 'image_text_review.json'
TOPICS_PATH = BASE / 'data' / 'topics' / 'topics.json'

PROMPT_HEAD = """\
這是一張中文資訊圖，用在 iPAS AI 應用規劃師考試的學習平台上。
請只做一件事：**檢查圖上的中文文字對不對**。不要評論配色、排版或美感。

逐條照抄你實際看到的每一串文字（標題、面板標籤、圖內小字），放進 readableText。
**照抄你看到的字，不要順手修正錯字**——我要知道圖上真正印的是什麼。

然後逐條判定，只挑真的有問題的放進 problems：

- garbled：字形錯亂、筆畫多出或缺少、根本不成字。
- nonword：每個字都是真的字，但連起來不是中文詞或讀不通
  （例如「驗證停升」「步時上限」「不示離散」都是這種）。
- truncated：詞被截斷（例如「優化演算」少了「法」）。
- terminology：與下方官方用詞清單不一致（例如圖上寫「判別式AI」，
  但官方章名用「鑑別式AI」）。note 要寫出應該用哪個詞。
- wrong：內容講錯（公式、定義、對比關係錯誤）。

判定從嚴但不要無中生有：**字形只是略粗略細、或字重不同，不算 garbled**；
只有「明顯不成字、會讓人認不出來」才算。英文與數字不在檢查範圍。

⚠️ **problems 必須列出你看到的每一個問題，不要只回報第一個或最嚴重的那個。**
下游會拿這份清單去逐條修圖；漏掉的那一項不會被修，而且會讓修圖在兩個標籤之間
來回擺盪（修好 A、漏講 B，下一輪修好 B、A 又壞掉）。逐格檢查完再輸出。

problems 為空才給 verdict=pass。
"""


def load_json(path: Path) -> Any:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def official_terms() -> list[str]:
    """章節名稱（toc_manifest 是 SSOT）＋ 定案概念名稱。不另建清單。"""
    terms: list[str] = []
    for manifest in sorted((BASE / 'data').glob('*/toc_manifest.json')):
        for subject in load_json(manifest).get('subjects', []):
            terms.append(str(subject.get('subject', '')))
            for chapter in subject.get('chapters', []):
                terms.append(str(chapter.get('title', '')))
    if TOPICS_PATH.exists():
        terms.extend(str(topic['name']) for topic in load_json(TOPICS_PATH)['topics'])
    seen: set[str] = set()
    ordered = []
    for term in terms:
        term = term.strip()
        if term and term not in seen:
            seen.add(term)
            ordered.append(term)
    return ordered


def build_prompt(record: dict, terms: list[str]) -> str:
    heading = '／'.join(record.get('headingPath') or []) or record.get('title', '')
    return (
        PROMPT_HEAD
        + f"\n這張圖的來源章節：{record.get('level', '')} {record.get('sourceNodeId', '')}"
        + f"\n這張圖對應的小節標題：{heading}\n"
        + "\n官方用詞清單（圖上的術語應與這些一致；清單裡沒有的術語不必挑）：\n"
        + '、'.join(terms)
        + "\n\n只輸出符合 JSON schema 的結果。\n"
    )


def run_check(image_path: Path, prompt: str, out_path: Path, timeout: int) -> bool:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()
    proc = subprocess.Popen(
        ['codex', 'exec', '--cd', BASE.as_posix(), '--sandbox', 'read-only',
         '--image', image_path.as_posix(),
         '--output-schema', SCHEMA_PATH.as_posix(),
         '-o', out_path.as_posix(), '-'],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        text=True, cwd=BASE, start_new_session=True)
    try:
        proc.communicate(prompt, timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
    return out_path.exists()


def check_one(image_path: Path, context: dict, timeout: int = 300,
              extra: str = '') -> dict:
    """單張檢查，給 `generate_images.py` 在產圖後直接呼叫。

    回傳 `{verdict, readableText, problems}`；codex 沒輸出時 verdict='error'
    ——**error 不等於 pass**，呼叫端要當失敗處理，否則又回到「偵測不到就放過」。
    """
    prompt = build_prompt(context, official_terms()) + extra
    scratch = BASE / 'build' / 'image_text_check'
    out_path = scratch / f'inline_{Path(image_path).stem}.json'
    if not run_check(Path(image_path), prompt, out_path, timeout):
        return {'verdict': 'error', 'readableText': [], 'problems': [],
                'note': 'codex 沒有輸出'}
    data = load_json(out_path)
    return {'verdict': data.get('verdict', 'error'),
            'readableText': data.get('readableText', []),
            'problems': data.get('problems', [])}


def problems_as_instructions(problems: list[dict]) -> str:
    """把上一輪的判定變成下一輪 prompt 的硬性要求。回饋比重試次數有用。"""
    if not problems:
        return ''
    lines = ['\n重要：上一版這張圖的文字有以下問題，這一版必須避免——']
    for problem in problems:
        lines.append(f'- 「{problem.get("text", "")}」：{problem.get("note", "")}')
    lines.append('請確認每一個標籤都是通順的繁體中文詞、沒有被截斷、'
                 '且術語與官方用詞一致。')
    return '\n'.join(lines)


def sampled_ids(records: list[dict], size: int, seed: int) -> list[str]:
    """與 08 §7-6 手工驗過的那批同一組（level-guideKey 分層、同 seed）。"""
    groups: dict[str, list[dict]] = defaultdict(list)
    for record in sorted(records, key=lambda r: r['id']):
        groups[f"{record['level']}-{record['guideKey']}"].append(record)
    total = len(records)
    quota = {key: max(1, round(size * len(group) / total)) for key, group in groups.items()}
    rng = random.Random(seed)
    picked: list[dict] = []
    for key in sorted(groups):
        picked.extend(rng.sample(groups[key], min(quota[key], len(groups[key]))))
    return [record['id'] for record in picked[:size]]


def report(payload: dict) -> None:
    results = payload.get('results', {})
    tally = Counter(row['verdict'] for row in results.values())
    kinds = Counter(problem['kind'] for row in results.values()
                    for problem in row.get('problems', []))
    print(f'已驗 {len(results)} 張｜pass {tally["pass"]}｜fail {tally["fail"]}'
          f'｜錯誤 {tally.get("error", 0)}')
    if kinds:
        print('問題類型：' + '  '.join(f'{k} {v}' for k, v in kinds.most_common()))
    for image_id, row in sorted(results.items()):
        if row['verdict'] != 'fail':
            continue
        print(f'\nFAIL {image_id}')
        for problem in row.get('problems', []):
            print(f'   [{problem["kind"]}] {problem["text"]} — {problem["note"]}')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--sample', type=int)
    parser.add_argument('--seed', type=int, default=20260808)
    parser.add_argument('--ids')
    parser.add_argument('--timeout', type=int, default=300)
    parser.add_argument('--force', action='store_true', help='已驗過的也重驗')
    parser.add_argument('--report', action='store_true', help='只讀既有結果')
    args = parser.parse_args()

    payload = load_json(OUT_PATH) if OUT_PATH.exists() else {'results': {}}
    if args.report:
        report(payload)
        return

    records = {record['id']: record for record in load_json(IMAGES_JSON)['images']}
    if args.ids:
        targets = [i.strip() for i in args.ids.split(',') if i.strip()]
    elif args.sample:
        targets = sampled_ids(list(records.values()), args.sample, args.seed)
    elif args.all:
        targets = sorted(records)
    else:
        raise SystemExit('FAIL 指定 --all / --sample N / --ids a,b')

    terms = official_terms()
    scratch = BASE / 'build' / 'image_text_check'
    for index, image_id in enumerate(targets, 1):
        record = records.get(image_id)
        if record is None:
            print(f'SKIP {image_id}：不在 guideImages.json')
            continue
        if not args.force and image_id in payload['results']:
            continue
        image_path = IMAGE_DIR / Path(record['src']).name
        if not image_path.exists():
            payload['results'][image_id] = {'verdict': 'error', 'problems': [],
                                            'note': '圖檔不存在'}
            continue

        out_path = scratch / f'{image_id}.json'
        ok = run_check(image_path, build_prompt(record, terms), out_path, args.timeout)
        if not ok:
            payload['results'][image_id] = {'verdict': 'error', 'problems': [],
                                            'note': 'codex 沒有輸出'}
            print(f'ERR  [{index}/{len(targets)}] {image_id}')
        else:
            data = load_json(out_path)
            payload['results'][image_id] = {
                'verdict': data.get('verdict', 'error'),
                'readableText': data.get('readableText', []),
                'problems': data.get('problems', []),
            }
            mark = 'OK  ' if data.get('verdict') == 'pass' else 'FAIL'
            kinds = ','.join(sorted({p['kind'] for p in data.get('problems', [])}))
            print(f'{mark} [{index}/{len(targets)}] {image_id}'
                  + (f'  ({kinds})' if kinds else ''))

        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n',
                            encoding='utf-8')

    print()
    report(payload)


if __name__ == '__main__':
    main()
