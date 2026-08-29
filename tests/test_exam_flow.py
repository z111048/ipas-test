"""考試流程端對端煙霧測試。

驗兩件事：

1. **作答的 key 對不對題**（第 2-6 節）。作答紀錄從陣列索引改成 question id 之後，
   勾選狀態是否還精確對應到該題——不串到別題、不被覆寫、計分不錯位。
   計分那條會用題庫算出的**預期分數**去比對成績頁；只檢查「有出現數字」驗不到錯位。

2. **切題後立刻作答，答案要落在目標題**（第 8 節）。這是一個真的踩過的錯答：
   程式觸發平滑捲動時，IntersectionObserver 會在動畫途中改掉 activeIndex。
   短距離與長距離都要測——理由見 tests/README.md 的坑 2，那裡記了一個
   「短距離全綠但其實是壞的」修法是怎麼被長距離抓出來的。
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from devserver import dev_server, require_playwright  # noqa: E402

require_playwright()
from playwright.sync_api import sync_playwright  # noqa: E402

EXAM = 'jr_1152_s1'
# 由 data/初級/questions/mock_jr_1152_s1.json 查得
CORRECT_Q1, CORRECT_Q2 = 'A', 'D'

fails = []


def check(label, cond, detail=''):
    print(f'  {"✓" if cond else "✗"} {label}' + (f'  {detail}' if detail else ''))
    if not cond:
        fails.append(label)


def checked_state(page):
    """目前每一題被勾選的選項，例 {'q0': 'A', 'q1': 'D'}。"""
    return page.evaluate('''() => {
        const out = {}
        for (const i of document.querySelectorAll('input[type=radio]'))
            if (i.checked) out[i.name] = i.value
        return out
    }''')


with dev_server() as BASE, sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width': 1280, 'height': 900})
    console_errors = []
    page.on('console', lambda m: console_errors.append(m.text) if m.type == 'error' else None)
    page.on('pageerror', lambda e: console_errors.append(f'pageerror: {e}'))

    print(f'\n=== 1. 載入考卷 #{EXAM} ===')
    page.goto(f'{BASE}/#/exam/{EXAM}', wait_until='networkidle')
    page.wait_for_selector('text=開始考試', timeout=20000)
    page.click('text=開始考試')
    page.wait_for_selector('input[type=radio]', timeout=20000)
    n_q = page.locator('input[type=radio]').count() // 4
    check('進入作答、選項渲染', n_q == 50, f'{n_q} 題')

    print('\n=== 2. 點選作答：第 1 題選 C ===')
    page.locator('input[name="q0"][value="C"]').first.click()
    page.wait_for_timeout(250)
    check('第 1 題 = C', checked_state(page).get('q0') == 'C')
    check('沒有連帶勾到別題', list(checked_state(page)) == ['q0'], str(checked_state(page)))

    print('\n=== 3. 鍵盤作答：在第 1 題按 1 → 覆寫成 A ===')
    page.keyboard.press('1')
    page.wait_for_timeout(300)
    state = checked_state(page)
    check('第 1 題被覆寫成 A（鍵盤走同一個 id）', state.get('q0') == 'A', str(state))
    check('覆寫沒有波及別題', list(state) == ['q0'], str(state))

    print('\n=== 4. 點選作答：第 2 題選 D ===')
    page.locator('input[name="q1"][value="D"]').first.click()
    page.wait_for_timeout(250)
    state = checked_state(page)
    check('第 2 題 = D', state.get('q1') == 'D')
    check('第 1 題仍是 A', state.get('q0') == 'A')
    check('恰好兩題有作答', sorted(state) == ['q0', 'q1'], str(state))

    print('\n=== 5. 題號盤 ===')
    page.click('button:has-text("題號盤")')
    page.wait_for_timeout(400)
    body = page.inner_text('body')
    found = re.search(r'(未答 \d+ 題|全部已答)', body)
    check('未答數 = 48', '未答 48 題' in body, found.group(0) if found else '（找不到未答字樣）')
    # 當前題吃 isActive 樣式、其餘已答的才是 success 綠色，所以兩種都要算
    marked = page.evaluate('''() => {
        const grid = [...document.querySelectorAll('div.grid')]
            .find(g => g.querySelectorAll('button').length >= 40)
        if (!grid) return null
        return [...grid.querySelectorAll('button')].map((b, i) => ({ n: i + 1, c: b.className }))
            .filter(x => x.c.includes('success') || x.c.includes('ring-accent'))
            .map(x => x.n)
    }''')
    check('題號盤標記的正是第 1、2 題', marked == [1, 2], f'標記={marked}')
    page.click('button:has-text("題號盤")')
    page.wait_for_timeout(300)

    print(f'\n=== 6. 交卷與計分（Q1=A 正解{CORRECT_Q1}、Q2=D 正解{CORRECT_Q2} → 2 對 = 4 分）===')
    page.click('button:has-text("繳卷交答案")')
    page.wait_for_timeout(500)
    page.click('button:has-text("確認繳卷")')
    # 等成績頁真的出現再取樣，不要用固定 sleep（見 tests/README.md 的坑 1）。
    # 判準用「重新考試」這個成績頁專屬按鈕，不要用 /\d+\s*分/——
    # 作答頁的計時器有 sr-only 的「剩餘 90 分鐘。」，那個正則在交卷前就恆真，
    # 等於這個 wait 完全沒有作用。
    page.wait_for_selector('button:has-text("重新考試")', timeout=20000)
    result = page.inner_text('body')
    score = re.search(r'(\d+)\s*分', result)
    check('分數 = 4（id-keyed 計分正確）', bool(score) and int(score.group(1)) == 4,
          f'{score.group(1) if score else "?"} 分')
    check('沒有 NaN / undefined', 'NaN' not in result and 'undefined' not in result)

    print('\n=== 7. Console 錯誤 ===')
    real = [e for e in console_errors if 'favicon' not in e.lower()]
    check('無 console error / pageerror', not real,
          f'{len(real)} 筆' + (f'：{real[:2]}' if real else ''))

    print('\n=== 8. 迴歸：切題後立刻作答，答案必須落在目標題 ===')
    # 這個 bug 的本質：平滑捲動的動畫途中，IntersectionObserver 會把 activeIndex
    # 改成畫面上當下經過的題，於是「切題 → 立刻按數字鍵」會答錯題。
    #
    # 兩種距離都要測，缺一不可：
    #   短距離（方向鍵，約一個題高）——原始 bug 的窗口在 ~150ms
    #   長距離（題號盤跳到第 45 題）——Chrome 的平滑捲動時長隨距離增加（實測上限
    #     約 1534ms），任何「捲動期間上鎖 + 固定 timeout」的修法都會在這裡提早解鎖，
    #     錯答窗口搬到 ~1050-1250ms。只測短距離會讓那種壞修法看起來是好的。
    #
    # 現行修法是程式觸發的捲動一律 instant：沒有動畫就沒有中間位置，
    # observer 拿到的第一批 entry 就是最終位置，所以以下所有延遲都應該正確。

    def fresh_exam():
        pg = browser.new_page(viewport={'width': 1280, 'height': 900})
        pg.goto(f'{BASE}/#/exam/{EXAM}', wait_until='networkidle')
        pg.wait_for_selector('text=開始考試', timeout=20000)
        pg.click('text=開始考試')
        pg.wait_for_selector('input[type=radio]', timeout=20000)
        return pg

    PALETTE_CLICK = (
        "() => {"
        "  const grid = [...document.querySelectorAll('div.grid')]"
        "    .find(g => g.querySelectorAll('button').length >= 40);"
        "  grid.querySelectorAll('button')[44].click();"
        "}"
    )
    SCROLL_TO_Q10 = (
        "() => {"
        "  const nodes = document.querySelectorAll('[data-q-index]');"
        "  nodes[9].scrollIntoView({ behavior: 'instant', block: 'center' });"
        "}"
    )

    print('  -- 短距離：ArrowRight --')
    for delay in (0, 50, 150, 300, 600):
        pg = fresh_exam()
        pg.keyboard.press('ArrowRight')
        pg.wait_for_timeout(delay)
        pg.keyboard.press('2')       # → B
        pg.wait_for_timeout(600)
        st = checked_state(pg)
        check(f'延遲 {delay:>4}ms：B 落在第 2 題', st == {'q1': 'B'}, str(st))
        pg.close()

    print('  -- 長距離：題號盤跳到第 45 題 --')
    for delay in (0, 150, 900, 1100, 1300):
        pg = fresh_exam()
        pg.click('button:has-text("題號盤")')
        pg.wait_for_timeout(300)
        pg.evaluate(PALETTE_CLICK)
        pg.wait_for_timeout(delay)
        pg.keyboard.press('3')       # → C
        pg.wait_for_timeout(800)
        st = checked_state(pg)
        check(f'延遲 {delay:>4}ms：C 落在第 45 題', st == {'q44': 'C'}, str(st))
        pg.close()

    print('  -- 反向：使用者自己捲動時 scroll-spy 仍要跟隨 --')
    # 修法把鎖整個拿掉了，所以 scroll-spy 應該完全正常。若哪天有人再加回「捲動期間
    # 鎖住 scroll-spy」那種修法，這條會抓到「使用者滑到別題、卻答到畫面外那題」的退化。
    pg = fresh_exam()
    pg.evaluate(SCROLL_TO_Q10)
    pg.wait_for_timeout(900)
    pg.keyboard.press('4')           # → D
    pg.wait_for_timeout(600)
    st = checked_state(pg)
    check('手動捲到第 10 題後按鍵，答案落在第 10 題', st == {'q9': 'D'}, str(st))
    pg.close()

    browser.close()

print('\n' + '=' * 52)
if fails:
    print(f'✗ {len(fails)} 項失敗：' + '、'.join(fails))
    sys.exit(1)
print('✓ 考試流程全部通過')
