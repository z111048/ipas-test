#!/usr/bin/env python3
"""Compare Gemini Vision audit results vs existing guide content via Codex CLI.

For each chapter, builds a focused prompt containing:
  - Structured blocks extracted by pdf_vision_audit.py (headings, tables, images, lists)
  - Existing guide markdown content from subject{N}_guide.json

Codex CLI identifies gaps and quality issues:
  - Heading hierarchy errors (wrong level, missing headings)
  - Tables present in PDF but missing or not HTML in guide
  - Images/figures lacking descriptions
  - Content sections missing from guide

Output per chapter: data/{level}/audit_compare/{key}/{chapter_id}.json
  {
    "chapter_id": "s2c1",
    "chapter_title": "...",
    "audit_pages": [6, 21],
    "codex_response": "...",
    "issues": [...],   # parsed issue list
    "status": "ok" | "warn" | "fail"
  }

Usage:
  python3 scripts/codex_audit_compare.py --level 初級 --subject 2
  python3 scripts/codex_audit_compare.py --level 初級 --subject 2 --chapter s2c1
  python3 scripts/codex_audit_compare.py --level 初級 --subject 2 --dry-run
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
DEFAULT_TIMEOUT = 120  # seconds per Codex call

# ── Data loading ──────────────────────────────────────────────────────────────

def load_manifest(level: str) -> dict:
    path = BASE / 'data' / level / 'toc_manifest.json'
    return json.loads(path.read_text(encoding='utf-8'))


def load_guide(level: str, subject_num: int) -> dict:
    """Load subject guide JSON → {chapter_id: chapter_dict}."""
    path = BASE / 'data' / level / 'guide' / f'subject{subject_num}_guide.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    return {ch['id']: ch for ch in data.get('chapters', [])}


def load_audit_pages(level: str, key: str, page_start: int, page_end: int) -> list[dict]:
    """Load audit cache pages for a chapter's page range (inclusive)."""
    cache_dir = BASE / 'data' / level / 'audit_cache' / key
    pages = []
    for idx in range(page_start, page_end + 1):
        p = cache_dir / f'page_{idx:03d}.json'
        if p.exists():
            d = json.loads(p.read_text(encoding='utf-8'))
            if d.get('type') == 'content':
                pages.append(d)
    return pages


# ── Prompt builder ────────────────────────────────────────────────────────────

def _blocks_summary(pages: list[dict]) -> str:
    """Render audit blocks as readable text for Codex."""
    lines = []
    for page in pages:
        idx = page.get('idx', '?')
        lines.append(f'\n--- 頁面 {idx} ---')
        for b in page.get('blocks', []):
            btype = b.get('type')
            if btype == 'heading':
                lines.append(f'  H{b["level"]}: {b["text"]}')
            elif btype == 'paragraph':
                text = b.get('text', '')
                lines.append(f'  [段落] {text[:120]}{"…" if len(text) > 120 else ""}')
            elif btype == 'list':
                items = b.get('items', [])
                lines.append(f'  [清單 ordered={b.get("ordered")}] {len(items)} 項：{items[0][:60] if items else ""}…')
            elif btype == 'table':
                html = b.get('html', '')
                lines.append(f'  [表格 HTML] {html[:150]}…')
            elif btype == 'formula':
                lines.append(f'  [公式 display={b.get("display")}] {b.get("latex", "")[:80]}')
            elif btype == 'image':
                lines.append(f'  [圖片] {b.get("description", "")}')
    return '\n'.join(lines)


def build_prompt(
    chapter: dict,
    guide_content: str,
    audit_pages: list[dict],
    page_start: int,
    page_end: int,
) -> str:
    audit_text = _blocks_summary(audit_pages)
    guide_preview = guide_content[:4000]
    guide_truncated = '（內容過長，已截斷）' if len(guide_content) > 4000 else ''

    return f"""你是一位教材品質審核專員，正在比對兩份資料：

【A】Gemini Vision 從 PDF 逐頁萃取的結構化內容（頁面 {page_start}–{page_end}）
【B】現有系統中的學習指引章節 Markdown 內容

章節：{chapter['id']} — {chapter['title']}

══════════════════════════════════════════════
【A】PDF 頁面萃取結果（Gemini Vision audit）
══════════════════════════════════════════════
{audit_text}

══════════════════════════════════════════════
【B】現有學習指引內容（Markdown）
══════════════════════════════════════════════
{guide_preview}{guide_truncated}

══════════════════════════════════════════════
請逐一檢查下列問題，並以條列方式回答：

1. **標題層次錯誤**：A 中的 H2/H3/H4 標題，在 B 中是否層級錯誤或完全缺失？
   - 列出每個有問題的標題及建議修正

2. **表格缺失或格式錯誤**：A 中有 [表格 HTML] 的位置，B 中是否：
   - 完全缺失？
   - 僅用 Markdown 表格而非 HTML？
   - 列出每個表格的位置與問題

3. **圖片/圖表未描述**：A 中有 [圖片] 的位置，B 中是否有對應描述？
   - 列出每張圖片，說明 B 中是否有提及

4. **內容缺漏**：A 中有重要段落或清單，但 B 中完全缺少？
   - 列出關鍵缺漏項目（忽略細節差異，只列重要缺失）

5. **總體評估**：
   - 整體品質：OK（無重大問題）/ WARN（有部分問題）/ FAIL（有重大缺漏）
   - 優先修正項目（最多 3 項）

請使用繁體中文回答，條列清晰，不需重複引用原文。"""


# ── Codex CLI call ────────────────────────────────────────────────────────────

def call_codex(prompt: str, timeout: int = DEFAULT_TIMEOUT) -> str | None:
    if not shutil.which('codex'):
        raise RuntimeError('找不到 Codex CLI，請先安裝並登入 codex。')
    try:
        result = subprocess.run(
            ['codex', 'exec', '-c', 'sandbox_permissions=["disk-full-read-access"]', '-'],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout.strip()
        if result.returncode != 0 and not output:
            err = result.stderr.strip()[:300]
            raise RuntimeError(f'Codex exit {result.returncode}: {err}')
        return output or None
    except subprocess.TimeoutExpired:
        raise RuntimeError(f'Codex timeout after {timeout}s')


# ── Issue parsing ─────────────────────────────────────────────────────────────

def parse_status(response: str) -> str:
    """Extract OK / WARN / FAIL from Codex response."""
    upper = response.upper()
    if 'FAIL' in upper:
        return 'fail'
    if 'WARN' in upper:
        return 'warn'
    if 'OK' in upper:
        return 'ok'
    return 'unknown'


def parse_issues(response: str) -> list[str]:
    """Extract bullet-point issues from response."""
    issues = []
    for line in response.splitlines():
        line = line.strip()
        if line.startswith(('-', '•', '*', '·')) or re.match(r'^\d+[\.\)、]', line):
            cleaned = re.sub(r'^[-•*·\d\.\)、\s]+', '', line).strip()
            if cleaned and len(cleaned) > 5:
                issues.append(cleaned)
    return issues[:20]  # cap at 20


# ── Main processing ───────────────────────────────────────────────────────────

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
        print(f'  [{ch_id}] already done (status={cached.get("status")}) — skip')
        return cached

    page_start, page_end = chapter['page_range']
    guide_ch = guide_chapters.get(ch_id, {})
    guide_content = guide_ch.get('content', '') or ''
    audit_pages = load_audit_pages(level, subject_key, page_start, page_end)

    content_count = len(audit_pages)
    print(f'  [{ch_id}] {chapter["title"]}')
    print(f'    pages {page_start}–{page_end}  audit_content={content_count}  guide={len(guide_content)} chars')

    prompt = build_prompt(chapter, guide_content, audit_pages, page_start, page_end)

    if dry_run:
        print(f'    [dry-run] prompt length: {len(prompt)} chars')
        print(f'    [dry-run] prompt preview:\n{prompt[:400]}...')
        return {}

    print(f'    → calling Codex CLI...', end=' ', flush=True)
    try:
        response = call_codex(prompt, timeout=timeout)
        if not response:
            raise RuntimeError('empty response')
        status = parse_status(response)
        issues = parse_issues(response)
        print(f'done  status={status}  issues={len(issues)}')
    except Exception as exc:
        print(f'ERROR: {exc}')
        response = f'ERROR: {exc}'
        status = 'error'
        issues = [str(exc)]

    result = {
        'chapter_id':    ch_id,
        'chapter_title': chapter['title'],
        'level':         level,
        'subject_key':   subject_key,
        'audit_pages':   [page_start, page_end],
        'audit_content_pages': content_count,
        'guide_chars':   len(guide_content),
        'codex_response': response,
        'issues':        issues,
        'status':        status,
    }
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--level',   default='初級')
    parser.add_argument('--subject', type=int, required=True, help='科目編號（1-based）')
    parser.add_argument('--chapter', help='只處理指定章節 ID（如 s2c1）')
    parser.add_argument('--force',   action='store_true', help='強制重跑已完成的章節')
    parser.add_argument('--dry-run', action='store_true', help='預覽 prompt，不呼叫 Codex')
    parser.add_argument('--timeout', type=int, default=DEFAULT_TIMEOUT)
    args = parser.parse_args()

    if not args.dry_run and not shutil.which('codex'):
        sys.exit('ERROR: codex CLI not found. Install and authenticate first.')

    manifest  = load_manifest(args.level)
    subject   = manifest['subjects'][args.subject - 1]
    key       = subject['key']
    chapters  = subject['chapters']
    guide_chs = load_guide(args.level, args.subject)

    out_dir = BASE / 'data' / args.level / 'audit_compare' / key
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.chapter:
        chapters = [ch for ch in chapters if ch['id'] == args.chapter]
        if not chapters:
            sys.exit(f'Chapter {args.chapter!r} not found in subject {args.subject}')

    print(f'=== codex_audit_compare ===')
    print(f'Level: {args.level}  Subject: {args.subject} ({subject["subject"]})')
    print(f'Chapters: {len(chapters)}  Output: {out_dir.relative_to(BASE)}')

    results = []
    for i, ch in enumerate(chapters):
        if i > 0 and not args.dry_run:
            time.sleep(2)  # brief pause between Codex calls
        r = process_chapter(
            args.level, key, ch, guide_chs, out_dir,
            dry_run=args.dry_run, force=args.force, timeout=args.timeout,
        )
        if r:
            results.append(r)

    if results and not args.dry_run:
        # Write summary
        summary = {
            'level': args.level,
            'subject': args.subject,
            'subject_key': key,
            'chapters': len(results),
            'by_status': {},
        }
        for r in results:
            s = r.get('status', 'unknown')
            summary['by_status'][s] = summary['by_status'].get(s, 0) + 1
        summary_path = out_dir / 'summary.json'
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')

        print(f'\n=== 完成 ===')
        for r in results:
            print(f'  {r["chapter_id"]}: {r["status"]:7s}  issues={len(r.get("issues", []))}')
        print(f'  Summary: {summary["by_status"]}')
        print(f'  Output: {out_dir.relative_to(BASE)}')


if __name__ == '__main__':
    main()
