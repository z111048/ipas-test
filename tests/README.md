<!-- 2026-11-01: 新增第 21 項 test_layout_audit（跨頁版面／文案稽核，UX 改版 Phase 0C）。 -->
<!-- 2026-10-31: 同步考題 16 卷／815 題（新增初級 115 第三次）。 -->
<!-- 2026-08-30: 同步考題 14 卷／715 題、初級樣題 70／中級樣題 45，並記錄逐頁 direct-view gate。 -->
# 自動化測試

2026-08-29 新增。在此之前這個專案**一支自動測試都沒有**，驗收只靠
`npm run build` 與 `verify_data_alignment.py`。

促成原因：把考試作答紀錄從「陣列索引」改成「question id」時，那兩條都驗不到
「勾選狀態有沒有對到正確的題」——build 會過、資料對齊也會過，但使用者可能答 A 卻記到別題。

## 21 項驗收，一個入口

```bash
uv run python tests/run_all.py                 # 全部；2026-09-07 實測 679 秒、2026-09-14 實測 797 秒（勿與其他重負載併行）
uv run python tests/run_all.py --skip-browser  # 僅 15/21 靜態診斷；不得當成 release pass
```

跑的是這 21 項——**15 項是靜態／資料防線，6 項是端對端**。原有 13 項的命令與語義不變：

| # | 項目 | 驗什麼 |
|---|---|---|
| 1 | `test_resource_catalog` | catalog schema、16 份考卷、route、題數、3 份 PDF 資源及完整 gallery（初級勘誤：3 page＋5 table＝8 assets）、legacy 資產鍵、815 題詳解的概念標註（mid_1151_s2_q39 詞彙表無對應、保留未標）、詞彙表 exact rebuild 與 id 帳本六道防線、兩份標註／`topicHeat`／`conceptGraph` 的穩定 id 與詞彙表逐筆一致且 export 精確重建、快取 v2 無損轉換與 id 優先對齊 |
| 2 | `test_repo_portability` | production 腳本無工作站絕對路徑，subprocess 有明確 cwd |
| 3 | `test_pipeline_output_safety` | Guide producer 所有權、完整 OCR cache、staging/rollback、partial export；appendix boundary、題目 ID／card 保留及 production 5 檔 179 題／179 cards |
| 4 | `test_exam_ocr_repairs` | 16 份／815 題（初級樣題 70、中級樣題 45）production 修復、code-image annotation、逐頁 direct-view SHA/inventory、reference v2 provenance／完整發布、盲答圖檔 bytes cache、原始 sidecar 不變與 promotion blocker |
| 5 | `test_track_a_ocr_repairs` | 閱讀頁 169 筆精確 inventory＋3 筆 publication overlays＋3 筆 structure contracts、跨頁 provenance、公式、來源圖與導覽搜尋一致性；不依賴本機 cache |
| 6 | `test_track_b_ocr_fixes` | 出題來源 78 筆（71 OCR／抽取＋2 來源數式＋5 provenance）、固定 canonical SHA、5 筆 deterministic page-type override、插入型勘誤與 TB-006 immutable OCR 重建、guide_sections exact rebuild、兩個出題入口拒絕 stale payload、cache 深比對與 fresh-clone 契約 |
| 7 | `test_learning_contracts` | Draft 2020-12 結構、領域 invariants、canonical hash 與 malformed payload 不 crash |
| 8 | `test_learning_references` | content、review、question 與 release 的跨檔引用完整性 |
| 9 | `test_learning_publication` | preview／published 隔離、atomic pointer、hash 與發佈 gate |
| 10 | `test_learning_assessment` | 固定 seed 組卷、hard quota、option order 與完整 golden result |
| 11 | `npm run build` | tsc 零錯誤 + vite 產出 |
| 12 | `test_learning_frontend_static` | production bundle 不含 preview pointer、正文、提示 marker 或 Lab assets；另以 `tests/frontend_checks/concept_lookup_check.cjs`（用 frontend 的 typescript 轉譯 `frontend/src/data/conceptLookup.ts` 後執行，Node 20 可跑）做 fixture 檢查，驗 `/concepts?c=` 的三段解析順序（id → 正式名稱 → previousNames，含兩概念互換名字） |
| 13 | `verify_data_alignment --level 初級` | 資料對齊 toc_manifest 與 resource catalog（SSOT） |
| 14 | `verify_data_alignment --level 中級` | 同上 |
| 15 | `audit_resources` | 8 類確定性審核（含三軌 `ocrSemantics`），任一 FAIL 就擋 |
| 16 | `tests/test_exam_flow.py` | 考試：作答、計分、背景計時補正、到期自動交卷 |
| 17 | `tests/test_practice_flow.py` | 章節練習：作答 + localStorage 保存與還原 |
| 18 | `tests/test_routes.py` | 30 條正常路由 + 2 條 `/concepts?c=` 連結相容（舊中文名改寫成 id、id 直達）+ 4 條預期錯誤路由 |
| 19 | `tests/test_learning_state.py` | IndexedDB hash/tamper、匯入衝突、idempotency、quota、storage failure 與跨分頁唯讀 |
| 20 | `tests/test_learning_frontend.py` | 真 preview 的單元、10 題續答／逾時／回補、Lab 五檔下載、分析與 375px keyboard flow |
| 21 | `tests/test_layout_audit.py` | 全部頁面（test_routes 的路由＋`/learn`、`/projects`、`/analysis/exams`、第一篇文章、404）× 1440 桌機／390 手機：無水平溢出、無 console error、無內部用語；Phase 1 檢查（h1、字級、觸控尺寸）先只回報 |

Fresh checkout 不含 gitignored 的 `pages_cache`、`exam_pages_cache`、`page_clean`、`page_extract`、
`guide_tree` 與 Track A reading snapshot。Release gate 因此以 committed canonical／signature
產物為必要層；本機完整 cache 存在時會追加來源重建深比對，partial cache 一律失敗。
Fresh checkout 的考題 sidecar 是 0/815；維護者本機即使有部分 coverage（2026-08-30 盤點為
150/715）也只供
診斷，不是 release input。Promotion 是獨立 gate，必須 815/815 且零 mismatch 才會放行；
coverage 未滿時 `--promotion-gate` 預期阻擋，不影響 verified production JSON。

`data/exam_visual_review/*.json` 是 16 卷逐頁 direct-view 的 committed 報告；
`verify_exam_visual_reviews.py` 以 PDF／question SHA 與完整 page／qid inventory fail-closed，並由考題 repair／audit gate 串入。

各支端對端也可以單獨跑，例如 `python3 tests/test_exam_flow.py` 或 `python3 tests/test_learning_frontend.py`。

學習 preview E2E 會先以 base 環境執行 `scripts/build_learning_content.py --preview`，不需要先手動生成或安裝 Lab kernel。Notebook 的乾淨 kernel L0–L3 是獨立重型門檻：

```bash
uv sync --group learning-lab
uv run --group learning-lab python tests/test_learning_lab.py
```

前置：`uv sync && uv run playwright install chromium`

舊三支端對端會**自己啟停 dev server**（port 5199）；learning flow/state 分別使用 5207/5208，test_layout_audit 用 5209。⚠️ 已經有 server 佔著對應 port 就直接用它、
且結束時不會關它（`devserver.py:63-66`）——所以本機另外開著 dev server 時，測的是那一支。
要指定外部 server 用 `IPAS_TEST_BASE=http://127.0.0.1:5173`。

## test_exam_flow.py 驗什麼

點選作答、鍵盤作答、覆寫、不波及別題、題號盤標記、未答數，
最後**用題庫算出的預期分數**去比對成績頁（Q1=A 正解 A、Q2=D 正解 D → 2 對 = 4 分）。
分數對得上，才算真的驗到 id-keyed 的計分路徑；只檢查「有出現數字」是驗不到錯位的。

## test_routes.py 驗什麼

catalog 展開的 16 份考卷與其餘正常路由逐一開啟，檢查無 console error / pageerror、
內容不是白畫面，且沒有「載入失敗」「NaN」「undefined」「找不到」。另驗證未知 route、
無效科目、無效考卷與無效概念各自顯示明確的找不到狀態；等待條件也會排除 Suspense skeleton。

`/concepts?c=` 的相容層（LP-210C）另有兩條：拿 `conceptGraph.json` 的第一個概念（不寫死名稱），
以舊的 `?c=<中文名>` 進來要看到該概念、且網址被改寫成 `?c=<id>`；以 `?c=<id>` 進來要直接命中。
概念改名時這兩條會跟著資料走，不需要改測試。

## test_layout_audit.py 驗什麼

UX 改版 Phase 0C 加入，讓每一個 UI 改動都在所有頁面、兩種寬度上一次驗完（約 2 分鐘）。

```bash
uv run python tests/test_layout_audit.py              # 全部
uv run python tests/test_layout_audit.py --only exam  # 只跑 label／route 含 exam 的
uv run python tests/test_layout_audit.py --phase1     # PENDING 也算失敗（預覽 Phase 1 完成度）
```

**ENFORCED**（失敗即 exit 1）：
- 水平溢出：`documentElement` 與 `<main>` 的 `scrollWidth <= clientWidth`。本站內容在 `<main>`
  裡捲動、不是 document，只量 document 會漏掉；失敗時列出最外層的溢出元素。
- console error／pageerror。
- `document.body.innerText` 不得含內部用語（章節／考卷內部 id、route、pipeline、已入庫、
  MOCK EXAM 等英文 eyebrow……完整清單見檔內 `BANNED_COPY`）。講義正文本來就會談 Data Pipeline、
  母體、分母，所以命中正文時**收窄 pattern、不做整頁白名單**，每個收窄決策都寫在 `BANNED_COPY` 上方的註解。

**PENDING**（`ENFORCE_PHASE1 = False`，只印 ⚠ 與每條路由的計數表）：每頁恰好一個 `<h1>`；
沒有 computed font-size < 12px 的可見文字；手機上 a／button／input／select／`[role=button]`／`[role=tab]`
至少 44×44——嵌在句子裡的 inline `<a>`（最近的 p／li／td／th／dd／dt／blockquote／figcaption
文字比連結長）豁免，checkbox／radio 量包住它的 `<label>`，收起的側欄、跳到主要內容等不在版面內的元素不計。
Phase 1 完成後把常數改成 `True`。

路由清單鏡像 `test_routes.py` 的 `ROUTES`（那支 import 時就會開跑，不能直接 import），並用 `ast`
讀 `test_routes.py` 做漂移檢查：那邊新增路由而這裡沒跟上，本測試直接失敗。文章頁取
`learningArticles/index.json` 的第一個 id，不寫死。

## 寫這類測試的兩個坑（都踩過）

**1. 不要用固定 sleep 等畫面。**
冷啟動的 vite dev server 上 `networkidle` 不代表畫完了——GuidePage 這種
動態 import 章節 JSON 的頁面要好幾秒。用「內容長度連續兩次取樣相同」判斷穩定
（`settle_text()`）。踩到時的症狀是同一條路由時過時不過（實測 912 字 vs 282 字）。

**2. 「切題後立刻作答」這個 bug，測試必須同時涵蓋短距離與長距離。**

原始症狀：方向鍵切題後立刻按數字鍵，有機率答到上一題（`ExamPage` 的
IntersectionObserver 會在平滑捲動途中改 `activeIndex`）。**已於 2026-08-29 修掉**，
修法是程式觸發的捲動一律 `behavior: 'instant'`——沒有動畫就沒有中間位置，
正確性是 by construction 而不是跟時序賽跑。

**為什麼測試要測兩種距離**：中途試過「捲動期間鎖住 scroll-spy + 固定 timeout」
來保留平滑動畫，短距離測試全綠，但那個修法其實是壞的——Chrome 的平滑捲動時長
隨距離增加（實測上限約 1534ms），長距離跳題時鎖會在動畫中途過期，錯答窗口
只是從 ~150ms 搬到 ~1050-1250ms。**只測方向鍵會讓壞修法看起來是好的。**

所以第 8 節測三組：短距離（方向鍵，0/50/150/300/600ms）、
長距離（題號盤跳第 45 題，0/150/900/1100/1300ms）、
以及一條反向測試（使用者自己捲動時 scroll-spy 仍要跟隨）——
最後那條是為了擋住「再把鎖加回來」這種退化。

同樣的 pattern 在 `PracticePage` 也有，一併修了。那邊更嚴重：
`PracticePage.tsx:215` 的 `!answers[q.id]` 讓一題只能作答一次，錯答無法覆寫，
而且會寫進 localStorage 存著。

## devserver.py

`npm run dev` 會再 spawn 一支 vite 子行程，只 `terminate()` npm 會留下孤兒佔著 port。
所以用 `start_new_session=True` + `os.killpg` 整組收掉，並在收完後確認 port 真的釋放。
