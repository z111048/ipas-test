#!/usr/bin/env python3
"""用 Apple Vision 獨立驗證「學習指引 PDF → 已發佈 guideContent」的文字覆蓋度。

Vision 與產出資料的 PaddleOCR-VL 是不同引擎，因此不會同步犯錯。兩個子命令：

  ocr      逐頁渲染 PDF 並以 Vision OCR，結果快取成 JSON（需 macOS＋pyobjc-framework-vision＋pypdfium2；
           例如用 ocr-lab 的 venv 直譯器執行；可 --shard i/n 開多個程序平行）。
  compare  純標準庫：把每頁 Vision 文字與該頁（前後各 1 頁）發佈文字比對，輸出召回率與缺漏候選行。

範圍與限制：只驗「PDF 上的字有沒有進發佈內容」（不驗反向多字，也不驗公式／表格語意）。
公式、圖內標籤、章節頁眉會被 Vision 誤讀或本來就不收，故以「頁面召回率」與「人工檢視候選行」為準，
不是逐字正確性證明。快取與報告預設寫在 gitignored 的 logs/guide_vision_ocr/。
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
import tempfile
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / 'frontend/src/generated/guideContent'
DEFAULT_CACHE = ROOT / 'logs/guide_vision_ocr'
FRONT_PAGES = 4          # 封面／目錄／職能基準等前置頁不進發佈內容
HEADER_RE = re.compile(r'^[\W_▶》＞〉>\\]*第.{1,3}章')


def guide_pdfs() -> dict[str, Path]:
    """{'初級-guide1': pdf, ...}；依 data/{level}/pdfs/ 的「學習指引-科目N」檔名。"""
    found: dict[str, Path] = {}
    for level in ('初級', '中級'):
        for n in (1, 2, 3):
            hits = sorted((ROOT / 'data' / level / 'pdfs').glob(f'*學習指引*科目{n}*.pdf'))
            if hits:
                found[f'{level}-guide{n}'] = hits[0]
    return found


def norm(text: str) -> str:
    text = unicodedata.normalize('NFKC', text)
    return ''.join(ch for ch in text if ch.isalnum())


def strip_tags(html: str) -> str:
    # 只剝真正的標籤；「<5」這類文字不能當標籤，否則會跨區塊吃掉內容。
    return re.sub(r'</?[A-Za-z][^<>]*>', ' ', html)


def bigrams(text: str) -> collections.Counter:
    return collections.Counter(text[i:i + 2] for i in range(len(text) - 1))


# ---------------------------------------------------------------- ocr

def cmd_ocr(args: argparse.Namespace) -> int:
    try:
        import Vision  # type: ignore
        from Foundation import NSURL  # type: ignore
        import pypdfium2 as pdfium  # type: ignore
    except ImportError as exc:
        print(f'缺少相依套件（{exc}）。請用有 pyobjc-framework-vision 與 pypdfium2 的直譯器執行，'
              '例如 ocr-lab 專案的 .venv/bin/python。', file=sys.stderr)
        return 2

    def vision_lines(png: str) -> list[str]:
        handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(NSURL.fileURLWithPath_(png), None)
        req = Vision.VNRecognizeTextRequest.alloc().init()
        req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
        req.setRecognitionLanguages_(['zh-Hant', 'en-US'])
        req.setUsesLanguageCorrection_(True)
        ok, err = handler.performRequests_error_([req], None)
        if not ok:
            raise RuntimeError(err)
        return [o.topCandidates_(1)[0].string() for o in req.results()]

    shard, total = map(int, args.shard.split('/'))
    cache = Path(args.cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    jobs = []
    for key, pdf in guide_pdfs().items():
        doc = pdfium.PdfDocument(str(pdf))
        jobs += [(key, pdf, p) for p in range(len(doc))]
    mine = [j for i, j in enumerate(jobs) if i % total == shard]
    done = 0
    for key, pdf, page in mine:
        out = cache / f'{key}_{page:04d}.json'
        if out.exists() and not args.force:
            continue
        image = pdfium.PdfDocument(str(pdf))[page].render(scale=args.dpi / 72).to_pil()
        with tempfile.TemporaryDirectory() as tmp:
            png = str(Path(tmp) / 'page.png')
            image.save(png)
            lines = vision_lines(png)
        out.write_text(json.dumps({'key': key, 'pageIndex': page, 'lines': lines}, ensure_ascii=False), encoding='utf-8')
        done += 1
    print(f'shard {shard}/{total}: OCR {done} 頁（略過已快取）')
    return 0


# ---------------------------------------------------------------- compare

def published_pages(key: str) -> tuple[dict[int, str], dict[int, list[str]]]:
    pages: dict[int, list[str]] = collections.defaultdict(list)
    for path in sorted((CONTENT / key).glob('*.json')):
        for block in json.loads(path.read_text(encoding='utf-8'))['blocks']:
            parts = [str(block.get(k) or '') for k in ('text', 'title', 'marker')]
            parts.append(strip_tags(str(block.get('html') or '')))
            if block.get('rows'):
                parts.append(strip_tags(json.dumps(block['rows'], ensure_ascii=False)))
            text = norm(' '.join(parts))
            for page in {block.get('pageIndex'), *(block.get('sourcePageIndexes') or [])}:
                if page is not None:
                    pages[int(page)].append(text)
    return {p: ''.join(v) for p, v in pages.items()}, pages


def cmd_compare(args: argparse.Namespace) -> int:
    cache = Path(args.cache_dir)
    report: dict[str, dict] = {}
    failures: list[str] = []
    for key, pdf in guide_pdfs().items():
        files = sorted(cache.glob(f'{key}_*.json'))
        if not files:
            print(f'{key}: 無 OCR 快取（先跑 ocr 子命令）', file=sys.stderr)
            return 2
        vis = {json.loads(f.read_text(encoding='utf-8'))['pageIndex']: json.loads(f.read_text(encoding='utf-8'))['lines']
               for f in files}
        last = max(vis)
        pub, _ = published_pages(key)
        seen = collections.Counter(norm(line) for lines in vis.values() for line in set(lines))
        running = {t for t, c in seen.items() if t and c >= max(5, 0.25 * len(vis))}   # 頁眉頁尾
        rows, candidates = [], []
        for page in sorted(vis):
            if page < FRONT_PAGES or page == last:
                continue
            pool = ''.join(pub.get(p, '') for p in (page - 1, page, page + 1))
            pool_bg = set(bigrams(pool))
            own = bigrams(pub.get(page, ''))
            text = norm(''.join(line for line in vis[page] if norm(line) not in running))
            vb = bigrams(text)
            n = sum(vb.values())
            if n == 0:
                continue
            recall = sum(min(c, own[b]) for b, c in vb.items()) / n
            recall_pool = sum(min(c, bigrams(pool)[b]) for b, c in vb.items()) / n
            rows.append({'page': page, 'chars': n, 'recall': round(recall, 3), 'recallPool': round(recall_pool, 3),
                         'published': bool(pub.get(page))})
            for line in vis[page]:
                t = norm(line)
                if len(t) < 8 or t in running or HEADER_RE.match(line):
                    continue
                bg = [t[i:i + 2] for i in range(len(t) - 1)]
                cov = sum(b in pool_bg for b in bg) / len(bg)
                if cov < 0.4:
                    candidates.append({'page': page, 'coverage': round(cov, 2), 'line': line})
        total = sum(r['chars'] for r in rows)
        weighted = sum(r['chars'] * r['recallPool'] for r in rows) / total
        empty = [r['page'] for r in rows if not r['published']]
        low = [r['page'] for r in rows if r['published'] and r['recallPool'] < args.page_threshold]
        report[key] = {'pages': len(vis), 'contentPages': len(rows), 'weightedRecall': round(weighted, 3),
                       'pagesWithoutPublished': empty, 'lowRecallPages': low, 'candidateLines': candidates}
        print(f'{key}: 內容頁 {len(rows)}／{len(vis)}，加權召回 {weighted:.3f}，'
              f'無發佈內容頁 {empty}，低於 {args.page_threshold} 的頁 {low}，缺漏候選行 {len(candidates)}')
        if empty:
            failures.append(f'{key} 有內容頁沒有任何發佈內容：{empty}')
        if weighted < args.min_recall:
            failures.append(f'{key} 加權召回 {weighted:.3f} < {args.min_recall}')
    out = cache / 'report.json'
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'報告：{out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}（candidateLines 需人工檢視）')
    for msg in failures:
        print('FAIL', msg, file=sys.stderr)
    return 1 if failures and args.check else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='cmd', required=True)
    for name, fn in (('ocr', cmd_ocr), ('compare', cmd_compare)):
        p = sub.add_parser(name)
        p.add_argument('--cache-dir', default=str(DEFAULT_CACHE))
        p.set_defaults(fn=fn)
        if name == 'ocr':
            p.add_argument('--shard', default='0/1', help='i/n，開 n 個程序平行')
            p.add_argument('--dpi', type=int, default=200)
            p.add_argument('--force', action='store_true')
        else:
            p.add_argument('--min-recall', type=float, default=0.90, help='每份指引加權召回下限')
            p.add_argument('--page-threshold', type=float, default=0.90)
            p.add_argument('--check', action='store_true', help='未達標時以非 0 結束')
    args = parser.parse_args()
    return args.fn(args)


if __name__ == '__main__':
    sys.exit(main())
