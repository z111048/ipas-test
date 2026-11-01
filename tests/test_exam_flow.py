"""考試流程端對端煙霧測試。

驗兩件事：

1. **作答的 key 對不對題**（第 2-6 節）。作答紀錄從陣列索引改成 question id 之後，
   勾選狀態是否還精確對應到該題——不串到別題、不被覆寫、計分不錯位。
   計分那條會用題庫算出的**預期分數**去比對成績頁；只檢查「有出現數字」驗不到錯位。

2. **切題後立刻作答，答案要落在目標題**（第 8 節）。這是一個真的踩過的錯答：
   程式觸發平滑捲動時，IntersectionObserver 會在動畫途中改掉 activeIndex。
   短距離與長距離都要測——理由見 tests/README.md 的坑 2，那裡記了一個
   「短距離全綠但其實是壞的」修法是怎麼被長距離抓出來的。

3. **交卷後回到頁首**（第 6 節）。真正的捲動容器是 App.tsx 的 <main>，
   window.scrollTo 沒有作用；成績頁要從頂端開始、焦點落在成績標題。

4. **作答中的進度不會掉**（第 10 節）。重新整理、站內導覽離開再回來都能續答，
   重新開始與交卷會清掉；作答中重新整理要跳 beforeunload 確認。

5. **一次點擊只作答一次**（第 11 節）。label onClick 與 radio onChange 曾經各觸發一次。

選項是 ui/ChoiceOption（<label> 包 sr-only radio）：作答一律點 label（使用者實際點到的元素），
只有第 11 節的「點 radio」直接對 input 派送 click。
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
    page.locator('label:has(input[name="q0"][value="C"])').first.click()
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
    page.locator('label:has(input[name="q1"][value="D"])').first.click()
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
    # 當前題吃 isActive 樣式（ring-accent）、其餘已答的是 answered 藍色（bg-answered-soft），
    # 兩種都要算。注意 unanswered 的 class 也含 "answered" 子字串，所以要比對完整 token。
    marked = page.evaluate('''() => {
        const grid = [...document.querySelectorAll('div.grid')]
            .find(g => g.querySelectorAll('button').length >= 40)
        if (!grid) return null
        return [...grid.querySelectorAll('button')].map((b, i) => ({ n: i + 1, c: b.className }))
            .filter(x => x.c.split(/\s+/).includes('bg-answered-soft') || x.c.includes('ring-accent'))
            .map(x => x.n)
    }''')
    check('題號盤標記的正是第 1、2 題', marked == [1, 2], f'標記={marked}')
    page.click('button:has-text("題號盤")')
    page.wait_for_timeout(300)

    print(f'\n=== 6. 交卷與計分（Q1=A 正解{CORRECT_Q1}、Q2=D 正解{CORRECT_Q2} → 2 對 = 4 分）===')
    page.click('button:has-text("繳卷交答案")')
    page.wait_for_timeout(500)
    MAIN_SCROLL_TOP = "() => document.getElementById('main-content').scrollTop"
    before_submit_top = page.evaluate(MAIN_SCROLL_TOP)
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
    page.wait_for_timeout(300)
    after_submit_top = page.evaluate(MAIN_SCROLL_TOP)
    check('交卷前 main 確實已往下捲（這條測試有意義）', before_submit_top > 500, f'{before_submit_top}px')
    check('成績頁 main 捲回頂端', after_submit_top <= 2, f'{after_submit_top}px')
    focus_id = page.evaluate('() => document.activeElement && document.activeElement.id')
    check('焦點移到成績標題', focus_id == 'exam-score-heading', str(focus_id))
    heading_box = page.locator('#exam-score-heading').bounding_box()
    check('成績標題在畫面內', bool(heading_box) and 0 <= heading_box['y'] < 900, str(heading_box))

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

    print('\n=== 9. 計時器以絕對截止時間校正背景分頁漂移 ===')
    timer_pg = browser.new_page(viewport={'width': 1280, 'height': 900})
    timer_pg.add_init_script('''(() => {
        let now = Date.now()
        Date.now = () => now
        window.__ipasAdvanceClock = (milliseconds) => { now += milliseconds }
    })()''')
    timer_pg.goto(f'{BASE}/#/exam/{EXAM}', wait_until='networkidle')
    timer_pg.wait_for_selector('text=開始考試', timeout=20000)
    timer_pg.click('text=開始考試')
    timer_pg.wait_for_selector('div.text-xl.tabular-nums', timeout=20000)
    initial_timer = timer_pg.locator('div.text-xl.tabular-nums').inner_text()
    check('初始倒數 = 90:00', initial_timer == '90:00', initial_timer)

    timer_pg.evaluate('''() => {
        window.__ipasAdvanceClock(5000)
        document.dispatchEvent(new Event('visibilitychange'))
    }''')
    timer_pg.wait_for_function(
        "() => document.querySelector('div.text-xl.tabular-nums')?.textContent === '89:55'",
        timeout=5000,
    )
    corrected_timer = timer_pg.locator('div.text-xl.tabular-nums').inner_text()
    check('回到前景時一次補正 5 秒', corrected_timer == '89:55', corrected_timer)

    timer_pg.evaluate('''() => {
        window.__ipasAdvanceClock(89 * 60 * 1000 + 55 * 1000)
        window.dispatchEvent(new Event('focus'))
    }''')
    timer_pg.wait_for_selector('button:has-text("重新考試")', timeout=5000)
    check('截止時間到達後自動交卷', '詳細解析' in timer_pg.inner_text('body'))
    timer_pg.close()

    print('\n=== 10. 作答進度：重新整理、站內導覽後可續答 ===')
    dialogs = []
    pg = fresh_exam()
    pg.on('dialog', lambda d: (dialogs.append(d.type), d.accept()))
    pg.locator('label:has(input[name="q0"][value="B"])').first.click()
    pg.locator('label:has(input[name="q2"][value="C"])').first.click()
    for _ in range(3):
        pg.keyboard.press('ArrowRight')
        pg.wait_for_timeout(150)
    pg.wait_for_timeout(300)
    stored = pg.evaluate(f"() => JSON.parse(localStorage.getItem('ipas:exam:{EXAM}:attempt'))")
    check('作答寫入 localStorage（含版本號）',
          bool(stored) and stored.get('v') == 1
          and stored.get('answers') == {f'{EXAM}_q1': 'B', f'{EXAM}_q3': 'C'},
          str(stored and stored.get('answers')))
    # 點第 3 題時 scroll-spy 會把當前題移到第 3 題附近，再按三次 → ；確切題號以存檔為準，
    # 只要求它確實離開了已作答的第 1、3 題，後面「按 1 落在哪題」才驗得出還原。
    saved_idx = stored.get('currentIndex') if stored else None
    check('目前題號寫入 localStorage（已往後移）', isinstance(saved_idx, int) and saved_idx >= 3,
          str(saved_idx))
    saved_idx = saved_idx if isinstance(saved_idx, int) else 3

    pg.reload(wait_until='networkidle')
    check('作答中重新整理會跳 beforeunload 確認', 'beforeunload' in dialogs, str(dialogs))
    resume_btn = pg.locator('button:has-text("繼續上次作答")')
    resume_btn.wait_for(timeout=20000)
    check('重新整理後 intro 顯示續答選項（已答 2 題）', '已答 2 題' in resume_btn.inner_text(),
          resume_btn.inner_text())
    check('同時提供「重新開始」', pg.locator('button:has-text("重新開始")').count() == 1)
    resume_btn.click()
    pg.wait_for_selector('input[type=radio]', timeout=20000)
    pg.wait_for_timeout(600)
    st = checked_state(pg)
    check('重新整理後作答還原', st == {'q0': 'B', 'q2': 'C'}, str(st))
    pg.keyboard.press('1')
    pg.wait_for_timeout(400)
    st = checked_state(pg)
    check(f'續答回到上次的第 {saved_idx + 1} 題（按 1 → 該題 = A）',
          st == {'q0': 'B', 'q2': 'C', f'q{saved_idx}': 'A'}, str(st))

    pg.evaluate("() => { location.hash = '#/' }")
    pg.wait_for_function("() => !document.querySelector('input[type=radio]')", timeout=10000)
    pg.wait_for_timeout(300)
    pg.evaluate(f"() => {{ location.hash = '#/exam/{EXAM}' }}")
    resume_btn = pg.locator('button:has-text("繼續上次作答")')
    resume_btn.wait_for(timeout=20000)
    check('站內導覽回來後顯示續答（已答 3 題）', '已答 3 題' in resume_btn.inner_text(),
          resume_btn.inner_text())
    resume_btn.click()
    pg.wait_for_selector('input[type=radio]', timeout=20000)
    pg.wait_for_timeout(400)
    st = checked_state(pg)
    check('站內導覽回來後作答還原', st == {'q0': 'B', 'q2': 'C', f'q{saved_idx}': 'A'}, str(st))

    pg.evaluate("() => { location.hash = '#/' }")
    pg.wait_for_function("() => !document.querySelector('input[type=radio]')", timeout=10000)
    pg.evaluate(f"() => {{ location.hash = '#/exam/{EXAM}' }}")
    pg.locator('button:has-text("重新開始")').wait_for(timeout=20000)
    pg.click('button:has-text("重新開始")')
    pg.wait_for_selector('input[type=radio]', timeout=20000)
    pg.wait_for_timeout(300)
    check('重新開始會清掉上次作答', checked_state(pg) == {}, str(checked_state(pg)))
    pg.locator('label:has(input[name="q1"][value="A"])').first.click()
    pg.click('button:has-text("繳卷交答案")')
    pg.click('button:has-text("確認繳卷")')
    pg.wait_for_selector('button:has-text("重新考試")', timeout=20000)
    left = pg.evaluate(f"() => localStorage.getItem('ipas:exam:{EXAM}:attempt')")
    check('交卷後清掉 localStorage 的作答', left is None, str(left)[:80])
    pg.click('button:has-text("重新考試")')
    pg.wait_for_selector('text=開始考試', timeout=20000)
    check('交卷後回 intro 不再提供續答', pg.locator('button:has-text("繼續上次作答")').count() == 0)

    pg.evaluate(f"""() => localStorage.setItem('ipas:exam:{EXAM}:attempt',
        JSON.stringify({{ v: 0, examKey: '{EXAM}', phase: 'active', answers: {{}},
                          currentIndex: 0, secondsRemaining: 100 }}))""")
    pg.reload(wait_until='networkidle')
    pg.wait_for_selector('text=開始考試', timeout=20000)
    check('版本不符的舊資料被忽略', pg.locator('button:has-text("繼續上次作答")').count() == 0)
    pg.close()

    print('\n=== 11. 一次點擊只觸發一次作答 ===')
    # 凍結時鐘，讓倒數不會產生寫入；作答紀錄每變一次就寫一次 localStorage，
    # 所以 setItem 次數 = selectAnswer 次數（每次都產生新的 userAnswers 物件）。
    pg = browser.new_page(viewport={'width': 1280, 'height': 900})
    pg.add_init_script('''(() => {
        const now = Date.now()
        Date.now = () => now
        window.__ipasAttemptWrites = 0
        const orig = Storage.prototype.setItem
        Storage.prototype.setItem = function (key, value) {
            if (String(key).startsWith('ipas:exam:')) window.__ipasAttemptWrites++
            return orig.call(this, key, value)
        }
    })()''')
    pg.goto(f'{BASE}/#/exam/{EXAM}', wait_until='networkidle')
    pg.wait_for_selector('text=開始考試', timeout=20000)
    pg.click('text=開始考試')
    pg.wait_for_selector('input[type=radio]', timeout=20000)
    pg.wait_for_timeout(500)
    for label, locator in (
        # radio 本身是 sr-only（ChoiceOption），座標點擊會落在 label 上；
        # 直接對 input 派送 click 才是「點 radio」這條路徑。
        ('點 radio', pg.locator('input[name="q0"][value="B"]').first),
        ('點選項文字（label）', pg.locator('label:has(input[name="q0"][value="C"])').first),
    ):
        before = pg.evaluate('() => window.__ipasAttemptWrites')
        if label == '點 radio':
            locator.dispatch_event('click')
        else:
            locator.click()
        pg.wait_for_timeout(300)
        after = pg.evaluate('() => window.__ipasAttemptWrites')
        check(f'{label}：恰好一次作答', after - before == 1, f'{after - before} 次')
    st = checked_state(pg)
    check('label 點擊後第 1 題 = C', st == {'q0': 'C'}, str(st))
    pg.locator('input[name="q0"][value="C"]').first.focus()
    before = pg.evaluate('() => window.__ipasAttemptWrites')
    pg.keyboard.press('ArrowDown')
    pg.wait_for_timeout(300)
    after = pg.evaluate('() => window.__ipasAttemptWrites')
    st = checked_state(pg)
    check('方向鍵 ↓ 在選項間移動並作答一次', st == {'q0': 'D'} and after - before == 1,
          f'{st}，{after - before} 次')
    pg.close()

    browser.close()

print('\n' + '=' * 52)
if fails:
    print(f'✗ {len(fails)} 項失敗：' + '、'.join(fails))
    sys.exit(1)
print('✓ 考試流程全部通過')
