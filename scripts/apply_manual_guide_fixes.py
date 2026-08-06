#!/usr/bin/env python3
"""補回 export_guide_outline_data.py 每次重跑都會沖掉的手動修正。

原本是 playbook/pipeline-reference.md §10 的兩段「複製貼上執行」的程式碼，
最容易漏（漏了不會報錯，只是前端側欄階層錯亂）。改成腳本以便納入流程：

    uv run python3 scripts/export_guide_outline_data.py --all-levels
    python3 scripts/apply_manual_guide_fixes.py            # ← 緊接著跑

修正內容見各 FIX 的註解。腳本是冪等的，重複執行不會出錯；
**字串對不上時會報錯而不是靜默跳過**——原本手動版本靜默不改的行為，
讓「以為補好了其實沒補」變成常態，所以這裡改成硬失敗。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

BASE = Path('/home/james/projects/ipas-test')
S1C4 = BASE / 'frontend/src/generated/guideContent/初級-guide1/s1c4.json'

# 修正 1：s1c4「本節階層」heading 層級（6 個 h4 → h3）
# 匯出腳本對所有「（\d+）」開頭的行一律輸出 ####，但 PDF 裡同一個符號用在兩個嵌套層次
# （x 座標同為 70.2，無法自動判斷），導致「（1）→（1）」變成同層。
DEMOTE_HEADINGS = [
    '（1）鑑別式AI 的原理與應用',
    '（2）生成式AI 的原理與應用',
    '（3）鑑別式AI 與生成式AI 的技術差異',
    '（1）整合應用的價值',
    '（2）整合應用的技術優勢',
    '（3）整合應用的挑戰與解決策略',
]

# 修正 2：s1c4 的 H4 標題截短。H3 節下的模型條目仍帶「（1）（2）…」前綴與整段敘述，
# 側欄看起來會跟上一層混在一起。
SHORTEN_HEADINGS = {
    '（1） 邏輯迴歸（Logistic Regression）是鑑別式AI 中最簡單且最基礎的分類模型': '邏輯迴歸（Logistic Regression）',
    '（2） 支援向量機（Support Vector Machine, SVM）是一種強大的分類模型，其核心': '支援向量機（SVM）',
    '（3） 決策樹（Decision Tree）是一種基於樹形結構進行數據分類的模型。其透過': '決策樹（Decision Tree）',
    '（4） 隨機森林（Random Forest）是決策樹的集成學習方法，其透過構建多棵決策': '隨機森林（Random Forest）',
    '（5） 神經網路（Neural Networks）是一種模擬生物神經系統的非線性模型，透過': '神經網路（Neural Networks）',
    '（1） 生成對抗網路（Generative Adversarial Networks, GAN）是生成式AI 中最具': '生成對抗網路（GAN）',
    '（2） 變分自編碼器（Variational Autoencoders, VAE）是一種基於概率生成模型的': '變分自編碼器（VAE）',
    '（3） 擴散模型（Diffusion Models）是一種基於逐步添加與去除雜訊的數據生成方': '擴散模型（Diffusion Models）',
}


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


if __name__ == '__main__':
    main()
