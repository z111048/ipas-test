#!/usr/bin/env python3
"""Extract structured exam questions from official exam PDF pages via Gemini Vision.

This script is intentionally separate from pdf_vision_extract.py. The guide
extractor produces Markdown and headings for study-guide pages; this extractor
produces reviewable question records for official exam and sample exam pages.

Cache layout:
  data/{level}/exam_pages_cache/{key}/page_{idx:03d}.json
    {
      "idx": 0,
      "page_type": "exam_questions" | "answer_key" | "mixed" | "cover" | "blank" | "other",
      "shared_contexts": [...],
      "questions": [...],
      "answers": [...],
      "visual_refs": [...],
      "raw_markdown": "...",
      "usage": {"input": N, "output": N}
    }
  data/{level}/exam_pages_cache/{key}/summary.json

Usage:
  uv run python3 scripts/gemini_exam_vision_extract.py --level 中級 --key exam2 --dry-run
  uv run python3 scripts/gemini_exam_vision_extract.py --level 中級 --key exam2 --page 12
  uv run python3 scripts/gemini_exam_vision_extract.py --level 中級 --all

Requires: GEMINI_API_KEY environment variable.
Override model with GOOGLE_MODEL env var (default: gemini-2.5-flash).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit('PyMuPDF not found. Run: uv sync')

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    sys.exit('google-genai not found. Run: uv add google-genai')

from extract_pdfs import EXAM_PDFS_BY_LEVEL

BASE = Path('/home/james/projects/ipas-test')
MODEL = os.environ.get('GOOGLE_MODEL', 'gemini-2.5-flash')

INPUT_PRICE_PER_M = 0.075
OUTPUT_PRICE_PER_M = 0.30

EXAM_PAGE_PROMPT = """\
你正在處理一頁台灣 iPAS AI 應用規劃師「歷屆試題 / 公告試題 / 考試樣題」PDF。

請只輸出合法 JSON，不要加 markdown code fence，不要加說明文字。

輸出格式：
{
  "page_type": "exam_questions" | "answer_key" | "mixed" | "cover" | "blank" | "other",
  "shared_contexts": [
    {
      "question_range": [43, 47],
      "text": "共用題幹、資料集描述、欄位說明或程式碼說明",
      "visual_refs": [
        {
          "label": "圖1",
          "placement": "context",
          "description": "圖表/截圖/資料表內容摘要",
          "bbox_hint": [0, 0, 1000, 1000]
        }
      ],
      "continues_from_previous_page": false,
      "continues_to_next_page": false
    }
  ],
  "questions": [
    {
      "number": 1,
      "question": "完整題幹文字。若題幹跨頁或接續共用題幹，請只放本題自己的題幹。",
      "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
      "answer": "A 或 null；若本頁看不到答案請填 null",
      "shared_context_range": [43, 47] 或 null,
      "visual_refs": [
        {
          "label": "圖1",
          "placement": "question" | "option_A" | "option_B" | "option_C" | "option_D" | "context",
          "description": "此圖與本題的關係",
          "bbox_hint": [0, 0, 1000, 1000]
        }
      ],
      "continues_from_previous_page": false,
      "continues_to_next_page": false,
      "confidence": "high" | "medium" | "low"
    }
  ],
  "answers": [
    {"number": 1, "answer": "A", "answer_text": "可選；答案欄或解析文字"}
  ],
  "visual_refs": [
    {
      "label": "圖1",
      "placement": "page",
      "description": "頁面上未能歸屬到特定題目的圖片/表格",
      "bbox_hint": [0, 0, 1000, 1000]
    }
  ],
  "raw_markdown": "保留頁面可讀文字，包含題號、答案欄、題目、選項、題組題幹與表格。"
}

辨識規則：
- 題號通常是「1.」「1．」或表格左側題號。請保留原始題號數字。
- 選項可能是「(A)」「（A）」或分行排版。請切成 A/B/C/D。
- 若本頁是答案表或解析頁，questions 可為空，answers 必須盡量補齊。
- 若出現「請回答 43~47 題」「回答第 48 至 50 題」等共用題幹，請放入 shared_contexts，並讓相關 questions 的 shared_context_range 指向該範圍。
- 若題組題幹、程式碼、表格、圖片在本頁但題目在下一頁，仍要輸出 shared_contexts，並標記 continues_to_next_page=true。
- 若本頁題目接續上一頁但缺少開頭，標記 continues_from_previous_page=true。
- 圖、表、程式碼截圖、資料集預覽都要在 visual_refs 中標記。bbox_hint 使用 0~1000 的頁面相對座標，粗略即可，但要包含整個圖或表。
- 不要自行推理教材知識，不要改寫題意。看不清楚的欄位填空字串或 null，confidence 設為 low。
"""


def page_to_png_bytes(page: fitz.Page, scale: float = 2.0) -> bytes:
    mat = fitz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat)
    return pix.tobytes('png')


def strip_json_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text).strip()
    return text


def normalize_result(data: dict[str, Any], usage: dict[str, int]) -> dict[str, Any]:
    return {
        'page_type': data.get('page_type', 'other'),
        'shared_contexts': data.get('shared_contexts') or [],
        'questions': data.get('questions') or [],
        'answers': data.get('answers') or [],
        'visual_refs': data.get('visual_refs') or [],
        'raw_markdown': data.get('raw_markdown') or '',
        'usage': usage,
    }


def call_exam_vision_api(client: genai.Client, img_bytes: bytes) -> dict[str, Any]:
    response = client.models.generate_content(
        model=MODEL,
        contents=[
            genai_types.Part.from_bytes(data=img_bytes, mime_type='image/png'),
            genai_types.Part.from_text(text=EXAM_PAGE_PROMPT),
        ],
    )
    usage = {
        'input': response.usage_metadata.prompt_token_count or 0,
        'output': response.usage_metadata.candidates_token_count or 0,
    }
    text = strip_json_fences(response.text or '')
    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError('Gemini response JSON is not an object')
        return normalize_result(data, usage)
    except Exception as exc:
        return {
            'page_type': 'other',
            'shared_contexts': [],
            'questions': [],
            'answers': [],
            'visual_refs': [],
            'raw_markdown': text,
            'usage': usage,
            'parse_error': str(exc),
        }


def exam_pdf_map(level: str) -> dict[str, str]:
    if level == 'all':
        result: dict[str, str] = {}
        for level_name, pdfs in EXAM_PDFS_BY_LEVEL.items():
            for key, pdf in pdfs.items():
                result[f'{level_name}/{key}'] = pdf
        return result
    return EXAM_PDFS_BY_LEVEL.get(level, {})


def process_exam_pdf(
    level: str,
    key: str,
    pdf_name: str,
    force: bool = False,
    dry_run: bool = False,
    single_page: int | None = None,
) -> None:
    pdf_path = BASE / 'data' / level / 'pdfs' / pdf_name
    if not pdf_path.exists():
        print(f'ERROR: PDF not found: {pdf_path}')
        return

    cache_dir = BASE / 'data' / level / 'exam_pages_cache' / key
    cache_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)
    page_indices = [single_page] if single_page is not None else list(range(total_pages))
    to_process: list[int] = []
    for idx in page_indices:
        if idx < 0 or idx >= total_pages:
            print(f'  WARN: page index out of range: {idx}')
            continue
        cache_path = cache_dir / f'page_{idx:03d}.json'
        if force or not cache_path.exists():
            to_process.append(idx)
            continue
        try:
            cached = json.loads(cache_path.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            to_process.append(idx)
            continue
        if cached.get('page_type') == 'error':
            to_process.append(idx)

    print(f'{level}/{key}: {total_pages} pages -> {cache_dir}')
    print(f'  {len(page_indices) - len(to_process)} already cached, {len(to_process)} to process')

    if dry_run:
        est_input = len(to_process) * 1800
        est_output = len(to_process) * 900
        est_cost = (est_input * INPUT_PRICE_PER_M + est_output * OUTPUT_PRICE_PER_M) / 1_000_000
        print(f'  [dry-run] estimated cost: ${est_cost:.3f} USD for {len(to_process)} pages')
        doc.close()
        return

    if not to_process:
        doc.close()
        write_summary(cache_dir, total_pages)
        return

    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        doc.close()
        sys.exit('GEMINI_API_KEY is required unless --dry-run is used')

    client = genai.Client(api_key=api_key)
    for order, idx in enumerate(to_process, start=1):
        cache_path = cache_dir / f'page_{idx:03d}.json'
        print(f'  [{order}/{len(to_process)}] page {idx:03d} ...', end=' ', flush=True)
        try:
            result = call_exam_vision_api(client, page_to_png_bytes(doc[idx]))
            result['idx'] = idx
            cache_path.write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + '\n',
                encoding='utf-8',
            )
            usage = result.get('usage', {})
            print(
                f"{result.get('page_type')} "
                f"q={len(result.get('questions', []))} "
                f"a={len(result.get('answers', []))} "
                f"v={len(result.get('visual_refs', []))} "
                f"({usage.get('input', 0)}in/{usage.get('output', 0)}out)"
            )
        except Exception as exc:
            print(f'ERROR: {exc}')
            cache_path.write_text(
                json.dumps({'idx': idx, 'page_type': 'error', 'error': str(exc)}, ensure_ascii=False) + '\n',
                encoding='utf-8',
            )
        if order < len(to_process):
            time.sleep(0.5)

    doc.close()
    write_summary(cache_dir, total_pages)


def write_summary(cache_dir: Path, total_pages: int) -> None:
    counts: dict[str, int] = {'total': total_pages, 'missing': 0}
    total_input = 0
    total_output = 0
    total_questions = 0
    total_answers = 0
    total_visual_refs = 0

    for idx in range(total_pages):
        path = cache_dir / f'page_{idx:03d}.json'
        if not path.exists():
            counts['missing'] += 1
            continue
        data = json.loads(path.read_text(encoding='utf-8'))
        page_type = data.get('page_type', 'other')
        counts[page_type] = counts.get(page_type, 0) + 1
        usage = data.get('usage') or {}
        total_input += int(usage.get('input') or 0)
        total_output += int(usage.get('output') or 0)
        total_questions += len(data.get('questions') or [])
        total_answers += len(data.get('answers') or [])
        total_visual_refs += len(data.get('visual_refs') or [])
        for context in data.get('shared_contexts') or []:
            total_visual_refs += len(context.get('visual_refs') or [])
        for question in data.get('questions') or []:
            total_visual_refs += len(question.get('visual_refs') or [])

    cost = (total_input * INPUT_PRICE_PER_M + total_output * OUTPUT_PRICE_PER_M) / 1_000_000
    summary = {
        **counts,
        'questions': total_questions,
        'answers': total_answers,
        'visual_refs': total_visual_refs,
        'total_input_tokens': total_input,
        'total_output_tokens': total_output,
        'cost_usd': round(cost, 4),
    }
    (cache_dir / 'summary.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )
    print(f'  Summary: {summary}')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--level', choices=['初級', '中級'], default='初級')
    parser.add_argument('--key', help='PDF key, e.g. exam1, exam2, exam3, sample')
    parser.add_argument('--all', action='store_true', help='Process all official exam PDFs for the level')
    parser.add_argument('--page', type=int, help='Process one zero-based PDF page index')
    parser.add_argument('--force', action='store_true', help='Reprocess cached pages')
    parser.add_argument('--dry-run', action='store_true', help='Estimate cost without calling Gemini')
    args = parser.parse_args()

    pdfs = exam_pdf_map(args.level)
    if not pdfs:
        sys.exit(f'No exam PDFs configured for level "{args.level}"')

    if not args.all and not args.key:
        parser.error('Specify --key KEY or --all')
    if args.key and args.key not in pdfs:
        parser.error(f'Unknown key "{args.key}" for level "{args.level}". Available: {", ".join(sorted(pdfs))}')

    keys = sorted(pdfs) if args.all else [args.key]
    for key in keys:
        process_exam_pdf(
            args.level,
            key,
            pdfs[key],
            force=args.force,
            dry_run=args.dry_run,
            single_page=args.page,
        )


if __name__ == '__main__':
    main()
