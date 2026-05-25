#!/usr/bin/env python3
"""Export cleaned PDF guide outlines and split content for static frontend imports."""

import json
import re
import shutil
from html import escape
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
    return bool(re.match(r'^(#{1,6}\s|[|>`~]|</?(?:table|thead|tbody|tr|th|td)\b)', text))


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
        re.match(r'^(第[一二三四五六七八九十]+章\s+|\d+\.\d+\s+|\d+\.$|（\d+）|[A-Z]\.\s+|[a-z]\.\s+|[•◦○]\s+|[\uf097\uf09f\uf077\uf0a1]\s*)', text)
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


def table_rows_to_html(rows: list[list[str]]) -> str:
    if not rows:
        return ''
    column_count = max(len(row) for row in rows)
    normalized_rows = [row + [''] * (column_count - len(row)) for row in rows]
    header = normalized_rows[0]
    body = normalized_rows[1:]

    def cell_text(value: str) -> str:
        escaped = escape(value, quote=False)
        return escaped.replace('\n', '<br />')

    lines = ['<table>', '<thead>', '<tr>']
    for cell in header:
        lines.append(f'<th>{cell_text(cell)}</th>')
    lines.extend(['</tr>', '</thead>', '<tbody>'])
    for row in body:
        lines.append('<tr>')
        for cell in row:
            lines.append(f'<td>{cell_text(cell)}</td>')
        lines.append('</tr>')
    lines.extend(['</tbody>', '</table>'])
    return '\n'.join(lines)


def block_text(value: str) -> str:
    value = (
        value
        .replace('\uf097', '• ')
        .replace('\uf09f', '• ')
        .replace('\uf077', '◦ ')
        .replace('\uf0a1', '○ ')
    )
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
        and re.search(r'(？|\?|下列|以下|何者|哪一|哪些|哪個|哪種|何種|是否|最適合)', stripped)
    )


def lettered_question_like(text: str) -> bool:
    stripped = text.strip()
    # In the guide PDFs, "A." / "B." is primarily a content hierarchy marker.
    # Chapter exercises use numbered questions plus full-width options such as
    # "（A）", so treating lettered content as questions corrupts headings like
    # "B. 常見合規做法與因應策略" because of the substring "因應".
    return False


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
    if stripped.startswith(' ') or stripped.startswith(' '):
        return 'list_item', 5, stripped[:1]
    if stripped.startswith(' '):
        return 'list_item', 6, stripped[:1]
    if stripped.startswith(' '):
        return 'list_item', 7, stripped[:1]
    if stripped.startswith('• '):
        return 'list_item', 5, '•'
    if stripped.startswith('◦ '):
        return 'list_item', 6, '◦'
    if stripped.startswith('○ '):
        return 'list_item', 7, '○'
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


def reset_block_ids(blocks: list[dict]) -> list[dict]:
    for index, block in enumerate(blocks, start=1):
        block['id'] = f'block-{index}'
    return blocks


def heading_anchor(title: str, index: int) -> str:
    return slugify_heading(title, index)


def retitle_heading(block: dict, title: str, index: int) -> None:
    block['title'] = block_text(title)
    block['anchor'] = heading_anchor(block['title'], index)


def split_heading_title(title: str, depth: int) -> tuple[str, str | None]:
    """Split verbose PDF headings such as "A. 原理：..." into heading + paragraph."""
    stripped = title.strip()
    if depth <= 3:
        return stripped, None

    colon_match = re.match(r'^((?:（\d+）|[A-Z]\.|[a-z]\.)\s*[^：:]{2,70})[：:]\s*(.+)$', stripped)
    if colon_match:
        heading = colon_match.group(1).strip()
        detail = colon_match.group(2).strip()
        if detail:
            return heading, detail
        return heading, None

    paren_match = re.match(r'^(（\d+）\s*.+?(?:（[^）]+）|\([^)]*\)))\s*(.+)$', stripped)
    if paren_match and len(stripped) > 34:
        heading = paren_match.group(1).strip()
        detail = paren_match.group(2).strip()
        if detail and not re.fullmatch(r'[：:，,。；;]*', detail):
            return heading, detail

    return stripped, None


CONTENT_SECTION_TITLES: dict[str, dict[str, list[str]]] = {
    'mid-s2c1': {
        '1.': ['1. 前言與章節導覽'],
        '2.': ['2. 集中趨勢與離散程度'],
    },
    'mid-s2c2': {
        '1.': ['1. 前言與章節導覽'],
        '2.': ['2. 機率分佈基本概念'],
        '3.': ['3. 離散型機率分佈'],
        '4.': ['4. 連續型機率分佈'],
        '5.': ['5. 分佈擬合與資料建模'],
    },
    'mid-s2c6': {
        '1.': ['1. 前言與章節導覽'],
        '2.': ['2. 資料轉換與前處理'],
    },
    'mid-s2c7': {
        '1.': ['1. 前言與章節導覽'],
        '3.': ['3. 大數據下統計推論的限制與風險'],
    },
    'mid-s2c11': {
        '1.': ['1. 前言與章節導覽'],
        '2.': ['2. 鑑別式AI 的核心任務與應用情境'],
    },
    'mid-s2c12': {
        '1.': ['1. 前言與章節導覽'],
        '2.': ['2. 生成式AI 資料需求與選擇'],
    },
    's2c1': {
        '3.': ['3. AI No Code / Low Code'],
        '4.': ['4. AI No Code / Low Code 產業應用'],
        '5.': ['5. No Code / Low Code 平台選擇與評估'],
        '7.': ['7. No Code / Low Code 導入效益'],
        '8.': ['8. AI No Code / Low Code 發展趨勢'],
    },
    's2c2': {
        '1.': ['1. 生成式AI 的基本概念'],
        '2.': ['2. 生成式AI 的市場價值與影響力'],
        '3.': ['3. 生成式AI 工具的技術進化'],
        '4.': ['4. 生成式AI 應用領域'],
    },
    's2c3': {
        '1.': ['1. 生成式AI 導入評估標準'],
    },
    's2pdf-c3': {
        '3.': ['3. AI No Code / Low Code', '3. 生成式AI 工具的技術進化'],
        '4.': ['4. AI No Code / Low Code 產業應用', '4. 生成式AI 應用領域'],
        '5.': ['5. 生成式AI 應用案例'],
        '7.': ['7. No Code / Low Code 導入效益'],
        '8.': ['8. AI No Code / Low Code 發展趨勢'],
    },
}


TITLE_REPLACEMENTS = {
    '3.1 第三章 AI 相關技術應用': '第三章 AI 相關技術應用',
    '3.1 第三章人工智慧基礎概論': '3.1 人工智慧概念',
    '3.1 第三章生成式AI 應用與規劃': '3.1 No code / Low code 概念',
    '3.1 No code / Low code': '3.1 No code / Low code 概念',
    '3.3 生成式AI': '3.3 生成式AI 技術與應用',
    '3.2 AI': '3.2 生成式AI 應用領域與工具使用',
    '3.3 AI': '3.3 生成式AI 導入評估規劃',
    '3.4 AI': '3.4 鑑別式AI 與生成式AI 概念',
    '4.1 AI': '4.1 AI 導入評估',
    '4.2 AI': '4.2 AI 導入規劃',
    '4.3 AI': '4.3 AI 風險管理',
    '5.2 AI': '5.2 AI 技術系統集成與部署',
    '6.2 AI': '6.2 大數據在鑑別式AI 中的應用',
    '6.3 AI': '6.3 大數據在生成式AI 中的應用',
    '3.1 機率/': '3.1 機率/統計之機器學習基礎應用',
    '5. No Code / Low Code': '5. No Code / Low Code 平台選擇與評估',
    '7. No Code / Low Code': '7. No Code / Low Code 導入效益',
    '8. AI No Code / Low Code': '8. AI No Code / Low Code 發展趨勢',
    '（4）數值標準化（Standardization）': '（4）數值標準化（Standardization）與正規化（Normalization）',
    '（1）基本架構與監督式學習不同，非監督學習模型的輸出通常不是具體的預測值，而是：': '（1）基本架構',
    '5. 多模態多模態 AI風險與未來趨勢': '5. 多模態 AI風險與未來趨勢',
    '3. 偏見（Bias）與倫理（Ethics': '3. 偏見（Bias）與倫理（Ethics）',
    'A. 原理：': 'A. 原理',
    '2. 監督式學習-': '2. 監督式學習-迴歸任務',
    '3. 監督式學習-': '3. 監督式學習-分類任務',
    '2. 生成式AI 導入流程': '3. 生成式AI 導入流程',
    '5. 生成式AI 導入風險與管理': '4. 生成式AI 導入風險與管理',
}


PARENT_BEFORE_HEADING: dict[str, dict[str, str]] = {
    'mid-s2c1': {
        '（1）偏度（Skewness）': '3. 分佈形狀與資料型態',
    },
    'mid-s2c4': {
        '（1）常見的資料品質問題類型': '2. 資料品質問題與清理策略',
    },
    'mid-s2c5': {
        '（1）結構化資料': '2. 資料型態與儲存需求',
    },
    'mid-s2c6': {
        '（1）特徵選擇方法（Feature Selection）': '3. 特徵工程',
        '（1）資料處理管線設計原則與流程架構': '4. 資料處理管線設計',
    },
    'mid-s2c10': {
        '（1）分散式模型訓練架構（Distributed Training）': '2. 大數據環境下的機器學習訓練',
        '（1）資料整合與處理管線（Data Processing）': '3. 端對端機器學習流程',
    },
    'mid-s2c11': {
        '（1）常見輸入資料型態與特性': '3. 鑑別式AI 的資料型態與標註策略',
    },
    'mid-s2c13': {
        '（1）個資識別風險': '2. 個資識別風險與保護技術',
        '（1）合規資料處理的基本原則': '3. 合規資料處理原則',
        '（1）制定資料與AI 治理政策': '4. 企業內部資料與AI 治理制度',
    },
    'mid-s2pdf-c3': {
        '（1）集中趨勢（Central Tendency）': '3.1 敘述性統計與資料摘要技術',
        '（1）偏度（Skewness）': '3. 分佈形狀與資料型態',
    },
    'mid-s2pdf-c4': {
        '（1）常見的資料品質問題類型': '3. 資料品質問題與評估',
        '（1）結構化資料': '2. 資料型態與儲存管理',
        '（1）特徵選擇方法（Feature Selection）': '3. 特徵工程',
    },
    'mid-s2pdf-c5': {
        '（1）樣本非隨機，偏誤被放大': '3. 大數據下統計推論的限制與風險',
    },
    'mid-s2pdf-c6': {
        '（1）資料規模大（Volume）': '2. 大數據特性對機器學習流程的影響',
        '（1）個資識別風險': '2. 個資識別風險與保護技術',
    },
    's2c1': {
        '（1） 模型準確性與可靠性': '6. AI No Code / Low Code 導入挑戰與風險',
        '（1） 降低技術門檻': '9. AI No Code / Low Code 對產業與社會的影響',
    },
    's2c2': {
        '（1） 生成式AI 技術突破': '3. 生成式AI 工具的技術進化',
        '（1） 藝術與設計/內容創作': '5. 生成式AI 應用案例',
    },
    's2c3': {
        '（1） 常見風險識別': '4. 生成式AI 導入風險與管理',
        '（1） 準備階段（挑選AI 應用方案）': '3. 生成式AI 導入流程',
        'A. 明確目標設定與優先級排序': '2. 導入目標與策略規劃',
    },
    's2pdf-c3': {
        '（1） 自動生成程式碼': '3. AI No Code / Low Code',
        '（1） 醫療保健': '4. AI No Code / Low Code 產業應用',
        '（1） 模型準確性與可靠性': '6. AI No Code / Low Code 導入挑戰與風險',
        '（1） 降低技術門檻': '9. AI No Code / Low Code 對產業與社會的影響',
        '（1） 深度學習網路（Deep Learning Networks）': '1. 生成式AI 的基本概念',
        '（1） 市場規模與增長趨勢': '2. 生成式AI 的市場價值與影響力',
        '（1） 生成式AI 技術突破': '3. 生成式AI 工具的技術進化',
        '（1） 專業化與垂直整合': '4. 生成式AI 應用領域',
        '（1） 藝術與設計/內容創作': '5. 生成式AI 應用案例',
        '（1） 需求與現狀評估': '1. 生成式AI 導入評估標準',
        '（1） 目標用戶與技術需求': '5. No Code / Low Code 平台選擇與評估',
        '（1） 準備階段（挑選AI 應用方案）': '3. 生成式AI 導入流程',
        'A. 明確目標設定與優先級排序': '2. 導入目標與策略規劃',
        '（1） 常見風險識別': '4. 生成式AI 導入風險與管理',
    },
}


DEMOTE_EXACT_HEADINGS_BY_CONTENT: dict[str, set[str]] = {
    's2pdf-c3': {
        '5. No Code / Low Code 平台選擇與評估',
    },
}


DEMOTE_ALPHA_PREFIXES_BY_CONTENT: dict[str, tuple[str, ...]] = {
    'mid-s3c1': ('A. 設定虛無假設',),
    'mid-s3pdf-c3': ('A. 設定虛無假設',),
    'mid-s3c4': ('A. 初始化策略或價值函數',),
    'mid-s3pdf-c4': ('A. 初始化策略或價值函數',),
    'mid-s1c4': ('A. 目前遇到的挑戰',),
    'mid-s1pdf-c3': ('A. 目前遇到的挑戰',),
    'mid-s2c3': ('A. 設定虛無假設',),
    'mid-s2pdf-c3': ('A. 設定虛無假設',),
}


DEMOTE_LEADING_TOC_BY_CONTENT: dict[str, set[str]] = {
    'mid-s1pdf-c3': {
        '第三章 AI 相關技術應用',
        '3.1 自然語言處理技術與應用',
        '3.2 電腦視覺技術與應用',
        '3.3 生成式AI 技術與應用',
        '3.4 多模態人工智慧應用',
    },
}


S1C4_MODEL_HEADING_PREFIXES = (
    '（1） 邏輯迴歸',
    '（2） 支援向量機',
    '（3） 決策樹',
    '（4） 隨機森林',
    '（5） 神經網路',
    '（1） 生成對抗網路',
    '（2） 變分自編碼器',
    '（3） 擴散模型',
)


def manifest_chapter_heading(current_id: str, raw_title: str, blocks: list[dict]) -> str | None:
    if 'pdf-' in current_id or 'pdf' in current_id:
        return None
    if not raw_title:
        return None
    for block in blocks[:4]:
        text = block.get('title') or block.get('text') or ''
        match = re.match(r'^(\d+\.\d+)(?:\s+.*)?$', text.strip())
        if match:
            return f'{match.group(1)} {raw_title}'
    return None


def next_section_title(content_id: str, marker: str, seen_markers: dict[str, int]) -> str | None:
    options = CONTENT_SECTION_TITLES.get(content_id, {}).get(marker)
    if not options:
        return None
    index = seen_markers.get(marker, 0)
    seen_markers[marker] = index + 1
    if index < len(options):
        return options[index]
    return None


def normalize_guide_heading_depths(blocks: list[dict]) -> None:
    seen_depth4_since_depth3 = False
    for block in blocks:
        if block.get('type') != 'heading':
            continue
        depth = int(block.get('depth') or 0)
        title = block.get('title') or ''
        if depth <= 3:
            seen_depth4_since_depth3 = False
        if depth == 4:
            seen_depth4_since_depth3 = True
        if depth == 5 and re.match(r'^[A-Z]\.\s+', title) and not seen_depth4_since_depth3:
            block['depth'] = 4


def demote_heading_to_list_item(block: dict) -> dict:
    title = block.get('title') or ''
    marker_match = re.match(r'^([A-Za-z]\.)\s*(.+)$', title)
    marker = marker_match.group(1) if marker_match else ''
    text = marker_match.group(2) if marker_match else title
    return {
        'type': 'list_item',
        'depth': int(block.get('depth') or 5),
        'marker': marker,
        'text': block_text(text),
        'pageIndex': block.get('pageIndex'),
        'bbox': block.get('bbox'),
    }


def demote_leading_toc_headings(current_id: str, blocks: list[dict]) -> None:
    titles = DEMOTE_LEADING_TOC_BY_CONTENT.get(current_id)
    if not titles:
        return
    demoted: set[str] = set()
    for index, block in enumerate(blocks):
        if block.get('type') != 'heading':
            continue
        title = block.get('title') or ''
        if title in titles and title not in demoted:
            blocks[index] = {
                'type': 'list_item',
                'depth': 3,
                'marker': '',
                'text': title,
                'pageIndex': block.get('pageIndex'),
                'bbox': block.get('bbox'),
            }
            demoted.add(title)
            if demoted == titles:
                return


def demote_gapped_alpha_heading_groups(blocks: list[dict]) -> None:
    group: list[int] = []

    def flush() -> None:
        nonlocal group
        if len(group) == 1:
            title = blocks[group[0]].get('title') or ''
            if not title.startswith('A. '):
                blocks[group[0]] = demote_heading_to_list_item(blocks[group[0]])
            group = []
            return
        if len(group) < 2:
            group = []
            return
        letters = []
        for index in group:
            title = blocks[index].get('title') or ''
            match = re.match(r'^([A-Z])\.\s+', title)
            if match:
                letters.append(match.group(1))
        expected = [chr(ord('A') + offset) for offset in range(len(letters))]
        if letters != expected:
            for index in group:
                blocks[index] = demote_heading_to_list_item(blocks[index])
        group = []

    for index, block in enumerate(blocks):
        if block.get('type') != 'heading':
            continue
        title = block.get('title') or ''
        depth = int(block.get('depth') or 0)
        if depth <= 4:
            flush()
        if depth == 5 and re.match(r'^[A-Z]\.\s+', title):
            group.append(index)
        elif depth <= 5:
            flush()
    flush()


def demote_specific_alpha_sequences(current_id: str, blocks: list[dict]) -> None:
    prefixes = DEMOTE_ALPHA_PREFIXES_BY_CONTENT.get(current_id)
    if not prefixes:
        return
    active_depth: int | None = None
    for index, block in enumerate(blocks):
        if block.get('type') != 'heading':
            continue
        depth = int(block.get('depth') or 0)
        title = block.get('title') or ''
        if active_depth is not None:
            if depth == active_depth and re.match(r'^[A-Z]\.\s+', title):
                blocks[index] = demote_heading_to_list_item(block)
                continue
            if depth <= active_depth:
                active_depth = None
        if any(title.startswith(prefix) for prefix in prefixes):
            active_depth = depth
            blocks[index] = demote_heading_to_list_item(block)


def merge_heading_continuation_paragraphs(blocks: list[dict]) -> list[dict]:
    merged: list[dict] = []
    for block in blocks:
        if (
            merged
            and merged[-1].get('type') == 'heading'
            and block.get('type') == 'paragraph'
            and re.match(r'^(與|及|和)[^。！？]{1,40}$', block.get('text') or '')
        ):
            title = f'{merged[-1]["title"]}{block["text"]}'
            retitle_heading(merged[-1], TITLE_REPLACEMENTS.get(title, title), len(merged))
            continue
        merged.append(block)
    return merged


def split_numbered_exercise_segments(text: str, answer_mode: bool = False) -> list[str]:
    text = block_text(text)
    if not text:
        return []
    if answer_mode:
        pattern = re.compile(r'(?<!\d)(\d{1,3})\.\s*Ans')
    else:
        pattern = re.compile(r'(?<!\d)(\d{1,3})\.\s+(?!Ans)')
    matches = list(pattern.finditer(text))
    if not matches:
        return [text]
    segments = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        segment = text[start:end].strip()
        if segment:
            segments.append(segment)
    return segments


def normalize_chapter_exercise_blocks(blocks: list[dict]) -> list[dict]:
    """Re-split chapter exercises that PDF extraction merged into option paragraphs."""
    normalized: list[dict] = []
    index = 0
    while index < len(blocks):
        block = blocks[index]
        normalized.append(block)
        if block.get('type') != 'heading' or block.get('title') != '章節練習題':
            index += 1
            continue

        exercise_blocks: list[dict] = []
        index += 1
        while index < len(blocks):
            exercise_blocks.append(blocks[index])
            index += 1

        question_parts: list[str] = []
        answer_parts: list[str] = []
        answer_started = False
        first_meta = {
            'pageIndex': exercise_blocks[0].get('pageIndex') if exercise_blocks else block.get('pageIndex'),
            'bbox': exercise_blocks[0].get('bbox') if exercise_blocks else block.get('bbox'),
        }
        for exercise_block in exercise_blocks:
            text = exercise_block.get('text') or exercise_block.get('title') or ''
            if not text:
                continue
            if exercise_block.get('type') == 'answer' or re.match(r'^\d+\.\s*Ans', text.strip()):
                answer_started = True
            if answer_started:
                answer_parts.append(text)
            else:
                question_parts.append(text)

        for segment in split_numbered_exercise_segments(' '.join(question_parts), answer_mode=False):
            normalized.append({
                'type': 'question',
                'depth': 4,
                'text': segment,
                'pageIndex': first_meta['pageIndex'],
                'bbox': first_meta['bbox'],
            })
        for segment in split_numbered_exercise_segments(' '.join(answer_parts), answer_mode=True):
            normalized.append({
                'type': 'answer',
                'depth': 4,
                'text': segment,
                'pageIndex': first_meta['pageIndex'],
                'bbox': first_meta['bbox'],
            })
        break
    return normalized


def post_process_guide_blocks(current_id: str, raw_title: str, blocks: list[dict]) -> list[dict]:
    processed: list[dict] = []
    seen_markers: dict[str, int] = {}
    chapter_heading = manifest_chapter_heading(current_id, raw_title, blocks)
    used_chapter_heading = False

    for original in blocks:
        block = dict(original)
        block_type = block.get('type')
        title_or_text = block.get('title') or block.get('text') or ''
        stripped = title_or_text.strip()

        if stripped == 'AI' and processed and processed[-1].get('type') == 'heading' and processed[-1].get('depth') == 2:
            continue

        if block_type in {'paragraph', 'question'}:
            marker_match = re.fullmatch(r'\d+\.', stripped)
            replacement = next_section_title(current_id, stripped, seen_markers) if marker_match else None
            if (
                not replacement
                and current_id not in {'s2pdf-c3'}
                and stripped == '1.'
                and processed
                and processed[-1].get('type') == 'heading'
                and processed[-1].get('depth') == 2
            ):
                replacement = '1. 前言與章節導覽'
            if replacement:
                block = {
                    'type': 'heading',
                    'depth': 3,
                    'title': replacement,
                    'anchor': '',
                    'pageIndex': block.get('pageIndex'),
                    'bbox': block.get('bbox'),
                }
                processed.append(block)
                continue
            if chapter_heading and not used_chapter_heading and re.fullmatch(r'\d+\.\d+', stripped):
                block = {
                    'type': 'heading',
                    'depth': 2,
                    'title': chapter_heading,
                    'anchor': '',
                    'pageIndex': block.get('pageIndex'),
                    'bbox': block.get('bbox'),
                }
                used_chapter_heading = True
                processed.append(block)
                continue
            paragraph_section = re.match(r'^(\d+\.)\s+(.+)$', stripped)
            if paragraph_section:
                replacement = next_section_title(current_id, paragraph_section.group(1), seen_markers)
                if (
                    not replacement
                    and current_id not in {'s2pdf-c3'}
                    and paragraph_section.group(1) == '1.'
                    and processed
                    and processed[-1].get('type') == 'heading'
                    and processed[-1].get('depth') == 2
                ):
                    replacement = '1. 前言與章節導覽'
                if replacement:
                    block = {
                        'type': 'heading',
                        'depth': 3,
                        'title': replacement,
                        'anchor': '',
                        'pageIndex': block.get('pageIndex'),
                        'bbox': block.get('bbox'),
                    }
                    processed.append(block)
                    detail = paragraph_section.group(2).strip()
                    if detail:
                        processed.append({
                            'type': 'paragraph',
                            'depth': 4,
                            'text': detail,
                            'pageIndex': original.get('pageIndex'),
                            'bbox': original.get('bbox'),
                        })
                    continue

        if block_type == 'heading':
            title = TITLE_REPLACEMENTS.get(stripped, stripped)
            if title.startswith('第三章 '):
                block['depth'] = 1
            if chapter_heading and not used_chapter_heading and int(block.get('depth') or 0) == 2:
                current_prefix = re.match(r'^(\d+\.\d+)(?:\s+.*)?$', title)
                target_prefix = re.match(r'^(\d+\.\d+)(?:\s+.*)?$', chapter_heading)
                if current_prefix and target_prefix and current_prefix.group(1) == target_prefix.group(1):
                    title = chapter_heading
                    used_chapter_heading = True

            if re.match(r'^[a-z]\.\s+', title):
                marker, text = title.split('.', 1)
                block = {
                    'type': 'list_item',
                    'depth': 6,
                    'marker': f'{marker}.',
                    'text': block_text(text),
                    'pageIndex': block.get('pageIndex'),
                    'bbox': block.get('bbox'),
                }
                processed.append(block)
                continue

            heading, detail = split_heading_title(title, int(block.get('depth') or 0))
            heading = TITLE_REPLACEMENTS.get(heading, heading)
            if current_id in {'s2c3', 's2pdf-c3'} and heading == '（3） 資源與基礎設施評估':
                heading = '（3） 導入策略與階段規劃'
            block['title'] = heading
            if (
                heading in DEMOTE_EXACT_HEADINGS_BY_CONTENT.get(current_id, set())
                or (current_id == 's2pdf-c3' and heading.startswith('5. No Code / Low Code 平台選擇'))
            ):
                block = demote_heading_to_list_item(block)
                processed.append(block)
                if detail:
                    processed.append({
                        'type': 'paragraph',
                        'depth': min(int(block.get('depth') or 0) + 1, 9),
                        'text': block_text(detail),
                        'pageIndex': original.get('pageIndex'),
                        'bbox': original.get('bbox'),
                    })
                continue
            if current_id in {'s1c4', 's1pdf-c3'} and any(heading.startswith(prefix) for prefix in S1C4_MODEL_HEADING_PREFIXES):
                block['depth'] = 5
            if current_id in {'s1c4', 's1pdf-c3'} and heading == 'A. 原理':
                block = demote_heading_to_list_item(block)
                processed.append(block)
                if detail:
                    processed.append({
                        'type': 'paragraph',
                        'depth': 6,
                        'text': block_text(detail),
                        'pageIndex': original.get('pageIndex'),
                        'bbox': original.get('bbox'),
                    })
                continue
            parent_title = PARENT_BEFORE_HEADING.get(current_id, {}).get(heading)
            if parent_title and not any(item.get('type') == 'heading' and item.get('title') == parent_title for item in processed):
                parent_depth = 2 if re.match(r'^\d+\.\d+\s+', parent_title) else 3
                processed.append({
                    'type': 'heading',
                    'depth': parent_depth,
                    'title': parent_title,
                    'anchor': '',
                    'pageIndex': block.get('pageIndex'),
                    'bbox': block.get('bbox'),
                })
            processed.append(block)
            if detail:
                processed.append({
                    'type': 'paragraph',
                    'depth': min(int(block.get('depth') or 0) + 1, 9),
                    'text': block_text(detail),
                    'pageIndex': block.get('pageIndex'),
                    'bbox': block.get('bbox'),
                })
            continue

        processed.append(block)

    normalize_guide_heading_depths(processed)
    demote_gapped_alpha_heading_groups(processed)
    demote_specific_alpha_sequences(current_id, processed)
    demote_leading_toc_headings(current_id, processed)
    processed = merge_heading_continuation_paragraphs(processed)
    processed = normalize_chapter_exercise_blocks(processed)
    for index, block in enumerate(processed, start=1):
        if block.get('type') == 'heading':
            retitle_heading(block, block.get('title') or '', index)
    return reset_block_ids(processed)


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
    if previous.get('type') != 'list_item' and len(text) > 60:
        return False
    prev_bbox = previous.get('bbox') or []
    current_bbox = item.get('bbox') or []
    if len(prev_bbox) == 4 and len(current_bbox) == 4:
        vertical_gap = current_bbox[1] - prev_bbox[3]
        if vertical_gap > 24:
            return False
        if previous.get('type') == 'list_item':
            continuation_indent = current_bbox[0] >= prev_bbox[0] + 8
            same_line_wrap = abs(current_bbox[0] - prev_bbox[0]) <= 24
            return continuation_indent or same_line_wrap
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
    in_chapter_exercises = False
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
            if not in_chapter_exercises:
                in_chapter_exercises = True
                current_context_depth = 3
                append_block(blocks, {
                    'type': 'heading',
                    'depth': 3,
                    'title': '章節練習題',
                    'anchor': slugify_heading('章節練習題', len(blocks) + 1),
                    'pageIndex': item.get('page_index'),
                    'bbox': item.get('bbox'),
                })
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
            html = table_rows_to_html(item.get('rows') or [])
            if html:
                chunks.append(html)
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
    prebuilt_blocks_by_node: dict[str, list[dict]] | None = None,
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
            prebuilt_blocks_by_node=prebuilt_blocks_by_node,
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
        blocks = (
            prebuilt_blocks_by_node.get(current_id)
            if prebuilt_blocks_by_node is not None
            else None
        )
        if blocks is None:
            blocks = post_process_guide_blocks(current_id, raw_node.get('title') or '', page_blocks(level, key, start_page, end_page))
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


def load_guide_tree(level: str, key: str) -> tuple[dict, dict[str, list[dict]]]:
    tree_dir = BASE / 'data' / level / 'guide_tree' / key
    tree_path = tree_dir / 'tree.json'
    blocks_path = tree_dir / 'blocks.json'
    if not tree_path.exists() or not blocks_path.exists():
        raise FileNotFoundError(
            f'Missing guide tree for {level}/{key}; run '
            f'python3 scripts/build_guide_tree.py --level {level} --key {key}'
        )
    return load_json(tree_path), load_json(blocks_path)


def export_level_from_guide_tree(level: str, content_dir: Path) -> dict[str, Any]:
    manifest = load_json(BASE / 'data' / level / 'toc_manifest.json')
    guides = {}
    for subject in manifest['subjects']:
        key = subject['key']
        content_key = f'{level}-{key}'
        tree, blocks_by_node = load_guide_tree(level, key)
        nodes_by_id: dict[str, dict] = {}
        root_ids = build_nodes(
            level=level,
            subject_id=subject['id'],
            key=key,
            content_key=content_key,
            raw_nodes=tree['outline'],
            manifest_subject=subject,
            content_dir=content_dir,
            prebuilt_blocks_by_node=blocks_by_node,
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
            'stats': tree.get('stats') or {},
            'treeSource': f'data/{level}/guide_tree/{key}/tree.json',
        }
        validate_guide(guide, content_dir)
        guides[subject['id']] = guide
    return guides


def export(levels: list[str], use_guide_tree: bool = False) -> dict[str, Any]:
    generated_dir = BASE / 'frontend' / 'src' / 'generated'
    content_dir = generated_dir / 'guideContent'
    if content_dir.exists():
        shutil.rmtree(content_dir)

    guides = {}
    for level in levels:
        if use_guide_tree:
            guides.update(export_level_from_guide_tree(level, content_dir))
        else:
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
    parser.add_argument('--use-guide-tree', action='store_true', help='使用 data/{level}/guide_tree/{key}/ 的預建章節樹')
    args = parser.parse_args()

    levels = ['初級', '中級'] if args.all_levels else [args.level]
    data = export(levels, use_guide_tree=args.use_guide_tree)
    out_path = BASE / 'frontend' / 'src' / 'generated' / 'guideOutlines.json'
    write_json(out_path, data)
    for guide in data['guides'].values():
        print(f'{guide["level"]}/{guide["sourceKey"]}: {len(guide["flat"])} guide outline nodes')


if __name__ == '__main__':
    main()
