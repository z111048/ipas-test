#!/usr/bin/env python3
"""Compare Gemini Vision audit results vs existing guide structure via Codex CLI.

SOP 位置：此腳本為教材品質審核流程的第三步，在 PDF 更新後重跑。

完整 SOP（官網 PDF 更新時執行）：
  Step 1: uv run python3 scripts/pdf_vision_audit.py --level 初級 --subject N
          → data/{level}/audit_cache/{key}/  (Gemini Vision 逐頁結構萃取)

  Step 2: python3 scripts/codex_audit_compare.py --level 初級 --subject N
          → data/{level}/audit_compare/{key}/{chapter_id}.json  (Codex 比對報告)

  Step 3: 人工審閱報告，依建議修正 guide JSON / 重跑 parse_guides.py

比對設計：
  A = Gemini Vision audit 結果（audit_cache）— 以標題層次 + 特殊內容(表格/圖片/公式)為主
  B = 現有 subject{N}_guide.json — 提取標題大綱 + 特殊內容標記

  「標題結構對齊」是核心：找出 A/B 標題層級不一致、A 有但 B 缺的標題、
  表格/圖片在 B 中的處理方式是否正確。

Output: data/{level}/audit_compare/{key}/{chapter_id}.json
  {
    "chapter_id": "s2c1",
    "status": "ok" | "warn" | "fail" | "error",
    "heading_diffs": [...],   # 標題層級差異
    "missing_headings": [...],# A 有但 B 缺
    "table_issues": [...],    # 表格問題
    "image_issues": [...],    # 圖片描述問題
    "other_issues": [...],
    "codex_response": "..."
  }

Usage:
  python3 scripts/codex_audit_compare.py --level 初級 --subject 2
  python3 scripts/codex_audit_compare.py --level 初級 --subject 2 --chapter s2c1
  python3 scripts/codex_audit_compare.py --level 初級 --subject 2 --dry-run
  python3 scripts/codex_audit_compare.py --level 初級 --subject 2 --force  # 重跑已完成章節
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

BASE = Path('/home/james/projects/ipas-test')
DEFAULT_TIMEOUT = 180  # seconds per Codex call

# ── Data loading ──────────────────────────────────────────────────────────────

def load_manifest(level: str) -> dict:
    path = BASE / 'data' / level / 'toc_manifest.json'
    return json.loads(path.read_text(encoding='utf-8'))


def load_guide(level: str, subject_num: int) -> dict:
    path = BASE / 'data' / level / 'guide' / f'subject{subject_num}_guide.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    return {ch['id']: ch for ch in data.get('chapters', [])}


def load_audit_pages(level: str, key: str, page_start: int, page_end: int) -> list[dict]:
    cache_dir = BASE / 'data' / level / 'audit_cache' / key
    pages = []
    for idx in range(page_start, page_end + 1):
        p = cache_dir / f'page_{idx:03d}.json'
        if p.exists():
            d = json.loads(p.read_text(encoding='utf-8'))
            if d.get('type') == 'content':
                pages.append(d)
    return pages


# ── Structure extraction ──────────────────────────────────────────────────────

def extract_audit_structure(pages: list[dict]) -> dict:
    """From audit blocks, extract headings + special content (tables/images/formulas)."""
    headings   = []  # [{"page": N, "level": 2, "text": "..."}]
    tables     = []  # [{"page": N, "html_preview": "..."}]
    images     = []  # [{"page": N, "description": "..."}]
    formulas   = []  # [{"page": N, "latex": "..."}]

    for page in pages:
        idx = page.get('idx', '?')
        for b in page.get('blocks', []):
            btype = b.get('type')
            if btype == 'heading':
                headings.append({'page': idx, 'level': b['level'], 'text': b['text']})
            elif btype == 'table':
                html = b.get('html', '')
                headings_preview = html[:200]
                tables.append({'page': idx, 'html_preview': headings_preview})
            elif btype == 'image':
                images.append({'page': idx, 'description': b.get('description', '')})
            elif btype == 'formula':
                formulas.append({'page': idx, 'latex': b.get('latex', ''), 'display': b.get('display')})

    return {'headings': headings, 'tables': tables, 'images': images, 'formulas': formulas}


def extract_guide_structure(content: str) -> dict:
    """From guide Markdown, extract heading outline + special content markers."""
    headings  = []  # [{"level": 2, "text": "..."}]
    tables_md = []  # lines that look like markdown tables
    has_html_tables = False
    images_mentioned = []  # paragraphs mentioning 圖/示意圖/流程圖

    for line in content.splitlines():
        # Headings
        m = re.match(r'^(#{1,6})\s+(.+)', line)
        if m:
            level = len(m.group(1))
            text = m.group(2).strip()
            headings.append({'level': level, 'text': text})
            continue
        # Markdown tables
        if re.match(r'^\|.+\|', line):
            tables_md.append(line[:80])
        # HTML tables
        if '<table' in line.lower():
            has_html_tables = True
        # Image mentions
        if re.search(r'圖\d*[：:、]|示意圖|流程圖|架構圖|如圖', line):
            images_mentioned.append(line.strip()[:100])

    return {
        'headings': headings,
        'markdown_table_rows': len(tables_md),
        'has_html_tables': has_html_tables,
        'markdown_table_sample': tables_md[:3],
        'image_mentions': images_mentioned[:5],
    }


# ── Prompt builder ────────────────────────────────────────────────────────────

def _fmt_headings(headings: list[dict], source: str) -> str:
    if not headings:
        return f'  （{source} 無標題）'
    lines = []
    for h in headings:
        indent = '  ' * (h['level'] - 1)
        prefix = 'H' + str(h['level']) if 'page' in h else '#' * h['level']
        page_str = f' [頁{h["page"]}]' if 'page' in h else ''
        lines.append(f'{indent}{prefix} {h["text"]}{page_str}')
    return '\n'.join(lines)


def build_prompt(
    chapter: dict,
    audit: dict,
    guide: dict,
    page_start: int,
    page_end: int,
) -> str:
    audit_headings_text  = _fmt_headings(audit['headings'], 'Gemini')
    guide_headings_text  = _fmt_headings(guide['headings'], '現有指引')

    # Tables section
    table_section = ''
    if audit['tables']:
        table_section += f'\n【A 表格】PDF 中發現 {len(audit["tables"])} 個表格：\n'
        for t in audit['tables']:
            table_section += f'  頁{t["page"]}: {t["html_preview"]}...\n'
        table_section += (
            f'【B 表格現況】現有指引含 Markdown 表格行數: {guide["markdown_table_rows"]}，'
            f'含 HTML <table>: {"是" if guide["has_html_tables"] else "否"}\n'
        )
        if guide['markdown_table_sample']:
            table_section += '  Markdown 表格樣本: ' + ' | '.join(guide['markdown_table_sample'][:2]) + '\n'

    # Images section
    image_section = ''
    if audit['images']:
        image_section += f'\n【A 圖片】PDF 中發現 {len(audit["images"])} 張圖片/示意圖：\n'
        for img in audit['images']:
            image_section += f'  頁{img["page"]}: {img["description"]}\n'
        image_section += '【B 圖片現況】現有指引提及圖片的段落：\n'
        if guide['image_mentions']:
            for m in guide['image_mentions']:
                image_section += f'  {m}\n'
        else:
            image_section += '  （無明確圖片描述）\n'

    # Formulas section
    formula_section = ''
    if audit['formulas']:
        formula_section += f'\n【A 公式】PDF 中發現 {len(audit["formulas"])} 個公式：\n'
        for f in audit['formulas']:
            formula_section += f'  頁{f["page"]} display={f["display"]}: {f["latex"][:80]}\n'

    return f"""你是一位教材品質審核專員，任務是比對以下兩份資料，找出現有指引需要修正的問題。

章節：{chapter['id']} — {chapter['title']}（PDF 頁面 {page_start}–{page_end}）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【A】Gemini Vision 從 PDF 萃取的標題結構（新，以此為準）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{audit_headings_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【B】現有學習指引的標題結構（舊，待比對）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{guide_headings_text}
{table_section}{image_section}{formula_section}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
請依序回答以下 5 項，每項條列，使用繁體中文：

1. **標題層級差異**
   - 比對 A 與 B 的每個標題，列出層級不一致的項目
   - 格式：`標題文字` A=H? B=H? → 建議改為 H?

2. **A 有但 B 缺的標題**
   - 列出 A 中存在、但 B 中完全找不到的標題（忽略措辭差異，聚焦缺失）

3. **表格處理問題**（若無表格則填「無」）
   - A 的 HTML 表格在 B 中是否正確呈現？缺失或格式錯誤請說明

4. **圖片描述問題**（若無圖片則填「無」）
   - A 中每張圖片，B 是否有對應描述？列出缺失項

5. **總體評估**
   - 狀態：OK / WARN / FAIL
   - 最優先修正項目（最多 3 點）"""


# ── Codex CLI ─────────────────────────────────────────────────────────────────

def call_codex(prompt: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    if not shutil.which('codex'):
        raise RuntimeError('找不到 Codex CLI，請先安裝並登入 codex。')
    result = subprocess.run(
        ['codex', 'exec', '-c', 'sandbox_permissions=["disk-full-read-access"]', '-'],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    output = result.stdout.strip()
    if result.returncode != 0 and not output:
        raise RuntimeError(f'Codex exit {result.returncode}: {result.stderr.strip()[:300]}')
    return output


# ── Issue parsing ─────────────────────────────────────────────────────────────

def parse_status(text: str) -> str:
    upper = text.upper()
    if 'FAIL' in upper:
        return 'fail'
    if 'WARN' in upper:
        return 'warn'
    if re.search(r'\bOK\b', upper):
        return 'ok'
    return 'unknown'


def parse_section(text: str, header_pattern: str) -> list[str]:
    """Extract bullet points under a numbered section header."""
    section_re = re.compile(header_pattern, re.IGNORECASE)
    next_section_re = re.compile(r'^\d+\.\s+\*\*', re.MULTILINE)
    m = section_re.search(text)
    if not m:
        return []
    start = m.end()
    nxt = next_section_re.search(text, start)
    chunk = text[start: nxt.start() if nxt else start + 2000]
    items = []
    for line in chunk.splitlines():
        line = line.strip()
        if line.startswith(('-', '•', '*')) or re.match(r'^`', line):
            cleaned = re.sub(r'^[-•*\s]+', '', line).strip()
            if cleaned and len(cleaned) > 3:
                items.append(cleaned)
    return items[:15]


def parse_result(response: str) -> dict:
    return {
        'heading_diffs':     parse_section(response, r'1\.\s+\*\*標題層級差異'),
        'missing_headings':  parse_section(response, r'2\.\s+\*\*A 有但 B 缺'),
        'table_issues':      parse_section(response, r'3\.\s+\*\*表格處理問題'),
        'image_issues':      parse_section(response, r'4\.\s+\*\*圖片描述問題'),
        'priority_fixes':    parse_section(response, r'5\.\s+\*\*總體評估'),
        'status':            parse_status(response),
    }


# ── Per-chapter processing ────────────────────────────────────────────────────

def process_chapter(
    level: str,
    subject_key: str,
    chapter: dict,
    guide_chapters: dict,
    out_dir: Path,
    dry_run: bool = False,
    force: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict:
    ch_id = chapter['id']
    out_path = out_dir / f'{ch_id}.json'

    if not force and out_path.exists():
        cached = json.loads(out_path.read_text(encoding='utf-8'))
        print(f'  [{ch_id}] cached (status={cached.get("status")}) — use --force to rerun')
        return cached

    page_start, page_end = chapter['page_range']
    guide_ch      = guide_chapters.get(ch_id, {})
    guide_content = guide_ch.get('content', '') or ''
    audit_pages   = load_audit_pages(level, subject_key, page_start, page_end)

    # Extract structures from both sources
    audit  = extract_audit_structure(audit_pages)
    guide  = extract_guide_structure(guide_content)

    print(f'  [{ch_id}] {chapter["title"]}')
    print(
        f'    pages {page_start}–{page_end}  '
        f'audit: {len(audit["headings"])}H/{len(audit["tables"])}T/{len(audit["images"])}I  '
        f'guide: {len(guide["headings"])}H  chars={len(guide_content)}'
    )

    prompt = build_prompt(chapter, audit, guide, page_start, page_end)

    if dry_run:
        print(f'    [dry-run] prompt {len(prompt)} chars')
        print('    --- prompt preview ---')
        print(prompt[:600])
        print('    ...')
        return {}

    print(f'    → Codex ...', end=' ', flush=True)
    try:
        response = call_codex(prompt, timeout)
        parsed   = parse_result(response)
        print(
            f'done  status={parsed["status"]}  '
            f'heading_diffs={len(parsed["heading_diffs"])}  '
            f'missing={len(parsed["missing_headings"])}'
        )
    except Exception as exc:
        print(f'ERROR: {exc}')
        response = f'ERROR: {exc}'
        parsed   = {'heading_diffs': [], 'missing_headings': [], 'table_issues': [],
                    'image_issues': [], 'priority_fixes': [], 'status': 'error'}

    result = {
        'chapter_id':    ch_id,
        'chapter_title': chapter['title'],
        'level':         level,
        'subject_key':   subject_key,
        'audit_pages':   [page_start, page_end],
        'audit_headings_count': len(audit['headings']),
        'guide_headings_count': len(guide['headings']),
        'guide_chars':   len(guide_content),
        **parsed,
        'codex_response': response,
    }
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--level',   default='初級')
    parser.add_argument('--subject', type=int, required=True)
    parser.add_argument('--chapter', help='只處理指定章節 ID（如 s2c1）')
    parser.add_argument('--force',   action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--timeout', type=int, default=DEFAULT_TIMEOUT)
    args = parser.parse_args()

    if not args.dry_run and not shutil.which('codex'):
        sys.exit('ERROR: codex CLI not found.')

    manifest  = load_manifest(args.level)
    subject   = manifest['subjects'][args.subject - 1]
    key       = subject['key']
    chapters  = subject['chapters']
    guide_chs = load_guide(args.level, args.subject)

    if args.chapter:
        chapters = [ch for ch in chapters if ch['id'] == args.chapter]
        if not chapters:
            sys.exit(f'Chapter {args.chapter!r} not found.')

    out_dir = BASE / 'data' / args.level / 'audit_compare' / key
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f'=== codex_audit_compare (v2) ===')
    print(f'Level: {args.level}  Subject {args.subject}: {subject["subject"]}')
    print(f'Comparing: audit_cache/{key} ↔ subject{args.subject}_guide.json')
    print(f'Output: {out_dir.relative_to(BASE)}')
    print()

    results = []
    for i, ch in enumerate(chapters):
        if i > 0 and not args.dry_run:
            time.sleep(2)
        r = process_chapter(
            args.level, key, ch, guide_chs, out_dir,
            dry_run=args.dry_run, force=args.force, timeout=args.timeout,
        )
        if r:
            results.append(r)

    if results and not args.dry_run:
        summary = {
            'level': args.level, 'subject': args.subject, 'key': key,
            'total': len(results),
            'by_status': {},
            'sop_next_step': (
                'Review issues in each chapter JSON, '
                'apply fixes to guide content, '
                'then rerun parse_guides.py if regenerating from source.'
            ),
        }
        for r in results:
            s = r.get('status', 'unknown')
            summary['by_status'][s] = summary['by_status'].get(s, 0) + 1
        (out_dir / 'summary.json').write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')

        print(f'\n=== 完成 ===')
        for r in results:
            hd = len(r.get('heading_diffs', []))
            mh = len(r.get('missing_headings', []))
            ti = len(r.get('table_issues', []))
            ii = len(r.get('image_issues', []))
            print(f'  {r["chapter_id"]:6s} {r["status"]:7s}  '
                  f'heading_diffs={hd}  missing={mh}  table={ti}  image={ii}')
        print(f'  Summary: {summary["by_status"]}')


if __name__ == '__main__':
    main()
