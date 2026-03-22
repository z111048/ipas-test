#!/usr/bin/env python3
"""Extract study guide PDFs into structured Markdown using PyMuPDF span metadata.

Approach: fully deterministic 6-level hierarchy extraction.
  L2 (size≥18, bold)        → ## section    (number in text, title from GUIDES)
  L3 (size≥13, bold)        → ### item      (e.g. "1." "2.")
  L4 (bold, starts （N）)   → #### subitem  (e.g. "（1）醫療保健：")
  L5 (bold, starts A./B.)   → ##### detail  (e.g. "A. 資料處理")
  L6 (bullet char \uf097)   → - list item
  L0                        → body paragraph

No LLM required for structure. Validation uses key term retention.

Usage:
  uv run python3 scripts/guide_to_md.py --subject 1
  uv run python3 scripts/guide_to_md.py --all
  uv run python3 scripts/guide_to_md.py --subject 1 --chapter s1c1
  uv run python3 scripts/guide_to_md.py --subject 1 --threshold 0.90
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit('PyMuPDF not found. Run: uv sync')

BASE = Path('/home/james/projects/ipas-test')
DATA = BASE / 'data' / '初級'
PDF_DIR = DATA / 'pdfs'
DEFAULT_THRESHOLD = 0.95

SENTENCE_END = re.compile(r'[。！？」』）\]]$')
CJK_END = re.compile(r'[\u4e00-\u9fff]$')
BULLET_CHARS = '\uf097\uf07d\u2022\u00b7\u25aa\u25cf'
PUA_RE = re.compile(r'[\ue000-\uf8ff]')

# ── Chapter definitions (loaded from toc_manifest.json) ──────────────────────

def _load_manifest() -> dict[int, dict]:
    """Load chapter definitions from toc_manifest.json (single source of truth)."""
    manifest_path = DATA / 'toc_manifest.json'
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


GUIDES = _load_manifest()


# ── Page index mapping ────────────────────────────────────────────────────────

def build_page_label_map(pdf_path: Path) -> dict[str, int]:
    """Map in-document page labels (e.g. '3-1') to 0-based page indices.

    Uses last occurrence so actual content pages win over TOC references.
    """
    doc = fitz.open(str(pdf_path))
    mapping: dict[str, int] = {}
    for i, page in enumerate(doc):
        for m in re.finditer(r'\b(\d+-\d+)\b', page.get_text()):
            mapping[m.group(1)] = i
    doc.close()
    return mapping


def find_page_index(label: str, label_map: dict[str, int]) -> int:
    if label in label_map:
        return label_map[label]
    prefix, num_str = label.rsplit('-', 1)
    next_label = f'{prefix}-{int(num_str) + 1}'
    if next_label in label_map:
        return label_map[next_label] - 1
    raise ValueError(f"Cannot find page index for '{label}'")


def get_chapter_pdf_pages(
    chapters: list[dict], label_map: dict[str, int], total_pages: int
) -> list[list[int]]:
    start_indices = [find_page_index(ch['start_page'], label_map) for ch in chapters]
    result = []
    for i, start in enumerate(start_indices):
        end = start_indices[i + 1] - 1 if i + 1 < len(start_indices) else total_pages - 1
        result.append(list(range(start, end + 1)))
    return result


# ── Line classification ───────────────────────────────────────────────────────

def classify_line(line: dict) -> dict | None:
    """Classify a single fitz text line by its typographic properties.

    Returns a classified dict or None if the line should be skipped.
    """
    spans = line.get('spans', [])
    if not spans:
        return None

    x0 = round(line['bbox'][0])
    raw_text = ''.join(sp['text'] for sp in spans)
    text = PUA_RE.sub('', raw_text).strip()
    if not text:
        return None

    # Compute dominant font size and bold
    valid_spans = [sp for sp in spans if sp['text'].strip()]
    if not valid_spans:
        return None
    sizes = [round(sp['size'], 1) for sp in valid_spans]
    dominant_size = max(set(sizes), key=sizes.count)
    is_bold = any(bool(sp['flags'] & 16) for sp in valid_spans)

    # ── Noise filters ─────────────────────────────────────────────────────
    # Header/footer font (size ≤ 10.5)
    if dominant_size <= 10.5:
        return None
    # Standalone page-number lines like "3-1", "A-1"
    if re.match(r'^[A-Za-z0-9]+-\d+$', text):
        return None
    # Chapter running header (short line with 第N章)
    if re.search(r'第[一二三四五六七八九十]+章', text) and len(text) < 30:
        return None

    # ── Level classification ───────────────────────────────────────────────
    has_bullet = any(c in raw_text for c in BULLET_CHARS)

    if dominant_size >= 18 and is_bold:
        level = 2  # Section number: "3.1", "3.2", …
    elif dominant_size >= 13 and is_bold:
        level = 3  # Numbered major item: "1.", "2.", "3."
    elif is_bold and re.match(r'^[（(]\d+[）)]', text):
        level = 4  # Parenthetical subitem: "（1）醫療保健："
    elif is_bold and re.match(r'^[A-Za-z]\.\s', text):
        level = 5  # Letter detail: "A. 資料處理", "B. 演算法"
    elif has_bullet:
        level = 6  # Bullet item
        # Strip bullet characters from text
        text = re.sub(r'^[' + re.escape(BULLET_CHARS) + r'\s]+', '', text).strip()
    else:
        level = 0  # Body text / continuation

    # x=89 lines are always continuations of the preceding line
    is_continuation = (level == 0 and x0 >= 87)

    return {
        'level': level,
        'text': text,
        'x0': x0,
        'is_continuation': is_continuation,
        'is_bold': is_bold,
        'size': dominant_size,
    }


# ── Line extraction and merging ───────────────────────────────────────────────

def extract_chapter_lines(pdf_path: Path, page_indices: list[int]) -> list[dict]:
    """Extract and classify all text lines from chapter pages."""
    doc = fitz.open(str(pdf_path))
    lines = []
    for pi in page_indices:
        page = doc[pi]
        for block in page.get_text('dict')['blocks']:
            if block['type'] != 0:  # skip image blocks
                continue
            for line in block['lines']:
                cl = classify_line(line)
                if cl:
                    lines.append(cl)
    doc.close()
    return lines


def merge_body_lines(lines: list[dict]) -> list[dict]:
    """Merge continuation lines into their predecessor body/bullet lines.

    Rules:
    - x=89 (is_continuation) → always merges with previous
    - x=77 non-bold, non-bullet → merges if previous didn't end with sentence-final punct
    Heading lines (level 2-5) are never merged.
    """
    result: list[dict] = []
    i = 0
    while i < len(lines):
        line = lines[i]

        if line['level'] in (2, 3, 4, 5):
            result.append(dict(line))
            i += 1
            continue

        # Body (level 0) or bullet (level 6): accumulate
        text = line['text']
        j = i + 1

        while j < len(lines):
            nxt = lines[j]
            if nxt['level'] not in (0,):
                break

            if nxt['is_continuation']:
                # x=89: direct join (no space for CJK, space for Latin)
                if CJK_END.search(text):
                    text += nxt['text']
                else:
                    text = text.rstrip() + nxt['text']
                j += 1

            elif line['level'] == 0 and nxt['level'] == 0 and not nxt['is_continuation']:
                # x=77/102: merge only if current text is mid-sentence
                if not SENTENCE_END.search(text) and not nxt['is_bold']:
                    if CJK_END.search(text):
                        text += nxt['text']
                    else:
                        text = text.rstrip() + nxt['text']
                    j += 1
                else:
                    break
            else:
                break

        result.append({**line, 'text': text})
        i = j

    return result


# ── Tree building ─────────────────────────────────────────────────────────────

def _new_node(heading: str, level: int) -> dict:
    return {
        'heading': heading,
        'level': level,
        'body': '',
        'bullets': [],
        'children': [],
    }


def _append_body(node: dict, text: str) -> None:
    if node['body']:
        node['body'] += '\n\n' + text
    else:
        node['body'] = text


def build_chapter_tree(lines: list[dict], chapter: dict) -> dict:
    """Build a nested 6-level content tree from classified lines.

    Tree shape:
      chapter_node
        .children  → [L3 nodes]
          .children → [L4 nodes]
            .children → [L5 nodes]
              .bullets → [str]
              .body    → str
    """
    root = _new_node(chapter['title'], 1)
    root['id'] = chapter['id']
    root['subtopics'] = chapter['subtopics']

    # Stack: index 0 = root, index 1 = current L3, index 2 = L4, index 3 = L5
    stack: list[dict] = [root]

    def current() -> dict:
        return stack[-1]

    def set_level(level: int, node: dict) -> None:
        # Pop stack until parent level
        while len(stack) > 1 and stack[-1]['level'] >= level:
            stack.pop()
        stack[-1]['children'].append(node)
        stack.append(node)

    for line in lines:
        lv = line['level']
        text = line['text']

        if lv == 2:
            # Chapter section header — already represented by root, skip number
            pass
        elif lv == 3:
            node = _new_node(text, 3)
            set_level(3, node)
        elif lv == 4:
            node = _new_node(text, 4)
            set_level(4, node)
        elif lv == 5:
            node = _new_node(text, 5)
            set_level(5, node)
        elif lv == 6:
            current()['bullets'].append(text)
        else:  # body
            _append_body(current(), text)

    return root


# ── Output conversion ─────────────────────────────────────────────────────────

def node_to_markdown_lines(node: dict, depth: int = 2) -> list[str]:
    """Recursively convert a tree node to Markdown lines."""
    out: list[str] = []
    hashes = '#' * depth

    # Chapter root: use ## for the chapter title
    heading_text = node.get('heading', node.get('title', ''))
    out.append(f'{hashes} {heading_text}')

    if node.get('body'):
        out.append('')
        out.append(node['body'])

    for bullet in node.get('bullets', []):
        out.append(f'- {bullet}')

    for child in node.get('children', []):
        out.append('')
        out.extend(node_to_markdown_lines(child, depth + 1))

    return out


def tree_to_markdown(root: dict) -> str:
    """Convert the chapter tree to a Markdown string."""
    lines = node_to_markdown_lines(root, depth=2)
    md = '\n'.join(lines)
    # Collapse 3+ blank lines
    md = re.sub(r'\n{3,}', '\n\n', md)
    return md.strip()


def node_to_sections(node: dict) -> list[dict]:
    """Convert children of a node to JSON section objects."""
    sections = []
    for child in node.get('children', []):
        sec = {
            'heading': child['heading'],
            'level': child['level'],
            'body': child['body'],
            'bullets': child['bullets'],
            'children': node_to_sections(child),
        }
        sections.append(sec)
    return sections


# ── Validation ────────────────────────────────────────────────────────────────

def extract_key_terms(text: str) -> set[str]:
    """Extract technical terms from raw text that must appear in output."""
    terms: set[str] = set()
    terms.update(t.upper() for t in re.findall(r'\b[A-Z]{2,}\b', text))
    terms.update(
        t.lower() for t in re.findall(r'\b[A-Za-z][a-zA-Z0-9]{2,}(?:[-/][a-zA-Z0-9]+)+\b', text)
    )
    terms.update(re.findall(r'\b(?:19|20)\d{2}\b', text))
    terms.update(re.findall(r'\b\d+\.?\d*\s*%', text))
    STOP = {'IS', 'IN', 'OR', 'TO', 'OF', 'AN', 'ON', 'AT', 'BY', 'AS', 'AND', 'THE'}
    return terms - STOP


@dataclass
class ValidationResult:
    chapter_id: str
    passed: bool
    retention_rate: float
    missing_terms: list[str]
    total_terms: int
    output_chars: int


def validate_output(
    source_terms: set[str],
    output_md: str,
    chapter_id: str,
    threshold: float,
) -> ValidationResult:
    output_upper = output_md.upper()
    missing = [t for t in source_terms if t.upper() not in output_upper]
    retention = 1.0 - len(missing) / len(source_terms) if source_terms else 1.0
    passed = retention >= threshold
    return ValidationResult(
        chapter_id=chapter_id,
        passed=passed,
        retention_rate=retention,
        missing_terms=missing,
        total_terms=len(source_terms),
        output_chars=len(output_md),
    )


# ── Section parser (for backward-compat sections field) ──────────────────────

def parse_sections_from_md(markdown: str) -> list[dict]:
    """Extract ## and ### headings with their content (flat list)."""
    sections: list[dict] = []
    current: dict | None = None
    for line in markdown.split('\n'):
        h2 = re.match(r'^## (.+)', line)
        h3 = re.match(r'^### (.+)', line)
        if h2 or h3:
            if current:
                current['content'] = current['content'].strip()
                sections.append(current)
            level = 2 if h2 else 3
            heading = (h2 or h3).group(1).strip()
            current = {'heading': heading, 'level': level, 'content': ''}
        elif current is not None:
            current['content'] += line + '\n'
    if current:
        current['content'] = current['content'].strip()
        sections.append(current)
    return sections


# ── Chapter processing ────────────────────────────────────────────────────────

def process_chapter(
    chapter: dict,
    pdf_path: Path,
    page_indices: list[int],
    threshold: float,
) -> tuple[dict, ValidationResult]:
    print(f"  {chapter['id']} ({chapter['title']}): pages {page_indices[0]}–{page_indices[-1]}")

    raw_lines = extract_chapter_lines(pdf_path, page_indices)
    merged_lines = merge_body_lines(raw_lines)
    tree = build_chapter_tree(merged_lines, chapter)
    markdown = tree_to_markdown(tree)
    nested_sections = node_to_sections(tree)

    print(f"    lines: {len(raw_lines)} raw → {len(merged_lines)} merged, "
          f"md: {len(markdown)} chars, "
          f"L3: {len(tree['children'])}, "
          f"L4: {sum(len(c['children']) for c in tree['children'])}")

    # Extract key terms from the raw text (all lines) as ground truth
    all_raw_text = ' '.join(l['text'] for l in raw_lines)
    source_terms = extract_key_terms(all_raw_text)
    val_result = validate_output(source_terms, markdown, chapter['id'], threshold)

    status = 'PASS' if val_result.passed else 'FAIL'
    print(f"    validation: {status} "
          f"retention={val_result.retention_rate:.1%} "
          f"({val_result.total_terms - len(val_result.missing_terms)}/{val_result.total_terms} terms)")
    if val_result.missing_terms:
        print(f"    missing: {val_result.missing_terms[:10]}")

    chapter_out = {
        'id': chapter['id'],
        'title': chapter['title'],
        'subtopics': chapter['subtopics'],
        'content': markdown,
        'content_format': 'markdown',
        'sections': parse_sections_from_md(markdown),  # flat, for GuidePage.tsx
        'nested_sections': nested_sections,             # rich tree, for future use
    }
    return chapter_out, val_result


# ── Guide processing ──────────────────────────────────────────────────────────

def process_guide(
    subject_num: int,
    chapter_filter: str | None,
    threshold: float,
) -> None:
    cfg = GUIDES[subject_num]
    pdf_path = PDF_DIR / cfg['pdf']
    if not pdf_path.exists():
        sys.exit(f'PDF not found: {pdf_path}')

    print(f'\nProcessing subject {subject_num} ({cfg["key"]}) from {pdf_path.name}')

    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)
    doc.close()

    label_map = build_page_label_map(pdf_path)
    chapters = cfg['chapters']
    page_groups = get_chapter_pdf_pages(chapters, label_map, total_pages)

    guide_dir = DATA / 'guide'
    guide_dir.mkdir(exist_ok=True)

    # Load existing JSON to preserve skipped chapters
    existing_json_path = guide_dir / f'subject{subject_num}_guide.json'
    existing_chapters: dict[str, dict] = {}
    if existing_json_path.exists():
        with open(existing_json_path, encoding='utf-8') as f:
            existing = json.load(f)
        existing_chapters = {c['id']: c for c in existing.get('chapters', [])}

    result_chapters: list[dict] = []
    md_parts = [f'# {cfg["subject"]}\n']
    all_validation: list[dict] = []
    flagged: list[dict] = []

    for chapter, page_indices in zip(chapters, page_groups):
        if chapter_filter and chapter['id'] != chapter_filter:
            result_chapters.append(
                existing_chapters.get(chapter['id'], {
                    'id': chapter['id'],
                    'title': chapter['title'],
                    'subtopics': chapter['subtopics'],
                    'content': '',
                })
            )
            continue

        chapter_out, val = process_chapter(chapter, pdf_path, page_indices, threshold)
        result_chapters.append(chapter_out)
        all_validation.append(asdict(val))

        if not val.passed:
            flagged.append({
                'chapter_id': chapter['id'],
                'title': chapter['title'],
                'retention_rate': val.retention_rate,
                'missing_terms': val.missing_terms,
            })

        md_parts.append(f'\n{chapter_out["content"]}')

    # Write Markdown
    md_path = guide_dir / f'subject{subject_num}_guide.md'
    md_path.write_text('\n'.join(md_parts), encoding='utf-8')
    print(f'  Saved {md_path}')

    # Write JSON (strip nested_sections for main guide JSON to keep it lean)
    json_chapters = []
    for c in result_chapters:
        ch = {k: v for k, v in c.items() if k != 'nested_sections'}
        json_chapters.append(ch)
    json_data = {'subject': cfg['subject'], 'chapters': json_chapters}
    json_path = guide_dir / f'subject{subject_num}_guide.json'
    json_path.write_text(json.dumps(json_data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'  Saved {json_path}')

    # Write nested structure JSON (full tree)
    nested_data = {
        'subject': cfg['subject'],
        'chapters': [
            {**c, 'nested_sections': c.get('nested_sections', [])}
            for c in result_chapters
        ],
    }
    nested_path = guide_dir / f'subject{subject_num}_guide_nested.json'
    nested_path.write_text(json.dumps(nested_data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'  Saved {nested_path}')

    # Write validation report
    report = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'subject': subject_num,
        'threshold': threshold,
        'overall_passed': all(v['passed'] for v in all_validation),
        'chapters': all_validation,
    }
    report_path = guide_dir / f'subject{subject_num}_validation_report.json'
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    overall = 'PASSED' if report['overall_passed'] else 'FAILED'
    print(f'  Validation: {report_path} [{overall}]')

    if flagged:
        flagged_path = guide_dir / f'subject{subject_num}_flagged.json'
        flagged_path.write_text(json.dumps(flagged, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'  Flagged: {flagged_path} ({len(flagged)} chapters need review)')


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description='Extract guide PDFs to structured Markdown (span-based, no LLM)'
    )
    parser.add_argument('--subject', type=int, choices=[1, 2])
    parser.add_argument('--all', action='store_true', help='Process both subjects')
    parser.add_argument('--chapter', help='Only this chapter ID (e.g. s1c1)')
    parser.add_argument(
        '--threshold', type=float, default=DEFAULT_THRESHOLD,
        help=f'Key term retention threshold (default {DEFAULT_THRESHOLD})'
    )
    args = parser.parse_args()

    if not args.subject and not args.all:
        parser.error('Specify --subject 1|2 or --all')

    subjects = [1, 2] if args.all else [args.subject]
    for n in subjects:
        process_guide(n, args.chapter, args.threshold)

    print('\nDone.')


if __name__ == '__main__':
    main()
