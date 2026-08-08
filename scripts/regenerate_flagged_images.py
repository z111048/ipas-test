#!/usr/bin/env python3
"""修好文字檢查不過的概念圖卡，直到通過（§7-6）。

`verify_generated_images.py` 把「圖上的字對不對」變成判定；這支負責照著判定修。

四個設計決定，改動前先想清楚：

1. **先試圖生圖（`/edit`），再退回文生圖（`/generate`）**。抽 30 張看過的結論是
   版面與內容本來就好，壞的只有幾個字；拿現有那張當參考、只改錯字，能保住版面。
   從頭重抽是抽籤，版面品質會一起變動。
2. **回饋比重試次數有用**。每一輪都把上一輪的問題（「不可出現『判別式AI』，
   官方用詞是『鑑別式AI』」）寫進 prompt，而不是原封不動再抽一次籤。
3. **絕不用更差的圖換掉現有的圖**。動手前先備份，每輪產完立刻檢查；
   所有嘗試都沒過就把備份還原，並回報「這張仍未通過」。
   影像模型的中文渲染有隨機性，不設這條就會靜靜地把好圖換成壞圖。
4. **`error` 不算 pass**。檢查器沒回應時當失敗重試，不要因為「沒抓到問題」就放行。

產圖走 `codex-imggen`（HTTP 服務，見 `imggen_client.py`），不直接 `codex exec`。

用法：
    python3 scripts/regenerate_flagged_images.py --from-review [--limit N] [--attempts 3]
    python3 scripts/regenerate_flagged_images.py --ids a,b --attempts 4 --no-edit
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from imggen_client import ImggenError, edit, generate, require_service
from verify_generated_images import (
    IMAGE_DIR,
    IMAGES_JSON,
    OUT_PATH as REVIEW_PATH,
    check_one,
    problems_as_instructions,
)

BASE = Path(__file__).resolve().parents[1]
UNITS_PATH = BASE / 'data' / '共用' / 'image_units_all_levels.json'
BACKUP_DIR = BASE / 'build' / 'image_backup'
LOG_PATH = BASE / 'build' / 'image_regeneration_log.jsonl'
# 與其餘 726 張一致（generate_images.OUTPUT_SIZE）
OUTPUT_SIZE = (1792, 1024)


def load_json(path: Path) -> Any:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def append_log(entry: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open('a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


def write_normalized(data: bytes, out_path: Path, quality: int = 92) -> None:
    """寫檔前正規化到 1792×1024。

    `size` 對 gpt-image-2 只是提示（USAGE.md 明講），服務會回它自己的標準尺寸——
    直接寫 bytes 會讓這張變成 727 張裡唯一尺寸不同的（實測 1659×948 vs 1792×1024）。
    """
    from io import BytesIO

    from PIL import Image, ImageOps

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(BytesIO(data)) as img:
        fitted = ImageOps.fit(img.convert('RGB'), OUTPUT_SIZE,
                              method=Image.Resampling.LANCZOS)
        fitted.save(out_path, 'WEBP', quality=quality)


def edit_prompt(problems: list[dict]) -> str:
    """圖生圖用的修字指令：只動指出來的字，其餘一律不要改。"""
    lines = ['這是一張中文資訊圖。**只修正文字，其他一切保持原樣**——',
             '版面、配色、圖示、面板位置、插圖內容都不要改動。',
             '', '要修正的文字：']
    for problem in problems:
        lines.append(f'- 「{problem.get("text", "")}」：{problem.get("note", "")}')
    lines.append('')
    lines.append('上面每一項若有寫出建議用詞，請**一字不改地照用那個建議的詞**，'
                 '不要自己再想別的說法、不要加字也不要減字。')
    lines.append('所有中文標籤都必須是通順的繁體中文詞、字形正確、沒有被截斷；'
                 '敘述不要過度斷言（例如中位數是「較不受」離群值影響，不是「不受」）。')
    lines.append('不要新增或刪除面板，不要改變任何非文字元素。')
    return '\n'.join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--from-review', action='store_true',
                        help='重生 image_text_review.json 裡 verdict=fail 的')
    parser.add_argument('--ids')
    parser.add_argument('--attempts', type=int, default=3)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--timeout', type=int, default=620)
    parser.add_argument('--no-edit', action='store_true',
                        help='不用圖生圖，一律從頭產（版面會跟著變，不建議）')
    args = parser.parse_args()

    review = load_json(REVIEW_PATH) if REVIEW_PATH.exists() else {'results': {}}
    if args.ids:
        targets = [i.strip() for i in args.ids.split(',') if i.strip()]
    elif args.from_review:
        targets = sorted(image_id for image_id, row in review['results'].items()
                         if row.get('verdict') == 'fail')
    else:
        raise SystemExit('FAIL 指定 --from-review 或 --ids a,b')
    if args.limit:
        targets = targets[:args.limit]
    if not targets:
        print('沒有需要重生的圖卡')
        return

    info = require_service()
    print(f'codex-imggen OK：{info.get("codex")}')
    records = {r['id']: r for r in load_json(IMAGES_JSON)['images']}
    units = {u['id']: u for u in load_json(UNITS_PATH)['units'] if u.get('id')}
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    fixed: list[str] = []
    still_failing: list[str] = []
    print(f'要重生 {len(targets)} 張，每張最多 {args.attempts} 次\n')

    for index, image_id in enumerate(targets, 1):
        record, unit = records.get(image_id), units.get(image_id)
        if record is None or unit is None or not unit.get('imagePrompt'):
            print(f'SKIP {image_id}：找不到 record 或 imagePrompt')
            continue
        out_path = IMAGE_DIR / Path(record['src']).name
        backup = BACKUP_DIR / out_path.name
        if out_path.exists() and not backup.exists():
            shutil.copy2(out_path, backup)

        problems = review['results'].get(image_id, {}).get('problems', [])
        passed = False
        for attempt in range(1, args.attempts + 1):
            # 先圖生圖（保住版面），失敗或使用者要求才退回文生圖
            use_edit = (not args.no_edit) and backup.exists() and problems
            try:
                if use_edit:
                    data = edit(edit_prompt(problems), [backup], timeout=args.timeout)
                    mode = 'edit'
                else:
                    data = generate(unit['imagePrompt'] + problems_as_instructions(problems),
                                    timeout=args.timeout)
                    mode = 'generate'
                write_normalized(data, out_path)
            except (ImggenError, Exception) as exc:  # noqa: B014
                print(f'   [{index}/{len(targets)}] {image_id} 第 {attempt} 次產圖失敗：'
                      f'{str(exc)[:80]}')
                append_log({'id': image_id, 'attempt': attempt, 'stage': 'generate',
                            'status': 'failed', 'error': str(exc)[:300]})
                continue

            result = check_one(out_path, record, timeout=args.timeout)
            append_log({'id': image_id, 'attempt': attempt, 'stage': 'verify',
                        'mode': mode, 'verdict': result['verdict'],
                        'problems': result['problems']})
            if result['verdict'] == 'pass':
                review['results'][image_id] = result
                print(f'OK   [{index}/{len(targets)}] {image_id}'
                      f'（{mode} 第 {attempt} 次通過）')
                fixed.append(image_id)
                passed = True
                break
            kinds = ','.join(sorted({p['kind'] for p in result['problems']})) or result['verdict']
            print(f'   [{index}/{len(targets)}] {image_id} 第 {attempt} 次仍不過（{kinds}）')
            problems = result['problems'] or problems

        if not passed:
            # 沒有任何一輪通過 → 還原備份，不要用更差的圖換掉原圖
            if backup.exists():
                shutil.copy2(backup, out_path)
            still_failing.append(image_id)
            print(f'FAIL [{index}/{len(targets)}] {image_id}：'
                  f'{args.attempts} 次都沒過，已還原原圖')

        REVIEW_PATH.write_text(json.dumps(review, ensure_ascii=False, indent=2) + '\n',
                               encoding='utf-8')

    print(f'\n修好 {len(fixed)}｜仍未通過 {len(still_failing)}')
    if still_failing:
        print('仍未通過（原圖已還原）：' + '、'.join(still_failing))
        print('這類就是影像模型的中文渲染極限——要根治得換成 HTML/SVG ＋ 真字型渲染。')


if __name__ == '__main__':
    main()
