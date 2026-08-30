#!/usr/bin/env python3
"""Export generated guide infographic metadata for frontend rendering."""

import argparse
import json
from pathlib import Path
from typing import Any
from asset_paths import image_url

BASE = Path(__file__).resolve().parents[1]
DEFAULT_LEVEL = '初級'
DEFAULT_UNITS_FILE = BASE / 'data' / DEFAULT_LEVEL / 'image_units' / 'all_image_units.json'
DEFAULT_OUTPUT = BASE / 'frontend' / 'src' / 'generated' / 'guideImages.json'
PUBLIC_IMAGES_DIR = BASE / 'frontend' / 'public' / 'images'


def load_json(path: Path) -> Any:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def export_images(units_file: Path, output: Path, public_images_dir: Path) -> dict:
    payload = load_json(units_file)
    units = payload.get('units')
    if not isinstance(units, list):
        raise ValueError(f'{units_file} must contain units[]')

    images = []
    missing_files = []
    for unit in units:
        image_output = unit.get('output')
        if not image_output:
            raise ValueError(f'Image unit is missing output: {unit.get("id")}')
        if not (public_images_dir / image_output).exists():
            missing_files.append(image_output)
            continue

        images.append({
            'id': unit.get('id'),
            'level': unit.get('level'),
            'subjectId': unit.get('subjectId'),
            'guideKey': unit.get('guideKey'),
            'sourceNodeId': unit.get('sourceNodeId'),
            'headingBlockId': unit.get('headingBlockId'),
            'headingDepth': unit.get('headingDepth'),
            'title': unit.get('title'),
            'headingPath': unit.get('headingPath') or [],
            'pageNumbers': unit.get('pageNumbers') or [],
            'src': image_url(image_output),
            'output': image_output,
        })

    if missing_files:
        missing = '\n'.join(f'- {name}' for name in missing_files[:20])
        more = '' if len(missing_files) <= 20 else f'\n... and {len(missing_files) - 20} more'
        raise FileNotFoundError(f'Missing generated image files:\n{missing}{more}')

    by_chapter: dict[str, list[dict]] = {}
    for image in images:
        key = f'{image["guideKey"]}:{image["sourceNodeId"]}'
        by_chapter.setdefault(key, []).append(image)

    try:
        source = units_file.relative_to(BASE).as_posix()
    except ValueError:
        source = units_file.as_posix()
    result = {
        'source': source,
        'totalImages': len(images),
        'images': images,
        'byChapter': by_chapter,
    }
    write_json(output, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--units-file', type=Path, default=DEFAULT_UNITS_FILE)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--public-images-dir', type=Path, default=PUBLIC_IMAGES_DIR)
    args = parser.parse_args()

    units_file = args.units_file if args.units_file.is_absolute() else BASE / args.units_file
    output = args.output if args.output.is_absolute() else BASE / args.output
    public_images_dir = (
        args.public_images_dir
        if args.public_images_dir.is_absolute()
        else BASE / args.public_images_dir
    )
    result = export_images(units_file, output, public_images_dir)
    try:
        display_output = output.relative_to(BASE)
    except ValueError:
        display_output = output
    print(f'Exported {result["totalImages"]} guide images to {display_output}')


if __name__ == '__main__':
    main()
