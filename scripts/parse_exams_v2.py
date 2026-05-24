#!/usr/bin/env python3
"""Parse exam questions from JSON tables (accurate extraction)."""

import json
import re
from pathlib import Path

from PIL import Image

from extract_pdfs import EXAM_PDFS_BY_LEVEL

BASE = Path('/home/james/projects/ipas-test')

EXAM_TITLES_BY_LEVEL: dict[str, dict[str, str]] = {
    '初級': {
        'exam1': '科目一 模擬考試：人工智慧基礎概論（114年第四梯次公告試題）',
        'exam2': '科目二 模擬考試：生成式AI應用與規劃（114年第四梯次公告試題）',
        'sample': '考試樣題（114年9月版）',
    },
    '中級': {
        'exam1': '中級科目一 模擬考試：人工智慧技術應用與規劃（114年第二梯次公告試題）',
        'exam2': '中級科目二 模擬考試：大數據處理分析與應用（114年第二梯次公告試題）',
        'exam3': '中級科目三 模擬考試：機器學習技術與應用（114年第二梯次公告試題）',
        'sample': '中級考試樣題（114年9月版）',
    },
}

FW_MAP = {'Ａ': 'A', 'Ｂ': 'B', 'Ｃ': 'C', 'Ｄ': 'D', '（': '(', '）': ')'}
IMAGE_HINT_RE = re.compile(
    r'附圖|下圖|圖中|如下圖|參考下圖|圖所示|欄位概觀|外觀如下|視覺化後的外觀|參考附圖|參考.*執行結果',
)
CODE_HINT_RE = re.compile(r'附圖程式碼|參考.*程式碼|下列程式碼|哪.*程式碼|程式碼片段')
SHARED_QUESTION_RE = re.compile(r'回答(?:以|第|後續)?\s*(\d+)\s*[~～\-至到]+\s*(\d+)\s*題')
OPTION_ANCHOR_RE = re.compile(r'(?:^|[\s;；])\(?([A-D])\)|選項\s*([A-D])\s*[:：]')
FOLLOWUP_CONTEXT_MARKERS = (
    '一間',
    '一家',
    '使用',
    '在郵遞',
    '資料的欄位概觀如下',
    '下圖顯示',
    '根據這份資料',
    '請根據',
    'VGG16',
)


def normalize(s: str) -> str:
    for fw, hw in FW_MAP.items():
        s = s.replace(fw, hw)
    return s


def clean_parsed_text(text: str) -> str:
    # PDF table extraction can leak the answer-column tail "案" into the
    # question cell. Keep this scoped to isolated glyphs with surrounding space.
    text = re.sub(r'\s+案\s+', ' ', text)
    text = re.sub(r'\s+案$', '', text)
    return re.sub(r'\s+', ' ', text).strip()


def trim_followup_context(text: str) -> str:
    match = SHARED_QUESTION_RE.search(text)
    if not match:
        return text.strip()

    earliest = match.start()
    for marker in FOLLOWUP_CONTEXT_MARKERS:
        index = text.find(marker)
        if index >= 0 and index < earliest:
            earliest = index
    return text[:earliest].strip(' ;；。')


def parse_question_cell(
    answer: str,
    cell_text: str,
    qnum: int,
    source_key: str,
    page_index: int | None = None,
) -> dict | None:
    """Parse a single question from table cell text."""
    answer = normalize(answer.strip())
    if answer not in ('A', 'B', 'C', 'D'):
        return None

    text = cell_text.strip()
    # Remove embedded question number (e.g. "\n1.\n" or "1.")
    text = re.sub(r'\n\d+[\.\．]\n', '\n', text)
    text = re.sub(r'^\d+[\.\．]\s*', '', text)

    # Extract options
    opts = {}
    opt_pattern = re.compile(r'\(([A-D])\)(.*?)(?=\([A-D]\)|\Z)', re.DOTALL)
    for m in opt_pattern.finditer(text):
        opt_text = m.group(2).strip()
        opt_text = trim_followup_context(opt_text)
        opt_text = re.sub(r'[；;]\s*$', '', opt_text)
        opt_text = clean_parsed_text(opt_text)
        opts[m.group(1)] = opt_text

    if len(opts) < 4:
        return None

    # Question text = everything before first option
    q_match = re.match(r'^(.*?)(?=\([A-D]\))', text, re.DOTALL)
    q_text = q_match.group(1).strip() if q_match else ''
    q_text = clean_parsed_text(q_text)

    if not q_text or not opts:
        return None

    question = {
        'id': f'{source_key}_q{qnum}',
        'question': q_text,
        'options': opts,
        'answer': answer,
        'explanation': f'正確答案為({answer})。',
        'source': source_key,
    }
    if page_index is not None:
        question['source_ref'] = {
            'page_index': page_index,
            'page_number': page_index + 1,
        }
    return question


def public_asset_path(level: str, key: str, page_index: int, filename: str) -> str:
    return f'/pdf-assets/{level}/{key}/page_{page_index:03d}/{filename}'


def public_asset_file(level: str, key: str, page_index: int, filename: str) -> Path:
    return BASE / 'frontend' / 'public' / 'pdf-assets' / level / key / f'page_{page_index:03d}' / filename


def load_page_image_assets(level: str, key: str) -> dict[int, dict]:
    pages_dir = BASE / 'data' / level / 'page_extract' / key / 'pages'
    if not pages_dir.exists():
        return {}

    assets_by_page: dict[int, dict] = {}
    for page_path in sorted(pages_dir.glob('page_*.json')):
        page = json.loads(page_path.read_text(encoding='utf-8'))
        page_index = page['page_index']
        images = []
        for image in page.get('images', []):
            rel_path = image.get('path')
            if not rel_path:
                continue
            images.append({
                'type': 'image',
                'src': public_asset_path(level, key, page_index, Path(rel_path).name),
                'alt': f'{key} 第 {page_index + 1} 頁圖片 {image.get("id", "")}'.strip(),
                'page_index': page_index,
                'page_number': page_index + 1,
                'bbox': image.get('bbox', []),
            })

        if images:
            assets_by_page[page_index] = {
                'images': images,
            }
    return assets_by_page


def load_page_extract(level: str, key: str) -> dict[int, dict]:
    pages_dir = BASE / 'data' / level / 'page_extract' / key / 'pages'
    if not pages_dir.exists():
        return {}
    return {
        int(path.stem.split('_')[-1]): json.loads(path.read_text(encoding='utf-8'))
        for path in sorted(pages_dir.glob('page_*.json'))
    }


def block_text(value: str) -> str:
    return re.sub(r'\s+', '', normalize(value))


def find_question_start_y(page: dict, question: dict) -> float | None:
    qid = question.get('id', '')
    number_match = re.search(r'_q(\d+)$', qid)
    qnum = int(number_match.group(1)) if number_match else None
    q_text = block_text(question.get('question', ''))
    q_probe = q_text[:14]
    number_candidates: list[float] = []
    number_text_candidates: list[float] = []
    text_candidates: list[float] = []

    for block in page.get('blocks', []):
        text = block.get('text', '')
        compact = block_text(text)
        if qnum is not None and re.search(rf'(^|[^\d~～\-]){qnum}(?![\d~～\-])[\.\s．]', normalize(text)):
            block_y = float(block['bbox'][1])
            number_candidates.append(block_y)
            if q_probe and q_probe in compact:
                number_text_candidates.append(block_y)
            continue
        if q_probe and q_probe in compact:
            text_candidates.append(float(block['bbox'][1]))

    if number_candidates:
        if number_text_candidates:
            return min(number_text_candidates)
        number_y = min(number_candidates)
        if text_candidates:
            closest_text_y = min(text_candidates, key=lambda value: abs(value - number_y))
            if abs(closest_text_y - number_y) <= 320:
                return closest_text_y
        return number_y
    return min(text_candidates) if text_candidates else None


def question_number(question: dict) -> int | None:
    match = re.search(r'_q(\d+)$', question.get('id', ''))
    return int(match.group(1)) if match else None


def build_question_ranges(questions: list[dict], pages: dict[int, dict]) -> dict[str, list[tuple[int, float, float]]]:
    starts: dict[str, tuple[int, float]] = {}
    questions_by_page: dict[int, list[dict]] = {}
    for question in questions:
        page_index = (question.get('source_ref') or {}).get('page_index')
        if not isinstance(page_index, int) or page_index not in pages:
            continue
        start_y = find_question_start_y(pages[page_index], question)
        if start_y is None:
            continue
        starts[question['id']] = (page_index, start_y)
        questions_by_page.setdefault(page_index, []).append(question)

    for page_questions in questions_by_page.values():
        page_questions.sort(key=lambda item: starts.get(item['id'], (9999, 9999))[1])

    ordered = [
        (question_number(question), question['id'], starts[question['id']])
        for question in questions
        if question['id'] in starts and question_number(question) is not None
    ]
    ordered.sort(key=lambda item: item[0] or 0)

    ranges: dict[str, list[tuple[int, float, float]]] = {}
    max_page_index = max(pages.keys(), default=-1)
    for index, (_qnum, question_id, (start_page, start_y)) in enumerate(ordered):
        if index + 1 < len(ordered):
            next_page, next_y = ordered[index + 1][2]
        else:
            next_page, next_y = max_page_index, float(pages.get(max_page_index, {}).get('height') or 842)

        intervals: list[tuple[int, float, float]] = []
        for page_index in range(start_page, next_page + 1):
            page = pages.get(page_index)
            if not page:
                continue
            height = float(page.get('height') or 842)
            y0 = start_y if page_index == start_page else 90
            y1 = next_y - 6 if page_index == next_page else height - 45
            if y1 > y0:
                intervals.append((page_index, y0, y1))
        ranges[question_id] = intervals

    return cap_ranges_at_followup_context(questions, pages, ranges)


def cap_ranges_at_followup_context(
    questions: list[dict],
    pages: dict[int, dict],
    ranges: dict[str, list[tuple[int, float, float]]],
) -> dict[str, list[tuple[int, float, float]]]:
    capped: dict[str, list[tuple[int, float, float]]] = {}
    qnum_by_id = {question['id']: question_number(question) for question in questions}
    for question_id, intervals in ranges.items():
        qnum = qnum_by_id.get(question_id)
        if qnum is None:
            capped[question_id] = intervals
            continue

        next_context: tuple[int, float] | None = None
        for page_index, y0, y1 in intervals:
            page = pages.get(page_index)
            if not page:
                continue
            for block in page.get('blocks', []):
                center_y = block_center_y(block)
                if center_y < y0 or center_y > y1:
                    continue
                match = SHARED_QUESTION_RE.search(normalize(block.get('text', '')))
                if match and int(match.group(1)) > qnum:
                    candidate = (page_index, center_y)
                    if next_context is None or candidate < next_context:
                        next_context = candidate

        if next_context is None:
            capped[question_id] = intervals
            continue

        context_page, context_y = next_context
        new_intervals = []
        for page_index, y0, y1 in intervals:
            if page_index > context_page:
                break
            if page_index == context_page:
                y1 = min(y1, context_y - 8)
            if y1 > y0:
                new_intervals.append((page_index, y0, y1))
        capped[question_id] = new_intervals

    return capped


def question_ranges_by_number(
    questions: list[dict],
    ranges: dict[str, list[tuple[int, float, float]]],
) -> dict[int, list[tuple[int, float, float]]]:
    by_number: dict[int, list[tuple[int, float, float]]] = {}
    for question in questions:
        qnum = question_number(question)
        if qnum is not None and question['id'] in ranges:
            by_number[qnum] = ranges[question['id']]
    return by_number


def image_center_y(image: dict) -> float | None:
    bbox = image.get('bbox') or []
    if len(bbox) < 4:
        return None
    return (float(bbox[1]) + float(bbox[3])) / 2


def images_in_question_range(images: list[dict], y0: float, y1: float) -> list[dict]:
    selected = []
    for image in images:
        center_y = image_center_y(image)
        if center_y is not None and y0 - 16 <= center_y <= y1 + 16:
            selected.append(image)
    return selected


def block_center_y(block: dict) -> float:
    bbox = block.get('bbox') or [0, 0, 0, 0]
    return (float(bbox[1]) + float(bbox[3])) / 2


def is_page_noise(text: str) -> bool:
    compact = re.sub(r'\s+', '', normalize(text))
    return (
        not compact
        or '能力鑑定' in compact
        or '考試日期' in compact
        or compact in {'答案題目', '答案', '題目', '答', '案'}
        or re.match(r'^第\d+頁,?共\d+頁$', compact) is not None
    )


def collect_text_between(page: dict, y0: float, y1: float) -> list[str]:
    lines = []
    for block in page.get('blocks', []):
        bbox = block.get('bbox') or []
        if len(bbox) < 4:
            continue
        center_y = block_center_y(block)
        if center_y < y0 or center_y > y1:
            continue
        text = clean_parsed_text(block.get('text', ''))
        if is_page_noise(text):
            continue
        if OPTION_ANCHOR_RE.search(normalize(text)):
            continue
        if re.match(r'^[A-D]\s*\d+(?:[\.\s．]|$)', normalize(text)):
            continue
        lines.append(text)
    return lines


def shared_context_start_y(page: dict, marker_y: float) -> float:
    anchors = find_option_anchors(page, 90, marker_y - 1)
    if anchors:
        return anchors[-1][1] + 18
    return 90


def previous_page_context_start_y(page: dict) -> float:
    anchors = find_option_anchors(page, 90, float(page.get('height') or 842) - 45)
    if anchors:
        return anchors[-1][1] + 18
    return 90


def build_shared_context_texts(
    pages: dict[int, dict],
    questions: list[dict],
    ranges_by_question: dict[str, list[tuple[int, float, float]]],
) -> dict[int, str]:
    shared_by_qnum: dict[int, str] = {}
    ranges_by_qnum = question_ranges_by_number(questions, ranges_by_question)
    for page_index, page in pages.items():
        height = float(page.get('height') or 842)
        for block in page.get('blocks', []):
            marker_text = clean_parsed_text(block.get('text', ''))
            match = SHARED_QUESTION_RE.search(normalize(marker_text))
            if not match:
                continue

            marker_y = block_center_y(block)
            start_q, end_q = int(match.group(1)), int(match.group(2))
            lines: list[str] = []

            same_page_lines = collect_text_between(page, shared_context_start_y(page, marker_y), marker_y - 2)
            lines.extend(same_page_lines)

            if not same_page_lines:
                previous_page = pages.get(page_index - 1)
                if previous_page:
                    previous_height = float(previous_page.get('height') or 842)
                    lines.extend(collect_text_between(
                        previous_page,
                        previous_page_context_start_y(previous_page),
                        previous_height - 45,
                    ))

            if marker_text and not is_page_noise(marker_text):
                lines.append(marker_text)

            first_target_range = ranges_by_qnum.get(start_q, [])
            if first_target_range:
                first_page, first_y, _first_y1 = first_target_range[0]
                for context_page_index in range(page_index, first_page + 1):
                    context_page = pages.get(context_page_index)
                    if not context_page:
                        continue
                    context_height = float(context_page.get('height') or 842)
                    after_y0 = marker_y + 2 if context_page_index == page_index else 90
                    after_y1 = first_y - 8 if context_page_index == first_page else context_height - 45
                    if after_y1 > after_y0:
                        lines.extend(collect_text_between(context_page, after_y0, after_y1))

            context = clean_parsed_text(' '.join(lines))
            if not context:
                continue
            for qnum in range(start_q, end_q + 1):
                shared_by_qnum[qnum] = context
    return shared_by_qnum


def find_option_anchors(page: dict, y0: float, y1: float) -> list[tuple[str, float]]:
    anchors: list[tuple[str, float]] = []
    for block in page.get('blocks', []):
        bbox = block.get('bbox') or []
        if len(bbox) < 4:
            continue
        center = block_center_y(block)
        if center < y0 - 8 or center > y1 + 8:
            continue
        text = normalize(block.get('text', '').strip())
        match = OPTION_ANCHOR_RE.search(text)
        if match:
            option = match.group(1) or match.group(2)
            anchors.append((option, center))
    return sorted(anchors, key=lambda item: item[1])


def make_visual_gap_crop(
    level: str,
    key: str,
    page_index: int,
    page: dict,
    question_id: str,
    y0: float,
    y1: float,
) -> dict | None:
    anchors = find_option_anchors(page, y0, y1)
    option_y = anchors[0][1] if anchors else y1
    crop_y0 = y0 + 18
    crop_y1 = option_y - 8
    if crop_y1 - crop_y0 < 24:
        return None

    page_image = page.get('page_image') or {}
    rel_path = page_image.get('path')
    if not rel_path:
        return None
    page_json = BASE / 'data' / level / 'page_extract' / key / 'pages' / f'page_{page_index:03d}.json'
    source = (page_json.parent / rel_path).resolve()
    if not source.exists():
        return None

    width = float(page.get('width') or 595)
    filename = f'{question_id}_visual_p{page_index:03d}.png'
    dest = public_asset_file(level, key, page_index, filename)
    dest.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(source) as image:
        scale_x = image.width / width
        scale_y = image.height / float(page.get('height') or 842)
        box = (
            max(0, int(110 * scale_x)),
            max(0, int(crop_y0 * scale_y)),
            min(image.width, int((width - 80) * scale_x)),
            min(image.height, int(crop_y1 * scale_y)),
        )
        if box[2] - box[0] < 40 or box[3] - box[1] < 20:
            return None
        image.crop(box).save(dest)

    return {
        'type': 'image',
        'src': public_asset_path(level, key, page_index, filename),
        'alt': f'{key} 第 {page_index + 1} 頁 {question_id} 題目附圖',
        'page_index': page_index,
        'page_number': page_index + 1,
        'bbox': [110, round(crop_y0, 2), round(width - 80, 2), round(crop_y1, 2)],
        'placement': 'question',
    }


def classify_image_placement(page: dict, image: dict, y0: float, y1: float) -> dict:
    payload = dict(image)
    payload['placement'] = 'question'
    center_y = image_center_y(image)
    if center_y is None:
        return payload

    anchors = find_option_anchors(page, y0, y1)
    if len(anchors) < 2:
        return payload

    for index, (option, anchor_y) in enumerate(anchors):
        next_y = anchors[index + 1][1] if index + 1 < len(anchors) else y1 + 24
        if anchor_y - 4 <= center_y < next_y - 4 and center_y - anchor_y <= 180:
            payload['placement'] = 'option'
            payload['option'] = option
            break
    return payload


def is_late_after_option_image_block(page: dict, image: dict, y0: float, y1: float) -> bool:
    center_y = image_center_y(image)
    if center_y is None:
        return False
    anchors = find_option_anchors(page, y0, y1)
    if len({option for option, _y in anchors}) < 4:
        return False
    return center_y - anchors[-1][1] > 180


def add_unique_image(images: list[dict], image: dict) -> None:
    if not any(existing.get('src') == image.get('src') for existing in images):
        images.append(image)


def build_shared_context_images(
    key: str,
    pages: dict[int, dict],
    assets_by_page: dict[int, dict],
    questions: list[dict],
    ranges_by_question: dict[str, list[tuple[int, float, float]]],
) -> tuple[dict[int, list[dict]], set[str]]:
    shared_by_qnum: dict[int, list[dict]] = {}
    shared_sources: set[str] = set()
    ranges_by_qnum = question_ranges_by_number(questions, ranges_by_question)
    for page_index, page in pages.items():
        page_images = (assets_by_page.get(page_index) or {}).get('images', [])
        if not page_images:
            continue
        for block in page.get('blocks', []):
            text = normalize(block.get('text', ''))
            match = SHARED_QUESTION_RE.search(text)
            if not match:
                continue
            start_q, end_q = int(match.group(1)), int(match.group(2))
            start_y = block_center_y(block)
            if text.strip().startswith('根據') and re.search(r'根據.*(資料|結果|圖)', text):
                context_images = [
                    dict(image, placement='context')
                    for image in page_images
                    if start_y - 260 <= (image_center_y(image) or 0) <= start_y + 8
                ]
            else:
                context_images = [
                    dict(image, placement='context')
                    for image in page_images
                    if (image_center_y(image) or 0) >= start_y - 8
                ]
            first_target_range = ranges_by_qnum.get(start_q, [])
            if first_target_range:
                first_page, first_y, _first_y1 = first_target_range[0]
                for extra_page_index in range(page_index + 1, first_page + 1):
                    extra_images = (assets_by_page.get(extra_page_index) or {}).get('images', [])
                    for image in extra_images:
                        center_y = image_center_y(image)
                        if center_y is None:
                            continue
                        if extra_page_index < first_page or center_y <= first_y - 8:
                            context_images.append(dict(image, placement='context'))
            for image in context_images:
                shared_sources.add(image['src'])
            for qnum in range(start_q, end_q + 1):
                for image in context_images:
                    shared_by_qnum.setdefault(qnum, []).append({
                        **image,
                        'alt': f'{key} 第 {page_index + 1} 頁第 {start_q}~{end_q} 題共用附圖',
                    })
    return shared_by_qnum, shared_sources


def question_text_blob(question: dict) -> str:
    combined = question.get('question', '')
    combined += ' '.join(question.get('options', {}).values())
    return combined


def question_needs_image(question: dict, has_nearby_assets: bool = False) -> bool:
    combined = question_text_blob(question)
    return bool(IMAGE_HINT_RE.search(combined)) or (has_nearby_assets and bool(CODE_HINT_RE.search(combined)))


def attach_exam_images(level: str, key: str, questions: list[dict]) -> None:
    assets_by_page = load_page_image_assets(level, key)
    pages = load_page_extract(level, key)
    if not pages:
        return
    ranges_by_question = build_question_ranges(questions, pages)
    shared_context_texts = build_shared_context_texts(pages, questions, ranges_by_question)
    shared_by_qnum, shared_sources = build_shared_context_images(
        key,
        pages,
        assets_by_page,
        questions,
        ranges_by_question,
    )

    attached = 0
    for question in questions:
        page_index = (question.get('source_ref') or {}).get('page_index')
        qnum = question_number(question)
        if qnum is not None:
            context = shared_context_texts.get(qnum)
            if context and context not in question.get('question', ''):
                question['context'] = context

        has_nearby_assets = (
            isinstance(page_index, int)
            and (
                bool((assets_by_page.get(page_index) or {}).get('images'))
                or bool((assets_by_page.get(page_index + 1) or {}).get('images'))
            )
        )
        if not question_needs_image(question, has_nearby_assets):
            continue

        selected: list[dict] = []
        for interval_page, y0, y1 in ranges_by_question.get(question['id'], []):
            page = pages.get(interval_page)
            page_images = (assets_by_page.get(interval_page) or {}).get('images', [])
            if not page or not page_images:
                continue
            for image in images_in_question_range(page_images, y0, y1):
                if image.get('src') in shared_sources:
                    continue
                if is_late_after_option_image_block(page, image, y0, y1):
                    continue
                add_unique_image(selected, classify_image_placement(page, image, y0, y1))

        if qnum is not None:
            for image in shared_by_qnum.get(qnum, []):
                add_unique_image(selected, image)

        if not selected and isinstance(page_index, int) and question_needs_image(question, has_nearby_assets):
            intervals = ranges_by_question.get(question['id'], [])
            if intervals:
                interval_page, y0, y1 = intervals[0]
                page = pages.get(interval_page)
                if page:
                    fallback = make_visual_gap_crop(level, key, interval_page, page, question['id'], y0, y1)
                    if fallback:
                        add_unique_image(selected, fallback)

        if selected:
            question['images'] = selected
            attached += 1

    if attached:
        print(f'  {key}: attached extracted images to {attached} questions')


def parse_exam_json(key: str, data_dir: Path) -> list[dict]:
    """Parse questions from exam JSON using table data."""
    with open(data_dir / 'extracted' / f'{key}.json', encoding='utf-8') as f:
        data = json.load(f)
    questions = []
    pending_answer: str | None = None
    pending_cell = ''
    pending_page_index: int | None = None

    def flush_pending() -> None:
        nonlocal pending_answer, pending_cell
        nonlocal pending_page_index
        if not pending_answer or not pending_cell.strip():
            pending_answer = None
            pending_cell = ''
            pending_page_index = None
            return
        qnum = len(questions) + 1
        q = parse_question_cell(pending_answer, pending_cell, qnum, key, pending_page_index)
        if q:
            questions.append(q)
        else:
            print(
                f"  WARN: {key} row {qnum} skipped "
                f"(answer={pending_answer!r}, cell={pending_cell[:40]!r})"
            )
        pending_answer = None
        pending_cell = ''
        pending_page_index = None

    for page in data['pages']:
        page_index = int(page.get('page', 1)) - 1
        for table in page.get('tables', []):
            for row in table:
                if not row or len(row) < 2:
                    continue
                cells = [str(cell or '').strip() for cell in row]
                # Skip header rows
                if any(cell in ('答案', '題號', '題目', '題 目') for cell in cells):
                    continue

                answer = None
                answer_index = -1
                for index, cell in enumerate(cells):
                    normalized = normalize(cell)
                    if re.match(r'^[A-D]$', normalized):
                        answer = normalized
                        answer_index = index
                        break

                text_cells = [
                    cell for index, cell in enumerate(cells)
                    if index != answer_index and cell and cell not in ('新',)
                ]
                cell = max(text_cells, key=len, default='').strip()

                if answer:
                    flush_pending()
                    pending_answer = answer
                    pending_cell = cell
                    pending_page_index = page_index
                elif pending_answer and cell:
                    pending_cell = f'{pending_cell}\n{cell}'.strip()
                else:
                    continue

    flush_pending()

    print(f"  {key}: {len(questions)} questions parsed")
    return questions


def parse_sample_json(data_dir: Path) -> list[dict]:
    """Parse sample exam from JSON — has different table format."""
    with open(data_dir / 'extracted' / 'sample.json', encoding='utf-8') as f:
        data = json.load(f)
    questions = []

    for page in data['pages']:
        page_index = int(page.get('page', 1)) - 1
        for table in page.get('tables', []):
            for row in table:
                if not row or len(row) < 4:
                    continue
                # Sample format: [qnum, '', '', answer, '', '', question_text, '']
                # or: ['1.', '', '', 'B', '', '', 'question...', '']
                # Find answer (A/B/C/D) and question text
                answer = None
                q_text_cell = None
                for cell in row:
                    s = normalize(str(cell or '').strip())
                    if re.match(r'^[ABCD]$', s) and answer is None:
                        answer = s
                    elif s and len(s) > 10 and '(A)' in s and answer is not None:
                        q_text_cell = s

                if answer and q_text_cell:
                    qnum = len(questions) + 1
                    q = parse_question_cell(answer, q_text_cell, qnum, 'sample', page_index)
                    if q:
                        questions.append(q)

    print(f"  sample: {len(questions)} questions parsed")
    return questions


def save_mock(filename: str, title: str, questions: list[dict], questions_dir: Path):
    mock = {
        'exam': title,
        'total': len(questions),
        'time_limit': '90分鐘',
        'passing_score': 60,
        'questions': questions,
    }
    path = questions_dir / filename
    path.write_text(json.dumps(mock, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Saved {path} ({len(questions)} questions)")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Parse exam questions from extracted JSON')
    parser.add_argument('--level', default='初級',
                        help='資料等級資料夾（預設: 初級）')
    args = parser.parse_args()

    data_dir = BASE / 'data' / args.level
    questions_dir = data_dir / 'questions'
    questions_dir.mkdir(exist_ok=True)

    exam_map = EXAM_PDFS_BY_LEVEL.get(args.level, {})
    titles = EXAM_TITLES_BY_LEVEL.get(args.level, {})
    for key in sorted(exam_map):
        if key == 'sample':
            qs = parse_sample_json(data_dir)
            attach_exam_images(args.level, key, qs)
            save_mock('sample_exam.json', titles.get(key, '考試樣題'), qs, questions_dir)
            continue
        questions = parse_exam_json(key, data_dir)
        attach_exam_images(args.level, key, questions)
        filename = f'mock_{key}.json'
        save_mock(filename, titles.get(key, f'{args.level} {key} 模擬考試'), questions, questions_dir)

    print("\nAll mock exams saved.")


if __name__ == '__main__':
    main()
