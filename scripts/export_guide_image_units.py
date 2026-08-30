#!/usr/bin/env python3
"""Split guide tree blocks into small image-generation units."""

import argparse
import json
import re
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
DEFAULT_LEVEL = '初級'
GUIDE_KEYS = ('guide1', 'guide2', 'guide3')
GUIDE_KEYS_BY_LEVEL: dict[str, tuple[str, ...]] = {
    '初級': ('guide1', 'guide2'),
    '中級': ('guide1', 'guide2', 'guide3'),
}
IMAGE_STYLE = (
    'clean flat-vector editorial infographic illustration for the iPAS AI study platform; '
    'off-white background, deep navy and slate foundation, blue accent, restrained amber '
    'and green highlights, soft shadows, 8px-radius visual panels'
)
IMAGE_LAYOUT = (
    'fixed 16:9 widescreen composition with one central concept object, three to five '
    'surrounding icon-based panels, thin connector lines, generous margins, consistent '
    'safe area, no cropping'
)
TEXT_RULES = (
    'the image must contain visible, correctly written Traditional Chinese text: one short '
    'main title plus three to five concise Traditional Chinese labels; each label must be '
    'eight Chinese characters or fewer; use large legible sans-serif typography; place each '
    'label inside a dedicated panel with strong contrast and generous padding'
)
TEXT_BLOCK_TYPES = {'paragraph', 'list_item'}
SKIPPED_BLOCK_TYPES = {'question', 'answer'}


def load_json(path: Path) -> Any:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def normalize_space(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()


def slugify(text: str, fallback: str) -> str:
    cleaned = re.sub(r'[^\w\u4e00-\u9fff]+', '-', text, flags=re.UNICODE)
    cleaned = re.sub(r'-+', '-', cleaned).strip('-').lower()
    return cleaned[:80] or fallback


def text_from_table(block: dict) -> str:
    rows = block.get('rows') or []
    cells = []
    for row in rows:
        cells.extend(normalize_space(str(cell)) for cell in row if normalize_space(str(cell)))
    return '；'.join(cells)


def block_text(block: dict) -> str:
    if block.get('type') in TEXT_BLOCK_TYPES:
        return normalize_space(block.get('text') or '')
    if block.get('type') == 'table':
        return text_from_table(block)
    return ''


def flatten_outline(nodes: list[dict], parent_path: list[str] | None = None) -> dict[str, dict]:
    parent_path = parent_path or []
    out = {}
    for node in nodes:
        title = node.get('title') or node.get('id') or ''
        current_path = [*parent_path, title]
        node_copy = dict(node)
        node_copy['title_path'] = current_path
        out[node['id']] = node_copy
        out.update(flatten_outline(node.get('children') or [], current_path))
    return out


def is_content_node(node_id: str, include_front_matter: bool) -> bool:
    if include_front_matter:
        return True
    return bool(re.fullmatch(r'(?:mid-)?s\d+c\d+', node_id))


def new_section(node: dict, block: dict, order: int, parent: dict | None) -> dict:
    title = block.get('title') or node.get('title') or block.get('id')
    path = [*(parent.get('heading_path') if parent else []), title]
    return {
        'source_node_id': node['id'],
        'source_node_title': node.get('title') or '',
        'source_node_path': node.get('title_path') or [node.get('title') or node['id']],
        'heading_block_id': block.get('id'),
        'heading_depth': block.get('depth'),
        'title': title,
        'heading_path': path,
        'order': order,
        'blocks': [],
        'children': [],
        'parent': parent,
        'start_page_index': block.get('pageIndex'),
    }


def fallback_section(node: dict) -> dict:
    return {
        'source_node_id': node['id'],
        'source_node_title': node.get('title') or '',
        'source_node_path': node.get('title_path') or [node.get('title') or node['id']],
        'heading_block_id': None,
        'heading_depth': node.get('depth'),
        'title': node.get('title') or node['id'],
        'heading_path': [node.get('title') or node['id']],
        'order': 0,
        'blocks': [],
        'children': [],
        'parent': None,
        'start_page_index': node.get('page_index'),
    }


def split_node_sections(node: dict, blocks: list[dict]) -> list[dict]:
    sections = []
    stack: list[dict] = []
    intro = fallback_section(node)
    section_order = 0

    for block in blocks:
        block_type = block.get('type')
        if block_type in SKIPPED_BLOCK_TYPES:
            continue
        if block_type == 'heading':
            depth = block.get('depth') or 0
            while stack and (stack[-1].get('heading_depth') or 0) >= depth:
                stack.pop()
            parent = stack[-1] if stack else None
            section_order += 1
            section = new_section(node, block, section_order, parent)
            if parent:
                parent['children'].append(section)
            sections.append(section)
            stack.append(section)
            continue

        target = stack[-1] if stack else intro
        target['blocks'].append(block)

    if intro['blocks']:
        sections.insert(0, intro)
    return sections


def section_stats(section: dict) -> dict:
    text_parts = [block_text(block) for block in section['blocks']]
    text_parts = [part for part in text_parts if part]
    page_indexes = sorted({
        block.get('pageIndex')
        for block in section['blocks']
        if isinstance(block.get('pageIndex'), int)
    })
    return {
        'text': normalize_space(' '.join(text_parts)),
        'text_chars': sum(len(part) for part in text_parts),
        'block_count': len(section['blocks']),
        'list_item_count': sum(1 for block in section['blocks'] if block.get('type') == 'list_item'),
        'table_count': sum(1 for block in section['blocks'] if block.get('type') == 'table'),
        'page_indexes': page_indexes,
    }


def is_unit_candidate(section: dict, min_chars: int, min_list_items: int) -> bool:
    stats = section_stats(section)
    if not stats['block_count']:
        return False
    if stats['text_chars'] >= min_chars:
        return True
    if stats['list_item_count'] >= min_list_items:
        return True
    return stats['table_count'] > 0


def visual_brief(section: dict, stats: dict, max_chars: int) -> str:
    title_path = ' > '.join(section['heading_path'])
    text = stats['text']
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(' ', 1)[0].rstrip('，。、；:：') + '...'
    return normalize_space(f'{title_path}: {text}')


def image_prompt(brief: str) -> str:
    return (
        'Generate a 1792x1024 wide landscape image (16:9).\n'
        f'Style: {IMAGE_STYLE}.\n'
        f'Layout: {IMAGE_LAYOUT}.\n'
        f'Topic reference, summarize this into the title and labels without copying long text verbatim: {brief}.\n'
        f'Text: {TEXT_RULES}.\n'
        'Rules: high quality, coherent composition, readable Chinese text is required, '
        'no text-free infographic, no long paragraphs, no tiny text, no random letters, '
        'no fake UI, no logos, no watermarks, no UI screenshots'
    )


def unit_from_section(guide: dict, node: dict, section: dict, index: int, max_context_chars: int) -> dict:
    stats = section_stats(section)
    unit_id = f'{guide["key"]}-{section["source_node_id"]}-img-{index:03d}'
    title_slug = slugify(section['title'], f'unit-{index:03d}')
    pages = [page + 1 for page in stats['page_indexes']]
    brief = visual_brief(section, stats, max_context_chars)
    return {
        'id': unit_id,
        'level': guide['level'],
        'subjectId': guide.get('subjectId'),
        'subject': guide.get('subject'),
        'guideKey': guide['key'],
        'sourceNodeId': section['source_node_id'],
        'sourceNodeTitle': section['source_node_title'],
        'sourceNodePath': section['source_node_path'],
        'headingBlockId': section['heading_block_id'],
        'headingDepth': section['heading_depth'],
        'title': section['title'],
        'headingPath': section['heading_path'],
        'pageIndexes': stats['page_indexes'],
        'pageNumbers': pages,
        'textChars': stats['text_chars'],
        'blockCount': stats['block_count'],
        'listItemCount': stats['list_item_count'],
        'tableCount': stats['table_count'],
        'visualBrief': brief,
        'imagePrompt': image_prompt(brief),
        'output': f'{unit_id}-{title_slug}.webp',
    }


def export_guide_units(
    level: str,
    key: str,
    include_front_matter: bool,
    min_chars: int,
    min_list_items: int,
    max_context_chars: int,
) -> dict:
    root = BASE / 'data' / level / 'guide_tree' / key
    tree = load_json(root / 'tree.json')
    blocks_by_node = load_json(root / 'blocks.json')
    nodes = flatten_outline(tree.get('outline') or [])

    units = []
    node_summaries = []
    for node_id in tree.get('flat') or []:
        if not is_content_node(node_id, include_front_matter):
            continue
        node = nodes[node_id]
        sections = split_node_sections(node, blocks_by_node.get(node_id) or [])
        candidates = [
            section
            for section in sections
            if is_unit_candidate(section, min_chars, min_list_items)
        ]
        for index, section in enumerate(candidates, start=1):
            units.append(unit_from_section(tree, node, section, index, max_context_chars))
        node_summaries.append({
            'nodeId': node_id,
            'title': node.get('title'),
            'sections': len(sections),
            'units': len(candidates),
        })

    return {
        'level': level,
        'guideKey': key,
        'subjectId': tree.get('subjectId'),
        'subject': tree.get('subject'),
        'source': {
            'tree': str((root / 'tree.json').relative_to(BASE)),
            'blocks': str((root / 'blocks.json').relative_to(BASE)),
        },
        'rules': {
            'includeFrontMatter': include_front_matter,
            'minChars': min_chars,
            'minListItems': min_list_items,
            'maxContextChars': max_context_chars,
            'unitDefinition': (
                'exclusive content under the lowest available heading; parent sections '
                'become units only for their own non-child intro content'
            ),
        },
        'nodeSummaries': node_summaries,
        'totalUnits': len(units),
        'units': units,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--level', default=DEFAULT_LEVEL, help='資料等級資料夾（預設: 初級）')
    parser.add_argument('--key', choices=GUIDE_KEYS, help='只匯出指定 guide key')
    parser.add_argument('--all', action='store_true', help='匯出該等級所有 guide keys')
    parser.add_argument('--include-front-matter', action='store_true', help='包含 s*pdf-c* 等前置章節')
    parser.add_argument('--min-chars', type=int, default=80, help='產圖單元最少文字字元數（預設: 80）')
    parser.add_argument('--min-list-items', type=int, default=3, help='文字不足時，至少幾個 list item 仍保留（預設: 3）')
    parser.add_argument('--max-context-chars', type=int, default=700, help='visualBrief 最長字元數（預設: 700）')
    parser.add_argument('--out-dir', default=None, help='輸出資料夾（預設: data/{level}/image_units）')
    args = parser.parse_args()

    if args.min_chars < 1:
        parser.error('--min-chars must be >= 1')
    if args.min_list_items < 1:
        parser.error('--min-list-items must be >= 1')
    if args.max_context_chars < 100:
        parser.error('--max-context-chars must be >= 100')

    level_keys = GUIDE_KEYS_BY_LEVEL.get(args.level, GUIDE_KEYS)
    keys = [args.key] if args.key else list(level_keys)
    out_dir = BASE / (args.out_dir or f'data/{args.level}/image_units')
    manifests = []
    all_units = []
    for key in keys:
        manifest = export_guide_units(
            args.level,
            key,
            args.include_front_matter,
            args.min_chars,
            args.min_list_items,
            args.max_context_chars,
        )
        write_json(out_dir / f'{key}_image_units.json', manifest)
        manifests.append({
            'guideKey': key,
            'subjectId': manifest['subjectId'],
            'subject': manifest['subject'],
            'totalUnits': manifest['totalUnits'],
            'path': str((out_dir / f'{key}_image_units.json').relative_to(BASE)),
        })
        all_units.extend(manifest['units'])

    combined = {
        'level': args.level,
        'guides': manifests,
        'totalUnits': len(all_units),
        'units': all_units,
    }
    write_json(out_dir / 'all_image_units.json', combined)
    print(f'Exported {len(all_units)} image units to {out_dir.relative_to(BASE)}')
    for manifest in manifests:
        print(f'- {manifest["guideKey"]}: {manifest["totalUnits"]} units')


if __name__ == '__main__':
    main()
