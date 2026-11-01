"""跨頁版面／文案回歸測試：每一個 UI 改動都在全部頁面、桌機＋手機兩種寬度一次驗完。

    uv run python tests/test_layout_audit.py
    uv run python tests/test_layout_audit.py --only exam      # 只跑 label/route 含 exam 的
    uv run python tests/test_layout_audit.py --phase1         # 把 PENDING 檢查也當成失敗

ENFORCED（失敗 → exit 1）：
  (a) 沒有水平溢出：documentElement 與 <main> 的 scrollWidth 都 <= clientWidth
      （本站內容在 <main> 內捲動，不是 document，所以兩個都要量）。
  (b) 沒有 console error / pageerror。
  (c) document.body.innerText 不含內部用語（BANNED_COPY）。CLAUDE.md 不變量 2 的延伸：
      使用者看到的是商品，不是我們的工作區。

PENDING（已實作，ENFORCE_PHASE1 = False 時只印 warning 與計數，方便追進度）：
  - 每頁恰好一個 <h1>。
  - 沒有可見文字節點的 computed font-size < 12px。
  - 手機寬度下可互動元素（a、button、input、select、[role=button]、[role=tab]）至少 44×44。
    豁免（對應 WCAG 2.5.8 的 inline 例外）：computed display 為 inline 的 <a>，
    且其最近的文字區塊祖先（p、li、td、th、dd、dt、blockquote、figcaption）的
    innerText 比連結本身長——也就是連結嵌在一段句子裡。checkbox／radio 若包在
    <label> 內，量的是 label 的尺寸。不在版面內的元素（寬或高 ≤ 1、visibility hidden、
    在 [inert]／[aria-hidden=true] 內、或整個落在 viewport 左右之外，例如收起的側欄）不計。

路由清單：test_routes.py 在 import 時就會 require_playwright 並直接開跑，無法安全 import，
所以這裡鏡像它的 ROUTES，並以 ast 讀 test_routes.py 的字面路由做漂移檢查——那邊新增
路由而這裡沒跟上時，本測試直接失敗。
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from devserver import dev_server, require_playwright  # noqa: E402

# Phase 1 的三項檢查（h1、字級、觸控尺寸）目前只回報；UX 改版 Phase 1 完成後改成 True。
ENFORCE_PHASE1 = False

VIEWPORTS = [
    ('desktop', {'viewport': {'width': 1440, 'height': 900}}),
    ('mobile', {'viewport': {'width': 390, 'height': 844}, 'is_mobile': True, 'has_touch': True}),
]

MIN_FONT_PX = 12
# 專用 port：5199 是 test_exam_flow／test_routes 共用的，別的測試收掉 server 時會連帶打斷這支。
PORT = 5209
MIN_TARGET_PX = 44

# ---------------------------------------------------------------- 路由

_catalog = json.loads((ROOT / 'data/resource_catalog.json').read_text(encoding='utf-8'))
CATALOG_EXAM_ROUTES = [
    (f'考卷 {exam["routeKey"]}', f'/exam/{exam["routeKey"]}') for exam in _catalog['exams']
]
FIRST_CONCEPT = json.loads(
    (ROOT / 'frontend/src/generated/conceptGraph.json').read_text(encoding='utf-8')
)['concepts'][0]
FIRST_ARTICLE_ID = json.loads(
    (ROOT / 'frontend/src/generated/learningArticles/index.json').read_text(encoding='utf-8')
)['flatArticleIds'][0]

# 鏡像 test_routes.ROUTES（見模組 docstring），再加上它沒涵蓋的頁面。
ROUTES = [
    ('首頁', '/'),
    ('科目總覽 s1', '/subject/s1'),
    ('科目總覽 mid-s1', '/subject/mid-s1'),
    ('學習指引 s1c1', '/guide/s1/s1c1'),
    ('學習指引 s1pdf-c3', '/guide/s1/s1pdf-c3'),
    ('學習指引 mid-s2c6', '/guide/mid-s2/mid-s2c6'),
    ('章節練習 s1c1', '/practice/s1/s1c1'),
    ('指引練習 s1c1', '/practice/s1/s1c1/guide'),
    *CATALOG_EXAM_ROUTES,
    ('學習文章列表', '/articles'),
    ('概念圖卡', '/visuals'),
    ('圖庫', '/images'),
    ('名詞解釋', '/glossary'),
    ('完整目錄', '/outline'),
    ('心智圖', '/mindmap'),
    ('概念索引', '/concepts'),
    ('概念索引 舊名連結', f'/concepts?c={FIRST_CONCEPT["name"]}'),
    # ---- test_routes 沒有的
    ('學習單元', '/learn'),
    ('專題', '/projects'),
    ('考題分析', '/analysis/exams'),
    (f'學習文章 {FIRST_ARTICLE_ID}', f'/articles/{FIRST_ARTICLE_ID}'),
    ('404', '/definitely-not-a-real-route'),
]


def route_drift() -> list[str]:
    """test_routes.py 的 ROUTES 裡的字面路由，必須都在這裡。"""
    tree = ast.parse((ROOT / 'tests/test_routes.py').read_text(encoding='utf-8'))
    theirs: set[str] = set()
    prefixes: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == 'ROUTES' for t in node.targets):
            in_fstring = {id(c) for j in ast.walk(node.value) if isinstance(j, ast.JoinedStr)
                          for c in j.values}
            for sub in ast.walk(node.value):
                if isinstance(sub, ast.JoinedStr) and isinstance(sub.values[0], ast.Constant):
                    prefixes.add(sub.values[0].value)  # f'/concepts?c={...}' → 前綴比對
                elif isinstance(sub, ast.Constant) and isinstance(sub.value, str) \
                        and sub.value.startswith('/') and id(sub) not in in_fstring:
                    theirs.add(sub.value)
    ours = {route for _, route in ROUTES}
    missing = theirs - ours
    missing |= {p + '…' for p in prefixes if not any(r.startswith(p) for r in ours)}
    return sorted(missing)


# ---------------------------------------------------------------- 禁用文案
#
# 收窄決策（2026-11-01 實跑全部路由後逐筆檢視命中；正文命中一律收窄 pattern，不做整頁白名單）：
#  - pipeline：mid-s2c6 講義與文章有「資料處理管線（Data Pipeline）」「Batch Pipeline」，
#    考題詳解有「訓練pipeline」、notebook 有 sklearn.pipeline。改為只抓**小寫、獨立成字**、
#    前面不是英文字／「.」／底線、也不是「英文字＋空白」（排除 data pipeline、ML pipeline）。
#    UI 外殼的內部用語是「由 pipeline 產生」這種中英夾雜的寫法，仍會命中。
#  - 母體：統計正文的「母體參數」「母體平均」「整體母體理解」（/articles 摘要命中）是考綱內容。
#    改為只抓題庫意義：「題目／考題／試題／題庫母體」或「母體」後面直接接數字。
#  - 分母：條件機率、softmax 詳解大量使用「分母則…」「分母：」。改為只抓計數意義：
#    「分母」後 4 字內接數字再接題／份／卷／筆／章。
#  - 待補：mid-s1c5 講義有「尚待補強」。改為 `待補(?!強)`。
#  - codex：conceptGraph 的題目 id 帶 `_codex100` 後綴，用 \b 已不會命中（底線是 \w）。
#  - 其餘詞目前無正文命中，維持原樣（英文 eyebrow 用 \b 且不分大小寫，因為 CSS uppercase
#    會讓 innerText 變成 MOCK EXAM）。
BANNED_COPY: list[tuple[str, re.Pattern[str]]] = [
    ('章節內部 id', re.compile(r'\b(mid-)?s\d(c\d+|pdf-c\d+)\b')),
    ('考卷內部 id', re.compile(r'\b(jr|mid)_\d{4}_s\d')),
    ('route', re.compile(r'\broute\b', re.I)),
    ('hash anchor', re.compile(r'hash anchor', re.I)),
    ('asset_id', re.compile(r'asset_id')),
    ('sidecar', re.compile(r'\bsidecar\b', re.I)),
    ('pipeline', re.compile(r'(?<![A-Za-z] )(?<![.\w])pipeline\b')),
    ('codex', re.compile(r'\bcodex\b', re.I)),
    ('已入庫', re.compile('已入庫')),
    ('待補', re.compile('待補(?!強)')),
    ('策展', re.compile('策展')),
    ('分母', re.compile(r'分母\D{0,4}\d+\s*(?:題|份|卷|筆|章)')),
    ('母體', re.compile(r'(?:題目?|考題|試題|題庫)母體|母體\s*\d')),
    ('已審', re.compile('已審')),
    ('檢索片段', re.compile('檢索片段')),
    ('快照 hash', re.compile(r'快照\s*hash', re.I)),
    ('Mock exam', re.compile(r'\bMock exam\b', re.I)),
    ('Learning articles', re.compile(r'\bLearning articles\b', re.I)),
    ('Concept cards', re.compile(r'\bConcept cards\b', re.I)),
    ('PDF assets', re.compile(r'\bPDF assets\b', re.I)),
    ('START HERE', re.compile(r'\bSTART HERE\b', re.I)),
]


def banned_hits(text: str) -> list[tuple[str, str]]:
    hits = []
    for name, pattern in BANNED_COPY:
        for m in pattern.finditer(text):
            lo, hi = max(0, m.start() - 14), min(len(text), m.end() + 14)
            snippet = text[lo:hi].replace('\n', '⏎')
            hits.append((name, snippet))
    return hits


# ---------------------------------------------------------------- 量測 JS

METRICS_JS = r"""
({minFont, minTarget, mobile}) => {
  const de = document.documentElement;
  const vw = de.clientWidth;
  const main = document.querySelector('main');
  const inHiddenTree = (el) => !!el.closest('[inert],[aria-hidden="true"]');
  const laidOut = (el, r, cs) => r.width > 1 && r.height > 1 && cs.visibility !== 'hidden'
      && cs.display !== 'none' && r.right > 0 && r.left < vw && r.bottom > 0;

  // ---- overflow
  const overflow = {
    doc: [de.scrollWidth, de.clientWidth],
    main: main ? [main.scrollWidth, main.clientWidth] : null,
    culprits: [],
  };
  if (de.scrollWidth > de.clientWidth + 1 || (main && main.scrollWidth > main.clientWidth + 1)) {
    const limit = main ? main.getBoundingClientRect().right : vw;
    for (const el of document.querySelectorAll('body *')) {
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.right <= limit + 1) continue;
      const cs = getComputedStyle(el);
      if (cs.position === 'fixed') continue;
      // 只回報最外層的元凶（父層沒有溢出的那個）
      const p = el.parentElement;
      if (p && p.getBoundingClientRect().right > limit + 1) continue;
      overflow.culprits.push(`${el.tagName.toLowerCase()}.${(el.className?.toString?.() || '').slice(0, 70)} right=${Math.round(r.right)}`);
      if (overflow.culprits.length >= 4) break;
    }
  }

  // ---- h1
  const h1s = [...document.querySelectorAll('h1')].filter(h => h.getClientRects().length > 0)
      .map(h => h.innerText.trim().slice(0, 30));

  // ---- tiny text
  const tiny = [];
  let tinyCount = 0;
  for (const el of document.querySelectorAll('body *')) {
    if (!['SCRIPT', 'STYLE', 'NOSCRIPT'].includes(el.tagName)
        && [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) {
      const cs = getComputedStyle(el);
      const fs = parseFloat(cs.fontSize);
      if (fs >= minFont) continue;
      const r = el.getBoundingClientRect();
      if (r.width <= 1 || r.height <= 1 || cs.visibility === 'hidden' || inHiddenTree(el)) continue;
      if (el.closest('svg')) continue;  // 圖表標籤另案處理，不算 UI 文字
      tinyCount++;
      if (tiny.length < 5) tiny.push(`${fs}px「${el.textContent.trim().slice(0, 16)}」`);
    }
  }

  // ---- touch targets（只在手機量）
  const small = [];
  let smallCount = 0;
  if (mobile) {
    const BLOCKS = 'p,li,td,th,dd,dt,blockquote,figcaption';
    for (const el of document.querySelectorAll('a,button,input,select,[role=button],[role=tab]')) {
      let target = el;
      if (el.tagName === 'INPUT' && ['checkbox', 'radio'].includes(el.type)) {
        target = el.closest('label') || el;
      }
      if (el.tagName === 'INPUT' && el.type === 'hidden') continue;
      const cs = getComputedStyle(target);
      const r = target.getBoundingClientRect();
      if (!laidOut(target, r, cs) || inHiddenTree(target)) continue;
      if (r.width >= minTarget && r.height >= minTarget) continue;
      if (el.tagName === 'A' && cs.display === 'inline') {
        const block = el.parentElement && el.parentElement.closest(BLOCKS);
        if (block && block.innerText.trim().length > el.innerText.trim().length) continue;
      }
      smallCount++;
      if (small.length < 5) {
        const label = (el.innerText || el.getAttribute('aria-label') || el.value || '').trim().slice(0, 14);
        small.push(`${el.tagName.toLowerCase()} ${Math.round(r.width)}×${Math.round(r.height)}「${label}」`);
      }
    }
  }
  return { overflow, h1s, tinyCount, tiny, smallCount, small };
}
"""


def settle_text(page, quiet_ms=400, timeout_ms=45000) -> str:
    """與 test_routes.settle_text 同一判準：沒有 skeleton／「載入中」且長度連續兩次相同。"""
    last, stable, waited = -1, 0, 0
    while waited < timeout_ms:
        text = page.inner_text('body')
        n = len(text.strip())
        loading = '載入中' in text or page.locator('[aria-hidden="true"].animate-pulse').count() > 0
        stable = stable + quiet_ms if (n == last and not loading) else 0
        last = n
        if stable >= quiet_ms and n > 0:
            return text
        page.wait_for_timeout(quiet_ms)
        waited += quiet_ms
    return page.inner_text('body')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--only', help='只跑 label 或 route 含這個字串的路由')
    parser.add_argument('--phase1', action='store_true', help='PENDING 檢查也視為失敗')
    args = parser.parse_args()
    enforce_phase1 = ENFORCE_PHASE1 or args.phase1

    require_playwright()
    from playwright.sync_api import sync_playwright

    drift = route_drift()
    routes = [r for r in ROUTES if not args.only or args.only in r[0] or args.only in r[1]]

    failures: list[str] = []
    pending: dict[str, dict[str, tuple[int, int, int]]] = {}
    started = time.monotonic()
    server_gone = False

    with dev_server(port=PORT) as base, sync_playwright() as pw:
        browser = pw.chromium.launch()
        for vp_name, ctx_opts in VIEWPORTS:
            print(f'\n=== {vp_name} {ctx_opts["viewport"]["width"]}×{ctx_opts["viewport"]["height"]} ===')
            ctx = browser.new_context(**ctx_opts)
            mobile = vp_name == 'mobile'
            for label, route in routes:
                page = ctx.new_page()
                errors: list[str] = []
                page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
                page.on('pageerror', lambda e: errors.append(f'pageerror: {e}'))
                notes: list[str] = []
                try:
                    page.goto(f'{base}/#{route}', wait_until='networkidle', timeout=45000)
                    text = settle_text(page)
                    m = page.evaluate(METRICS_JS, {'minFont': MIN_FONT_PX,
                                                   'minTarget': MIN_TARGET_PX, 'mobile': mobile})
                except Exception as exc:  # noqa: BLE001
                    failures.append(f'{label}@{vp_name}')
                    print(f'  ✗ {label:<30} 例外：{type(exc).__name__}: {str(exc)[:90]}')
                    page.close()
                    if 'ERR_CONNECTION_REFUSED' in str(exc):
                        print('  ✗ dev server 已經不在了，中止（其餘頁面未驗）')
                        server_gone = True
                        break
                    continue

                # (a) overflow
                dsw, dcw = m['overflow']['doc']
                if dsw > dcw + 1:
                    notes.append(f'document 水平溢出 {dsw}>{dcw}')
                if m['overflow']['main']:
                    msw, mcw = m['overflow']['main']
                    if msw > mcw + 1:
                        notes.append(f'<main> 水平溢出 {msw}>{mcw}')
                if notes and m['overflow']['culprits']:
                    notes.append('元凶：' + ' | '.join(m['overflow']['culprits']))
                # (b) console
                real_errors = [e for e in errors if 'favicon' not in e.lower()]
                for e in real_errors[:3]:
                    notes.append(f'console: {e[:120]}')
                # (c) copy
                for name, snippet in banned_hits(text):
                    notes.append(f'禁用文案〔{name}〕…{snippet}…')

                h1 = len(m['h1s'])
                pending[label] = pending.get(label, {})
                pending[label][vp_name] = (h1, m['tinyCount'], m['smallCount'])
                warn = []
                if h1 != 1:
                    warn.append(f'h1×{h1}')
                if m['tinyCount']:
                    warn.append(f'<{MIN_FONT_PX}px×{m["tinyCount"]} ' + ' '.join(m['tiny'][:2]))
                if m['smallCount']:
                    warn.append(f'<{MIN_TARGET_PX}px 目標×{m["smallCount"]} ' + ' '.join(m['small'][:2]))

                ok = not notes and (not enforce_phase1 or not warn)
                if not ok:
                    failures.append(f'{label}@{vp_name}')
                print(f'  {"✓" if ok else "✗"} {label:<30}')
                for n in notes:
                    print(f'      ✗ {n}')
                if warn:
                    print(f'      {"✗" if enforce_phase1 else "⚠"} ' + '；'.join(warn))
                page.close()
            ctx.close()
            if server_gone:
                break
        browser.close()

    print('\n=== PENDING 計數（h1 數 / <12px 文字節點 / 手機 <44px 互動元素）===')
    print(f'  {"route":<30} {"desktop h1/tiny":>16} {"mobile h1/tiny/target":>22}')
    for label, _ in routes:
        d = pending.get(label, {}).get('desktop')
        mo = pending.get(label, {}).get('mobile')
        ds = f'{d[0]}/{d[1]}' if d else '-'
        ms = f'{mo[0]}/{mo[1]}/{mo[2]}' if mo else '-'
        print(f'  {label:<30} {ds:>16} {ms:>22}')

    print('\n' + '=' * 60)
    if drift:
        print('✗ test_routes.py 有這裡沒鏡像的路由：' + '、'.join(drift))
    elapsed = time.monotonic() - started
    total = len(routes) * len(VIEWPORTS)
    if failures or drift or server_gone:
        print(f'✗ {len(failures)}/{total} 個頁面×寬度未通過（{elapsed:.0f}s）：' + '、'.join(failures))
        return 1
    print(f'✓ {total} 個頁面×寬度通過 ENFORCED 檢查（{elapsed:.0f}s）'
          + ('' if enforce_phase1 else '；PENDING 只列計數'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
