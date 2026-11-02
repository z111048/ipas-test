#!/usr/bin/env python3
"""Export generated guide infographic metadata for frontend rendering."""

import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Any
from asset_paths import image_url
from guide_block_id_migrations import BlockIdMigration, sha256_bytes

BASE = Path(__file__).resolve().parents[1]
DEFAULT_LEVEL = '初級'
DEFAULT_UNITS_FILE = BASE / 'data' / DEFAULT_LEVEL / 'image_units' / 'all_image_units.json'
DEFAULT_OUTPUT = BASE / 'frontend' / 'src' / 'generated' / 'guideImages.json'
PUBLIC_IMAGES_DIR = BASE / 'frontend' / 'public' / 'images'

# Every image unit's headingBlockId must point at a heading block whose title
# matches the unit title (NFKC, whitespace and one leading numbering prefix
# ignored). Exceptions need an entry here: unit id -> {'headingBlockId': the
# exact id being excused, 'reason': why the mismatch is correct}. Unused or
# stale entries fail too. Empty since the 2026-11-02 realignment (171 ids in
# data/共用/image_units_all_levels.json rebased by title onto the current
# guideContent; every one of the 727 units matches).
HEADING_TITLE_ALLOWLIST: dict[str, dict[str, str]] = {}

_HEADING_NUMBER_RE = re.compile(
    r'^(?:第[一二三四五六七八九十百零〇0-9]+[章節篇部]'
    r'|[0-9]+(?:\.[0-9]+)*\.?'
    r'|\(?[0-9一二三四五六七八九十]+\)'
    r'|[一二三四五六七八九十]+[、.]'
    r'|[A-Za-z][.)])'
)


class HeadingAlignmentError(ValueError):
    """An image unit is anchored to a block that is not its heading."""


def normalize_heading_title(text: str | None) -> str:
    value = re.sub(r'\s+', '', unicodedata.normalize('NFKC', text or ''))
    return _HEADING_NUMBER_RE.sub('', value, count=1)


def check_heading_alignment(
    units: list[dict],
    content: dict[str, dict[str, list[dict]]],
    allowlist: dict[str, dict[str, str]] | None = None,
) -> None:
    """Fail closed unless each unit's headingBlockId is the heading it is titled after."""
    allowlist = HEADING_TITLE_ALLOWLIST if allowlist is None else allowlist
    errors: list[str] = []
    used: set[str] = set()
    for unit in units:
        unit_id = str(unit.get('id'))
        guide = f"{unit.get('level')}-{unit.get('guideKey')}"
        node = str(unit.get('sourceNodeId') or '')
        block_id = unit.get('headingBlockId')
        blocks = (content.get(guide) or {}).get(node)
        where = f'image unit {unit_id} {guide}/{node} headingBlockId {block_id}'
        if blocks is None:
            errors.append(f'{where}: node is not in the current guideContent')
            continue
        block = next((b for b in blocks if b.get('id') == block_id), None)
        if block is None:
            problem = 'block does not exist'
        elif block.get('type') != 'heading':
            problem = f"points at a {block.get('type')} block, not a heading"
        elif normalize_heading_title(block.get('title')) != normalize_heading_title(unit.get('title')):
            problem = f"heading {block.get('title')!r} does not match unit title {unit.get('title')!r}"
        else:
            problem = None
        exception = allowlist.get(unit_id)
        if exception is not None:
            if not str(exception.get('reason') or '').strip():
                errors.append(f'{where}: allowlist entry lacks a reason')
            elif exception.get('headingBlockId') != block_id:
                errors.append(f"{where}: allowlist entry is for {exception.get('headingBlockId')}")
            elif problem is None:
                errors.append(f'{where}: allowlisted but already aligned; drop the entry')
            else:
                used.add(unit_id)
            continue
        if problem:
            errors.append(f'{where}: {problem}')
    for unit_id in sorted(set(allowlist) - used - {str(u.get('id')) for u in units}):
        errors.append(f'allowlist entry {unit_id}: no such image unit')
    if errors:
        shown = '\n'.join(f'- {error}' for error in errors[:30])
        more = '' if len(errors) <= 30 else f'\n... and {len(errors) - 30} more'
        raise HeadingAlignmentError(
            f'{len(errors)} image unit(s) not anchored to their heading:\n{shown}{more}'
        )


def load_json(path: Path) -> Any:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def units_scope_key(units_file: Path) -> str:
    try:
        return units_file.resolve().relative_to(BASE).as_posix()
    except ValueError:
        return units_file.as_posix()


def export_images(
    units_file: Path,
    output: Path,
    public_images_dir: Path,
    migration: BlockIdMigration | None = None,
) -> dict:
    payload = load_json(units_file)
    units = payload.get('units')
    if not isinstance(units, list):
        raise ValueError(f'{units_file} must contain units[]')
    # Image units are generated once (export_guide_image_units.py is not rerun);
    # remap their headingBlockId to the current guideContent and fail closed.
    if migration is None:
        migration = BlockIdMigration.load(
            table_path=BASE / 'data/guide_block_id_migrations.json',
            overrides_path=BASE / 'data/guide_citation_overrides.json',
            content_root=BASE / 'frontend/src/generated/guideContent',
        )
    units, remapped = migration.migrate_heading_block_ids(
        units,
        scope_key=units_scope_key(units_file),
        digest=sha256_bytes(units_file.read_bytes()),
    )
    if remapped:
        print(f'INFO remapped {remapped} image-unit headingBlockId(s) via block-id migration')
    check_heading_alignment(units, migration.content)

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
