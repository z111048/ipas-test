#!/usr/bin/env python3
"""Export cropped PDF image/table assets to frontend/public with a gallery manifest."""

import argparse
import json
import shutil
import uuid
from pathlib import Path
from asset_paths import pdf_asset_url

BASE = Path(__file__).resolve().parents[1]
KEY_ORDER = {
    'guide1': 0,
    'guide2': 1,
    'guide3': 2,
    'errata': 3,
    'briefing': 4,
    'sample': 5,
    'exam1': 6,
    'exam2': 7,
    'exam3': 8,
}
TYPE_ORDER = {'page': 0, 'image': 1, 'table': 2}
LEVEL_ORDER = {'初級': 0, '中級': 1, '共用': 2}


def load_json(path: Path) -> dict:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def merge_gallery_manifests(existing: dict, replacements: list[dict]) -> dict:
    """Replace selected levels while retaining every untouched level."""
    replacement_levels = {manifest['level'] for manifest in replacements}
    items = [
        item
        for item in existing.get('items', [])
        if item.get('level') not in replacement_levels
    ]
    for manifest in replacements:
        items.extend(manifest.get('items', []))

    existing_levels = list(existing.get('levels') or [])
    if not existing_levels and existing.get('level'):
        existing_levels = [existing['level']]
    levels = [level for level in existing_levels if level not in replacement_levels]
    for manifest in replacements:
        if manifest['level'] not in levels:
            levels.append(manifest['level'])
    present_levels = {item.get('level') for item in items if item.get('level')}
    levels = [level for level in levels if level in present_levels or level in replacement_levels]
    for level in sorted(present_levels - set(levels), key=lambda value: (LEVEL_ORDER.get(value, 999), value)):
        levels.append(level)
    levels.sort(key=lambda value: (LEVEL_ORDER.get(value, 999), value))

    items.sort(key=lambda item: (
        LEVEL_ORDER.get(item.get('level'), 999),
        item.get('level', ''),
        KEY_ORDER.get(item['key'], len(KEY_ORDER)),
        TYPE_ORDER.get(item['type'], len(TYPE_ORDER)),
        item['page_number'],
        item['asset_id'],
    ))
    return {'levels': levels, 'total': len(items), 'items': items}


def write_combined_manifest(replacements: list[dict]) -> dict:
    """Atomically merge selected levels into the frontend gallery manifest."""
    path = BASE / 'frontend' / 'src' / 'generated' / 'pdfGallery.json'
    existing = load_json(path) if path.exists() else {'levels': [], 'items': []}
    merged = merge_gallery_manifests(existing, replacements)
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.with_name(f'.{path.name}.staging-{uuid.uuid4().hex}')
    try:
        staged.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding='utf-8')
        staged.replace(path)
    finally:
        if staged.exists():
            staged.unlink()
    return merged


def export_gallery(level: str, force: bool, write_src_manifest: bool = True) -> dict:
    source_root = BASE / 'data' / level / 'page_extract'
    public_root = BASE / 'frontend' / 'public' / 'pdf-assets' / level
    if force and public_root.exists():
        shutil.rmtree(public_root)
    public_root.mkdir(parents=True, exist_ok=True)

    items = []
    for key_dir in sorted(path for path in source_root.iterdir() if path.is_dir()):
        key = key_dir.name
        pages_dir = key_dir / 'pages'
        if not pages_dir.exists():
            continue
        for page_path in sorted(pages_dir.glob('page_*.json')):
            page = load_json(page_path)
            page_image = page.get('page_image')
            if page_image and page_image.get('path'):
                source_path = (page_path.parent / page_image['path']).resolve()
                if source_path.exists():
                    dest_rel = Path(key) / f'page_{page["page_index"]:03d}' / source_path.name
                    dest_path = public_root / dest_rel
                    if force or not dest_path.exists():
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source_path, dest_path)
                    items.append({
                        'id': f'{level}-{key}-p{page["page_index"]:03d}-page',
                        'level': level,
                        'key': key,
                        'pdf': page['pdf'],
                        'type': 'page',
                        'asset_id': 'page',
                        'page_index': page['page_index'],
                        'page_number': page['page_number'],
                        'page_label': page.get('page_label') or '',
                        'bbox': page_image.get('bbox', []),
                        'path': pdf_asset_url(level, dest_rel.as_posix()),
                    })
            for kind in ('images', 'tables'):
                for asset in page.get(kind, []):
                    rel_source = asset.get('path')
                    if not rel_source:
                        continue
                    source_path = (page_path.parent / rel_source).resolve()
                    if not source_path.exists():
                        continue
                    item_type = 'image' if kind == 'images' else 'table'
                    dest_rel = Path(key) / f'page_{page["page_index"]:03d}' / source_path.name
                    dest_path = public_root / dest_rel
                    if force or not dest_path.exists():
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source_path, dest_path)
                    items.append({
                        'id': f'{level}-{key}-p{page["page_index"]:03d}-{asset["id"]}',
                        'level': level,
                        'key': key,
                        'pdf': page['pdf'],
                        'type': item_type,
                        'asset_id': asset['id'],
                        'page_index': page['page_index'],
                        'page_number': page['page_number'],
                        'page_label': page.get('page_label') or '',
                        'bbox': asset.get('bbox', []),
                        'path': pdf_asset_url(level, dest_rel.as_posix()),
                    })

    items.sort(key=lambda item: (
        KEY_ORDER.get(item['key'], len(KEY_ORDER)),
        TYPE_ORDER.get(item['type'], len(TYPE_ORDER)),
        item['page_number'],
        item['asset_id'],
    ))

    manifest = {
        'level': level,
        'total': len(items),
        'items': items,
    }
    # 2026-08-26：不再寫 public_root/gallery.json。前端唯一的消費者是
    # ImageGalleryPage.tsx，讀的是下面那份 generated/pdfGallery.json；
    # public 那份（三個 level 合計 589 KB）從來沒有人讀過，已從版控刪除。

    if write_src_manifest:
        write_combined_manifest([manifest])
    return manifest


def export_galleries(levels: list[str], force: bool) -> dict:
    manifests = []
    for level in levels:
        manifest = export_gallery(level, force, write_src_manifest=False)
        manifests.append(manifest)
    return write_combined_manifest(manifests)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--level', default='初級', help='資料等級資料夾（預設: 初級）')
    parser.add_argument('--all-levels', action='store_true', help='匯出所有已支援等級')
    parser.add_argument('--force', action='store_true', help='overwrite copied public assets')
    args = parser.parse_args()

    if args.all_levels:
        manifest = export_galleries(['初級', '中級', '共用'], args.force)
        print(f'Exported {manifest["total"]} image/table assets across {", ".join(manifest["levels"])}')
    else:
        manifest = export_gallery(args.level, args.force)
        print(f'Exported {manifest["total"]} image/table assets to frontend/public/pdf-assets/{args.level}')


if __name__ == '__main__':
    main()
