#!/usr/bin/env python3
"""Extract structured Markdown from PDF pages using Claude Vision API.

Each page is rendered to PNG and sent to Claude for structured extraction.
Results are cached per page — re-runs only process missing/failed pages.

Cache layout:
  data/初級/pages_cache/{key}/page_{idx:03d}.json
    {
      "idx": 0,
      "type": "content" | "practice" | "skip",
      "markdown": "...",          # only when type == "content"
      "usage": {"input": N, "output": N}
    }
  data/初級/pages_cache/{key}/summary.json
    {total, content, practice, skip, failed, cost_usd}

Usage:
  uv run python3 scripts/pdf_vision_extract.py --subject 1
  uv run python3 scripts/pdf_vision_extract.py --all
  uv run python3 scripts/pdf_vision_extract.py --subject 1 --dry-run
  uv run python3 scripts/pdf_vision_extract.py --subject 1 --force   # reprocess all
  uv run python3 scripts/pdf_vision_extract.py --subject 1 --page 29 # single page
"""

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit('PyMuPDF not found. Run: uv sync')

try:
    import anthropic
except ImportError:
    sys.exit('anthropic not found. Run: uv sync')

BASE = Path('/home/james/projects/ipas-test')
DATA = BASE / 'data' / '初級'
PDF_DIR = DATA / 'pdfs'
CACHE_DIR = DATA / 'pages_cache'

MODEL = 'claude-sonnet-4-6'
# Pricing (USD per 1M tokens) — update if model changes
INPUT_PRICE_PER_M = 3.0
OUTPUT_PRICE_PER_M = 15.0

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

PAGE_PROMPT = """\
你正在處理一頁來自台灣 iPAS 初級 AI 應用規劃師學習指引的 PDF 頁面。

請依照以下規則回傳內容：

【輸出格式】
只能輸出以下三種之一：
1. Markdown 格式的頁面內容
2. [PRACTICE] — 若此頁為練習題或解析答案頁
3. [SKIP] — 若此頁為目錄、序言、版權頁、附件、空白頁或參考書目

【Markdown 格式規則】
- 使用 ## 表示主要章節標題（如 1. 2. 3. 等編號）
- 使用 ### 表示子節標題（如（1）（2）等）
- 使用 #### 表示字母小節（如 A. B. C.）
- 使用 - 表示清單項目（保留原有的條列符號）
- 表格轉為 Markdown 表格格式
- 省略頁碼（如 3-24）和章節頁首（如「第三章 人工智慧基礎概論」）
- 保留所有中英文專業術語，完整呈現技術內容
- 不要加入任何評語或說明，直接輸出內容

【判斷練習題的標準】
頁面以編號選擇題為主（如「1. 下列何者...（A）...（B）...」），或為解析頁（含「Ans（X）解析：」）"""


def page_to_png_b64(page: fitz.Page, scale: float = 2.0) -> str:
    """Render a PDF page to PNG at given scale, return base64 string."""
    mat = fitz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat)
    return base64.standard_b64encode(pix.tobytes('png')).decode()


def call_vision_api(client: anthropic.Anthropic, img_b64: str) -> dict:
    """Send one page image to Claude Vision. Returns {type, markdown?, usage}."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        messages=[{
            'role': 'user',
            'content': [
                {
                    'type': 'image',
                    'source': {
                        'type': 'base64',
                        'media_type': 'image/png',
                        'data': img_b64,
                    },
                },
                {'type': 'text', 'text': PAGE_PROMPT},
            ],
        }],
    )
    text = response.content[0].text.strip()
    usage = {
        'input': response.usage.input_tokens,
        'output': response.usage.output_tokens,
    }
    if text == '[PRACTICE]':
        return {'type': 'practice', 'usage': usage}
    if text == '[SKIP]':
        return {'type': 'skip', 'usage': usage}
    return {'type': 'content', 'markdown': text, 'usage': usage}


def process_guide(subject_num: int, force: bool = False, dry_run: bool = False,
                  single_page: int | None = None) -> None:
    cfg = GUIDES[subject_num]
    key = cfg['key']
    pdf_path = PDF_DIR / cfg['pdf']
    cache_dir = CACHE_DIR / key
    cache_dir.mkdir(parents=True, exist_ok=True)

    if not pdf_path.exists():
        print(f'  ERROR: PDF not found: {pdf_path}')
        return

    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)
    print(f'{key}: {total_pages} pages  →  {cache_dir}')

    # Determine which pages to process
    if single_page is not None:
        page_indices = [single_page]
    else:
        page_indices = list(range(total_pages))

    to_process = []
    for idx in page_indices:
        cache_path = cache_dir / f'page_{idx:03d}.json'
        if force or not cache_path.exists():
            to_process.append(idx)
        else:
            # Retry failed pages
            with open(cache_path) as f:
                cached = json.load(f)
            if cached.get('type') == 'error':
                to_process.append(idx)

    cached_count = len(page_indices) - len(to_process)
    print(f'  {cached_count} already cached, {len(to_process)} to process')

    if dry_run:
        # Rough estimate: ~1500 input tokens per page (image ≈ 1200 + prompt ≈ 300)
        est_input = len(to_process) * 1500
        est_output = len(to_process) * 500
        est_cost = (est_input * INPUT_PRICE_PER_M + est_output * OUTPUT_PRICE_PER_M) / 1_000_000
        print(f'  [dry-run] estimated cost: ${est_cost:.3f} USD for {len(to_process)} pages')
        doc.close()
        return

    if not to_process:
        print('  Nothing to process.')
        doc.close()
        _write_summary(cache_dir, total_pages)
        return

    client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))
    total_input = 0
    total_output = 0
    errors = 0

    for i, idx in enumerate(to_process):
        cache_path = cache_dir / f'page_{idx:03d}.json'
        print(f'  [{i+1}/{len(to_process)}] page {idx:3d} ...', end=' ', flush=True)
        try:
            img_b64 = page_to_png_b64(doc[idx])
            result = call_vision_api(client, img_b64)
            result['idx'] = idx
            cache_path.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                                  encoding='utf-8')
            usage = result.get('usage', {})
            total_input += usage.get('input', 0)
            total_output += usage.get('output', 0)
            print(f"{result['type']}  ({usage.get('input', 0)}in/{usage.get('output', 0)}out)")
        except Exception as e:
            print(f'ERROR: {e}')
            cache_path.write_text(json.dumps({'idx': idx, 'type': 'error', 'error': str(e)},
                                              ensure_ascii=False),
                                  encoding='utf-8')
            errors += 1
        # Avoid hitting rate limits
        if i < len(to_process) - 1:
            time.sleep(0.5)

    doc.close()

    cost = (total_input * INPUT_PRICE_PER_M + total_output * OUTPUT_PRICE_PER_M) / 1_000_000
    print(f'  Done. tokens: {total_input}in/{total_output}out  cost: ${cost:.4f} USD  errors: {errors}')
    _write_summary(cache_dir, total_pages)


def _write_summary(cache_dir: Path, total_pages: int) -> None:
    counts = {'total': total_pages, 'content': 0, 'practice': 0, 'skip': 0,
              'error': 0, 'missing': 0}
    total_input = total_output = 0
    for idx in range(total_pages):
        p = cache_dir / f'page_{idx:03d}.json'
        if not p.exists():
            counts['missing'] += 1
            continue
        with open(p) as f:
            d = json.load(f)
        t = d.get('type', 'missing')
        counts[t] = counts.get(t, 0) + 1
        u = d.get('usage', {})
        total_input += u.get('input', 0)
        total_output += u.get('output', 0)
    cost = (total_input * INPUT_PRICE_PER_M + total_output * OUTPUT_PRICE_PER_M) / 1_000_000
    summary = {**counts, 'total_input_tokens': total_input,
               'total_output_tokens': total_output, 'cost_usd': round(cost, 4)}
    (cache_dir / 'summary.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'  Summary: {summary}')


def main() -> None:
    parser = argparse.ArgumentParser(description='Extract PDF pages via Claude Vision')
    parser.add_argument('--subject', type=int, choices=[1, 2])
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--force', action='store_true', help='Reprocess all pages')
    parser.add_argument('--dry-run', action='store_true', help='Estimate cost only')
    parser.add_argument('--page', type=int, help='Process a single page index')
    args = parser.parse_args()

    if not args.subject and not args.all:
        parser.error('Specify --subject 1|2 or --all')

    subjects = [1, 2] if args.all else [args.subject]
    for s in subjects:
        process_guide(s, force=args.force, dry_run=args.dry_run, single_page=args.page)


if __name__ == '__main__':
    main()
