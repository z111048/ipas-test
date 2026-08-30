#!/usr/bin/env python3
"""Pure, idempotent publication hierarchy overlays shared by guide exporters.

These source-reviewed exceptions used to run only as a post-export file edit.
Keeping the transformations pure lets the staged exporter install the final
release shape directly and validate it before touching live outputs.
"""

from __future__ import annotations

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
    return result
