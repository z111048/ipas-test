#!/usr/bin/env python3
"""Export cleaned PDF guide outlines and split content for static frontend imports."""

import json
import re
import shutil
from pathlib import Path
from typing import Any

BASE = Path('/home/james/projects/ipas-test')


def load_json(path: Path) -> dict:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def normalize(value: str) -> str:
    return re.sub(r'\s+', '', value).lower()


def page_count(node: dict) -> int:
    page_range = node.get('page_range') or [node.get('page_number'), node.get('page_number')]
    start_page, end_page = page_range
    if not start_page or not end_page:
        return 0
    return max(0, end_page - start_page + 1)


def filter_duplicate_sibling_nodes(raw_nodes: list[dict]) -> list[dict]:
    """Drop short TOC placeholder nodes when a real sibling section has the same label."""
    groups: dict[tuple[str, str], list[dict]] = {}
    for node in raw_nodes:
        key = (node.get('number') or '', normalize(node.get('title') or ''))
        groups.setdefault(key, []).append(node)

    result = []
    for node in raw_nodes:
        key = (node.get('number') or '', normalize(node.get('title') or ''))
        siblings = groups[key]
        keep = True
        if key[0] and len(siblings) > 1:
            largest = max(page_count(sibling) for sibling in siblings)
            keep = page_count(node) == largest

        if keep:
            cleaned = dict(node)
            cleaned['children'] = filter_duplicate_sibling_nodes(node.get('children', []))
            result.append(cleaned)
    return result


def page_content(level: str, key: str, start_page: int, end_page: int) -> str:
    pages_dir = BASE / 'data' / level / 'page_clean' / key / 'pages'
    chunks = []
    for page_number in range(start_page, end_page + 1):
        page = load_json(pages_dir / f'page_{page_number - 1:03d}.json')
        text = page.get('cleaned_text') or ''
        if text:
            chunks.append(text)
    return '\n\n'.join(chunks).strip()


def markdown_heading_for_line(line: str, root_title: str) -> str | None:
    """Map common PDF outline markers to Markdown headings."""
    text = line.strip()
    if not text:
        return None
    if re.match(r'^第[一二三四五六七八九十]+章\s+', text):
        return f'## {text}'
    if re.match(r'^\d+\.\d+\s+', text):
        return f'## {text}'
    if re.match(r'^\d+\.$', text):
        return f'### {text}'
    if re.match(r'^（\d+）', text):
        return f'#### {text}'
    if re.match(r'^[A-Z]\.\s+', text):
        return f'##### {text}'
    if re.match(r'^[a-z]\.\s+', text):
        return f'###### {text}'
    if text == root_title:
        return f'## {text}'
    return None


def is_markdown_structural_line(text: str) -> bool:
    return bool(re.match(r'^(#{1,6}\s|[-*+]\s|\d+\.\s|[A-Z]\.\s|[a-z]\.\s|[|>`~])', text))


def normalize_ocr_soft_breaks(markdown: str) -> str:
    """Remove OCR line wraps that came from PDF column width, not paragraph intent."""
    result: list[str] = []
    block: list[str] = []

    def flush_block() -> None:
        if not block:
            return
        if any(is_markdown_structural_line(line) for line in block):
            result.extend(block)
        else:
            text = ' '.join(line.strip() for line in block)
            text = re.sub(r'([，、；：])\s+', r'\1', text)
            text = re.sub(r'\s+([，。！？；：、）】])', r'\1', text)
            text = re.sub(r'([（【])\s+', r'\1', text)
            result.append(text)
        block.clear()

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            flush_block()
            if result and result[-1] != '':
                result.append('')
            continue
        block.append(line)

    flush_block()
    return '\n'.join(result).strip()


def format_markdown(title: str, raw_content: str) -> str:
    lines = [line.rstrip() for line in raw_content.splitlines()]
    result = [f'# {title}', '']
    seen_page_headers: set[str] = set()
    previous_blank = True

    for line in lines:
        text = line.strip()
        if not text:
            if not previous_blank:
                result.append('')
                previous_blank = True
            continue

        heading = markdown_heading_for_line(text, title)
        if heading:
            if text in seen_page_headers and re.match(r'^第[一二三四五六七八九十]+章\s+', text):
                continue
            seen_page_headers.add(text)
            if not previous_blank:
                result.append('')
            result.append(heading)
            result.append('')
            previous_blank = True
            continue

        result.append(text)
        previous_blank = False

    return normalize_ocr_soft_breaks('\n'.join(result).strip())



def source_pages(level: str, key: str, start_page: int, end_page: int) -> list[dict]:
    pages_dir = BASE / 'data' / level / 'page_clean' / key / 'pages'
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
            'image': f'/pdf-assets/{level}/{key}/page_{page_index:03d}/page.png',
        })
    return result


def node_id(subject_id: str, node: dict, manifest_subject: dict, index_path: list[int]) -> str:
    number = node.get('number')
    title = normalize(node.get('title') or '')
    if number:
        for chapter in manifest_subject.get('chapters', []):
            if chapter.get('start_page') == node.get('page_label'):
                return chapter['id']
        if not node.get('page_label'):
            for chapter in manifest_subject.get('chapters', []):
                if normalize(chapter.get('title') or '') == title:
                    return chapter['id']
    return f'{subject_id}pdf-c{"-".join(str(part) for part in index_path)}'


def build_nodes(
    level: str,
    subject_id: str,
    key: str,
    content_key: str,
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
            level=level,
            subject_id=subject_id,
            key=key,
            content_key=content_key,
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
        content = page_content(level, key, start_page, end_page)
        write_json(content_dir / content_key / content_ref, {
            'id': current_id,
            'title': raw_node.get('title') or '',
            'content': format_markdown(raw_node.get('title') or '', content),
            'contentFormat': 'markdown',
            'sourcePages': source_pages(level, key, start_page, end_page),
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


def export_level(level: str, content_dir: Path) -> dict[str, Any]:
    manifest = load_json(BASE / 'data' / level / 'toc_manifest.json')
    guides = {}
    for subject in manifest['subjects']:
        key = subject['key']
        content_key = f'{level}-{key}'
        outline = load_json(BASE / 'data' / level / 'page_clean' / key / 'outline.json')
        nodes_by_id: dict[str, dict] = {}
        root_ids = build_nodes(
            level=level,
            subject_id=subject['id'],
            key=key,
            content_key=content_key,
            raw_nodes=filter_duplicate_sibling_nodes(outline['outline']),
            manifest_subject=subject,
            content_dir=content_dir,
            nodes_by_id=nodes_by_id,
        )
        guide = {
            'level': level,
            'subjectId': subject['id'],
            'key': content_key,
            'sourceKey': key,
            'subject': subject['subject'],
            'pdf': subject['pdf'],
            'root': root_ids,
            'nodesById': nodes_by_id,
            'flat': flatten_ids(root_ids, nodes_by_id),
            'stats': outline.get('stats') or {},
        }
        validate_guide(guide, content_dir)
        guides[subject['id']] = guide
    return guides


def export(levels: list[str]) -> dict[str, Any]:
    generated_dir = BASE / 'frontend' / 'src' / 'generated'
    content_dir = generated_dir / 'guideContent'
    if content_dir.exists():
        shutil.rmtree(content_dir)

    guides = {}
    for level in levels:
        guides.update(export_level(level, content_dir))
    return {
        'levels': levels,
        'guides': guides,
    }


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--level', default='初級', help='資料等級資料夾（預設: 初級）')
    parser.add_argument('--all-levels', action='store_true', help='匯出所有已支援等級')
    args = parser.parse_args()

    levels = ['初級', '中級'] if args.all_levels else [args.level]
    data = export(levels)
    out_path = BASE / 'frontend' / 'src' / 'generated' / 'guideOutlines.json'
    write_json(out_path, data)
    for guide in data['guides'].values():
        print(f'{guide["level"]}/{guide["sourceKey"]}: {len(guide["flat"])} guide outline nodes')


if __name__ == '__main__':
    main()
