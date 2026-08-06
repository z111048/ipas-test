#!/usr/bin/env python3
"""把 guide_ocr 的高精度 OCR 逐頁輸出轉成 pages_cache 的 schema（Track B：出題用）。

背景：學習指引原本用 Gemini 2.5 Flash vision 解析（scripts/pdf_vision_extract.py，144 dpi），
2026-08-06 改用 PaddleOCR-VL（288 dpi）重跑並人工校正，成果已複製進本專案成為
**學習指引的單一真相來源**：`data/{level}/guide_ocr/{key}/`。本腳本只做格式轉接，不呼叫 API。

    來源  data/{level}/guide_ocr/{key}/pages/page_NNNN/page_NNNN.md
    目標  data/{level}/pages_cache/{key}/page_NNN.json
          {"idx": 0-based, "markdown": str, "headings": [...], "type": str}

寫進去之後 parse_guides.py 見到 pages_cache/{key}/ 存在就走 vision mode，下游不必改。
本腳本只餵 Track B（出題用的 data/{level}/guide/subject*.json）。前端 GuidePage 讀的
guideContent 走 Track A（guide_ocr → page_extract → export_guide_outline_data），是另一支腳本。
同一份 guide_ocr 餵兩條軌，這是「單一真相來源」的落實方式。

## type 從哪裡來

沿用備份的 Gemini 快取（pages_cache_gemini_backup/）按 idx 對應——PDF 沒換、頁數一致，
這樣本次只改動 markdown 文字這一個變數，章節組裝行為與舊版完全相同。
同時跑一套規則判定當交叉檢查，不一致的頁會列在報告裡（--report）供人工確認。
沒有備份可對應時（例如新加的 errata）才落回規則判定。

## 標題規則（2026-08-06 用全 716 頁實測校準，見 --report）

PaddleOCR 的 block_label 語意不可靠，markdown 的 # 標記則是「有標的多半真的是標題、
但層級亂掉」。所以策略是不對稱的：

  * 已經有 # 的行 → 信任它是標題，只重算層級（PaddleOCR 會把 3.1 標成 ###、把（1）標成 ##）。
  * 沒有 # 的行 → 只在「有 a./A. 這類前綴 + 夠短 + 沒有句末標點」時才提升。
    實測 plain 的「第X章」「N.N」全部是目錄行（`..... 3-3`），plain 的「（N）」全部是
    正文段落（最短也超過 40 字），plain 的「N.」幾乎全是練習頁題號，一律不提升。
    唯一值得提升的是 a./A. 型小標（76 筆，如「a. 方法概述」）。

沒有前綴的純文字標題（如「獨立樣本 t 檢定（Independent-samples t-test）」）本腳本抓不到，
Gemini 版抓得到——這是已知的取捨，寧可漏抓也不要把正文誤判成標題。--report 會量化差距。
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path

BASE = Path('/home/james/projects/ipas-test')

# OCR 成果已複製進本專案，這裡是學習指引的單一真相來源。
# 版面結構：data/{level}/guide_ocr/{key}/pages/page_NNNN/page_NNNN.{md,_res.json}
#           data/{level}/guide_ocr/{key}/merged.md
OCR_ROOT = 'guide_ocr'

# (level, key, 頁數)。頁數用來驗證來源完整。errata 不進 pages_cache（不是學習指引本文），
# 但同樣有 OCR 成果在 guide_ocr/errata/，供勘誤套用階段使用。
BOOKS = [
    ('初級', 'guide1', 71),
    ('初級', 'guide2', 62),
    ('中級', 'guide1', 168),
    ('中級', 'guide2', 182),
    ('中級', 'guide3', 223),
]

# --- 標題規則 ---------------------------------------------------------------
# 目錄行：「第三章 AI 相關技術應用..... 3-1」。這種行永遠不是標題。
TOC_LINE = re.compile(r'[.…]{3,}|\s\d+\s*[-–]\s*\d+\s*$')

# (名稱, 樣式, 層級)。順序即優先，第一個命中者勝。層級反映原書階層：
#   第X章 > N.N 節 > 一、/ N. 小節 > （N）> a.
HEADING_RULES = [
    ('chapter', re.compile(r'^第[一二三四五六七八九十百0-9]+章[\s、]'), 2),
    ('section', re.compile(r'^\d+[.\-]\d+(\.\d+)?[\s、]'), 2),
    ('cjk_num', re.compile(r'^[一二三四五六七八九十]+[、]'), 3),
    ('arabic', re.compile(r'^\d+[.、]\s*\D'), 3),
    ('paren', re.compile(r'^[（(][0-9一二三四五六七八九十][）)]'), 4),
    ('alpha', re.compile(r'^[a-zA-Z][.)]\s'), 5),
]

# 沒有 # 標記時，只有這些前綴 + 夠短 + 無句末標點才提升為標題。
PROMOTABLE = {'alpha'}
PROMOTE_MAX_LEN = 40
SENTENCE_END = re.compile(r'[。；：，、]$|。')

BULLET = re.compile(r'^[■○●▪◆•‧・]\s*')

# PaddleOCR 把插圖抽成 <img src="imgs/xxx.jpg">，指向 paddleocr-test 專案裡的檔案。
# 那些檔案不在本專案，留著只會變成 prompt 裡的死連結雜訊（Gemini 版本來就沒有圖片語法）。
# 原圖仍在 data/{level}/guide_ocr/{key}/pages/page_NNNN/imgs/ 內，日後要做原頁對照再接。
IMG_TAG = re.compile(r'<img\b[^>]*>')
EMPTY_DIV = re.compile(r'<div\b[^>]*>\s*</div>')


def classify_heading(body: str) -> tuple[str, int] | None:
    """回傳 (規則名, 層級)，或 None 表示不符合任何標題樣式。"""
    for name, pattern, level in HEADING_RULES:
        if pattern.match(body):
            return name, level
    return None


def normalize_markdown(raw: str) -> tuple[str, list[dict]]:
    """正規化一頁 markdown 的標題層級與條列符號，並抽出 headings。"""
    out_lines: list[str] = []
    headings: list[dict] = []
    seen_chapter: set[str] = set()

    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            out_lines.append('')
            continue

        # HTML 表格整段原樣保留（PaddleOCR 輸出 <table>，Gemini 版也是，下游相容）；
        # 插圖標籤剝掉，剝完若整行空掉就丟棄。
        if stripped.startswith('<'):
            cleaned = EMPTY_DIV.sub('', IMG_TAG.sub('', stripped)).strip()
            if cleaned:
                out_lines.append(cleaned)
            continue

        m = re.match(r'^(#+)\s+(.*)$', stripped)
        hashed = bool(m)
        body = m.group(2).strip() if m else stripped

        if TOC_LINE.search(body):
            # 目錄行：拿掉可能的 # 後當普通文字留著（這些頁多半是 skip type）。
            out_lines.append(body)
            continue

        hit = classify_heading(body)
        is_heading = False
        if hit:
            name, level = hit
            if hashed:
                is_heading = True
            elif name in PROMOTABLE and len(body) <= PROMOTE_MAX_LEN and not SENTENCE_END.search(body):
                is_heading = True

        if is_heading:
            name, level = hit
            # 頁眉重複：「第三章 機率統計基礎」每頁都印一次，只留第一次出現的。
            if name == 'chapter':
                norm = unicodedata.normalize('NFKC', body)
                if norm in seen_chapter:
                    continue
                seen_chapter.add(norm)
            out_lines.append(f'{"#" * level} {body}')
            headings.append({'level': level, 'title': body})
            continue

        if hashed:
            # PaddleOCR 認定是標題但不符任何前綴樣式（多為純文字小標）。
            # 保留標題身分，層級夾到 2-6 並統一為 3（節內小標的常見位置）。
            level = 3
            out_lines.append(f'{"#" * level} {body}')
            headings.append({'level': level, 'title': body})
            continue

        out_lines.append(BULLET.sub('- ', stripped))

    text = '\n'.join(out_lines)
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    return text, headings


# --- type 判定 --------------------------------------------------------------
# 「模擬考題」「考題解析」是章末練習區塊的起點，會單獨成行（或是該頁的標題行）。
# 不能只用 search：目錄頁把這幾個字當條目列出，會誤判整本。
PRACTICE_MARK = re.compile(r'^#{0,6}\s*(模擬\s*考題|考題\s*解析|練習題)\s*$')
ANSWER_LINE = re.compile(r'^#{0,6}\s*\d+[.、]\s*.{0,20}Ans')
# 題號行不帶 # ——「### 5. CV 應用情境與實務案例」是正文小標，不是題目。
QUESTION_NO = re.compile(r'^\d+[.、]')
OPTION_LINE = re.compile(r'^[-\s]*[（(][A-D][）)]')


def rule_based_type(markdown: str, idx: int) -> str:
    """單頁判定，不帶跨頁狀態。

    早期版本用「看到模擬考題就進入 practice、看到下一章才離開」的跨頁狀態機，
    但初級的章標題在 OCR 輸出裡不會重複出現，狀態一開就關不掉，整本後半被誤判。
    改用局部特徵：練習頁的題號行與選項行密度和正文頁差異極大（實測正文頁為 0）。
    """
    if not markdown.strip():
        return 'skip'
    if idx < 3:
        # 封面、版權頁、目錄開頭。目錄會把「模擬考題」當條目列出，要先擋掉。
        return 'skip'

    lines = [l.strip() for l in markdown.splitlines() if l.strip()]
    if any(PRACTICE_MARK.match(l) or ANSWER_LINE.match(l) for l in lines):
        return 'practice'
    if sum(bool(QUESTION_NO.match(l)) for l in lines) >= 3:
        return 'practice'
    if sum(bool(OPTION_LINE.match(l)) for l in lines) >= 4:
        return 'practice'
    return 'content'


def load_backup_types(level: str, key: str) -> dict[int, str]:
    backup = BASE / 'data' / level / f'pages_cache_gemini_backup' / key
    if not backup.exists():
        return {}
    types = {}
    for path in backup.glob('page_[0-9]*.json'):
        with path.open(encoding='utf-8') as f:
            d = json.load(f)
        types[d['idx']] = d.get('type', 'content')
    return types


def load_backup_headings(level: str, key: str) -> dict[int, list[dict]]:
    backup = BASE / 'data' / level / 'pages_cache_gemini_backup' / key
    if not backup.exists():
        return {}
    out = {}
    for path in backup.glob('page_[0-9]*.json'):
        with path.open(encoding='utf-8') as f:
            d = json.load(f)
        out[d['idx']] = d.get('headings', [])
    return out


def ocr_pages_dir(level: str, key: str) -> Path:
    return BASE / 'data' / level / OCR_ROOT / key / 'pages'


def convert_book(level: str, key: str, expected_pages: int, dry_run: bool) -> dict:
    pages_dir = ocr_pages_dir(level, key)
    if not pages_dir.exists():
        raise SystemExit(f'來源不存在：{pages_dir}')

    md_paths = sorted(pages_dir.glob('page_[0-9]*/page_[0-9]*.md'))
    if len(md_paths) != expected_pages:
        raise SystemExit(
            f'{level}/{key}: 來源 {len(md_paths)} 頁，預期 {expected_pages} 頁——先確認來源完整再跑'
        )

    backup_types = load_backup_types(level, key)
    backup_headings = load_backup_headings(level, key)
    out_dir = BASE / 'data' / level / 'pages_cache' / key

    entries = []
    for md_path in md_paths:
        page_no = int(re.search(r'page_(\d+)\.md$', md_path.name).group(1))
        idx = page_no - 1  # page_NNNN 是 1-based PDF 頁碼
        raw = md_path.read_text(encoding='utf-8')
        markdown, headings = normalize_markdown(raw)
        entries.append({
            'idx': idx,
            'markdown': markdown,
            'headings': headings,
            '_gemini_headings': backup_headings.get(idx, []),
        })

    for e in entries:
        e['_rule_type'] = rule_based_type(e['markdown'], e['idx'])
        e['type'] = backup_types.get(e['idx'], e['_rule_type'])

    if not dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
        for stale in out_dir.glob('page_[0-9]*.json'):
            stale.unlink()
        for e in entries:
            payload = {k: v for k, v in e.items() if not k.startswith('_')}
            path = out_dir / f'page_{e["idx"]:03d}.json'
            with path.open('w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)

        index = {
            'key': key,
            'pages': [
                {'idx': e['idx'], 'type': e['type'], 'headings': e['headings']}
                for e in entries
            ],
        }
        with (out_dir / 'page_index.json').open('w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=2)

        counts = {t: sum(1 for e in entries if e['type'] == t) for t in ('content', 'practice', 'skip')}
        with (out_dir / 'summary.json').open('w', encoding='utf-8') as f:
            json.dump({
                'total': len(entries),
                'engine': 'paddleocr-vl-3.6.0',
                'source': str(pages_dir),
                **counts,
            }, f, ensure_ascii=False, indent=2)

    return {'level': level, 'key': key, 'entries': entries}


def report(result: dict) -> None:
    entries = result['entries']
    level, key = result['level'], result['key']
    type_mismatch = [e for e in entries if e['type'] != e['_rule_type']]
    n_head = sum(len(e['headings']) for e in entries)
    n_gemini = sum(len(e['_gemini_headings']) for e in entries)
    chars = sum(len(e['markdown']) for e in entries)

    print(f'\n=== {level} {key}')
    print(f'  頁數 {len(entries)}  字元 {chars:,}')
    print(f'  headings: 本腳本 {n_head}  vs  Gemini 版 {n_gemini}')
    print(f'  type 與 Gemini 不一致（已採用 Gemini 的）：{len(type_mismatch)} 頁')
    for e in type_mismatch[:8]:
        print(f'    idx={e["idx"]:>3} gemini={e["type"]:<8} rule={e["_rule_type"]}')
    if len(type_mismatch) > 8:
        print(f'    …另外 {len(type_mismatch) - 8} 頁')

    # 只在 content 頁上比標題集合，practice/skip 頁不影響下游
    missing_pages = [
        e for e in entries
        if e['type'] == 'content' and e['_gemini_headings'] and not e['headings']
    ]
    print(f'  content 頁中 Gemini 有標題、本腳本全無：{len(missing_pages)} 頁')
    for e in missing_pages[:5]:
        titles = '、'.join(h['title'] for h in e['_gemini_headings'][:2])
        print(f'    idx={e["idx"]:>3} Gemini: {titles[:60]}')


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--level', choices=['初級', '中級'], help='只轉某一級別（預設全部）')
    ap.add_argument('--key', help='只轉某一份，如 guide2')
    ap.add_argument('--dry-run', action='store_true', help='只算不寫檔')
    args = ap.parse_args()

    books = [b for b in BOOKS
             if (not args.level or b[0] == args.level)
             and (not args.key or b[1] == args.key)]
    if not books:
        raise SystemExit('沒有符合條件的書')

    for level, key, pages in books:
        result = convert_book(level, key, pages, args.dry_run)
        report(result)

    print('\n(dry-run，未寫檔)' if args.dry_run else '\n完成，已寫入 data/{level}/pages_cache/')


if __name__ == '__main__':
    main()
