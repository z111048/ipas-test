# 設計審查與交接紀錄

日期：2026-09-07。這份紀錄只描述規格撰寫與檢查，不代表新功能已實作或通過執行驗收。

## 協作範圍

- 架構規劃：獨立檢視現有前端與 pipeline，撰寫 architecture、implementation-plan 與入口文件。
- 資料設計：獨立盤點來源、ID、題庫與標註，撰寫 data-contracts。
- 教學與操作設計：檢視現有文章及 notebooks，查核官方文件，撰寫 content-and-labs。
- 統整：協調同一 MVP 範例、資料所有權與跨文件契約；新增專案 README 入口。
- 驗收：由未參與撰寫的模型獨立讀回；檢查結果與修正記於下方。

## Claude Code 協作狀態

本機存在 Claude Code CLI，曾提交停用工具、停用工作階段保存的架構摘要審查請求。
第一次請求回傳 `Request timed out`，沒有取得設計意見。
後續申請連線被自動核准審查拒絕；理由是向外部 Claude 服務傳送專案內部架構與資料流程摘要，
需要使用者對內容及目的地更明確的授權。因此本版**沒有 Claude Code 的審查結論**，也沒有繞過拒絕重試。

若使用者授權追加此項審查，先提供要傳送的摘要讓使用者確認，僅傳送本次規格所需內容；
要求 Claude 針對資料來源所有權、ID 遷移、發佈一致性、模擬組題、Colab 驗收與 MVP 範圍找缺口。
收到回覆後以問題／決策／修正／驗證記錄更新本檔，不能將模型建議直接視為既有程式事實。

## 本次文件驗收

由未參與撰寫的模型依固定驗收清單完整讀回，結論為 **PASS**，沒有未解 P0／P1／P2。
讀回時發現的契約歧義已在定稿前修正並再次核對，包含 LearningPath target、QuestionRef、
qualified objective、Project rubric ID、ContextGroup、Difficulty、MockPoolRef、Evidence hash、外部來源
snapshot、審核資格與角色、生命週期、確定性組卷、Attempt／Progress、sample 科目與 session 分母，
以及先寫不可變資產、最後原子切換 `current.json` 的發布回復流程。

文件靜態檢查涵蓋 7 份 Markdown、21 個相對連結、非空內容、結尾 newline、code fences、連結目標及
`git diff --check`，結果均通過。契約內 TypeScript 示意片段曾合併後以 `tsc --strict --noEmit` 檢查通過；
這只證明示意型別相容，不代表 runtime 或 JSON Schema 已驗收。

本次沒有執行 build、OCR、資料 pipeline、notebook／Colab、Playwright、付費 API 或部署；規格中的
新增功能、CLI、schema、內容及測試仍須由對應 LP 工作包實作並取得各自證據。

## 實作接手邊界

本次只新增規劃文件及 README 入口，沒有變更 runtime、資料 JSON、notebook、CI 或部署。
規格中的候選檔案、介面、測試及 CLI 均須在對應開發任務落實，不能直接假定存在。
現況操作以 [CLAUDE.md](../../CLAUDE.md) 與 [pipeline-reference.md](../../playbook/pipeline-reference.md) 為準。
新行為實作後才更新權威操作手冊；不要把本規格的未實作命令抄成現況。
