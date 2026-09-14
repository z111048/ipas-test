# iPAS 實務學習平台：架構藍圖與開發規格

版本：藍圖 v1.0｜盤點日期：2026-09-07｜狀態：**本機 MVP 完成，20 項驗收通過**；正式發布仍待真人 Colab L5，詳見 [progress.md](progress.md)。

本藍圖將既有考試教材網站擴展成「讀懂指引 → 理解實務 → 完成專題 → 分析考題 → 模擬診斷 → Colab 驗證」的學習平台。
首要投資是學習指引的實務補充與可驗證練習；擴大題量及分析畫面應建立在內容可信、來源可追溯之後。
預設延續繁體中文、iPAS 初級與中級；第一個 lab 以免費 CPU 與無付費 API 依賴設計。
使用者已確認開始 MVP，開發沿用本藍圖；網站部署、帳號後端與付費服務建置仍在本輪範圍外。

## 文件與閱讀順序

| 文件 | 要回答的問題 |
|---|---|
| [architecture.md](architecture.md) | 模組如何協作、哪些既有系統沿用、資料如何保存及演進？ |
| [data-contracts.md](data-contracts.md) | ID、內容、引用、審核、分析及模擬資料如何表示與驗證？ |
| [content-and-labs.md](content-and-labs.md) | 如何編寫實務內容、設計專題、產出與驗收 Colab？ |
| [implementation-plan.md](implementation-plan.md) | 從哪個工作包開始、依賴什麼、做到什麼才算完成？ |
| [review.md](review.md) | 架構審查發現什麼、如何處理、哪些限制仍需保留？ |
| [progress.md](progress.md) | MVP 實際完成哪些工作，驗收證據與尚待完成項目為何？ |
| [mvp-runbook.md](mvp-runbook.md) | 如何重建本機預覽、操作學習流程與執行驗證？ |
| [topic-id-migration.md](topic-id-migration.md) | Topic stable ID 要怎麼遷移：誰是 consumer、id 規則提案、碰撞與停點？ |

接手模型先讀本頁及 `CLAUDE.md`，再讀與工作包相關的規格及 playbook 小節。
現有行為的權威仍是 `CLAUDE.md` 與 `playbook/pipeline-reference.md`；本目錄描述新增功能的目標。
若發現衝突，先保留既有不變量、回報差異，再以獨立變更更新提案；不得把規劃文字視為已完成遷移。
欄位及序列化規則以 `data-contracts.md` 為準，內容品質及 notebook 驗收以 `content-and-labs.md` 為準，工作包順序以 `implementation-plan.md` 為準。

## 已有能力與擴充目標

以下是此次讀取原始碼與版控產物的盤點，不代表重新執行所有既有品質驗收。
數量是盤點快照，後續實作應從 canonical 資料重新計算，不能寫成永久常數。

| 領域 | 已有能力 | 本藍圖增加的能力 |
|---|---|---|
| 指引閱讀 | Track A 閱讀頁、41 篇章節文章、來源頁／區塊引用 | 獨立實務補充層、誤解診斷、案例與操作決策；保留原文閱讀 |
| 學習路徑 | 6 條文章閱讀路徑 | 混合文章、補充、練習、lab 的步驟；有產出與評分規準的專題 |
| 考題 | 官方／樣題、章節練習、詳解、指引標註、考試計時與計分 | 可說明分母及覆蓋缺口的歷屆分析；可重現的主題診斷與後續正式模擬組卷 |
| 概念索引 | `topics.json`、概念標註、熱度、心智圖及概念頁 | 跨內容關聯、版本化引用、失效偵測；沿用唯一概念詞彙表 |
| 實作 | 兩級共 41 本 notebook、Colab 入口與既有執行審查 | 明確 lab 契約、starter／solution、乾淨環境驗收、專題交付及完成證據 |
| 保存與發布 | React 靜態站、GitHub Pages、章節作答 localStorage、13 項既有 release gate | 版本化學習紀錄、可攜匯出／匯入、新內容發佈閘門與安全回復 |

主要現況依據：`frontend/src/App.tsx`、`frontend/src/types/index.ts`、`scripts/export_learning_articles.py`、
`frontend/src/store/examStore.ts`、`playbook/pipeline-reference.md` §1a／§3／§5、`tests/README.md`。

## 已選定的設計決策

1. 採靜態網站優先的模組化單體：沿用 Python 內容 pipeline、React/Vite、GitHub Pages；新增內容在建置前產生。
2. 不複製章節、概念及資源清冊：分別引用 manifest、`data/topics/topics.json`、`data/resource_catalog.json`。
3. Track A／Track B 完整保留；實務補充是第三種內容域，不能回寫為指引原文或替換 canonical 出題來源。
4. 新 authored source 放 `content/learning/`；前端讀驗證後的 `frontend/src/generated/learning/` 分片。既有 articles、題庫與 notebooks 逐步以 adapter 接入。
5. 新內容以版本、來源、獨立審查及實際執行證據決定可否發布；舊資料缺少新審查時標記待確認，不能自動升格。
6. 先做一條完整學習流程，再擴大到更多章節；MVP 不追求全部 41 章重寫或大量新增試題。
7. MVP 不建帳號、收費、雲端作答同步、伺服器執行 notebook；Colab 在學習者自己的環境執行。

## 第一條可驗收流程

共同示範主題為「不平衡分類評估與資料洩漏」，以 manifest 中的 `mid-s3c9`「模型訓練、評估與驗證」為主要指引入口，
需要的資料清理基礎引用 `mid-s2c4`。這些 ID 是示範引用，不是新增章節定義。

學習者從指引進入三個實務單元，辨識切分／fit 順序、選擇不平衡分類指標，並理解閾值如何影響決策；
接著比較 3–5 題經審核的來源題，完成一份 CPU、免付費 API 的 Colab，交付實驗表與決策說明，最後完成 10 題主題診斷。
三個單元、一個專題、一份 lab 及一份診斷卷構成 MVP；Colab 開啟事件不等於實作通過。
來源題不足時呈現實際覆蓋數；新增診斷題不足時阻擋發布，不能用未審題補足。

## 需求追蹤

| 需求 ID | 使用者需求 | 模組與開發階段 | 驗收定位 |
|---|---|---|---|
| R1 | 指引提供更實務的補充，優先度最高 | LearningUnit、GuideRef；P0–P1 | 指引可到補充再返回原頁；含案例、選擇理由、失敗情境及來源；LP-110／LP-130；AC-01–03 |
| R2 | 製作主題性專題 | Project、LearningPath；P1–P2 | 跨內容步驟有先備要求、可交付成果及 rubric；LP-160／LP-220；AC-04–05 |
| R3 | 歷屆試題與考題分析 | ExamAnalysis、QuestionRef；P1 基礎、P3 完整 | 可以回到原題；數量可人工重算；顯示範圍、分母、缺失與標註版本；LP-150／LP-310；AC-07 |
| R4 | 考題模擬 | MockBlueprint、Attempt；P1 主題診斷、P3 組卷 | 相同 seed／pool 產生相同題目、題目不重複、計分與回復不錯位；LP-170／LP-320；AC-06 |
| R5 | Colab 實際操作練習 | Lab、Project 成果；P1–P2 | 乾淨 runtime 順序執行 solution、starter 可完成、成果可自評；LP-140／LP-230；AC-04–05 |
| R6 | 後續模型依藍圖實作並可擴大 | 版本契約、release、工作包 | 每項 task 有輸入、輸出、驗收與回復方法；LP-000 至 LP-330；AC-08–10 |

## 開發接手入口

從 [implementation-plan.md 的 LP-000](implementation-plan.md#lp-000-基線與範圍固定) 開始。
優先檢查工作樹與既有驗收基線，再落實契約和一組小 fixture；不先重跑 OCR、不先建立後端、不批次呼叫模型。
每個模型工作包交付「變更檔案、執行命令、驗收證據、已知缺口、下一個 task ID」。
完整三軌 OCR 及既有正式發布程序仍依 playbook 執行；本規格新增的 gate 應加入它，而不是替代它。
