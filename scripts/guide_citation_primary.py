#!/usr/bin/env python3
"""Curated primary guide citations for exam reference answers.

``data/guide_citation_primary.json`` holds, per published exam question, the
guide blocks that directly support the official answer (``primary``), related
background blocks (``secondary``) and an internal note on what the guide lacks
(``gap``).  It is produced by ``scripts/generate_citation_primary.py`` and
consumed by ``scripts/export_exam_reference_answers.py``, which puts the
primary blocks first in every answer's ``citations`` and demotes the older
citations to 「補充」 so ``export_guide_exam_annotations.prominence()`` no longer
treats them as primary.

Every block reference stores the sha256 of its reader-visible text
(``guide_block_id_migrations.block_text``); the export fails closed when a
block id is gone or its text changed, so a guide rebuild can never silently
point a curated citation at a different paragraph.  ``gap`` is internal only
(exported to ``data/audit/guide_content_gaps.json``) and never reaches the
frontend.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from guide_block_id_migrations import block_text, sha256_text


ROOT = Path(__file__).resolve().parents[1]
CURATED_PATH = ROOT / 'data/guide_citation_primary.json'
GAPS_PATH = ROOT / 'data/audit/guide_content_gaps.json'
CONTENT_ROOT = ROOT / 'frontend/src/generated/guideContent'
SCHEMA_VERSION = 1
SUPPLEMENT_PREFIX = '補充：'
WHY_MAX_CHARS = 25
MAX_PRIMARY = 3
MAX_SECONDARY = 3
MAX_SECONDARY_WHEN_EMPTY = 2
# Blocks that may never be primary: chapter exercises (question or worked
# answer) and bare headings.  Worked answers may still be secondary.
NON_PRIMARY_KINDS = {'exercise_answer', 'exercise_question', 'heading'}
NON_CITABLE_KINDS = {'exercise_question'}

# Reader-facing ``why`` must not leak the production process (商品化不變量).
# Domain words such as 生成式 AI／模型 are legitimate exam content and stay allowed.
INTERNAL_TERMS_RE = re.compile(
    # 檢索／片段／候選框／實例 ID are exam vocabulary (RAG, tokenization, object
    # detection); only the prompt's own wording is banned.
    r'候選(?:段落|清單|區塊|內容)|段落(?:編號|代號|清單)|代號|(?<![A-Za-z0-9])C\d{1,2}(?![A-Za-z0-9.])'
    r'|(?<![A-Za-z])(?:id|ids|block|blocks)(?![A-Za-z0-9])|BM25'
    r'|本模型|模型(?:認為|挑選|選出)|我(?:認為|選|判斷)|AI\s*(?:挑選|選出|整理)',
)
# Common simplified-only characters; their presence means the text is not 繁體.
SIMPLIFIED_CHARS = set('这说为与数学习时实现关应计经过进发动开对将们个图层问题选项种类处来没样还从'
                       '称连续轻较义务录记论设识证读谁调负贝财购资质边运远')


def block_kind(block: dict[str, Any]) -> str:
    return str(block.get('kind') or block.get('type') or '')


def block_text_hash(block: dict[str, Any]) -> str:
    return sha256_text(block_text(block))


def why_length(why: str) -> int:
    return len(re.sub(r'\s+', '', why or ''))


def why_problems(why: str) -> list[str]:
    problems: list[str] = []
    text = str(why or '').strip()
    if not text:
        problems.append('empty why')
    if why_length(text) > WHY_MAX_CHARS:
        problems.append(f'why longer than {WHY_MAX_CHARS} chars')
    if INTERNAL_TERMS_RE.search(text):
        problems.append('why contains internal wording')
    simplified = sorted({char for char in text if char in SIMPLIFIED_CHARS})
    if simplified:
        problems.append('why contains simplified characters: ' + ''.join(simplified))
    return problems


def load_node_meta(content_root: Path = CONTENT_ROOT) -> dict[tuple[str, str], dict[str, Any]]:
    """``(guideKey, nodeId) -> {title, page_label}`` as citations display them."""
    meta: dict[tuple[str, str], dict[str, Any]] = {}
    for path in sorted(content_root.glob('*/*.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        pages = data.get('sourcePages') or []
        meta[(path.parent.name, path.stem)] = {
            'title': str(data.get('title') or ''),
            'page_label': (pages[0].get('label') if pages else None),
        }
    return meta


def _block_index(
    content: dict[str, dict[str, list[dict[str, Any]]]],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    return {
        (guide, node, str(block.get('id'))): block
        for guide, nodes in content.items()
        for node, blocks in nodes.items()
        for block in blocks
    }


def validate_payload(
    payload: Any,
    content: dict[str, dict[str, list[dict[str, Any]]]],
) -> list[str]:
    """Return every schema / content-binding error of a curated payload."""
    errors: list[str] = []
    if not isinstance(payload, dict) or payload.get('schemaVersion') != SCHEMA_VERSION:
        return [f'schemaVersion must be {SCHEMA_VERSION}']
    for field in ('method', 'generatedOn', 'model'):
        if not isinstance(payload.get(field), str) or not payload.get(field):
            errors.append(f'missing top-level {field}')
    if payload.get('method') == 'manual':
        errors.append('method must describe the generator, not "manual"')
    entries = payload.get('questions')
    if not isinstance(entries, list):
        return errors + ['questions must be a list']
    index = _block_index(content)
    seen: set[tuple[str, str]] = set()
    for position, entry in enumerate(entries):
        where = f'questions[{position}]'
        if not isinstance(entry, dict):
            errors.append(f'{where}: not an object')
            continue
        level = entry.get('level')
        identity = (str(entry.get('exam') or ''), str(entry.get('questionId') or ''))
        where = f'{level}/{identity[0]}/{identity[1]}'
        if level not in ('初級', '中級') or not all(identity):
            errors.append(f'{where}: level/exam/questionId required')
            continue
        if identity in seen:
            errors.append(f'{where}: duplicate entry')
        seen.add(identity)
        if not str(entry.get('questionFingerprint') or '').startswith('sha256:'):
            errors.append(f'{where}: questionFingerprint required')
        if not isinstance(entry.get('gap'), str):
            errors.append(f'{where}: gap must be a string')
        refs_seen: set[tuple[str, str, str]] = set()
        counts = {}
        for section, limit in (('primary', MAX_PRIMARY), ('secondary', MAX_SECONDARY)):
            refs = entry.get(section)
            if not isinstance(refs, list):
                errors.append(f'{where}: {section} must be a list')
                counts[section] = 0
                continue
            counts[section] = len(refs)
            if len(refs) > limit:
                errors.append(f'{where}: more than {limit} {section} blocks')
            for ref in refs:
                key = (str(ref.get('guideKey') or ''), str(ref.get('nodeId') or ''),
                       str(ref.get('blockId') or ''))
                label = f'{where} {section} {"/".join(key)}'
                if not key[0].startswith(f'{level}-'):
                    errors.append(f'{label}: guideKey is not in the question level')
                if key in refs_seen:
                    errors.append(f'{label}: block cited twice')
                refs_seen.add(key)
                block = index.get(key)
                if block is None:
                    errors.append(f'{label}: block is not in the current guideContent')
                    continue
                if ref.get('textHash') != block_text_hash(block):
                    errors.append(f'{label}: block text changed since curation (textHash mismatch)')
                kind = block_kind(block)
                if kind in NON_CITABLE_KINDS:
                    errors.append(f'{label}: exercise questions cannot be cited')
                if section == 'primary' and kind in NON_PRIMARY_KINDS:
                    errors.append(f'{label}: {kind} blocks may only be secondary')
                if section == 'primary' and str(ref.get('why') or '').startswith(SUPPLEMENT_PREFIX[:2]):
                    errors.append(f'{label}: primary why must not start with 補充 (read as secondary)')
                for problem in why_problems(str(ref.get('why') or '')):
                    errors.append(f'{label}: {problem}')
        if counts.get('primary') == 0 and not (
            1 <= counts.get('secondary', 0) <= MAX_SECONDARY_WHEN_EMPTY
        ):
            errors.append(f'{where}: empty primary needs 1-{MAX_SECONDARY_WHEN_EMPTY} secondary blocks')
    return errors


def load_curated(
    content: dict[str, dict[str, list[dict[str, Any]]]],
    path: Path = CURATED_PATH,
) -> dict[tuple[str, str], dict[str, Any]]:
    """``(exam routeKey, questionId) -> entry``; raises ValueError when stale."""
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding='utf-8'))
    errors = validate_payload(payload, content)
    if errors:
        shown = '\n  '.join(errors[:30])
        more = f'\n  … and {len(errors) - 30} more' if len(errors) > 30 else ''
        raise ValueError(f'Invalid curated primary citations {path}:\n  {shown}{more}')
    return {(entry['exam'], entry['questionId']): entry for entry in payload['questions']}


def _group(refs: list[dict[str, Any]], level: str) -> list[tuple[str, str, list[dict[str, Any]]]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for ref in refs:
        groups.setdefault((ref['guideKey'], ref['nodeId']), []).append(ref)
    return [(guide, node, items) for (guide, node), items in groups.items()]


def _citation(
    level: str,
    guide: str,
    node: str,
    refs: list[dict[str, Any]],
    node_meta: dict[tuple[str, str], dict[str, Any]],
    supplement: bool,
) -> dict[str, Any]:
    meta = node_meta.get((guide, node))
    if meta is None:
        raise ValueError(f'Curated citation node missing from guideContent: {guide}/{node}')
    whys = list(dict.fromkeys(str(ref['why']).strip() for ref in refs if str(ref.get('why') or '').strip()))
    why = '；'.join(whys)
    if supplement:
        why = SUPPLEMENT_PREFIX + why
    return {
        'guide_key': guide.removeprefix(f'{level}-'),
        'node_id': node,
        'title': meta['title'],
        'page_label': meta['page_label'],
        'block_ids': [str(ref['blockId']) for ref in refs],
        'why_relevant': why,
    }


def merge_answer_citations(
    level: str,
    answer: dict[str, Any],
    entry: dict[str, Any],
    node_meta: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    """Curated primary first, curated secondary next, older citations as 「補充」.

    Older citations lose blocks the curated entry already cites; a citation
    left without blocks is dropped.  Every older citation's why_relevant gets
    the 「補充：」 prefix so annotation prominence treats it as secondary.
    """
    primary = [
        _citation(level, guide, node, refs, node_meta, supplement=False)
        for guide, node, refs in _group(entry['primary'], level)
    ]
    secondary = [
        _citation(level, guide, node, refs, node_meta, supplement=True)
        for guide, node, refs in _group(entry['secondary'], level)
    ]
    used = {
        (ref['guideKey'], ref['nodeId'], str(ref['blockId']))
        for ref in entry['primary'] + entry['secondary']
    }
    older = []
    for citation in answer.get('citations') or []:
        guide = f"{level}-{citation.get('guide_key')}"
        node = str(citation.get('node_id') or '')
        block_ids = [
            block_id for block_id in citation.get('block_ids') or []
            if (guide, node, str(block_id)) not in used
        ]
        if citation.get('block_ids') and not block_ids:
            continue
        why = str(citation.get('why_relevant') or '').strip()
        if not why.startswith(SUPPLEMENT_PREFIX[:2]):
            why = SUPPLEMENT_PREFIX + why
        older.append({**citation, 'block_ids': block_ids, 'why_relevant': why})
    return {**answer, 'citations': primary + secondary + older}
