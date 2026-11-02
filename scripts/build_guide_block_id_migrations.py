#!/usr/bin/env python3
"""Build the reviewable guide block-id migration table (deterministic, no API).

Compares the *old* published guide blocks (``frontend/src/generated/guideContent``
at a git ref, i.e. the content that reference-answer citations and image units
were generated against) with the *new* published blocks in the working tree,
and writes ``data/guide_block_id_migrations.json``:

* ``blocks``: per guide/node, every old id whose identity is not trivially
  preserved — ``exact`` (same text, different id), ``normalized`` (NFKC /
  whitespace / bullet-insensitive equal; covers 「(」→「（」), ``fuzzy``
  (difflib ratio ≥ threshold on the same ±1 page, recorded with ``ratio``) and
  ``unmapped`` (``new: null``).  Old ids absent from the table map to
  themselves (exact text, same id).
* ``citationScope`` / ``imageUnitsScope``: digests of the inputs the table may
  rewrite (old published reference answers per exam; the image-unit file, only
  while it is still byte-identical to the old ref — a unit file whose ids were
  already rebased onto the new content is left out and only validated).
* ``citations``: question-specific ``auto-citation`` resolutions for citations
  that point at an unmapped old block (e.g. the 初級 s1pdf-c3 giant answer
  blocks).  Candidates are the new blocks of the same node that fill the gap
  between the new positions of the old block's nearest mapped neighbours
  (i.e. exactly what the split block became, inside its page range); when the
  neighbours are not monotone, the page range of new blocks whose text is
  contained in the old block is used instead.  Candidates are ranked by
  character-bigram BM25 against the citation's ``why_relevant`` (the stem is
  only a fallback).  A winner whose lead over the runner-up is at least the
  relative-margin threshold is written as ``auto-citation`` (still reviewed
  per item); every other case goes to ``unresolvedCitations`` with its top
  candidates and needs a curated
  ``data/guide_citation_overrides.json`` entry (remap or remove).

Usage (after ``export_guide_outline_data.py`` rebuilt guideContent):

    python3 scripts/build_guide_block_id_migrations.py --old-ref 153f13d
    python3 scripts/build_guide_block_id_migrations.py --check   # committed table is current
"""

from __future__ import annotations

import argparse
import difflib
import json
import math
import re
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from guide_block_id_migrations import (
    DEFAULT_CONTENT_ROOT,
    MIGRATIONS_PATH,
    OVERRIDES_PATH,
    SCHEMA_VERSION,
    block_text,
    guide_content_sha256,
    load_content_tree,
    normalized_block_text,
    reference_answers_digest,
    sha256_bytes,
    validate_overrides,
)
from resource_catalog import exam_entries, level_entries

ROOT = Path(__file__).resolve().parents[1]
CONTENT_REL = 'frontend/src/generated/guideContent'
REFERENCE_REL = 'frontend/src/generated/examReferenceAnswers'
GUIDE_IMAGES_REL = 'frontend/src/generated/guideImages.json'
FUZZY_THRESHOLD = 0.80
# Auto-apply only when the winner leads the runner-up by >= 30% of its score.
# Calibration (shadow rebuild, 1,827 mapped citations, ±60-block windows):
# coverage 50%, top-1 within ±1 block of a true cited block 94.2%.
CITATION_MIN_RELATIVE_MARGIN = 0.30
REVIEW_CANDIDATES = 5
TEXT_PREVIEW = 80
TEXT_TYPES = {'paragraph', 'list_item', 'heading'}


# -- git access (read-only) ----------------------------------------------------

def git(*args: str) -> bytes:
    result = subprocess.run(['git', *args], cwd=ROOT, capture_output=True, check=False)
    if result.returncode != 0:
        raise SystemExit(f'git {" ".join(args)} failed: {result.stderr.decode(errors="replace").strip()}')
    return result.stdout


def resolve_ref(ref: str) -> str:
    return git('rev-parse', '--verify', f'{ref}^{{commit}}').decode().strip()


def git_json(ref: str, rel_path: str) -> Any:
    return json.loads(git('show', f'{ref}:{rel_path}').decode('utf-8'))


def load_git_content_tree(ref: str) -> dict[str, dict[str, list[dict[str, Any]]]]:
    names = git('ls-tree', '-r', '--name-only', ref, '--', CONTENT_REL).decode('utf-8').splitlines()
    tree: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for name in sorted(names):
        path = Path(name)
        if path.suffix != '.json' or path.parent.parent.as_posix() != CONTENT_REL:
            continue
        data = git_json(ref, name)
        tree.setdefault(path.parent.name, {})[path.stem] = list(data.get('blocks') or [])
    if not tree:
        raise SystemExit(f'No guideContent found at {ref}:{CONTENT_REL}')
    return tree


# -- block mapping ---------------------------------------------------------------

def types_compatible(old_type: Any, new_type: Any) -> bool:
    return old_type == new_type or {old_type, new_type} <= TEXT_TYPES


def map_node(
    old_blocks: list[dict[str, Any]],
    new_blocks: list[dict[str, Any]],
    fuzzy_threshold: float,
) -> dict[str, dict[str, Any]]:
    """Deterministic old→new mapping for one node (all old ids)."""
    exact_index: dict[tuple[Any, str], list[str]] = defaultdict(list)
    normalized_index: dict[str, list[str]] = defaultdict(list)
    for block in new_blocks:
        text = block_text(block)
        exact_index[(block.get('type'), text)].append(str(block['id']))
        normalized_index[normalized_block_text(text)].append(str(block['id']))
    claimed: set[str] = set()
    mapping: dict[str, dict[str, Any]] = {}
    pending: list[dict[str, Any]] = []
    for block in old_blocks:
        candidates = [
            new_id for new_id in exact_index.get((block.get('type'), block_text(block)), [])
            if new_id not in claimed
        ]
        if candidates:
            claimed.add(candidates[0])
            mapping[str(block['id'])] = {'new': candidates[0], 'method': 'exact'}
        else:
            pending.append(block)
    still_pending: list[dict[str, Any]] = []
    for block in pending:
        normalized = normalized_block_text(block_text(block))
        candidates = [
            new_id for new_id in normalized_index.get(normalized, [])
            if new_id not in claimed
        ] if normalized else []
        if candidates:
            claimed.add(candidates[0])
            mapping[str(block['id'])] = {'new': candidates[0], 'method': 'normalized'}
        else:
            still_pending.append(block)
    normalized_new = {str(block['id']): normalized_block_text(block_text(block)) for block in new_blocks}
    for block in still_pending:
        normalized = normalized_block_text(block_text(block))
        page = block.get('pageIndex')
        best_ratio, best_id = 0.0, None
        for candidate in new_blocks:
            candidate_id = str(candidate['id'])
            if candidate_id in claimed:
                continue
            candidate_page = candidate.get('pageIndex')
            if isinstance(page, int) and isinstance(candidate_page, int) and abs(page - candidate_page) > 1:
                continue
            if not types_compatible(block.get('type'), candidate.get('type')):
                continue
            ratio = difflib.SequenceMatcher(
                None, normalized, normalized_new[candidate_id], autojunk=False
            ).ratio() if normalized else 0.0
            if ratio > best_ratio:
                best_ratio, best_id = ratio, candidate_id
        if best_id is not None and best_ratio >= fuzzy_threshold:
            claimed.add(best_id)
            mapping[str(block['id'])] = {'new': best_id, 'method': 'fuzzy', 'ratio': round(best_ratio, 3)}
        else:
            mapping[str(block['id'])] = {
                'new': None, 'method': 'unmapped', 'ratio': round(best_ratio, 3),
                'type': block.get('type'), 'pageIndex': page,
                'text': block_text(block)[:TEXT_PREVIEW],
            }
    return mapping


def table_entry(old_id: str, entry: dict[str, Any]) -> dict[str, Any] | None:
    """Keep only entries a reviewer must see; exact same-id is implicit identity."""
    if entry['method'] == 'exact' and entry['new'] == old_id:
        return None
    return entry


# -- citation auto-resolution ----------------------------------------------------

_TOKEN_STRIP_RE = re.compile(r'[\W_]+', re.UNICODE)


def bigrams(text: str) -> Counter[str]:
    value = _TOKEN_STRIP_RE.sub('', unicodedata.normalize('NFKC', text or '').lower())
    return Counter(value[index:index + 2] for index in range(len(value) - 1))


def contained_in(old_normalized: str, block: dict[str, Any]) -> bool:
    text = normalized_block_text(block_text(block))
    if len(text) < 4:
        return False
    if text in old_normalized:
        return True
    if len(text) < 12:
        return False
    grams = {text[index:index + 4] for index in range(len(text) - 3)}
    hits = sum(1 for gram in grams if gram in old_normalized)
    return hits / len(grams) >= 0.8


def rank_candidates(
    query: Counter[str], candidates: list[dict[str, Any]],
) -> list[tuple[float, int, dict[str, Any]]]:
    """Okapi BM25 over character bigrams (k1=1.2, b=0.75), stable tie order."""
    docs = [bigrams(block_text(block)) for block in candidates]
    total = len(docs)
    if not total:
        return []
    average_length = sum(sum(doc.values()) for doc in docs) / total or 1.0
    document_frequency: Counter[str] = Counter()
    for doc in docs:
        document_frequency.update(doc.keys())
    ranked = []
    for order, (block, doc) in enumerate(zip(candidates, docs)):
        length = sum(doc.values())
        score = 0.0
        for gram, query_weight in query.items():
            frequency = doc.get(gram, 0)
            if not frequency:
                continue
            df = document_frequency[gram]
            idf = math.log(1 + (total - df + 0.5) / (df + 0.5))
            score += query_weight * idf * frequency * 2.2 / (
                frequency + 1.2 * (0.25 + 0.75 * length / average_length)
            )
        ranked.append((round(score, 4), order, block))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return ranked


def citation_query(citation: dict[str, Any], question: dict[str, Any] | None) -> Counter[str]:
    """``why_relevant`` describes the cited block; the stem is only a fallback.

    Calibration on the 1,827 already-mapped citations (shadow rebuild, ±60
    block window): why-only BM25 beat why+stem/options and TF-IDF cosine.
    """
    query = bigrams(str(citation.get('why_relevant') or ''))
    if not query and question:
        query = bigrams(str(question.get('question') or ''))
    return query


def candidate_summary(score: float, block: dict[str, Any], contained: bool) -> dict[str, Any]:
    return {
        'id': str(block['id']), 'score': score, 'pageIndex': block.get('pageIndex'),
        'type': block.get('type'), 'containedInOld': contained,
        'text': block_text(block)[:TEXT_PREVIEW],
    }


def old_block_window(
    old_blocks: list[dict[str, Any]],
    new_blocks: list[dict[str, Any]],
    mapping: dict[str, dict[str, Any]],
    old_id: str,
) -> list[dict[str, Any]] | None:
    """New blocks strictly between the new positions of the nearest mapped old neighbours.

    An unmapped old block (typically one giant block that the rebuild split
    into many) occupies exactly the gap between its mapped predecessor and
    successor.  Returns None when the neighbours are not monotone.
    """
    old_ids = [str(block['id']) for block in old_blocks]
    if old_id not in old_ids:
        return None
    new_position = {str(block['id']): index for index, block in enumerate(new_blocks)}
    position = old_ids.index(old_id)
    low = -1
    for previous in reversed(old_ids[:position]):
        target = mapping.get(previous, {}).get('new')
        if target is not None:
            low = new_position[target]
            break
    high = len(new_blocks)
    for following in old_ids[position + 1:]:
        target = mapping.get(following, {}).get('new')
        if target is not None:
            high = new_position[target]
            break
    if high - low < 2:
        return None
    return new_blocks[low + 1:high]


def resolve_unmapped_citation(
    old_block: dict[str, Any] | None,
    window: list[dict[str, Any]] | None,
    new_blocks: list[dict[str, Any]],
    citation: dict[str, Any],
    question: dict[str, Any] | None,
    min_relative_margin: float,
) -> dict[str, Any]:
    if old_block is None:
        return {'status': 'unresolved', 'why': 'old block id does not exist in the old content', 'candidates': []}
    old_normalized = normalized_block_text(block_text(old_block))
    if window:
        # Exact gap left by the split block: every candidate belongs to it.
        candidates = [block for block in window if block.get('type') != 'source_image']
        candidate_source = 'neighbour-window'
    else:
        contained = [block for block in new_blocks if contained_in(old_normalized, block)]
        pages = {block.get('pageIndex') for block in contained}
        if isinstance(old_block.get('pageIndex'), int):
            pages.add(old_block['pageIndex'])
        pages.discard(None)
        if not pages:
            return {'status': 'unresolved', 'why': 'old block has no page range', 'candidates': []}
        low, high = min(pages), max(pages)
        candidates = [
            block for block in new_blocks
            if isinstance(block.get('pageIndex'), int) and low <= block['pageIndex'] <= high
            and block.get('type') != 'source_image'
        ]
        candidate_source = 'contained-page-range'
    contained_ids = {str(block['id']) for block in candidates if contained_in(old_normalized, block)}
    candidate_pages = [block['pageIndex'] for block in candidates if isinstance(block.get('pageIndex'), int)]
    ranked = rank_candidates(citation_query(citation, question), candidates)
    shown = [
        candidate_summary(score, block, str(block['id']) in contained_ids)
        for score, _, block in ranked[:REVIEW_CANDIDATES]
    ]
    result: dict[str, Any] = {
        'candidateSource': candidate_source,
        'candidateCount': len(candidates),
        'pageRange': [min(candidate_pages), max(candidate_pages)] if candidate_pages else None,
        'candidates': shown,
    }
    if not ranked:
        return {**result, 'status': 'unresolved', 'why': 'no candidates'}
    top_score, _, top_block = ranked[0]
    second = ranked[1][0] if len(ranked) > 1 else 0.0
    relative_margin = round((top_score - second) / top_score, 4) if top_score > 0 else 0.0
    result.update({'score': top_score, 'relativeMargin': relative_margin})
    reasons = []
    if candidate_source != 'neighbour-window' and str(top_block['id']) not in contained_ids:
        reasons.append('best candidate is not part of the old block text')
    if top_score <= 0:
        reasons.append('no lexical overlap')
    if relative_margin < min_relative_margin:
        reasons.append(f'relative margin {relative_margin} < {min_relative_margin}')
    if reasons:
        return {**result, 'status': 'unresolved', 'why': '; '.join(reasons)}
    return {**result, 'status': 'resolved', 'newBlockIds': [str(top_block['id'])]}


def question_lookup(level: str, question_file: str) -> tuple[dict[str, dict], dict[int, dict]]:
    path = ROOT / 'data' / level / 'questions' / question_file
    questions = json.loads(path.read_text(encoding='utf-8')).get('questions') or []
    by_id = {str(item.get('id')): item for item in questions if item.get('id')}
    by_number: dict[int, dict] = {}
    for item in questions:
        match = re.search(r'_q(\d+)$', str(item.get('id') or ''))
        if match:
            by_number[int(match.group(1))] = item
    return by_id, by_number


def find_question(question_id: str, by_id: dict[str, dict], by_number: dict[int, dict]) -> dict | None:
    if question_id in by_id:
        return by_id[question_id]
    match = re.search(r'_q(\d+)$', question_id)
    return by_number.get(int(match.group(1))) if match else None


# -- table assembly ----------------------------------------------------------------

def build_table(
    old_ref: str,
    new_root: Path,
    *,
    fuzzy_threshold: float = FUZZY_THRESHOLD,
    min_relative_margin: float = CITATION_MIN_RELATIVE_MARGIN,
    overrides_path: Path = OVERRIDES_PATH,
    excluded_scopes: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    old_sha = resolve_ref(old_ref)
    old_tree = load_git_content_tree(old_sha)
    new_tree = load_content_tree(new_root)
    if set(old_tree) != set(new_tree):
        raise SystemExit(f'guide set differs: old={sorted(old_tree)} new={sorted(new_tree)}')

    blocks_table: dict[str, dict[str, dict[str, Any]]] = {}
    full_mapping: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
    stats: dict[str, Counter[str]] = {}
    for guide in sorted(old_tree):
        guide_stats: Counter[str] = Counter()
        guide_table: dict[str, dict[str, Any]] = {}
        full_mapping[guide] = {}
        for node in sorted(set(old_tree[guide]) | set(new_tree[guide])):
            old_blocks = old_tree[guide].get(node, [])
            new_blocks = new_tree[guide].get(node, [])
            mapping = map_node(old_blocks, new_blocks, fuzzy_threshold)
            full_mapping[guide][node] = mapping
            node_table = {}
            for old_id, entry in mapping.items():
                guide_stats[entry['method']] += 1
                if entry['new'] is not None and entry['new'] != old_id:
                    guide_stats['idChanged'] += 1
                kept = table_entry(old_id, entry)
                if kept is not None:
                    node_table[old_id] = kept
            guide_stats['oldBlocks'] += len(old_blocks)
            guide_stats['newBlocks'] += len(new_blocks)
            claimed = {entry['new'] for entry in mapping.values() if entry['new']}
            guide_stats['newUnclaimed'] += sum(1 for block in new_blocks if str(block['id']) not in claimed)
            if node_table:
                guide_table[node] = dict(sorted(node_table.items(), key=lambda item: block_order(item[0])))
        blocks_table[guide] = guide_table
        stats[guide] = guide_stats

    overrides_payload = (
        json.loads(overrides_path.read_text(encoding='utf-8')) if overrides_path.exists() else None
    )
    overrides = validate_overrides(overrides_payload, overrides_path) if overrides_payload else []

    citation_scope: dict[str, str] = {}
    auto_citations: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    citation_stats: Counter[str] = Counter()
    old_index = {
        (guide, node): {str(block['id']): block for block in blocks}
        for guide, nodes in old_tree.items() for node, blocks in nodes.items()
    }
    for level_config in level_entries():
        level = level_config['dataLevel']
        for exam in exam_entries(level=level):
            rel = f"{REFERENCE_REL}/{exam['routeKey']}.json"
            try:
                answers = git_json(old_sha, rel)
            except SystemExit:
                continue
            scope_key = f"{level}/{exam['key']}"
            if scope_key in excluded_scopes:
                continue  # regenerated against the new content: validate only
            citation_scope[scope_key] = reference_answers_digest(answers)
            by_id, by_number = question_lookup(level, exam['questionFile'])
            for question_id, answer in sorted(answers.items()):
                for citation_index, citation in enumerate(answer.get('citations') or []):
                    guide = f"{level}-{citation.get('guide_key')}"
                    node = str(citation.get('node_id') or '')
                    for old_id in citation.get('block_ids') or []:
                        old_id = str(old_id)
                        citation_stats['blockRefs'] += 1
                        entry = full_mapping.get(guide, {}).get(node, {}).get(old_id)
                        if entry is not None and entry['new'] is not None:
                            citation_stats[f"block:{entry['method']}"] += 1
                            continue
                        key = {
                            'level': level, 'exam': exam['key'], 'questionId': question_id,
                            'citationIndex': citation_index, 'guideKey': guide, 'nodeId': node,
                            'oldBlockId': old_id,
                        }
                        override = next((
                            item for item in overrides
                            if all(item[field] == key[field] for field in (
                                'level', 'exam', 'questionId', 'guideKey', 'nodeId', 'oldBlockId'))
                            and item.get('citationIndex') in (None, citation_index)
                        ), None)
                        old_node_blocks = old_tree.get(guide, {}).get(node, [])
                        new_node_blocks = new_tree.get(guide, {}).get(node, [])
                        resolution = resolve_unmapped_citation(
                            old_index.get((guide, node), {}).get(old_id),
                            old_block_window(
                                old_node_blocks, new_node_blocks,
                                full_mapping.get(guide, {}).get(node, {}), old_id,
                            ),
                            new_node_blocks,
                            citation,
                            find_question(question_id, by_id, by_number),
                            min_relative_margin,
                        )
                        record = {
                            **key,
                            'whyRelevant': citation.get('why_relevant'),
                            **{k: v for k, v in resolution.items() if k != 'status'},
                        }
                        if resolution['status'] == 'resolved' and override is None:
                            record['method'] = 'auto-citation'
                            auto_citations.append(record)
                            citation_stats['autoCitation'] += 1
                        else:
                            if override is not None:
                                record['override'] = override['action']
                                citation_stats[f"override:{override['action']}"] += 1
                            else:
                                citation_stats['unresolvedWithoutOverride'] += 1
                            unresolved.append(record)

    image_scope: dict[str, str] = {}
    try:
        images = git_json(old_sha, GUIDE_IMAGES_REL)
    except SystemExit:
        images = None
    if images and images.get('source'):
        old_units = git('show', f"{old_sha}:{images['source']}")
        current_units = ROOT / images['source']
        # Only an image-unit file still byte-identical to the old ref carries old
        # ids. A file rebased onto the new content (2026-11-02: headingBlockId
        # realigned by title) holds current ids: it is validated, never remapped.
        if current_units.exists() and current_units.read_bytes() == old_units:
            image_scope[images['source']] = sha256_bytes(old_units)

    return {
        'schemaVersion': SCHEMA_VERSION,
        'generator': 'scripts/build_guide_block_id_migrations.py',
        'description': (
            'Old→new published guide block ids. Old ids not listed map to themselves. '
            'Applied at export by export_exam_reference_answers.py (citations) and '
            'export_guide_images_data.py (headingBlockId); see scripts/guide_block_id_migrations.py.'
        ),
        'from': {
            'gitRef': old_sha,
            'contentRoot': CONTENT_REL,
            'guideSha256': {guide: guide_content_sha256(old_tree[guide]) for guide in sorted(old_tree)},
        },
        'to': {
            'contentRoot': CONTENT_REL,
            'guideSha256': {guide: guide_content_sha256(new_tree[guide]) for guide in sorted(new_tree)},
        },
        'thresholds': {
            'fuzzyRatio': fuzzy_threshold,
            'citationScorer': 'bm25-char-bigram(why_relevant)',
            'citationMinRelativeMargin': min_relative_margin,
        },
        'stats': {
            'blocks': {guide: dict(sorted(counter.items())) for guide, counter in sorted(stats.items())},
            'citations': dict(sorted(citation_stats.items())),
        },
        'citationScope': dict(sorted(citation_scope.items())),
        'citationScopeExcluded': sorted(excluded_scopes),
        'imageUnitsScope': image_scope,
        'blocks': blocks_table,
        'citations': auto_citations,
        'unresolvedCitations': unresolved,
    }


def block_order(block_id: str) -> tuple[int, str]:
    suffix = block_id.removeprefix('block-')
    return (int(suffix), block_id) if suffix.isdigit() else (sys.maxsize, block_id)


def dump_table(value: Any, indent: int = 0) -> str:
    """Pretty JSON where flat records stay on one line (reviewable diffs)."""
    pad = '  ' * indent
    inner = '  ' * (indent + 1)

    def is_leaf(item: Any) -> bool:
        if isinstance(item, dict):
            return all(not isinstance(v, (dict, list)) or (isinstance(v, list) and all(
                not isinstance(x, (dict, list)) for x in v)) for v in item.values())
        if isinstance(item, list):
            return all(not isinstance(x, (dict, list)) for x in item)
        return True

    if is_leaf(value):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, dict):
        if not value:
            return '{}'
        parts = [f'{inner}{json.dumps(k, ensure_ascii=False)}: {dump_table(v, indent + 1)}' for k, v in value.items()]
        return '{\n' + ',\n'.join(parts) + f'\n{pad}}}'
    if not value:
        return '[]'
    parts = [f'{inner}{dump_table(item, indent + 1)}' for item in value]
    return '[\n' + ',\n'.join(parts) + f'\n{pad}]'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--old-ref', help='git ref of the old published guideContent (default: the committed table\'s from.gitRef)')
    parser.add_argument('--new-root', type=Path, default=DEFAULT_CONTENT_ROOT)
    parser.add_argument('--output', type=Path, default=MIGRATIONS_PATH)
    parser.add_argument('--overrides', type=Path, default=OVERRIDES_PATH)
    parser.add_argument('--fuzzy-threshold', type=float, default=FUZZY_THRESHOLD)
    parser.add_argument('--citation-min-relative-margin', type=float, default=CITATION_MIN_RELATIVE_MARGIN)
    parser.add_argument(
        '--exclude-citation-scope', action='append', default=[], metavar='LEVEL/EXAM',
        help='exam whose reference answers were regenerated against the new content '
             '(never remapped; ids are only validated). Persisted in the table.',
    )
    parser.add_argument('--check', action='store_true', help='exit 1 if --output differs from a fresh build')
    args = parser.parse_args()

    output = args.output if args.output.is_absolute() else ROOT / args.output
    new_root = args.new_root if args.new_root.is_absolute() else ROOT / args.new_root
    overrides = args.overrides if args.overrides.is_absolute() else ROOT / args.overrides
    old_ref = args.old_ref
    excluded = set(args.exclude_citation_scope)
    if output.exists():
        existing = json.loads(output.read_text(encoding='utf-8'))
        old_ref = old_ref or existing['from']['gitRef']
        excluded |= set(existing.get('citationScopeExcluded') or [])
    if not old_ref:
        raise SystemExit('--old-ref is required when no migration table exists yet')

    table = build_table(
        old_ref, new_root,
        fuzzy_threshold=args.fuzzy_threshold,
        min_relative_margin=args.citation_min_relative_margin,
        overrides_path=overrides,
        excluded_scopes=frozenset(excluded),
    )
    text = dump_table(table) + '\n'
    for guide, counter in table['stats']['blocks'].items():
        print(guide, counter)
    print('citations', table['stats']['citations'])
    if args.check:
        if not output.exists() or output.read_text(encoding='utf-8') != text:
            print(f'FAIL {output} is stale; rerun without --check')
            raise SystemExit(1)
        print(f'OK {output} is current')
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding='utf-8')
    print(f'Wrote {output}')
    if table['stats']['citations'].get('unresolvedWithoutOverride'):
        print(
            'NOTE unresolvedCitations without override: '
            f"{table['stats']['citations']['unresolvedWithoutOverride']} — review candidates in "
            f'{output.name} and add remap/remove entries to {overrides.name}; '
            'export_exam_reference_answers.py fails closed until they are resolved'
        )


if __name__ == '__main__':
    main()
