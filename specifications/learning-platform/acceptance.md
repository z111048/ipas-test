# MVP 獨立 runtime／read-back 驗收

驗收日期：2026-09-07。驗收者：`/root/p0_baseline`。本頁只記錄直接讀碼、fresh-root 重建及實際命令結果；作者自述不作為通過證據。

## 目前結論

狀態：**MVP runtime／read-back 驗收通過；production promotion 仍由真人 L5 擋住**。

- CLI 文件與實際 `--help` 介面一致；未發現 playbook 將 preview 說成正式發布。
- fresh-root preview 可只靠可版控來源與 base uv 環境重建，連跑兩次 release ID 與 36 個輸出檔 bytes 相同；沒有讀取 authoring staging，也沒有產生 production `current.json`。正式 review 補記後，完整 gate 又以最終來源在 temporary root 重建並確認相同隔離條件。這不代表 Git 已提交；交接時新增來源仍含 untracked 檔案。
- Lab 作者依獨立 L4 初審修正六項實質缺口後，L0–L3 與外部 fixture 重算通過；原獨立 reviewer 第二輪 L4 通過並留下 hash-bound review，L5 仍未執行。
- frontend／IndexedDB 初讀發現的 blocking 缺口已由 frontend owner 修正；黑盒 state 與完整 learning frontend E2E 均已在最終 frozen source 通過。
- 變更後完整 `tests/run_all.py` 實跑 20/20，包含 production build、初／中級 alignment、舊三支與新兩支真 Chromium E2E，沒有使用 `--skip-browser`。

## 規格與操作文件 read-back

已讀 `progress.md`、`mvp-runbook.md`、`content-review.md`、`tests/README.md`，並核對本輪 `playbook/pipeline-reference.md` 與 `playbook/pipeline-script-catalog.md` diff。

`pipeline-reference.md` 只增加到 MVP catalog／progress 的路由；`pipeline-script-catalog.md` 所列五支 CLI 都存在。以 `UV_CACHE_DIR=/tmp/ipas-uv-cache uv run --group learning-lab python <script> --help` 實查：

- `validate_learning_content.py --all --check --assessment-at`
- `build_learning_content.py --preview --check/--dry-run --assessment-at --lab-assets-manifest --without-assessment`
- `generate_learning_lab.py --check`
- `verify_learning_labs.py --lab ... --profile cpu --check`
- `curate_learning_questions.py --check`

另核對 `build_learning_assessment.py --preview --check --dry-run --record-reviews --lab-assets-manifest`。Runbook 的最小 preview 命令已改成 base `uv run python scripts/build_learning_content.py --preview`；optional `learning-lab` group 只留給 Notebook 維護／執行。

Backend 契約、引用、發布與 assessment 以 `uv run python -m unittest tests.test_learning_contracts tests.test_learning_references tests.test_learning_publication tests.test_learning_assessment` 獨立執行：41 tests OK／16.467s，exit 0。這項結果不涵蓋瀏覽器狀態或 Lab L4。

最終內容 source 經 validator 讀得 128 個實體、`issues=[]`、`invalidReviews={}`；兩次 preview 都是 `learning-e6732041208784d31304146c`。已完成的 machine review 缺口均有 hash-bound 正式紀錄，唯一未滿足項目是 Lab 真人 L5。

## Preview 不變性與隔離

在 `/tmp/ipas-learning-fresh-root-m3an7f_f` 建立不含 `data/learning/pipeline/` 的必要來源檔複本，從 repo cwd 連跑兩次：

```bash
uv run python scripts/build_learning_content.py --preview --repo-root /tmp/ipas-learning-fresh-root-m3an7f_f
```

兩次 exit 0，release ID 都是 `learning-a095090b736e2b54c84a365d`；36 個 preview／pointer 檔案逐 byte SHA-256 map 完全相同。`stagingAbsent=true`、`currentAbsent=true`，pointer 的 `availability=preview` 且 manifest 位於 `previews/`。完整機械報告：`/tmp/ipas-learning-preview-determinism.json`；兩次 stdout：`/tmp/ipas-learning-preview-first.log`、`/tmp/ipas-learning-preview-second.log`。

上項 CLI 測試早於最後一批正式 review 紀錄。最終 20 項 gate 中的 `test_learning_assessment` 會從 real `assessment_inputs(ROOT)` 收集最終 resolver inputs，複製到新的 `TemporaryDirectory`，在沒有 `data/learning/pipeline/` 的情況下重建 preview，逐檔核 manifest hash，並確認沒有 `frontend/public/labs` 與 production `current.json`；因此最後新增的 review／evidence 也已納入 fresh-source read-back。

## Lab 獨立初審與作者修正

獨立 reviewer 的第一次 L4 是 `changes_requested`，證據在 `content/learning/evidence/lab-semantic-review.md`。初版外部 verifier 可接受空 fit IDs、虛構兩列 test 與負成本曲線，故初版 L4 不合格。

作者修正後：test score 移到 validation threshold 凍結之後；Dummy 實際 predict 並與 Logistic 結果並列；starter 只留兩個核心函式 TODO，保留完整輸出範本與 `assert_result`；兩項資料路徑 fault 會真傳 full/test dataframe；外部 verifier 從 fixture 重建模型、19 個主成本列、19 個 FN=5 列與 400 筆 test；execution report 記錄實際 Python/package versions。

實跑命令：

```bash
uv run --group learning-lab python scripts/verify_learning_labs.py --lab lab-imbalanced-classification --profile cpu
uv run --group learning-lab python -m unittest tests.test_learning_lab
uv run --group learning-lab python scripts/generate_learning_lab.py --check
uv run python scripts/validate_learning_content.py --all --check
```

結果依序為 exit 0（L0–L3 pass；starter 未完成時阻擋；三項 fault rejected）、6 tests OK／75.869s、exit 0 無 drift、exit 0 且 schema/reference issues 空。最後一項仍列出缺少的 review／execution gate，`publicationApproved=false`，沒有冒作正式發布。

## Frontend／狀態 read-back

frontend frozen 前曾發現以下 blocking findings，均已於發現時交 root 與 frontend owner修正：

1. `frontend/src/features/learning/state/repository.ts` 的 storage record 缺契約要求的 `snapshotHash`／`importedFrom`，save/import 未重算完整 snapshot hash。
2. 同檔 import 只做淺層 `schemaVersion/items` 檢查；未拒絕額外／被改造的正解欄位、未驗引用版本，不同內容另存時也未保存 `importedFrom`。
3. 初讀沒有 `BroadcastChannel`、備份匯出／預覽匯入／清除的使用者入口，且 `tests/test_learning_state.py` 不存在。
4. `SimulationPage.tsx` 的錯題回補只連到 `/learn`，沒有依該題 mapping 回到精確 Unit，再由 Unit 返回真 Guide anchor。

同時已確認的正向行為：learning routes 使用 React lazy import；索引與詳頁分開載入；DEV 讀 `preview.json`，production 只 glob `current.json`／`releases/**`；未知 entity ID 與載入錯誤顯示不同狀態；Simulation 保存 questionKey/revision/contentHash/displayed option IDs 與絕對 deadline；Lab 的下載操作與使用者自報完成是兩個操作。

修正後以 `UV_CACHE_DIR=/tmp/ipas-uv-cache uv run python tests/test_learning_state.py` 執行真 Vite／Chromium／IndexedDB 黑盒驗收：15 checks 全數通過，exit 0。測試從真實 simulation 匯出合法 envelope 後再刻意破壞，涵蓋 stored snapshot hash 篡改、額外 correctAnswer、不一致 release/pool ref、錯誤 snapshot hash、同檔重匯 dedup、衝突另存 importedFrom、重複提交 idempotent、100 筆與 projected 50 MB 上限、native `QuotaExceededError` 顯示，以及 BroadcastChannel 跨分頁唯讀。案例清單在 `tests/fixtures/learning/state/cases.json`。

## Blueprint／Pool／Analysis 非作者審查

`agent-p0-baseline` 以非作者身份重新計算由 `agent-content-labs` authored 的 MockBlueprint、MockPool 與 ExamAnalysis；授權範圍是三實體 D1 與 pool 策展完整性 A1，不包含重新審查前者 authored 的十題答案。命令 `UV_CACHE_DIR=/tmp/ipas-uv-cache uv run python /tmp/audit_assessment_review.py` 為 exit 0、21/21 checks PASS，封存證據為 `content/learning/evidence/assessment/assessment-peer-review-20260907.json`。

覆核結果為十題／十個 family 無重複、hard quota 與實際 slot assignment 都是 3／4／3、固定 seed 與 option permutation 完整；每個 pool payload 的 content/file/source/annotation hash、正解映射及既有 `agent-content-labs` 單題 D1/A1 review 均精確綁定。分析只含三份官方卷，各 50 題、母體 150；已審 5 題分布為 2／2／1，unknown 145，`exhaustive=false`、`prevalence=null`，上下界、五個原卷 route/page 與三個 Unit GuideRef 均重算一致。四筆正式 review 已讀回驗證 schema、subject hash、reviewer／author independence 及 evidence refs。

## 最終完整 gate

在 frontend 與 content source frozen 後執行：

```bash
UV_CACHE_DIR=/tmp/ipas-uv-cache uv run python tests/run_all.py
```

exit 0，20/20 通過，共 679 秒，沒有 `--skip-browser`。15 個靜態／資料 gate 包含 production `npm run build`（112.7s）、learning contracts／references／publication／assessment、初級與中級 alignment、resource audit；五個真瀏覽器 gate 依序為 exam 105.2s、practice 71.1s、routes 213.2s、learning state 35.9s、learning frontend 55.1s。完整 stdout/stderr 與 exit marker 在 `/tmp/ipas-learning-final-gate.log`，SHA-256 為 `26a230ff003a93585f8b22f2100e7a8ca087ac2523c24ae143a60c2482459794`。

`git diff --check` exit 0。README 的 20 項總數、15 static／5 browser 邊界與不得以 `--skip-browser` 當 release pass 的描述正確；表格順序已依 `run_all.py` 改為 learning backend 在 build 前，估計時間也改為本次實測 679 秒。Runbook 的 `cd frontend` 後 `npm ci`、`/#/learn` 路由及 preview／production 邊界和實際操作一致。

## 待完成

- Lab L4 已由 `/root/content_labs` 對 content hash `sha256:5bb3dc8b27d18e8d5407398445a7ea52791c2ae5d97de5d5131a63c3c319cb2b` 重做並通過；review 為 `review-lab-semantic-20260907-v1`。這不代表 L5。
- L5 人工 Colab smoke 與不可變 Git commit URL 仍屬 production blocker；本輪不得補造。
