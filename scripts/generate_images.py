#!/usr/bin/env python3
"""Generate Codex image assets and convert them to WebP for the frontend."""

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE / 'frontend' / 'public' / 'images'
PROMPT_CACHE = BASE / 'build' / 'image_prompts.json'
GENERATION_LOG = BASE / 'build' / 'image_generation_log.jsonl'
DEFAULT_UNITS_FILE = BASE / 'data' / '初級' / 'image_units' / 'all_image_units.json'
OUTPUT_SIZE = (1792, 1024)
DEFAULT_STYLE = (
    'clean flat-vector editorial infographic illustration for the iPAS AI study platform; '
    'off-white background, deep navy and slate foundation, blue accent, restrained amber '
    'and green highlights, soft shadows, 8px-radius visual panels'
)
DEFAULT_LAYOUT = (
    'fixed 16:9 widescreen composition with one central concept object, three to five '
    'surrounding icon-based panels, thin connector lines, generous margins, consistent '
    'safe area, no cropping'
)
TEXT_RULES = (
    'the image must contain visible, correctly written Traditional Chinese text: one short '
    'main title plus three to five concise Traditional Chinese labels; each label must be '
    'eight Chinese characters or fewer; use large legible sans-serif typography; place each '
    'label inside a dedicated panel with strong contrast and generous padding'
)


def build_prompt(visual: str, style: str = DEFAULT_STYLE, layout: str = DEFAULT_LAYOUT) -> str:
    return (
        'Generate a 1792x1024 wide landscape image (16:9).\n'
        f'Style: {style}.\n'
        f'Layout: {layout}.\n'
        f'Topic reference, summarize this into the title and labels without copying long text verbatim: {visual}.\n'
        f'Text: {TEXT_RULES}.\n'
        'Rules: high quality, coherent composition, readable Chinese text is required, '
        'no text-free infographic, no long paragraphs, no tiny text, no random letters, '
        'no fake UI, no logos, no watermarks, no UI screenshots'
    )


def build_compact_prompt(title: str, context: str = '') -> str:
    topic = title if not context else f'{title}: {context}'
    return build_prompt(topic[:260])


IMAGES = [
    {
        'name': 'ai-study-roadmap',
        'output': 'ai-study-roadmap.webp',
        'visual': (
            'an abstract learning roadmap for iPAS AI exam preparation, with connected '
            'milestones representing AI fundamentals, data governance, model evaluation, '
            'and exam practice, arranged as clear labeled visual zones'
        ),
        'prompt': build_prompt(
            'an abstract learning roadmap for iPAS AI exam preparation, with connected '
            'milestones representing AI fundamentals, data governance, model evaluation, '
            'and exam practice, arranged as clear labeled visual zones'
        ),
    },
    {
        'name': 'ai-governance-lifecycle',
        'output': 'ai-governance-lifecycle.webp',
        'visual': (
            'a circular AI governance lifecycle scene showing data collection, model training, '
            'risk review, human oversight, deployment monitoring, and continuous improvement '
            'as labeled symbolic panels around a central AI system'
        ),
        'prompt': build_prompt(
            'a circular AI governance lifecycle scene showing data collection, model training, '
            'risk review, human oversight, deployment monitoring, and continuous improvement '
            'as labeled symbolic panels around a central AI system'
        ),
    },
]


def load_prompt_cache() -> dict[str, dict[str, str]]:
    if not PROMPT_CACHE.exists():
        return {}
    with PROMPT_CACHE.open(encoding='utf-8') as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f'{PROMPT_CACHE} must contain a JSON object')
    return data


def write_prompt_cache(cache: dict[str, dict[str, str]]) -> None:
    PROMPT_CACHE.parent.mkdir(parents=True, exist_ok=True)
    PROMPT_CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding='utf-8')


def append_generation_log(entry: dict) -> None:
    GENERATION_LOG.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        **entry,
    }
    with GENERATION_LOG.open('a', encoding='utf-8') as f:
        f.write(json.dumps(payload, ensure_ascii=False) + '\n')


def image_prompt(image: dict[str, str], cache: dict[str, dict[str, str]]) -> str:
    return image['prompt']


def update_prompt_cache(image: dict[str, str], prompt: str, cache: dict[str, dict[str, str]]) -> bool:
    entry = {
        'visual': image.get('visual', ''),
        'image_prompt': prompt,
    }
    if cache.get(image['name']) == entry:
        return False
    cache[image['name']] = entry
    return True


def last_lines(output: str, count: int = 12) -> str:
    lines = output.strip().splitlines()
    return '\n'.join(lines[-count:])


def run_codex_image(prompt: str, timeout: int = 620) -> tuple[str, str]:
    """保留舊介面（回傳「產物路徑」）以免呼叫端全改；實際走 codex-imggen 服務。"""
    from imggen_client import generate as imggen_generate

    data = imggen_generate(prompt, size=f'{OUTPUT_SIZE[0]}x{OUTPUT_SIZE[1]}',
                           fmt='png', timeout=timeout)
    scratch = BASE / 'build' / 'imggen_raw'
    scratch.mkdir(parents=True, exist_ok=True)
    raw = scratch / f'{abs(hash(prompt)) % 10**12}.png'
    raw.write_bytes(data)
    return raw.as_posix(), ''


def copy_to_output(raw_png: str, out_path: Path, quality: int = 92) -> Path:
    """把服務回傳的 PNG 正規化成前端要的 WebP 尺寸。

    2026-08-08 改走 codex-imggen（`imggen_client.py`）。原本是直接 `codex exec` 再去
    scrape `~/.codex/generated_images/<session>/`，**檔名慣例隨 codex-cli 版本變**
    （0.146 起 `ig_*.png` → `exec-<uuid>.png`），圖產出來了腳本卻報「找不到 PNG」。
    服務直接回傳 bytes，沒有目錄與檔名可壞，session 垃圾也留在容器裡。
    """
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise RuntimeError('找不到 Pillow，無法轉 WebP。請執行：uv sync 或 uv add pillow') from exc

    source = Path(raw_png)
    if not source.exists():
        raise FileNotFoundError(f'找不到產圖 PNG：{source}')
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as img:
        normalized = ImageOps.fit(img.convert('RGB'), OUTPUT_SIZE, method=Image.Resampling.LANCZOS)
        normalized.save(out_path, 'WEBP', quality=quality)
    return source


def selected_images(name: str | None) -> list[dict[str, str]]:
    if name is None:
        return IMAGES
    matches = [image for image in IMAGES if image['name'] == name]
    if not matches:
        available = ', '.join(image['name'] for image in IMAGES)
        raise ValueError(f'找不到圖片定義：{name}。可用名稱：{available}')
    return matches


def image_from_unit(unit: dict) -> dict[str, str]:
    output = unit.get('output')
    prompt = unit.get('imagePrompt')
    if not output or not prompt:
        raise ValueError(f'Invalid image unit, missing output/imagePrompt: {unit.get("id")}')
    heading_path = unit.get('headingPath') or []
    compact_title = ' > '.join(str(part) for part in heading_path[-2:]) or unit.get('title') or unit.get('id') or ''
    return {
        'name': unit.get('id') or Path(output).stem,
        'output': output,
        'visual': unit.get('visualBrief') or '',
        'prompt': prompt,
        'fallback_prompt': build_compact_prompt(compact_title, unit.get('sourceNodeTitle') or ''),
    }


def selected_unit_images(units_file: Path, name: str | None, offset: int, limit: int | None) -> list[dict[str, str]]:
    with units_file.open(encoding='utf-8') as f:
        payload = json.load(f)
    units = payload.get('units')
    if not isinstance(units, list):
        raise ValueError(f'{units_file} must contain a units[] list')

    if name:
        units = [unit for unit in units if unit.get('id') == name or unit.get('output') == name]
        if not units:
            raise ValueError(f'找不到圖片單元：{name}')
    else:
        units = units[offset:]
        if limit is not None:
            units = units[:limit]
    return [image_from_unit(unit) for unit in units]


def verify_text(image: dict[str, str], out_path: Path, timeout: int) -> dict:
    """產圖後檢查圖上的中文文字。

    2026-08-08 加上：原本的重試只處理技術失敗（timeout、抓不到 session id），
    **從不因文字品質重試**——抽 30 張發現約三分之一的標題字形變形、4 張有真缺陷
    （非中文詞、截斷、術語與考綱不符），卻全部照樣進站。偵測不到就等於沒有偵測。
    ⚠️ `error`（codex 沒回應）**不算 pass**，否則又回到「檢查不出來就放過」。
    """
    from verify_generated_images import check_one

    context = {
        'level': image.get('level', ''),
        'sourceNodeId': image.get('sourceNodeId', ''),
        'headingPath': image.get('headingPath') or [],
        'title': image.get('name', ''),
    }
    return check_one(out_path, context, timeout=timeout)


def generate_one(image: dict[str, str], prompt: str, out_path: Path, max_retries: int,
                 timeout: int, verify: bool = True) -> bool:
    from verify_generated_images import problems_as_instructions

    feedback = ''
    for attempt in range(1, max_retries + 2):
        try:
            raw_png, _ = run_codex_image(prompt + feedback, timeout=timeout)
            source_png = copy_to_output(raw_png, out_path)
            if verify:
                result = verify_text(image, out_path, timeout)
                if result['verdict'] != 'pass':
                    kinds = ','.join(sorted({p['kind'] for p in result['problems']})) \
                        or result['verdict']
                    append_generation_log({
                        'name': image['name'],
                        'output': image['output'],
                        'status': 'text_check_failed',
                        'attempt': attempt,
                        'verdict': result['verdict'],
                        'problems': result['problems'],
                    })
                    print(f'TEXT {image["name"]} attempt {attempt}: 文字檢查不過（{kinds}）')
                    feedback = problems_as_instructions(result['problems'])
                    continue
            append_generation_log({
                'name': image['name'],
                'output': image['output'],
                'status': 'ok',
                'prompt_kind': 'primary',
                'attempt': attempt,
                'source_png': str(raw_png),
                'source_png': str(source_png),
                'out_path': str(out_path),
                'prompt': prompt,
            })
            print(f'OK {image["name"]}: {source_png} -> {out_path}')
            return True
        except subprocess.TimeoutExpired:
            error = f'Codex timeout after {timeout}s'
        except Exception as exc:
            error = str(exc)
        append_generation_log({
            'name': image['name'],
            'output': image['output'],
            'status': 'failed_attempt',
            'prompt_kind': 'primary',
            'attempt': attempt,
            'error': last_lines(error, 1),
            'prompt': prompt,
        })
        print(f'FAIL {image["name"]} attempt {attempt}/{max_retries + 1}: {last_lines(error, 1)}')

    fallback_prompt = image.get('fallback_prompt')
    if fallback_prompt and fallback_prompt != prompt:
        print(f'FALLBACK {image["name"]}: retrying with compact prompt')
        for attempt in range(1, 4):
            try:
                raw_png, _ = run_codex_image(fallback_prompt, timeout=timeout)
                source_png = copy_to_output(raw_png, out_path)
                append_generation_log({
                    'name': image['name'],
                    'output': image['output'],
                    'status': 'ok',
                    'prompt_kind': 'fallback',
                    'attempt': attempt,
                    'source_png': str(raw_png),
                    'source_png': str(source_png),
                    'out_path': str(out_path),
                    'prompt': fallback_prompt,
                })
                print(f'OK {image["name"]}: {source_png} -> {out_path}')
                return True
            except subprocess.TimeoutExpired:
                error = f'Codex timeout after {timeout}s'
            except Exception as exc:
                error = str(exc)
            append_generation_log({
                'name': image['name'],
                'output': image['output'],
                'status': 'failed_attempt',
                'prompt_kind': 'fallback',
                'attempt': attempt,
                'error': last_lines(error, 1),
                'prompt': fallback_prompt,
            })
            print(f'FAIL {image["name"]} fallback attempt {attempt}/3: {last_lines(error, 1)}')
    append_generation_log({
        'name': image['name'],
        'output': image['output'],
        'status': 'failed',
        'prompt_kind': 'all',
    })
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', help='只印出 prompt，不呼叫 Codex CLI')
    parser.add_argument('--no-verify', action='store_true',
                        help='跳過產圖後的中文文字檢查（不建議：偵測不到就等於沒有偵測）')
    parser.add_argument('--name', help='只產生指定圖片 name')
    parser.add_argument('--units-file', type=Path, help=f'從 image units JSON 讀取批次清單（預設範例清單不使用）')
    parser.add_argument('--limit', type=int, help='搭配 --units-file，只處理幾張圖片')
    parser.add_argument('--offset', type=int, default=0, help='搭配 --units-file，從第幾筆開始（0-based，預設: 0）')
    parser.add_argument('--skip-existing', dest='skip_existing', action='store_true', default=True, help='已有輸出檔時略過（預設）')
    parser.add_argument('--no-skip-existing', dest='skip_existing', action='store_false', help='即使檔案存在也重新產生')
    parser.add_argument('--max-retries', type=int, default=2, help='失敗後最多重試次數（預設: 2）')
    parser.add_argument('--timeout', type=int, default=180, help='單次 Codex CLI timeout 秒數（預設: 180）')
    args = parser.parse_args()

    if args.max_retries < 0:
        parser.error('--max-retries must be >= 0')
    if args.timeout <= 0:
        parser.error('--timeout must be > 0')
    if args.limit is not None and args.limit < 1:
        parser.error('--limit must be >= 1')
    if args.offset < 0:
        parser.error('--offset must be >= 0')

    try:
        if args.units_file:
            units_file = args.units_file if args.units_file.is_absolute() else BASE / args.units_file
            images = selected_unit_images(units_file, args.name, args.offset, args.limit)
        else:
            images = selected_images(args.name)
    except ValueError as exc:
        parser.error(str(exc))

    cache = load_prompt_cache()
    cache_changed = False
    stats = {'ok': 0, 'failed': 0, 'skipped': 0}

    if not args.dry_run:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for image in images:
        out_path = OUTPUT_DIR / image['output']
        prompt = image_prompt(image, cache)

        if args.skip_existing and out_path.exists() and not args.dry_run:
            print(f'SKIP {image["name"]}: {out_path} already exists')
            append_generation_log({
                'name': image['name'],
                'output': image['output'],
                'status': 'skipped',
                'out_path': str(out_path),
            })
            stats['skipped'] += 1
            continue

        if args.dry_run:
            print(f'[{image["name"]}] -> {out_path}')
            print(prompt)
            print()
            continue

        cache_changed = update_prompt_cache(image, prompt, cache) or cache_changed
        if generate_one(image, prompt, out_path, args.max_retries, args.timeout,
                        verify=not args.no_verify):
            stats['ok'] += 1
        else:
            stats['failed'] += 1

    if cache_changed and not args.dry_run:
        write_prompt_cache(cache)

    if args.dry_run:
        print(f'DRY RUN: {len(images)} image prompt(s)')
    else:
        print(f'完成：ok={stats["ok"]} failed={stats["failed"]} skipped={stats["skipped"]}')


if __name__ == '__main__':
    main()
