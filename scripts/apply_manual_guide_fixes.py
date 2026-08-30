#!/usr/bin/env python3
"""驗證／遷移舊版 export 產物中的 publication hierarchy overlays。

原本是 playbook/pipeline-reference.md §10 的兩段「複製貼上執行」的程式碼，
最容易漏（漏了不會報錯，只是前端側欄階層錯亂）。現行
``export_guide_outline_data.py`` 已在 staged candidate 內套用並驗證相同規則，
所以標準 export 後執行本腳本應為 0 change；本腳本只保留作舊產物遷移與
相容性驗證：

    uv run python3 scripts/export_guide_outline_data.py --all-levels
    python3 scripts/apply_manual_guide_fixes.py            # 可選，預期回報 0 change

修正內容見各 FIX 的註解。腳本是冪等的，重複執行不會出錯；
**字串對不上時會報錯而不是靜默跳過**——原本手動版本靜默不改的行為，
讓「以為補好了其實沒補」變成常態，所以這裡改成硬失敗。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_guide_outline_data import slugify_heading  # noqa: E402
from guide_publication_overlays import (  # noqa: E402
    DEMOTE_HEADINGS,
    PROMOTE_HEADINGS,
    SHORTEN_HEADINGS,
)

BASE = Path(__file__).resolve().parents[1]
S1C4 = BASE / 'frontend/src/generated/guideContent/初級-guide1/s1c4.json'

# 修正 1：s1c4「本節階層」heading 層級（6 個 h4 → h3）
# 匯出腳本對所有「（\d+）」開頭的行一律輸出 ####，但 PDF 裡同一個符號用在兩個嵌套層次
# （x 座標同為 70.2，無法自動判斷），導致「（1）→（1）」變成同層。
# 修正 2：s1c4 的 H4 標題截短。H3 節下的模型條目仍帶「（1）（2）…」前綴與整段敘述，
# 側欄看起來會跟上一層混在一起。
# 修正 5：s1c2「假說檢定名詞介紹：」升為 h3（2026-08-08）
# 這章在 PDF 裡只有這一個次級標題，而且它緊貼表格上緣（y 421.6–434.9 vs 表格起點
# 426.3），一度被 export 的表格重疊過濾整行刪掉——那個內容遺失已在
# export_guide_outline_data.py 修掉，但標題判定仍走編號式 regex，認不得無編號標題。
# 全語料套用 OCR 標題約半數是雜訊（見該檔 ocr_heading_levels 註解），所以這裡逐條指定。
S1C2 = BASE / 'frontend/src/generated/guideContent/初級-guide1/s1c2.json'
def apply_s1c2(strict: bool) -> list[str]:
    if not S1C2.exists():
        raise SystemExit(f'找不到 {S1C2.relative_to(BASE)}——先跑 export_guide_outline_data.py --all-levels')
    data = json.loads(S1C2.read_text(encoding='utf-8'))
    title, level = PROMOTE_HEADINGS['s1c2']
    marker = '#' * level
    notes: list[str] = []

    content = data['content']
    if f'\n{marker} {title}\n' in content:
        promoted = 0                      # 已是修正後狀態
    elif f'\n{title}\n' in content:
        content = content.replace(f'\n{title}\n', f'\n{marker} {title}\n', 1)
        data['content'] = content
        promoted = 1
    else:
        notes.append(f'修正5 在 s1c2 找不到「{title}」——export 可能又把它刪掉了')
        promoted = 0

    # anchor 必須跟匯出腳本用同一套 slug：export_guide_hierarchy 會跳過沒有 anchor 的
    # heading block，headings[] 也是拿 id 當 anchor 用。少了它就補了等於沒補。
    anchor = slugify_heading(title, 1)

    titles = {h.get('title') for h in data.get('headings', [])}
    if title not in titles and f'{marker} {title}' in data['content']:
        data.setdefault('headings', []).append(
            {'id': anchor, 'level': level, 'title': title})

    for block in data.get('blocks', []):
        if block.get('type') != 'heading' and str(block.get('text', '')).strip() == title:
            block['type'] = 'heading'
            block['depth'] = level
            block['title'] = title
            block['anchor'] = anchor
            block.pop('text', None)

    S1C2.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f's1c2: 標題升階 {promoted} 處、headings 共 {len(data.get("headings", []))} 個')

    if notes and strict:
        for note in notes:
            print(f'  ⚠ {note}')
        raise SystemExit('手動修正有對不上的項目——不要當作補好了，請先查明')
    return notes



def apply_s1c4(strict: bool) -> list[str]:
    if not S1C4.exists():
        raise SystemExit(f'找不到 {S1C4.relative_to(BASE)}——先跑 export_guide_outline_data.py --all-levels')
    data = json.loads(S1C4.read_text(encoding='utf-8'))
    notes: list[str] = []

    content = data['content']
    demoted = 0
    for title in DEMOTE_HEADINGS:
        old, new = f'#### {title}\n', f'### {title}\n'
        if old in content:
            content = content.replace(old, new)
            demoted += 1
        elif new not in content:
            notes.append(f'修正1 找不到標題（也不是已修正狀態）：{title}')
    data['content'] = content

    heading_demoted = 0
    for heading in data.get('headings', []):
        if heading.get('title') in DEMOTE_HEADINGS and heading.get('level') == 4:
            heading['level'] = 3
            heading_demoted += 1

    shortened = 0
    for heading in data.get('headings', []):
        title = heading.get('title')
        if title in SHORTEN_HEADINGS:
            heading['title'] = SHORTEN_HEADINGS[title]
            shortened += 1
    already = sum(1 for h in data.get('headings', [])
                  if h.get('title') in set(SHORTEN_HEADINGS.values()))
    if shortened == 0 and already < len(SHORTEN_HEADINGS):
        notes.append(f'修正2 只找到 {already}/{len(SHORTEN_HEADINGS)} 個標題，'
                     f'export 可能改了原文字串——請更新 SHORTEN_HEADINGS')

    S1C4.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f's1c4: content 降階 {demoted} 處、headings 降階 {heading_demoted} 個、標題截短 {shortened} 個'
          f'（已是截短狀態的 {already} 個）')

    if notes and strict:
        for note in notes:
            print(f'  ⚠ {note}')
        raise SystemExit('手動修正有對不上的項目——不要當作補好了，請先查明')
    return notes


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--no-strict', action='store_true',
                    help='對不上時只警告不中斷（預設中斷）')
    args = ap.parse_args()
    apply_s1c4(strict=not args.no_strict)
    apply_s1c2(strict=not args.no_strict)


if __name__ == '__main__':
    main()
