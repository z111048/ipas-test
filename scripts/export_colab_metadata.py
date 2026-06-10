#!/usr/bin/env python3
"""Export Colab notebook metadata from notebooks/ to frontend/src/generated/colabNotebooks/.

Reads .ipynb files under notebooks/{level}/ and extracts the lightweight
cell metadata needed by the frontend (strips execution outputs etc.).

Usage:
  python3 scripts/export_colab_metadata.py --level 中級
  python3 scripts/export_colab_metadata.py --level 中級 --chapter mid-s2c1
"""

import argparse
import json
import logging
import sys
from pathlib import Path

BASE = Path('/home/james/projects/ipas-test')
GITHUB_REPO = 'z111048/ipas-test'

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger(__name__)


def colab_url(level: str, chapter_id: str) -> str:
    return (
        f'https://colab.research.google.com/github/{GITHUB_REPO}'
        f'/blob/main/notebooks/{level}/{chapter_id}.ipynb'
    )


def ipynb_to_metadata(ipynb_path: Path, level: str) -> dict | None:
    """Convert .ipynb to lightweight frontend metadata JSON."""
    try:
        ipynb = json.loads(ipynb_path.read_text(encoding='utf-8'))
    except Exception as e:
        log.error(f'Failed to read {ipynb_path}: {e}')
        return None

    chapter_id = ipynb_path.stem
    title = ''
    cells: list[dict] = []

    for nb_cell in ipynb.get('cells', []):
        source = ''.join(nb_cell.get('source', []))
        if nb_cell['cell_type'] == 'markdown':
            # Extract title from first markdown cell if not set
            if not title:
                for line in source.split('\n'):
                    stripped = line.lstrip('#').strip()
                    if stripped and not stripped.startswith('📌'):
                        title = stripped
                        break
            cells.append({'type': 'markdown', 'content': source.strip()})
        elif nb_cell['cell_type'] == 'code':
            # Parse structured comments back into fields
            lines = source.split('\n')
            cell_title = ''
            explanation_lines: list[str] = []
            code_lines: list[str] = []
            in_explanation = False

            for line in lines:
                if line.startswith('# ── ') and '─' in line:
                    # Title line: "# ── Section title ────"
                    cell_title = line[5:].split('─')[0].strip()
                    in_explanation = True
                elif in_explanation and line.startswith('# ') and line != '#':
                    explanation_lines.append(line[2:])
                elif in_explanation and line == '':
                    # Blank line ends explanation block
                    if explanation_lines:
                        in_explanation = False
                    code_lines.append(line)
                else:
                    in_explanation = False
                    code_lines.append(line)

            # Trim leading/trailing blank lines from code
            while code_lines and not code_lines[0].strip():
                code_lines.pop(0)
            while code_lines and not code_lines[-1].strip():
                code_lines.pop()

            cells.append({
                'type': 'code',
                'title': cell_title or '',
                'explanation': '\n'.join(explanation_lines).strip(),
                'content': '\n'.join(code_lines),
            })

    if not title:
        title = chapter_id

    return {
        'chapter_id': chapter_id,
        'chapter_title': title,
        'colab_url': colab_url(level, chapter_id),
        'cells': cells,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description='Export Colab metadata to frontend JSON')
    parser.add_argument('--level', default='中級')
    parser.add_argument('--chapter', help='specific chapter id')
    args = parser.parse_args()

    level = args.level
    notebooks_dir = BASE / 'notebooks' / level
    frontend_dir = BASE / 'frontend' / 'src' / 'generated' / 'colabNotebooks' / level
    frontend_dir.mkdir(parents=True, exist_ok=True)

    if not notebooks_dir.exists():
        log.error(f'Notebooks directory not found: {notebooks_dir}')
        sys.exit(1)

    ipynb_files = sorted(notebooks_dir.glob('*.ipynb'))
    if args.chapter:
        ipynb_files = [f for f in ipynb_files if f.stem == args.chapter]

    if not ipynb_files:
        log.warning(f'No .ipynb files found in {notebooks_dir}')
        sys.exit(0)

    count = 0
    for ipynb_path in ipynb_files:
        meta = ipynb_to_metadata(ipynb_path, level)
        if meta is None:
            continue
        out = frontend_dir / f'{ipynb_path.stem}.json'
        out.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
        log.info(f'✓ {ipynb_path.stem} → {out} ({len(meta["cells"])} cells)')
        count += 1

    log.info(f'完成：{count} notebooks exported to {frontend_dir}')


if __name__ == '__main__':
    main()
