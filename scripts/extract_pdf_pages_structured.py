#!/usr/bin/env python3
"""Extract every PDF page with text, image/table positions, and cropped assets."""

import argparse
import ast
import json
import re
import shutil
from pathlib import Path
from typing import Any
from collections import Counter

import fitz  # PyMuPDF
import pdfplumber
from PIL import Image, ImageChops

BASE = Path('/home/james/projects/ipas-test')


def load_manifest(level: str) -> dict:
    path = BASE / 'data' / level / 'toc_manifest.json'
    if not path.exists():
        return {'subjects': []}
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def load_extra_pdf_maps() -> dict[str, dict[str, str]]:
    source = (BASE / 'scripts' / 'extract_pdfs.py').read_text(encoding='utf-8')
    module = ast.parse(source)
    result: dict[str, dict[str, str]] = {}
    for node in module.body:
        if (
            isinstance(node, ast.AnnAssign)
            and getattr(node.target, 'id', None) in {'EXAM_PDFS_BY_LEVEL', 'REFERENCE_PDFS_BY_LEVEL'}
        ):
            current = ast.literal_eval(node.value)
            for level, pdfs in current.items():
                result.setdefault(level, {}).update(pdfs)
    if not result:
        raise RuntimeError('PDF maps not found in scripts/extract_pdfs.py')
    return result


def pdf_map(level: str) -> dict[str, str]:
    result: dict[str, str] = {}
    manifest = load_manifest(level)
    for subject in manifest.get('subjects', []):
        result[subject['key']] = subject['pdf']
    result.update(load_extra_pdf_maps().get(level, {}))
    return result


def clean_text(text: str) -> str:
    text = (
        text
        .replace('\uf097', '• ')
        .replace('\uf09f', '• ')
        .replace('\uf077', '◦ ')
        .replace('\uf0a1', '○ ')
    )
    text = re.sub(r'[\ue000-\uf8ff]', '', text)
    return re.sub(r'[ \t]+', ' ', text).strip()


def rect_to_list(rect: fitz.Rect | tuple[float, float, float, float]) -> list[float]:
    if isinstance(rect, fitz.Rect):
        values = [rect.x0, rect.y0, rect.x1, rect.y1]
    else:
        values = list(rect)
    return [round(float(v), 2) for v in values]


def safe_name(value: str) -> str:
    return re.sub(r'[^A-Za-z0-9_.-]+', '_', value)


def crop_page_region(
    page: fitz.Page,
    bbox: tuple[float, float, float, float] | fitz.Rect,
    out_path: Path,
    scale: float,
    trim_whitespace: bool = False,
) -> list[float] | None:
    rect = fitz.Rect(bbox) & page.rect
    if rect.is_empty or rect.width < 2 or rect.height < 2:
        return None
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=rect, alpha=False)
    pix.save(str(out_path))
    if not trim_whitespace:
        return rect_to_list(rect)

    trimmed_rect = trim_image_whitespace(out_path, rect, scale)
    return rect_to_list(trimmed_rect)


def trim_image_whitespace(path: Path, source_rect: fitz.Rect, scale: float) -> fitz.Rect:
    """Trim mostly-white margins from a rendered crop and map the crop back to PDF coords."""
    image = Image.open(path).convert('RGB')
    background = Image.new('RGB', image.size, (255, 255, 255))
    diff = ImageChops.difference(image, background).convert('L')
    mask = diff.point(lambda value: 255 if value > 10 else 0)
    bbox = mask.getbbox()
    if not bbox:
        return source_rect

    pad = 8
    left = max(0, bbox[0] - pad)
    upper = max(0, bbox[1] - pad)
    right = min(image.width, bbox[2] + pad)
    lower = min(image.height, bbox[3] + pad)
    if left == 0 and upper == 0 and right == image.width and lower == image.height:
        return source_rect

    image.crop((left, upper, right, lower)).save(path)
    return fitz.Rect(
        source_rect.x0 + left / scale,
        source_rect.y0 + upper / scale,
        source_rect.x0 + right / scale,
        source_rect.y0 + lower / scale,
    )


def render_clean_page(
    page: fitz.Page,
    out_path: Path,
    scale: float,
    watermark_bboxes: set[tuple[float, float, float, float]],
) -> dict:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    pix.save(str(out_path))
    return {
        'id': 'page',
        'bbox': rect_to_list(page.rect),
        'path': f'../assets/page_{page.number:03d}/{out_path.name}',
    }


def extract_blocks(page: fitz.Page) -> list[dict[str, Any]]:
    blocks = []
    for block in page.get_text('dict').get('blocks', []):
        bbox = block.get('bbox')
        if block.get('type') != 0 or not bbox:
            continue
        lines = []
        for line in block.get('lines', []):
            spans = line.get('spans', [])
            line_text = clean_text(''.join(span.get('text', '') for span in spans))
            if line_text:
                lines.append(line_text)
        text = '\n'.join(lines).strip()
        if text:
            blocks.append({'type': 'text', 'bbox': rect_to_list(tuple(bbox)), 'text': text})
    return blocks


def image_bbox_key(rect: fitz.Rect) -> tuple[float, float, float, float]:
    return tuple(rect_to_list(rect))


def detect_watermark_bboxes(doc: fitz.Document) -> set[tuple[float, float, float, float]]:
    """Detect repeated centered raster images that behave like page watermarks."""
    counts: Counter[tuple[float, float, float, float]] = Counter()
    page_hits: dict[tuple[float, float, float, float], set[int]] = {}
    page_size: dict[tuple[float, float, float, float], tuple[float, float]] = {}

    for page_index, page in enumerate(doc):
        for image in page.get_images(full=True):
            xref = image[0]
            for rect in page.get_image_rects(xref):
                key = image_bbox_key(rect)
                if key in page_hits and page_index in page_hits[key]:
                    continue
                counts[key] += 1
                page_hits.setdefault(key, set()).add(page_index)
                page_size[key] = (page.rect.width, page.rect.height)

    watermarks = set()
    min_pages = max(3, int(len(doc) * 0.5))
    for key, count in counts.items():
        x0, y0, x1, y1 = key
        page_width, page_height = page_size[key]
        width = x1 - x0
        height = y1 - y0
        center_x = (x0 + x1) / 2
        center_y = (y0 + y1) / 2
        is_centered = (
            page_width * 0.2 <= center_x <= page_width * 0.8
            and page_height * 0.25 <= center_y <= page_height * 0.75
        )
        is_large = width >= page_width * 0.35 and height >= page_height * 0.12
        if count >= min_pages and is_centered and is_large:
            watermarks.add(key)
    return watermarks


def is_watermark_geometry(page: fitz.Page, rect: fitz.Rect) -> bool:
    """Catch cover/appendix watermark images that do not repeat often enough."""
    if (
        rect.x0 < -1
        or rect.y0 < -1
        or rect.x1 > page.rect.width + 1
        or rect.y1 > page.rect.height + 1
    ):
        return True

    width = rect.width
    height = rect.height
    center_x = (rect.x0 + rect.x1) / 2
    center_y = (rect.y0 + rect.y1) / 2
    is_centered = (
        page.rect.width * 0.2 <= center_x <= page.rect.width * 0.8
        and page.rect.height * 0.25 <= center_y <= page.rect.height * 0.75
    )
    return (
        is_centered
        and width >= page.rect.width * 0.7
        and height >= page.rect.height * 0.2
    )


def is_decorative_image(page: fitz.Page, rect: fitz.Rect) -> bool:
    """Skip title ornaments, tiny icons, and other low-value decorative crops."""
    area = rect.width * rect.height
    page_area = page.rect.width * page.rect.height
    if rect.width < 90 or rect.height < 45:
        return True
    if area < page_area * 0.018 and rect.height < 90:
        return True
    return False


def extract_images(
    page: fitz.Page,
    page_assets_dir: Path,
    rel_prefix: str,
    scale: float,
    watermark_bboxes: set[tuple[float, float, float, float]],
) -> list[dict]:
    images = []
    seen: set[tuple[float, float, float, float]] = set()
    for image_index, image in enumerate(page.get_images(full=True), start=1):
        xref = image[0]
        for rect_index, rect in enumerate(page.get_image_rects(xref), start=1):
            bbox_tuple = image_bbox_key(rect)
            if bbox_tuple in watermark_bboxes or is_watermark_geometry(page, rect):
                continue
            if is_decorative_image(page, rect):
                continue
            if bbox_tuple in seen:
                continue
            seen.add(bbox_tuple)
            asset_name = f'image_{image_index:02d}_{rect_index:02d}.png'
            out_path = page_assets_dir / asset_name
            cropped_bbox = crop_page_region(page, rect, out_path, scale)
            if not cropped_bbox:
                continue
            images.append({
                'id': f'image_{image_index:02d}_{rect_index:02d}',
                'xref': xref,
                'bbox': cropped_bbox,
                'path': f'{rel_prefix}/{asset_name}',
            })
    return images


def table_text_chars(rows: list[list[Any]]) -> int:
    total = 0
    for row in rows:
        for cell in row:
            if cell:
                total += len(str(cell).strip())
    return total


def extract_tables(
    plumber_page: pdfplumber.page.Page,
    fitz_page: fitz.Page,
    page_assets_dir: Path,
    rel_prefix: str,
    scale: float,
) -> list[dict]:
    tables = []
    try:
        found = plumber_page.find_tables()
    except Exception:
        found = []
    for table_index, table in enumerate(found, start=1):
        bbox = tuple(float(v) for v in table.bbox)
        try:
            rows = table.extract() or []
        except Exception:
            rows = []
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        if table_text_chars(rows) < 4 and width * height < 30000:
            continue

        asset_name = f'table_{table_index:02d}.png'
        out_path = page_assets_dir / asset_name
        padded_bbox = (
            max(0.0, bbox[0] - 24.0),
            max(0.0, bbox[1] - 28.0),
            min(float(fitz_page.rect.width), bbox[2] + 24.0),
            min(float(fitz_page.rect.height), bbox[3] + 14.0),
        )
        cropped_bbox = crop_page_region(
            fitz_page, padded_bbox, out_path, scale, trim_whitespace=True
        )
        tables.append({
            'id': f'table_{table_index:02d}',
            'bbox': cropped_bbox or rect_to_list(bbox),
            'path': f'{rel_prefix}/{asset_name}' if cropped_bbox else None,
            'rows': rows,
        })
    return tables


def page_markers(images: list[dict], tables: list[dict]) -> list[dict]:
    markers = []
    for item in images:
        markers.append({'type': 'image', 'id': item['id'], 'bbox': item['bbox']})
    for item in tables:
        markers.append({'type': 'table', 'id': item['id'], 'bbox': item['bbox']})
    return sorted(markers, key=lambda item: (item['bbox'][1], item['bbox'][0]))


def write_page_markdown(page_data: dict, out_path: Path) -> None:
    markers = page_data['markers']
    lines = [
        f'# {page_data["key"]} page {page_data["page_number"]}',
        '',
        f'- PDF label: {page_data.get("page_label") or "-"}',
        f'- Size: {page_data["width"]} x {page_data["height"]}',
        '',
        '## Markers',
        '',
    ]
    if markers:
        for marker in markers:
            lines.append(f'- [{marker["type"]}:{marker["id"]}] bbox={marker["bbox"]}')
    else:
        lines.append('- none')
    lines.extend(['', '## Text', '', page_data['text']])
    out_path.write_text('\n'.join(lines), encoding='utf-8')


def extract_pdf(level: str, key: str, pdf_name: str, scale: float, force: bool) -> dict:
    pdf_path = BASE / 'data' / level / 'pdfs' / pdf_name
    out_dir = BASE / 'data' / level / 'page_extract' / key
    pages_dir = out_dir / 'pages'
    assets_dir = out_dir / 'assets'
    pages_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(pdf_path))
    watermark_bboxes = detect_watermark_bboxes(doc)
    if watermark_bboxes:
        print(f'  {key}: removing {len(watermark_bboxes)} repeated watermark image bbox(es)')
    page_summaries = []
    with pdfplumber.open(str(pdf_path)) as plumber_pdf:
        for idx, page in enumerate(doc):
            page_json = pages_dir / f'page_{idx:03d}.json'
            if page_json.exists() and not force:
                with page_json.open(encoding='utf-8') as f:
                    cached = json.load(f)
                page_summaries.append(cached['summary'])
                continue

            page_assets_dir = assets_dir / f'page_{idx:03d}'
            if force and page_assets_dir.exists():
                shutil.rmtree(page_assets_dir)
            rel_prefix = f'../assets/page_{idx:03d}'
            text = clean_text(page.get_text('text') or '')
            blocks = extract_blocks(page)
            page_image = render_clean_page(
                page, page_assets_dir / 'page.png', scale, watermark_bboxes
            )
            page_image['path'] = f'{rel_prefix}/page.png'
            images = extract_images(page, page_assets_dir, rel_prefix, scale, watermark_bboxes)
            tables = extract_tables(
                plumber_pdf.pages[idx], page, page_assets_dir, rel_prefix, scale
            )
            data = {
                'key': key,
                'pdf': pdf_name,
                'page_index': idx,
                'page_number': idx + 1,
                'page_label': next(iter(re.findall(r'\b\d+-\d+\b', page.get_text() or '')), ''),
                'width': round(page.rect.width, 2),
                'height': round(page.rect.height, 2),
                'text': text,
                'blocks': blocks,
                'page_image': page_image,
                'images': images,
                'tables': tables,
                'markers': page_markers(images, tables),
            }
            data['summary'] = {
                'page_index': idx,
                'page_number': idx + 1,
                'page_label': data['page_label'],
                'text_chars': len(text),
                'text_blocks': len(blocks),
                'images': len(images),
                'tables': len(tables),
            }
            page_json.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            write_page_markdown(data, pages_dir / f'page_{idx:03d}.md')
            page_summaries.append(data['summary'])
    doc.close()

    summary = {
        'key': key,
        'pdf': pdf_name,
        'pages': len(page_summaries),
        'text_chars': sum(page['text_chars'] for page in page_summaries),
        'images': sum(page['images'] for page in page_summaries),
        'tables': sum(page['tables'] for page in page_summaries),
        'page_summaries': page_summaries,
    }
    (out_dir / 'summary.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    print(
        f'{key}: {summary["pages"]} pages, {summary["text_chars"]} chars, '
        f'{summary["images"]} images, {summary["tables"]} tables'
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--level', default='初級', help='資料等級資料夾（預設: 初級）')
    parser.add_argument('--key', help='只處理指定 PDF key，如 guide1/exam1/sample')
    parser.add_argument('--all', action='store_true', help='處理所有 manifest/exam PDF')
    parser.add_argument('--scale', type=float, default=2.0, help='crop render scale')
    parser.add_argument('--force', action='store_true', help='overwrite existing page JSON/assets')
    args = parser.parse_args()

    pdfs = pdf_map(args.level)
    if not args.key and not args.all:
        parser.error('Specify --key KEY or --all')
    keys = sorted(pdfs) if args.all else [args.key]
    run_summary = {}
    for key in keys:
        if key not in pdfs:
            print(f'[WARN] unknown key: {key}')
            continue
        run_summary[key] = extract_pdf(args.level, key, pdfs[key], args.scale, args.force)

    out_path = BASE / 'data' / args.level / 'page_extract' / 'summary.json'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(run_summary, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
