# LP-210B：非作者審查的委派紀錄

日期：2026-09-09。這份紀錄說明「誰授權了誰、審查範圍到哪裡」，不是審查結果本身。

## 為什麼需要重新審查

LP-210B 把 `TopicRef` 從 `{name, vocabularyHash}` 改成 `{id, name}`。
5 個 authored 實體的 `contentHash` 因此改變，依 `data-contracts.md` §7
（「審核以 subjectHash 和 dependency hashes 全等才有效，不能沿用舊 PASS」），
13 筆綁在舊 hash 上的 review 全部失效，必須以新 hash 重新開立。

## 維護者的授權與範圍限定

維護者（本 repo 的使用者）於 2026-09-08 指示「你可以使用 Codex CLI 審核」，
並於 2026-09-09 就 13 筆失效 review 的處理方式，在三個選項中明確選擇
**選項一：範圍受限的重新審查**——由非作者審查者驗證
「差異只在 topicRefs、正文 byte 相同、新 ref 都能解析」，
然後以新 hash 開立新紀錄，紀錄中明寫 scope 是機械式遷移，並以 `supersedes` 指回前一版。

因此本輪的審查範圍被明確限定為：

**涵蓋**：機械式遷移的正確性——差異是否確實只在 `topicRefs` 與 `contentHash`、
新的 id/name 是否都能解析、詞彙表改動是否為純新增、代號帳本的耐久性護欄是否有效、
新契約是否真的解決了「新增概念就讓全部引用失效」的原問題、有沒有引入新缺陷。

**不涵蓋**：重做教學內容的語意審查、重跑真人 Colab L5、重新判斷題目答案。
原本的 domain／semantic 結論是針對**未被本次改動觸及**的內容，本輪只確認那些內容確實沒被觸及。

## 角色

- 作者：`agent-claude-code`（本次遷移的實作者）
- 審查者：`agent-codex-cli`（Codex CLI，`codex exec` 唯讀 sandbox，
  `sandbox_permissions=["disk-full-read-access"]`），角色 `independent_model`
- 資格授予者：`maintainer`（repo 使用者本人），不等於審查者，也不等於作者
- `humanApproval: false`——維護者授權了一個 model reviewer，這不等於維護者本人完成了審查

自動化檢查（`deterministic_contract` 的 C1、`notebook_execution` 的 L0–L3）
不由 Codex 認定，而是由腳本本身背書：

- C1：`scripts/validate_learning_content.py --all --check` 於 2026-09-09 實跑，
  結果 `validated`、143 entities、`issues=[]`。
- L0–L3：`scripts/verify_learning_labs.py --lab lab-imbalanced-classification --profile cpu --check`
  於 2026-09-09 由**作者本機**實跑（exit 0），報告存在
  `content/learning/evidence/assessment/lab-l0-l3-reverify-20260909.json`。
  審查者 Codex 在自己的唯讀 sandbox 中無法建立 Jupyter socket，因此**沒有**獨立重現這一項；
  它在報告中明確列為「無法驗證」。這筆 review 的背書者是腳本與作者的實跑紀錄，不是 Codex。

Lab 的 L4（獨立語意審查）本輪**沒有**重做。`review-lab-semantic-20260909-v2` 的 `L4: pass`
只能讀作「舊結論經遷移確認後承接」，不得引用為 Codex 新做的 L4。真人 Colab L5 仍未完成。
