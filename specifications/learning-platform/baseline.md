# LP-000 現況基線與範圍

盤點時間：2026-09-07（Asia/Taipei）  
基準 commit：`e35a312d08dfc2eb0e30a7635a46b1dcc1293654`（branch `main`）

這份文件固定 P0 開工前的現況，供後續變更判斷退化。完整 13 項基線套件在任何新 runtime 實作落檔前完成；本工作包只新增本文件，沒有修改程式、canonical JSON、OCR inventory 或簽核紀錄。

## 起始工作樹

執行基線前工作樹已非乾淨狀態，內容是前一輪已交付但尚未提交的學習平台規格：

- `README.md`：modified（`git diff --stat` 為 4 insertions）。
- `specifications/learning-platform/`：untracked，包含 `README.md`、`architecture.md`、`content-and-labs.md`、`data-contracts.md`、`implementation-plan.md`、`review.md`。

上述內容不是 LP-000 測試或盤點產生的 runtime 改動；基線完成後新增的 `progress.md` 與本文件 `baseline.md` 也屬該 untracked 目錄。

## 重新盤點快照

以下數量以小切片 `jq`、檔名清冊及 canonical 題檔逐檔計數取得，沒有整讀超過 50 KB 的 JSON。

| 項目 | 現況 | 權威／盤點來源 |
|---|---:|---|
| 章節 | 41（初級 7、中級 34） | `data/{level}/toc_manifest.json` 的 `subjects[].chapters[]` |
| 主題文章 | 41（初級 7、中級 34） | `frontend/src/generated/learningArticles/index.json` |
| 文章閱讀路徑 | 6 | 同上；`ai-foundations`、`genai-practice`、`data-analytics`、`ml-engineering`、`ai-solutions`、`governance-risk` |
| Colab notebook | 41（初級 7、中級 34） | `frontend/src/generated/colabNotebooks/index.json` 的 `total`／`byChapter`，並以 `notebooks/{level}/*.ipynb` 檔名清冊核對 |
| topics | 181 | `data/topics/topics.json` 的 `topics`；狀態 `signed-off`，簽核日 2026-08-31（`phraseCount` 3034） |
| 公告考卷 | 12 份、600 題 | `data/resource_catalog.json`；兩級各 6 份、每份 50 題，並逐一對 canonical `questions` 陣列計數 |
| 樣題 | 2 份、115 題 | 初級 70、中級 45；catalog 與兩份 canonical `sample_exam.json` 實際計數一致 |
| 考卷合計 | 14 份、715 題 | catalog 及 14 個 canonical 題檔逐檔核對 |

數量是本 commit／工作樹的盤點快照，不得複製成新的永久常數；後續仍由 manifest、catalog、topics 及各自 exporter 提供資料。

## MVP 引用有效性

兩個 ID 都直接取自 `data/中級/toc_manifest.json`，不是新章節定義：

| 角色 | chapter ID | manifest 標題 | PDF 頁碼範圍 | 既有文章／notebook |
|---|---|---|---|---|
| primary | `mid-s3c9` | 模型訓練、評估與驗證 | 150–162 | 兩者皆存在 |
| secondary | `mid-s2c4` | 數據收集與清理 | 56–62 | 兩者皆存在 |

## 沿用與新增矩陣

| 領域 | 沿用的來源／能力 | P0–P1 候選新增 | 邊界 |
|---|---|---|---|
| 章節身份與導覽 | `build_manifest.py` → `toc_manifest.json` | MVP 所需精確 `GuideRef` anchor／alias | 不複製章節表，不改 Track A 原文 |
| 概念身份 | `data/topics/topics.json` 的既有 name 與簽核詞彙 | MVP reference adapter；stable ID 完整遷移留到 LP-210 | 不另建同義 topic 清冊 |
| 考題身份 | `resource_catalog.json`、既有題檔、來源頁與 `QuestionRef` namespace | MVP 3–5 題經審來源 mapping、10 題診斷內容 | 不以未審題補數，不改既有題號或答案 |
| 文章與路徑 | 41 篇文章、6 條閱讀路徑及既有 routes | 三個 LearningUnit、一個 Project、一條混合 LearningPath | 補充內容是新 authored domain，不回寫 Track A／B |
| Lab | 41 本既有 notebook 與 Colab metadata | `lab-imbalanced-classification` starter／solution、review 與 runtime report | 開啟 Colab 不算執行通過；MVP 僅免費 CPU、無付費 API |
| 前端與保存 | React/Vite 靜態站、章節作答 localStorage、既有考試計分 | 新內容 loader／route、版本化 progress、匯出／匯入 | 不新增帳號、後端同步、付款或伺服器 notebook runner |
| 發布與驗收 | 既有 13 項 release gate、GitHub Pages 流程 | learning schema/reference/content/lab gates | 新 gate 加入既有流程，不取代 OCR 與 runtime gate |

## 基線測試證據

所有 subprocess 的 cwd 都是 `/home/james/projects/ipas-test`。使用既有環境並把 uv cache 指到 `/tmp/ipas-uv-cache`；沒有使用 `--skip-browser`。

1. 沙箱內執行 `UV_CACHE_DIR=/tmp/ipas-uv-cache uv run python tests/run_all.py`：2026-09-07 19:14:47–19:16:01 +08:00，外層 74 秒，exit 1。10/13 靜態項目通過；三項 browser 測試都在 `tests/devserver.py` 建立 `socket.socket()` 時原樣回報 `PermissionError: [Errno 1] Operation not permitted`，未進入產品流程。原始 stdout/stderr 與 exit metadata：`/tmp/ipas-learning-baseline.sandbox.log`。
2. 經核准在沙箱外重跑同一個完整命令：2026-09-07 19:16:37–19:20:35 +08:00，外層 238 秒，exit 0；runner 報 `13/13 通過，共 247s`。三項端對端均實際執行：`test_exam_flow` 56.6s、`test_practice_flow` 33.4s、`test_routes` 94.9s。原始 stdout/stderr 與 exit metadata：`/tmp/ipas-learning-baseline.log`。

第二次完整執行是 current baseline：13/13 通過。第一輪失敗只證明受限沙箱不能建立測試所需本機 socket；在該沙箱中屬 browser gate 的環境阻擋，但不是產品失敗，也不阻擋目前 LP-000，因相同 commit 已在允許 socket 的環境完整通過。未觀察到其他既有測試失敗。

## 已知既有界線

- 13 項通過證明目前 committed canonical／signature、build、資料對齊與既有瀏覽器流程符合 gate；它不替未審來源頁證明 OCR 語意正確。新 PDF 或 sidecar promotion 仍需依既有逐頁核對與三軌 gate。
- Fresh checkout 不帶 gitignored OCR／版面 cache；完整 cache 可追加深比對，partial cache 會失敗。考題 sidecar coverage 未滿 715/715 時，promotion gate 預期阻擋，但不阻擋已驗證 production JSON 或 LP-000。
- 本基線沒有執行候選 learning CLI、notebook 乾淨 runtime 或新內容語意審查；這些能力尚未實作，必須由後續工作包各自提出可重算證據，不能由本次 13/13 推定已通過。
