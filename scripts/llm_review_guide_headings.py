#!/usr/bin/env python3
"""Review guide heading hierarchy with Codex CLI and write JSON reports."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

BASE = Path('/home/james/projects/ipas-test')
GUIDE_CONTENT = BASE / 'frontend' / 'src' / 'generated' / 'guideContent'


def load_json(path: Path) -> Any:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def parse_guide_dir(path: Path) -> tuple[str, str]:
    if '-' not in path.name:
        raise ValueError(f'Unexpected guide content directory: {path}')
    level, key = path.name.split('-', 1)
    return level, key


def compact_heading(block: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        'index': index,
        'depth': block.get('depth'),
        'title': block.get('title') or block.get('text') or '',
        'page': block.get('page_number'),
        'kind': classify_heading(str(block.get('title') or block.get('text') or '')),
    }


def classify_heading(title: str) -> str:
    text = title.strip()
    if re.match(r'^\d+\.\d+\s+', text):
        return 'chapter_decimal'
    if re.match(r'^\d+\.\s+', text):
        return 'section_number'
    if re.match(r'^（\d+）', text):
        return 'paren_number'
    if re.match(r'^[A-Z]\.\s+', text):
        return 'upper_alpha'
    if re.match(r'^[a-z]\.\s+', text):
        return 'lower_alpha'
    if text.startswith('•'):
        return 'bullet'
    if text.startswith('○'):
        return 'circle'
    return 'plain'


def context_preview(blocks: list[dict[str, Any]], heading_index: int) -> dict[str, Any]:
    before = []
    after = []
    for block in blocks[max(0, heading_index - 1):heading_index]:
        text = block.get('text') or block.get('title') or block.get('markdown') or ''
        if text:
            before.append(str(text)[:80])
    for block in blocks[heading_index + 1:heading_index + 3]:
        text = block.get('text') or block.get('title') or block.get('markdown') or ''
        if text:
            after.append(str(text)[:100])
    return {'before': before, 'after': after}


def chapter_payload(content_path: Path) -> dict[str, Any]:
    content = load_json(content_path)
    blocks = content.get('blocks') or []
    headings = []
    for block_index, block in enumerate(blocks):
        if block.get('type') != 'heading':
            continue
        heading = compact_heading(block, len(headings) + 1)
        heading['block_id'] = block.get('id')
        heading['context'] = context_preview(blocks, block_index)
        headings.append(heading)
    return {
        'id': content.get('id') or content_path.stem,
        'title': content.get('title') or content_path.stem,
        'content_ref': content_path.name,
        'heading_count': len(headings),
        'headings': headings,
    }


def guide_payload(guide_dir: Path) -> dict[str, Any]:
    level, key = parse_guide_dir(guide_dir)
    chapters = [chapter_payload(path) for path in sorted(guide_dir.glob('*.json'))]
    return {
        'level': level,
        'key': key,
        'chapter_count': len(chapters),
        'chapters': chapters,
    }


def prompt_for_guide(payload: dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False, indent=2)
    return f"""你正在審核 iPAS AI 學習指引的 PDF 階層標題抽取結果。請只輸出 JSON，不要 Markdown。

審核目標：
1. 檢查每個章節的 heading depth 是否符合階層語意。
2. 檢查標題是否有被截斷、誤把內文當標題、或標題與下一行沒有合併。
3. 檢查同一章節內標號順序是否合理，例如 1. → 2.、（1）→（2）、A.→B.。
4. 檢查深層項目是否應只是段落/list item，而不應是側邊欄標題。
5. 只根據提供的標題與前後文摘要判斷；不確定時標示 severity=warn。

請輸出這個 JSON 形狀：
{{
  "level": "...",
  "key": "...",
  "status": "pass|warn|fail",
  "summary": "繁體中文摘要",
  "stats": {{
    "chapters_reviewed": 0,
    "headings_reviewed": 0,
    "issue_count": 0
  }},
  "issues": [
    {{
      "severity": "warn|fail",
      "chapter_id": "...",
      "chapter_title": "...",
      "heading_index": 1,
      "title": "...",
      "current_depth": 3,
      "suggested_depth": 4,
      "issue_type": "wrong_depth|false_heading|truncated_heading|missing_heading|sequence_gap|merge_needed|other",
      "reason": "為什麼判斷有問題",
      "suggested_fix": "具體修正建議"
    }}
  ]
}}

待審核資料：
{data}
"""


def codex_home() -> Path:
    target = Path('/tmp/ipas-codex-heading-review-home')
    target.mkdir(parents=True, exist_ok=True)
    source_home = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex')))
    for filename in ('auth.json', 'config.toml', 'installation_id', 'version.json'):
        source = source_home / filename
        if source.exists() and not (target / filename).exists():
            shutil.copy2(source, target / filename)
    return target


def parse_json_response(text: str) -> Any:
    stripped = text.strip()
    if stripped.startswith('```'):
        stripped = re.sub(r'^```(?:json)?\s*', '', stripped)
        stripped = re.sub(r'\s*```$', '', stripped)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', stripped, flags=re.S)
        if match:
            return json.loads(match.group(0))
        raise


def run_codex(payload: dict[str, Any], out_path: Path, model: str | None, timeout: int) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile(prefix='codex-heading-review-', suffix='.json', delete=False) as tmp:
        tmp_path = Path(tmp.name)

    command = [
        'codex',
        'exec',
        '--sandbox',
        'read-only',
        '--cd',
        str(BASE),
        '--output-last-message',
        str(tmp_path),
        '--color',
        'never',
        '--ephemeral',
    ]
    if model:
        command.extend(['--model', model])
    command.append('-')

    completed = subprocess.run(
        command,
        cwd=BASE,
        env={**os.environ, 'CODEX_HOME': str(codex_home())},
        input=prompt_for_guide(payload),
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        result = {
            'level': payload['level'],
            'key': payload['key'],
            'status': 'fail',
            'summary': 'Codex CLI 執行失敗',
            'error': {
                'returncode': completed.returncode,
                'stdout': completed.stdout[-4000:],
                'stderr': completed.stderr[-4000:],
            },
        }
        write_json(out_path, result)
        return result

    try:
        result = parse_json_response(tmp_path.read_text(encoding='utf-8'))
    except Exception as exc:
        result = {
            'level': payload['level'],
            'key': payload['key'],
            'status': 'fail',
            'summary': '無法解析 Codex JSON 輸出',
            'error': {
                'message': str(exc),
                'stdout': completed.stdout[-4000:],
                'stderr': completed.stderr[-4000:],
                'last_message': tmp_path.read_text(encoding='utf-8', errors='replace')[-4000:],
            },
        }
    write_json(out_path, result)
    return result


def selected_guide_dirs(level: str | None, key: str | None, all_levels: bool) -> list[Path]:
    dirs = []
    for path in sorted(GUIDE_CONTENT.iterdir()):
        if not path.is_dir():
            continue
        dir_level, dir_key = parse_guide_dir(path)
        if not all_levels and level and dir_level != level:
            continue
        if key and dir_key != key:
            continue
        dirs.append(path)
    return dirs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--level', default='中級', help='資料等級，預設中級')
    parser.add_argument('--key', help='只審核指定 guide key，如 guide1')
    parser.add_argument('--all-levels', action='store_true', help='審核所有等級')
    parser.add_argument('--model', help='傳給 Codex CLI 的 model 名稱')
    parser.add_argument('--timeout', type=int, default=900, help='每份 guide 的 Codex timeout 秒數')
    parser.add_argument('--dry-run', action='store_true', help='只輸出 prompt payload，不呼叫 LLM')
    parser.add_argument('--force', action='store_true', help='覆寫既有報告')
    args = parser.parse_args()

    guide_dirs = selected_guide_dirs(args.level, args.key, args.all_levels)
    if not guide_dirs:
        raise SystemExit('No guide content directories selected.')

    summaries = []
    for guide_dir in guide_dirs:
        payload = guide_payload(guide_dir)
        out_dir = BASE / 'data' / payload['level'] / 'analysis' / 'heading_llm_review'
        out_path = out_dir / f'{payload["key"]}.json'
        if out_path.exists() and not args.force and not args.dry_run:
            result = load_json(out_path)
            print(f'SKIP {payload["level"]}/{payload["key"]}: {out_path.relative_to(BASE)} exists')
        elif args.dry_run:
            dry_path = out_dir / f'{payload["key"]}.payload.json'
            write_json(dry_path, payload)
            result = {'level': payload['level'], 'key': payload['key'], 'status': 'dry-run', 'issues': []}
            print(f'DRY {payload["level"]}/{payload["key"]}: wrote {dry_path.relative_to(BASE)}')
        else:
            print(f'RUN {payload["level"]}/{payload["key"]}: {payload["chapter_count"]} chapters')
            result = run_codex(payload, out_path, args.model, args.timeout)
            print(f'WROTE {out_path.relative_to(BASE)} status={result.get("status")}')
        summaries.append({
            'level': payload['level'],
            'key': payload['key'],
            'status': result.get('status'),
            'issue_count': len(result.get('issues') or []),
        })

    if not args.dry_run:
        by_level: dict[str, list[dict[str, Any]]] = {}
        for item in summaries:
            by_level.setdefault(item['level'], []).append(item)
        for level, items in by_level.items():
            write_json(
                BASE / 'data' / level / 'analysis' / 'heading_llm_review' / 'summary.json',
                {
                    'level': level,
                    'items': items,
                    'issue_count': sum(item['issue_count'] for item in items),
                    'status_counts': {status: sum(1 for item in items if item['status'] == status) for status in sorted({item['status'] for item in items})},
                },
            )


if __name__ == '__main__':
    main()
