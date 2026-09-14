# LP-210C：非作者審查的委派紀錄

日期：2026-09-14。這份紀錄說明「誰授權了誰、審查範圍到哪裡」，不是審查結果本身；
審查報告本文歸檔在 [`topic-id-migration-review.md`](topic-id-migration-review.md) 的 LP-210C 節。

## 為什麼需要非作者審查

LP-210C 把四份 tracked 衍生產物（兩份標註、`topicHeat.json`、`conceptGraph.json`）與三個 gitignored 模型快取
改成同時帶 topic 穩定 id，並改動前端 `/concepts` 的選取鍵與網址相容層。標註與快取是**付費模型產出**，
回填只能是純新增、不能改到任何一筆判定；export 產物是 committed、要能位元重現；前端相容層錯了會讓既有分享連結失效。
作者自己跑過的證明（拆掉 id 與原檔相等、快取 v2 轉回 v1 逐字相等、跨 hash seed 位元相同）需要由未參與實作的人重現。

## 授權與範圍限定

維護者（本 repo 的使用者）在 LP-210C 的開場指示中明確要求「交非作者審查」，並沿用 2026-09-08 對 LP-210A 的授權
「你可以使用 Codex CLI 審核」。本包沒有改動任何 authored 內容或 review 紀錄，因此**不涉及任何 review 的重新開立**，
審查對象只有工具層與衍生產物。

**涵蓋**：純新增證明（對 `git show HEAD:` 基準）、id 與詞彙表逐筆一致、快取無損轉換（對 scratchpad 唯讀備份）、
export 可重建、fail-closed 行為的實測、改名路徑、既有破壞性行為（驗收快取被 `--limit` 洗掉）的修正、
前端相容層邏輯、§3 未決事項 C 是否被代決、範圍紀律（未碰 SSOT／帳本／id／`content/`／review／glossary）。

**不涵蓋**：重跑瀏規器 E2E 與完整 20 項 gate（審查者的唯讀 sandbox 不跑，由作者實跑並記錄）、
教學內容或標籤語意的正確性（那是 2026-08 標註驗收與後續 review 的職責，本包沒有改變任何判定）。

## 角色

- 作者：`agent-claude-code`（本次實作者，Claude Code／Fable 5.1）
- 審查者：`agent-codex-cli`（Codex CLI 0.154.0，`codex exec --sandbox read-only`），角色 `independent_model`
- 資格授予者：`maintainer`（repo 使用者本人），不等於審查者，也不等於作者
- `humanApproval: false`——維護者授權了一個 model reviewer，這不等於維護者本人完成了審查

審查提示詞全文與各輪報告本文見 `topic-id-migration-review.md` 的 LP-210C 節；含工具呼叫 trace 的原始 log 留在本機 scratchpad，不進版控。
與 LP-210A／B 相同，審查者無法取得工作樹「修改前」的完整基準——但本包不同的是，四份 tracked 產物在 HEAD 有修改前版本，
純新增證明因此**有真實基準**；只有三個 gitignored 快取要靠作者提供的唯讀備份（SHA-256 記在 `lp210c-derived-artifacts-20260914.md`）。
