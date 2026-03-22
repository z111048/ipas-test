#!/usr/bin/env python3
"""Parse study guide PDFs into chapter-structured JSON.

Two modes (auto-selected):
  1. Vision mode  — if pages_cache/{key}/ exists from pdf_vision_extract.py,
                    chapter content is assembled from LLM-extracted per-page markdown.
  2. Regex mode   — fallback: text extraction + structural regex conversion.

Usage:
  uv run python3 scripts/parse_guides.py                   # default: 初級, all subjects
  uv run python3 scripts/parse_guides.py --level 初級
  uv run python3 scripts/parse_guides.py --level 初級 --subject 1
"""

import argparse
import json
import re
from pathlib import Path

try:
    import fitz  # PyMuPDF — only needed for vision mode page-label mapping
    _FITZ_AVAILABLE = True
except ImportError:
    _FITZ_AVAILABLE = False

BASE = Path('/home/james/projects/ipas-test')


def _load_manifest(data_dir: Path) -> dict[int, dict]:
    """Load chapter definitions from toc_manifest.json (single source of truth)."""
    manifest_path = data_dir / 'toc_manifest.json'
    with open(manifest_path, encoding='utf-8') as f:
        manifest = json.load(f)
    result = {}
    for i, subj in enumerate(manifest['subjects'], 1):
        result[i] = {
            'key': subj['key'],
            'pdf': subj['pdf'],
            'subject': subj['subject'],
            'chapters': subj['chapters'],
        }
    return result


PAGE_SEP = '\x01'  # sentinel between pages in joined text (won't appear in PDF content)


def is_practice_page(text: str) -> bool:
    """Return True if the page contains practice questions or answer explanations."""
    # Answer pages: contain "N. Ans（X）" pattern
    if re.search(r'\d+[\.\．]\s*Ans（[A-D]）', text):
        return True
    # Question pages: 4+ multiple-choice option lines "(A)/(B)/(C)/(D)"
    if len(re.findall(r'（[ABCD]）', text)) >= 4:
        return True
    return False


def load_guide_text(key: str, data_dir: Path) -> str:
    """Concatenate all page texts using PAGE_SEP as page boundary marker."""
    with open(data_dir / 'extracted' / f'{key}.json', encoding='utf-8') as f:
        data = json.load(f)
    parts = []
    for p in data['pages']:
        text = p.get('text', '').strip()
        if text:
            parts.append(text)
    return PAGE_SEP.join(parts)


def strip_practice_pages(text: str) -> tuple[str, int]:
    """Remove practice question/answer pages from a chapter segment."""
    pages = text.split(PAGE_SEP)
    clean, skipped = [], 0
    for page in pages:
        if is_practice_page(page):
            skipped += 1
        else:
            clean.append(page)
    return '\n'.join(clean), skipped


def prev_page_label(start_page: str) -> str:
    """Given '3-24', return '3-23' (last page of the preceding chapter)."""
    prefix, num_str = start_page.rsplit('-', 1)
    return f'{prefix}-{int(num_str) - 1}'


def split_into_chapters(raw_text: str, chapters: list[dict]) -> list[str]:
    """
    Split raw_text at chapter boundaries.

    Each boundary is the in-document page label of the last page of the
    preceding chapter (i.e. next chapter's start page minus 1).
    """
    # Find split positions: right after each boundary label
    split_positions = []
    for ch in chapters[1:]:
        boundary = prev_page_label(ch['start_page'])
        pattern = r'\b' + re.escape(boundary) + r'\b'
        m = re.search(pattern, raw_text)
        if m:
            split_positions.append(m.end())
        else:
            print(f"  WARN: boundary '{boundary}' not found in text")
            split_positions.append(None)

    segments = []
    prev = 0
    for pos in split_positions:
        if pos is None:
            segments.append(raw_text[prev:])
            prev = len(raw_text)
        else:
            segments.append(raw_text[prev:pos])
            prev = pos
    segments.append(raw_text[prev:])
    return segments


_CJK = '\u4e00-\u9fff'
_SENT_END = re.compile(r'[。！？」』）】]$')
_STRUCT_START = re.compile(
    r'^(?:[\uf097\u2022\u25aa•]|（[一二三四五六七八九十\d]）|[A-Z]\.\s|[a-z]\.\s|\d+\.\s)'
)


def _merge_pdf_lines(lines: list[str]) -> list[str]:
    """Join lines broken mid-sentence by PDF layout."""
    result: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line:
            result.append(line)
            i += 1
            continue
        # Merge while current line ends mid-sentence (CJK char or mid-sentence
        # punctuation like ，、）) and next line continues the sentence
        while (
            i + 1 < len(lines)
            and lines[i + 1]
            and re.search(f'[{_CJK}，、）】]$', line)
            and not _SENT_END.search(line)
            and not _STRUCT_START.match(lines[i + 1])
        ):
            line = line + lines[i + 1]
            i += 1
        result.append(line)
        i += 1
    return result


def clean_segment(text: str) -> str:
    """Remove structural noise from a chapter text segment."""
    lines = []
    for line in text.split('\n'):
        # Preserve \uf097 (PDF bullet glyph) as '• ' before stripping other PUA chars
        line = line.replace('\uf097', '• ')
        # Strip remaining Unicode Private Use Area chars (e.g. \uf07d from font artifacts)
        stripped = re.sub(r'[\ue000-\uf8ff]', '', line).strip()
        s = stripped
        # Drop TOC dot-leader lines
        if re.search(r'\.{5,}', s):
            continue
        # Drop in-document page number lines like "3-1", "A-1"
        if re.match(r'^[A-Z\d]+-\d+$', s):
            continue
        # Drop repeated chapter running headers (may have PUA prefix chars)
        if re.search(r'第[一二三四五六七八九十]+章', s):
            continue
        # Drop [TABLES] markers
        if s == '[TABLES]':
            continue
        # Drop short separator-like lines (|, =====, -----)
        if re.match(r'^[|\-=]{3,}$', s):
            continue
        # Drop standalone section-number/heading lines like "3.1", "3.2 No code / Low code"
        if re.match(r'^3\.\d', s) and len(s) < 40:
            continue
        # Drop isolated short PUA-stripped lines that are clearly garbled headers
        if re.match(r'^(?:AI|MCP|LLM|RAG)\s*$', s):
            continue
        if re.match(r'^\d+\.\s+AI\s*$', s):
            continue
        lines.append(stripped)

    lines = _merge_pdf_lines(lines)
    cleaned = '\n'.join(lines)
    # Collapse runs of 3+ blank lines to 2
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()


def _split_heading_content(rest: str) -> tuple[str, str]:
    """Split a potentially merged 'TITLE：content' or 'TITLETITLE content' string.

    Returns (heading, content_or_empty).
    """
    # Case 1: ends with ： and short enough → pure heading
    if rest.endswith('：') and len(rest) <= 35:
        return rest[:-1].strip(), ''

    # Case 2: "TITLE：content" — find first ：within 50 chars
    m = re.match(r'^(.{1,50}?)：(.+)', rest)
    if m:
        return m.group(1).strip(), m.group(2).strip()

    # Case 3: title repeated at start — "技術底層技術底層是..."
    m = re.match(r'^(.{2,8})\1(.+)', rest)
    if m:
        return m.group(1).strip(), (m.group(1) + m.group(2)).strip()

    # Case 4: long merged text — split at first full-width comma within 20 chars
    m = re.match(r'^(.{4,20})[，、](.+)', rest)
    if m:
        return m.group(1).strip(), m.group(2).strip()

    # Case 5a: "TERM（English）是..." — split at ）followed by 是/為/指
    m = re.match(r'^(.{4,50}?[）)])(\s*(?:是指|是一種|是一個|是一|是|為一種|係指|指的是))(.{10,})', rest)
    if m:
        return m.group(1).strip(), (m.group(2) + m.group(3)).strip()

    # Case 5b: CJK content-start verb "是指/是一種/主要用" after a CJK char
    m = re.match(r'^(.{4,40}?[\u4e00-\u9fff])(是指|是一種|是一個|係指|指的是|主要用於|主要是)(.{8,})', rest)
    if m:
        return m.group(1).strip(), (m.group(2) + m.group(3)).strip()

    # Case 6: heading ends with common topic-summary suffixes (效應/差異/優勢/方向 etc.)
    _HEADING_SUFFIX = r'(?:效應|差異|優勢|挑戰|方向|趨勢|穩定性|公平性|適應性|靈活性|準確性|可靠性|一致性|完整性|可用性|防範|應用|架構|整合|融合|協同|特性|特徵|概念|原理|方法|機制|流程|分析|管理|設計|開發|部署|評估|優化|調整|處理|操作|執行|實現|實施|建立|構建|生成|識別|檢測|監控|控制|保護|加密|驗證)'
    m = re.match(rf'^(.{{4,25}}{_HEADING_SUFFIX})([\u4e00-\u9fff].{{10,}})', rest)
    if m:
        return m.group(1).strip(), m.group(2).strip()

    # No split found — use full text as heading
    return rest, ''


def text_to_markdown(text: str, chapter_title: str) -> str:
    """Convert cleaned plain text chapter content to Markdown.

    Heading hierarchy detected by regex:
      H2 : ^\d+\.          top-level numbered sections
      H3 : ^（N）           sub-sections (full-width parens)
      H4 : ^[A-Z]\.        lettered items
      -  : ^[a-z]\. | ^• | short_term：long_content  (definition bullets)
    """
    lines = text.split('\n')
    out: list[str] = [f'# {chapter_title}', '']
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if not line:
            if out and out[-1] != '':
                out.append('')
            continue

        # H2 — standalone "1." or "1. Title"
        m = re.match(r'^(\d+)\.\s*(.*)', line)
        if m:
            num, rest = m.group(1), m.group(2).strip()
            if not rest:
                # Consume the next non-empty line as section description
                while i < len(lines) and not lines[i].strip():
                    i += 1
                if i < len(lines):
                    rest = lines[i].strip()
                    i += 1
            out.extend([f'## {num}. {rest}' if rest else f'## {num}.', ''])
            continue

        # H3 — （N）[title]  or  （N）[title]：[content merged]
        m = re.match(r'^（([一二三四五六七八九十\d]+)）\s*(.*)', line)
        if m:
            rest = m.group(2).strip()
            heading, content = _split_heading_content(rest)
            if content:
                out.extend([f'### {heading}', '', content, ''])
            else:
                out.extend([f'### {heading}', ''])
            continue

        # H4 — "A. Title"
        m = re.match(r'^([A-Z])\.\s+(.*)', line)
        if m:
            heading, content = _split_heading_content(m.group(2).strip())
            if content:
                out.extend([f'#### {m.group(1)}. {heading}', '', content, ''])
            else:
                out.extend([f'#### {m.group(1)}. {heading}', ''])
            continue

        # Bullet — "a. text" or "• text"
        m = re.match(r'^[a-z]\.\s+(.*)', line)
        if m:
            out.append(f'- {m.group(1).strip()}')
            continue
        if line.startswith('• '):
            out.append(f'- {line[2:].strip()}')
            continue

        # Definition bullet — "短詞彙：長內容" (term ≤ 12 CJK chars, content ≥ 15 chars)
        m = re.match(r'^([\u4e00-\u9fff\w（）()]{1,15})：([\u4e00-\u9fff].{14,})', line)
        if m:
            term, content = m.group(1).strip(), m.group(2).strip()
            out.append(f'- **{term}**：{content}')
            continue

        out.append(line)

    result = '\n'.join(out)
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result.strip()


# ── Vision-cache chapter loading ──────────────────────────────────────────────

def _build_page_label_map(pdf_path: Path) -> dict[str, int]:
    """Map in-document page labels (e.g. '3-24') → 0-based page index.

    Scans every page for numeric labels like '3-24'.  Uses the LAST occurrence
    so that actual content pages win over TOC forward-references.
    """
    doc = fitz.open(str(pdf_path))
    mapping: dict[str, int] = {}
    for i, page in enumerate(doc):
        for m in re.finditer(r'\b(\d+-\d+)\b', page.get_text()):
            mapping[m.group(1)] = i
    doc.close()
    return mapping


def _get_chapter_page_ranges(
    chapters: list[dict], label_map: dict[str, int], total_pages: int
) -> list[list[int]]:
    """Return a list of page-index lists, one per chapter."""
    def _find(label: str) -> int:
        if label in label_map:
            return label_map[label]
        # Fallback: label-1 not found → try label+1 and subtract 1
        prefix, num = label.rsplit('-', 1)
        nxt = f'{prefix}-{int(num) + 1}'
        if nxt in label_map:
            return label_map[nxt] - 1
        raise ValueError(f"Cannot find page index for '{label}'")

    starts = [_find(ch['start_page']) for ch in chapters]
    result = []
    for i, start in enumerate(starts):
        end = starts[i + 1] - 1 if i + 1 < len(starts) else total_pages - 1
        result.append(list(range(start, end + 1)))
    return result


def load_chapter_pages_vision(
    key: str, chapters: list[dict], pdf_path: Path, cache_dir: Path
) -> list[str] | None:
    """Load chapter markdown from vision cache.

    Returns a list of chapter-level markdown strings (one per chapter),
    or None if the cache is incomplete or unavailable.
    """
    guide_cache_dir = cache_dir / key
    if not guide_cache_dir.exists():
        return None

    if not _FITZ_AVAILABLE:
        print('  [vision] PyMuPDF not available; falling back to regex mode')
        return None

    # Count available content pages (skip page_index.json)
    cached = {}
    for p in guide_cache_dir.glob('page_*.json'):
        if p.name == 'page_index.json':
            continue
        with open(p, encoding='utf-8') as f:
            d = json.load(f)
        cached[d['idx']] = d

    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)
    doc.close()

    # Require at least 80% of pages cached
    coverage = len(cached) / total_pages if total_pages else 0
    if coverage < 0.8:
        print(f'  [vision] cache only {coverage:.0%} complete; falling back to regex mode')
        return None

    label_map = _build_page_label_map(pdf_path)
    try:
        page_ranges = _get_chapter_page_ranges(chapters, label_map, total_pages)
    except ValueError as e:
        print(f'  [vision] page mapping failed ({e}); falling back to regex mode')
        return None

    chapter_contents = []
    for ch, page_indices in zip(chapters, page_ranges):
        parts = []
        for idx in page_indices:
            entry = cached.get(idx)
            if entry is None or entry.get('type') != 'content':
                continue
            md = entry.get('markdown', '').strip()
            if md:
                parts.append(md)
        chapter_contents.append('\n\n'.join(parts))

    # Sanity: all chapters should have some content
    empty = [ch['id'] for ch, c in zip(chapters, chapter_contents) if not c.strip()]
    if empty:
        print(f'  [vision] chapters with no content: {empty}; falling back to regex mode')
        return None

    return chapter_contents


def parse_guide(
    subject_num: int,
    guides: dict[int, dict],
    pdf_dir: Path,
    cache_dir: Path,
    data_dir: Path,
) -> dict:
    cfg = guides[subject_num]
    key = cfg['key']
    print(f'Processing {key}...')

    chapters = cfg['chapters']

    # ── Vision mode (preferred) ────────────────────────────────────────────────
    pdf_path = pdf_dir / cfg['pdf']
    vision_contents = None
    if _FITZ_AVAILABLE and pdf_path.exists():
        vision_contents = load_chapter_pages_vision(key, chapters, pdf_path, cache_dir)

    if vision_contents is not None:
        print('  [vision mode]')
        result_chapters = []
        for ch, content in zip(chapters, vision_contents):
            # Prepend chapter title as H1 for consistency
            full_content = f'# {ch["title"]}\n\n{content}'.strip()
            result_chapters.append({
                'id': ch['id'],
                'title': ch['title'],
                'subtopics': ch['subtopics'],
                'content': full_content,
                'content_format': 'markdown',
            })
            print(f"  {ch['id']} ({ch['title']}): {len(full_content)} chars")
        return {'subject': cfg['subject'], 'chapters': result_chapters}

    # ── Regex mode (fallback) ──────────────────────────────────────────────────
    print('  [regex mode]')
    raw_text = load_guide_text(key, data_dir)
    segments = split_into_chapters(raw_text, chapters)

    result_chapters = []
    total_skipped = 0
    for i, (ch, seg) in enumerate(zip(chapters, segments)):
        # strip_practice_pages converts \x01 page sentinels → \n, must run first
        seg, skipped = strip_practice_pages(seg)
        total_skipped += skipped
        # For the first chapter, skip the preface/TOC intro pages that
        # appear before the actual chapter content (intro ends at page '2-1').
        if i == 0:
            # Find the standalone page number '2-1' (on its own line),
            # not the one embedded in TOC dot-leader lines.
            m = re.search(r'(?:^|\n)(2-1)\n', seg)
            if m:
                seg = seg[m.end():]
        plain = clean_segment(seg)
        content = text_to_markdown(plain, ch['title'])
        result_chapters.append({
            'id': ch['id'],
            'title': ch['title'],
            'subtopics': ch['subtopics'],
            'content': content,
            'content_format': 'markdown',
        })
        print(f"  {ch['id']} ({ch['title']}): {len(content)} chars")
    print(f"  (skipped {total_skipped} practice/answer pages)")

    return {
        'subject': cfg['subject'],
        'chapters': result_chapters,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--level', default='初級',
                        help='資料等級資料夾（預設: 初級）')
    parser.add_argument('--subject', type=int,
                        help='只處理指定科目（不指定則處理所有科目）')
    args = parser.parse_args()

    data_dir = BASE / 'data' / args.level
    pdf_dir = data_dir / 'pdfs'
    cache_dir = data_dir / 'pages_cache'
    guide_dir = data_dir / 'guide'
    guide_dir.mkdir(exist_ok=True)

    guides = _load_manifest(data_dir)
    if not guides:
        import sys
        sys.exit(f'No subjects in manifest for level "{args.level}". '
                 f'Run build_manifest.py --level {args.level} first.')

    subjects = [args.subject] if args.subject else sorted(guides.keys())
    for n in subjects:
        if n not in guides:
            print(f'[WARN] Subject {n} not found in manifest')
            continue
        data = parse_guide(n, guides, pdf_dir, cache_dir, data_dir)
        out_path = guide_dir / f'subject{n}_guide.json'
        out_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8'
        )
        print(f'Saved {out_path}')


if __name__ == '__main__':
    main()
