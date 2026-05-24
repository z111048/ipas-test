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
    items = []
    for page_number in range(start_page, end_page + 1):
        page_index = page_number - 1
        page = load_json(pages_dir / f'page_{page_index:03d}.json')
        items.extend(positioned_page_items(level, key, page_index, page))
    return render_positioned_items(merge_split_tables(items)).strip()


def page_blocks(level: str, key: str, start_page: int, end_page: int) -> list[dict]:
    pages_dir = BASE / 'data' / level / 'page_clean' / key / 'pages'
    items = []
    for page_number in range(start_page, end_page + 1):
        page_index = page_number - 1
        page = load_json(pages_dir / f'page_{page_index:03d}.json')
        items.extend(positioned_page_items(level, key, page_index, page))
    return build_content_blocks(merge_split_tables(items))


def markdown_heading_for_line(line: str, root_title: str) -> str | None:
    """Map common PDF outline markers to Markdown headings."""
    text = line.strip()
    if not text:
        return None
    if re.match(r'^第[一二三四五六七八九十]+章\s+', text):
        return f'## {text}'
    if re.match(r'^\d+\.\d+\s+', text):
        return f'## {text}'
    if is_numbered_section_heading(text):
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


def is_numbered_section_heading(text: str) -> bool:
    match = re.match(r'^\d+\.\s+(?P<title>.+)', text.strip())
    if not match:
        return False
    title = match.group('title')
    if title.strip() in {'AI', 'NLP'}:
        return False
    if len(title) > 30:
        return False
    if re.search(r'(Ans|解析|下列|以下|何者|哪一|哪個|哪種|何種|是否|最適合|屬於|正確|錯誤|主要|目的|應$|是什|？|\?)', title):
        return False
    if re.match(r'^(在|若|當|為了|以下|下列)', title):
        return False
    return True


def is_markdown_structural_line(text: str) -> bool:
    return bool(re.match(r'^(#{1,6}\s|[|>`~])', text))


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
            text = re.sub(r'(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])', '', text)
            result.append(text)
        block.clear()

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            flush_block()
            if result and result[-1] != '':
                result.append('')
            continue
        if is_markdown_structural_line(line.strip()):
            flush_block()
            result.append(line)
            continue
        block.append(line)

    flush_block()
    return '\n'.join(result).strip()


def clean_table_cell(value: Any) -> str:
    if value is None:
        return ''
    text = str(value).replace('\r\n', '\n').replace('\r', '\n')
    lines = [re.sub(r'\s+', ' ', line).strip() for line in text.splitlines()]
    return '\n'.join(line for line in lines if line).strip()


def clean_table_rows(rows: list[list[Any]]) -> list[list[str]]:
    cleaned_rows = []
    has_later_content = [
        any(clean_table_cell(cell) for cell in row)
        for row in rows
    ]
    for index, row in enumerate(rows):
        cleaned = [clean_table_cell(cell) for cell in row]
        if any(cleaned) or (index == 0 and any(has_later_content[1:])):
            cleaned_rows.append(cleaned)
    return cleaned_rows


def bbox_center(bbox: list[float]) -> tuple[float, float]:
    return ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)


def bbox_contains_point(bbox: list[float], x: float, y: float, pad: float = 0) -> bool:
    return bbox[0] - pad <= x <= bbox[2] + pad and bbox[1] - pad <= y <= bbox[3] + pad


def block_overlaps_table(block: dict, table_bbox: list[float]) -> bool:
    x, y = bbox_center(block.get('bbox') or [0, 0, 0, 0])
    return bbox_contains_point(table_bbox, x, y, pad=8)


def recover_header_row(table: dict, blocks: list[dict]) -> list[str] | None:
    rows = clean_table_rows(table.get('rows') or [])
    if not rows:
        return None
    column_count = max(len(row) for row in rows)
    first_row = rows[0] + [''] * (column_count - len(rows[0]))
    if sum(1 for cell in first_row if cell.strip()) > max(1, column_count // 2):
        return None

    bbox = table.get('bbox') or []
    if len(bbox) != 4:
        return None
    x0, y0, x1, _ = bbox
    width = max(1, x1 - x0)
    header_cells = [''] * column_count
    header_blocks = []
    for block in blocks:
        block_bbox = block.get('bbox') or []
        if len(block_bbox) != 4:
            continue
        cx, cy = bbox_center(block_bbox)
        if y0 - 2 <= cy <= y0 + 42 and x0 - 18 <= cx <= x1 + 18:
            header_blocks.append(block)

    for block in sorted(header_blocks, key=lambda item: (item['bbox'][0], item['bbox'][1])):
        cx, _ = bbox_center(block['bbox'])
        column = int((cx - x0) / width * column_count)
        column = min(max(column, 0), column_count - 1)
        text = clean_table_cell(block.get('text') or '')
        if not text:
            continue
        header_cells[column] = f'{header_cells[column]}\n{text}'.strip() if header_cells[column] else text

    if (
        column_count == 4
        and not header_cells[0]
        and header_cells[1:] == ['角色定位', '範疇', '常見任務']
    ):
        header_cells[0] = '概念'
    return header_cells if any(header_cells) else None


def markdown_escape_cell(value: str) -> str:
    text = value.replace('|', '\\|').replace('\n', ' ')
    return re.sub(r'(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])', '', text)


def text_looks_complete(text: str) -> bool:
    text = text.strip()
    return text.endswith(('。', '？', '！', '；', ':', '：', ')', '）', '」', '』'))


def text_looks_sentence_complete(text: str) -> bool:
    text = text.strip()
    return text.endswith(('。', '？', '！', '；', ':', '：', '」', '』'))


def text_looks_hard_complete(text: str) -> bool:
    text = text.strip()
    return text.endswith(('。', '？', '！', '；', ':', '：'))


def text_looks_structural(text: str) -> bool:
    text = text.strip()
    return bool(
        re.match(r'^(第[一二三四五六七八九十]+章\s+|\d+\.\d+\s+|\d+\.$|（\d+）|[A-Z]\.\s+|[a-z]\.\s+)', text)
        or is_numbered_section_heading(text)
    )


def is_number_marker(text: str) -> bool:
    return bool(re.match(r'^\d+\.$', text.strip()))


def is_short_heading_title(text: str) -> bool:
    text = text.strip()
    if not text or len(text) > 28:
        return False
    if re.search(r'[，。！？；：、,.!?;:]', text):
        return False
    if re.search(r'(Ans|解析|下列|以下|何者|哪一|哪個|哪種|何種|是否|最適合|屬於|正確|錯誤|主要|目的|應$|是什)', text):
        return False
    if re.match(r'^(在|若|當|為了|以下|下列)', text):
        return False
    return bool(re.search(r'[\u4e00-\u9fffA-Za-z]', text))


def items_form_numbered_heading(previous: dict, current: dict) -> bool:
    if previous.get('type') != 'text' or current.get('type') != 'text':
        return False
    if previous.get('page_index') != current.get('page_index'):
        return False
    previous_text = previous.get('text') or ''
    current_text = current.get('text') or ''
    if not is_number_marker(previous_text) or not is_short_heading_title(current_text):
        return False
    previous_bbox = previous.get('bbox') or []
    current_bbox = current.get('bbox') or []
    if len(previous_bbox) != 4 or len(current_bbox) != 4:
        return False
    return abs(current_bbox[1] - previous_bbox[1]) <= 6 and 0 <= current_bbox[0] - previous_bbox[2] <= 18


def items_form_same_line_heading(previous: dict, current: dict) -> bool:
    if previous.get('type') != 'text' or current.get('type') != 'text':
        return False
    if previous.get('page_index') != current.get('page_index'):
        return False
    previous_text = previous.get('text') or ''
    current_text = current.get('text') or ''
    if not re.match(r'^\d+\.\s+.+', previous_text.strip()):
        return False
    if text_looks_complete(previous_text) or not is_short_heading_title(current_text):
        return False
    combined = f'{previous_text.strip()}{current_text.strip()}'
    if len(combined) > 46:
        return False
    previous_bbox = previous.get('bbox') or []
    current_bbox = current.get('bbox') or []
    if len(previous_bbox) != 4 or len(current_bbox) != 4:
        return False
    max_gap = 130 if re.search(r'\b(?:AI|NLP)$', previous_text.strip()) else 22
    return abs(current_bbox[1] - previous_bbox[1]) <= 6 and 0 <= current_bbox[0] - previous_bbox[2] <= max_gap


def join_heading_fragments(previous_text: str, current_text: str) -> str:
    previous_text = previous_text.rstrip()
    current_text = current_text.lstrip()
    if re.search(r'[A-Za-z0-9]$', previous_text) and re.match(r'[A-Za-z0-9]', current_text):
        return f'{previous_text} {current_text}'
    return f'{previous_text}{current_text}'


def text_items_should_join(previous: dict, current: dict) -> bool:
    if previous.get('type') != 'text' or current.get('type') != 'text':
        return False
    if previous.get('page_index') != current.get('page_index'):
        return False
    previous_bbox = previous.get('bbox') or []
    current_bbox = current.get('bbox') or []
    if len(previous_bbox) != 4 or len(current_bbox) != 4:
        return False
    previous_text = previous.get('text') or ''
    current_text = current.get('text') or ''
    if not previous_text or not current_text:
        return False
    vertical_gap = current_bbox[1] - previous_bbox[3]
    same_left_edge = abs(current_bbox[0] - previous_bbox[0]) <= 38
    continuation_indent = current_bbox[0] >= previous_bbox[0] and current_bbox[0] - previous_bbox[0] <= 45
    if vertical_gap > 20:
        return False
    if text_looks_structural(current_text) or text_looks_structural(previous_text):
        return False
    if text_looks_complete(previous_text):
        return False
    return same_left_edge or continuation_indent or not text_looks_complete(previous_text)


def merge_text_items(items: list[dict]) -> list[dict]:
    merged: list[dict] = []
    for item in items:
        if merged and items_form_numbered_heading(merged[-1], item):
            merged[-1]['text'] = f'{merged[-1]["text"]} {item["text"]}'
            previous_bbox = merged[-1].get('bbox') or item.get('bbox')
            current_bbox = item.get('bbox') or previous_bbox
            if len(previous_bbox) == 4 and len(current_bbox) == 4:
                merged[-1]['bbox'] = [
                    min(previous_bbox[0], current_bbox[0]),
                    min(previous_bbox[1], current_bbox[1]),
                    max(previous_bbox[2], current_bbox[2]),
                    max(previous_bbox[3], current_bbox[3]),
                ]
            continue
        if merged and items_form_same_line_heading(merged[-1], item):
            merged[-1]['text'] = join_heading_fragments(merged[-1]['text'], item['text'])
            previous_bbox = merged[-1].get('bbox') or item.get('bbox')
            current_bbox = item.get('bbox') or previous_bbox
            if len(previous_bbox) == 4 and len(current_bbox) == 4:
                merged[-1]['bbox'] = [
                    min(previous_bbox[0], current_bbox[0]),
                    min(previous_bbox[1], current_bbox[1]),
                    max(previous_bbox[2], current_bbox[2]),
                    max(previous_bbox[3], current_bbox[3]),
                ]
            continue
        if merged and text_items_should_join(merged[-1], item):
            merged[-1]['text'] = f'{merged[-1]["text"]}\n{item["text"]}'
            previous_bbox = merged[-1].get('bbox') or item.get('bbox')
            current_bbox = item.get('bbox') or previous_bbox
            if len(previous_bbox) == 4 and len(current_bbox) == 4:
                merged[-1]['bbox'] = [
                    min(previous_bbox[0], current_bbox[0]),
                    min(previous_bbox[1], current_bbox[1]),
                    max(previous_bbox[2], current_bbox[2]),
                    max(previous_bbox[3], current_bbox[3]),
                ]
            continue
        merged.append(dict(item))
    return merged


def table_rows_for_markdown(table: dict, blocks: list[dict]) -> list[list[str]]:
    rows = clean_table_rows(table.get('rows') or [])
    if not rows:
        return []
    column_count = max(len(row) for row in rows)
    normalized_rows = [row + [''] * (column_count - len(row)) for row in rows]
    recovered_header = recover_header_row(table, blocks)
    if recovered_header:
        normalized_rows[0] = recovered_header
    return normalized_rows


def table_rows_to_markdown(rows: list[list[str]]) -> str:
    if not rows:
        return ''
    column_count = max(len(row) for row in rows)
    normalized_rows = [row + [''] * (column_count - len(row)) for row in rows]
    header = normalized_rows[0]
    body = normalized_rows[1:]
    lines = [
        '| ' + ' | '.join(markdown_escape_cell(cell) for cell in header) + ' |',
        '| ' + ' | '.join('---' for _ in range(column_count)) + ' |',
    ]
    for row in body:
        lines.append('| ' + ' | '.join(markdown_escape_cell(cell) for cell in row) + ' |')
    return '\n'.join(lines)


def block_text(value: str) -> str:
    text = ' '.join(line.strip() for line in value.splitlines() if line.strip())
    text = re.sub(r'([，、；：])\s+', r'\1', text)
    text = re.sub(r'\s+([，。！？；：、）】])', r'\1', text)
    text = re.sub(r'([（【])\s+', r'\1', text)
    return re.sub(r'(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])', '', text).strip()


def numbered_question_like(text: str) -> bool:
    stripped = text.strip()
    if re.match(r'^\d+\.\s*Ans', stripped):
        return False
    if is_numbered_section_heading(stripped):
        return False
    return bool(
        re.match(r'^\d+\.\s+', stripped)
        and (
            re.search(r'(？|\?|下列|以下|何者|哪一|哪個|哪種|何種|是否|最適合|屬於|正確|錯誤|主要|目的|稱為|可以採用|應)', stripped)
            or len(stripped) > 34
        )
    )


def lettered_question_like(text: str) -> bool:
    stripped = text.strip()
    return bool(
        re.match(r'^[A-Za-z]\.\s+', stripped)
        and re.search(r'(？|\?|下列|以下|何者|哪一|哪些|哪個|哪種|何種|是否|最適合|屬於|正確|錯誤|主要|目的|應)', stripped)
    )


def classify_text_block(text: str) -> tuple[str, int, str | None]:
    stripped = text.strip()
    if re.match(r'^第[一二三四五六七八九十]+章\s+', stripped):
        return 'heading', 1, None
    if re.match(r'^\d+\.\d+\s+', stripped):
        return 'heading', 2, None
    if is_numbered_section_heading(stripped):
        return 'heading', 3, None
    if re.match(r'^（\d+）', stripped):
        return 'heading', 4, None
    if lettered_question_like(stripped):
        return 'question', 5, None
    if re.match(r'^[A-Z]\.\s+', stripped):
        return 'heading', 5, None
    if re.match(r'^[a-z]\.\s+', stripped):
        return 'heading', 6, None
    if stripped.startswith('• '):
        return 'list_item', 7, '•'
    if stripped.startswith('○ '):
        return 'list_item', 8, '○'
    if re.match(r'^\d+\.\s*Ans', stripped):
        return 'answer', 3, None
    if numbered_question_like(stripped):
        return 'question', 3, None
    return 'paragraph', 0, None


def append_block(blocks: list[dict], block: dict) -> None:
    if not block.get('text') and not block.get('title') and block.get('type') != 'table':
        return
    block['id'] = f'block-{len(blocks) + 1}'
    blocks.append(block)


def can_extend_previous_heading(previous: dict, text: str, item: dict) -> bool:
    if previous.get('type') != 'heading':
        return False
    if len(previous.get('title') or '') < 28:
        return False
    if text_looks_sentence_complete(previous.get('title') or ''):
        return False
    if classify_text_block(text)[0] != 'paragraph':
        return False
    if len(text) > 30:
        return False
    prev_bbox = previous.get('bbox') or []
    current_bbox = item.get('bbox') or []
    if len(prev_bbox) == 4 and len(current_bbox) == 4:
        vertical_gap = current_bbox[1] - prev_bbox[3]
        if vertical_gap > 24:
            return False
    return True


def can_extend_previous_text_block(previous: dict, text: str, item: dict) -> bool:
    if previous.get('type') not in {'paragraph', 'list_item'}:
        return False
    if classify_text_block(text)[0] != 'paragraph':
        return False
    if text_looks_hard_complete(previous.get('text') or ''):
        return False
    if len(text) > 60:
        return False
    prev_bbox = previous.get('bbox') or []
    current_bbox = item.get('bbox') or []
    if len(prev_bbox) == 4 and len(current_bbox) == 4:
        vertical_gap = current_bbox[1] - prev_bbox[3]
        if vertical_gap > 24:
            return False
    return True


def merge_block_bbox(previous: list | None, current: list | None) -> list | None:
    if not previous or len(previous) != 4:
        return current if current and len(current) == 4 else previous
    if not current or len(current) != 4:
        return previous
    return [
        min(previous[0], current[0]),
        min(previous[1], current[1]),
        max(previous[2], current[2]),
        max(previous[3], current[3]),
    ]


def build_content_blocks(items: list[dict]) -> list[dict]:
    blocks: list[dict] = []
    current_context_depth = 2
    for item in merge_text_items(items):
        item_type = item.get('type')
        if item_type == 'table':
            rows = item.get('rows') or []
            if rows:
                append_block(blocks, {
                    'type': 'table',
                    'depth': min(current_context_depth + 1, 9),
                    'rows': rows,
                    'pageIndex': item.get('page_index'),
                    'bbox': item.get('bbox'),
                })
            continue

        text = block_text(item.get('text') or '')
        if not text:
            continue

        block_type, depth, marker = classify_text_block(text)
        if blocks and can_extend_previous_heading(blocks[-1], text, item):
            blocks[-1]['title'] = block_text(f'{blocks[-1]["title"]} {text}')
            blocks[-1]['bbox'] = merge_block_bbox(blocks[-1].get('bbox'), item.get('bbox'))
            continue
        if blocks and can_extend_previous_text_block(blocks[-1], text, item):
            blocks[-1]['text'] = block_text(f'{blocks[-1]["text"]} {text}')
            blocks[-1]['bbox'] = merge_block_bbox(blocks[-1].get('bbox'), item.get('bbox'))
            continue

        if block_type == 'heading':
            current_context_depth = depth
            append_block(blocks, {
                'type': 'heading',
                'depth': depth,
                'title': text,
                'anchor': slugify_heading(text, len(blocks) + 1),
                'pageIndex': item.get('page_index'),
                'bbox': item.get('bbox'),
            })
        elif block_type == 'list_item':
            append_block(blocks, {
                'type': 'list_item',
                'depth': depth,
                'marker': marker,
                'text': block_text(text.removeprefix(marker or '').strip()),
                'pageIndex': item.get('page_index'),
                'bbox': item.get('bbox'),
            })
        elif block_type == 'question':
            append_block(blocks, {
                'type': 'question',
                'depth': max(current_context_depth + 1, depth),
                'text': text,
                'pageIndex': item.get('page_index'),
                'bbox': item.get('bbox'),
            })
        elif block_type == 'answer':
            append_block(blocks, {
                'type': 'answer',
                'depth': max(current_context_depth + 1, depth),
                'text': text,
                'pageIndex': item.get('page_index'),
                'bbox': item.get('bbox'),
            })
        else:
            append_block(blocks, {
                'type': 'paragraph',
                'depth': min(current_context_depth + 1, 9),
                'text': text,
                'pageIndex': item.get('page_index'),
                'bbox': item.get('bbox'),
            })
    return blocks


def table_to_markdown(table: dict, blocks: list[dict]) -> str:
    rows = table_rows_for_markdown(table, blocks)
    return table_rows_to_markdown(rows)


def is_running_header_or_footer(block: dict, page_height: float) -> bool:
    bbox = block.get('bbox') or []
    if len(bbox) != 4:
        return False
    text = clean_table_cell(block.get('text') or '')
    if page_height and bbox[1] >= page_height - 70:
        return True
    if bbox[1] <= 95 and re.match(r'^第[一二三四五六七八九十]+章\s+', text):
        return True
    return False


def positioned_page_items(level: str, key: str, page_index: int, cleaned_page: dict) -> list[dict]:
    extract_path = BASE / 'data' / level / 'page_extract' / key / 'pages' / f'page_{page_index:03d}.json'
    if not extract_path.exists():
        text = cleaned_page.get('cleaned_text') or ''
        return [{'type': 'text', 'page_index': page_index, 'y': 0, 'x': 0, 'text': text}] if text else []

    extracted = load_json(extract_path)
    tables = extracted.get('tables') or []

    page_height = float(extracted.get('height') or 0)
    table_bboxes = [table.get('bbox') or [] for table in tables if len(table.get('bbox') or []) == 4]
    items: list[dict] = []
    for block in extracted.get('blocks') or []:
        bbox = block.get('bbox') or []
        if len(bbox) != 4:
            continue
        if is_running_header_or_footer(block, page_height):
            continue
        text = clean_table_cell(block.get('text') or '')
        if not text:
            continue
        if any(block_overlaps_table(block, table_bbox) for table_bbox in table_bboxes):
            continue
        items.append({
            'type': 'text',
            'page_index': page_index,
            'page_height': page_height,
            'bbox': bbox,
            'y': bbox[1],
            'x': bbox[0],
            'text': text,
        })

    for table in tables:
        bbox = table.get('bbox') or []
        if len(bbox) != 4:
            continue
        rows = table_rows_for_markdown(table, extracted.get('blocks') or [])
        if rows:
            items.append({
                'type': 'table',
                'page_index': page_index,
                'page_height': page_height,
                'bbox': bbox,
                'y': bbox[1],
                'x': bbox[0],
                'rows': rows,
            })

    return sorted(items, key=lambda item: (item['page_index'], item['y'], item['x']))


def table_column_count(item: dict) -> int:
    return max((len(row) for row in item.get('rows') or []), default=0)


def is_split_table_continuation(previous: dict, current: dict) -> bool:
    if previous.get('type') != 'table' or current.get('type') != 'table':
        return False
    if current.get('page_index') != previous.get('page_index') + 1:
        return False
    if table_column_count(previous) != table_column_count(current):
        return False
    previous_bbox = previous.get('bbox') or []
    current_bbox = current.get('bbox') or []
    if len(previous_bbox) != 4 or len(current_bbox) != 4:
        return False
    previous_height = float(previous.get('page_height') or 0)
    current_height = float(current.get('page_height') or 0)
    if not previous_height or not current_height:
        return False
    return previous_bbox[3] >= previous_height * 0.72 and current_bbox[1] <= current_height * 0.32


def merge_split_tables(items: list[dict]) -> list[dict]:
    merged: list[dict] = []
    for item in items:
        if merged and is_split_table_continuation(merged[-1], item):
            rows = item.get('rows') or []
            if rows:
                merged[-1]['rows'].extend(rows[1:] if len(rows) > 1 else rows)
                merged[-1]['bbox'] = item.get('bbox') or merged[-1].get('bbox')
                merged[-1]['page_index'] = item.get('page_index')
                merged[-1]['page_height'] = item.get('page_height')
            continue
        merged.append(item)
    return merged


def render_positioned_items(items: list[dict]) -> str:
    chunks = []
    for item in merge_text_items(items):
        if item.get('type') == 'table':
            markdown = table_rows_to_markdown(item.get('rows') or [])
            if markdown:
                chunks.append(markdown)
        else:
            text = item.get('text') or ''
            if text:
                chunks.append(text)
    return '\n\n'.join(chunks)


def positioned_page_content(level: str, key: str, page_index: int, cleaned_page: dict) -> str:
    return render_positioned_items(positioned_page_items(level, key, page_index, cleaned_page))


def source_page_tables(level: str, key: str, page_index: int) -> list[dict]:
    page_path = BASE / 'data' / level / 'page_extract' / key / 'pages' / f'page_{page_index:03d}.json'
    if not page_path.exists():
        return []

    page = load_json(page_path)
    tables = []
    for table in page.get('tables') or []:
        rows = clean_table_rows(table.get('rows') or [])
        if not rows:
            continue

        source_path = table.get('path') or ''
        asset_name = Path(source_path).name if source_path else f'{table.get("id", "table")}.png'
        tables.append({
            'id': table.get('id') or f'table_{len(tables) + 1:02d}',
            'bbox': table.get('bbox') or [],
            'image': f'/pdf-assets/{level}/{key}/page_{page_index:03d}/{asset_name}',
            'rows': rows,
        })
    return tables


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

    normalized = normalize_ocr_soft_breaks('\n'.join(result).strip())
    return re.sub(r'(?<=[\u4e00-\u9fff])[ \t]+(?=[\u4e00-\u9fff])', '', normalized)


def slugify_heading(text: str, index: int) -> str:
    slug = re.sub(r'\s+', '-', normalize(text).lower())
    slug = re.sub(r'[^0-9a-z\u4e00-\u9fff\-]+', '', slug)
    slug = slug.strip('-')
    return slug or f'section-{index}'


def markdown_headings(markdown: str) -> list[dict]:
    headings = []
    for line in markdown.splitlines():
        match = re.match(r'^(#{2,6})\s+(.+?)\s*$', line.strip())
        if not match:
            continue
        title = match.group(2).strip()
        if re.fullmatch(r'\d+\.', title):
            continue
        headings.append({
            'id': slugify_heading(title, len(headings) + 1),
            'level': len(match.group(1)),
            'title': title,
        })
    return headings


def source_pages(level: str, key: str, start_page: int, end_page: int) -> list[dict]:
    pages_dir = BASE / 'data' / level / 'page_clean' / key / 'pages'
    result = []
    for page_number in range(start_page, end_page + 1):
        page_index = page_number - 1
        page_path = pages_dir / f'page_{page_index:03d}.json'
        if not page_path.exists():
            continue
        page = load_json(page_path)
        item = {
            'index': page_index,
            'page': page_number,
            'label': page.get('page_label') or '',
            'image': f'/pdf-assets/{level}/{key}/page_{page_index:03d}/page.png',
        }
        tables = source_page_tables(level, key, page_index)
        if tables:
            item['tables'] = tables
        result.append(item)
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
        markdown_content = format_markdown(raw_node.get('title') or '', content)
        blocks = page_blocks(level, key, start_page, end_page)
        write_json(content_dir / content_key / content_ref, {
            'id': current_id,
            'title': raw_node.get('title') or '',
            'content': markdown_content,
            'contentFormat': 'markdown',
            'headings': markdown_headings(markdown_content),
            'blocks': blocks,
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
