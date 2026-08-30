"""全路由煙霧測試：每一頁都要有內容、沒有 console error、沒有白畫面。

涵蓋這次改動到的：StatePanel 置換（PracticePage / ExamPage）、
補上的 .catch（TopicHeatPanel / GuideSearchDialog / QuestionModal / GuidePage / VisualCardsPage）、
以及 referenceAnswerLoaders / articleLoaders 的快取重寫。
另外驗證未知路由與無效科目會顯示明確的找不到狀態，不會默默回退到第一科。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from devserver import dev_server, require_playwright  # noqa: E402

require_playwright()
from playwright.sync_api import sync_playwright  # noqa: E402


CATALOG_EXAM_ROUTES = [
    (f'考卷 {exam["routeKey"]}', f'/exam/{exam["routeKey"]}')
    for exam in json.loads(
        (ROOT / 'data/resource_catalog.json').read_text(encoding='utf-8')
    )['exams']
]

ROUTES = [
    ('首頁', '/'),
    ('科目總覽 s1', '/subject/s1'),
    ('科目總覽 mid-s1', '/subject/mid-s1'),
    ('學習指引 s1c1（有 notebook）', '/guide/s1/s1c1'),
    ('學習指引 s1pdf-c3（無 notebook）', '/guide/s1/s1pdf-c3'),
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
]

EXPECTED_NOT_FOUND_ROUTES = [
    ('未知路由', '/definitely-not-a-real-route', '找不到頁面'),
    ('無效科目', '/subject/not-a-real-subject', '找不到科目'),
    ('無效考卷', '/exam/not-a-real-exam', '找不到考試'),
]

fails = []

def settle_text(page, quiet_ms=500, timeout_ms=45000):
    """等頁面真的載完再取樣。

    兩個判準要一起用，缺一不可：

    1. **畫面上沒有載入態**。路由 lazy import 期間是 App 的
       `PageSkeleton` (`[aria-hidden].animate-pulse`)；頁面內非同步資料則用
       `StatePanel tone="loading"`，文案含「載入中」。兩種都要排除。
    2. 內容長度連續兩次取樣相同。

    只用 (2) 會被騙：外殼先畫出來（約 282 字）之後，動態 import 章節 JSON
    的那幾秒內長度完全不動，看起來就像「穩定了」。冷啟動的 vite dev server 上
    那個 transform 要好幾秒，實測會讓 GuidePage 停在 282 字被誤判成白畫面。
    """
    last, stable, waited = -1, 0, 0
    while waited < timeout_ms:
        text = page.inner_text('body')
        n = len(text.strip())
        route_skeleton = page.locator('[aria-hidden="true"].animate-pulse').count() > 0
        loading = '載入中' in text or route_skeleton
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

    for label, route, expected in EXPECTED_NOT_FOUND_ROUTES:
        page = browser.new_page(viewport={'width': 1280, 'height': 900})
        errors = []
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        page.on('pageerror', lambda e: errors.append(f'pageerror: {e}'))
        try:
            page.goto(f'{BASE}/#{route}', wait_until='networkidle', timeout=45000)
            text = settle_text(page)
            real_errors = [e for e in errors if 'favicon' not in e.lower()]
            ok = expected in text and not real_errors
            note = []
            if expected not in text:
                note.append(f'缺少「{expected}」')
            if real_errors:
                note.append(f'console: {real_errors[0][:90]}')
            print(f'  {"✓" if ok else "✗"} {label:<34} 預期錯誤狀態  {"; ".join(note)}')
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
    total_routes = len(ROUTES) + len(EXPECTED_NOT_FOUND_ROUTES)
    print(f'✗ {len(fails)}/{total_routes} 條路由有問題：' + '、'.join(fails))
    sys.exit(1)
print(f'✓ {len(ROUTES)} 條正常路由＋{len(EXPECTED_NOT_FOUND_ROUTES)} 條錯誤路由全部正常')
