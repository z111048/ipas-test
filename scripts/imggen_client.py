#!/usr/bin/env python3
"""codex-imggen（`~/projects/codex-imggen`）的最小 client。

為什麼不直接 `codex exec`：直接呼叫會把 session rollout 與原始 PNG 堆在 host 的
`~/.codex/`，而且**產物檔名慣例會隨 codex-cli 版本變**——2026-08-08 就因為
0.146 把 `ig_*.png` 改成 `exec-<uuid>.png`，`generate_images.py` 在圖其實產出來
的情況下報「找不到 PNG」並重試三次全滅。這個服務直接回傳圖片 bytes，
沒有目錄與檔名可壞，垃圾也留在容器裡。

`/edit`（圖生圖）是這裡最有價值的一支：修圖卡錯字時可以**拿現有那張當參考、
只改文字**，保住原本的版面，而不是從頭重抽一張（重抽是抽籤，版面品質會變）。

用法：
    from imggen_client import generate, edit, healthz
    data = generate('...')                       # bytes
    data = edit('把「判別式AI」改成「鑑別式AI」', [Path('old.webp')])
"""

from __future__ import annotations

import os
from pathlib import Path

import requests

BASE_URL = os.environ.get('IMGGEN_URL', 'http://localhost:8090')
DEFAULT_SIZE = '1792x1024'
DEFAULT_FORMAT = 'webp'
# USAGE.md：單次生成數十秒到數分鐘，服務端逾時 600s
DEFAULT_TIMEOUT = 620


class ImggenError(RuntimeError):
    pass


def healthz(timeout: int = 5) -> dict:
    response = requests.get(f'{BASE_URL}/healthz', timeout=timeout)
    response.raise_for_status()
    return response.json()


def require_service() -> dict:
    """開跑前先確認服務活著，不要跑到一半才發現（錯誤訊息要指得出怎麼救）。"""
    try:
        info = healthz()
    except Exception as exc:
        raise ImggenError(
            f'連不上 codex-imggen（{BASE_URL}）：{exc}\n'
            '請在 ~/projects/codex-imggen 執行 docker compose up -d 後重試。'
        ) from exc
    if not info.get('ok'):
        raise ImggenError(f'codex-imggen 回報不健康：{info}')
    return info


def _check(response: requests.Response) -> bytes:
    if response.status_code != 200:
        detail = ''
        try:
            detail = response.json().get('detail', '')
        except Exception:
            detail = response.text[:300]
        raise ImggenError(f'HTTP {response.status_code}：{detail}')
    if not response.content:
        raise ImggenError('回應是 200 但 body 是空的')
    return response.content


def generate(prompt: str, size: str = DEFAULT_SIZE, fmt: str = DEFAULT_FORMAT,
             timeout: int = DEFAULT_TIMEOUT) -> bytes:
    response = requests.post(
        f'{BASE_URL}/generate',
        json={'prompt': prompt, 'size': size, 'format': fmt},
        timeout=timeout)
    return _check(response)


def edit(prompt: str, images: list[Path], size: str = DEFAULT_SIZE,
         fmt: str = DEFAULT_FORMAT, timeout: int = DEFAULT_TIMEOUT) -> bytes:
    handles = []
    try:
        files = []
        for path in images:
            handle = Path(path).open('rb')
            handles.append(handle)
            files.append(('image', (Path(path).name, handle)))
        response = requests.post(
            f'{BASE_URL}/edit',
            data={'prompt': prompt, 'size': size, 'format': fmt},
            files=files, timeout=timeout)
        return _check(response)
    finally:
        for handle in handles:
            handle.close()


if __name__ == '__main__':
    print(require_service())
