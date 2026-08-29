"""全路由煙霧測試：每一頁都要有內容、沒有 console error、沒有白畫面。

涵蓋這次改動到的：StatePanel 置換（PracticePage / ExamPage）、
補上的 .catch（TopicHeatPanel / GuideSearchDialog / QuestionModal / GuidePage / VisualCardsPage）、
以及 referenceAnswerLoaders / articleLoaders 的快取重寫。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from devserver import dev_server, require_playwright  # noqa: E402

require_playwright()
from playwright.sync_api import sync_playwright  # noqa: E402


ROUTES = [
    ('首頁', '/'),
    ('科目總覽 s1', '/subject/s1'),
    ('科目總覽 mid-s1', '/subject/mid-s1'),
    ('學習指引 s1c1（有 notebook）', '/guide/s1/s1c1'),
    ('學習指引 s1pdf-c3（無 notebook）', '/guide/s1/s1pdf-c3'),
    ('學習指引 mid-s2c6', '/guide/mid-s2/mid-s2c6'),
    ('章節練習 s1c1', '/practice/s1/s1c1'),
    ('指引練習 s1c1', '/practice/s1/s1c1/guide'),
    ('考卷 jr_1152_s1', '/exam/jr_1152_s1'),
    ('考卷 mid_1141_s3（legacy 題號）', '/exam/mid_1141_s3'),
    ('學習文章列表', '/articles'),
    ('概念圖卡', '/visuals'),
    ('圖庫', '/images'),
    ('名詞解釋', '/glossary'),
    ('完整目錄', '/outline'),
    ('心智圖', '/mindmap'),
    ('概念索引', '/concepts'),
]

fails = []

def settle_text(page, quiet_ms=500, timeout_ms=45000):
    """等頁面真的載完再取樣。

    兩個判準要一起用，缺一不可：

    1. **畫面上沒有「載入中」**。這是正向訊號——全站載入態都用
       `StatePanel tone="loading"`，文案一律含「載入中」
       （GuidePage:867「載入學習指引內容中...」、PracticePage「題目載入中...」…）。
    2. 內容長度連續兩次取樣相同。

    只用 (2) 會被騙：外殼先畫出來（約 282 字）之後，動態 import 章節 JSON
    的那幾秒內長度完全不動，看起來就像「穩定了」。冷啟動的 vite dev server 上
    那個 transform 要好幾秒，實測會讓 GuidePage 停在 282 字被誤判成白畫面。
    """
    last, stable, waited = -1, 0, 0
    while waited < timeout_ms:
        text = page.inner_text('body')
        n = len(text.strip())
        loading = '載入中' in text
        stable = stable + quiet_ms if (n == last and not loading) else 0
        last = n
        if stable >= quiet_ms and n > 0:
            return text
        page.wait_for_timeout(quiet_ms)
        waited += quiet_ms
    return page.inner_text('body')


with dev_server() as BASE, sync_playwright() as pw:
    browser = pw.chromium.launch()
    for label, route in ROUTES:
        page = browser.new_page(viewport={'width': 1280, 'height': 900})
        errors = []
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        page.on('pageerror', lambda e: errors.append(f'pageerror: {e}'))
        try:
            page.goto(f'{BASE}/#{route}', wait_until='networkidle', timeout=45000)
            text = settle_text(page)
            real_errors = [e for e in errors if 'favicon' not in e.lower()]
            # 白畫面判準：主內容區實質沒有東西（扣掉固定的側欄/頁首約 400 字）
            too_empty = len(text.strip()) < 400
            broken = ('載入失敗' in text or 'NaN' in text
                      or 'undefined' in text or '找不到' in text)
            ok = not real_errors and not too_empty and not broken
            note = []
            if real_errors:
                note.append(f'console: {real_errors[0][:90]}')
            if too_empty:
                note.append(f'內容僅 {len(text.strip())} 字')
            if broken:
                for w in ('載入失敗', 'NaN', 'undefined', '找不到'):
                    if w in text:
                        note.append(f'頁面出現「{w}」')
                        break
            print(f'  {"✓" if ok else "✗"} {label:<34} {len(text.strip()):>6} 字  {"; ".join(note)}')
            if not ok:
                fails.append(label)
        except Exception as exc:
            print(f'  ✗ {label:<34} 例外：{type(exc).__name__}: {str(exc)[:80]}')
            fails.append(label)
        finally:
            page.close()
    browser.close()

print('\n' + '=' * 60)
if fails:
    print(f'✗ {len(fails)}/{len(ROUTES)} 條路由有問題：' + '、'.join(fails))
    sys.exit(1)
print(f'✓ {len(ROUTES)} 條路由全部正常')
