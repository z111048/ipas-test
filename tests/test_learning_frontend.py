#!/usr/bin/env python3
"""真實 preview 的學習閱讀、診斷、回補、Lab 與 mobile 流程。"""

from __future__ import annotations

import json
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from devserver import dev_server, require_playwright  # noqa: E402

require_playwright()
from playwright.sync_api import sync_playwright  # noqa: E402


def check(label: str, condition: bool, detail: str = "") -> None:
    print(f'  {"✓" if condition else "✗"} {label}' + (f"  {detail}" if detail else ""))
    if not condition:
        FAILS.append(label)


def build_preview() -> tuple[dict, Path]:
    result = subprocess.run(
        [sys.executable, "scripts/build_learning_content.py", "--preview"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if result.returncode:
        raise RuntimeError((result.stdout + result.stderr)[-4000:])
    pointer = json.loads((ROOT / "frontend/src/generated/learning/preview.json").read_text())
    base = ROOT / "frontend/src/generated/learning" / Path(pointer["manifestPath"]).parent
    return pointer, base


FAILS: list[str] = []
POINTER, RELEASE = build_preview()
INDEX = json.loads((RELEASE / "index.json").read_text())
BLUEPRINT_ID = INDEX["blueprints"][0]["id"]
LAB_ID = INDEX["labs"][0]["id"]
ASSEMBLY_WRAPPER = json.loads((RELEASE / INDEX["assemblies"][0]["path"]).read_text())
ASSEMBLY = ASSEMBLY_WRAPPER["document"]
QUESTIONS = {
    ref["questionKey"]: json.loads((RELEASE / ASSEMBLY_WRAPPER["questionPaths"][ref["questionKey"]]).read_text())
    for ref in ASSEMBLY["selectedQuestionRevisions"]
}
DISPLAY = {
    row["question"]["questionKey"]: row["optionIds"]
    for row in ASSEMBLY["displayedOptionIds"]
}


def saved_answer_count(page) -> int:
    return page.evaluate("""async () => {
      const db = await new Promise((resolve, reject) => {
        const request = indexedDB.open('ipas-learning-v1', 1)
        request.onsuccess = () => resolve(request.result)
        request.onerror = () => reject(request.error)
      })
      const rows = await new Promise((resolve, reject) => {
        const request = db.transaction('attempts').objectStore('attempts').getAll()
        request.onsuccess = () => resolve(request.result)
        request.onerror = () => reject(request.error)
      })
      return rows[0]?.snapshot.items.filter((item) => item.selectedOptionId).length ?? 0
    }""")


with dev_server(port=5207) as base, sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    context = browser.new_context(accept_downloads=True)
    errors: list[str] = []
    page = context.new_page()
    page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
    page.on("pageerror", lambda error: errors.append(f"pageerror: {error}"))

    print("\n=== 1. 章節入口、單元與精確原文 ===")
    page.goto(f"{base}/#/guide/mid-s3/mid-s3c9", wait_until="networkidle")
    unit_link = page.get_by_role("link", name="不平衡分類：從矩陣回答業務問題")
    unit_link.wait_for(timeout=30_000)
    check("章節顯示實務補充入口", unit_link.is_visible())
    unit_link.click()
    page.get_by_role("heading", name="不平衡分類：從矩陣回答業務問題").first.wait_for()
    check("單元載入真實 Markdown", "混淆矩陣" in page.locator("main").inner_text())
    back = page.get_by_role("link", name="返回學習指引原文")
    check("返回連結使用已知 block", "#block-70" in (back.get_attribute("href") or ""))
    back.click()
    page.locator('[data-guide-block-id="block-70"]').wait_for(timeout=30_000)
    check("返回後命中實際 DOM anchor", "#block-70" in page.url)

    print("\n=== 2. 固定 10 題、保存、重整、提交與精確回補 ===")
    page.goto(f"{base}/#/simulations/{BLUEPRINT_ID}", wait_until="networkidle")
    page.locator("article[data-learning-question]").first.wait_for(timeout=30_000)
    articles = page.locator("article[data-learning-question]")
    check("固定組卷渲染 10 題", articles.count() == 10, str(articles.count()))
    refs = ASSEMBLY["selectedQuestionRevisions"]
    desired: list[str] = []
    for index, ref in enumerate(refs):
        key = ref["questionKey"]
        correct = QUESTIONS[key]["correctOptionId"]
        desired.append(next(option for option in DISPLAY[key] if option != correct) if index == 0 else correct)
    for index in range(4):
        key = refs[index]["questionKey"]
        articles.nth(index).locator("button[aria-pressed]").nth(DISPLAY[key].index(desired[index])).click()
    page.wait_for_function("() => document.querySelector('main')?.innerText.includes('4 / 10 已答')")
    page.wait_for_function("() => true", timeout=100)
    for _ in range(30):
        if saved_answer_count(page) == 4:
            break
        page.wait_for_timeout(100)
    check("4 題已原子保存", saved_answer_count(page) == 4)
    page.reload(wait_until="networkidle")
    page.locator("article[data-learning-question]").first.wait_for(timeout=30_000)
    check("重整續答保留 optionId", page.locator('button[aria-pressed="true"]').count() == 4)
    articles = page.locator("article[data-learning-question]")
    for index in range(4, 10):
        key = refs[index]["questionKey"]
        articles.nth(index).locator("button[aria-pressed]").nth(DISPLAY[key].index(desired[index])).click()
    page.get_by_role("button", name="提交診斷").click()
    page.get_by_text("得分 90 分").wait_for(timeout=15_000)
    wrong = articles.nth(0)
    unit_id = ASSEMBLY["slotAssignments"][0]["quotaId"]
    check("錯題連到精確單元", f"/learn/{unit_id}" in (wrong.get_by_role("link", name="閱讀對應單元").get_attribute("href") or ""))
    guide_href = wrong.get_by_role("link", name="回到指引原文").get_attribute("href") or ""
    check("錯題連到真實 Guide block", "/guide/" in guide_href and "#block-" in guide_href, guide_href)

    print("\n=== 3. Lab 五種真實資產與自評狀態 ===")
    page.goto(f"{base}/#/labs/{LAB_ID}", wait_until="networkidle")
    page.get_by_role("heading", name="設備異常告警：不平衡分類與防資料洩漏").wait_for(timeout=30_000)
    lab_wrapper = json.loads((RELEASE / INDEX["labs"][0]["path"]).read_text())
    expected_assets = [
        ("下載 Starter", "starter.ipynb", lab_wrapper["assetLocations"][0]["hash"]),
        ("下載 Solution", "solution.ipynb", lab_wrapper["assetLocations"][1]["hash"]),
        *[(asset["label"], asset["path"].split("/")[-1], asset["hash"]) for asset in lab_wrapper["supportAssets"]],
    ]
    for label, suffix, expected_hash in expected_assets:
        with page.expect_download() as event:
            page.get_by_role("button", name=re.compile("^" + re.escape(label))).click()
        download = event.value
        check(f"{label} 可下載", download.suggested_filename.endswith(suffix), download.suggested_filename)
        downloaded = Path(download.path()).read_bytes()
        check(f"{label} bytes 綁定 manifest", "sha256:" + hashlib.sha256(downloaded).hexdigest() == expected_hash)
    colab = page.get_by_role("link", name="開啟 Colab 並手動上傳")
    check("Colab 流程明列手動上傳", colab.get_attribute("href").startswith("https://colab.research.google.com/"))
    colab.evaluate("element => element.addEventListener('click', event => event.preventDefault(), { once: true })")
    colab.click()
    page.get_by_text("目前：已開啟，尚未自評完成").wait_for()
    check("開啟 Colab 不會冒充完成", "已自評完成" not in page.locator("main").inner_text())
    page.get_by_role("button", name="我已自行完成並核對").click()
    page.get_by_text("目前：已自評完成").wait_for()
    page.reload(wait_until="networkidle")
    page.get_by_text("目前：已自評完成").wait_for(timeout=15_000)
    check("Lab 自評與開啟狀態分開且可恢復", "不是系統驗證" in page.locator("main").inner_text())

    print("\n=== 4. 五題策展對照與 mobile drawer ===")
    page.goto(f"{base}/#/analysis/exams", wait_until="networkidle")
    page.get_by_role("heading", name="5 題原卷對照").wait_for()
    check("策展子集列出 5 題原卷", page.locator("section article").count() == 5)
    check("明示不是考頻", "不是考頻" in page.locator("main").inner_text())
    mobile = context.new_page()
    mobile.set_viewport_size({"width": 375, "height": 844})
    mobile.goto(f"{base}/#/", wait_until="networkidle")
    mobile.locator('button[aria-controls="primary-navigation"]').click()
    diagnostic_link = mobile.get_by_role("link", name="主題診斷")
    check("375px drawer 可達主題診斷", diagnostic_link.is_visible())
    diagnostic_link.focus()
    mobile.keyboard.press("Enter")
    mobile.wait_for_url(re.compile(r"#/simulations/"))
    check("mobile 新入口可用鍵盤開啟", "/simulations/" in mobile.url)
    mobile.close()

    print("\n=== 5. 未知內容、載入失敗與逾時重整 ===")
    page.goto(f"{base}/#/learn/not-a-learning-unit", wait_until="networkidle")
    page.get_by_text("找不到這份實務補充").wait_for(timeout=15_000)
    check("未知 Unit 明確顯示不可用", "找不到這份實務補充" in page.locator("main").inner_text())
    broken = context.new_page()
    unit_path = INDEX["units"][0]["path"]
    broken.route(f"**/{unit_path}", lambda route: route.abort())
    broken.goto(f"{base}/#/learn/{INDEX['units'][0]['id']}", wait_until="domcontentloaded")
    broken.get_by_text("內容載入失敗").wait_for(timeout=15_000)
    check("已知內容網路失敗不會假裝空資料", "內容載入失敗" in broken.locator("main").inner_text())
    broken.close()

    timer_context = browser.new_context()
    timer_page = timer_context.new_page()
    timer_page.goto(f"{base}/#/simulations/{BLUEPRINT_ID}", wait_until="networkidle")
    timer_page.locator("article[data-learning-question]").first.wait_for(timeout=30_000)
    timer_page.evaluate("""async () => {
      const open = indexedDB.open('ipas-learning-v1', 1)
      const db = await new Promise((resolve, reject) => { open.onsuccess = () => resolve(open.result); open.onerror = () => reject(open.error) })
      const transaction = db.transaction('attempts', 'readwrite')
      const store = transaction.objectStore('attempts')
      const rows = await new Promise((resolve, reject) => { const request = store.getAll(); request.onsuccess = () => resolve(request.result); request.onerror = () => reject(request.error) })
      const record = rows[0]
      record.snapshot.deadlineAt = new Date(Date.now() - 1000).toISOString()
      const canonical = value => Array.isArray(value) ? value.map(canonical) : value && typeof value === 'object' ? Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])])) : value
      const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(JSON.stringify(canonical(record.snapshot))))
      record.snapshotHash = 'sha256:' + Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('')
      store.put(record)
      await new Promise((resolve, reject) => { transaction.oncomplete = resolve; transaction.onerror = () => reject(transaction.error) })
    }""")
    timer_page.reload(wait_until="networkidle")
    timer_page.get_by_text("得分 0 分").wait_for(timeout=15_000)
    check("逾時重整自動提交且不重設期限", timer_page.get_by_text("答對 0 / 10 題").is_visible())
    timer_context.close()

    real_errors = [error for error in errors if "favicon" not in error.lower()]
    check("流程無 console/page error", not real_errors, str(real_errors[:3]))
    context.close()
    browser.close()

print("\n" + "=" * 60)
if FAILS:
    print(f"✗ {len(FAILS)} 項失敗：" + "、".join(FAILS))
    raise SystemExit(1)
print("✓ learning frontend 真實 preview 流程全部通過")
