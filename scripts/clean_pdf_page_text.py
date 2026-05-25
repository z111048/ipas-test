#!/usr/bin/env python3
"""Clean extracted PDF page text and rebuild per-PDF hierarchical outlines."""

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BASE = Path('/home/james/projects/ipas-test')

PAGE_LABEL_RE = re.compile(r'^\d+-\d+$')
GUIDE_PAGE_TITLE_RE = re.compile(r'^第[一二三四五六七八九十]+章\s+.+$')
GUIDE_NUMBERED_RE = re.compile(r'^(?P<num>\d+(?:\.\d+)*)(?:\s+(?P<title>.+))?$')
GUIDE_TOC_RE = re.compile(r'(?P<num>\d+(?:\.\d+)*)\s+(?P<title>.+?)\s*\.{3,}\s*(?P<label>[A-Z]?-?\d+-\d+)')
EXAM_HEADER_RE = re.compile(r'^(?:114 年|第一科|第二科|考試日期|試題公告日期|第\s*\d+\s*頁，共\s*\d+\s*頁)')
QUESTION_RE = re.compile(r'^\d+[.、]\s*')
OPTION_RE = re.compile(r'^\([A-D]\)')


@dataclass(frozen=True)
class Strategy:
    name: str
    kind: str


STRATEGIES = {
    'guide1': Strategy('guide', 'guide'),
    'guide2': Strategy('guide', 'guide'),
    'exam1': Strategy('exam', 'exam'),
    'exam2': Strategy('exam', 'exam'),
    'exam3': Strategy('exam', 'exam'),
    'sample': Strategy('sample_exam', 'exam'),
    'errata': Strategy('errata', 'guide'),
    'briefing': Strategy('briefing', 'guide'),
}


def load_json(path: Path) -> dict:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def clean_line(line: str) -> str:
    line = (
        line
        .replace('\uf097', '• ')
        .replace('\uf09f', '• ')
        .replace('\uf077', '◦ ')
        .replace('\uf0a1', '○ ')
    )
    line = re.sub(r'[\ue000-\uf8ff]', '', line)
    line = re.sub(r'[ \t]+', ' ', line)
    return line.strip()


def page_lines(page: dict) -> list[str]:
    return [cleaned for line in page.get('text', '').splitlines() if (cleaned := clean_line(line))]


def is_lone_page_number(line: str) -> bool:
    return re.fullmatch(r'\d{1,3}', line) is not None


def is_common_noise(line: str) -> bool:
    return (
        not line
        or PAGE_LABEL_RE.fullmatch(line) is not None
        or re.fullmatch(r'[.\-_= ]{3,}', line) is not None
        or line in {'題號', '答案', '題目', '題 目', '題號 答案'}
    )


def is_exam_header_footer(line: str) -> bool:
    return is_common_noise(line) or is_lone_page_number(line) or EXAM_HEADER_RE.match(line) is not None


def is_guide_header_footer(line: str) -> bool:
    return is_common_noise(line) or is_lone_page_number(line)


def trim_edges(lines: list[str], strategy: Strategy) -> tuple[list[str], list[str], list[str]]:
    if strategy.kind == 'guide':
        is_noise = is_guide_header_footer
    else:
        is_noise = is_exam_header_footer

    start = 0
    while start < len(lines) and is_noise(lines[start]):
        start += 1
    end = len(lines)
    while end > start and is_noise(lines[end - 1]):
        end -= 1
    return lines[:start], lines[start:end], lines[end:]


def remove_inline_noise(lines: list[str], strategy: Strategy) -> tuple[list[str], list[str]]:
    kept = []
    removed = []
    for index, line in enumerate(lines):
        remove = False
        if strategy.kind == 'guide':
            remove = PAGE_LABEL_RE.fullmatch(line) is not None or (
                is_lone_page_number(line)
                and index <= 2
            )
        else:
            remove = is_exam_header_footer(line)
        if remove:
            removed.append(line)
        else:
            kept.append(line)
    return kept, removed


def normalize_title(title: str) -> str:
    title = clean_line(title)
    title = re.sub(r'\.{3,}.*$', '', title)
    return title.rstrip('：:').strip()


def heading_from_lines(
    lines: list[str],
    index: int,
    page: dict,
    strategy: Strategy,
    toc_title_by_number: dict[str, str],
) -> list[dict]:
    line = lines[index]
    result = []
    if '...' in line:
        return result
    if strategy.kind == 'guide':
        if GUIDE_PAGE_TITLE_RE.match(line):
            result.append({
                'level': 1,
                'number': None,
                'title': normalize_title(line),
                'page_index': page['page_index'],
                'page_number': page['page_number'],
                'page_label': page.get('page_label') or '',
                'source': 'page',
            })
        match = GUIDE_NUMBERED_RE.match(line)
        if match:
            number = match.group('num')
            title = normalize_title(toc_title_by_number.get(number) or match.group('title') or '')
            if not title and index + 1 < len(lines):
                candidate = lines[index + 1]
                if not GUIDE_NUMBERED_RE.fullmatch(candidate):
                    title = normalize_title(candidate)
            if title and number.count('.') > 0:
                level = number.count('.') + 1
                result.append({
                    'level': level,
                    'number': number,
                    'title': title,
                    'page_index': page['page_index'],
                    'page_number': page['page_number'],
                    'page_label': page.get('page_label') or '',
                    'source': 'page',
                })
    elif QUESTION_RE.match(line):
        title = normalize_title(line)
        if re.fullmatch(r'\d+[.、]', title):
            for candidate in lines[index + 1:index + 5]:
                if re.fullmatch(r'[A-D]', candidate):
                    continue
                if not is_exam_header_footer(candidate):
                    title = normalize_title(f'{title} {candidate}')
                    break
        result.append({
            'level': 1,
            'number': QUESTION_RE.match(line).group(0).rstrip('.、 '),
            'title': title,
            'page_index': page['page_index'],
            'page_number': page['page_number'],
            'page_label': page.get('page_label') or '',
            'source': 'question',
        })
    return result


def detect_headings(
    page: dict,
    lines: list[str],
    strategy: Strategy,
    toc_title_by_number: dict[str, str],
) -> list[dict]:
    headings = []
    for index in range(len(lines)):
        headings.extend(heading_from_lines(lines, index, page, strategy, toc_title_by_number))
    return headings


def extract_toc_entries(pages: list[dict], strategy: Strategy) -> list[dict]:
    if strategy.kind != 'guide':
        return []
    entries = []
    for page in pages[:6]:
        for line in page.get('cleaned_lines', []):
            match = GUIDE_TOC_RE.search(line)
            if not match:
                continue
            number = match.group('num')
            entries.append({
                'level': number.count('.') + 1,
                'number': number,
                'title': normalize_title(match.group('title')),
                'page_label': match.group('label'),
                'page_index': None,
                'page_number': None,
                'source': 'toc',
            })
    return entries


def starts_new_unit(page: dict) -> bool:
    lines = page.get('cleaned_lines', [])
    if not lines:
        return False
    first = lines[0]
    return (
        GUIDE_PAGE_TITLE_RE.match(first) is not None
        or GUIDE_NUMBERED_RE.match(first) is not None and '.' in first.split(maxsplit=1)[0]
        or QUESTION_RE.match(first) is not None
        or first in {'序', '目錄'}
    )


def line_looks_continued(line: str) -> bool:
    if not line:
        return False
    if line.endswith(('：', ':')):
        return True
    if line.endswith(('。', '？', '！', '；', ')', '）')):
        return False
    if OPTION_RE.match(line) or QUESTION_RE.match(line):
        return False
    return True


def enrich_guide_number_lines(page: dict, toc_title_by_number: dict[str, str]) -> None:
    if page.get('strategy') != 'guide':
        return
    enriched = []
    changed = False
    for line in page.get('cleaned_lines', []):
        match = GUIDE_NUMBERED_RE.fullmatch(line)
        if match and match.group('num') in toc_title_by_number and not match.group('title'):
            enriched.append(f'{match.group("num")} {toc_title_by_number[match.group("num")]}')
            changed = True
        else:
            enriched.append(line)
    if changed:
        page['cleaned_lines'] = enriched
        page['cleaned_text'] = '\n'.join(enriched).strip()
        page['cleaned_text_chars'] = len(page['cleaned_text'])


def add_continuation_flags(pages: list[dict]) -> None:
    for index, page in enumerate(pages):
        prev_page = pages[index - 1] if index > 0 else None
        next_page = pages[index + 1] if index + 1 < len(pages) else None
        lines = page.get('cleaned_lines', [])
        first = lines[0] if lines else ''
        last = lines[-1] if lines else ''

        page['continues_from_previous'] = bool(
            prev_page
            and lines
            and not starts_new_unit(page)
            and not OPTION_RE.match(first)
            and not QUESTION_RE.match(first)
        )
        page['continues_to_next'] = bool(
            next_page
            and lines
            and (
                not starts_new_unit(next_page)
                or line_looks_continued(last)
            )
        )


def attach_page_ranges(entries: list[dict], total_pages: int) -> list[dict]:
    page_entries = [entry for entry in entries if entry.get('page_index') is not None]
    for index, entry in enumerate(page_entries):
        next_entry = next(
            (
                candidate
                for candidate in page_entries[index + 1:]
                if candidate.get('level', 99) <= entry.get('level', 99)
            ),
            None,
        )
        start_page = entry['page_number']
        end_page = (next_entry['page_number'] - 1) if next_entry else total_pages
        entry['page_range'] = [
            start_page,
            max(start_page, end_page),
        ]
    return entries


def dedupe_entries(entries: list[dict]) -> list[dict]:
    seen = set()
    seen_guide_running_titles = set()
    result = []
    for entry in entries:
        if entry.get('source') == 'page' and not entry.get('number'):
            title_key = normalize_title(entry.get('title') or '')
            if title_key in seen_guide_running_titles:
                continue
            seen_guide_running_titles.add(title_key)
        key = (
            entry.get('level'),
            entry.get('number'),
            entry.get('title'),
            entry.get('page_label'),
            entry.get('page_number'),
            entry.get('source'),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(entry)
    return result


def nest_entries(entries: list[dict]) -> list[dict]:
    roots = []
    stack = []
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


def write_outline_markdown(nodes: list[dict], path: Path) -> None:
    lines = []

    def walk(items: list[dict], depth: int = 0) -> None:
        for item in items:
            number = f' {item["number"]}' if item.get('number') else ''
            page = item.get('page_label') or item.get('page_number') or '-'
            lines.append(f'{"  " * depth}- L{item["level"]}{number} {item["title"]} ({page})')
            walk(item.get('children', []), depth + 1)

    walk(nodes)
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def clean_pdf(level: str, key: str) -> dict:
    strategy = STRATEGIES.get(key, Strategy('generic', 'guide'))
    source_dir = BASE / 'data' / level / 'page_extract' / key / 'pages'
    out_dir = BASE / 'data' / level / 'page_clean' / key
    page_out_dir = out_dir / 'pages'
    page_paths = sorted(source_dir.glob('page_*.json'))
    if not page_paths:
        raise FileNotFoundError(f'No page extraction found for {key}: {source_dir}')

    cleaned_pages = []
    toc_title_by_number: dict[str, str] = {}
    for path in page_paths:
        page = load_json(path)
        raw_lines = page_lines(page)
        removed_prefix, middle, removed_suffix = trim_edges(raw_lines, strategy)
        cleaned_lines, removed_inline = remove_inline_noise(middle, strategy)
        cleaned_text = '\n'.join(cleaned_lines).strip()
        cleaned = {
            'key': key,
            'pdf': page['pdf'],
            'strategy': strategy.name,
            'page_index': page['page_index'],
            'page_number': page['page_number'],
            'page_label': page.get('page_label') or '',
            'raw_text_chars': len(page.get('text') or ''),
            'cleaned_text_chars': len(cleaned_text),
            'raw_lines': raw_lines,
            'cleaned_lines': cleaned_lines,
            'cleaned_text': cleaned_text,
            'removed': {
                'prefix_lines': removed_prefix,
                'inline_lines': removed_inline,
                'suffix_lines': removed_suffix,
            },
            'headings': [],
            'markers': page.get('markers', []),
            'page_image': page.get('page_image'),
        }
        cleaned_pages.append(cleaned)

    toc_entries = extract_toc_entries(cleaned_pages, strategy)
    toc_title_by_number = {
        entry['number']: entry['title']
        for entry in toc_entries
        if entry.get('number') and entry.get('title')
    }
    for page in cleaned_pages:
        enrich_guide_number_lines(page, toc_title_by_number)
        page['headings'] = detect_headings(page, page['cleaned_lines'], strategy, toc_title_by_number)

    add_continuation_flags(cleaned_pages)
    for page in cleaned_pages:
        write_json(page_out_dir / f'page_{page["page_index"]:03d}.json', page)

    page_entries = [heading for page in cleaned_pages for heading in page['headings']]
    toc_numbers_with_page_entry = {
        entry.get('number')
        for entry in page_entries
        if entry.get('number')
    }
    missing_toc_entries = [
        entry
        for entry in toc_entries
        if entry.get('number') not in toc_numbers_with_page_entry
    ]
    entries = dedupe_entries(missing_toc_entries + page_entries)
    entries.sort(key=lambda item: (
        item.get('page_index') if item.get('page_index') is not None else -1,
        item.get('page_number') or -1,
        item.get('level') or 99,
        item.get('number') or '',
        item.get('title') or '',
    ))
    attach_page_ranges(entries, len(cleaned_pages))
    outline = nest_entries(entries)
    result = {
        'key': key,
        'strategy': strategy.name,
        'pages': len(cleaned_pages),
        'stats': {
            'raw_text_chars': sum(page['raw_text_chars'] for page in cleaned_pages),
            'cleaned_text_chars': sum(page['cleaned_text_chars'] for page in cleaned_pages),
            'toc_entries': len(toc_entries),
            'page_heading_entries': len(page_entries),
            'outline_entries': len(entries),
            'continuation_from_previous': sum(1 for page in cleaned_pages if page['continues_from_previous']),
            'continuation_to_next': sum(1 for page in cleaned_pages if page['continues_to_next']),
        },
        'entries': entries,
        'outline': outline,
    }
    write_json(out_dir / 'outline.json', result)
    write_outline_markdown(outline, out_dir / 'outline.md')
    write_json(out_dir / 'summary.json', {
        'key': key,
        'strategy': strategy.name,
        'pages': result['pages'],
        'stats': result['stats'],
    })
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--level', default='初級', help='資料等級資料夾（預設: 初級）')
    parser.add_argument('--key', help='只處理指定 PDF key，如 guide1/exam1/sample')
    parser.add_argument('--all', action='store_true', help='處理所有 page_extract PDF')
    args = parser.parse_args()

    extract_dir = BASE / 'data' / args.level / 'page_extract'
    if not args.key and not args.all:
        parser.error('Specify --key KEY or --all')
    keys = [p.name for p in sorted(extract_dir.iterdir()) if (p / 'pages').exists()] if args.all else [args.key]
    summary = {}
    for key in keys:
        result = clean_pdf(args.level, key)
        summary[key] = result['stats']
        print(f'{key}: {result["pages"]} pages, {result["stats"]}')
    write_json(BASE / 'data' / args.level / 'page_clean' / 'summary.json', summary)


if __name__ == '__main__':
    main()
