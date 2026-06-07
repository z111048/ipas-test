#!/usr/bin/env python3
"""Audit PDF pages via Gemini Vision for content quality review.

Purpose: extract structured content to AUDIT and ENRICH existing guide content
— NOT to replace it. Output per page includes:
  - Heading hierarchy with bounding boxes
  - Tables converted to HTML
  - Mathematical formulas in LaTeX
  - Images/figures described with bounding boxes

Results are cached in data/{level}/audit_cache/{key}/page_{idx:03d}.json,
separate from the production pages_cache/ to avoid contamination.

Usage:
  uv run python3 scripts/pdf_vision_audit.py --level 初級 --subject 2 --dry-run
  uv run python3 scripts/pdf_vision_audit.py --level 初級 --subject 2
  uv run python3 scripts/pdf_vision_audit.py --level 初級 --subject 2 --force
  uv run python3 scripts/pdf_vision_audit.py --level 初級 --subject 2 --page 6

Requires: GEMINI_API_KEY environment variable.
Model:    GOOGLE_MODEL env var (default: gemini-3-flash-preview).
Budget:   --max-cost flag (default: 5.0 USD).
Flex:     thinking disabled by default (cheaper); use --no-flex to enable thinking.
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit('PyMuPDF not found. Run: uv sync')

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    sys.exit('google-genai not found. Run: uv add google-genai')

BASE = Path('/home/james/projects/ipas-test')

DEFAULT_MODEL = 'gemini-3-flash-preview'
# Conservative upper-bound pricing (USD per 1M tokens).
# Update once gemini-3-flash-preview pricing is confirmed.
INPUT_PRICE_PER_M  = 0.15   # non-thinking / flex mode
OUTPUT_PRICE_PER_M = 0.60
DEFAULT_MAX_COST   = 5.0    # USD hard budget cap

# ── Prompts ───────────────────────────────────────────────────────────────────

def _build_prompt(with_bbox: bool) -> str:
    bbox_rule = (
        '\n每個 block 必須包含 "bbox"：[x0, y0, x1, y1]，'
        '座標為 0–1000 正規化值（頁面寬/高各為 1000），整數，y 軸向下遞增。'
        if with_bbox else ''
    )
    bf = ',"bbox":[x0,y0,x1,y1]' if with_bbox else ''   # bbox field in examples
    bq = '\n- bbox 需準確反映內容在頁面上的實際位置（0–1000 正規化）' if with_bbox else ''

    return (
        '你正在審核一頁來自台灣「iPAS AI 應用規劃師（初級）學習指引—科目二：生成式AI應用與規劃」的 PDF 頁面。\n'
        '\n'
        '目的：提取結構化內容，供教材品質審核與補強，**不是用來取代現有教材**。\n'
        '\n'
        '請只輸出以下 JSON（不加其他文字、markdown fence 或任何說明）：\n'
        '{\n'
        '  "type": "content" | "practice" | "skip",\n'
        '  "blocks": [ ... ]\n'
        '}\n'
        '\n'
        '━━━ type 判斷 ━━━\n'
        '- "practice"：選擇題題目頁或解析答案頁（含「Ans」「解析」等字樣）\n'
        '- "skip"：目錄、序言、版權頁、空白頁、參考書目\n'
        '- "content"：教材正文（type 非 content 時，blocks 填空陣列 []）\n'
        '\n'
        '━━━ blocks 陣列規則 ━━━\n'
        f'依頁面由上至下順序列出所有內容區塊。{bbox_rule}\n'
        '\n'
        '■ heading（章節標題）\n'
        f'{{"type":"heading","level":2|3|4,"text":"完整標題文字"{bf}}}\n'
        '  判斷原則：heading 必須在視覺上比正文字體**明顯更大**；單純粗體但字體大小與正文相同者不算 heading。\n'
        '  level 2 → 字體最大的大節標題（如「1. No Code 概念」「3.2 生成式AI應用」「第三章 生成式AI」）\n'
        '  level 3 → 字體中等、明顯大於正文的子節標題（如「（1）定義與特性」「一、背景」）\n'
        '  level 4 → 字體略大於正文、仍視覺可辨為標題的更深子節\n'
        '  ⚠️ 以字母 A./B./C./a./b./c. 開頭的項目：\n'
        '     - 若字體明顯大於正文 → 可為 heading（level 依大小決定）\n'
        '     - 若字體大小與正文相同（即使粗體）→ 改為 list（items 中去除前綴字母）\n'
        '\n'
        '■ paragraph（段落文字）\n'
        f'{{"type":"paragraph","text":"完整段落，保留所有中英文術語與縮寫"{bf}}}\n'
        '\n'
        '■ list（條列清單）\n'
        f'{{"type":"list","ordered":true|false,"items":["項目1","項目2"]{bf}}}\n'
        '  ordered: true 為數字編號，false 為符號清單\n'
        '  items 中的文字不含前綴符號（-, •, 1.）\n'
        '\n'
        '■ table（表格） → 必須轉成 HTML\n'
        f'{{"type":"table","html":"<table><tr><th>欄位</th></tr><tr><td>內容</td></tr></table>","caption":"表格說明（若無則省略此欄）"{bf}}}\n'
        '  表頭用 <th>，資料格用 <td>，合併格加 colspan/rowspan 屬性\n'
        '  不得省略任何儲存格內容，換行用 <br>\n'
        '\n'
        '■ formula（數學 / 統計公式） → 必須轉成 LaTeX\n'
        f'{{"type":"formula","latex":"LaTeX 公式內容","display":true|false{bf}}}\n'
        '  display: true = 獨立行公式，false = 行內公式\n'
        '  latex 欄位只填公式本身，不含 $ 或 $$ 符號\n'
        '\n'
        '■ image（圖表、示意圖、流程圖、截圖）\n'
        f'{{"type":"image","description":"描述圖片主題、重要元素、數字與文字標籤（100字以內）"{bf}}}\n'
        '  圖中如有文字標籤或數值，必須在 description 中提及\n'
        '\n'
        '━━━ 品質要求 ━━━\n'
        '- 完整保留所有技術術語及中英對照（如 No Code、Prompt Engineering）\n'
        '- 不合併相鄰段落；段落不截斷\n'
        f'- 頁碼數字、頁首章節名稱、頁尾資訊不列入 blocks{bq}'
    )


# Pre-built prompt constants
AUDIT_PROMPT      = _build_prompt(with_bbox=False)   # default — no bbox
AUDIT_PROMPT_BBOX = _build_prompt(with_bbox=True)    # targeted spatial analysis


# ── Manifest ──────────────────────────────────────────────────────────────────

def _load_manifest(level: str) -> dict[int, dict]:
    manifest_path = BASE / 'data' / level / 'toc_manifest.json'
    with open(manifest_path, encoding='utf-8') as f:
        manifest = json.load(f)
    result = {}
    for i, subj in enumerate(manifest['subjects'], 1):
        result[i] = {
            'key': subj['key'],
            'pdf': subj['pdf'],
            'subject': subj['subject'],
        }
    return result


# ── Image rendering ───────────────────────────────────────────────────────────

def page_to_png_bytes(page: fitz.Page, scale: float = 2.0) -> bytes:
    mat = fitz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat)
    return pix.tobytes('png')


# ── Validation ────────────────────────────────────────────────────────────────

ALLOWED_TYPES       = {'content', 'practice', 'skip'}
ALLOWED_BLOCK_TYPES = {'heading', 'paragraph', 'list', 'table', 'formula', 'image'}
REQUIRED_FIELDS: dict[str, list[str]] = {
    'heading':   ['level', 'text'],
    'paragraph': ['text'],
    'list':      ['ordered', 'items'],
    'table':     ['html'],
    'formula':   ['latex', 'display'],
    'image':     ['description'],
}
# Additional required fields when bbox mode is active
REQUIRED_FIELDS_BBOX: dict[str, list[str]] = {
    k: v + ['bbox'] for k, v in REQUIRED_FIELDS.items()
}


def _check_bbox(bbox) -> str | None:
    # Accept any absolute coordinates (model returns PDF point units, not percentages)
    if not isinstance(bbox, list) or len(bbox) != 4:
        return 'bbox must be [x0, y0, x1, y1] (4 numbers)'
    for v in bbox:
        if not isinstance(v, (int, float)):
            return f'bbox value {v!r} is not a number'
        if v < 0:
            return f'bbox value {v} is negative'
    if bbox[0] >= bbox[2] or bbox[1] >= bbox[3]:
        return f'bbox not in order (x0>=x1 or y0>=y1): {bbox}'
    return None


def _check_html_table(html: str) -> str | None:
    h = html.lower()
    if '<table' not in h:
        return 'missing <table> tag'
    if '<tr' not in h:
        return 'missing <tr> tag'
    if '<td' not in h and '<th' not in h:
        return 'missing <td> or <th> tag'
    return None


def _check_latex(latex: str) -> str | None:
    if not latex.strip():
        return 'latex is empty'
    depth = 0
    for ch in latex:
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
        if depth < 0:
            return 'unmatched closing brace }'
    if depth != 0:
        return f'{depth} unclosed brace(s) {{'
    return None


def validate(data: dict, with_bbox: bool = False) -> list[str]:
    """Return list of error strings; empty list means valid."""
    errors: list[str] = []

    page_type = data.get('type')
    if page_type not in ALLOWED_TYPES:
        errors.append(f'invalid page type {page_type!r}')
        return errors

    blocks = data.get('blocks')
    if not isinstance(blocks, list):
        errors.append('"blocks" must be an array')
        return errors

    if page_type != 'content':
        if blocks:
            errors.append(f'type={page_type!r} but blocks is non-empty ({len(blocks)} items)')
        return errors

    if len(blocks) == 0:
        errors.append('content page has empty blocks []')

    required = REQUIRED_FIELDS_BBOX if with_bbox else REQUIRED_FIELDS

    for i, block in enumerate(blocks):
        pfx = f'block[{i}]'
        btype = block.get('type')

        if btype not in ALLOWED_BLOCK_TYPES:
            errors.append(f'{pfx}: unknown type {btype!r}')
            continue

        for field in required.get(btype, []):
            if field not in block:
                errors.append(f'{pfx} ({btype}): missing field "{field}"')

        if with_bbox and 'bbox' in block:
            err = _check_bbox(block.get('bbox'))
            if err:
                errors.append(f'{pfx} ({btype}) bbox: {err}')

        if btype == 'heading':
            if block.get('level') not in (2, 3, 4):
                errors.append(f'{pfx}: level {block.get("level")!r} must be 2, 3, or 4')
            if not str(block.get('text', '')).strip():
                errors.append(f'{pfx}: text is empty')

        elif btype == 'table':
            err = _check_html_table(block.get('html', ''))
            if err:
                errors.append(f'{pfx} table html: {err}')

        elif btype == 'formula':
            err = _check_latex(block.get('latex', ''))
            if err:
                errors.append(f'{pfx} formula latex: {err}')
            if not isinstance(block.get('display'), bool):
                errors.append(f'{pfx}: "display" must be boolean')

        elif btype == 'list':
            if not isinstance(block.get('ordered'), bool):
                errors.append(f'{pfx}: "ordered" must be boolean')
            items = block.get('items')
            if not isinstance(items, list) or len(items) == 0:
                errors.append(f'{pfx}: "items" must be non-empty array')

    return errors


# ── API call ──────────────────────────────────────────────────────────────────

def call_api(
    client: genai.Client,
    img_bytes: bytes,
    model: str,
    use_flex: bool,
    with_bbox: bool = False,
) -> tuple[dict, dict]:
    """Returns (parsed_data, usage_dict). Raises ValueError on JSON parse failure."""
    config_kwargs: dict = {}
    if use_flex:
        try:
            config_kwargs['thinking_config'] = genai_types.ThinkingConfig(thinking_budget=0)
        except AttributeError:
            pass  # Older SDK — no ThinkingConfig; proceed without it

    prompt = AUDIT_PROMPT_BBOX if with_bbox else AUDIT_PROMPT
    call_kw: dict = dict(
        model=model,
        contents=[
            genai_types.Part.from_bytes(data=img_bytes, mime_type='image/png'),
            genai_types.Part.from_text(text=prompt),
        ],
    )
    if config_kwargs:
        call_kw['config'] = genai_types.GenerateContentConfig(**config_kwargs)

    response = client.models.generate_content(**call_kw)
    text = response.text.strip()
    meta = response.usage_metadata
    usage = {
        'input':    meta.prompt_token_count or 0,
        'output':   meta.candidates_token_count or 0,
        'thinking': getattr(meta, 'thoughts_token_count', 0) or 0,
    }

    # Strip markdown code fences if model wrapped the JSON
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f'JSON parse failed: {exc}\n--- raw (first 600 chars) ---\n{text[:600]}'
        ) from exc

    return data, usage


# ── Per-guide processing ──────────────────────────────────────────────────────

def process_guide(
    subject_num: int,
    cfg: dict,
    pdf_dir: Path,
    audit_dir: Path,
    model: str,
    use_flex: bool,
    max_cost: float,
    cumulative_cost: list[float],
    input_price: float,
    output_price: float,
    force: bool = False,
    dry_run: bool = False,
    single_page: int | None = None,
    with_bbox: bool = False,
) -> None:
    key = cfg['key']
    pdf_path = pdf_dir / cfg['pdf']
    key_dir = audit_dir / key
    key_dir.mkdir(parents=True, exist_ok=True)

    if not pdf_path.exists():
        print(f'  ERROR: PDF not found: {pdf_path}')
        return

    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)
    print(f'\n[{key}] {cfg["subject"]}')
    print(f'  PDF: {pdf_path.name}  ({total_pages} pages)')
    print(f'  Cache: {key_dir}')

    page_indices = [single_page] if single_page is not None else list(range(total_pages))

    to_process: list[int] = []
    for idx in page_indices:
        path = key_dir / f'page_{idx:03d}.json'
        if force or not path.exists():
            to_process.append(idx)
        else:
            cached = json.loads(path.read_text())
            # Reprocess errored pages or pages that failed validation
            if cached.get('type') == 'error' or not cached.get('validated'):
                to_process.append(idx)

    cached_ok = len(page_indices) - len(to_process)
    print(f'  Cached (valid): {cached_ok}  To process: {len(to_process)}')

    if dry_run:
        est_input  = len(to_process) * 2500
        est_output = len(to_process) * 900
        est_cost   = (est_input * input_price + est_output * output_price) / 1_000_000
        print(f'  [dry-run] est. cost: ${est_cost:.4f} USD')
        print(f'  [dry-run] budget remaining: ${max_cost - cumulative_cost[0]:.4f} USD')
        doc.close()
        return

    if not to_process:
        print('  Nothing to process.')
        doc.close()
        _write_summary(key_dir, total_pages)
        return

    client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])
    ok = failed = warn = 0
    total_in = total_out = total_think = 0

    for i, idx in enumerate(to_process):
        remaining_budget = max_cost - cumulative_cost[0]
        est_page = (2500 * input_price + 900 * output_price) / 1_000_000
        if remaining_budget < est_page:
            print(f'\n  [BUDGET STOP] remaining ${remaining_budget:.4f} < est. page ${est_page:.4f}')
            break

        path = key_dir / f'page_{idx:03d}.json'
        print(f'  [{i+1}/{len(to_process)}] page {idx:03d} ...', end=' ', flush=True)

        try:
            page_obj = doc[idx]
            img_bytes = page_to_png_bytes(page_obj)
            page_w = round(page_obj.rect.width, 1)
            page_h = round(page_obj.rect.height, 1)
            data, usage = call_api(client, img_bytes, model, use_flex, with_bbox)

            errors    = validate(data, with_bbox=with_bbox)
            validated = len(errors) == 0

            entry = {
                'idx':               idx,
                'with_bbox':         with_bbox,
                'page_width_pt':     page_w,   # PDF point units for bbox normalisation
                'page_height_pt':    page_h,
                'type':              data.get('type', 'error'),
                'blocks':            data.get('blocks', []),
                'usage':             usage,
                'validated':         validated,
                'validation_errors': errors,
            }
            path.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding='utf-8')

            in_tok  = usage['input']
            out_tok = usage['output']
            thi_tok = usage['thinking']
            page_cost = (in_tok * input_price + out_tok * output_price) / 1_000_000

            total_in    += in_tok
            total_out   += out_tok
            total_think += thi_tok
            cumulative_cost[0] += page_cost
            ok += 1

            think_str = f' think={thi_tok}' if thi_tok else ''
            warn_str  = f'  ⚠ {len(errors)} error(s)' if errors else ''
            print(
                f"{entry['type']:8s}  "
                f"blocks={len(entry['blocks']):2d}  "
                f"{in_tok}in/{out_tok}out{think_str}  "
                f"${page_cost:.4f}"
                f"{warn_str}"
            )
            if errors:
                warn += 1
                for e in errors[:3]:
                    print(f'      ↳ {e}')

        except Exception as exc:
            print(f'ERROR: {exc}')
            path.write_text(
                json.dumps({
                    'idx': idx, 'type': 'error', 'blocks': [],
                    'usage': {}, 'validated': False,
                    'validation_errors': [str(exc)],
                }, ensure_ascii=False),
                encoding='utf-8',
            )
            failed += 1

        if i < len(to_process) - 1:
            time.sleep(0.5)

    doc.close()
    run_cost = (total_in * input_price + total_out * output_price) / 1_000_000
    print(
        f'\n  ok={ok} failed={failed} validation_warn={warn}  '
        f'tokens={total_in}in/{total_out}out/{total_think}think  '
        f'cost=${run_cost:.4f}  cumulative=${cumulative_cost[0]:.4f}/${max_cost}'
    )
    _write_summary(key_dir, total_pages)


def _write_summary(key_dir: Path, total_pages: int) -> None:
    counts: dict = {
        'total': total_pages, 'content': 0, 'practice': 0, 'skip': 0,
        'error': 0, 'missing': 0, 'validated_ok': 0, 'validated_warn': 0,
    }
    ti = to = tt = 0
    for idx in range(total_pages):
        p = key_dir / f'page_{idx:03d}.json'
        if not p.exists():
            counts['missing'] += 1
            continue
        d = json.loads(p.read_text())
        ptype = d.get('type', 'error')
        counts[ptype] = counts.get(ptype, 0) + 1
        u = d.get('usage', {})
        ti += u.get('input', 0)
        to += u.get('output', 0)
        tt += u.get('thinking', 0)
        if d.get('validated'):
            counts['validated_ok'] += 1
        elif ptype not in ('missing',):
            counts['validated_warn'] += 1

    summary = {**counts,
               'total_input_tokens': ti,
               'total_output_tokens': to,
               'total_thinking_tokens': tt}
    (key_dir / 'summary.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'  Summary: {summary}')


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--level',    default='初級')
    parser.add_argument('--subject',  type=int, help='科目編號（1-based）')
    parser.add_argument('--all',      action='store_true', help='處理此等級所有科目')
    parser.add_argument('--force',    action='store_true', help='強制重處理已快取頁面')
    parser.add_argument('--dry-run',  action='store_true', help='估算費用，不呼叫 API')
    parser.add_argument('--page',     type=int,  help='只處理指定頁面索引（0-based）')
    parser.add_argument('--max-cost', type=float, default=DEFAULT_MAX_COST,
                        help=f'預算上限 USD（預設 {DEFAULT_MAX_COST}）')
    parser.add_argument('--no-flex',   action='store_true',
                        help='停用 flex 模式（允許 thinking，費用較高）')
    parser.add_argument('--with-bbox', action='store_true',
                        help='啟用 bbox 模式（針對特定頁面的空間位置解析）')
    parser.add_argument('--input-price',  type=float, default=INPUT_PRICE_PER_M,
                        help='輸入 token 費率 USD/1M（預設保守估算值）')
    parser.add_argument('--output-price', type=float, default=OUTPUT_PRICE_PER_M,
                        help='輸出 token 費率 USD/1M（預設保守估算值）')
    args = parser.parse_args()

    if not args.subject and not args.all:
        parser.error('請指定 --subject N 或 --all')
    if not args.dry_run and not os.environ.get('GEMINI_API_KEY'):
        sys.exit('ERROR: GEMINI_API_KEY environment variable not set')

    model    = os.environ.get('GOOGLE_MODEL', DEFAULT_MODEL)
    use_flex = not args.no_flex

    data_dir  = BASE / 'data' / args.level
    pdf_dir   = data_dir / 'pdfs'
    audit_dir = data_dir / 'audit_cache'

    guides = _load_manifest(args.level)
    if not guides:
        sys.exit(f'No subjects found for level "{args.level}". Run build_manifest.py first.')

    subjects = sorted(guides.keys()) if args.all else [args.subject]
    cumulative_cost: list[float] = [0.0]

    print(f'=== pdf_vision_audit ===')
    with_bbox = args.with_bbox
    print(f'Model: {model}  Flex(no-thinking): {use_flex}  BBox: {with_bbox}  Budget: ${args.max_cost}')

    for s in subjects:
        if s not in guides:
            print(f'[WARN] Subject {s} not found for level "{args.level}"')
            continue
        process_guide(
            s, guides[s], pdf_dir, audit_dir,
            model, use_flex, args.max_cost, cumulative_cost,
            args.input_price, args.output_price,
            force=args.force, dry_run=args.dry_run, single_page=args.page,
            with_bbox=with_bbox,
        )
        if cumulative_cost[0] >= args.max_cost:
            print(f'\n[BUDGET EXHAUSTED] ${cumulative_cost[0]:.4f} >= ${args.max_cost}. Stopping.')
            break

    print(f'\n=== Total cost: ${cumulative_cost[0]:.4f} ===')


if __name__ == '__main__':
    main()
