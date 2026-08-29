#!/usr/bin/env python3
"""對「資料 JSON 裡引用的每一個資產 URL」發 HEAD，確認線上真的拿得到。

  python3 scripts/verify_r2_assets.py --base https://assets.example.com
  python3 scripts/verify_r2_assets.py --base https://... --sample 50   # 只驗前 50 筆（快速煙霧測試）

**預設是全量，不是抽樣**，這是刻意的：實測 1,947 筆引用裡有 **1,930 筆（99%）路徑含非 ASCII 字元**
（`pdf-assets/` 100%、`images/` 710/727）。中文 key 在物件儲存的百分比編碼是最典型的
「抽樣看起來全過、實際壞掉一半」的失效模式。

引用來源掃兩軌：`frontend/src/generated/**` 與 `data/{level}/questions/*.json`
（後者放考題附圖，前端經 `@data` / `@data-mid` alias 讀）。
比對規則與 `audit_resources.py` 一致：key 為 `src` / `path` / `image` 且值以 `/` 開頭的字串。
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Iterator

from asset_paths import BASE

GENERATED = BASE / 'frontend' / 'src' / 'generated'
ASSET_KEYS = ('src', 'path', 'image')


def iter_asset_srcs(node: Any) -> Iterator[str]:
    """與 audit_resources._iter_image_srcs 同一套規則。"""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ASSET_KEYS and isinstance(value, str) and value.startswith('/'):
                yield value
            else:
                yield from iter_asset_srcs(value)
    elif isinstance(node, list):
        for item in node:
            yield from iter_asset_srcs(item)


def source_files() -> list[Path]:
    """所有可能引用資產的資料 JSON。

    **兩軌都要掃**：`frontend/src/generated/**` 是主要來源，但考題附圖的路徑住在
    `data/{level}/questions/*.json`（前端經 `@data` / `@data-mid` alias 讀，實測 65 筆）。
    只掃 generated 的話，資產搬 R2 後這支會印「✓ 全部回 200」而那 65 張根本沒驗過。
    """
    paths = [p for p in GENERATED.rglob('*.json')
             if 'before_ocr_merge' not in p.as_posix()]
    paths += sorted((BASE / 'data').glob('*/questions/*.json'))
    return sorted(set(paths))


def collect_referenced() -> list[str]:
    srcs: set[str] = set()
    for path in source_files():
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as exc:
            print(f'WARN: {path.relative_to(BASE)} 不是合法 JSON：{exc}', file=sys.stderr)
            continue
        srcs.update(iter_asset_srcs(data))
    return sorted(srcs)


def head(base: str, src: str, timeout: float) -> tuple[str, int | str]:
    """回傳 (src, 狀態)。狀態是 HTTP code，或連線層的錯誤字串。"""
    # 逐段 quote：路徑分隔的 '/' 要保留，中文與空白要編碼
    encoded = '/'.join(urllib.parse.quote(part) for part in src.lstrip('/').split('/'))
    url = f'{base.rstrip("/")}/{encoded}'
    request = urllib.request.Request(url, method='HEAD')
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return src, response.status
    except urllib.error.HTTPError as exc:
        return src, exc.code
    except Exception as exc:  # 連線層失敗（DNS、TLS、timeout）
        return src, f'{type(exc).__name__}: {exc}'


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--base', required=True, help='資產來源，例如 https://assets.example.com')
    parser.add_argument('--sample', type=int, help='只驗前 N 筆（煙霧測試用；正式驗收不要用）')
    parser.add_argument('--workers', type=int, default=24)
    parser.add_argument('--timeout', type=float, default=20.0)
    args = parser.parse_args()

    srcs = collect_referenced()
    if not srcs:
        print('ERROR: 在 generated/ 與 data/*/questions/ 底下都找不到任何資產引用，'
              '檢查邏輯可能壞了。', file=sys.stderr)
        return 1

    non_ascii = sum(1 for s in srcs if any(ord(c) > 127 for c in s))
    print(f'引用的資產 URL：{len(srcs)} 筆（其中 {non_ascii} 筆含非 ASCII 字元，'
          f'{non_ascii / len(srcs) * 100:.0f}%）')

    if args.sample:
        srcs = srcs[:args.sample]
        print(f'⚠️  只驗前 {len(srcs)} 筆——這是煙霧測試，不是驗收。')

    print(f'對 {args.base} 發 {len(srcs)} 個 HEAD…\n')

    bad: list[tuple[str, int | str]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for done, (src, status) in enumerate(
                pool.map(lambda s: head(args.base, s, args.timeout), srcs), start=1):
            if status != 200:
                bad.append((src, status))
            if done % 200 == 0 or done == len(srcs):
                print(f'  {done}/{len(srcs)}　失敗 {len(bad)}')

    print()
    if not bad:
        print(f'✓ 全部 {len(srcs)} 個資產都回 200。')
        return 0

    print(f'✗ {len(bad)} 個資產取不到：\n')
    for src, status in bad[:25]:
        print(f'  [{status}] {src}')
    if len(bad) > 25:
        print(f'  …另有 {len(bad) - 25} 筆')

    bad_non_ascii = sum(1 for s, _ in bad if any(ord(c) > 127 for c in s))
    if bad_non_ascii == len(bad) and len(bad) > 1:
        print('\n注意：失敗的全部都是含非 ASCII 字元的路徑 —— 這是 key 編碼問題，'
              '不是漏傳。檢查上傳工具的 S3 key 編碼。')
    return 1


if __name__ == '__main__':
    sys.exit(main())
