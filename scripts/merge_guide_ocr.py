#!/usr/bin/env python3
"""把 guide_ocr 的結構性成果合併進 Track A（前端閱讀頁）的 page_extract。

## 為什麼是「合併」而不是「取代」

Track A 的來源鏈是
    extract_pdf_pages_structured.py → page_extract → clean_pdf_page_text.py → page_clean
    → export_guide_outline_data.py → frontend/src/generated/guideContent/

`page_extract` 的文字來自 **PDF 文字層**，對原稿是無損的。2026-08-06 實測比對後確認，
PaddleOCR 在這三件事上比文字層差，不能拿來取代：

  * 條列符號流失 72.8%（文字層 5,803 個 → OCR 1,577 個）。文字層有乾淨的三層階層
    （• 1769 / ◦ 2028 / ○ 2004），正是 guideContent 巢狀清單深度的依據；OCR 把它們
    塌成 ■/◆/○/• 且不一致。
  * 殘留 OCR 錯字（抽驗到「侷→侗」「考題→考礎」）。
  * 異體字偏離原稿（「佈→布」，而原稿印的是「佈」）。

OCR 贏的是另外三件事，文字層做不到：

  * 公式：文字層把公式攤成亂碼字元，OCR 給 LaTeX（682 個行內 + 63 個顯示式，
    且已經 KaTeX/MathJax 雙引擎驗過零解析錯誤）。
  * 表格：OCR 給結構完整的 HTML <table>，PDF 的列偵測會把上下標吃掉（「H₁」vs `$H_1$`）。
  * 區塊語意標籤：header / number 明確標出頁眉頁碼。

所以本腳本只注入後三項，一個字都不改文字層內容。

## 產出

  1. 就地改寫 `data/{level}/page_extract/{key}/pages/page_NNN.json` 的 `tables[].rows`
     （只替換既有表格，不新增——新增的表格沒有對應的 PNG 資產，前端會 404）。
     首次執行會先整包備份到 `page_extract_before_ocr_merge/`。
  2. 新增 `data/{level}/ocr_formulas/{key}/page_NNN.json`，格式刻意做成
     `export_guide_outline_data.py` 的 `collect_formula_blocks()` 吃得下的樣子
     （`{"blocks": [{"type": "formula", "latex": ..., "display": ...}]}`），
     這樣就沿用既有的 audit_cache 公式注入管線，不必另造一套匹配邏輯。

跑完之後照 playbook/06 §9 重建 page_clean → guideContent。
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from html.parser import HTMLParser
from pathlib import Path

BASE = Path('/home/james/projects/ipas-test')

BOOKS = [
    ('初級', 'guide1', 71),
    ('初級', 'guide2', 62),
    ('中級', 'guide1', 168),
    ('中級', 'guide2', 182),
    ('中級', 'guide3', 223),
]

# bbox 重疊多少才算同一個表格。OCR 與 PDF 的偵測框不會完全一致，取寬鬆門檻。
TABLE_IOU_MIN = 0.30


class TableParser(HTMLParser):
    """把 OCR 的 <table> 拆成 rows。只需處理 <tr>/<td>，另含少量 rowspan/colspan。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._spans: dict[tuple[int, int], str] = {}  # (row, col) → 由 rowspan 佔位的內容
        self._rowspan_pending: list[tuple[int, int, int, str]] = []  # r, c, 剩餘列數, 內容

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag == 'tr':
            self._row = []
        elif tag in ('td', 'th') and self._row is not None:
            self._cell = []
            self._colspan = int(a.get('colspan') or 1)
            self._rowspan = int(a.get('rowspan') or 1)

    def handle_endtag(self, tag: str) -> None:
        if tag in ('td', 'th') and self._cell is not None and self._row is not None:
            # OCR 在儲存格內用「字面兩字元 \n」表示換行，不是真的換行字元。
            # 前端表格是 whitespace-pre-line，轉成真換行才會正確斷行。
            text = ''.join(self._cell).replace('\\n', '\n')
            text = re.sub(r'[ \t]+', ' ', text)
            text = re.sub(r'\s*\n\s*', '\n', text).strip()
            r = len(self.rows)
            # 先把上一列 rowspan 佔走的欄位補進來，欄位才不會左移
            while (r, len(self._row)) in self._spans:
                self._row.append(self._spans.pop((r, len(self._row))))
            c = len(self._row)
            for i in range(self._colspan):
                self._row.append(text if i == 0 else '')
            for extra in range(1, self._rowspan):
                self._spans[(r + extra, c)] = text
            self._cell = None
        elif tag == 'tr' and self._row is not None:
            r = len(self.rows)
            while (r, len(self._row)) in self._spans:
                self._row.append(self._spans.pop((r, len(self._row))))
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


def parse_table_html(html: str) -> list[list[str]]:
    p = TableParser()
    p.feed(html)
    rows = [r for r in p.rows if any(c.strip() for c in r)]
    if not rows:
        return []
    width = max(len(r) for r in rows)
    return [r + [''] * (width - len(r)) for r in rows]


def parse_bbox(value) -> list[float] | None:
    """OCR 的 block_bbox 有時是字串 "[294, 208, 817, 261]"，有時已是 list。"""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return None
    if isinstance(value, (list, tuple)) and len(value) == 4:
        return [float(v) for v in value]
    return None


def iou(a: list[float], b: list[float]) -> float:
    ix0, iy0 = max(a[0], b[0]), max(a[1], b[1])
    ix1, iy1 = min(a[2], b[2]), min(a[3], b[3])
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    inter = (ix1 - ix0) * (iy1 - iy0)
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


INLINE_FORMULA = re.compile(r'\$([^$]{2,}?)\$')


def collect_formulas(blocks: list[dict]) -> list[dict]:
    """抽出該頁所有公式，顯示式與行內式都要。去重但保留順序。"""
    out: list[dict] = []
    seen: set[tuple[str, bool]] = set()

    def add(latex: str, display: bool) -> None:
        latex = latex.strip()
        # PaddleOCR 常輸出 "$ H_{0} $" 這種前後帶空白的形式，正規化以利去重與比對
        latex = re.sub(r'\s+', ' ', latex).strip()
        if len(latex) < 2:
            return
        if (latex, display) in seen:
            return
        seen.add((latex, display))
        out.append({'type': 'formula', 'latex': latex, 'display': display})

    for b in blocks:
        content = b.get('block_content') or ''
        if b.get('block_label') == 'display_formula':
            add(INLINE_FORMULA.sub(r'\1', content) if content.strip().startswith('$') else content, True)
            continue
        for m in INLINE_FORMULA.finditer(content):
            add(m.group(1), False)
    return out


def ocr_res_path(level: str, key: str, idx: int) -> Path:
    page_no = idx + 1
    return (BASE / 'data' / level / 'guide_ocr' / key / 'pages'
            / f'page_{page_no:04d}' / f'page_{page_no:04d}_res.json')


def backup_page_extract(level: str, key: str) -> None:
    src = BASE / 'data' / level / 'page_extract' / key
    dst = BASE / 'data' / level / 'page_extract_before_ocr_merge' / key
    if dst.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)
    print(f'  備份 {src.relative_to(BASE)} → {dst.relative_to(BASE)}')


def merge_book(level: str, key: str, pages: int, dry_run: bool) -> dict:
    pe_dir = BASE / 'data' / level / 'page_extract' / key / 'pages'
    formula_dir = BASE / 'data' / level / 'ocr_formulas' / key
    if not dry_run:
        backup_page_extract(level, key)
        formula_dir.mkdir(parents=True, exist_ok=True)

    stats = {'tables_replaced': 0, 'tables_unmatched': 0, 'pdf_tables': 0,
             'formula_pages': 0, 'formulas': 0, 'missing_ocr': 0}

    for idx in range(pages):
        pe_path = pe_dir / f'page_{idx:03d}.json'
        res_path = ocr_res_path(level, key, idx)
        if not pe_path.exists() or not res_path.exists():
            stats['missing_ocr'] += 1
            continue

        pe = json.loads(pe_path.read_text(encoding='utf-8'))
        res = json.loads(res_path.read_text(encoding='utf-8'))
        blocks = res.get('parsing_res_list') or []

        # OCR 座標是像素（288 DPI），page_extract 是 PDF point，比例逐頁算不硬編
        pdf_w = float(pe.get('width') or 0)
        ocr_w = float(res.get('width') or 0)
        scale = ocr_w / pdf_w if pdf_w and ocr_w else 0

        # --- 表格：用 OCR 的 rows 換掉 PDF 偵測的 rows（只換不增）
        pdf_tables = pe.get('tables') or []
        stats['pdf_tables'] += len(pdf_tables)
        if scale:
            ocr_tables = []
            for b in blocks:
                if b.get('block_label') != 'table':
                    continue
                bbox = parse_bbox(b.get('block_bbox'))
                rows = parse_table_html(b.get('block_content') or '')
                if bbox and rows:
                    ocr_tables.append(([v / scale for v in bbox], rows))

            used: set[int] = set()
            for table in pdf_tables:
                tb = table.get('bbox') or []
                if len(tb) != 4:
                    continue
                best_i, best_score = None, 0.0
                for i, (ob, _rows) in enumerate(ocr_tables):
                    if i in used:
                        continue
                    score = iou(tb, ob)
                    if score > best_score:
                        best_i, best_score = i, score
                if best_i is not None and best_score >= TABLE_IOU_MIN:
                    used.add(best_i)
                    table['rows'] = ocr_tables[best_i][1]
                    table['rows_source'] = 'guide_ocr'
                    stats['tables_replaced'] += 1
                else:
                    stats['tables_unmatched'] += 1

        # --- 公式：另存一份，走既有的 audit_cache 注入管線
        formulas = collect_formulas(blocks)
        if formulas:
            stats['formula_pages'] += 1
            stats['formulas'] += len(formulas)

        if not dry_run:
            pe_path.write_text(json.dumps(pe, ensure_ascii=False, indent=2), encoding='utf-8')
            if formulas:
                (formula_dir / f'page_{idx:03d}.json').write_text(
                    json.dumps({'blocks': formulas}, ensure_ascii=False, indent=2),
                    encoding='utf-8')

    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--level', choices=['初級', '中級'])
    ap.add_argument('--key')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    books = [b for b in BOOKS
             if (not args.level or b[0] == args.level)
             and (not args.key or b[1] == args.key)]
    if not books:
        raise SystemExit('沒有符合條件的書')

    for level, key, pages in books:
        print(f'=== {level} {key}')
        s = merge_book(level, key, pages, args.dry_run)
        print(f'  表格 {s["tables_replaced"]}/{s["pdf_tables"]} 換成 OCR 版'
              f'（{s["tables_unmatched"]} 個沒對上，保留 PDF 版）')
        print(f'  公式 {s["formulas"]} 個，分布 {s["formula_pages"]} 頁')
        if s['missing_ocr']:
            print(f'  ⚠ {s["missing_ocr"]} 頁缺 OCR 或 page_extract')

    print('\n(dry-run，未寫檔)' if args.dry_run else '\n完成')


if __name__ == '__main__':
    main()
