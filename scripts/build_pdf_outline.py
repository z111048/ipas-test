#!/usr/bin/env python3
"""Build a reviewable hierarchical outline from structured per-page PDF extraction."""

import argparse
import json
import re
from pathlib import Path
from typing import Any

BASE = Path('/home/james/projects/ipas-test')

CHAPTER_RE = re.compile(r'^第[一二三四五六七八九十]+章\s+(.+)$')
NUMBERED_RE = re.compile(r'^(?P<num>\d+(?:\.\d+)+)\s*(?P<title>.+?)?$')
TOC_LINE_RE = re.compile(
    r'(?P<num>\d+(?:\.\d+)+)\s*(?P<title>.+?)\s*\.{3,}\s*(?P<label>\d+-\d+)'
)
PAREN_RE = re.compile(r'^（(?P<num>[一二三四五六七八九十\d]+)）\s*(?P<title>.+)$')
LETTER_RE = re.compile(r'^(?P<num>[A-Z])\.\s*(?P<title>.+)$')
PAGE_LABEL_RE = re.compile(r'\b\d+-\d+\b')


def clean_line(line: str) -> str:
    line = line.replace('\uf097', '• ')
    line = re.sub(r'[\ue000-\uf8ff]', '', line)
    line = re.sub(r'\s+', ' ', line)
    return line.strip()


def load_page(path: Path) -> dict:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def iter_page_lines(page: dict) -> list[str]:
    lines = []
    for block in page.get('blocks', []):
        for line in block.get('text', '').split('\n'):
            cleaned = clean_line(line)
            if cleaned:
                lines.append(cleaned)
    return lines


def is_noise(line: str) -> bool:
    return (
        not line
        or line in {'AI'}
        or PAGE_LABEL_RE.fullmatch(line) is not None
        or line.startswith('')
        or re.fullmatch(r'[.\-_= ]{3,}', line) is not None
        or line in {'題號', '答案', '題目'}
    )


def normalize_title(title: str) -> str:
    title = clean_line(title)
    title = re.sub(r'\.{3,}.*$', '', title).strip()
    return title.rstrip('：:').strip()


def title_from_next(lines: list[str], index: int) -> str:
    for candidate in lines[index + 1:index + 4]:
        if not is_noise(candidate) and not NUMBERED_RE.fullmatch(candidate):
            return normalize_title(candidate)
    return ''


def extract_toc_entries(pages: list[dict]) -> list[dict[str, Any]]:
    entries = []
    for page in pages[:5]:
        for raw_line in iter_page_lines(page):
            line = clean_line(raw_line)
            match = TOC_LINE_RE.search(line)
            if not match:
                continue
            num = match.group('num')
            title = normalize_title(match.group('title'))
            entries.append({
                'level': num.count('.') + 1,
                'number': num,
                'title': title,
                'page_label': match.group('label'),
                'source': 'toc',
            })
    return entries


def load_vision_headings(level: str, key: str) -> list[dict[str, Any]]:
    cache_dir = BASE / 'data' / level / 'pages_cache' / key
    if not cache_dir.exists():
        return []
    entries = []
    for path in sorted(cache_dir.glob('page_*.json')):
        if path.name == 'page_index.json':
            continue
        with path.open(encoding='utf-8') as f:
            page = json.load(f)
        if page.get('type') != 'content':
            continue
        for heading in page.get('headings', []):
            title = normalize_title(heading.get('title', ''))
            if not title:
                continue
            entries.append({
                'level': int(heading.get('level', 2)),
                'title': title,
                'page_index': page.get('idx'),
                'page_number': page.get('idx', 0) + 1,
                'page_label': None,
                'source': 'vision',
            })
    return entries


def detect_page_headings(page: dict) -> list[dict[str, Any]]:
    headings = []
    lines = iter_page_lines(page)
    for i, line in enumerate(lines):
        if is_noise(line):
            continue
        chapter = CHAPTER_RE.match(line)
        if chapter:
            headings.append({
                'level': 1,
                'title': normalize_title(chapter.group(1)),
                'page_index': page['page_index'],
                'page_number': page['page_number'],
                'page_label': page.get('page_label'),
                'source': 'page',
            })
            continue

        numbered = NUMBERED_RE.match(line)
        if numbered:
            num = numbered.group('num')
            title = normalize_title(numbered.group('title') or title_from_next(lines, i))
            if title:
                headings.append({
                    'level': num.count('.') + 1,
                    'number': num,
                    'title': title,
                    'page_index': page['page_index'],
                    'page_number': page['page_number'],
                    'page_label': page.get('page_label'),
                    'source': 'page',
                })
            continue

        paren = PAREN_RE.match(line)
        if paren and len(line) <= 80:
            headings.append({
                'level': 3,
                'number': f'（{paren.group("num")}）',
                'title': normalize_title(paren.group('title')),
                'page_index': page['page_index'],
                'page_number': page['page_number'],
                'page_label': page.get('page_label'),
                'source': 'page',
            })
            continue

        letter = LETTER_RE.match(line)
        if letter and len(line) <= 80:
            headings.append({
                'level': 4,
                'number': letter.group('num'),
                'title': normalize_title(letter.group('title')),
                'page_index': page['page_index'],
                'page_number': page['page_number'],
                'page_label': page.get('page_label'),
                'source': 'page',
            })
    return headings


def dedupe(entries: list[dict]) -> list[dict]:
    result = []
    seen = set()
    for entry in entries:
        key = (
            entry.get('level'),
            entry.get('number'),
            entry.get('title'),
            entry.get('page_label'),
            entry.get('page_index'),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(entry)
    return result


def nest_outline(entries: list[dict]) -> list[dict]:
    roots: list[dict] = []
    stack: list[dict] = []
    for entry in entries:
        node = {**entry, 'children': []}
        while stack and stack[-1]['level'] >= node['level']:
            stack.pop()
        if stack:
            stack[-1]['children'].append(node)
        else:
            roots.append(node)
        stack.append(node)
    return roots


def write_markdown(nodes: list[dict], out_path: Path) -> None:
    lines: list[str] = []

    def walk(items: list[dict], depth: int = 0) -> None:
        for item in items:
            loc = item.get('page_label') or item.get('page_number') or '-'
            number = f' {item["number"]}' if item.get('number') else ''
            lines.append(f'{"  " * depth}- L{item["level"]}{number} {item["title"]} ({loc})')
            walk(item.get('children', []), depth + 1)

    walk(nodes)
    out_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def build_outline(level: str, key: str) -> dict:
    base = BASE / 'data' / level / 'page_extract' / key
    page_paths = sorted((base / 'pages').glob('page_*.json'))
    if not page_paths:
        raise FileNotFoundError(f'No structured page JSON found for {key}. Run extract_pdf_pages_structured.py first.')
    pages = [load_page(path) for path in page_paths]
    page_labels = {page['page_index']: page.get('page_label') for page in pages}
    toc_entries = extract_toc_entries(pages)
    vision_entries = load_vision_headings(level, key)
    for entry in vision_entries:
        entry['page_label'] = page_labels.get(entry['page_index'])
    page_entries: list[dict] = []
    for page in pages:
        page_entries.extend(detect_page_headings(page))

    structural_entries = vision_entries if vision_entries else page_entries
    entries = dedupe(toc_entries + structural_entries)
    entries.sort(key=lambda item: (
        item.get('page_index', 10_000),
        item.get('page_number', 10_000),
        item.get('level', 9),
        item.get('number') or '',
        item.get('title') or '',
    ))
    nested = nest_outline(entries)
    return {
        'key': key,
        'entries': entries,
        'outline': nested,
        'stats': {
            'pages': len(pages),
            'toc_entries': len(toc_entries),
            'vision_heading_entries': len(vision_entries),
            'page_heading_entries': len(page_entries),
            'deduped_entries': len(entries),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--level', default='初級', help='資料等級資料夾（預設: 初級）')
    parser.add_argument('--key', help='PDF key, e.g. guide1')
    parser.add_argument('--all', action='store_true', help='build outlines for all extracted PDFs')
    args = parser.parse_args()

    out_dir = BASE / 'data' / args.level / 'outline'
    out_dir.mkdir(parents=True, exist_ok=True)
    if not args.key and not args.all:
        parser.error('Specify --key KEY or --all')

    extract_dir = BASE / 'data' / args.level / 'page_extract'
    keys = [p.name for p in sorted(extract_dir.iterdir()) if (p / 'pages').exists()] if args.all else [args.key]
    combined = {}
    for key in keys:
        result = build_outline(args.level, key)
        json_path = out_dir / f'{key}_outline.json'
        md_path = out_dir / f'{key}_outline.md'
        json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        write_markdown(result['outline'], md_path)
        combined[key] = result['stats']
        print(f'{key}: {result["stats"]} -> {json_path}, {md_path}')
    (out_dir / 'summary.json').write_text(
        json.dumps(combined, ensure_ascii=False, indent=2), encoding='utf-8'
    )


if __name__ == '__main__':
    main()
