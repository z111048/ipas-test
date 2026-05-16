#!/usr/bin/env python3
"""Export cropped PDF image/table assets to frontend/public with a gallery manifest."""

import argparse
import json
import shutil
from pathlib import Path

BASE = Path('/home/james/projects/ipas-test')
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


def load_json(path: Path) -> dict:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


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
                        'path': f'/pdf-assets/{level}/{dest_rel.as_posix()}',
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
                        'path': f'/pdf-assets/{level}/{dest_rel.as_posix()}',
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
    manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2)
    manifest_path = public_root / 'gallery.json'
    manifest_path.write_text(manifest_text, encoding='utf-8')

    if write_src_manifest:
        src_manifest_path = BASE / 'frontend' / 'src' / 'generated' / 'pdfGallery.json'
        src_manifest_path.parent.mkdir(parents=True, exist_ok=True)
        src_manifest_path.write_text(manifest_text, encoding='utf-8')
    return manifest


def export_galleries(levels: list[str], force: bool) -> dict:
    all_items = []
    for level in levels:
        manifest = export_gallery(level, force, write_src_manifest=False)
        all_items.extend(manifest['items'])

    all_items.sort(key=lambda item: (
        levels.index(item['path'].split('/')[2]) if item['path'].split('/')[2] in levels else len(levels),
        KEY_ORDER.get(item['key'], len(KEY_ORDER)),
        TYPE_ORDER.get(item['type'], len(TYPE_ORDER)),
        item['page_number'],
        item['asset_id'],
    ))
    manifest = {
        'levels': levels,
        'total': len(all_items),
        'items': all_items,
    }
    src_manifest_path = BASE / 'frontend' / 'src' / 'generated' / 'pdfGallery.json'
    src_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    src_manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return manifest


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
