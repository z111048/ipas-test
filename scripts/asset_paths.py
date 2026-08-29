#!/usr/bin/env python3
"""靜態資產（pdf-assets / images）的路徑慣例，單一來源。

分兩件事，不要混在一起：

1. **URL 前綴**（`/pdf-assets/…`、`/images/…`）——寫進資料 JSON 的 `src` / `path` / `image`
   欄位。這一層**刻意維持根相對路徑，不含 host**。資產搬到 CDN 之後由前端的
   `frontend/src/utils/assets.ts` 的 `publicAsset()` 在 runtime 補上 base URL，
   2000 多筆資料 JSON 一個字都不用改。

2. **本機檔案根目錄**（`frontend/public/`）——給「這個 src 對應的檔案在不在」這種檢查用。
   資產移出版控之後，本機仍留著（gitignored），但**新 clone 或 CI 上會不存在**，
   所以要能用 `IPAS_ASSET_ROOT` 指到別的地方（或設成空字串表示「檔案不在本機，跳過存在性檢查」）。

第 1 點原本散在 4 支腳本裡各寫一次同樣的 `page_{n:03d}` 慣例
（`parse_guides.py`、`export_guide_outline_data.py` ×2、`parse_exams_v2.py`）。
`playbook/pipeline-reference.md` 記錄的 2026-08-25 事故——資產鍵改名導致 19 題引用附圖
但一張圖都沒有——就是這種各寫一份的慣例走鐘。
"""

from __future__ import annotations

import os
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]

# 寫進資料 JSON 的 URL 前綴。改這裡等於改全站資料，除非你真的要重跑整條 pipeline，否則不要動。
PDF_ASSETS_PREFIX = '/pdf-assets'
IMAGES_PREFIX = '/images'


def asset_root() -> Path | None:
    """資產在本機的根目錄；回傳 None 表示「不在本機，存在性檢查應跳過」。

    優先序：`IPAS_ASSET_ROOT` 環境變數 > 預設的 `frontend/public`。
    設成空字串（`IPAS_ASSET_ROOT=`）代表刻意宣告資產不在本機——
    這比讓每個檢查都誤報「檔案不見了」誠實。
    """
    raw = os.environ.get('IPAS_ASSET_ROOT')
    if raw is not None:
        return Path(raw).expanduser().resolve() if raw.strip() else None
    return BASE / 'frontend' / 'public'


def local_path(src: str) -> Path | None:
    """把資料 JSON 裡的根相對 URL（`/pdf-assets/初級/…`）對回本機檔案路徑。

    回傳 None 代表資產不在本機（見 `asset_root()`），呼叫端應跳過檢查而不是判定缺檔。
    """
    root = asset_root()
    if root is None:
        return None
    return root / src.lstrip('/')


def page_dir_name(page_index: int) -> str:
    """頁面資產目錄名。`page_index` 是 0-based。"""
    return f'page_{page_index:03d}'


def page_asset_url(level: str, key: str, page_index: int, filename: str = 'page.png') -> str:
    """PDF 頁面資產的根相對 URL。

    這是 `parse_guides.py`、`export_guide_outline_data.py`、`parse_exams_v2.py`
    共用的同一套慣例——四處各寫一份 f-string 是資產鍵走鐘的溫床。
    """
    return f'{PDF_ASSETS_PREFIX}/{level}/{key}/{page_dir_name(page_index)}/{filename}'


def pdf_asset_url(level: str, relative: str) -> str:
    """`pdf-assets/{level}/` 底下任意相對路徑的根相對 URL（gallery 用）。"""
    return f'{PDF_ASSETS_PREFIX}/{level}/{relative.lstrip("/")}'


def image_url(filename: str) -> str:
    """概念圖卡（`frontend/public/images/`）的根相對 URL。"""
    return f'{IMAGES_PREFIX}/{filename.lstrip("/")}'
