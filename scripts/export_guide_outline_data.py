#!/usr/bin/env python3
"""Export cleaned PDF guide outlines and split content for static frontend imports."""

import json
import re
import shutil
from pathlib import Path
from typing import Any

BASE = Path('/home/james/projects/ipas-test')
LEVEL = '初級'


def load_json(path: Path) -> dict:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def normalize(value: str) -> str:
    return re.sub(r'\s+', '', value).lower()


def page_content(key: str, start_page: int, end_page: int) -> str:
    pages_dir = BASE / 'data' / LEVEL / 'page_clean' / key / 'pages'
    chunks = []
    for page_number in range(start_page, end_page + 1):
        page = load_json(pages_dir / f'page_{page_number - 1:03d}.json')
        text = page.get('cleaned_text') or ''
        if text:
            chunks.append(text)
    return '\n\n'.join(chunks).strip()


def source_pages(key: str, start_page: int, end_page: int) -> list[dict]:
    pages_dir = BASE / 'data' / LEVEL / 'page_clean' / key / 'pages'
    result = []
    for page_number in range(start_page, end_page + 1):
        page_index = page_number - 1
        page_path = pages_dir / f'page_{page_index:03d}.json'
        if not page_path.exists():
            continue
        page = load_json(page_path)
        result.append({
            'index': page_index,
            'page': page_number,
            'label': page.get('page_label') or '',
            'image': f'/pdf-assets/{LEVEL}/{key}/page_{page_index:03d}/page.png',
        })
    return result


def node_id(subject_id: str, node: dict, manifest_subject: dict, index_path: list[int]) -> str:
    number = node.get('number')
    title = normalize(node.get('title') or '')
    if number:
        for chapter in manifest_subject.get('chapters', []):
            if chapter.get('start_page') == node.get('page_label'):
                return chapter['id']
            if normalize(chapter.get('title') or '') == title:
                return chapter['id']
    return f'{subject_id}pdf-c{"-".join(str(part) for part in index_path)}'


def build_nodes(
    subject_id: str,
    key: str,
    raw_nodes: list[dict],
    manifest_subject: dict,
    content_dir: Path,
    parent_id: str | None = None,
    depth: int = 1,
    index_path: list[int] | None = None,
    nodes_by_id: dict[str, dict] | None = None,
) -> list[str]:
    if index_path is None:
        index_path = []
    if nodes_by_id is None:
        nodes_by_id = {}

    child_ids = []
    for order, raw_node in enumerate(raw_nodes, start=1):
        current_path = index_path + [order]
        current_id = node_id(subject_id, raw_node, manifest_subject, current_path)
        if current_id in nodes_by_id:
            raise ValueError(f'Duplicate guide node id: {current_id}')

        page_range = raw_node.get('page_range') or [raw_node.get('page_number'), raw_node.get('page_number')]
        start_page, end_page = page_range
        if not start_page or not end_page or end_page < start_page:
            raise ValueError(f'Invalid page range for {current_id}: {page_range}')

        child_node_ids = build_nodes(
            subject_id=subject_id,
            key=key,
            raw_nodes=raw_node.get('children', []),
            manifest_subject=manifest_subject,
            content_dir=content_dir,
            parent_id=current_id,
            depth=depth + 1,
            index_path=current_path,
            nodes_by_id=nodes_by_id,
        )
        for child_id in child_node_ids:
            child_depth = nodes_by_id[child_id]['depth']
            if child_depth != depth + 1:
                raise ValueError(f'Invalid depth for child {child_id}: {child_depth}')

        content_ref = f'{current_id}.json'
        content = page_content(key, start_page, end_page)
        write_json(content_dir / key / content_ref, {
            'id': current_id,
            'title': raw_node.get('title') or '',
            'content': f'# {raw_node.get("title") or ""}\n\n{content}'.strip(),
            'contentFormat': 'markdown',
            'sourcePages': source_pages(key, start_page, end_page),
        })

        nodes_by_id[current_id] = {
            'id': current_id,
            'parentId': parent_id,
            'depth': depth,
            'order': order,
            'number': raw_node.get('number'),
            'title': raw_node.get('title') or '',
            'pageLabel': raw_node.get('page_label') or '',
            'pageRange': page_range,
            'route': f'/guide/{subject_id}/{current_id}',
            'contentRef': content_ref,
            'children': child_node_ids,
        }
        child_ids.append(current_id)
    return child_ids


def flatten_ids(root_ids: list[str], nodes_by_id: dict[str, dict]) -> list[str]:
    result = []
    for node_id_value in root_ids:
        result.append(node_id_value)
        result.extend(flatten_ids(nodes_by_id[node_id_value]['children'], nodes_by_id))
    return result


def validate_guide(guide: dict, content_dir: Path) -> None:
    nodes_by_id = guide['nodesById']
    for node_id_value, node in nodes_by_id.items():
        page_range = node['pageRange']
        if page_range[1] < page_range[0]:
            raise ValueError(f'{node_id_value} has invalid pageRange: {page_range}')
        if node['parentId'] and node['parentId'] not in nodes_by_id:
            raise ValueError(f'{node_id_value} has missing parent: {node["parentId"]}')
        for child_id in node['children']:
            if child_id not in nodes_by_id:
                raise ValueError(f'{node_id_value} has missing child: {child_id}')
            child = nodes_by_id[child_id]
            if child['parentId'] != node_id_value:
                raise ValueError(f'{child_id} parent mismatch')
            if child['depth'] != node['depth'] + 1:
                raise ValueError(f'{child_id} depth mismatch')
        content_path = content_dir / guide['key'] / node['contentRef']
        if not content_path.exists():
            raise ValueError(f'{node_id_value} missing content file: {content_path}')


def export() -> dict[str, Any]:
    manifest = load_json(BASE / 'data' / LEVEL / 'toc_manifest.json')
    generated_dir = BASE / 'frontend' / 'src' / 'generated'
    content_dir = generated_dir / 'guideContent'
    if content_dir.exists():
        shutil.rmtree(content_dir)

    guides = {}
    for subject in manifest['subjects']:
        key = subject['key']
        outline = load_json(BASE / 'data' / LEVEL / 'page_clean' / key / 'outline.json')
        nodes_by_id: dict[str, dict] = {}
        root_ids = build_nodes(
            subject_id=subject['id'],
            key=key,
            raw_nodes=outline['outline'],
            manifest_subject=subject,
            content_dir=content_dir,
            nodes_by_id=nodes_by_id,
        )
        guide = {
            'subjectId': subject['id'],
            'key': key,
            'subject': subject['subject'],
            'pdf': subject['pdf'],
            'root': root_ids,
            'nodesById': nodes_by_id,
            'flat': flatten_ids(root_ids, nodes_by_id),
            'stats': outline.get('stats') or {},
        }
        validate_guide(guide, content_dir)
        guides[subject['id']] = guide
    return {
        'level': LEVEL,
        'guides': guides,
    }


def main() -> None:
    data = export()
    out_path = BASE / 'frontend' / 'src' / 'generated' / 'guideOutlines.json'
    write_json(out_path, data)
    for guide in data['guides'].values():
        print(f'{guide["key"]}: {len(guide["flat"])} guide outline nodes')


if __name__ == '__main__':
    main()
