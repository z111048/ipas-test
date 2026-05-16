#!/usr/bin/env python3
"""Review cleaned PDF pages with Codex CLI in read-only sandbox and write JSON results."""

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

BASE = Path('/home/james/projects/ipas-test')
SCHEMA = BASE / 'scripts' / 'codex_page_review.schema.json'


def load_json(path: Path) -> dict:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def compact_page_payload(page: dict) -> dict:
    return {
        'key': page['key'],
        'pdf': page['pdf'],
        'strategy': page['strategy'],
        'page_index': page['page_index'],
        'page_number': page['page_number'],
        'page_label': page.get('page_label') or '',
        'cleaned_text': page.get('cleaned_text') or '',
        'removed': page.get('removed') or {},
        'continues_from_previous': page.get('continues_from_previous'),
        'continues_to_next': page.get('continues_to_next'),
        'detected_headings': page.get('headings') or [],
        'markers': page.get('markers') or [],
    }


def prompt_for_page(page: dict) -> str:
    payload = json.dumps(compact_page_payload(page), ensure_ascii=False, indent=2)
    return f"""你正在審核 PDF 單頁抽取結果。請只輸出符合 schema 的 JSON，不要 Markdown。

任務：
1. 確認 cleaned_text 開頭與結尾是否已移除頁首、頁尾、頁碼、表格欄名等雜訊。
2. 判斷本頁是否承接上一頁、是否延續到下一頁。
3. 確認 detected_headings 是否符合本頁可見章節層級；若漏判或誤判，列在 suggested_headings / false_headings。
4. 如果不確定，使用 status=warn 並在 issues 說明。

頁面資料：
{payload}
"""


def image_argument(level: str, page: dict) -> list[str]:
    page_image = page.get('page_image') or {}
    rel_path = page_image.get('path')
    if not rel_path:
        return []
    page_extract_image = (
        BASE
        / 'data'
        / level
        / 'page_extract'
        / page['key']
        / 'pages'
        / f'page_{page["page_index"]:03d}.json'
    )
    if not page_extract_image.exists():
        return []
    raw_page = load_json(page_extract_image)
    raw_image = raw_page.get('page_image') or {}
    raw_rel_path = raw_image.get('path')
    if not raw_rel_path:
        return []
    resolved = (page_extract_image.parent / raw_rel_path).resolve()
    return ['--image', str(resolved)] if resolved.exists() else []


def run_codex_review(level: str, page: dict, out_path: Path, model: str | None, with_image: bool) -> dict:
    codex_home = Path('/tmp/ipas-codex-page-review-home')
    codex_home.mkdir(parents=True, exist_ok=True)
    source_home = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex')))
    for filename in ('auth.json', 'config.toml', 'installation_id', 'version.json'):
        source = source_home / filename
        if source.exists() and not (codex_home / filename).exists():
            shutil.copy2(source, codex_home / filename)
    with tempfile.NamedTemporaryFile(prefix='codex-page-review-', suffix='.json', delete=False) as tmp:
        tmp_path = Path(tmp.name)

    command = [
        'codex',
        'exec',
        '--sandbox',
        'read-only',
        '--cd',
        str(BASE),
        '--output-schema',
        str(SCHEMA),
        '--output-last-message',
        str(tmp_path),
        '--color',
        'never',
        '--ephemeral',
    ]
    if model:
        command.extend(['--model', model])
    if with_image:
        command.extend(image_argument(level, page))
    command.append(prompt_for_page(page))

    completed = subprocess.run(
        command,
        cwd=BASE,
        env={
            **os.environ,
            'CODEX_HOME': str(codex_home),
        },
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        result = {
            'page_index': page['page_index'],
            'page_number': page['page_number'],
            'status': 'fail',
            'error': {
                'returncode': completed.returncode,
                'stdout': completed.stdout[-4000:],
                'stderr': completed.stderr[-4000:],
            },
        }
        write_json(out_path, result)
        return result

    try:
        result = json.loads(tmp_path.read_text(encoding='utf-8'))
    except Exception as exc:
        result = {
            'page_index': page['page_index'],
            'page_number': page['page_number'],
            'status': 'fail',
            'error': {
                'message': f'Cannot parse Codex output: {exc}',
                'stdout': completed.stdout[-4000:],
                'stderr': completed.stderr[-4000:],
                'last_message': tmp_path.read_text(encoding='utf-8', errors='replace')[-4000:],
            },
        }
    write_json(out_path, result)
    return result


def selected_pages(level: str, key: str, page_number: int | None) -> list[Path]:
    pages_dir = BASE / 'data' / level / 'page_clean' / key / 'pages'
    if page_number is not None:
        path = pages_dir / f'page_{page_number - 1:03d}.json'
        if not path.exists():
            raise FileNotFoundError(path)
        return [path]
    return sorted(pages_dir.glob('page_*.json'))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--level', default='初級', help='資料等級資料夾（預設: 初級）')
    parser.add_argument('--key', help='只審核指定 PDF key，如 guide1/exam1/sample')
    parser.add_argument('--all', action='store_true', help='審核所有 page_clean PDF')
    parser.add_argument('--page', type=int, help='只審核 1-based PDF 頁碼')
    parser.add_argument('--limit', type=int, help='每份 PDF 最多審核幾頁，方便分批執行')
    parser.add_argument('--force', action='store_true', help='覆寫既有審核 JSON')
    parser.add_argument('--model', help='傳給 Codex CLI 的 model 名稱')
    parser.add_argument('--with-image', action='store_true', help='把去浮水印頁面截圖也傳給 Codex CLI')
    args = parser.parse_args()

    clean_root = BASE / 'data' / args.level / 'page_clean'
    if not args.key and not args.all:
        parser.error('Specify --key KEY or --all')
    keys = [p.name for p in sorted(clean_root.iterdir()) if (p / 'pages').exists()] if args.all else [args.key]

    summary = {}
    for key in keys:
        paths = selected_pages(args.level, key, args.page)
        if args.limit:
            paths = paths[:args.limit]
        key_summary = {'pass': 0, 'warn': 0, 'fail': 0, 'skipped': 0}
        for page_path in paths:
            page = load_json(page_path)
            out_path = (
                BASE
                / 'data'
                / args.level
                / 'codex_page_review'
                / key
                / f'page_{page["page_index"]:03d}.json'
            )
            if out_path.exists() and not args.force:
                key_summary['skipped'] += 1
                continue
            result = run_codex_review(args.level, page, out_path, args.model, args.with_image)
            key_summary[result.get('status', 'fail')] = key_summary.get(result.get('status', 'fail'), 0) + 1
            print(f'{key} page {page["page_number"]}: {result.get("status")}')
        summary[key] = key_summary
    write_json(BASE / 'data' / args.level / 'codex_page_review' / 'summary.json', summary)


if __name__ == '__main__':
    main()
