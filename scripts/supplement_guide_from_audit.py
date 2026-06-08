#!/usr/bin/env python3
"""Supplement guide JSON with content from Gemini Vision audit_cache.

For chapters that are missing content (fail status or high missing-heading count),
replace with Markdown assembled from audit_cache blocks. Existing pdfplumber content
is kept for warn/ok chapters by default.

Block types handled:
  heading   → ## / ### / #### Markdown heading
  paragraph → plain text paragraph
  list      → Markdown bullet list (nested ◦/■/*/◆ → indented sub-bullets)
  table     → HTML <table> as-is
  formula   → $$...$$ (display) or $...$ (inline)
  image     → > 🖼 description (blockquote note)

Usage:
  uv run python3 scripts/supplement_guide_from_audit.py --level 中級 --subject 1
  uv run python3 scripts/supplement_guide_from_audit.py --level 中級 --all
  uv run python3 scripts/supplement_guide_from_audit.py --level 中級 --subject 1 --chapter mid-s1c1
  uv run python3 scripts/supplement_guide_from_audit.py --level 中級 --all --strategy all
  uv run python3 scripts/supplement_guide_from_audit.py --level 中級 --subject 1 --dry-run

Requires:
  data/{level}/audit_cache/{key}/   (from pdf_vision_audit.py)
  data/{level}/audit_compare/{key}/ (from codex_audit_compare.py, for status)
  data/{level}/guide/subject{N}_guide.json
  data/{level}/toc_manifest.json
"""

from __future__ import annotations
import argparse
import json
import re
import shutil
from pathlib import Path

BASE = Path('/home/james/projects/ipas-test')

# mid-s1 → (subject_num=1, guide_key='guide1')
SUBJECT_MAP: dict[str, tuple[int, str]] = {
    'mid-s1': (1, 'guide1'),
    'mid-s2': (2, 'guide2'),
    'mid-s3': (3, 'guide3'),
}

SUB_BULLET_RE = re.compile(r'^(\s*)([◦■◆•]|\*(?!\*))\s*(.*)')


# ── Block → Markdown converters ────────────────────────────────────────────────

def _format_list_item(item: str) -> str:
    """Convert one list item string (possibly multi-line with nested markers) to Markdown."""
    if not item.strip():
        return ''
    lines = item.split('\n')
    result: list[str] = []
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        m = SUB_BULLET_RE.match(line)
        if m:
            indent_chars = len(m.group(1))
            depth = max(1, indent_chars // 2 + 1)
            result.append('  ' * depth + '- ' + m.group(3).strip())
        elif i == 0:
            result.append('- ' + line.strip())
        else:
            # Continuation line — indent under parent bullet
            result.append('  ' + line.strip())
    return '\n'.join(result)


def blocks_to_markdown(blocks: list[dict]) -> str:
    """Convert a list of audit_cache blocks to a Markdown string."""
    parts: list[str] = []
    for b in blocks:
        t = b.get('type', '')

        if t == 'heading':
            level = max(1, min(6, b.get('level', 2)))
            parts.append('#' * level + ' ' + b.get('text', '').strip())

        elif t == 'paragraph':
            text = b.get('text', '').strip()
            if text:
                parts.append(text)

        elif t == 'list':
            items = b.get('items', [])
            bullet_lines: list[str] = []
            for item in items:
                formatted = _format_list_item(str(item))
                if formatted:
                    bullet_lines.append(formatted)
            if bullet_lines:
                parts.append('\n'.join(bullet_lines))

        elif t == 'table':
            html = b.get('html', '').strip()
            if html:
                parts.append(html)

        elif t == 'formula':
            latex = b.get('latex', '').strip()
            if latex:
                if b.get('display', False):
                    parts.append(f'$$\n{latex}\n$$')
                else:
                    parts.append(f'${latex}$')

        elif t == 'image':
            desc = b.get('description', '').strip()
            if desc:
                parts.append(f'> 🖼 {desc}')

    return '\n\n'.join(p for p in parts if p)


# ── Audit cache assembly ────────────────────────────────────────────────────────

HEADING_LINE_RE = re.compile(r'^#{1,6} ')


def _trim_to_first_heading(md: str) -> str:
    """Drop any content (orphaned lists/paragraphs) that appears before the
    first Markdown heading line. Handles cases where the chapter's first PDF
    page contains tail-end content from the previous chapter."""
    for i, line in enumerate(md.splitlines()):
        if HEADING_LINE_RE.match(line):
            return '\n'.join(md.splitlines()[i:])
    return md  # no heading found — return as-is


def _find_title_start_idx(
    pages: list[tuple[int, list[dict], str]],
    chapter_title: str,
) -> int:
    """Return the index into `pages` where the chapter title first appears in
    a heading, so we can skip leading pages that contain previous-chapter overview.
    Falls back to 0 (first page) if no match is found."""
    title_core = re.sub(r'^\d+[\.\s]+', '', chapter_title).strip()
    for i, (_, headings, _) in enumerate(pages):
        for h in headings:
            if title_core and title_core in h.get('title', ''):
                return i
    return 0


def assemble_chapter_from_audit(
    key: str,
    page_range: list[int],
    cache_dir: Path,
    skip_practice: bool = False,
) -> str:
    """Assemble Markdown content for one chapter from audit_cache pages.

    Trims any orphaned content before the first heading (tail-end of the
    previous chapter that may appear on this chapter's first PDF page).
    """
    start_page, end_page = page_range  # 1-based, inclusive
    all_blocks: list[dict] = []

    for page_num in range(start_page, end_page + 1):
        idx = page_num - 1  # 0-based file index
        page_file = cache_dir / f'page_{idx:03d}.json'
        if not page_file.exists():
            continue
        d = json.loads(page_file.read_text(encoding='utf-8'))
        page_type = d.get('type', 'content')
        if page_type == 'skip':
            continue
        if skip_practice and page_type == 'practice':
            continue
        all_blocks.extend(d.get('blocks', []))

    return _trim_to_first_heading(blocks_to_markdown(all_blocks))


def assemble_chapter_from_pages_cache(
    key: str,
    page_range: list[int],
    cache_dir: Path,
    chapter_title: str = '',
    skip_practice: bool = False,
) -> str:
    """Assemble Markdown content for one chapter from pages_cache (vision extract).

    Reads the pre-built `markdown` field from each page and concatenates them.
    If `chapter_title` is given, skips leading pages until the title appears
    in a heading (handles chapter-boundary pages with previous-chapter overviews).
    Falls back gracefully if pages are missing from cache.
    """
    start_page, end_page = page_range  # 1-based, inclusive
    pages: list[tuple[int, list[dict], str]] = []

    for page_num in range(start_page, end_page + 1):
        idx = page_num - 1  # 0-based
        page_file = cache_dir / f'page_{idx:03d}.json'
        if not page_file.exists():
            continue
        d = json.loads(page_file.read_text(encoding='utf-8'))
        page_type = d.get('type', 'content')
        if page_type == 'skip':
            continue
        if skip_practice and page_type == 'practice':
            continue
        md = d.get('markdown', '').strip()
        if md:
            pages.append((idx, d.get('headings', []), md))

    if not pages:
        return ''

    start_idx = _find_title_start_idx(pages, chapter_title) if chapter_title else 0
    return '\n\n'.join(md for _, _, md in pages[start_idx:])


# ── Status helpers ──────────────────────────────────────────────────────────────

def load_chapter_status(compare_dir: Path, chapter_id: str) -> dict:
    """Return audit_compare result dict for a chapter, or {} if not found."""
    f = compare_dir / f'{chapter_id}.json'
    if not f.exists():
        return {}
    return json.loads(f.read_text(encoding='utf-8'))


def should_replace(
    status_data: dict,
    strategy: str,
    min_missing: int,
    force_chapter: str | None,
    chapter_id: str,
) -> tuple[bool, str]:
    """Return (replace, reason) based on strategy."""
    if force_chapter and chapter_id == force_chapter:
        return True, 'forced by --chapter'

    status = status_data.get('status', 'unknown')
    missing = len(status_data.get('missing_headings', []))

    if strategy == 'all':
        return True, 'strategy=all'
    if strategy == 'fail' and status == 'fail':
        return True, f'status=fail'
    if strategy == 'missing' and missing >= min_missing:
        return True, f'missing_headings={missing} >= {min_missing}'

    return False, f'status={status} missing={missing} (skipped)'


# ── Main processing ─────────────────────────────────────────────────────────────

def process_subject(
    level: str,
    subject_id: str,
    subject_num: int,
    guide_key: str,
    chapters: list[dict],
    strategy: str,
    min_missing: int,
    force_chapter: str | None,
    dry_run: bool,
    skip_practice: bool,
    source: str = 'audit_cache',
) -> None:
    data_dir = BASE / 'data' / level
    audit_cache_dir = data_dir / 'audit_cache' / guide_key
    pages_cache_dir = data_dir / 'pages_cache' / guide_key
    compare_dir = data_dir / 'audit_compare' / guide_key
    guide_path = data_dir / 'guide' / f'subject{subject_num}_guide.json'

    if source == 'audit_cache' and not audit_cache_dir.exists():
        print(f'  [skip] audit_cache/{guide_key}/ not found')
        return
    if source == 'pages_cache' and not pages_cache_dir.exists():
        print(f'  [skip] pages_cache/{guide_key}/ not found')
        return
    if not guide_path.exists():
        print(f'  [skip] guide not found: {guide_path}')
        return

    guide_data = json.loads(guide_path.read_text(encoding='utf-8'))
    ch_map = {ch['id']: ch for ch in guide_data['chapters']}

    replaced = 0
    skipped = 0

    for ch_def in chapters:
        ch_id = ch_def['id']
        ch_title = ch_def.get('title', '')
        page_range = ch_def.get('page_range')
        if not page_range:
            print(f'  {ch_id}: no page_range, skipping')
            continue

        status_data = load_chapter_status(compare_dir, ch_id)
        replace, reason = should_replace(
            status_data, strategy, min_missing, force_chapter, ch_id
        )

        if not replace:
            print(f'  {ch_id}: {reason}')
            skipped += 1
            continue

        # Assemble new content
        if source == 'pages_cache':
            # Check coverage for this chapter's page range
            start_idx, end_idx = page_range[0] - 1, page_range[1] - 1
            cached_pages = sum(
                1 for i in range(start_idx, end_idx + 1)
                if (pages_cache_dir / f'page_{i:03d}.json').exists()
            )
            total_pages = end_idx - start_idx + 1
            coverage = cached_pages / total_pages if total_pages else 0
            if coverage < 0.8:
                print(f'  {ch_id}: pages_cache coverage {coverage:.0%} < 80%, skipping')
                skipped += 1
                continue
            new_content = assemble_chapter_from_pages_cache(
                guide_key, page_range, pages_cache_dir,
                chapter_title=ch_title, skip_practice=skip_practice,
            )
        else:
            new_content = assemble_chapter_from_audit(
                guide_key, page_range, audit_cache_dir, skip_practice
            )
        if not new_content.strip():
            print(f'  {ch_id}: assembled content empty, skipping')
            skipped += 1
            continue

        old_chars = len(ch_map.get(ch_id, {}).get('content', ''))
        new_chars = len(new_content)

        if dry_run:
            print(f'  {ch_id}: [DRY-RUN] {reason} | old={old_chars}c new={new_chars}c')
        else:
            if ch_id in ch_map:
                ch_map[ch_id]['content'] = new_content
            else:
                print(f'  {ch_id}: chapter not in guide JSON, skipping')
                skipped += 1
                continue
            print(f'  {ch_id}: replaced ({reason}) | {old_chars}c → {new_chars}c')
            replaced += 1

    if not dry_run and replaced > 0:
        # Backup original
        backup = guide_path.with_suffix('.json.bak')
        shutil.copy2(guide_path, backup)
        guide_path.write_text(
            json.dumps(guide_data, ensure_ascii=False, indent=2), encoding='utf-8'
        )
        print(f'  → wrote {guide_path.name} ({replaced} replaced, backup: {backup.name})')
    elif dry_run:
        print(f'  → dry-run: {replaced + skipped} chapters reviewed')
    else:
        print(f'  → no changes (all skipped)')


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--level', default='中級')
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument('--subject', type=int, choices=[1, 2, 3])
    grp.add_argument('--all', action='store_true')
    parser.add_argument('--chapter', help='Force-replace a specific chapter ID')
    parser.add_argument(
        '--strategy',
        choices=['fail', 'missing', 'all'],
        default='fail',
        help='Which chapters to replace: fail=audit status=fail (default), '
             'missing=min-missing threshold, all=every chapter',
    )
    parser.add_argument(
        '--min-missing', type=int, default=5,
        help='With --strategy missing: replace chapters with >= N missing headings (default 5)',
    )
    parser.add_argument('--skip-practice', action='store_true',
                        help='Exclude practice/exam pages from assembled content')
    parser.add_argument(
        '--source',
        choices=['audit_cache', 'pages_cache'],
        default='audit_cache',
        help='Content source: audit_cache (default, structured blocks) or '
             'pages_cache (vision extract markdown, requires 80%% chapter coverage)',
    )
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    data_dir = BASE / 'data' / args.level
    manifest = json.loads((data_dir / 'toc_manifest.json').read_text(encoding='utf-8'))

    subjects_to_run: list[dict] = []
    if args.all:
        subjects_to_run = manifest['subjects']
    else:
        for s in manifest['subjects']:
            snum = SUBJECT_MAP.get(s['id'], (None, None))[0]
            if snum == args.subject:
                subjects_to_run = [s]
                break

    for subj in subjects_to_run:
        s_id = subj['id']
        s_num, g_key = SUBJECT_MAP.get(s_id, (None, None))
        if s_num is None:
            print(f'Unknown subject id: {s_id}')
            continue
        print(f'\nSubject {s_num} ({s_id}) — {g_key}')
        process_subject(
            level=args.level,
            subject_id=s_id,
            subject_num=s_num,
            guide_key=g_key,
            chapters=subj['chapters'],
            strategy=args.strategy,
            min_missing=args.min_missing,
            force_chapter=args.chapter,
            dry_run=args.dry_run,
            skip_practice=args.skip_practice,
            source=args.source,
        )

    print('\n完成')


if __name__ == '__main__':
    main()
