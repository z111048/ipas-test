#!/usr/bin/env python3
"""Derive the mind-map data for the guide tree, weighted by past-exam frequency.

Reads only committed artifacts — no API calls, no pipeline reruns:
  frontend/src/generated/guideNav.json              chapter/section tree (SSOT: guideHierarchy)
  frontend/src/generated/guideExamAnnotations/      official past-exam citations per chapter
  frontend/src/generated/guideContent/              chapter text (for the density metric)

Writes frontend/src/generated/guideMindmap/{subjectId}.json plus an index.

Two things the numbers do NOT mean, and the UI must not imply otherwise:
  * Counts are DISTINCT questions citing that chapter. They are not additive across
    chapters — one question usually cites several, so the column sums to ~905 while
    only 450 official questions exist. Never render a total by summing nodes.
  * Only chapters carry counts today; the annotations do not resolve below chapter
    level. Section nodes are emitted with `q: null` so the UI can grey them out
    rather than draw a fake zero.

Density (questions per 1,000 characters) is emitted alongside the raw count because
chapter length varies by an order of magnitude — mid-s1c1 is 36,918 characters, so a
raw count ranks "long" as "hot".

Usage:
  python3 scripts/export_guide_mindmap.py [--check]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
GENERATED = BASE / 'frontend' / 'src' / 'generated'
NAV_PATH = GENERATED / 'guideNav.json'
ANNOTATION_INDEX = GENERATED / 'guideExamAnnotations' / 'index.json'
CONTENT_DIR = GENERATED / 'guideContent'
OUT_DIR = GENERATED / 'guideMindmap'


def load_json(path: Path) -> Any:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n',
                    encoding='utf-8')


def chapter_char_counts(guide_key: str) -> dict[str, int]:
    """Characters of guide text per node, for the density metric."""
    counts: dict[str, int] = {}
    guide_dir = CONTENT_DIR / guide_key
    if not guide_dir.is_dir():
        return counts
    for path in guide_dir.glob('*.json'):
        data = load_json(path)
        content = data.get('content')
        if isinstance(content, str):
            counts[path.stem] = len(content)
    return counts


def build_guide(subject_id: str, guide: dict[str, Any],
                annotations: dict[str, dict[str, Any]]) -> dict[str, Any]:
    nodes_by_id = guide['nodesById']
    chars = chapter_char_counts(guide['key'])
    hits = annotations.get(guide['key'], {})

    nodes = []
    for node_id, node in nodes_by_id.items():
        stat = hits.get(node_id)
        questions = stat['questions'] if stat else None
        size = chars.get(node_id)
        density = None
        if questions and size:
            density = round(questions / size * 1000, 3)
        nodes.append({
            'i': node_id,
            'p': node.get('parentId'),
            't': node.get('title', ''),
            'd': node.get('depth', 1),
            'k': node.get('kind', ''),
            'r': node.get('route'),
            'c': size,
            'q': questions,
            'y': density,
        })

    # Subtree totals cannot be summed (a question cites several chapters), so the
    # roll-up is a max over descendants — "the hottest thing under here".
    by_id = {n['i']: n for n in nodes}
    children: dict[str | None, list[str]] = {}
    for node in nodes:
        children.setdefault(node['p'], []).append(node['i'])

    def peak(node_id: str) -> int:
        node = by_id[node_id]
        best = node['q'] or 0
        for child in children.get(node_id, []):
            best = max(best, peak(child))
        node['Q'] = best
        return best

    for root in guide['rootIds']:
        peak(root)

    ranked = sorted((n['q'] for n in nodes if n['q'] is not None), reverse=True)
    for node in nodes:
        if node['q'] is None:
            node['h'] = None
            continue
        # percentile among chapters that have any citation at all
        below = sum(1 for value in ranked if value < node['q'])
        node['h'] = round(below / max(len(ranked) - 1, 1), 3)

    return {
        'subjectId': subject_id,
        'level': guide['level'],
        'subject': guide['subject'],
        'guideKey': guide['key'],
        'rootIds': guide['rootIds'],
        'scoredNodes': len(ranked),
        'nodes': nodes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--check', action='store_true',
                        help='print the ranking instead of writing files')
    args = parser.parse_args()

    nav = load_json(NAV_PATH)
    annotations = load_json(ANNOTATION_INDEX)['byGuide']

    index = {'levels': nav['levels'], 'guides': []}
    for subject_id, guide in nav['guides'].items():
        payload = build_guide(subject_id, guide, annotations)
        hot = sorted((n for n in payload['nodes'] if n['q']),
                     key=lambda n: n['q'], reverse=True)[:5]
        if args.check:
            print(f'{subject_id:8} {payload["subject"]}')
            print(f'  節點 {len(payload["nodes"]):3}  有熱度 {payload["scoredNodes"]:2}')
            for node in hot:
                print(f'    {node["q"]:4} 題  密度 {node["y"] or 0:5.2f}/千字  '
                      f'{node["t"][:34]}')
            continue
        save_json(OUT_DIR / f'{subject_id}.json', payload)
        index['guides'].append({
            'subjectId': subject_id,
            'level': guide['level'],
            'subject': guide['subject'],
            'nodes': len(payload['nodes']),
            'scoredNodes': payload['scoredNodes'],
            'topChapter': {'id': hot[0]['i'], 'title': hot[0]['t'], 'questions': hot[0]['q']}
                          if hot else None,
        })

    if not args.check:
        save_json(OUT_DIR / 'index.json', index)
        total = sum(g['nodes'] for g in index['guides'])
        print(f'wrote {len(index["guides"])} guide(s), {total} nodes → '
              f'{OUT_DIR.relative_to(BASE)}')


if __name__ == '__main__':
    main()
