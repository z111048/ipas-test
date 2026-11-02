#!/usr/bin/env python3
"""Export cleaned PDF guide outlines and split content for static frontend imports."""

import hashlib
import json
import re
import shutil
import sys
import tempfile
import unicodedata
import uuid
from html import escape
from pathlib import Path
from typing import Any
from asset_paths import page_asset_url
from cjk_parentheses import normalize_block_parentheses, normalize_cjk_parentheses
from guide_publication_overlays import (
    HYPOTHESIS_AGGREGATE_ROUTE,
    HYPOTHESIS_TABLE_OVERLAY_ID,
    apply_publication_block_overlays,
    apply_publication_heading_overlays,
    apply_publication_markdown_overlays,
)
from track_a_ocr_repairs import (
    EXERCISE_PROVENANCE_PAGES,
    OCR_VISUAL_FALLBACKS,
    SEMANTIC_VISUAL_PAGES,
    SIGNATURE_REGISTRY_PATH,
    PUBLICATION_VISUAL_ALTS,
    VISUAL_INVENTORY_BY_PAGE,
    apply_formula_repairs,
    apply_markdown_repairs,
    apply_markdown_structure_repairs,
    apply_text_repairs,
    apply_track_a_block_repairs,
    audit_generated_track_a,
)

BASE = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _track_a_signature_registry() -> dict[str, Any]:
    registry = load_json(SIGNATURE_REGISTRY_PATH)
    if registry.get('schema') != 'track-a-ocr-signatures-v2':
        raise ValueError('unsupported Track-A signature registry schema')
    return registry


def _visual_signature(level: str, key: str, page_index: int) -> dict[str, Any]:
    inventory = VISUAL_INVENTORY_BY_PAGE[(level, key, page_index)]
    expected = _track_a_signature_registry()['visuals'][inventory['id']]
    location = (expected.get('level'), expected.get('key'), expected.get('pageIndex'))
    if location != (level, key, page_index) or expected.get('node') != inventory['node']:
        raise ValueError(f"{inventory['id']}: visual signature location mismatch")
    return expected


def _visual_source_path(level: str, key: str, page_index: int) -> Path:
    """Resolve the one reviewed source file for an exact visual signature."""
    visual_key = (level, key, page_index)
    expected = _visual_signature(level, key, page_index)
    expected_name = Path(str(expected['src'])).name
    fallback = OCR_VISUAL_FALLBACKS.get(visual_key)
    if fallback:
        source = Path(fallback['source'])
        if str(fallback['filename']) != expected_name:
            raise ValueError(f"{expected['src']}: OCR fallback filename differs from registry")
    else:
        extract_path = BASE / 'data' / level / 'page_extract' / key / 'pages' / f'page_{page_index:03d}.json'
        if not extract_path.is_file():
            raise ValueError(f'{level}/{key}/page_{page_index:03d}: source extraction missing')
        extracted = load_json(extract_path)
        candidates = [
            (extract_path.parent / str(image.get('path'))).resolve()
            for image in extracted.get('images') or []
            if image.get('path') and Path(str(image['path'])).name == expected_name
        ]
        if len(candidates) != 1:
            raise ValueError(
                f'{level}/{key}/page_{page_index:03d}: exact source visual matched '
                f'{len(candidates)}, expected 1'
            )
        source = candidates[0]
    if not source.is_file():
        raise ValueError(f'{level}/{key}/page_{page_index:03d}: exact source visual file missing')
    if _sha256_file(source) != expected['assetSha256']:
        raise ValueError(f'{level}/{key}/page_{page_index:03d}: exact source visual SHA-256 mismatch')
    return source


def _stage_track_a_visual_assets(levels: list[str], staged_public_root: Path) -> list[Path]:
    """Copy reviewed assets into an isolated overlay; never touch live public."""
    relative_paths: list[Path] = []
    for (level, key, page_index), inventory in VISUAL_INVENTORY_BY_PAGE.items():
        if level not in levels:
            continue
        expected = _track_a_signature_registry()['visuals'][inventory['id']]
        relative = Path(str(expected['src']).lstrip('/'))
        destination = staged_public_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(_visual_source_path(level, key, page_index), destination)
        if _sha256_file(destination) != expected['assetSha256']:
            raise ValueError(f"{inventory['id']}: staged visual SHA-256 mismatch")
        relative_paths.append(relative)
    return relative_paths


def _guide_level(guide: dict) -> str:
    """Read a guide's level, including older outline files without ``level``."""
    level = str(guide.get('level') or '')
    if level:
        return level
    key = str(guide.get('key') or '')
    return key.split('-', 1)[0] if '-' in key else ''


def _validate_export(data: dict[str, Any], content_dir: Path, asset_root: Path | None = None) -> None:
    """Validate the complete merged export before it can replace live data."""
    guides = data.get('guides')
    if not isinstance(guides, dict):
        raise ValueError('guideOutlines export must contain a guides object')
    for subject_id, guide in guides.items():
        if guide.get('subjectId') != subject_id:
            raise ValueError(f'{subject_id} subjectId mismatch')
        validate_guide(guide, content_dir, asset_root=asset_root)


def _commit_staged_outputs(
    staged_content_dir: Path,
    content_dir: Path,
    staged_outlines_path: Path,
    outlines_path: Path,
    *,
    staged_public_root: Path | None = None,
    public_root: Path | None = None,
    asset_relative_paths: list[Path] | None = None,
) -> None:
    """Replace content, outlines, and reviewed assets as one rollback unit."""
    token = uuid.uuid4().hex
    content_backup = content_dir.with_name(f'.{content_dir.name}.backup-{token}')
    outlines_backup = outlines_path.with_name(f'.{outlines_path.name}.backup-{token}')
    assets = list(asset_relative_paths or [])
    asset_backup_root: Path | None = None
    changed_assets: list[tuple[Path, Path, bool]] = []
    installed_content = False
    installed_outlines = False
    backed_up_content = False
    backed_up_outlines = False
    try:
        if assets:
            if staged_public_root is None or public_root is None:
                raise ValueError('asset transaction requires staged_public_root and public_root')
            missing = [relative for relative in assets if not (staged_public_root / relative).is_file()]
            if missing:
                raise FileNotFoundError(f'missing staged publication assets: {missing}')
            public_root.mkdir(parents=True, exist_ok=True)
            asset_backup_root = public_root / f'.track-a-assets.backup-{token}'
            asset_backup_root.mkdir()
            for relative in assets:
                staged_asset = staged_public_root / relative
                live_asset = public_root / relative
                if live_asset.is_file() and _sha256_file(live_asset) == _sha256_file(staged_asset):
                    continue
                existed = live_asset.exists()
                backup_asset = asset_backup_root / relative
                changed_assets.append((live_asset, backup_asset, existed))
                if existed:
                    backup_asset.parent.mkdir(parents=True, exist_ok=True)
                    live_asset.rename(backup_asset)
                live_asset.parent.mkdir(parents=True, exist_ok=True)
                staged_asset.rename(live_asset)

        if content_dir.exists():
            content_dir.rename(content_backup)
            backed_up_content = True
        staged_content_dir.rename(content_dir)
        installed_content = True

        if outlines_path.exists():
            outlines_path.rename(outlines_backup)
            backed_up_outlines = True
        staged_outlines_path.rename(outlines_path)
        installed_outlines = True
    except Exception:
        if installed_outlines and outlines_path.exists():
            outlines_path.unlink()
        if backed_up_outlines and outlines_backup.exists():
            outlines_backup.rename(outlines_path)
        if installed_content and content_dir.exists():
            shutil.rmtree(content_dir)
        if backed_up_content and content_backup.exists():
            content_backup.rename(content_dir)
        for live_asset, backup_asset, existed in reversed(changed_assets):
            if live_asset.exists():
                live_asset.unlink()
            if existed and backup_asset.exists():
                live_asset.parent.mkdir(parents=True, exist_ok=True)
                backup_asset.rename(live_asset)
        raise
    else:
        if content_backup.exists():
            shutil.rmtree(content_backup)
        if outlines_backup.exists():
            outlines_backup.unlink()
    finally:
        if asset_backup_root and asset_backup_root.exists():
            shutil.rmtree(asset_backup_root)
        if staged_public_root and staged_public_root.exists():
            shutil.rmtree(staged_public_root)


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


def exercise_block_key(block: dict) -> tuple[str, int] | None:
    match = re.match(r'^\s*(\d+)\.', str(block.get('text') or ''))
    if block.get('type') not in ('question', 'answer') or not match:
        return None
    return str(block['type']), int(match.group(1))


def refresh_prebuilt_exercise_text(
    blocks: list[dict],
    level: str,
    key: str,
    node: str,
    title: str,
    start_page: int,
    end_page: int,
) -> list[dict]:
    """Overlay current cleaned exercise text onto stale guide-tree blocks.

    Guide-tree artifacts are intentionally reviewable caches and can lag
    source/errata overlays.  Only question/answer text is refreshed here; the
    reviewed hierarchy and every non-exercise block remain guide-tree-owned.
    """
    if (level, key, node) not in EXERCISE_PROVENANCE_PAGES:
        return blocks
    current = post_process_guide_blocks(node, title, page_blocks(level, key, start_page, end_page))
    current_by_key = {
        identifier: block
        for block in current
        if (identifier := exercise_block_key(block)) is not None
    }
    result = [dict(block) for block in blocks]
    for block in result:
        identifier = exercise_block_key(block)
        if identifier is None:
            continue
        source = current_by_key.get(identifier)
        if source is None:
            raise ValueError(f'{level}/{key}/{node}: current exercise block {identifier} missing')
        block['text'] = source.get('text') or ''
    return result


TRACK_A_BIBLIOGRAPHY_PAGES: dict[tuple[str, str, str], int] = {
    ('初級', 'guide1', 's1c4'): 69,
    ('初級', 'guide2', 's2c3'): 60,
}


def inject_structured_bibliography(
    blocks: list[dict],
    level: str,
    key: str,
    node: str,
) -> list[dict]:
    """Recover the two appendices swallowed by prebuilt exercise blocks."""
    page_index = TRACK_A_BIBLIOGRAPHY_PAGES.get((level, key, node))
    if page_index is None:
        return blocks
    result = [dict(block) for block in blocks]
    for block in result:
        if block.get('type') != 'answer':
            continue
        text = str(block.get('text') or '')
        block['text'] = re.sub(r'\s*附件\s*本學習指引參考書目\s*$', '', text).rstrip()

    has_heading = any(block.get('type') == 'heading' and '參考書目' in str(block.get('title') or '') for block in result)
    has_table = any(
        block.get('type') == 'table'
        and block.get('pageIndex') == page_index
        and len(block.get('rows') or []) >= 10
        for block in result
    )
    if has_heading and has_table:
        return result

    appendix_blocks = page_blocks(level, key, page_index + 1, page_index + 1)
    if not has_heading:
        heading = next(
            (block for block in appendix_blocks if block.get('type') == 'heading' and '參考書目' in str(block.get('title') or '')),
            None,
        )
        if heading is None:
            source = next(
                (block for block in appendix_blocks if block.get('type') == 'paragraph' and '參考書目' in str(block.get('text') or '')),
                None,
            )
            if source is not None:
                heading = {
                    'type': 'heading',
                    'depth': 3,
                    'title': str(source.get('text') or '').strip(),
                    'anchor': normalize_heading_key(str(source.get('text') or '')),
                    'pageIndex': source.get('pageIndex'),
                    'bbox': source.get('bbox'),
                }
        if heading is None:
            raise ValueError(f'{level}/{key}/{node}: bibliography heading not recoverable')
        result.append(dict(heading))
    if not has_table:
        table = next(
            (block for block in appendix_blocks if block.get('type') == 'table' and len(block.get('rows') or []) >= 10),
            None,
        )
        if table is None:
            raise ValueError(f'{level}/{key}/{node}: bibliography table not recoverable')
        result.append(dict(table))
    return reset_block_ids(result)


# Aggregate PDF-chapter routes print the same pages as their leaf sections, so
# they carry the reviewed source figures too (round 3, 2026-11-02).  The copy is
# tagged with trackAMirrorRepairId and is not counted by the Track A inventory,
# which keeps owning exactly the leaf block.
SEMANTIC_VISUAL_MIRROR_ROUTES: dict[str, str] = {
    's1c4': 's1pdf-c3',
    'mid-s2c1': 'mid-s2pdf-c3',
    'mid-s2c9': 'mid-s2pdf-c5',
    'mid-s3c5': 'mid-s3pdf-c4',
    'mid-s3c8': 'mid-s3pdf-c5',
    'mid-s3c9': 'mid-s3pdf-c5',
}


def inject_semantic_source_images(
    blocks: list[dict],
    level: str,
    key: str,
    node: str,
    start_page: int,
    end_page: int,
) -> list[dict]:
    """Inject exact PDF/OCR source figures into both export paths.

    `--use-guide-tree` supplies prebuilt blocks and therefore bypasses
    `page_blocks()`.  Re-reading only the 17 reviewed visual pages here keeps
    both paths equivalent.  Asset copies are additive publication inputs; the
    generated-content transaction validates every resulting `src` via the
    standalone Track-A gate.
    """
    semantic_pages = {
        page_index
        for repair_level, repair_key, page_index in SEMANTIC_VISUAL_PAGES
        if (repair_level, repair_key) == (level, key)
        and start_page - 1 <= page_index <= end_page - 1
    }
    # Legacy page assembly may already have injected these into aggregate
    # nodes. Rebuild reviewed source images from the explicit route registry so
    # only the intended leaf receives exactly one block per inventory item.
    result = [
        dict(block) for block in blocks
        if not (block.get('type') == 'source_image' and block.get('pageIndex') in semantic_pages)
    ]
    for page_number in range(start_page, end_page + 1):
        page_index = page_number - 1
        visual_key = (level, key, page_index)
        inventory = VISUAL_INVENTORY_BY_PAGE.get(visual_key)
        if inventory is None:
            continue
        mirror = inventory['node'] != node
        if mirror and SEMANTIC_VISUAL_MIRROR_ROUTES.get(inventory['node']) != node:
            continue
        page_path = BASE / 'data' / level / 'page_clean' / key / 'pages' / f'page_{page_index:03d}.json'
        if not page_path.is_file():
            raise ValueError(f"{inventory['id']}: cleaned source page missing")
        items = positioned_page_items(level, key, page_index, load_json(page_path))
        source_items = [item for item in items if item.get('type') == 'source_image']
        if len(source_items) != 1:
            raise ValueError(f"{inventory['id']}: source-image block matched {len(source_items)}, expected 1")
        item = source_items[0]
        expected = _visual_signature(level, key, page_index)
        if item.get('src') != expected['src'] or item.get('alt') != expected['alt']:
            raise ValueError(f"{inventory['id']}: source-image src/alt differs from committed signature")
        image_block = {
            'type': 'source_image',
            'depth': 3,
            'src': item.get('src'),
            # 簽章驗完來源忠實度之後，才套 publication 層的圖說覆寫
            'alt': PUBLICATION_VISUAL_ALTS.get(inventory['id'], item.get('alt')),
            'pageIndex': page_index,
            'sourcePageIndexes': [page_index],
            'bbox': item.get('bbox'),
        }
        if mirror:
            image_block['trackAMirrorRepairId'] = inventory['id']
        image_y = float((item.get('bbox') or [0, 0])[1])
        insert_at = len(result)
        for index, block in enumerate(result):
            block_page = block.get('pageIndex')
            block_bbox = block.get('bbox') or []
            block_y = float(block_bbox[1]) if len(block_bbox) == 4 else 0.0
            if isinstance(block_page, int) and (
                block_page > page_index
                or (block_page == page_index and block_y > image_y)
            ):
                insert_at = index
                break
        result.insert(insert_at, image_block)
    return reset_block_ids(result)


def normalize_heading_key(text: str) -> str:
    """比對 OCR 標題用的正規化鍵：去空白、統一全半形。"""
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', text)).strip()


def ocr_page_heading_keys(level: str, key: str, page_index: int) -> set[str]:
    """單頁的 OCR 標題（正規化鍵）。pages_cache 不存在時回空集合。"""
    return set(ocr_heading_levels(level, key, page_index + 1, page_index + 1))


def ocr_heading_levels(level: str, key: str, start_page: int, end_page: int) -> dict[str, int]:
    """從 pages_cache 取 OCR 已判定的標題 → {正規化標題: markdown 層級}。

    只拿來救「被表格 bbox 吃掉的整行文字」（見 positioned_page_items），
    **不拿來判定標題層級**。量過：OCR 的標題標記在這份語料上約半數是雜訊
    （`• 分布式詞嵌入`、`○ 應用示例：`、重複三次的 `處理機制：`、
    斷句的 `響包括：`），全語料套用會讓 25 章的章節導覽變差，得不償失。
    標題判定仍以 markdown_heading_for_line 的編號式 regex 為準。

    pages_cache 是 gitignored，不存在時回空 dict——行為與舊版完全相同。
    """
    cache_dir = BASE / 'data' / level / 'pages_cache' / key
    if not cache_dir.is_dir():
        return {}
    found: dict[str, int] = {}
    for page_number in range(start_page, end_page + 1):
        page_path = cache_dir / f'page_{page_number - 1:03d}.json'
        if not page_path.exists():
            continue
        for heading in load_json(page_path).get('headings') or []:
            title = str(heading.get('title') or '').strip()
            depth = heading.get('level')
            if not title or not isinstance(depth, int) or not 2 <= depth <= 6:
                continue
            # 練習題答案（「8. $\underline{Ans (C)}$」）被 OCR 標成 heading，
            # 它們不是章節標題；長句也不是。
            if len(title) > 40 or 'Ans' in title or '$' in title:
                continue
            found.setdefault(normalize_heading_key(title), depth)
    return found


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


def _compact_nfkc(value: str) -> str:
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', value or ''))


def is_line_outside_ocr_table(block: dict, table: dict) -> bool:
    """Keep a body line that sticks out of an OCR-rows table's bbox.

    The PDF-text table detector often included the caption line (「常見的統計
    方法可做以下分類：」, 「○ 對立假設（H₁）…三種形式：」, 「舉例示意：」…) as
    the table's first row, so the overlap filter's deletion was harmless.  OCR
    rows come from the table image and never contain that caption, so after
    the OCR merge the same filter silently deleted it (2026-11-01 rebuild:
    初級 1 line, 中級 7 lines).  Only a block that begins above the table's
    top edge or ends below its bottom edge, and whose text is absent from the
    OCR cells, is kept (measured 2026-11-01: 13 top + 5 bottom lines, all
    verified as body text against page images).
    """
    if table.get('rows_source') != 'guide_ocr':
        return False
    bbox = block.get('bbox') or []
    table_bbox = table.get('bbox') or []
    if len(bbox) != 4 or len(table_bbox) != 4:
        return False
    # Above the top edge (caption/lead-in) or running past the bottom edge
    # (first line of the next paragraph, e.g. 中級 guide2 page_039
    # 「舉例來說，若要檢驗某食品…適用雙尾」 left only 「檢定；若想…」).
    if not (bbox[1] < table_bbox[1] - 1 or bbox[3] > table_bbox[3] + 1):
        return False
    text = _compact_nfkc(block.get('text') or '')
    cells = _compact_nfkc(''.join(
        str(cell or '') for row in table.get('rows') or [] for cell in row
    ))
    return bool(text) and text not in cells


def recover_header_row(table: dict, blocks: list[dict]) -> list[str] | None:
    # OCR table rows (merge_guide_ocr.py) are read from the table image and
    # already contain the printed header.  Text-layer header recovery exists
    # for PDF-text tables whose header row came out empty.  Applying it to an
    # OCR table whose nested sub-table widened it to 4 columns replaced the
    # real header 「名稱／說明」 with the first body line 「接受域」 (初級
    # guide1 page_index 32, 2026-11-01 rebuild).  Measured over every
    # page_extract table: this was the only guide table the rule touched.
    if table.get('rows_source') == 'guide_ocr':
        return None
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


def merge_text_metadata(previous: dict, current: dict) -> None:
    previous.setdefault('first_x', previous.get('x'))
    previous.setdefault('line_xs', [previous.get('x')])
    previous.setdefault('body_left', previous.get('x'))
    current_x = current.get('x')
    if current_x is not None:
        previous['line_xs'] = [x for x in previous.get('line_xs', []) if x is not None] + [current_x]
    current_body_left = current.get('body_left')
    if previous.get('body_left') is None:
        previous['body_left'] = current_body_left
    elif current_body_left is not None:
        previous['body_left'] = min(previous['body_left'], current_body_left)


def merge_text_items(items: list[dict]) -> list[dict]:
    merged: list[dict] = []
    for item in items:
        if item.get('type') == 'text':
            item = dict(item)
            item.setdefault('first_x', item.get('x'))
            item.setdefault('line_xs', [item.get('x')])
        if merged and items_form_numbered_heading(merged[-1], item):
            merged[-1]['text'] = f'{merged[-1]["text"]} {item["text"]}'
            merge_text_metadata(merged[-1], item)
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
            merge_text_metadata(merged[-1], item)
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
            merge_text_metadata(merged[-1], item)
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

    lines = ['<table class="table-soft text-sm table-auto">', '<thead>', '<tr>']
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


HYPOTHESIS_TITLE = '假說檢定名詞介紹：'
HTML_TABLE = re.compile(r'<table\b[^>]*>.*?</table>', re.S)


def _html_header_cells(table_html: str) -> list[str]:
    head = re.search(r'<thead>(.*?)</thead>', table_html, re.S)
    cells = re.findall(r'<th>(.*?)</th>', head.group(1), re.S) if head else []
    return [re.sub(r'<[^>]+>', '', cell).strip() for cell in cells]


def sync_hypothesis_markdown_tables(
    level: str, key: str, node: str, markdown: str, blocks: list[dict],
) -> str:
    """Mirror the s1c2 hypothesis-table block overlay on the Markdown surface.

    `content` is still read by 概念圖卡 and the export flow, so it must not keep
    the OCR shape the block overlay removed (4-column table, 「檢定 (test)」 ×5,
    and the PDF-text duplicate of the Type I/II sub-table).  Replaces exactly
    the three tables that follow the title with the two published tables.
    """
    routes = {('初級', 'guide1', 's1c2'), HYPOTHESIS_AGGREGATE_ROUTE}
    if (level, key, node) not in routes:
        return markdown
    targets = [block for block in blocks if block.get('publicationOverlayId') == HYPOTHESIS_TABLE_OVERLAY_ID]
    if len(targets) != 2:
        raise ValueError(f'{level}/{key}/{node}: expected 2 overlaid hypothesis tables, got {len(targets)}')
    rendered = [table_rows_to_html(block['rows']) for block in targets]
    if all(markdown.count(html) == 1 for html in rendered):
        return markdown
    if markdown.count(HYPOTHESIS_TITLE) != 1:
        raise ValueError(f'{level}/{key}/{node}: hypothesis title occurs {markdown.count(HYPOTHESIS_TITLE)} times in Markdown')
    title_end = markdown.index(HYPOTHESIS_TITLE) + len(HYPOTHESIS_TITLE)
    following = [match for match in HTML_TABLE.finditer(markdown) if match.start() >= title_end][:3]
    if len(following) != 3:
        raise ValueError(f'{level}/{key}/{node}: hypothesis Markdown tables missing')
    gaps = [markdown[title_end:following[0].start()],
            markdown[following[0].end():following[1].start()],
            markdown[following[1].end():following[2].start()]]
    headers = [_html_header_cells(match.group(0)) for match in following]
    if (
        any(gap.strip() for gap in gaps)
        or headers[0] != ['名稱', '說明']
        or [cell for cell in headers[1] if cell] != ['名稱', '說明']
        or len(headers[1]) != 4
        or '為真' not in following[2].group(0)
    ):
        raise ValueError(f'{level}/{key}/{node}: hypothesis Markdown table shape changed')
    return markdown[:following[0].start()] + '\n\n'.join(rendered) + markdown[following[2].end():]


def normalize_published_block_parentheses(blocks: list[dict]) -> list[dict]:
    """Apply the Chinese-context parenthesis rule (see cjk_parentheses.py).

    Runs after Track A repairs, publication overlays and formula attachment so
    their exact source-text matchers are unaffected; table ``html`` is rebuilt
    from the normalized ``rows`` exactly as ``enrich_guide_blocks`` builds it.
    """
    result = []
    for block in blocks:
        normalized = normalize_block_parentheses(block)
        if (
            normalized.get('type') == 'table'
            and normalized.get('rows') != block.get('rows')
            and 'html' in block
        ):
            normalized['html'] = table_rows_to_html(normalized.get('rows') or [])
        result.append(normalized)
    return result


def collect_formula_blocks(value: Any) -> list[dict]:
    formulas: list[dict] = []
    if isinstance(value, dict):
        if value.get('type') == 'formula' and str(value.get('latex') or '').strip():
            latex = str(value['latex']).strip()
            if latex.startswith('$$') and latex.endswith('$$'):
                latex = latex[2:-2].strip()
            elif latex.startswith('$') and latex.endswith('$'):
                latex = latex[1:-1].strip()
            formulas.append({
                'latex': latex,
                'display': bool(value.get('display', True)),
            })
        for child in value.values():
            formulas.extend(collect_formula_blocks(child))
    elif isinstance(value, list):
        for child in value:
            formulas.extend(collect_formula_blocks(child))
    return formulas


def _load_formula_cache(cache_dir: Path) -> dict[int, list[dict]]:
    if not cache_dir.exists():
        return {}

    pages: dict[int, list[dict]] = {}
    for path in sorted(cache_dir.glob('page_*.json')):
        try:
            page_index = int(path.stem.removeprefix('page_'))
        except ValueError:
            continue
        formulas = collect_formula_blocks(load_json(path))
        if formulas:
            pages[page_index] = formulas
    return pages


def load_audit_formula_pages(level: str, key: str) -> dict[int, list[dict]]:
    """公式來源有兩處，合併後回傳。

    `audit_cache/` 是舊的 Gemini 審核產物；`ocr_formulas/` 是 guide_ocr 抽出來的
    （scripts/merge_guide_ocr.py 產生），數量與正確性都遠勝——OCR 版經 KaTeX 與
    MathJax 雙引擎驗過零解析錯誤。同頁兩邊都有時 OCR 版排前面，`enrich_guide_blocks`
    的比對會優先採用它；重複的 latex 去掉。
    """
    audit = _load_formula_cache(BASE / 'data' / level / 'audit_cache' / key)
    ocr = _load_formula_cache(BASE / 'data' / level / 'ocr_formulas' / key)

    pages: dict[int, list[dict]] = {}
    for page_index in set(audit) | set(ocr):
        merged: list[dict] = []
        seen: set[str] = set()
        # PaddleOCR-VL formulas are the source-faithful primary track.  Mixing
        # Gemini audit variants into a page that already has OCR formulas was
        # the main source of duplicated and shifted attachments.  Audit is a
        # fallback only when the primary page has no formula result.
        source = ocr.get(page_index) or audit.get(page_index, [])
        for formula in source:
            latex = str(formula.get('latex') or '').strip()
            if not latex or latex in seen:
                continue
            seen.add(latex)
            merged.append(formula)
        if merged:
            pages[page_index] = merged
    return pages


FORMULA_TEXT_RE = re.compile(
    r'([=∑Σ√∞≤≥≈≠^]|'
    r'[𝑎-𝑧𝐴-𝑍𝛼-𝜔𝝁𝝈𝜇𝜎𝜆]|'
    r'\b(?:ROI|NPV|MSE|IQR|IOU|RSS|TSS|Softmax|Sigmoid|ReLU|TF|IDF|tf-idf|'
    r'Var|Accuracy|Precision|Recall|F1|Loss|Bayes)\b|'
    r'[A-Za-z𝑨-𝒛𝐴-𝑍]\s*[（(][^）)]*[|｜=,，])',
    re.IGNORECASE,
)

FORMULA_CUE_RE = re.compile(r'(公式如下|計算公式|計算方式|可表示為|數學定義為|定義為：?$)')
FORMULA_EXPRESSION_RE = re.compile(
    r'([=＝∑Σ√∞≤≥≈≠^]|'
    r'[𝑎-𝑧𝐴-𝑍𝛼-𝜔𝝁𝝈𝜇𝜎𝜆]|'
    r'[P𝑃]\s*[（(][^）)]*[|｜=,，])'
)


def text_looks_formula_related(text: str) -> bool:
    if not text:
        return False
    return bool(FORMULA_TEXT_RE.search(text) or FORMULA_CUE_RE.search(text))


def text_has_formula_expression(text: str) -> bool:
    if not text:
        return False
    return bool(FORMULA_EXPRESSION_RE.search(text))


def formula_slot_count(text: str) -> int:
    if not text:
        return 0
    equation_count = len(re.findall(r'[=＝]', text))
    probability_count = len(re.findall(r'[P𝑃]\s*[（(]', text))
    named_formula_count = len(re.findall(
        r'\b(?:ROI|NPV|MSE|IQR|IOU|RSS|TSS|TF|IDF|tf-idf|N-grams|Softmax|Sigmoid|ReLU|Accuracy|Precision|Recall|F1|Loss)\b',
        text,
        re.IGNORECASE,
    ))
    slots = max(probability_count, named_formula_count, 1 if equation_count else 0)
    if slots == 0 and (FORMULA_CUE_RE.search(text) or text_looks_formula_related(text)):
        slots = 1
    return max(1, min(slots, 4)) if text_looks_formula_related(text) else 0


def text_is_formula_cue_only(text: str) -> bool:
    return bool(FORMULA_CUE_RE.search(text) and not FORMULA_TEXT_RE.search(text))


def text_is_formula_context_only(text: str) -> bool:
    return text_looks_formula_related(text) and not FORMULA_CUE_RE.search(text) and not text_has_formula_expression(text)


def text_is_formula_only(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    chinese_count = len(re.findall(r'[\u4e00-\u9fff]', stripped))
    math_count = len(re.findall(r'[=∑Σ√∞≤≥≈≠×÷^]|[𝑎-𝑧𝐴-𝑍𝛼-𝜔𝝁𝝈𝜇𝜎𝜆]', stripped))
    latin_formula = bool(re.search(r'^(?:ROI|NPV|MSE|IQR|IOU|RSS|TSS|TF|IDF|Var|Loss|P|E|f|Z|R\^2)\b', stripped, re.IGNORECASE))
    return (
        len(stripped) <= 120
        and (math_count >= 3 or latin_formula)
        and chinese_count <= 8
    )


def high_confidence_formula_for_text(text: str) -> dict | None:
    stripped = text.strip()
    if not stripped:
        return None
    normalized = re.sub(r'\s+', '', stripped).lower()
    if 'roi' in normalized and '投資回報' in stripped:
        return {'latex': r'\mathrm{ROI} = \frac{\text{投資回報} - \text{投資成本}}{\text{投資成本}} \times 100\%', 'display': True}
    if 'npv' in normalized and '每期現金流' in stripped:
        return {'latex': r'\mathrm{NPV} = \sum_{t=1}^{n}\frac{\mathrm{CF}_t}{(1+r)^t} - I_0', 'display': True}
    if '風險等級' in stripped and '發生機率' in stripped and '影響程度' in stripped:
        return {'latex': r'\text{風險等級} = \text{發生機率} \times \text{影響程度}', 'display': True}
    if '變異數公式' in stripped or ('𝜎2' in stripped and '∑' in stripped):
        return {'latex': r'\sigma^2 = \frac{1}{N}\sum_{i=1}^{N}(x_i-\mu)^2', 'display': True}
    if '標準差公式' in stripped or ('𝜎' in stripped and '√' in stripped and '∑' in stripped):
        return {'latex': r'\sigma = \sqrt{\frac{1}{N}\sum_{i=1}^{N}(x_i-\mu)^2}', 'display': True}
    if '算術平均' in stripped and ('x1' in normalized or '𝑥1' in stripped):
        return {'latex': r'\text{算術平均} = \frac{x_1+x_2+\cdots+x_n}{n}', 'display': True}
    if '幾何平均' in stripped and ('∏' in stripped or '乘積' in stripped):
        return {'latex': r'\text{幾何平均} = \left(\prod_{i=1}^{n}x_i\right)^{1/n}', 'display': True}
    if '調和平均' in stripped and ('∑' in stripped or '倒數' in stripped):
        return {'latex': r'\text{調和平均} = \frac{n}{\sum_{i=1}^{n}\frac{1}{x_i}}', 'display': True}
    if '中位數' in stripped and ('n+1' in normalized or '𝑛+1' in stripped):
        return {'latex': r'\text{中位數} = x_{\left(\frac{n+1}{2}\right)}', 'display': True}
    if '中位數' in stripped and ('n/2' in normalized or '𝑛/2' in stripped):
        return {'latex': r'\text{中位數} = \frac{x_{\left(\frac{n}{2}\right)} + x_{\left(\frac{n}{2}+1\right)}}{2}', 'display': True}
    if re.search(r'\bIOU\b', stripped, re.IGNORECASE) and ('intersection' in normalized or 'union' in normalized):
        return {'latex': r'\mathrm{IOU} = \frac{\mathrm{Intersection}}{\mathrm{Union}}', 'display': True}
    return None


FORMULA_MATCH_KEYWORDS = (
    'tf-idf', 'tfidf', 'tf', 'idf', 'roi', 'npv', 'mse', 'iqr', 'iou',
    'rss', 'tss', 'softmax', 'sigmoid', 'relu', 'accuracy', 'precision',
    'recall', 'f1', 'loss', 'var', 'bayes', 'n-grams', 'ngrams',
    'support', 'lift', 'confidence',
)

GREEK_TEXT_MARKERS = {
    'alpha': ('α', '𝛼'),
    'beta': ('β', '𝛽'),
    'gamma': ('γ', '𝛾'),
    'lambda': ('λ', '𝜆'),
    'mu': ('μ', '𝜇'),
    'omega': ('ω', '𝜔'),
    'rho': ('ρ', '𝜌'),
    'sigma': ('σ', '𝜎'),
    'theta': ('θ', '𝜃'),
    'xi': ('ξ', '𝜉'),
}


def compact_formula_text(text: str) -> str:
    lowered = text.lower()
    lowered = lowered.replace('tf-idf', 'tfidf').replace('n-grams', 'ngrams')
    return re.sub(r'\s+', '', lowered)


def formula_match_score(formula: dict, text: str) -> int:
    latex = str(formula.get('latex') or '')
    if not latex or not text:
        return 0
    latex_compact = compact_formula_text(latex)
    text_compact = compact_formula_text(text)
    score = 0

    for keyword in FORMULA_MATCH_KEYWORDS:
        key = keyword.replace('-', '')
        if key in latex_compact and key in text_compact:
            score += 5

    for chinese in re.findall(r'[\u4e00-\u9fff]{2,}', latex):
        if chinese in text:
            score += 3

    if '\\sum' in latex and '∑' in text:
        score += 2
    if '\\frac' in latex and ('/' in text or '分數' in text or '公式' in text):
        score += 1
    if re.search(r'\\?binom|\\choose', latex) and ('二項' in text or '組合' in text):
        score += 3
    if re.search(r'\bP\s*\(', latex) and re.search(r'[P𝑃]\s*[（(]', text):
        score += 5
    if re.search(r'\bS\s*=', latex) and re.search(r'\bS\s*=', text):
        score += 5

    for greek_name, markers in GREEK_TEXT_MARKERS.items():
        if f'\\{greek_name}' in latex and any(marker in text for marker in markers):
            score += 2

    latex_tokens = {
        token
        for token in re.findall(r'(?<!\\)\b[A-Za-z][A-Za-z0-9]*\b', latex)
        if len(token) <= 8 and token.lower() not in {'text', 'frac', 'left', 'right', 'sum', 'log', 'exp'}
    }
    for token in latex_tokens:
        if token.lower() in text_compact:
            score += 1

    return score


def add_formula_to_block(block: dict, formula: dict) -> None:
    formulas = block.setdefault('formulas', [])
    if any(existing.get('latex') == formula.get('latex') for existing in formulas):
        return
    formulas.append(formula)


def enrich_guide_blocks(blocks: list[dict], audit_formulas_by_page: dict[int, list[dict]]) -> list[dict]:
    enriched = [dict(block) for block in blocks]
    text_blocks_by_page: dict[int, list[dict]] = {}

    for block in enriched:
        if block.get('type') == 'table':
            rows = block.get('rows') or []
            html = table_rows_to_html(rows)
            if html:
                block['html'] = html
            continue

        if block.get('type') not in {'paragraph', 'list_item', 'question', 'answer'}:
            continue

        page_index = block.get('pageIndex')
        if isinstance(page_index, int):
            text_blocks_by_page.setdefault(page_index, []).append(block)

    for page_index, page_formulas in audit_formulas_by_page.items():
        remaining = [dict(formula) for formula in page_formulas]
        page_blocks = text_blocks_by_page.get(page_index) or []
        candidates = [
            block
            for block in page_blocks
            if text_looks_formula_related(block.get('text') or '')
        ]
        effective_candidates = [
            block
            for index, block in enumerate(candidates)
            if not (
                (
                    text_is_formula_cue_only(block.get('text') or '')
                    or text_is_formula_context_only(block.get('text') or '')
                )
                and any(
                    text_has_formula_expression(candidate.get('text') or '')
                    for candidate in candidates[index + 1:]
                )
            )
        ] or candidates

        capacities = {
            id(block): formula_slot_count(block.get('text') or '')
            for block in effective_candidates
        }
        for formula in remaining:
            available = [block for block in effective_candidates if capacities.get(id(block), 0) > 0]
            if not available:
                break
            scored = [
                (formula_match_score(formula, block.get('text') or ''), -index, block)
                for index, block in enumerate(available)
            ]
            best_score, _, best_block = max(scored, key=lambda item: (item[0], item[1]))
            if best_score < 2:
                continue
            add_formula_to_block(best_block, formula)
            capacities[id(best_block)] = max(0, capacities.get(id(best_block), 0) - 1)

    for page_blocks in text_blocks_by_page.values():
        for block in page_blocks:
            # 規則表是最後一道保險：專門認得文字層攤平公式後的亂碼（「算術平均= 𝑥1 + 𝑥2 …」）。
            # 原本還多一個「整頁都沒有快取公式才啟用」的頁級條件，但那太寬——
            # 同一頁只要有任何一個公式進了快取，整頁其他區塊就拿不到規則表的救援。
            # 逐區塊的 `not block.get('formulas')` 已經足以避免重複附加。
            rule_formula = high_confidence_formula_for_text(block.get('text') or '')
            if rule_formula and not block.get('formulas'):
                add_formula_to_block(block, rule_formula)

    for block in enriched:
        if block.get('formulas') and text_is_formula_only(block.get('text') or ''):
            block['formulaOnly'] = True
    return enriched


# 換行接續規則（2026-11-02 第三輪）：PDF 版面在中文詞與後接的括號註解之間斷行
# （「循環神經網路\n（Recurrent …）」），以空白接回會留下「網路 （」的假空白。
# 上一行以 CJK 字或全形標點結尾、下一行以全形「（」或半形 "(" 開頭時直接相接；
# 選項／編號標記（「（A）」「(2)」「（三）」）是新項目的開頭，仍以空白分隔。
# 其他換行（含「） 中文」這類標籤＋正文）仍以單一空白接續，不在此處處理。
CJK_LINE_END_PATTERN = re.compile(r'[\u3000-\u303f\u4e00-\u9fff\uff01-\uff0f\uff1a-\uff20\uff3b-\uff40\uff5b-\uff65]$')
ENUMERATION_MARKER_PATTERN = re.compile(r'^[（(]\s*(?:[A-Za-zＡ-Ｚａ-ｚ]|[0-9０-９]+|[一二三四五六七八九十]+)\s*[）)]')


def join_wrapped_lines(lines: list[str]) -> str:
    parts = [line.strip() for line in lines if line.strip()]
    if not parts:
        return ''
    text = parts[0]
    for line in parts[1:]:
        if (
            line[0] in '（('
            and CJK_LINE_END_PATTERN.search(text)
            and not ENUMERATION_MARKER_PATTERN.match(line)
        ):
            text += line
        else:
            text += ' ' + line
    return text


def block_text(value: str) -> str:
    value = (
        value
        .replace('\uf097', '• ')
        .replace('\uf09f', '• ')
        .replace('\uf077', '◦ ')
        .replace('\uf0a1', '○ ')
    )
    text = join_wrapped_lines(value.splitlines())
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
    if (
        not block.get('text')
        and not block.get('title')
        and block.get('type') not in {'table', 'source_image'}
    ):
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


# 初級 guide1: the PDF text layer drops the heading words of the numbered
# sections and keeps only the 「N.」 marker (guide_ocr has them).  Titles are
# copied from the page images (2026-11-02 review, 初級 guide1 idx 6/8/9/16/17/
# 19/22 = 3-1…3-18, idx 39/40/44 = 3-34…3-39, idx 54/61 = 3-49/3-56).
# TA-048 (s1c1 '1.') follows the printed 3-1 title (user decision 2026-11-02).
CONTENT_SECTION_TITLES: dict[str, dict[str, list[str]]] = {
    's1c1': {
        '1.': ['1. 人工智慧的應用領域'],
        '2.': ['2. 人工智慧的架構'],
        '3.': ['3. 資料處理與分析'],
        '4.': ['4. 演算法'],
        '5.': ['5. 機器學習'],
        '6.': ['6. 深度學習'],
        '7.': ['7. 生成式人工智慧'],
    },
    's1c3': {
        '1.': ['1. 機器學習基本理論'],
        '2.': ['2. 機器學習的類型'],
        '3.': ['3. 機器學習核心過程'],
    },
    's1c4': {
        '1.': ['1. 鑑別式 AI 與生成式 AI 的基本原理'],
        '2.': ['2. 鑑別式 AI 與生成式 AI 的整合應用'],
    },
}


# Numbered section headings 「N. 標題」 of 初級 guide2 (3-1…3-50) and 中級
# guide2 (第三章～第六章).  Their heading font loses every CJK glyph in the PDF
# text layer: what survives is the bare 「N.」 marker (sometimes glued to the
# section's first sentence) plus the Latin letters of the title, which leak to
# the start of the next paragraph (「3.」 + 「AI No Code / Low Code 生成式AI…」).
# Earlier hand tables guessed titles from those fragments and invented parent
# headings; the user decided on 2026-11-02 that these headings follow the
# printed page.  Every title below is the pages_cache (Track B) heading of that
# page, checked against the page image on 2026-11-02 (scratchpad
# round3/b4/heads_montage_*.png).  Keyed by (0-based pageIndex, number).
PRINTED_SECTION_TITLES: dict[str, dict[tuple[int, int], str]] = {
    '初級/guide2': {
        (6, 1): '1. No Code 平台',
        (7, 2): '2. Low Code 平台',
        (7, 3): '3. 生成式 AI 與 No Code / Low Code 的結合',
        (7, 4): '4. 生成式 AI 在各行各業的應用實例',
        (9, 5): '5. No Code / Low Code 平台的選擇與評估',
        (11, 6): '6. 生成式 AI 與 No Code / Low Code 結合所面臨的挑戰',
        (13, 7): '7. No Code / Low Code 的市場價值',
        (14, 8): '8. AI 發展趨勢中的 No Code / Low Code',
        (15, 9): '9. 對 AI 民主化的影響',
        (22, 1): '1. 生成式 AI 的基本概念',
        (23, 2): '2. 市場價值與影響力',
        (25, 3): '3. AI 工具的技術進化',
        (27, 4): '4. 工具發展與趨勢',
        (29, 5): '5. 各領域的應用與發展',
        (36, 1): '1. 生成式 AI 導入評估',
        (39, 2): '2. 生成式 AI 導入規劃',
        (50, 3): '3. 生成式 AI 風險管理',
    },
    '中級/guide2': {
        (8, 1): '1. 前言與章節導覽',
        (9, 2): '2. 集中趨勢與離散量度',
        (16, 3): '3. 資料偏度（Skewness）與峰度（Kurtosis）',
        (19, 1): '1. 前言與章節導覽',
        (19, 2): '2. 機率分佈簡介',
        (22, 3): '3. 常見離散型分佈',
        (24, 4): '4. 常見連續型分佈',
        (27, 5): '5. 分佈擬合與資料建模',
        (29, 1): '1. 前言與章節導覽',
        (29, 2): '2. 統計推論概念與應用情境',
        (31, 3): '3. 假設檢定的基本流程',
        (35, 4): '4. 型一與型二錯誤',
        (37, 5): '5. 常見統計檢定方法與應用',
        (56, 1): '1. 前言與章節導覽',
        (56, 2): '2. 資料來源類型與蒐集方式',
        (59, 3): '3. 資料品質問題類型與評估指標',
        (63, 1): '1. 前言與章節導覽',
        (63, 2): '2. 資料型態與結構管理',
        (65, 3): '3. 分散式儲存與資料湖架構',
        (67, 4): '4. 儲存效能優化與查詢管理',
        (69, 5): '5. 資料一致性、版本控制與治理機制',
        (74, 1): '1. 前言與章節導覽',
        (74, 2): '2. 清理後的資料準備與轉換',
        (77, 3): '3. 特徵工程技術',
        (80, 4): '4. 分散式資料處理框架',
        (81, 5): '5. 資料處理管線與自動化工具',
        (89, 1): '1. 前言與章節導覽',
        (89, 2): '2. 大數據下敘述統計的挑戰與限制',
        (90, 3): '3. 大數據下統計推論的挑戰與限制',
        (93, 4): '4. 統計學在大數據中的實務應用案例',
        (97, 1): '1. 前言與章節導覽',
        (97, 2): '2. 描述性分析與近似計算方法',
        (101, 3): '3. 時序數據分析',
        (104, 4): '4. 網路分析',
        (107, 5): '5. 文字資料分析',
        (110, 6): '6. 地理空間資料分析',
        (113, 7): '7. 異常偵測方法',
        (116, 1): '1. 前言與章節導覽',
        (116, 2): '2. 常用視覺化方法與圖表類型',
        (126, 3): '3. 主流數據視覺化平台與工具類型',
        (129, 4): '4. 大數據視覺化應用案例與設計原則',
        (139, 1): '1. 前言與章節導覽',
        (139, 2): '2. 大數據特性對機器學習流程的影響',
        (146, 3): '3. 大數據環境下的模型訓練與加速技術',
        (148, 4): '4. 大數據到模型部署的整合流程',
        (151, 1): '1. 前言與章節導覽',
        (151, 2): '2. 典型應用情境與模型任務',
        (156, 3): '3. 輸入資料類型與標註資料來源整合',
        (162, 1): '1. 前言與章節導覽',
        (162, 2): '2. 資料選擇對生成內容品質的影響分析',
        (165, 3): '3. 典型應用情境',
        (167, 1): '1. 前言與章節導覽',
        (167, 2): '2. 個資識別風險與資料匿名化/隱私強化技術',
        (171, 3): '3. AI 訓練資料的合規取得與處理要求',
        (174, 4): '4. 企業內部治理機制',
    },
}

PRINTED_SECTION_TITLE_ROUTES: dict[str, str] = {
    **{route: '初級/guide2' for route in ('s2c1', 's2c2', 's2c3', 's2pdf-c3')},
    **{f'mid-s2c{index}': '中級/guide2' for index in range(1, 14)},
    **{f'mid-s2pdf-c{index}': '中級/guide2' for index in range(3, 7)},
}

ASCII_TITLE_RUN = re.compile(r'[!-~]+')


def printed_title_text_layer_leak(title: str) -> str:
    """ASCII characters of a printed section title as the PDF text layer keeps them.

    Every CJK glyph and full-width bracket is lost; Latin words, digits and
    ASCII punctuation survive, space-separated (「No Code / Low Code」, and the
    lone 「/」 of 「資料匿名化/隱私強化技術」).
    """
    body = re.sub(r'^\d+\.\s*', '', title)
    return ' '.join(ASCII_TITLE_RUN.findall(body))


def _strip_title_leak(text: str, leak: str) -> str | None:
    if not leak:
        return text
    if text.startswith(leak + ' ') and text[len(leak) + 1:].strip():
        return text[len(leak) + 1:]
    return None


def _pages_cache_section_title(level: str, key: str, page_index: int, number: int) -> str | None:
    path = BASE / 'data' / level / 'pages_cache' / key / f'page_{page_index:03d}.json'
    if not path.exists():
        return None
    markdown = str(load_json(path).get('markdown') or '')
    titles = [
        match.group(1).strip()
        for match in re.finditer(rf'^#{{1,6}}\s*({number}\.(?!\d)\s*.+)$', markdown, re.M)
    ]
    if len(titles) != 1:
        raise ValueError(
            f'{level}/{key} page {page_index}: pages_cache has {len(titles)} 「{number}.」 headings'
        )
    return titles[0]


def restore_printed_section_headings(current_id: str, blocks: list[dict]) -> list[dict]:
    """Rebuild the 「N.」 headings of PRINTED_SECTION_TITLE_ROUTES from the printed titles.

    Every printed heading on the node's pages must be found exactly once in one
    of the three text-layer shapes, otherwise the build fails closed:
    a paragraph that is only 「N.」 (the next paragraph then has to start with
    the title's leaked Latin letters, which are removed); a paragraph
    「N. <leak> <first sentence>」 (split into heading + paragraph); or a heading
    「N. <leak>」/「N. <printed title>」.
    """
    family = PRINTED_SECTION_TITLE_ROUTES.get(current_id)
    if family is None:
        return blocks
    level, key = family.split('/')
    table = PRINTED_SECTION_TITLES[family]
    # The chapter title 「第三章 生成式AI應用與規劃」 leaves a lone 「AI」 line
    # right before the first section heading (初級 3-1).
    blocks = [
        block for index, block in enumerate(blocks)
        if not (
            block.get('type') == 'paragraph'
            and str(block.get('text') or '').strip() == 'AI'
            and index + 1 < len(blocks)
            and blocks[index + 1].get('type') == 'heading'
            and int(blocks[index + 1].get('depth') or 0) == 2
        )
    ]
    pages = {block.get('pageIndex') for block in blocks}
    expected = {slot: title for slot, title in table.items() if slot[0] in pages}
    for (page_index, number), title in expected.items():
        cached = _pages_cache_section_title(level, key, page_index, number)
        if cached is not None and cached != title:
            raise ValueError(
                f'{current_id}: printed title {title!r} differs from pages_cache {cached!r} '
                f'(page {page_index})'
            )

    result: list[dict] = []
    claimed: set[tuple[int, int]] = set()
    pending_leak: tuple[tuple[int, int], str] | None = None
    for original in blocks:
        block = dict(original)
        text = str(block.get('title') or block.get('text') or '').strip()
        if pending_leak is not None:
            slot, leak = pending_leak
            pending_leak = None
            stripped = _strip_title_leak(text, leak) if block.get('type') == 'paragraph' else None
            if stripped is None:
                raise ValueError(f'{current_id}: printed heading {slot} leak {leak!r} not found in {text[:40]!r}')
            block['text'] = stripped
            result.append(block)
            continue
        marker = re.match(r'^(\d+)\.(?!\d)\s*(.*)$', text, re.S)
        slot = (block.get('pageIndex'), int(marker.group(1))) if marker else None
        if slot is None or slot not in expected or slot in claimed:
            result.append(block)
            continue
        title = expected[slot]
        leak = printed_title_text_layer_leak(title)
        rest = marker.group(2).strip()
        heading = {
            'type': 'heading', 'depth': 3, 'title': title, 'anchor': '',
            'pageIndex': block.get('pageIndex'), 'bbox': block.get('bbox'),
        }
        block_type = block.get('type')
        if block_type == 'paragraph' and not rest:
            claimed.add(slot)
            result.append(heading)
            if leak:
                pending_leak = (slot, leak)
            continue
        if block_type == 'paragraph':
            body = _strip_title_leak(rest, leak)
            if body is None:
                result.append(block)
                continue
            claimed.add(slot)
            result.append(heading)
            result.append({**block, 'text': body})
            continue
        if block_type == 'heading' and int(block.get('depth') or 0) <= 3:
            if normalize(rest) not in {normalize(leak), normalize(re.sub(r'^\d+\.\s*', '', title))}:
                raise ValueError(f'{current_id}: heading {text!r} does not match printed {title!r}')
            claimed.add(slot)
            result.append(heading)
            continue
        result.append(block)
    if pending_leak is not None:
        raise ValueError(f'{current_id}: printed heading {pending_leak[0]} has no following paragraph')
    missing = sorted(set(expected) - claimed)
    if missing:
        raise ValueError(f'{current_id}: printed section headings not found in text layer: {missing}')
    return result


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
    '（4）數值標準化（Standardization）': '（4）數值標準化（Standardization）與正規化（Normalization）',
    '（1）基本架構與監督式學習不同，非監督學習模型的輸出通常不是具體的預測值，而是：': '（1）基本架構',
    '5. 多模態多模態 AI風險與未來趨勢': '5. 多模態 AI風險與未來趨勢',
    '3. 偏見（Bias）與倫理（Ethics': '3. 偏見（Bias）與倫理（Ethics）',
    'A. 原理：': 'A. 原理',
    '2. 監督式學習-': '2. 監督式學習-迴歸任務',
    '3. 監督式學習-': '3. 監督式學習-分類任務',
}


PARENT_BEFORE_HEADING: dict[str, dict[str, str]] = {
    'mid-s2pdf-c3': {
        '（1）集中趨勢（Central Tendency）': '3.1 敘述性統計與資料摘要技術',
    },
}


DEMOTE_EXACT_HEADINGS_BY_CONTENT: dict[str, set[str]] = {}


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


# Heading glyph runs the text layer split off a standalone 「N.」 marker and
# glued onto the next paragraph (初級 guide1 idx 61: 「2.」「AI」「AI」, then
# 「AI AI 鑑別式AI 與生成式AI 是…」).  When the marker becomes the section
# heading, the paragraph must start with exactly this spill, which is removed;
# any other shape fails closed.
CONTENT_SECTION_TITLE_SPILL: dict[tuple[str, str], str] = {
    ('s1c4', '2.'): 'AI AI ',
}


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
            and merged[-1].get('pageIndex') == block.get('pageIndex')
            and re.match(r'^(與|及|和)[^。！？]{1,40}$', block.get('text') or '')
        ):
            title = f'{merged[-1]["title"]}{block["text"]}'
            retitle_heading(merged[-1], TITLE_REPLACEMENTS.get(title, title), len(merged))
            continue
        merged.append(block)
    return merged


def normalize_empty_marker_list_items(blocks: list[dict]) -> list[dict]:
    normalized = []
    for block in blocks:
        if block.get('type') == 'list_item' and not (block.get('marker') or '').strip():
            normalized.append({
                'type': 'paragraph',
                'depth': int(block.get('depth') or 3),
                'text': block_text(block.get('text') or ''),
                'pageIndex': block.get('pageIndex'),
                'bbox': block.get('bbox'),
            })
            continue
        normalized.append(block)
    return normalized


def looks_like_short_continuation_fragment(text: str) -> bool:
    text = text.strip()
    if not text or len(text) > 24:
        return False
    if re.fullmatch(r'\d+(?:\.\d+)?\.?', text):
        return False
    if text.endswith(('：', ':')):
        return False
    return bool(re.search(r'[\u4e00-\u9fffA-Za-z0-9）)]', text))


def should_merge_list_item_continuation(previous: dict, current: dict) -> bool:
    if previous.get('type') != 'list_item' or current.get('type') != 'paragraph':
        return False
    if previous.get('pageIndex') != current.get('pageIndex'):
        return False
    text = block_text(current.get('text') or '')
    previous_text = block_text(previous.get('text') or '')
    marker = previous.get('marker') or ''
    if not text or text_looks_structural(text):
        return False
    if looks_like_short_continuation_fragment(text) and not text_looks_hard_complete(previous_text):
        return True
    if marker in {'•', '◦', '○'} and not text_looks_hard_complete(previous_text) and len(text) <= 80:
        return True
    return False


def merge_list_item_continuation_paragraphs(blocks: list[dict]) -> list[dict]:
    merged: list[dict] = []
    for block in blocks:
        if merged and should_merge_list_item_continuation(merged[-1], block):
            merged[-1]['text'] = block_text(f'{merged[-1].get("text") or ""}\n{block.get("text") or ""}')
            merged[-1]['bbox'] = merge_block_bbox(merged[-1].get('bbox'), block.get('bbox'))
            continue
        merged.append(block)
    return merged


def remove_standalone_numeric_artifact_paragraphs(blocks: list[dict]) -> list[dict]:
    result = []
    for block in blocks:
        text = (block.get('text') or '').strip()
        if block.get('type') == 'paragraph' and re.fullmatch(r'\d+(?:\.\d+)?\.?', text):
            continue
        result.append(block)
    return result


def opens_nested_example_list(text: str) -> bool:
    stripped = block_text(text)
    if not stripped.endswith(('：', ':')):
        return False
    return bool(re.search(r'(示例|例如|假設|分別為|如下|如下所示)', stripped))


def looks_like_nested_example_child(text: str) -> bool:
    stripped = block_text(text)
    if not stripped:
        return False
    if opens_nested_example_subheading(stripped):
        return False
    return bool(
        re.match(r'^(文件\s*\d+|["“][^"”]+["”]|[\[（(]|[A-Za-z][A-Za-z0-9_-]*\s*[=:：])', stripped)
        or re.match(r'^[\d.-]+(?:\s|,|，)', stripped)
    )


def opens_nested_example_subheading(text: str) -> bool:
    stripped = block_text(text)
    return bool(re.match(r'^文件\s*\d+\s*的.+(?:向量|矩陣|結果|數值|計算)\s*為$', stripped))


def bbox_left(block: dict) -> float | None:
    bbox = block.get('bbox') or []
    if len(bbox) == 4 and isinstance(bbox[0], (int, float)):
        return float(bbox[0])
    return None


def can_open_indented_children(text: str) -> bool:
    stripped = block_text(text)
    if stripped.endswith(('：', ':')):
        return True
    colon_index = min(
        [index for index in [stripped.find('：'), stripped.find(':')] if index >= 0],
        default=-1,
    )
    if colon_index <= 0 or colon_index > 90:
        return False
    label = stripped[:colon_index]
    if re.search(r'[。！？；;，,]', label):
        return False
    return bool(re.search(r'[\u4e00-\u9fffA-Za-z]', label))


def refine_indented_same_marker_list_depths(blocks: list[dict]) -> list[dict]:
    """Use PDF indentation to recover nested lists when extraction reuses ○ for multiple levels."""
    result: list[dict] = []
    stack: list[dict] = []
    for block in blocks:
        block = dict(block)
        if block.get('type') != 'list_item':
            if block.get('type') in {'heading', 'table', 'question', 'answer'}:
                stack = []
            result.append(block)
            continue

        left = bbox_left(block)
        depth = int(block.get('depth') or 0)
        marker = block.get('marker') or ''
        while stack:
            parent = stack[-1]
            parent_left = parent.get('left')
            parent_depth = int(parent.get('depth') or 0)
            if left is None or parent_left is None or left <= parent_left + 7 or depth < parent_depth:
                stack.pop()
                continue
            break

        if stack and marker == stack[-1].get('marker') and left is not None:
            parent_left = stack[-1].get('left')
            if parent_left is not None and left > float(parent_left) + 7:
                block['depth'] = min(int(stack[-1].get('depth') or depth) + 1, 9)

        text = block.get('text') or ''
        if can_open_indented_children(text) and left is not None:
            stack.append({'left': left, 'depth': int(block.get('depth') or depth), 'marker': marker})
        result.append(block)
    return result


def split_inferred_nested_example_paragraphs(blocks: list[dict]) -> list[dict]:
    result: list[dict] = []
    for block in blocks:
        if (
            result
            and block.get('type') == 'paragraph'
            and result[-1].get('type') == 'list_item'
            and '示例' in (result[-1].get('text') or '')
        ):
            previous_left = bbox_left(result[-1])
            current_left = bbox_left(block)
            text = block_text(block.get('text') or '')
            if previous_left is not None and current_left is not None and current_left > previous_left + 8:
                parts = re.split(r'\s+(?=預測中心詞（Center Word）)', text)
                if len(parts) > 1 and all(part.strip() for part in parts):
                    child_depth = min(int(result[-1].get('depth') or 7) + 1, 9)
                    for part in parts:
                        result.append({
                            'type': 'list_item',
                            'depth': child_depth,
                            'marker': '▪',
                            'text': block_text(part),
                            'pageIndex': block.get('pageIndex'),
                            'bbox': block.get('bbox'),
                        })
                    continue
        result.append(block)
    return result


def infer_indented_paragraph_list_items(blocks: list[dict]) -> list[dict]:
    """Recover list levels whose glyphs were lost but whose indentation remains in the PDF."""
    result: list[dict] = []
    list_parent: dict | None = None
    inferred_parent: dict | None = None
    for block in blocks:
        block = dict(block)
        block_type = block.get('type')
        left = bbox_left(block)

        if block_type == 'list_item':
            list_parent = {'left': left, 'depth': int(block.get('depth') or 0)}
            inferred_parent = None
            result.append(block)
            continue

        if block_type in {'heading', 'table', 'question', 'answer'}:
            list_parent = None
            inferred_parent = None
            result.append(block)
            continue

        if block_type != 'paragraph' or left is None:
            result.append(block)
            continue

        text = block_text(block.get('text') or '')
        if not text:
            result.append(block)
            continue

        parent_left = list_parent.get('left') if list_parent else None
        parent_depth = int(list_parent.get('depth') or 0) if list_parent else 0
        inferred_left = inferred_parent.get('left') if inferred_parent else None
        inferred_depth = int(inferred_parent.get('depth') or 0) if inferred_parent else 0

        if text.endswith(('：', ':')) and parent_left is not None and left > float(parent_left) + 8:
            depth = min(parent_depth + 1, 9)
            converted = {
                'type': 'list_item',
                'depth': depth,
                'marker': '▪',
                'text': text,
                'pageIndex': block.get('pageIndex'),
                'bbox': block.get('bbox'),
            }
            result.append(converted)
            inferred_parent = {'left': left, 'depth': depth}
            continue

        if inferred_left is not None and left > float(inferred_left) + 8:
            result.append({
                'type': 'list_item',
                'depth': min(inferred_depth + 1, 9),
                'marker': '-',
                'text': text,
                'pageIndex': block.get('pageIndex'),
                'bbox': block.get('bbox'),
            })
            continue

        inferred_parent = None
        result.append(block)

    return result


def refine_nested_example_list_depths(blocks: list[dict]) -> list[dict]:
    """Use local semantics to nest example rows when PDF bullets reuse the same glyph."""
    active_parent_depth: int | None = None
    result = []
    for block in blocks:
        block = dict(block)
        block_type = block.get('type')
        if block_type != 'list_item':
            if block_type in {'heading', 'table', 'question', 'answer'}:
                active_parent_depth = None
            result.append(block)
            continue

        marker = block.get('marker') or ''
        depth = int(block.get('depth') or 0)
        text = block.get('text') or ''
        if marker in {'•', '◦'} and depth <= 6:
            active_parent_depth = None

        if marker == '○':
            if active_parent_depth is not None and depth == active_parent_depth and opens_nested_example_subheading(text):
                active_parent_depth = depth
            elif active_parent_depth is not None and depth == active_parent_depth and looks_like_nested_example_child(text):
                block['depth'] = min(active_parent_depth + 1, 9)
            elif active_parent_depth is not None and depth <= active_parent_depth and not opens_nested_example_list(text):
                active_parent_depth = None

            if depth == 7 and (opens_nested_example_list(text) or opens_nested_example_subheading(text)):
                active_parent_depth = depth
        elif marker not in {'○'}:
            active_parent_depth = None

        result.append(block)
    return result


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


def exercise_segment_source_meta(
    parts: list[str],
    sources: list[dict],
    segments: list[str],
    answer_mode: bool,
    fallback: dict,
) -> list[dict]:
    """Per-segment pageIndex/sourcePageIndexes/bbox from the source lines.

    ``split_numbered_exercise_segments`` cuts the normalized concatenation of
    ``parts``; map every cut back to the source blocks it overlaps so each
    question/answer carries its own page and bbox instead of question 1's
    (2026-11-02 review).  The page is the first overlapped source block's
    page; the bbox is the union of overlapped blocks on that page.  If the
    offsets cannot be mapped exactly (prefix normalization drift or a
    segment count mismatch) every segment keeps ``fallback``.
    """
    if not segments:
        return []
    fallback_meta = [dict(fallback) for _ in segments]
    full = block_text(' '.join(parts))
    if not full or len(parts) != len(sources):
        return fallback_meta
    # Normalized end offset of each part within ``full``.
    ends: list[int] = []
    for index in range(len(parts)):
        prefix = block_text(' '.join(parts[:index + 1]))
        if not full.startswith(prefix):
            return fallback_meta
        ends.append(len(prefix))
    if answer_mode:
        pattern = re.compile(r'(?<!\d)(\d{1,3})\.\s*Ans')
    else:
        pattern = re.compile(r'(?<!\d)(\d{1,3})\.\s+(?!Ans)')
    starts = [match.start() for match in pattern.finditer(full)]
    if not starts:
        starts = [0]
    if len(starts) != len(segments):
        return fallback_meta
    bounds = starts[1:] + [len(full)]
    metas: list[dict] = []
    for seg_start, seg_end in zip(starts, bounds):
        covered = []
        part_start = 0
        for index, part_end in enumerate(ends):
            if part_start < seg_end and seg_start < part_end:
                covered.append(sources[index])
            part_start = part_end
        paged = [block for block in covered if isinstance(block.get('pageIndex'), int)]
        if not paged:
            metas.append(dict(fallback))
            continue
        page = paged[0]['pageIndex']
        boxes = [
            block.get('bbox') for block in paged
            if block.get('pageIndex') == page
            and isinstance(block.get('bbox'), list) and len(block.get('bbox')) == 4
        ]
        bbox = (
            [min(box[0] for box in boxes), min(box[1] for box in boxes),
             max(box[2] for box in boxes), max(box[3] for box in boxes)]
            if boxes else fallback.get('bbox')
        )
        pages = sorted({
            page_index
            for block in covered
            for page_index in [block.get('pageIndex')] + list(block.get('sourcePageIndexes') or [])
            if isinstance(page_index, int)
        })
        metas.append({'pageIndex': page, 'sourcePageIndexes': pages, 'bbox': bbox})
    return metas


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
        appendix_blocks: list[dict] = []
        index += 1
        while index < len(blocks):
            candidate = blocks[index]
            candidate_text = candidate.get('text') or candidate.get('title') or ''
            if candidate.get('type') == 'table' or '附件本學習指引參考書目' in candidate_text.replace(' ', ''):
                appendix_blocks = blocks[index:]
                break
            exercise_blocks.append(candidate)
            index += 1

        question_parts: list[str] = []
        answer_parts: list[str] = []
        answer_started = False
        first_meta = {
            'pageIndex': exercise_blocks[0].get('pageIndex') if exercise_blocks else block.get('pageIndex'),
            'bbox': exercise_blocks[0].get('bbox') if exercise_blocks else block.get('bbox'),
        }
        source_page_indexes = sorted({
            page_index
            for exercise_block in exercise_blocks
            for page_index in (
                [exercise_block.get('pageIndex')]
                + list(exercise_block.get('sourcePageIndexes') or [])
            )
            if isinstance(page_index, int)
        })
        question_sources: list[dict] = []
        answer_sources: list[dict] = []
        for exercise_block in exercise_blocks:
            text = exercise_block.get('text') or exercise_block.get('title') or ''
            if not text:
                continue
            if exercise_block.get('type') == 'answer' or re.match(r'^\d+\.\s*Ans', text.strip()):
                answer_started = True
            if answer_started:
                answer_parts.append(text)
                answer_sources.append(exercise_block)
            else:
                question_parts.append(text)
                question_sources.append(exercise_block)

        fallback_meta = {**first_meta, 'sourcePageIndexes': source_page_indexes}
        for block_type, parts, sources, answer_mode in (
            ('question', question_parts, question_sources, False),
            ('answer', answer_parts, answer_sources, True),
        ):
            segments = split_numbered_exercise_segments(' '.join(parts), answer_mode=answer_mode)
            metas = exercise_segment_source_meta(parts, sources, segments, answer_mode, fallback_meta)
            for segment, meta in zip(segments, metas):
                normalized.append({
                    'type': block_type,
                    'depth': 4,
                    'text': segment,
                    'pageIndex': meta['pageIndex'],
                    'sourcePageIndexes': meta['sourcePageIndexes'],
                    'bbox': meta['bbox'],
                })
        if appendix_blocks:
            first = dict(appendix_blocks[0])
            appendix_title = first.get('text') or first.get('title') or ''
            if '附件本學習指引參考書目' in appendix_title.replace(' ', ''):
                first = {
                    'type': 'heading',
                    'depth': 3,
                    'title': '附件 本學習指引參考書目',
                    'anchor': '',
                    'pageIndex': first.get('pageIndex'),
                    'bbox': first.get('bbox'),
                }
                appendix_blocks[0] = first
            normalized.extend(appendix_blocks)
        break
    return normalized


def post_process_guide_blocks(current_id: str, raw_title: str, blocks: list[dict]) -> list[dict]:
    processed: list[dict] = []
    seen_markers: dict[str, int] = {}
    chapter_heading = manifest_chapter_heading(current_id, raw_title, blocks)
    used_chapter_heading = False

    blocks = restore_printed_section_headings(current_id, blocks)
    pending_spill: tuple[str, str] | None = None
    for original in blocks:
        block = dict(original)
        block_type = block.get('type')
        if pending_spill is not None:
            marker, spill = pending_spill
            pending_spill = None
            text = str(block.get('text') or '')
            if block_type != 'paragraph' or not text.startswith(spill) or not text[len(spill):].strip():
                raise ValueError(
                    f'{current_id}: section {marker} heading spill {spill!r} missing from the next paragraph'
                )
            block['text'] = text[len(spill):]
        title_or_text = block.get('title') or block.get('text') or ''
        stripped = title_or_text.strip()

        if stripped == 'AI' and processed and processed[-1].get('type') == 'heading' and processed[-1].get('depth') == 2:
            continue
        # 「3. 偏見（Bias）與倫理（Ethics」 wraps its closing bracket onto a line
        # of its own; TITLE_REPLACEMENTS restores it on the heading (中級 3-129).
        if (
            block_type == 'paragraph' and stripped in {'）', ')'}
            and processed and processed[-1].get('type') == 'heading'
            and str(processed[-1].get('title') or '').endswith(('）', ')'))
        ):
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
                spill = CONTENT_SECTION_TITLE_SPILL.get((current_id, stripped))
                if spill is not None:
                    pending_spill = (stripped, spill)
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
                    if detail and not (current_id == 's1c4' and detail.replace(' ', '') == 'AIAI'):
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
            if detail and heading.endswith(detail):
                # The replacement already restores the split-off tail (中級 guide2 idx 76 「（4）數值
                # 標準化（Standardization）與正規化（Normalization）」 was published twice).
                detail = None
            if current_id in {'s2c3', 's2pdf-c3'} and heading == '（3） 資源與基礎設施評估':
                heading = '（3）企業導入階段性實施策略'  # official errata, page 3-32
            block['title'] = heading
            if heading in DEMOTE_EXACT_HEADINGS_BY_CONTENT.get(current_id, set()):
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

    if pending_spill is not None:
        raise ValueError(f'{current_id}: section {pending_spill[0]} heading spill has no following paragraph')
    normalize_guide_heading_depths(processed)
    demote_gapped_alpha_heading_groups(processed)
    demote_specific_alpha_sequences(current_id, processed)
    demote_leading_toc_headings(current_id, processed)
    processed = normalize_empty_marker_list_items(processed)
    processed = merge_heading_continuation_paragraphs(processed)
    processed = merge_list_item_continuation_paragraphs(processed)
    processed = remove_standalone_numeric_artifact_paragraphs(processed)
    processed = refine_indented_same_marker_list_depths(processed)
    processed = split_inferred_nested_example_paragraphs(processed)
    processed = infer_indented_paragraph_list_items(processed)
    processed = refine_nested_example_list_depths(processed)
    processed = normalize_chapter_exercise_blocks(processed)
    for index, block in enumerate(processed, start=1):
        if block.get('type') == 'heading':
            retitle_heading(block, block.get('title') or '', index)
    return reset_block_ids(processed)


def can_extend_previous_heading(previous: dict, text: str, item: dict) -> bool:
    if previous.get('type') != 'heading':
        return False
    if previous.get('pageIndex') != item.get('page_index'):
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
    if previous.get('pageIndex') != item.get('page_index'):
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
        if item_type == 'source_image':
            append_block(blocks, {
                'type': 'source_image',
                'depth': min(current_context_depth + 1, 9),
                'src': item.get('src'),
                'alt': item.get('alt') or '學習指引原圖',
                'pageIndex': item.get('page_index'),
                'sourcePageIndexes': [item.get('page_index')],
                'bbox': item.get('bbox'),
            })
            continue
        if item_type == 'table':
            rows = item.get('rows') or []
            if rows:
                append_block(blocks, {
                    'type': 'table',
                    'depth': min(current_context_depth + 1, 9),
                    'rows': rows,
                    'pageIndex': item.get('page_index'),
                    'sourcePageIndexes': item.get('source_page_indexes') or [item.get('page_index')],
                    'bbox': item.get('bbox'),
                })
            continue

        text = block_text(item.get('text') or '')
        if not text:
            continue

        block_type, depth, marker = classify_text_block(text)
        if blocks and can_extend_previous_heading(blocks[-1], text, item):
            blocks[-1]['title'] = block_text(f'{blocks[-1]["title"]}\n{text}')
            blocks[-1]['bbox'] = merge_block_bbox(blocks[-1].get('bbox'), item.get('bbox'))
            continue
        if blocks and can_extend_previous_text_block(blocks[-1], text, item):
            blocks[-1]['text'] = block_text(f'{blocks[-1]["text"]}\n{text}')
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
            first_x = item.get('first_x')
            body_left = item.get('body_left')
            line_xs = [x for x in item.get('line_xs', []) if isinstance(x, (int, float))]
            block = {
                'type': 'paragraph',
                'depth': min(current_context_depth + 1, 9),
                'text': text,
                'pageIndex': item.get('page_index'),
                'bbox': item.get('bbox'),
            }
            if isinstance(first_x, (int, float)) and isinstance(body_left, (int, float)):
                block['indentFirstLine'] = first_x - body_left >= 12
            elif len(line_xs) >= 2:
                block['indentFirstLine'] = line_xs[0] - min(line_xs) >= 12
            append_block(blocks, block)
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
    # 表格重疊判定用「block 中心點 + pad 8」，緊貼表格上緣的標題會被整行刪掉：
    # s1c2 的「假說檢定名詞介紹：」（y 421.6–434.9）就這樣消失在 table_02
    # （y 起 426.3）裡。OCR 已判定是標題的行不因為擦邊就丟——量過，兩級合計
    # 只有這 1 個 block 受影響，不會動到表格內文。
    rescued = ocr_page_heading_keys(level, key, page_index)

    page_height = float(extracted.get('height') or 0)
    measured_tables = [table for table in tables if len(table.get('bbox') or []) == 4]
    text_items: list[dict] = []
    for block in extracted.get('blocks') or []:
        bbox = block.get('bbox') or []
        if len(bbox) != 4:
            continue
        if is_running_header_or_footer(block, page_height):
            continue
        text = clean_table_cell(block.get('text') or '')
        if not text:
            continue
        if normalize_heading_key(text) not in rescued and any(
            block_overlaps_table(block, table['bbox'])
            and not is_line_outside_ocr_table(block, table)
            for table in measured_tables
        ):
            continue
        text_items.append({
            'type': 'text',
            'page_index': page_index,
            'page_height': page_height,
            'bbox': bbox,
            'y': bbox[1],
            'x': bbox[0],
            'text': text,
        })

    body_left = page_body_left(text_items)
    for item in text_items:
        item['body_left'] = body_left
        item['first_x'] = item.get('x')
        item['line_xs'] = [item.get('x')]

    items: list[dict] = [*text_items]
    for table in tables:
        bbox = table.get('bbox') or []
        if len(bbox) != 4:
            continue
        rows = table_rows_for_markdown(table, extracted.get('blocks') or [])
        if rows:
            items.append({
                'type': 'table',
                'page_index': page_index,
                'source_page_indexes': [page_index],
                'page_height': page_height,
                'bbox': bbox,
                'y': bbox[1],
                'x': bbox[0],
                'rows': rows,
            })

    visual_key = (level, key, page_index)
    if visual_key in SEMANTIC_VISUAL_PAGES:
        expected = _visual_signature(level, key, page_index)
        expected_name = Path(str(expected['src'])).name
        fallback = OCR_VISUAL_FALLBACKS.get(visual_key)
        if fallback:
            bbox = list(fallback['bbox'])
            source_index = 1
        else:
            candidates = [
                (image_index, source_image)
                for image_index, source_image in enumerate(extracted.get('images') or [], start=1)
                if source_image.get('path')
                and Path(str(source_image['path'])).name == expected_name
                and len(source_image.get('bbox') or []) == 4
            ]
            if len(candidates) != 1:
                raise ValueError(
                    f'{level}/{key}/page_{page_index:03d}: exact source-image item '
                    f'matched {len(candidates)}, expected 1'
                )
            source_index, source_image = candidates[0]
            bbox = list(source_image['bbox'])
        # Resolve and hash now so a missing/tampered source cannot silently
        # produce a block whose asset is absent.  The copy itself happens only
        # in the isolated publication staging tree.
        _visual_source_path(level, key, page_index)
        items.append({
            'type': 'source_image',
            'page_index': page_index,
            'page_height': page_height,
            'bbox': bbox,
            'y': bbox[1],
            'x': bbox[0],
            'src': expected['src'],
            'alt': expected['alt'],
            'source_index': source_index,
        })

    return sorted(items, key=lambda item: (item['page_index'], item['y'], item['x']))


def page_body_left(text_items: list[dict]) -> float | None:
    xs = [
        float(item['x'])
        for item in text_items
        if isinstance(item.get('x'), (int, float))
        and len((item.get('text') or '').strip()) >= 4
        and not text_looks_structural(item.get('text') or '')
    ]
    if not xs:
        return None
    buckets: dict[int, list[float]] = {}
    for x in xs:
        buckets.setdefault(round(x / 4), []).append(x)
    _, values = max(buckets.items(), key=lambda item: (len(item[1]), -sum(item[1]) / len(item[1])))
    return sum(values) / len(values)


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
                merged[-1]['source_page_indexes'] = sorted({
                    page_index
                    for page_index in (
                        list(merged[-1].get('source_page_indexes') or [merged[-1].get('page_index')])
                        + list(item.get('source_page_indexes') or [item.get('page_index')])
                    )
                    if isinstance(page_index, int)
                })
                merged[-1]['bbox'] = item.get('bbox') or merged[-1].get('bbox')
                merged[-1]['page_height'] = item.get('page_height')
            continue
        merged.append(item)
    return merged


def render_positioned_items(items: list[dict]) -> str:
    chunks = []
    for item in merge_text_items(items):
        if item.get('type') == 'source_image':
            src = item.get('src') or ''
            if src:
                chunks.append(f'![{item.get("alt") or "學習指引原圖"}]({src})')
        elif item.get('type') == 'table':
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
            'image': page_asset_url(level, key, page_index, asset_name),
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


# PDF 文字層把公式攤成「數學斜體碼點（U+1D400–U+1D7FF）＋運算符號」的連續片段，
# 例如「算術平均= 𝑥1 + 𝑥2 + ⋯+ 𝑥𝑛 𝑛」。至少要含兩個數學斜體碼點才算，
# 否則會把「x 軸」這種普通敘述也吃掉。
FLATTENED_MATH_RUN = re.compile(
    r'(?:[\U0001D400-\U0001D7FF][\U0001D400-\U0001D7FF\s0-9a-zA-Z_^(){}\[\],.=+\-*/|∑∏√∫≤≥≠≈±×÷⋯…−]*)'
    r'[\U0001D400-\U0001D7FF][\U0001D400-\U0001D7FF\s0-9a-zA-Z_^(){}\[\],.=+\-*/|∑∏√∫≤≥≠≈±×÷⋯…−]*'
)


def inject_formulas_into_markdown(markdown: str, blocks: list[dict]) -> str:
    """把 content 裡被文字層攤平的公式亂碼換成 $$latex$$。

    為什麼需要這步：`content` 由 render_positioned_items 直接串接文字層字串產生，
    公式在 PDF 文字層裡是一堆數學斜體碼點（「算術平均= 𝑥1 + 𝑥2 + ⋯+ 𝑥𝑛 𝑛」），
    直接呈現給讀者是不能看的。`blocks` 那一路已經有 enrich_guide_blocks 掛上 LaTeX，
    但 `content` 這一路沒有對應處理——歷史上是靠人工 patch 補的
    （commit 3710342「patch LaTeX formulas」，98 處），重跑 export 就會全部消失。

    這裡改成自動化：凡是 enrich 判定為 formulaOnly（整個區塊就是一條公式）且掛上了
    LaTeX 的區塊，就在 content 中把它的原文換成公式。只換 formulaOnly 的區塊，
    夾雜敘述的段落不動，避免把正文吃掉。
    """
    def render(formula: dict) -> str:
        latex = str(formula.get('latex') or '').strip()
        if not latex:
            return ''
        return f'$${latex}$$' if formula.get('display', True) else f'${latex}$'

    replacements: list[tuple[str, str]] = []
    for block in blocks:
        formulas = [f for f in (block.get('formulas') or []) if render(f)]
        text = (block.get('text') or '').strip()
        if not formulas or len(text) < 4:
            continue

        if block.get('formulaOnly'):
            # 整個區塊就是一條公式，整段換掉
            replacements.append((text, '\n\n'.join(render(f) for f in formulas)))
            continue

        # 夾雜敘述的段落：只換掉裡面被攤平的那一段，敘述文字保留。
        # 逐段對應該區塊掛上的公式，數量不足就停手（寧可少換也不要錯位）。
        runs = [m.group(0).strip() for m in FLATTENED_MATH_RUN.finditer(text)]
        for run, formula in zip(runs, formulas):
            if len(run) >= 4:
                replacements.append((run, render(formula)))

    # 長的先換，避免短字串先命中而切斷長字串
    for text, rendered in sorted(replacements, key=lambda pair: -len(pair[0])):
        # 文字層與 content 之間可能有空白差異，用寬鬆的空白比對
        pattern = re.compile(r'[ \t]*'.join(re.escape(part) for part in text.split()))
        markdown = pattern.sub(lambda _m: rendered, markdown)
    return markdown


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
            'image': page_asset_url(level, key, page_index),
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
    audit_formulas_by_page: dict[int, list[dict]] | None = None,
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
            audit_formulas_by_page=audit_formulas_by_page,
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
        prebuilt_blocks = (
            prebuilt_blocks_by_node.get(current_id)
            if prebuilt_blocks_by_node is not None
            else None
        )
        blocks = prebuilt_blocks
        if blocks is None:
            blocks = post_process_guide_blocks(current_id, raw_node.get('title') or '', page_blocks(level, key, start_page, end_page))
        else:
            blocks = refresh_prebuilt_exercise_text(
                blocks,
                level,
                key,
                current_id,
                raw_node.get('title') or '',
                start_page,
                end_page,
            )
        blocks = apply_track_a_block_repairs(
            level,
            key,
            current_id,
            blocks,
            require_prebuilt_matches=prebuilt_blocks is not None,
        )
        blocks = apply_publication_block_overlays(level, key, current_id, blocks)
        blocks = inject_structured_bibliography(blocks, level, key, current_id)
        blocks = inject_semantic_source_images(blocks, level, key, current_id, start_page, end_page)
        blocks = apply_text_repairs(
            level,
            key,
            blocks,
            node=current_id,
            strict=prebuilt_blocks is not None,
        )
        markdown_content = apply_markdown_repairs(level, key, markdown_content)
        markdown_content = apply_markdown_structure_repairs(current_id, markdown_content)
        blocks = enrich_guide_blocks(blocks, audit_formulas_by_page or {})
        blocks = apply_formula_repairs(
            level,
            key,
            blocks,
            node=current_id,
            strict=prebuilt_blocks is not None,
        )
        markdown_content = inject_formulas_into_markdown(markdown_content, blocks)
        markdown_content = apply_publication_markdown_overlays(
            level, key, current_id, markdown_content,
        )
        markdown_content = sync_hypothesis_markdown_tables(
            level, key, current_id, markdown_content, blocks,
        )
        # Final publication pass: every exact matcher above saw the source text.
        markdown_content = normalize_cjk_parentheses(markdown_content)
        blocks = normalize_published_block_parentheses(blocks)
        content_headings = apply_publication_heading_overlays(
            level,
            key,
            current_id,
            markdown_headings(markdown_content),
        )
        write_json(content_dir / content_key / content_ref, {
            'id': current_id,
            'title': raw_node.get('title') or '',
            'content': markdown_content,
            'contentFormat': 'markdown',
            'headings': content_headings,
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


def validate_guide(guide: dict, content_dir: Path, *, asset_root: Path | None = None) -> None:
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
        try:
            content_data = load_json(content_path)
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(
                f'{node_id_value} invalid content JSON: {content_path}'
            ) from exc
        if not isinstance(content_data, dict):
            raise ValueError(f'{node_id_value} content JSON must be an object: {content_path}')
        if content_data.get('id') != node_id_value:
            raise ValueError(f'{node_id_value} content id mismatch: {content_path}')
        content = content_data.get('content')
        if not isinstance(content, str) or not content.strip():
            raise ValueError(f'{node_id_value} content must be non-empty: {content_path}')
        if content_data.get('contentFormat') not in {'plain', 'markdown'}:
            raise ValueError(f'{node_id_value} invalid contentFormat: {content_path}')
        blocks = content_data.get('blocks')
        if not isinstance(blocks, list) or not blocks or not all(isinstance(block, dict) for block in blocks):
            raise ValueError(f'{node_id_value} blocks must be a non-empty object list: {content_path}')
        for block in blocks:
            if block.get('type') != 'source_image':
                continue
            src = str(block.get('src') or '')
            if not src.startswith('/pdf-assets/'):
                raise ValueError(f'{node_id_value} invalid source_image src: {src!r}')
            asset = asset_root / src.lstrip('/') if asset_root is not None else None
            if asset is not None and (not asset.is_file() or asset.stat().st_size <= 0):
                raise ValueError(f'{node_id_value} missing source_image asset: {asset}')
        if not isinstance(content_data.get('sourcePages'), list):
            raise ValueError(f'{node_id_value} sourcePages must be a list: {content_path}')


def export_level(level: str, content_dir: Path) -> dict[str, Any]:
    manifest = load_json(BASE / 'data' / level / 'toc_manifest.json')
    guides = {}
    for subject in manifest['subjects']:
        key = subject['key']
        content_key = f'{level}-{key}'
        outline = load_json(BASE / 'data' / level / 'page_clean' / key / 'outline.json')
        audit_formulas_by_page = load_audit_formula_pages(level, key)
        nodes_by_id: dict[str, dict] = {}
        root_ids = build_nodes(
            level=level,
            subject_id=subject['id'],
            key=key,
            content_key=content_key,
            raw_nodes=filter_duplicate_sibling_nodes(outline['outline']),
            manifest_subject=subject,
            content_dir=content_dir,
            audit_formulas_by_page=audit_formulas_by_page,
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
        audit_formulas_by_page = load_audit_formula_pages(level, key)
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
            audit_formulas_by_page=audit_formulas_by_page,
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


def _undeferred_track_a_failures(semantic: dict[str, Any], deferred: frozenset[str]) -> list[str]:
    """Return staged Track-A failures that are not explicitly deferred for review.

    Deferral covers only inventory items (``TA-NNN: …``).  Publication overlay
    and structure contracts can never be deferred.
    """
    blocking = [
        *semantic['publication_overlay_failures'],
        *semantic['publication_structure_failures'],
    ]
    for failure in semantic['failures']:
        item_id = str(failure).split(':', 1)[0].strip()
        if item_id not in deferred:
            blocking.append(failure)
    return blocking


def export(
    levels: list[str],
    use_guide_tree: bool = False,
    defer_track_a_review: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    generated_dir = BASE / 'frontend' / 'src' / 'generated'
    content_dir = generated_dir / 'guideContent'
    outlines_path = generated_dir / 'guideOutlines.json'
    public_dir = BASE / 'frontend' / 'public'
    generated_dir.mkdir(parents=True, exist_ok=True)

    staged_content_dir = Path(tempfile.mkdtemp(
        prefix='.guideContent.staging-',
        dir=generated_dir,
    ))
    staged_outlines_path = generated_dir / f'.guideOutlines.staging-{uuid.uuid4().hex}.json'
    standard_all_levels = set(levels) == {'初級', '中級'} and len(levels) == 2
    staged_public_root = (
        Path(tempfile.mkdtemp(prefix='.track-a-public.staging-', dir=BASE / 'frontend'))
        if standard_all_levels else None
    )
    staged_asset_paths: list[Path] = []
    try:
        # Start from the live tree so a partial-level export preserves all other
        # levels. Only the explicitly requested level directories are rebuilt.
        if content_dir.exists():
            shutil.copytree(content_dir, staged_content_dir, dirs_exist_ok=True)
        for child in list(staged_content_dir.iterdir()):
            if child.is_dir() and any(child.name.startswith(f'{level}-') for level in levels):
                shutil.rmtree(child)

        existing = load_json(outlines_path) if outlines_path.exists() else {'levels': [], 'guides': {}}
        guides = {
            subject_id: guide
            for subject_id, guide in (existing.get('guides') or {}).items()
            if _guide_level(guide) not in levels
        }
        for level in levels:
            if use_guide_tree:
                guides.update(export_level_from_guide_tree(level, staged_content_dir))
            else:
                guides.update(export_level(level, staged_content_dir))

        merged_levels = list(existing.get('levels') or [])
        for level in levels:
            if level not in merged_levels:
                merged_levels.append(level)
        represented_levels = {_guide_level(guide) for guide in guides.values()}
        merged_levels = [level for level in merged_levels if level in represented_levels]
        for level in sorted(represented_levels - set(merged_levels)):
            if level:
                merged_levels.append(level)

        data = {'levels': merged_levels, 'guides': guides}
        if staged_public_root is not None:
            staged_asset_paths = _stage_track_a_visual_assets(levels, staged_public_root)
        _validate_export(
            data,
            staged_content_dir,
            asset_root=staged_public_root or public_dir,
        )
        if staged_public_root is not None:
            semantic = audit_generated_track_a(
                BASE,
                content_root=staged_content_dir,
                public_root=staged_public_root,
                source_screenshot_root=public_dir,
                check_optional_reading_seed=False,
            )
            if (
                semantic['remaining']
                or semantic['publication_overlay_remaining']
                or semantic['publication_structure_remaining']
            ):
                failures = _undeferred_track_a_failures(semantic, defer_track_a_review)
                if failures:
                    raise ValueError(f'staged Track-A semantic gate failed: {failures}')
                # Explicitly deferred items still fail the standalone
                # track_a_ocr_repairs.py gate and therefore tests/run_all.py:
                # this only lets the rebuild chain continue to page review.
                print(
                    'WARNING: committing with Track-A items deferred for page-image review: '
                    f'{semantic["failures"]}',
                    file=sys.stderr,
                )
        write_json(staged_outlines_path, data)
        _commit_staged_outputs(
            staged_content_dir,
            content_dir,
            staged_outlines_path,
            outlines_path,
            staged_public_root=staged_public_root,
            public_root=public_dir,
            asset_relative_paths=staged_asset_paths,
        )
        return data
    finally:
        # Before commit these are staging paths; after commit they no longer
        # exist. Cleanup never touches the live output names.
        if staged_content_dir.exists():
            shutil.rmtree(staged_content_dir)
        if staged_outlines_path.exists():
            staged_outlines_path.unlink()
        if staged_public_root and staged_public_root.exists():
            shutil.rmtree(staged_public_root)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--level', default='初級', help='資料等級資料夾（預設: 初級）')
    parser.add_argument('--all-levels', action='store_true', help='匯出所有已支援等級')
    parser.add_argument('--use-guide-tree', action='store_true', help='使用 data/{level}/guide_tree/{key}/ 的預建章節樹')
    parser.add_argument(
        '--defer-track-a-review',
        default='',
        help=(
            '逗號分隔的 Track A inventory ID（如 TA-106,TA-107）：只有這些項目失敗時仍允許 commit，'
            '供重建後逐頁審查用。overlay／structure 契約不可延後；'
            'track_a_ocr_repairs.py 與 tests/run_all.py 仍會失敗，直到重新簽章。'
        ),
    )
    args = parser.parse_args()

    deferred = frozenset(
        item.strip() for item in args.defer_track_a_review.split(',') if item.strip()
    )
    bad = sorted(item for item in deferred if not re.fullmatch(r'TA-\d{3}', item))
    if bad:
        parser.error(f'--defer-track-a-review expects TA-NNN IDs, got {bad}')
    levels = ['初級', '中級'] if args.all_levels else [args.level]
    data = export(levels, use_guide_tree=args.use_guide_tree, defer_track_a_review=deferred)
    for guide in data['guides'].values():
        if guide['level'] in levels:
            print(f'{guide["level"]}/{guide["sourceKey"]}: {len(guide["flat"])} guide outline nodes')


if __name__ == '__main__':
    main()
