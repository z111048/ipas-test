#!/usr/bin/env python3
"""Pure, idempotent publication hierarchy overlays shared by guide exporters.

These source-reviewed exceptions used to run only as a post-export file edit.
Keeping the transformations pure lets the staged exporter install the final
release shape directly and validate it before touching live outputs.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any


DEMOTE_HEADINGS = [
    '（1）鑑別式AI 的原理與應用',
    '（2）生成式AI 的原理與應用',
    '（3）鑑別式AI 與生成式AI 的技術差異',
    '（1）整合應用的價值',
    '（2）整合應用的技術優勢',
    '（3）整合應用的挑戰與解決策略',
]

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

PROMOTE_HEADINGS = {'s1c2': ('假說檢定名詞介紹：', 3)}

GUIDE_NAVIGATION_HEADINGS = {
    'manual-heading:s1c2-hypothesis': {
        'level': '初級',
        'key': 'guide1',
        'node': 's1c2',
        'subjectId': 's1',
        'title': '假說檢定名詞介紹：',
        'depth': 3,
        'anchor': '假說檢定名詞介紹',
        'pageIndex': 31,
        'hierarchyPage': 32,
        'forbiddenTitles': [],
    },
    'manual-heading:s2c3-import-strategy': {
        'level': '初級',
        'key': 'guide2',
        'node': 's2c3',
        'subjectId': 's2',
        'title': '（3） 導入策略與階段規劃',
        'depth': 4,
        'anchor': '3導入策略與階段規劃',
        'pageIndex': 37,
        'hierarchyPage': 38,
        'forbiddenTitles': ['（3）企業導入階段性實施策略企業需採取'],
    },
}


# ── 來源內容修正（2026-09-05 逐頁核對頁面影像後新增）────────────────────────
# 與上面的 heading overlay 不同：這些改的是**內容**而非結構。
# 每一筆都附頁面影像出處，且 fail-closed——來源形狀對不上就 raise，不會靜默略過。

# 原書 3-60（PDF 67）：表頭是跨兩行的圖片文字，Track A 切成兩列並丟失
# 「特徵」「生成式」「鑑別式」。頁面影像：中級/guide1/page_066/page.png
TABLE_HEADER_FIXES = {
    ('中級', 'guide1', 'mid-s1c3'): [{
        'match_rows': [['', 'AI', 'AI'], ['', 'Generative AI', 'Discriminative AI']],
        'header': ['特徵', '生成式 AI（Generative AI）', '鑑別式 AI（Discriminative AI）'],
    }],
}

# `*原圖` 是抽取階段留下的通用佔位 alt，不是原書的圖說。
# 最嚴重的案例：mid-s2c9 的十張圖共用「資料處理流程原圖」，
# 實際卻是直方圖／箱型圖／散佈圖／熱力圖／長條圖／圓餅圖等十種不同的圖。
PLACEHOLDER_ALT = re.compile(r'^.{0,12}原圖$')
ALT_LOOKBACK = 6          # 往前找幾個 block
ALT_MAX_LEN = 40          # 推導出來的圖說上限


def _alt_from_neighbour(text: str) -> str:
    """把前一個條列／標題的文字收斂成一句圖說。"""
    value = re.sub(r'\s+', ' ', str(text or '')).strip()
    value = re.sub(r'^[（(]\d+[）)]\s*', '', value)      # 去掉「（1）」這類編號
    value = re.sub(r'^[A-Z][.、]\s*', '', value)          # 去掉「C. 」
    # 「高效梯度提升方法（如XGBoost、LightGBM） 高效梯度提升方法是對傳統…」
    # 這種「名稱＋接續說明」只取名稱那一段
    closing = value.find('） ')
    if closing != -1:
        value = value[:closing + 1]
    value = re.split(r'[。！？：]', value)[0].strip()
    return value[:ALT_MAX_LEN].strip()


def derive_source_image_alts(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """通用佔位 alt → 用圖片前方最近的標題／條列命名（原書自己的用字）。"""
    result = [dict(block) for block in blocks]
    for index, block in enumerate(result):
        if block.get('type') != 'source_image':
            continue
        if not PLACEHOLDER_ALT.match(str(block.get('alt') or '')):
            continue
        for back in range(index - 1, max(-1, index - 1 - ALT_LOOKBACK), -1):
            neighbour = result[back]
            if neighbour.get('type') not in {'heading', 'list_item'}:
                continue
            candidate = _alt_from_neighbour(neighbour.get('title') or neighbour.get('text'))
            if 4 <= len(candidate) <= ALT_MAX_LEN:
                block['alt'] = candidate
                block['publicationOverlayId'] = 'source-image-alt:derived'
                break
    return result


def apply_table_header_fixes(level: str, key: str, node: str,
                             blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fixes = TABLE_HEADER_FIXES.get((level, key, node))
    if not fixes:
        return blocks
    result = [dict(block) for block in blocks]
    for fix in fixes:
        want = [[_normalized(c) for c in row] for row in fix['match_rows']]
        target = [_normalized(c) for c in fix['header']]
        hits = done = 0
        for block in result:
            rows = block.get('rows')
            if block.get('type') != 'table' or not rows:
                continue
            if [_normalized(c) for c in rows[0]] == target:
                done += 1                  # 已經是修正後的表頭
                continue
            if len(rows) < len(want) + 1:
                continue
            head = [[_normalized(c) for c in row] for row in rows[:len(want)]]
            if head != want:
                continue
            block['rows'] = [list(fix['header'])] + [list(r) for r in rows[len(want):]]
            block['publicationOverlayId'] = 'table-header-fix'
            hits += 1
        if hits + done != 1:
            raise ValueError(
                f'{level}/{key}/{node}: table header fix matched {hits} wrong + {done} '
                f'already-correct tables, expected exactly 1 in total'
            )
    return result


def _normalized(value: Any) -> str:
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', str(value or '')))


def _table_starts_with(block: dict[str, Any], title: str) -> bool:
    rows = block.get('rows') or []
    return bool(
        block.get('type') == 'table'
        and rows
        and rows[0]
        and _normalized(rows[0][0]) == _normalized(title)
    )


def apply_publication_block_overlays(
    level: str,
    key: str,
    node: str,
    blocks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return exact navigable heading blocks for source-reviewed exceptions."""
    result = [dict(block) for block in blocks]

    contract_name = 'manual-heading:s1c2-hypothesis'
    contract = GUIDE_NAVIGATION_HEADINGS[contract_name]
    if (level, key, node) == (contract['level'], contract['key'], contract['node']):
        title = str(contract['title'])
        matches = [
            index for index, block in enumerate(result)
            if block.get('type') == 'heading' and block.get('title') == title
        ]
        tables = [
            index for index, block in enumerate(result)
            if _table_starts_with(block, title)
        ]
        if len(tables) != 1 or len(matches) > 1:
            raise ValueError(
                f'{level}/{key}/{node}: hypothesis navigation source matched '
                f'headings={len(matches)}, tables={len(tables)}; expected at most one/one'
            )
        table_index = tables[0]
        if not matches:
            result.insert(table_index, {
                'type': 'heading',
                'depth': contract['depth'],
                'title': title,
                'anchor': contract['anchor'],
                'pageIndex': contract['pageIndex'],
                'sourcePageIndexes': [contract['pageIndex']],
                'bbox': [101.8, 421.61, 218.23, 434.9],
                'publicationOverlayId': contract_name,
            })
            table_index += 1
            matches = [table_index - 1]
        heading_index = matches[0]
        if heading_index + 1 != table_index:
            raise ValueError(f'{level}/{key}/{node}: hypothesis heading is not before its table')
        result[heading_index].update({
            'depth': contract['depth'],
            'anchor': contract['anchor'],
            'pageIndex': contract['pageIndex'],
            'sourcePageIndexes': [contract['pageIndex']],
            'bbox': [101.8, 421.61, 218.23, 434.9],
            'publicationOverlayId': contract_name,
        })

    contract_name = 'manual-heading:s2c3-import-strategy'
    contract = GUIDE_NAVIGATION_HEADINGS[contract_name]
    if (level, key, node) == (contract['level'], contract['key'], contract['node']):
        title = str(contract['title'])
        forbidden = set(contract['forbiddenTitles'])
        matches = [
            index for index, block in enumerate(result)
            if block.get('type') == 'heading'
            and (block.get('title') == title or block.get('title') in forbidden)
        ]
        if len(matches) != 1:
            raise ValueError(
                f'{level}/{key}/{node}: import-strategy heading matched '
                f'{len(matches)}, expected exactly one'
            )
        result[matches[0]].update({
            'title': title,
            'depth': contract['depth'],
            'anchor': contract['anchor'],
            'pageIndex': contract['pageIndex'],
            'sourcePageIndexes': [contract['pageIndex']],
            'publicationOverlayId': contract_name,
        })

    result = apply_table_header_fixes(level, key, node, result)
    result = derive_source_image_alts(result)
    return result


def apply_publication_markdown_overlays(
    level: str,
    key: str,
    node: str,
    markdown: str,
) -> str:
    """Return the exact final Markdown hierarchy, failing on source drift."""
    if (level, key, node) == ('初級', 'guide1', 's1c2'):
        title, depth = PROMOTE_HEADINGS[node]
        plain = f'\n{title}\n'
        promoted = f'\n{"#" * depth} {title}\n'
        plain_count = markdown.count(plain)
        promoted_count = markdown.count(promoted)
        if (plain_count, promoted_count) == (1, 0):
            markdown = markdown.replace(plain, promoted, 1)
        elif (plain_count, promoted_count) != (0, 1):
            raise ValueError(
                f'{level}/{key}/{node}: hypothesis heading matched '
                f'plain={plain_count}, promoted={promoted_count}; expected exactly one'
            )

    if (level, key, node) == ('初級', 'guide1', 's1c4'):
        for title in DEMOTE_HEADINGS:
            old = f'#### {title}\n'
            new = f'### {title}\n'
            # Count complete lines.  A raw substring count incorrectly treats
            # ``#### title`` as also containing ``### title``.
            lines = markdown.splitlines()
            old_count = lines.count(old.rstrip('\n'))
            new_count = lines.count(new.rstrip('\n'))
            if (old_count, new_count) == (1, 0):
                markdown = markdown.replace(old, new, 1)
            elif (old_count, new_count) != (0, 1):
                raise ValueError(
                    f'{level}/{key}/{node}: manual heading {title!r} matched '
                    f'h4={old_count}, h3={new_count}; expected exactly one'
                )

    contract = GUIDE_NAVIGATION_HEADINGS['manual-heading:s2c3-import-strategy']
    if (level, key, node) == (contract['level'], contract['key'], contract['node']):
        title = str(contract['title'])
        old_title = str(contract['forbiddenTitles'][0])
        old_line = f'{"#" * int(contract["depth"])} {old_title}'
        new_line = f'{"#" * int(contract["depth"])} {title}'
        lines = markdown.splitlines()
        old_count = lines.count(old_line)
        new_count = lines.count(new_line)
        if (old_count, new_count) == (1, 0):
            markdown = markdown.replace(old_line, new_line, 1)
        elif (old_count, new_count) != (0, 1):
            raise ValueError(
                f'{level}/{key}/{node}: import-strategy Markdown matched '
                f'old={old_count}, final={new_count}; expected exactly one'
            )
    return markdown


def apply_publication_heading_overlays(
    level: str,
    key: str,
    node: str,
    headings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return final sidebar heading metadata with exact source-reviewed titles."""
    result = [dict(heading) for heading in headings]
    if (level, key, node) == ('初級', 'guide1', 's1c2'):
        title, depth = PROMOTE_HEADINGS[node]
        matches = [heading for heading in result if heading.get('title') == title]
        if len(matches) != 1 or matches[0].get('level') != depth:
            raise ValueError(f'{level}/{key}/{node}: exact promoted heading metadata missing')

    if (level, key, node) == ('初級', 'guide1', 's1c4'):
        for title in DEMOTE_HEADINGS:
            matches = [heading for heading in result if heading.get('title') == title]
            if len(matches) != 1 or matches[0].get('level') != 3:
                raise ValueError(f'{level}/{key}/{node}: exact depth-3 metadata missing for {title!r}')
        for long_title, short_title in SHORTEN_HEADINGS.items():
            long_matches = [heading for heading in result if heading.get('title') == long_title]
            short_matches = [heading for heading in result if heading.get('title') == short_title]
            if len(long_matches) == 1 and not short_matches:
                long_matches[0]['title'] = short_title
            elif long_matches or len(short_matches) != 1:
                raise ValueError(
                    f'{level}/{key}/{node}: heading shortening contract differs for {short_title!r}'
                )

    contract = GUIDE_NAVIGATION_HEADINGS['manual-heading:s2c3-import-strategy']
    if (level, key, node) == (contract['level'], contract['key'], contract['node']):
        title = str(contract['title'])
        forbidden = set(contract['forbiddenTitles'])
        matches = [
            heading for heading in result
            if heading.get('title') == title or heading.get('title') in forbidden
        ]
        if len(matches) != 1 or matches[0].get('level') != contract['depth']:
            raise ValueError(f'{level}/{key}/{node}: exact import-strategy metadata missing')
        matches[0]['title'] = title
        matches[0]['id'] = contract['anchor']
    return result
