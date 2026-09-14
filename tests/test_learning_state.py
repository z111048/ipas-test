#!/usr/bin/env python3
"""Black-box browser checks for the LP-180 IndexedDB repository contract."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from devserver import dev_server, require_playwright  # noqa: E402

require_playwright()
from playwright.sync_api import sync_playwright  # noqa: E402


FAILS: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    print(f'  {"✓" if condition else "✗"} {label}' + (f"  {detail}" if detail else ""))
    if not condition:
        FAILS.append(label)


def build_preview() -> str:
    completed = subprocess.run(
        [sys.executable, "scripts/build_learning_content.py", "--preview"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if completed.returncode:
        raise RuntimeError((completed.stdout + completed.stderr)[-4000:])
    pointer = json.loads((ROOT / "frontend/src/generated/learning/preview.json").read_text())
    release = ROOT / "frontend/src/generated/learning" / Path(pointer["manifestPath"]).parent
    index = json.loads((release / "index.json").read_text())
    return index["blueprints"][0]["id"]


def wait_for_attempt(page) -> None:
    page.wait_for_function(
        """async () => {
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
          return rows.length > 0
        }""",
        timeout=30_000,
    )


BLUEPRINT_ID = build_preview()
CASES = json.loads((ROOT / "tests/fixtures/learning/state/cases.json").read_text())["cases"]
check("11 個破壞案例 fixture 已載入", len(CASES) == 11, str(len(CASES)))

with dev_server(port=5208) as base, sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    context = browser.new_context()
    page = context.new_page()
    page.goto(f"{base}/#/simulations/{BLUEPRINT_ID}", wait_until="networkidle")
    page.locator("article[data-learning-question]").first.wait_for(timeout=30_000)
    wait_for_attempt(page)

    exported = page.evaluate("""async () => {
      const { learnerRepository } = await import('/src/features/learning/state/repository.ts')
      return learnerRepository.exportData()
    }""")
    original = json.loads(exported)
    check("真實 simulation 產生單一 hashed envelope", len(original["attempts"]) == 1 and original["attempts"][0]["snapshotHash"].startswith("sha256:"))

    print("\n=== 1. Stored snapshot 與匯入 fail-closed ===")
    tamper = page.evaluate("""async () => {
      const { learnerRepository } = await import('/src/features/learning/state/repository.ts')
      const db = await new Promise((resolve, reject) => {
        const request = indexedDB.open('ipas-learning-v1', 1)
        request.onsuccess = () => resolve(request.result)
        request.onerror = () => reject(request.error)
      })
      const row = await new Promise((resolve, reject) => {
        const request = db.transaction('attempts').objectStore('attempts').getAll()
        request.onsuccess = () => resolve(request.result[0])
        request.onerror = () => reject(request.error)
      })
      row.snapshot.items[0].selectedOptionId = row.snapshot.items[0].displayedOptionIds[0]
      await new Promise((resolve, reject) => {
        const request = db.transaction('attempts', 'readwrite').objectStore('attempts').put(row)
        request.onsuccess = () => resolve()
        request.onerror = () => reject(request.error)
      })
      try { await learnerRepository.getAttempt(row.attemptId); return { rejected: false } }
      catch (error) { return { rejected: true, message: String(error.message || error) } }
    }""")
    check("IndexedDB 內容被改但 hash 未改時拒絕續讀", tamper["rejected"] and "修改或損壞" in tamper.get("message", ""), tamper.get("message", ""))

    # Restore the exact exported envelope through IndexedDB so later cases start from a valid live record.
    page.evaluate("""async (envelope) => {
      const db = await new Promise((resolve, reject) => {
        const request = indexedDB.open('ipas-learning-v1', 1)
        request.onsuccess = () => resolve(request.result)
        request.onerror = () => reject(request.error)
      })
      await new Promise((resolve, reject) => {
        const request = db.transaction('attempts', 'readwrite').objectStore('attempts').put({ attemptId: envelope.snapshot.attemptId, ...envelope })
        request.onsuccess = () => resolve()
        request.onerror = () => reject(request.error)
      })
    }""", original["attempts"][0])

    import_checks = page.evaluate("""async (raw) => {
      const api = await import('/src/features/learning/state/repository.ts')
      const base = JSON.parse(raw)
      async function rejected(payload) {
        try { await api.learnerRepository.previewImport(JSON.stringify(payload)); return false }
        catch { return true }
      }
      const correctAnswer = structuredClone(base)
      correctAnswer.attempts[0].snapshot.items[0].correctAnswer = 'opt-A'
      const reference = structuredClone(base)
      reference.attempts[0].snapshot.poolRef.releaseId = 'altered-release'
      reference.attempts[0].snapshotHash = await api.snapshotHash(reference.attempts[0].snapshot)
      const hash = structuredClone(base)
      hash.attempts[0].snapshotHash = 'sha256:' + '0'.repeat(64)
      return {
        correctAnswer: await rejected(correctAnswer),
        reference: await rejected(reference),
        hash: await rejected(hash),
      }
    }""", exported)
    check("匯入拒絕額外 correctAnswer", import_checks["correctAnswer"])
    check("匯入拒絕不一致 release/pool 引用", import_checks["reference"])
    check("匯入拒絕被改造 snapshot hash", import_checks["hash"])

    print("\n=== 2. Dedup、conflict provenance 與 idempotent submit ===")
    dedup = page.evaluate("""async (raw) => {
      const { learnerRepository } = await import('/src/features/learning/state/repository.ts')
      await learnerRepository.clearData()
      await learnerRepository.importData(raw)
      const first = JSON.parse(await learnerRepository.exportData()).attempts
      await learnerRepository.importData(raw)
      const second = JSON.parse(await learnerRepository.exportData()).attempts
      return { first, second }
    }""", exported)
    check("同一備份重匯不重複", len(dedup["first"]) == len(dedup["second"]) == 1)
    check("空瀏覽器匯入 active 會降為帶來源的歷史紀錄", dedup["first"][0]["snapshot"]["status"] == "abandoned" and dedup["first"][0].get("importedFrom") == original["attempts"][0]["snapshot"]["attemptId"])

    conflict = page.evaluate("""async (raw) => {
      const api = await import('/src/features/learning/state/repository.ts')
      const source = JSON.parse(raw).attempts[0]
      await api.learnerRepository.clearData()
      await api.learnerRepository.saveAttempt(source.snapshot, 0)
      const changed = structuredClone(source)
      changed.snapshot.items[0].selectedOptionId = changed.snapshot.items[0].displayedOptionIds[0]
      changed.snapshot.items[0].answeredAt = new Date().toISOString()
      changed.snapshotHash = await api.snapshotHash(changed.snapshot)
      const changedRaw = JSON.stringify({ schemaVersion: 1, attempts: [changed], progress: [] })
      await api.learnerRepository.importData(changedRaw)
      const first = JSON.parse(await api.learnerRepository.exportData()).attempts
      await api.learnerRepository.importData(changedRaw)
      const second = JSON.parse(await api.learnerRepository.exportData()).attempts
      return { first, second, sourceId: source.snapshot.attemptId }
    }""", exported)
    imported = [row for row in conflict["first"] if row.get("importedFrom") == conflict["sourceId"]]
    check("同 attemptId 不同內容另存且保留 importedFrom", len(conflict["first"]) == 2 and len(imported) == 1 and imported[0]["snapshot"]["status"] == "abandoned")
    check("同一衝突備份再次匯入仍 dedup", len(conflict["second"]) == 2)

    idempotent = page.evaluate("""async (raw) => {
      const api = await import('/src/features/learning/state/repository.ts')
      const source = JSON.parse(raw).attempts[0].snapshot
      await api.learnerRepository.clearData()
      const active = await api.learnerRepository.saveAttempt(source, 0)
      const submitted = structuredClone(source)
      submitted.status = 'submitted'
      submitted.submittedAt = new Date().toISOString()
      submitted.result = {
        score: 0, eligibleCount: submitted.items.length, correctCount: 0,
        invalidatedQuestionKeys: [],
        answerKeySnapshot: submitted.items.map((item) => ({ questionKey: item.questionKey, revision: item.revision, correctOptionId: item.displayedOptionIds[0] })),
      }
      const first = await api.learnerRepository.submitAttempt(submitted, active.writeVersion)
      const second = await api.learnerRepository.submitAttempt(submitted, first.writeVersion)
      return { firstVersion: first.writeVersion, secondVersion: second.writeVersion, firstHash: first.snapshotHash, secondHash: second.snapshotHash }
    }""", exported)
    check("重複提交相同快照保持 idempotent", idempotent["firstVersion"] == idempotent["secondVersion"] and idempotent["firstHash"] == idempotent["secondHash"])

    print("\n=== 3. 100筆／50MB／native quota ===")
    caps = page.evaluate("""async (raw) => {
      const api = await import('/src/features/learning/state/repository.ts')
      const source = JSON.parse(raw).attempts[0].snapshot
      await api.learnerRepository.clearData()
      for (let index = 0; index < 100; index += 1) {
        const row = structuredClone(source)
        row.attemptId = `cap-${String(index).padStart(3, '0')}`
        row.status = 'abandoned'; row.submittedAt = null; delete row.result
        await api.learnerRepository.saveAttempt(row, 0)
      }
      let recordMessage = ''
      try {
        const overflow = structuredClone(source)
        overflow.attemptId = 'cap-overflow'; overflow.status = 'abandoned'; overflow.submittedAt = null; delete overflow.result
        await api.learnerRepository.saveAttempt(overflow, 0)
      } catch (error) { recordMessage = String(error.message || error) }
      const afterRecordCap = JSON.parse(await api.learnerRepository.exportData()).attempts.length
      await api.learnerRepository.clearData()
      let byteMessage = ''
      try {
        const huge = structuredClone(source)
        huge.attemptId = 'byte-overflow'; huge.status = 'abandoned'; huge.submittedAt = null; delete huge.result
        huge.items[0].promptSnapshot.stem = 'x'.repeat(50 * 1024 * 1024 + 1)
        await api.learnerRepository.saveAttempt(huge, 0)
      } catch (error) { byteMessage = String(error.message || error) }
      const afterByteCap = JSON.parse(await api.learnerRepository.exportData()).attempts.length
      return { recordMessage, afterRecordCap, byteMessage, afterByteCap }
    }""", exported)
    check("第 101 筆被拒且原 100 筆未刪", "100 筆" in caps["recordMessage"] and caps["afterRecordCap"] == 100, caps["recordMessage"])
    check("projected 50MB 被拒且未寫入", "50 MB" in caps["byteMessage"] and caps["afterByteCap"] == 0, caps["byteMessage"])

    page.evaluate("""async () => { const { learnerRepository } = await import('/src/features/learning/state/repository.ts'); await learnerRepository.clearData() }""")
    quota_page = context.new_page()
    quota_page.add_init_script("""IDBObjectStore.prototype.put = function () { throw new DOMException('injected quota', 'QuotaExceededError') }""")
    quota_page.goto(f"{base}/#/simulations/{BLUEPRINT_ID}", wait_until="networkidle")
    quota_panel = quota_page.get_by_text("作答未保存", exact=True)
    quota_panel.wait_for(timeout=30_000)
    check("native QuotaExceededError 在 UI 顯示未保存", "儲存空間已滿" in quota_page.locator("main").inner_text())
    quota_page.close()

    print("\n=== 4. 跨分頁 writer 衝突 ===")
    page.evaluate("""async () => { const { learnerRepository } = await import('/src/features/learning/state/repository.ts'); await learnerRepository.clearData() }""")
    writer = context.new_page()
    reader = context.new_page()
    writer.goto(f"{base}/#/simulations/{BLUEPRINT_ID}", wait_until="networkidle")
    writer.locator("article[data-learning-question]").first.wait_for(timeout=30_000)
    wait_for_attempt(writer)
    reader.goto(f"{base}/#/simulations/{BLUEPRINT_ID}", wait_until="networkidle")
    reader.locator("article[data-learning-question]").first.wait_for(timeout=30_000)
    writer.locator("article[data-learning-question]").first.locator("button[aria-pressed]").first.click()
    reader.get_by_text("其他分頁已更新這份作答；此分頁已切換為唯讀，請重新載入", exact=False).wait_for(timeout=15_000)
    check("BroadcastChannel 使第二分頁切成唯讀", reader.locator("article[data-learning-question]").first.locator("button").first.is_disabled())
    writer.close()
    reader.close()

    context.close()
    browser.close()

print("\n" + "=" * 60)
if FAILS:
    print(f"✗ {len(FAILS)} 項失敗：" + "、".join(FAILS))
    raise SystemExit(1)
print("✓ LP-180 IndexedDB 黑盒案例全部通過")
