"""章節練習的作答路徑端對端測試。

與考試頁是同一類 bug，但這一頁的後果更嚴重，所以單獨守一支：

- `PracticePage.tsx:215` 的 `!answers[q.id]` 讓一題**只能作答一次**，
  所以切題後立刻按數字鍵若答到別題，那個錯答**無法覆寫**；
- `:142-154` 的 effect 會把 answers 整包寫進 localStorage
  （key 形如 `ipas:practice:s1:s1c1:chapter`），錯答會被保存下來，
  下次進來還原回去。

修法與考試頁相同：程式觸發的捲動一律 `behavior: 'instant'`（見 goTo 的註解）。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from devserver import dev_server, require_playwright  # noqa: E402

require_playwright()
from playwright.sync_api import sync_playwright  # noqa: E402

SUBJECT, CHAPTER = 's1', 's1c1'

fails = []


def check(label, cond, detail=''):
    print(f'  {"✓" if cond else "✗"} {label}' + (f'  {detail}' if detail else ''))
    if not cond:
        fails.append(label)


# 練習頁的選項是 <button aria-pressed>（OptionButton.tsx:32-42），不是 radio；
# 題目容器是 <article data-q-index>（QuestionCard.tsx:44-47）。
READY_SELECTOR = 'article[data-q-index] button[aria-pressed]'

PICKED_JS = (
    "() => {"
    "  const out = {};"
    "  for (const art of document.querySelectorAll('article[data-q-index]')) {"
    "    const i = art.getAttribute('data-q-index');"
    "    for (const b of art.querySelectorAll('button[aria-pressed=\"true\"]')) {"
    "      const m = (b.innerText || '').match(/\\(([A-D])\\)/);"
    "      if (m) out['q' + i] = m[1];"
    "    }"
    "  }"
    "  return out;"
    "}"
)


def picked(page):
    """每一題目前選了什麼，例 {'q0': 'A'}。"""
    return page.evaluate(PICKED_JS)


with dev_server() as BASE, sync_playwright() as pw:
    browser = pw.chromium.launch()

    # 所有分頁共用一份錯誤蒐集，且 listener 一律在 goto 之前掛——
    # 掛在 goto 之後只會抓到「載完之後」的錯誤，載入期的完全漏掉。
    errors: list[str] = []

    def fresh():
        pg = browser.new_page(viewport={'width': 1280, 'height': 900})
        pg.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        pg.on('pageerror', lambda e: errors.append(f'pageerror: {e}'))
        # 每次清掉 localStorage，否則上一輪的作答會被還原回來
        pg.add_init_script("try { localStorage.clear() } catch (e) {}")
        pg.goto(f'{BASE}/#/practice/{SUBJECT}/{CHAPTER}', wait_until='networkidle')
        pg.wait_for_selector(READY_SELECTOR, timeout=25000)
        return pg

    print('\n=== 1. 載入 ===')
    page = fresh()
    n = page.locator('article[data-q-index]').count()
    check('題目渲染', n > 0, f'{n} 題')

    print('\n=== 2. 點選作答不串題 ===')
    page.locator('article[data-q-index="0"] button[aria-pressed]').nth(1).click()
    page.wait_for_timeout(300)
    check('第 1 題 = B 且只有它', picked(page) == {'q0': 'B'}, str(picked(page)))
    page.close()

    print('\n=== 3. 迴歸：切題後立刻作答（錯了就無法覆寫，所以更要準）===')
    for delay in (0, 50, 150, 300, 600):
        pg = fresh()
        pg.keyboard.press('ArrowRight')
        pg.wait_for_timeout(delay)
        pg.keyboard.press('3')       # → C
        pg.wait_for_timeout(600)
        st = picked(pg)
        check(f'延遲 {delay:>4}ms：C 落在第 2 題', st == {'q1': 'C'}, str(st))
        pg.close()

    print('\n=== 4. 作答會寫進 localStorage 並在重整後還原 ===')
    pg = browser.new_page(viewport={'width': 1280, 'height': 900})
    pg.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
    pg.on('pageerror', lambda e: errors.append(f'pageerror: {e}'))
    pg.goto(f'{BASE}/#/practice/{SUBJECT}/{CHAPTER}', wait_until='networkidle')
    pg.evaluate("() => { try { localStorage.clear() } catch (e) {} }")
    pg.reload(wait_until='networkidle')
    pg.wait_for_selector(READY_SELECTOR, timeout=25000)
    pg.locator('article[data-q-index="0"] button[aria-pressed]').nth(3).click()
    pg.wait_for_timeout(400)
    stored = pg.evaluate(
        "() => localStorage.getItem('ipas:practice:%s:%s:chapter')" % (SUBJECT, CHAPTER))
    check('答案有寫進 localStorage', bool(stored) and '"D"' in stored, str(stored))
    pg.reload(wait_until='networkidle')
    pg.wait_for_selector(READY_SELECTOR, timeout=25000)
    pg.wait_for_timeout(600)
    check('重整後還原成 D', picked(pg).get('q0') == 'D', str(picked(pg)))
    pg.close()

    print('\n=== 5. Console 錯誤 ===')
    real = [e for e in errors if 'favicon' not in e.lower()]
    check('全部分頁都無 console error / pageerror', not real,
          f'{len(real)} 筆' + (f'：{real[:2]}' if real else ''))

    browser.close()

print('\n' + '=' * 52)
if fails:
    print(f'✗ {len(fails)} 項失敗：' + '、'.join(fails))
    sys.exit(1)
print('✓ 章節練習流程全部通過')
