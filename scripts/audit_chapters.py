#!/usr/bin/env python3
"""LLM-based chapter content audit for iPAS study guides.

Reads subject{N}_guide.json and sends each chapter to Claude for review:
  - Are all expected subtopics covered?
  - Is any content clearly misplaced (belongs to a different chapter)?

Output: data/{level}/guide/subject{N}_audit_report.json

Usage:
  uv run python3 scripts/audit_chapters.py --all
  uv run python3 scripts/audit_chapters.py --subject 1
  uv run python3 scripts/audit_chapters.py --level 初級 --subject 1 --chapter s1c1
  uv run python3 scripts/audit_chapters.py --all --dry-run   # print prompts only

Requires: ANTHROPIC_API_KEY environment variable.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import anthropic
except ImportError:
    sys.exit('anthropic not found. Run: uv sync')

BASE = Path('/home/james/projects/ipas-test')

MODEL = 'claude-haiku-4-5-20251001'
# Truncate chapter content to avoid excessive token usage
CONTENT_MAX_CHARS = 6000


def _load_manifest(data_dir: Path) -> dict[int, dict]:
    """Load chapter definitions from toc_manifest.json."""
    with open(data_dir / 'toc_manifest.json', encoding='utf-8') as f:
        manifest = json.load(f)
    result = {}
    for i, subj in enumerate(manifest['subjects'], 1):
        result[i] = {'subject': subj['subject'], 'chapters': subj['chapters']}
    return result


def build_prompt(chapter_id: str, chapter_title: str, subtopics: list[str], content: str) -> str:
    subtopics_text = '\n'.join(f'  - {t}' for t in subtopics)
    truncated = content[:CONTENT_MAX_CHARS]
    if len(content) > CONTENT_MAX_CHARS:
        truncated += '\n\n[... 內容已截斷 ...]'
    return f"""\
你是一位 iPAS AI 考試教材品質審核員。

以下是章節定義：
章節 ID：{chapter_id}
章節標題：{chapter_title}
預定涵蓋的子主題：
{subtopics_text}

以下是從 PDF 解析出的章節內容（Markdown 格式）：
---
{truncated}
---

請審核：
1. 預定子主題是否都有在內容中出現？列出缺漏的。
2. 是否有明顯屬於其他章節的內容混入？
3. 整體品質評分：
   - PASS：所有子主題覆蓋完整，無明顯錯置
   - WARN：少數子主題未提及，但主體正確
   - FAIL：多個子主題缺漏，或有嚴重內容錯置

請以以下 JSON 格式回覆（只輸出 JSON，不要加說明）：
{{"status": "PASS", "missing_subtopics": [], "misplaced_content": "", "notes": "所有子主題均有涵蓋"}}\
"""


def audit_chapter(
    client: anthropic.Anthropic,
    chapter_id: str,
    chapter_title: str,
    subtopics: list[str],
    content: str,
    dry_run: bool,
) -> dict:
    prompt = build_prompt(chapter_id, chapter_title, subtopics, content)

    if dry_run:
        print(f'\n{"="*60}')
        print(f'[DRY RUN] {chapter_id} — {chapter_title}')
        print(f'{"="*60}')
        print(prompt[:800] + ('...' if len(prompt) > 800 else ''))
        return {
            'id': chapter_id,
            'title': chapter_title,
            'status': 'DRY_RUN',
            'missing_subtopics': [],
            'misplaced_content': '',
            'notes': '',
            'content_chars': len(content),
        }

    print(f'  Auditing {chapter_id} ({chapter_title})...', end=' ', flush=True)
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=512,
            messages=[{'role': 'user', 'content': prompt}],
        )
        raw = response.content[0].text.strip()

        # Extract JSON (model may wrap in code fences)
        if '```' in raw:
            import re
            m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw, re.DOTALL)
            raw = m.group(1) if m else raw
        result = json.loads(raw)
        status = result.get('status', 'UNKNOWN')
        print(status)
        return {
            'id': chapter_id,
            'title': chapter_title,
            'status': status,
            'missing_subtopics': result.get('missing_subtopics', []),
            'misplaced_content': result.get('misplaced_content', ''),
            'notes': result.get('notes', ''),
            'content_chars': len(content),
        }
    except Exception as exc:
        print(f'ERROR: {exc}')
        return {
            'id': chapter_id,
            'title': chapter_title,
            'status': 'ERROR',
            'missing_subtopics': [],
            'misplaced_content': '',
            'notes': str(exc),
            'content_chars': len(content),
        }


def audit_subject(
    subject_num: int,
    chapter_filter: str | None,
    dry_run: bool,
    client: anthropic.Anthropic | None,
    guide_dir: Path,
    manifest: dict[int, dict],
) -> None:
    guide_path = guide_dir / f'subject{subject_num}_guide.json'
    if not guide_path.exists():
        print(f'[SKIP] {guide_path} not found — run: uv run python3 scripts/parse_guides.py')
        return

    with open(guide_path, encoding='utf-8') as f:
        guide = json.load(f)

    manifest_chapters = {ch['id']: ch for ch in manifest[subject_num]['chapters']}

    print(f'\nAuditing subject {subject_num} ({guide["subject"]})...')
    chapter_results = []

    for ch in guide['chapters']:
        ch_id = ch['id']
        if chapter_filter and ch_id != chapter_filter:
            continue

        manifest_ch = manifest_chapters.get(ch_id, {})
        subtopics = manifest_ch.get('subtopics', ch.get('subtopics', []))
        content = ch.get('content', '')

        result = audit_chapter(
            client=client,
            chapter_id=ch_id,
            chapter_title=ch['title'],
            subtopics=subtopics,
            content=content,
            dry_run=dry_run,
        )
        chapter_results.append(result)

    if dry_run or not chapter_results:
        return

    pass_count = sum(1 for r in chapter_results if r['status'] == 'PASS')
    warn_count = sum(1 for r in chapter_results if r['status'] == 'WARN')
    fail_count = sum(1 for r in chapter_results if r['status'] in ('FAIL', 'ERROR'))

    if fail_count > 0:
        overall = 'FAIL'
    elif warn_count > 0:
        overall = 'WARN'
    else:
        overall = 'PASS'

    report = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'subject': subject_num,
        'model': MODEL,
        'overall_status': overall,
        'pass_count': pass_count,
        'warn_count': warn_count,
        'fail_count': fail_count,
        'chapters': chapter_results,
    }

    report_path = guide_dir / f'subject{subject_num}_audit_report.json'
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'  Saved {report_path} [{overall}] '
          f'(PASS:{pass_count} WARN:{warn_count} FAIL:{fail_count})')


def main() -> None:
    parser = argparse.ArgumentParser(
        description='LLM audit of parsed chapter content against expected subtopics'
    )
    parser.add_argument('--level', default='初級',
                        help='資料等級資料夾（預設: 初級）')
    parser.add_argument('--subject', type=int,
                        help='只審核指定科目')
    parser.add_argument('--all', action='store_true', help='審核所有科目')
    parser.add_argument('--chapter', help='Only this chapter ID (e.g. s1c1)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print prompts without calling the API')
    args = parser.parse_args()

    if not args.subject and not args.all:
        parser.error('Specify --subject N or --all')

    data_dir = BASE / 'data' / args.level
    guide_dir = data_dir / 'guide'
    manifest = _load_manifest(data_dir)

    client = None
    if not args.dry_run:
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            sys.exit('ANTHROPIC_API_KEY not set')
        client = anthropic.Anthropic(api_key=api_key)

    available_subjects = sorted(manifest.keys())
    subjects = available_subjects if args.all else [args.subject]
    for n in subjects:
        if n not in manifest:
            print(f'[WARN] Subject {n} not found in manifest for level "{args.level}"')
            continue
        audit_subject(n, args.chapter, args.dry_run, client, guide_dir, manifest)

    print('\nDone.')


if __name__ == '__main__':
    main()
