#!/usr/bin/env python3
"""Build reviewable guide hierarchy trees from cleaned PDF extraction outputs."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any

BASE = Path('/home/james/projects/ipas-test')
if str(BASE / 'scripts') not in sys.path:
    sys.path.insert(0, str(BASE / 'scripts'))

import export_guide_outline_data as exporter  # noqa: E402


def load_json(path: Path) -> dict:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def normalize(value: str) -> str:
    return re.sub(r'\s+', '', value or '').lower()


def page_count(node: dict) -> int:
    page_range = node.get('page_range') or [node.get('page_number'), node.get('page_number')]
    start_page, end_page = page_range
    if not start_page or not end_page:
        return 0
    return max(0, end_page - start_page + 1)


def node_page_range(node: dict) -> list[int]:
    page_range = node.get('page_range') or [node.get('page_number'), node.get('page_number')]
    return [int(page_range[0] or 0), int(page_range[1] or 0)]


def filter_duplicate_sibling_nodes(raw_nodes: list[dict]) -> list[dict]:
    return exporter.filter_duplicate_sibling_nodes(raw_nodes)


def guide_node_id(subject_id: str, node: dict, manifest_subject: dict, index_path: list[int]) -> str:
    return exporter.node_id(subject_id, node, manifest_subject, index_path)


def iter_tree(nodes: list[dict], parent_id: str | None = None, depth: int = 1):
    for order, node in enumerate(nodes, start=1):
        yield node, parent_id, depth, order
        yield from iter_tree(node.get('children') or [], node.get('id'), depth + 1)


def enumerate_nodes(
    subject_id: str,
    nodes: list[dict],
    manifest_subject: dict,
    index_path: list[int] | None = None,
    parent_id: str | None = None,
    depth: int = 1,
) -> list[dict]:
    if index_path is None:
        index_path = []

    result = []
    for order, raw_node in enumerate(nodes, start=1):
        current_path = index_path + [order]
        node = copy.deepcopy(raw_node)
        node['id'] = guide_node_id(subject_id, node, manifest_subject, current_path)
        node['parentId'] = parent_id
        node['depth'] = depth
        node['order'] = order
        node['indexPath'] = current_path
        node['children'] = enumerate_nodes(
            subject_id=subject_id,
            nodes=node.get('children') or [],
            manifest_subject=manifest_subject,
            index_path=current_path,
            parent_id=node['id'],
            depth=depth + 1,
        )
        result.append(node)
    return result


def flatten_nodes(nodes: list[dict]) -> list[dict]:
    flattened = []
    for node in nodes:
        flattened.append(node)
        flattened.extend(flatten_nodes(node.get('children') or []))
    return flattened


def block_kind(block: dict) -> str:
    if block.get('type') == 'heading':
        return 'heading'
    if block.get('type') == 'question':
        return 'exercise_question'
    if block.get('type') == 'answer':
        return 'exercise_answer'
    return block.get('type') or 'unknown'


def enrich_block(block: dict, node_id: str, index: int) -> dict:
    enriched = dict(block)
    enriched['id'] = block.get('id') or f'block-{index + 1}'
    enriched['nodeId'] = node_id
    enriched['kind'] = block_kind(block)
    enriched['source'] = 'page_extract'
    return enriched


def heading_signature(title: str) -> tuple[str, str]:
    title = title.strip()
    if match := re.match(r'^(第[一二三四五六七八九十]+章)\s+(.+)$', title):
        return ('chapter', match.group(1))
    if match := re.match(r'^(\d+\.\d+)\s+(.+)$', title):
        return ('decimal', match.group(1))
    if match := re.match(r'^(\d+)\.\s+(.+)$', title):
        return ('numbered', match.group(1))
    if match := re.match(r'^（(\d+)）\s*(.+)$', title):
        return ('paren_number', match.group(1))
    if match := re.match(r'^([A-Z])\.\s+(.+)$', title):
        return ('alpha', match.group(1))
    return ('plain', normalize(title))


def expected_next(previous: str, current: str, kind: str) -> bool:
    if kind in {'numbered', 'paren_number'} and previous.isdigit() and current.isdigit():
        return int(current) == int(previous) + 1
    if kind == 'alpha' and len(previous) == 1 and len(current) == 1:
        return ord(current) == ord(previous) + 1
    return True


def warning(severity: str, code: str, message: str, node: dict | None = None, block: dict | None = None) -> dict:
    payload = {
        'severity': severity,
        'code': code,
        'message': message,
    }
    if node:
        payload.update({
            'nodeId': node.get('id'),
            'title': node.get('title'),
            'pageRange': node_page_range(node),
        })
    if block:
        payload.update({
            'blockId': block.get('id'),
            'pageIndex': block.get('pageIndex'),
            'text': block.get('title') or block.get('text') or '',
        })
    return payload


def validate_outline_tree(nodes: list[dict]) -> list[dict]:
    warnings: list[dict] = []
    ids: set[str] = set()

    def walk(siblings: list[dict], parent: dict | None = None):
        sibling_titles: dict[str, dict] = {}
        previous_by_kind: dict[str, tuple[str, dict]] = {}
        for node in siblings:
            node_id = node.get('id')
            if node_id in ids:
                warnings.append(warning('fatal', 'duplicate_node_id', f'Duplicate node id: {node_id}', node))
            ids.add(node_id)

            if parent and node.get('depth') != int(parent.get('depth') or 0) + 1:
                warnings.append(warning('fatal', 'invalid_node_depth', 'Child node depth does not match parent depth.', node))

            start_page, end_page = node_page_range(node)
            if not start_page or not end_page or end_page < start_page:
                warnings.append(warning('fatal', 'invalid_page_range', 'Node page range is empty or reversed.', node))
            if parent:
                parent_start, parent_end = node_page_range(parent)
                if start_page < parent_start or end_page > parent_end:
                    warnings.append(warning('warn', 'child_page_range_outside_parent', 'Child page range is outside parent range.', node))

            title_key = normalize(node.get('title') or '')
            if title_key in sibling_titles:
                warnings.append(warning('warn', 'duplicate_sibling_title', 'Duplicate heading title under the same parent.', node))
            sibling_titles[title_key] = node

            kind, marker = heading_signature(node.get('title') or '')
            if kind in {'numbered', 'paren_number', 'alpha'}:
                previous = previous_by_kind.get(kind)
                if previous and not expected_next(previous[0], marker, kind):
                    warnings.append(warning('warn', f'{kind}_sequence_gap', 'Heading marker sequence is not continuous.', node))
                previous_by_kind[kind] = (marker, node)

            walk(node.get('children') or [], node)

    walk(nodes)
    return warnings


def validate_blocks(node: dict, blocks: list[dict]) -> list[dict]:
    warnings: list[dict] = []
    heading_stack: list[dict] = []
    exercise_seen = False
    question_count = 0
    answer_count = 0
    sibling_markers: dict[tuple[str, int], list[str]] = {}

    for block in blocks:
        block_type = block.get('type')
        depth = int(block.get('depth') or 0)
        text = block.get('title') or block.get('text') or ''

        if block_type == 'heading':
            if exercise_seen:
                warnings.append(warning('warn', 'heading_after_exercise', 'Heading appears after chapter exercises started.', node, block))
            if heading_stack and depth > int(heading_stack[-1].get('depth') or 0) + 1:
                warnings.append(warning('warn', 'heading_depth_jump', 'Heading depth jumps more than one level.', node, block))
            while heading_stack and int(heading_stack[-1].get('depth') or 0) >= depth:
                heading_stack.pop()
            parent_key = heading_stack[-1].get('id') if heading_stack else node.get('id', 'root')
            heading_stack.append(block)

            if match := re.match(r'^([A-Z])\.\s+', text):
                sibling_markers.setdefault((str(parent_key), depth), []).append(match.group(1))
            continue

        if block_type == 'question':
            exercise_seen = True
            question_count += 1
            if '（A）' not in text:
                warnings.append(warning('warn', 'question_missing_option_a', 'Exercise question does not contain option （A）.', node, block))
            continue

        if block_type == 'answer':
            exercise_seen = True
            answer_count += 1
            continue

        if block_type == 'list_item' and block.get('marker') in {'•', '◦', '○'} and depth <= 3:
            warnings.append(warning('warn', 'shallow_list_item', 'List item is attached too close to the chapter root.', node, block))

    for (_, depth), markers in sibling_markers.items():
        if len(markers) == 1 and markers[0] != 'A':
            warnings.append(warning('warn', 'single_alpha_heading_not_a', f'Single alpha heading at depth {depth} is not A.', node))
        expected = [chr(ord('A') + index) for index in range(len(markers))]
        if len(markers) > 1 and markers != expected:
            warnings.append(warning('warn', 'alpha_sequence_gap', f'Alpha heading sequence at depth {depth} is not continuous.', node))

    if question_count and answer_count and question_count != answer_count:
        warnings.append(warning('warn', 'exercise_question_answer_mismatch', f'Chapter exercises have {question_count} questions and {answer_count} answers.', node))
    return warnings


def build_node_blocks(level: str, key: str, node: dict) -> list[dict]:
    start_page, end_page = node_page_range(node)
    raw_blocks = exporter.page_blocks(level, key, start_page, end_page)
    processed = exporter.post_process_guide_blocks(node['id'], node.get('title') or '', raw_blocks)
    return [enrich_block(block, node['id'], index) for index, block in enumerate(processed)]


def build_guide_tree(level: str, subject: dict) -> dict:
    key = subject['key']
    outline_path = BASE / 'data' / level / 'page_clean' / key / 'outline.json'
    if not outline_path.exists():
        raise FileNotFoundError(f'Missing outline: {outline_path}')

    outline = load_json(outline_path)
    root_nodes = enumerate_nodes(
        subject_id=subject['id'],
        nodes=filter_duplicate_sibling_nodes(outline.get('outline') or []),
        manifest_subject=subject,
    )
    warnings = validate_outline_tree(root_nodes)
    blocks_by_node: dict[str, list[dict]] = {}

    for node in flatten_nodes(root_nodes):
        blocks = build_node_blocks(level, key, node)
        blocks_by_node[node['id']] = blocks
        warnings.extend(validate_blocks(node, blocks))

    flat = [node['id'] for node in flatten_nodes(root_nodes)]
    return {
        'tree': {
            'level': level,
            'subjectId': subject['id'],
            'key': key,
            'subject': subject['subject'],
            'pdf': subject['pdf'],
            'outline': root_nodes,
            'flat': flat,
            'stats': {
                **(outline.get('stats') or {}),
                'guide_tree_nodes': len(flat),
                'guide_tree_warnings': len([item for item in warnings if item['severity'] == 'warn']),
                'guide_tree_fatal': len([item for item in warnings if item['severity'] == 'fatal']),
            },
        },
        'blocks': blocks_by_node,
        'warnings': warnings,
    }


def build_level(level: str, key: str | None = None) -> list[tuple[str, int, int]]:
    manifest = load_json(BASE / 'data' / level / 'toc_manifest.json')
    result = []
    for subject in manifest.get('subjects') or []:
        if key and subject.get('key') != key:
            continue
        payload = build_guide_tree(level, subject)
        out_dir = BASE / 'data' / level / 'guide_tree' / subject['key']
        write_json(out_dir / 'tree.json', payload['tree'])
        write_json(out_dir / 'blocks.json', payload['blocks'])
        write_json(out_dir / 'warnings.json', payload['warnings'])
        fatal_count = sum(1 for item in payload['warnings'] if item['severity'] == 'fatal')
        warn_count = sum(1 for item in payload['warnings'] if item['severity'] == 'warn')
        result.append((subject['key'], warn_count, fatal_count))
    if key and not result:
        raise ValueError(f'No subject key {key!r} for level {level}')
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--level', default='初級', help='資料等級資料夾（預設: 初級）')
    parser.add_argument('--key', help='只處理單一 PDF key，例如 guide1')
    parser.add_argument('--all', action='store_true', help='處理該 level 的所有 guide')
    args = parser.parse_args()

    rows = build_level(args.level, args.key if not args.all else None)
    for key, warn_count, fatal_count in rows:
        print(f'{args.level}/{key}: guide tree built, warnings={warn_count}, fatal={fatal_count}')
    if any(fatal_count for _, _, fatal_count in rows):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
