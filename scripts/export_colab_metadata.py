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

BASE = Path(__file__).resolve().parents[1]
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

    write_index(frontend_dir.parent)


def write_index(root: Path) -> None:
    """重建 colabNotebooks/index.json。

    這份 index 是「這一章有沒有 notebook」的唯一機讀來源。GuidePage 原本靠
    `import.meta.glob` 的 build-time 查表判斷存在性；資料改成 runtime fetch 之後
    那張表會消失，沒有 index 就只剩「每章都打一次 404」或「功能靜默消失」兩條路。

    刻意掃「整個 colabNotebooks/ 目錄」而不是只掃這次跑的 level——
    `--level 初級 --chapter s1c1` 這種單章重跑不能把中級從 index 裡洗掉。
    """
    levels: list[str] = []
    notebooks: list[dict] = []
    for level_dir in sorted(d for d in root.iterdir() if d.is_dir()):
        level = level_dir.name
        found = False
        for path in sorted(level_dir.glob('*.json')):
            if path.name == 'index.json':
                continue
            data = json.loads(path.read_text(encoding='utf-8'))
            notebooks.append({
                'chapterId': data.get('chapter_id', path.stem),
                'level': level,
                'title': data.get('chapter_title', ''),
                'colabUrl': data.get('colab_url', ''),
                'cells': len(data.get('cells', [])),
            })
            found = True
        if found:
            levels.append(level)

    index = {
        'levels': levels,
        'total': len(notebooks),
        # chapterId → 章節資訊。前端用 `chapterId in byChapter` 判斷存在性。
        'byChapter': {n['chapterId']: n for n in notebooks},
    }
    out = root / 'index.json'
    out.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding='utf-8')
    log.info(f'✓ index.json → {out}（{len(notebooks)} 章、{len(levels)} 個 level）')


if __name__ == '__main__':
    main()
