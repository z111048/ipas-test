# 實務補充、主題專題與 Colab 開發規格

文件版本：1.0；盤點與外部文件查核日期：2026-09-07。
文件性質：目標內容與 Lab 規格；實際 MVP 完成與驗收範圍見 [progress.md](progress.md)，操作方式見 [mvp-runbook.md](mvp-runbook.md)。下列 P2／P3 項目與示範不因此視為已完成。
共用 ID、生命週期、來源引用與雜湊規則依同目錄 `data-contracts.md`；系統邊界依 `architecture.md`。
本文件只規範教學內容與實作資產，不改動 `CLAUDE.md`、既有 playbook 或官方指引原文。

## 1. 已驗證基線與教學缺口

截至盤點日，`notebooks/*/*.ipynb` 共 41 本（初級 7、中級 34）；learningArticles 與 colabNotebooks 分片各 41 份。
`LearningArticle` 現有 `sections`、`blocks`、來源及路徑；內容由指引匯出，沒有獨立實務編輯層。
證據：`frontend/src/types/index.ts:310`、`scripts/export_learning_articles.py:1`、`frontend/src/data/articleLoaders.ts:74`。
既有 `ColabNotebook` 只含章節、連結、可選 pass/warn 與 cells，尚未表達先修、資料授權、rubric 或執行版本。
證據：`frontend/src/types/index.ts:448`、`scripts/export_colab_metadata.py:25`。
`committed_review.json` 的 41 筆 execution 與 semantic 狀態均為 ok；這是既有報告內容，並非本次重新執行結果。
現有複查會略過 TODO、去除 shell/magic，缺依賴可記 skipped；不能直接升格為本規格的完整驗證。
證據：`scripts/review_committed_notebooks.py:64`、`:87`；限制已有 `playbook/pipeline-reference.md:369` 記載。

本次優先補足「會辨識名詞，仍不會做決策」的落差：從指引概念出發，讀例子、修錯誤、做實作並說明取捨。
不把指引已談過的主題一律判為缺漏；`gapStatement` 必須指出缺的是可操作步驟、反例、遷移任務或評量。
例如 mid-s3c9 已說明不平衡評估，新增價值是可重現的比較、資料切分紀律與業務閾值決策。

## 2. 內容分層與來源所有權

| 層 | 唯一來源與責任 | 前端呈現 |
|---|---|---|
| 官方指引 | 現有 PDF → guideContent；遵守 OCR 與 publication overlay 流程 | 原文、頁面與既有 `/guide` |
| 閱讀重組 | 現有 learningArticles；由指引衍生 | 保留 `/articles/:articleId` |
| 實務單元 LearningUnit | `content/learning/units/<unitId>.json` 與其 `bodyRef` Markdown | `/learn/:unitId` |
| 主題專題 Project | `content/learning/projects/<projectId>.json` | `/projects/:projectId` |
| 實作 Lab | `content/learning/labs/<labId>.json` 與 notebook 單一來源 | `/labs/:labId`、外部 Colab |

章節 title、subject 與導覽必須由 `toc_manifest.json` 解參照；作者只填 `chapterRefs`，不得維護另一份章節表。
`TopicRef={name,vocabularyHash,id?}` 沿用 `data/topics/topics.json` 受控名稱；MVP 不另造英文 topic ID。
目前確認名稱含「評估指標」「類別不平衡」「資料洩漏」「交叉驗證」；未收錄主題先走原詞彙審核流程。
`GuideRef` 必須保存原文版本與區塊快照；block ID 只對該 `sourceHash` 有意義，重建後要重新驗證。
實務教學、示意資料與作者推論顯示「實務補充」「示範資料」；對外命名沿用專案既有不變量。
來源有錯時在補充中說明限制並走原文校正流程，禁止為了配合案例直接改 generated 指引。

## 3. LearningUnit 作者介面

所有新物件沿用共用 Envelope；下列欄位是 LearningUnit 的必要領域欄位，不另定生命週期。

| 欄位 | 契約與最低要求 |
|---|---|
| `title`, `summary`, `levelIds` | 繁中標題、80–180 字導讀、適用等級 |
| `chapterRefs`, `topicRefs`, `guideRefs` | 至少 1 個合法章節、1 個受控主題及1個可解析指引引用 |
| `gapStatement` | 指引已有內容、缺少的實務能力、補充如何填補；每項附引用 |
| `objectives[]` | 2–4 個 `{id, action, condition, criterion, assessmentIds}` |
| `prerequisites[]` | `{kind:'unit'|'skill', ref, diagnosticPrompt, remediationRef}`；不得形成 unit 循環 |
| `estimatedMinutes` | 整數 10–30；是規劃時長，試學後校正 |
| `bodyRef` | 同一 units 目錄的 UTF-8 `.md`，禁止可執行 MDX、任意 HTML/script |
| `sections[]` | `{id,kind,bodyAnchor,objectiveIds,claimIds}`；引用 Markdown 唯一 heading anchor |
| `claims[]` | `{id,kind:'source'|'editorial'|'example',text,sourceRefs}`；事實性主張要有來源 |
| `assessments[]` | `{id,kind,prompt,objectiveIds,expectedEvidence,rubricId}` |
| `rubrics[]` | `criteria[]` 明確列得分條件與失敗例；rubric ID 必須可解析 |
| `labRefs`, `projectRefs` | 可為空；發布存在連結時必須引用同一 release 中可用物件 |

objective 禁止只有「了解／熟悉／掌握」；改成「給定混淆矩陣，計算召回率，誤差小於 0.001」。
至少一個 objective 要求分析或決策，至少一個 assessment 要求自行產出，而非只選答案或執行範例。
前測 2–3 題用於指出先修補救連結；無帳號模式不把前測未過作成強制鎖課。

每個 body 必須依序具備以下 section kind；順序由 schema 關聯驗證器檢查：

1. `context`：工作情境、輸入、限制、要交付的決策，以及指引定位。
2. `concept_bridge`：公式或原理對應程式變數、資料欄位與考題判斷。
3. `worked_example`：完整小例；先提出預測，再展示步驟、輸出與解釋。
4. `guided_practice`：提示漸退的 2–3 步任務；提示與解答可個別展開。
5. `independent_practice`：改變資料、成本或條件；不只把範例參數換名字。
6. `misconceptions`：至少 2 個「錯法 → 可觀察症狀 → 修正理由」的反例。
7. `assessment_reflection`：rubric、自評證據、限制、下一步與來源。

每個圖／表需有文字等價說明，程式碼可複製，公式保留可讀表示；手機版不能只靠 hover 取得提示。
外部工具步驟必須標示查核日；若平台介面改版，核心教學仍能由 `.ipynb` 下載於本機 Jupyter 完成。

## 4. 主題專題：把單元組成完整交付

Project 是有工作成果的學習序列；不是文章 tag 集合，也不能只列閱讀連結。
必要欄位：`brief`、`chapterRefs`、`topicRefs`、`unitRefs`、`labRefs`、`milestones[]`、`deliverables[]`、`rubric`。
`milestones[]` 含 `{id,title,requiredUnitIds,task,deliverableIds,acceptanceCriteria}`，必須形成有序且無循環的依賴圖。
`deliverables[]` 含 `{id,format,requiredFields,maxBytes,rubricCriterionIds}`；格式限文字／CSV／PNG／本機 notebook。
專題 rubric 同時評估技術正確、解釋、決策依據、限制；不得以最佳 leaderboard 分數替代教學目標。
MVP 不上傳使用者檔案到本站；成果保存在使用者 Colab／本機，網站提供檢核表與本機進度。

## 5. 第一條完整路徑：不平衡分類與防資料洩漏

這是共同 MVP 的唯一完整垂直範例；3 個單元＋1 個 Lab＋1 個 Project，最後接 10 題主題診斷。
主章節：`{levelId:'middle',subjectId:'mid-s3',chapterId:'mid-s3c9'}`，名稱由 manifest 解析。
次章節：`middle/mid-s2/mid-s2c4`；初級入口可引用 `junior/s1/s1c3`，不改官方先後順序。
既有主章定位證據：`data/中級/toc_manifest.json:477`。
指引例子：`block-70`／pageIndex 154 談全預測負類仍有 95% accuracy；`block-148`／158 談不平衡策略。
交叉驗證標題是 `block-167`／159，anchor 為 `4交叉驗證`；以上索引皆為零起算 PDF pageIndex。
證據：`frontend/src/generated/guideContent/中級-guide3/mid-s3c9.json:1305`、`:2694`、`:3017`。
實作時填當前 GuideRef `sourceHash`；正文引用短句可核對，路由 fallback 為 `/guide/mid-s3/mid-s3c9`。

| 順序與固定新 ID | 可量測目標 | 學習成果 |
|---|---|---|
| `unit-split-before-fit` | 找出 3 個洩漏位置且修正；驗證 fit 僅用 train row IDs | 切分圖、Pipeline、fit 範圍證據 |
| `unit-imbalanced-classification` | 手算 precision/recall/F1 誤差 ≤0.001；指出 accuracy 的限制 | 混淆矩陣、多指標比較 |
| `unit-threshold-decision` | 用 validation 成本選 threshold；提交可重現決策與限制 | 成本表、閾值、測試結果 |
| `lab-imbalanced-classification` | 在新 kernel 產生完整評估報告，並完成獨立任務 | `metrics.json`、`decision.md` |
| `project-imbalanced-classification` | 回答「是否先上線告警試點，依據是什麼」 | 1 頁決策摘要及證據附件 |

情境為設備異常告警；資料完全合成、不含個資，列代表獨立設備的一次觀測，正類代表需要檢查的異常。
不宣稱示範可以推估真實故障率；如果延伸為同設備多次觀測，必須另教 group/time split，不能沿用隨機切分。
先修：Python 函式、DataFrame 篩選、分類任務、分數計算；每項提供前測與既有文章補救連結。
示範資料固定 2,000 列、8 個數值特徵、5% 正類；預先產生 60/20/20 train/validation/test row ID manifest。
合成 seed 42；資料一旦發版以 bytes/checksum 為準，不能因上游套件升級靜默重生不同 fixture。

完整 worked example 先使用人工指定的 400 筆混淆矩陣：TP=12、FN=8、FP=18、TN=362。
正類為異常；accuracy=0.935、precision=0.4、recall=0.6、F1=0.48，與全負類 accuracy=0.95 對照。
這些是可手算教學數值，不冒充尚未執行的模型輸出；scikit-learn 的 matrix 列為實際、欄為預測，要標清楚。
引導任務：先分割，再於 train fit 缺失值處理／標準化／LogisticRegression；用 DummyClassifier 作 baseline。
附錯法示範：全資料先 fit scaler、加入事故後才取得的欄位、使用 test 挑 threshold；每個都要解釋哪種資訊流洩漏。
錯法區明示用途，不能把不正確流程接進正式評估結果；模型數值未變差也不能當作沒有洩漏。
Pipeline 可避免轉換在錯誤子集上 fit，但不能防止不合法特徵或錯誤切分；教學須同時檢查資料語意。
參考：[scikit-learn 官方常見陷阱](https://scikit-learn.org/stable/common_pitfalls.html)（查核 2026-09-07）。

獨立任務將 FN 成本設為 20、FP 成本設為 1，計算 validation 每筆平均成本 `(20*FN+FP)/N`。
threshold 候選固定 `[0.05,0.10,...,0.95]`；成本相同依 recall 高者，再依 threshold 小者決定。
先凍結模型、資料切分與 threshold，再讀 test 結果一次並寫報告；不因 test 失望回頭調參。
test 中為了課堂自評可見答案；「一次」是教學規範與報告紀錄，公開 notebook 無法提供防作弊隔離。
獨立變式要求成本改為 FN=5，重新提出 validation 決策並比較；不能保證新 threshold 必定不同。
反思至少回答：正類比例改變會影響什麼、低成本是否代表可上線、真實部署還缺哪些資料與驗證。

Project 里程碑：M1 資料與切分契約 → M2 baseline/指標報告 → M3 validation 閾值選擇 → M4 最終測試與試點建議。
主要成果 `metrics.json` 必含 dataChecksum、splitHash、modelConfig、threshold、confusionMatrix、指標、成本與 seed。
`decision.md` 必含目標、資料限制、方案比較、建議與驗證下一步；不得將合成數據結果寫成真實績效承諾。
依 `QuestionRef` 選 3–5 題現有官方來源作考點連結；重新核對題文與答案後才進 published 單元。
已查到的候選來源鍵含 `jr_1151_s1:jr_1151_s1_q40`、`jr_1151_s1:jr_1151_s1_q6`、`mid_1141_s3:exam3_q19`。
它們目前只是既有 topic assignments 中的候選，不能以標籤紀錄代替逐題審查；不在本文件複製題文。
10 題新主題診斷按 3／4／3 分配上述單元，至少 3 題情境判斷、2 題指標計算；依模擬契約去重與審核。
這是跨章學習診斷，前端不得冠以某一官方考卷或宣稱正式測驗配額。

## 6. Lab 與 notebook 單一來源

LabSpec 使用共用 Envelope，必要領域欄位如下；具體 JSON schema 由實作者依資料契約建立。

| 欄位 | 規則 |
|---|---|
| `unitRefs`, `chapterRefs`, `topicRefs`, `objectiveIds` | 跨檔完整性必驗，至少連 1 個單元 |
| `sourceNotebookRef` | 唯一 `.ipynb` 來源：`notebooks/labs/<labId>.ipynb` |
| `environment` | pythonVersion、lockRef、lockHash、kernelName、runtimeProfile、seed |
| `datasets[]` | `{resource:ResourceRef,hash,version,fallbackResource?}`；來源 metadata 由 `data/resource_catalog.json` 解參照，禁止在 Lab 重複維護 |
| `executionPolicy` | cpuOnly、maxMemoryMb、cellTimeoutSeconds、totalTimeoutSeconds、networkPolicy |
| `steps[]` | step ID、phase、cellIds、objectiveIds、estimatedMinutes、expectedArtifacts |
| `checks[]` | check ID、objectiveIds、artifactRef、predicate、tolerance／bounds、severity |
| `rubric`, `reflectionPrompts` | 要求理由與產出；不是 Run All 成功紀錄 |
| `artifacts` | 建置填 starter/solution URL、SHA256、版本與 size；不得手填漂移連結 |

來源 notebook 保存完整解答及明確 cell metadata；`metadata.learning` 至少含 labId、revision、cellId、phase、objectiveIds。
允許 phase：`setup`、`worked`、`guided`、`independent`、`check`、`reflection`；cellId 跨重排維持穩定。
解答 code cell 另有 `starterSource`；派生 starter 以明確字段置換，禁止用字串搜尋 TODO 猜哪些 cell 要刪。
Markdown 提示與完整答案分設 cell，以 `audience:'both'|'solution'` 控制；共有文字／程式碼只改單一來源。
starter 不保留答案輸出、execution_count 或解答 metadata；solution 不保留機密或執行者本機路徑。
未完成 starter 合法呈現「待完成」；所有共用 setup/worked cells 仍須可執行，公開 check 明確回報未完成。
不能藉略過整段 TODO 使 setup 中真實 NameError 被當作通過；starter 健康與作業完成是兩個結果。
`expectedArtifacts` 中提交檔案由學生程式產生；評量 check 使用獨立重新計算，不相信學生自行填的 pass 欄位。

輸出路徑：`frontend/public/labs/<labId>/<revision>/{starter,solution}.ipynb`，以及輕量 Lab 前端分片。
這兩份 `.ipynb` 是要進 git 的審核派生靜態輸入；每次來源改動需重產並比對，禁止分別手工維護。
Colab URL 使用 `https://colab.research.google.com/github/<owner>/<repo>/blob/<commit>/<path>`。
`<path>` 指向上述已提交檔，`<commit>` 是包含它的 Git commit；由站台 build metadata 注入，不嵌回 notebook 造成自我雜湊。
不能只產生 gitignored `docs/` 中的 notebook 卻生成 GitHub blob URL；不可取用 mutable main 作已驗證版本的識別。
Google 官方提供從 GitHub 開啟 notebook 的示範；固定 commit 是本系統為追溯所作的設計選擇。
參考：[Google Colab GitHub 範例](https://github.com/googlecolab/colabtools/blob/main/notebooks/colab-github-demo.ipynb)（查核 2026-09-07）。

## 7. 環境、資料與可重現性

MVP 基準為 CPU、2 vCPU／4 GB、整本執行 ≤5 分鐘、單 cell ≤60 秒；此為 CI 驗收預算，不是 Colab 資源保證。
核心教學不可要求 GPU、付費 API、私人資料集、Drive mount 或外部帳密；進階選修另標前提且不影響核心完成。
Python minor 與依賴必須在實作時選一組實測相容版本，寫入 committed lock（含 transitive exact pins/hash）。
每個 lab 可共用環境 lock；鎖檔位置用 `lockRef` 引用，CI image digest 與 lockHash 要寫入驗證證據。
Colab 預裝環境會變；setup 顯示實際版本並安裝核准依賴，如需重啟則寫清楚；不宣稱可以鎖住 Google VM 版本。
CI 在精確環境驗收，Colab 另做相容 smoke；安裝不相容須顯示可操作修復／本機環境說明，不默默裝 latest。
所有隨機來源指定 seed；split、模型、numpy 及任務自建 generator 分別明示；圖表與計時不做 byte equality。

優先採可再散布的微型資料或作者生成 fixture；本案例先核准合成資料授權，再提交固定 CSV 與產生器。
資料集唯一來源登錄為既有 `data/resource_catalog.json` 的 resource；Lab `datasets[]` 只保存 ResourceRef、hash、version 與可選 fallbackResource。
catalog 解參照後的資料集欄位必含 license、licenseRef、provenance、sha256、bytes、fixtureRef、schema，以及產生器版本／原始來源。
schema 需定義欄位型別、label 語意、允許缺失與預期列數；Lab 可在 `checks[]` 保存本教學額外的切分、比例或評量條件，不能重複來源 metadata。
授權缺失、無法確認再散布或 checksum 不符一律阻擋發版；「網路可下載」不能代替授權紀錄。
Lab revision 鎖定 catalog 資料集 version/hash，與 notebook/source 共同進 release；MVP fixture ≤5 MB，單 notebook ≤2 MB，較大資料列入後續設計再處理。
catalog 的 fixtureRef 使用已提交本地檔；下載 URL 若存在需固定版本、SHA256；Lab 執行策略設定 30 秒 timeout、至多 2 次 retry。
CI 執行前把核准資料複製到沙箱，執行期禁外網；Colab 支援從公開固定版本抓同檔或手動上傳同 checksum fixture。
發布提供 notebook＋fixture＋lock 的下載包；資料來源斷線時仍可透過本機 Jupyter 在預備環境執行。
離線 fixture 保障資料不必即時下載，不表示 Colab 服務或第一次依賴安裝能離線運作。
外部 API 類課題須有明示的錄製回應 fixture；不可用 fixture 結果宣稱實際模型服務延遲或真實準確率。

## 8. 三種驗證與發布閘門

`nbformat.validate` 檢查 notebook 格式結構；不執行、不證明數學或教學正確。
實作者必須明確呼叫 validation 並處理 ValidationError，生成穩定 cell IDs，禁止只用 json.loads 代表通過。
參考：[nbformat 官方 API](https://nbformat.readthedocs.io/en/latest/api.html#nbformat.validate)（查核 2026-09-07）。
`nbclient.NotebookClient` 在全新 kernel 按順序累積執行，保留實際 IPython 語意、cell 錯誤與輸出。
指定 `kernel_name`、工作目錄、timeout、`allow_errors=False`；刻意錯誤示範以預期 exception assertion 捕捉。
禁止全域 allow_errors 或把缺套件視為通過；沒有完成的執行結果為 inconclusive，不能當成功。
參考：[nbclient 官方執行文件](https://nbclient.readthedocs.io/en/latest/client.html)（查核 2026-09-07）。

| Gate | 必須存證 | 阻擋條件 |
|---|---|---|
| L0 來源與結構 | source/lock/data hashes、nbformat、所有 cross refs | 非合法 notebook、引用失效、授權缺失 |
| L1 starter 健康 | setup/worked 實際 cells、placeholder 未完成結果 | 非預期錯誤、漏掉必要 setup、洩出解答 |
| L2 solution 執行 | 每 cell 狀態／耗時、乾淨 kernel、環境 digest | error、timeout、缺依賴、非核准外網 |
| L3 結果正確 | 各 objective 對應的自動 check 與 artifact | 錯公式、洩漏、輸出不符、check 未執行 |
| L4 教學語意 | 獨立 reviewer 按 rubric 審完整文字＋code＋output | 說明不符、證據不足、目標無評量、反例誤導 |
| L5 發布可用 | source hash 綁定、連結路徑、Colab smoke、手機閱讀 | 舊 review、GitHub 檔案不存在、必要步驟不可操作 |

L3 判定優先使用不變條件：train/test row IDs 不交集、fit rows ⊆ train、test 未參與 threshold 搜尋。
固定混淆矩陣的計算使用絕對誤差 1e-6；列數、類別比例、schema 與 splitHash 精確相等。
模型輸出 metrics 要有限且在 [0,1]；precision／recall／F1 從 matrix 重算，不能只檢查落在寬鬆區間。
threshold 必須是 validation 成本最小者並符合 tie-break，測試指標使用凍結方案獨立重算。
模型品質上下界由首個 reviewed reference run 產生，附數據與模型版本；不得在執行失敗後為求通過放寬門檻。
不強制模型每次贏過 baseline；若教學要求改善，必須為核准 fixture 先量測並審查該穩定條件。
至少以 3 個 fault injection 驗證 check 能拒絕：全資料 fit、把 test 當 validation、precision/recall 顛倒。
語意 reviewer 要看完整 cell；超長可切片但顯示截斷與未審範圍，no-response／部分審查均不算通過。

CI 將 notebook 當不可信程式：PR 僅跑無 secrets、token 唯讀、無憑證的臨時 runner；checkout 關閉 persist credentials。
執行用非 root、無 host mounts／Docker socket、限制程序數/記憶體/CPU/磁碟的沙箱，執行期禁網路並設定整體 timeout。
依賴預備階段只讀已核准 lock，核准可執行套件及 pinned image；安裝期也無 secrets，PR 不能寫共享可信 cache。
禁止以 `pull_request_target` checkout PR notebook 執行；有發布權限的 job 不執行 PR 產物、不得信任自報通過的 artifact。
release 應在受信任 workflow 重新核算來源雜湊／驗證結果，不因 notebook 自寫 `approved=true` 取得發布資格。
參考：[GitHub Actions 官方安全參考](https://docs.github.com/en/actions/reference/security/secure-use)（查核 2026-09-07）。

## 9. 評量、完成狀態與外部環境

| 評量項 | 比重 | 可接受證據 |
|---|---|---|
| 資料與切分紀律 | 30 | row ID 清單、fit 範圍驗證、洩漏反例解釋 |
| 指標與計算 | 25 | matrix、手算／程式一致、多數類 baseline 比較 |
| 閾值與決策 | 25 | validation 成本表、凍結參數、test 報告 |
| 反思與限制 | 20 | 至少 2 個適用限制、下一步資料／試點計畫 |

rubric 自評建議門檻 80/100；資料洩漏未修或錯誤指標仍使用時即需重做，不以其他項目補分。
自動 check 最多證明已實作的可計算條件；反思與決策由公開 rubric 指引，MVP 無可信自動閱卷服務。
starter／solution 都在公開 repository，學生能看答案；可用提示漸進改善學習，但不能宣稱隱藏解答或防作弊考試。
本站閱讀／下載不需帳號；前往 Colab 後由學生使用自己的 Google 帳號與執行環境，本站不代登入。
Colab VM 與使用者帳號相關，閒置與資源限制會影響可用性；保存 notebook 不等於保存 VM 所有檔案與環境。
參考：[Google Colab 官方 FAQ](https://research.google.com/colaboratory/faq.html)（查核 2026-09-07）。

本站沒有可靠的 Colab 作答回傳契約；點擊「開啟 Colab」只記 opened，不記 executed／passed。
MVP completion 只採使用者自填已完成，存 local progress 並明示「自評完成」；不得顯示「系統認證通過」。
可選後續本機 `lab-result.json` 匯入須驗 schema、size ≤100 KB、已知 lab/revision、欄位白名單與純文字顯示。
匯入結果標 `unverified_import`；可竄改，不能提升為可信成績，也不能攜帶 HTML、檔案路徑執行或伺服器 callback。
`labId + revision` 綁定進度；新版可提示重做，保留舊版完成日期，不把舊版完成複製成新版合格。

## 10. 版本、失效與撤回

unit、lab、project 的 revision 與依賴快照共同進 release；任一 body、notebook、lock、fixture 改動使相關 review 失效。
外部來源保存 URL、查核日期、擷取摘要 hash 與 `reviewDueAt`；需依賴該來源的事實過期便進待複核清單。
單純 URL 暫時失聯不等於已發布事實錯誤；維持引用快照、標示狀態，新的 release 依審核規則決定是否可發布。
若確認錯誤、授權撤回或有害程式，對應物件轉 retired 並以撤回紀錄標 reason/replacementRef；索引停止推薦／開啟。
嚴重撤回時保留說明 tombstone；從新站台 release 移除可下載問題版本，對歷史 commit／學生複本不宣稱能遠端收回。
資料或套件新版本用新 revision 驗證；禁止修檔但保留原 sourceHash、沿用舊 Colab smoke 日期。
現有 41 本維持既有入口；轉新系統先登記 `legacy_unverified` 遷移資格，逐本補齊 L0–L5 才列入新版 Lab 目錄。

## 11. 建議內容 backlog 與最小驗收

排序欄位：`guideGap`（0–3）、`teachability`（0–3）、`examEvidence`（0–2）、`cost`（1–3）及證據引用。
先看指南缺口與可教性，歷屆考點只提供支持；可採 `3*guideGap + 2*teachability + examEvidence - cost` 作初排，再編輯審核。
以下是待 gap audit 的候選順序，未完成逐題語意審查，不是考題預測、正式覆蓋率或已承諾產量。

| 優先 | 主題與章節候選 | 真正要補的能力／CPU 交付 |
|---|---|---|
| P0 | 不平衡分類＋防洩漏：mid-s3c9、mid-s2c4 | 完成 §5 的比較、修錯、決策 |
| P1 | 資料清理：s1c2、mid-s2c4 | 缺失／重複／型別契約與清理前後品質報告 |
| P1 | POC 與 ROI：s2c3、mid-s1c6 | 成本假設、敏感度表、停止／擴大試點判準 |
| P2 | RAG 檢索評估：mid-s1c3 | 小型本地文字集、TF-IDF 檢索、引用正確率；明示僅檢索基線 |
| P2 | 超參數與驗證：mid-s3c10 | train/validation 紀律、搜尋成本、錯誤樂觀估計反例 |

內容審核欄位必須記錄排序所用指引 anchor 與核對過的 QuestionRef；沒有考點證據可填 0，不臆造支持題。
P0 端到端驗收：從 `/guide/mid-s3/mid-s3c9` 開實務補充，完成三單元，看到來源頁／提示／rubric，能返回原章。
同一路徑可開 Project／Lab，下載 starter 與 fixture，對固定 commit 開 Colab；乾淨 CPU 環境 solution 通過 L0–L5。
grader 的三個 fault injection 皆失敗；未完成 starter 顯示待完成；只點 Colab 不能改成完成，自評需使用者明確操作。
至少一名未參與寫作的試學者依 starter 完成成果、回報實際分鐘與卡點；評審核對 objective 是否被成果支持。
新來源變動時已發布引用不靜默漂移；過期 review、遺失 fixture、來源被撤回，各有可重現阻擋／tombstone 測例。
增量實作需保留原 41 本入口；涉及 frontend／JSON 跑 build，涉及 pipeline 跑 alignment，正式發版依原 13 項驗收。
