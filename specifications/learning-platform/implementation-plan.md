# 開發工作包、驗收與模型交接

狀態：本文件是目標工作包與驗收規格；實際 MVP 完成範圍見 [progress.md](progress.md)，可執行命令見 [mvp-runbook.md](mvp-runbook.md)。未列為已完成的 P2／P3 工作包仍是後續規格。
參照 [architecture.md](architecture.md)、[data-contracts.md](data-contracts.md)、[content-and-labs.md](content-and-labs.md)。

## 開發方式與階段出口

一個工作包以一個可 review 的變更集交付；每包先確認前置依賴，避免模型同時改相同來源檔。
任務可由 Codex、Claude Code 或其他模型承接，責任依輸出與驗收分配，不依模型名稱決定誰的答案正確。
寫作、實作與審查可平行；發布決定綁定具體版本，模型同意不能取代執行或來源核對證據。
規格變更先回到契約說明影響，再修改消費端；不得用臨時欄位讓單一頁面先跑過。

| 階段 | 目標 | 必須達成的出口 | 不能提前擴大 |
|---|---|---|---|
| P0 基線與契約 | 避免現況重造、固定 source ownership | LP-000／010／020 完成；fixture 可驗，沒有 production 改動 | 不重跑全量 OCR、不批產內容 |
| P1 垂直 MVP | 一條指引→實務→專題→lab→診斷的完整流程 | LP-110 至 LP-190；一個完整 slice 通過內容及 runtime gate | 不以多做列表替代可執行 lab |
| P2 內容規模化 | 第二個主題驗證可重用架構 | LP-210／220／230；增內容不需新增章節／概念常數 | 不用複製第一個專題元件擴張 |
| P3 分析與組卷 | 系統化歷屆比較、正式配置的模擬 | LP-310／320／330；統計可重算、缺額可診斷 | 不宣稱預測考題或心理計量能力 |

P0 → P1 是建議第一個開發目標；P2／P3 保留規格但不併入 MVP 驗收。
不給沒有團隊產能及執行基線支持的固定工期；每個階段以出口決定是否繼續。

## LP-000 基線與範圍固定

- 依賴：無。輸入：`CLAUDE.md`、必要 playbook 小節、`tests/README.md`、本規格及目前 git diff。
- 輸出：候選 `specifications/learning-platform/baseline.md`，記錄 commit、現有改動、41 篇／41 notebook／6 paths 等重新盤點數量及 current tests。
- 操作：用小切片讀取 manifest、catalog、topics；先辨識來源及格式，不全讀大型 JSON。
- 驗收：有新增/沿用矩陣、MVP primary=`mid-s3c9` 與 secondary=`mid-s2c4` 引用有效；現行測試失敗單獨記錄並區分是否阻擋。
- 回復：只產生文件；不得為取得綠燈修改既有 OCR inventory、預期題數或簽核紀錄。

## P0 契約與身份

| ID／依賴 | 輸入 | 候選輸出／修改位置 | 完成條件 |
|---|---|---|---|
| LP-010；000 | data-contracts、既有 types／source samples | `schemas/learning/*.schema.json`、`scripts/learning/contracts.py`、小 fixture | 所有新實體、review、manifest、attempt 有 schema；未知 enum／欄位型別／缺必要值 fail；正常 fixture pass |
| LP-020；010 | manifests、catalog、topics、來源題／block slices | `scripts/learning/references.py`、`content/learning/identity/`、`tests/test_learning_references.py` | 來源命名空間不撞題；不存在／跨版本錯誤／歧義 anchor 阻擋；topic name＋hash adapter；不複製原文 |

LP-020 第一版只建立 MVP 所需確切 anchors 及 aliases，不先為全站產生未審定位。
Guide block 重排 fixture 須讓舊 `b12` 指向不同文字，確認 resolver 拒絕誤接；人工修復後新 review 才放行。
Question fixture 須包含兩個題庫都叫 `Q1`，確認 namespace、答案與頁面來源各自正確。
Topic stable ID 遷移先列 consumer inventory；MVP 保留 name，完整遷移放 LP-210。

## P1 第一條完整學習流程

共用 fixture 主題：不平衡分類評估與資料洩漏；primary=`mid-s3c9`，secondary=`mid-s2c4`。
三個 LearningUnit 涵蓋「切分與 fit 順序」、「不平衡分類評估」、「閾值及實務決策」，依契約使用 stable IDs。
對應 `unit-split-before-fit`、`unit-imbalanced-classification`、`unit-threshold-decision`；專題為
`project-imbalanced-classification`，lab 為 `lab-imbalanced-classification`。10 題按三單元 3／4／3 分配，至少含 3 題情境判斷與 2 題指標計算。
一個 Project 組織三個單元及一份 Lab；從現有資料逐題挑 3–5 題相關來源題，不猜題號或將全章題目一律貼標。
另準備 10 題已通過答案、干擾選項、來源及語意審查的單選題，形成主題診斷，不冒稱正式試卷配額。

| ID／依賴 | 輸入 | 候選輸出／修改位置 | 完成條件 |
|---|---|---|---|
| LP-110；020 | 小節原稿與可靠補充來源、內容模板 | `content/learning/units/`、`reviews/`、`mappings/` | 3 個單元含可測目標、情境、選擇理由、失敗例、來源、自檢；每個主張與來源可核對 |
| LP-120；010、020 | entities、reviews、resolver | `scripts/build_learning_content.py`、`scripts/learning/publication.py`、generated不可變releases與current.json | 可 dry-run／check；先寫版本內容/lab、全驗後原子切pointer；未審拒發、hash失效、deterministic bytes、pointer rollback全通過 |
| LP-130；110、120 | 通過 gate 的 units、guide relation index | `features/learning/`、`GuidePage.tsx`、`App.tsx`、Sidebar | 從原章進補充再返回原 anchor；詳頁不 eager-load 全內容；未知 ID／重試／手機導覽可用 |
| LP-140；020、110 | LabSpec、單一 notebook、免金鑰資料 | `content/learning/labs/`、`notebooks/labs/`、候選 lab exporter／verifier | starter／solution 同源、乾淨 CPU runtime 執行、assertions 有效；Colab 人工完整跑通；reports 綁版本 |
| LP-150；020、110 | 已發布來源題、標註與 review | MVP 分析分片、`features/analysis/`、mapping reports | 3–5 題可回原題及指引；範圍／未標註／分母明示；人工重算與 JSON 結果一致 |
| LP-160；110、130、140 | 三 units、一 Lab、Project rubric | `content/learning/projects/`、`features/projects/`、`features/labs/` | 有先備、交付清單與步驟；lab 詳頁資訊可讀、Colab 連結版本正確、點開不記 passed |
| LP-165；020、110 | 三 units、canonical Track B、既有出題／答案審查流程 | `data/learning/pipeline/<runId>/` 草稿、審核後策展合併原 `data/中級/questions/subject3_questions.json`、`reviews/`、`mock-blueprints/` | 作者交付10新題及3／4／3 blueprint；獨立reviewer逐題驗來源/答案/干擾選項；保存舊題ID/cards，不合格不合併 |
| LP-170；120、165 | LP-165 的 10 題合格 pool 與主題 blueprint | `features/simulation/`、`scripts/learning/assessment.py`、生成pool分片 | 相同 pool/seed 相同題序；題號不撞、缺額阻擋、10 題計分正確；提交後有補充／lab 回饋 |
| LP-180；160、170 | state contract、既有 localStorage | IndexedDB `LearnerRepository`、`features/learning/state/`、`tests/test_learning_state.py` | transaction保存／恢復、deadline補正、舊題版本拒絕誤套、匯入／衝突／quota錯誤可處理；自報與已驗證區別 |
| LP-190；130–180 | 全 slice、既有 test harness | `tests/test_learning_flow.py`、`tests/test_learning_publication.py`、`tests/run_all.py` | E2E 從指引到成果／診斷後回補充；新失敗 cases 與既有完整 release gate 通過；發佈回復演練 |

LP-110 與 LP-140 的教學內容可先平行草擬，但落地 notebook／來源題必須等契約與 primary refs 確認。
LP-170 的純選題函式可用 fixture 開發；正式 pool 未簽核前不讓新診斷卷出現在 production index。
LP-165 的題目作者沿用現有小節出題／答案交叉驗證介面產生候選，輸出先放隔離 run directory，不讓模型直接寫 production。
由維護者完成刻意策展合併及 commit 說明，QuestionRef namespace 沿用 `middle:subject3_questions`，章節引用取 `mid-s3c9`；
跨章補充及 lab 作延伸來源明確記錄，不冒稱指引原稿的逐字依據。驗收報告記新舊題數與精確變更 ID，既有題目不可被重編或覆寫。
LP-150 在 P1 只提供與專題相關的來源題及透明計數；完整年份／科目比較屬 P3。
LP-120 只允許完整新 learning bundle 產生；破壞性或既有部分等級 export 行為不在本包改動。
若修改共同題目元件，LP-170／180 必須同時跑既有 exam/practice E2E，不能以新 simulation test 代替。

### P1 教學與 runtime 驗收案例

| Case | 操作／情境 | 必須觀察到的結果 |
|---|---|---|
| AC-01 指引延伸 | 從 mid-s3c9 開補充後返回 | 原章、來源頁與 anchor 可定位；原稿文字及 Track A／B checksum 未改 |
| AC-02 實務差異 | 比較全資料 fit 與訓練資料 fit 的流程 | 學習者指出洩漏發生位置及修復；unit 與 notebook 說法一致 |
| AC-03 指標決策 | 在不平衡資料上比較 baseline 與模型 | 提供至少兩種適用指標與混淆矩陣，解釋單看 accuracy 的限制 |
| AC-04 實驗完成 | 由乾淨 runtime 執行 solution | 在規定 CPU 環境成功；輸出與 assertions 符合契約；starter 留有需要學習者完成的工作 |
| AC-05 成果與證據 | 開啟 Colab，再手動標記完成 | opened 與自評完成分別顯示；不出現假 passed；lab report匯入是P2可選項 |
| AC-06 作答正確 | 跨題快速切換、修改答案、重整、交卷 | 10 題輸入只影響正確 qref；由 fixture 算出的分數精確相同 |
| AC-07 標註與分母 | 篩選含多 topic 的題目集合 | 複合標註不重複計入總題數；不足／未知清楚顯示；可逐題核對 |
| AC-08 發布阻擋 | 修改 unit 來源 SHA、刪 lab 資產或移除 review | build 回非零；上一發布內容完整保留；沒有半新半舊頁面 |
| AC-09 裝置與錯誤 | 375 px 寬／鍵盤導覽／瀏覽器儲存失效 | 新入口可達、焦點合理、表格可讀、作答仍可用且保存狀態明確 |
| AC-10 相容與效能 | 開舊 articles/path/exam URL 及新首頁 | 舊路徑有效；新索引及 body 達預算；首頁不匯入全題庫／notebooks |

P1 交付含學習者完整走查記錄、執行環境／版本、測試摘要及已知限制。
只有 schema／build 成功、空白頁面或全由 solution 展示的 notebook，不算完成這條 slice。

## P2 跨主題擴展與內容運作

| ID／依賴 | 輸入 | 候選輸出／修改位置 | 完成條件 |
|---|---|---|---|
| LP-210；190 | topic consumers、既有 merge overlays／標籤 | 原 `topics.json` schema 與相關讀取器／遷移腳本 | 同一詞彙表加 stable ID；name/alias 相容、重建冪等、歷史topic refs可解析；無第二詞彙表 |
| LP-220；190 | 原6 path definitions、Project／Path契約 | `content/learning/paths/`、article exporter adapter、`/paths` | 舊6路徑及 query 保持；移除 code 中重複定義；新增第二專題只增source，不重寫UI |
| LP-230；190、220 | 第二專題、legacy notebook reviews、內容覆蓋矩陣 | batch authoring/check CLI、run manifests、失效引用與lab維護報告 | 第二個主題完整上線；run可重入、prompt/source/model/budget可追；infra/semantic重試分開；legacy逐本映射證據、lab可重驗 |

第二專題以第一階段學習者回饋及現有來源選擇，先寫 brief，再執行同一套契約及 gate。
內容覆蓋矩陣以 manifest／topics／已發布 units 動態生成，呈現尚缺實務案例、lab、題例的範圍。
不為了填滿圖表強行創造沒有教學價值的 notebook；可記錄不適合程式操作的主題理由與替代產出。
新增概念須遵循原詞彙表的 review 與 merge 流程，不能讓內容作者任意建立同義 topic。

## P3 歷屆分析與正式模擬配置

| ID／依賴 | 輸入 | 候選輸出／修改位置 | 完成條件 |
|---|---|---|---|
| LP-310；190、210 | 全部catalog考卷、已審topic mappings | 擴充原catalog schema/readers的session、帶證據publicationInventory及sample科目segments；`scripts/export_exam_analysis.py`、analysis分片/UI | 科目／年份／卷別／概念篩選；sample未分科留unknown分母；coverage/snapshot正確；未知不冒作0；既有熱度口徑差異明示 |
| LP-320；170、310 | 明確版次及來源的exam profile、題池配額 | 新mock blueprints、組卷診斷、完整simulation流程 | 不同科目配置分開；題數／group／難度／topic配額可行性預檢；相同seed可重現；無解可說明 |
| LP-330；220、230、310、320 | 覆蓋率／build與runtime量測 | capacity report、後端／CDN是否啟動的ADR | 第二主題及多blueprint共用架構；列實測限制與擴展觸發；沒有需求不建立帳號／付款／微服務 |

正式考試配置（題數、時間、範圍）須以實作當時可驗證的官方文件為準，並記錄版本與引用。
若官方未公布 topic／難度配額，標示為平台練習配置；不能自行命名為官方比例。
相同題目多 topic 可用於學習回饋；組卷配額需依契約選定的主分桶計算，避免同題重複滿足互斥名額。
沒有群體作答資料前，不增加「鑑別度」「實測難度」「能力估計」等指標名稱。

## 驗證命令與預期證據

現有命令，依改動範圍使用；以 `CLAUDE.md` 與 `tests/README.md` 的當前要求為準：

```bash
cd frontend && npm run build
python3 scripts/verify_data_alignment.py --level 初級
python3 scripts/verify_data_alignment.py --level 中級
uv run python tests/run_all.py
```

候選新增 CLI 契約（由 LP-010／020／120／140／150 等實作並記錄 `--help`）：

```text
uv run python scripts/validate_learning_content.py --all --check
uv run python scripts/build_learning_content.py --dry-run
uv run python scripts/build_learning_content.py --check
uv run python scripts/build_learning_content.py
uv run python scripts/verify_learning_labs.py --lab <labId> --profile cpu
uv run python scripts/export_exam_analysis.py --check
```

所有新 CLI 從檔案位置找 repo root；`--check` 不寫 production；`--dry-run` 列影響、依賴與缺口，不呼叫付費服務。
報告包含 exit code、受驗 entities／版本、pass／fail／未完成數；未完成語意審查或執行不能算 pass。
資料／前端變更按照既有規則跑 build/alignment；runtime 及 release 跑完整 suite。
Notebook 的完整執行另外出具 runtime report；既有 13 項 gate 未包含的新檢查需明確串入或作為 release 必需 job。
不為本次純 Markdown 規劃聲稱做過 runtime 驗收；文件驗收只核對連結、路徑、契約一致性及需求覆蓋。

## 回復、相容與範圍外

每包在實作前記錄會改動的 source／generated／state keys；禁止一次改 canonical 與前端後失去回復依據。
Source 回復用版本控制；新發布包失敗保留舊pointer及不可變目錄；跨欄位schema修改先有相容讀取器，再切exporter。版本資產先寫、指標最後切；不把兩棵檔案樹當成一次rename。
Topic／anchor／question alias 遷移建立小樣本與 dry-run 報告，再處理更大集合；不以模糊文字自動接回不明來源。
Learner state migration 保留原 key，驗證新資料後設 migration marker；中斷可重試，rollback 不刪使用者紀錄。
每次 release 記錄新舊 release ID；關閉新入口的功能旗標不得停止既有章節、文章與考卷 route。

MVP 範圍外：雲端帳號同步、多人班級管理、付費訂閱、可信遠端自動評分、監考、即時模型問答、
任意使用者上傳 notebook 執行、全面重寫 OCR、將全站改為後端 SSR、多考試品類的通用 LMS。
沒有要擴張上述需求時，不建立只有 stub 的 backend/API、無用資料庫表或部署設定。

## 後續模型工作單模板

```text
Task ID：LP-___
本次目的：以一個可觀察的使用者結果描述。
已完成依賴：Task IDs + commit / evidence。
必讀規格：本規格的具體小節 + CLAUDE / playbook 路由。
輸入：source paths、schemaVersion、實體及revision，禁止整讀的大檔切片方式。
允許改動：明確paths；與其他模型約定唯一寫入者。
不變量：manifest/topics/catalog SSOT、Track A/B ownership、legacy review界線。
輸出：runtime files / authored content / generated output / tests / docs。
驗收：本task表格條件 + AC cases + 必需既有gate。
回復：來源版本、staging回復、state migration策略。
回報：完成/未完成，檔案:行號，命令與exit code，未驗證限制，下一Task ID。
```

協作建議：一個模型負責契約與內容來源，另一個負責消費端；第三個在固定 commit 上獨立審查。
審查者用原始 PDF／官方文件、可執行輸出及測試重算核對關鍵主張，不只評閱讀文字是否合理。
若模型無法使用某工具，明確標示缺少的驗證，把可獨立完成的部分交付，不偽造執行或審查成功。
