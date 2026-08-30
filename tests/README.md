<!-- 2026-08-30: 同步考題 14 卷／715 題、初級樣題 70／中級樣題 45，並記錄逐頁 direct-view gate。 -->
# 自動化測試

2026-08-29 新增。在此之前這個專案**一支自動測試都沒有**，驗收只靠
`npm run build` 與 `verify_data_alignment.py`。

促成原因：把考試作答紀錄從「陣列索引」改成「question id」時，那兩條都驗不到
「勾選狀態有沒有對到正確的題」——build 會過、資料對齊也會過，但使用者可能答 A 卻記到別題。

## 13 項驗收，一個入口

```bash
uv run python tests/run_all.py                 # 全部，約 4–5 分鐘
uv run python tests/run_all.py --skip-browser  # 僅 10/13 靜態診斷；不得當成 release pass
```

跑的是這 13 項——**前 10 項是靜態／資料防線，後 3 項是端對端**：

| # | 項目 | 驗什麼 |
|---|---|---|
| 1 | `test_resource_catalog` | catalog schema、14 份考卷、route、題數、3 份 PDF 資源及完整 gallery（初級勘誤：3 page＋5 table＝8 assets）、legacy 資產鍵、565/565 詳解題都有 signed-off 概念標註 |
| 2 | `test_repo_portability` | production 腳本無工作站絕對路徑，subprocess 有明確 cwd |
| 3 | `test_pipeline_output_safety` | Guide producer 所有權、完整 OCR cache、staging/rollback、partial export；appendix boundary、題目 ID／card 保留及 production 5 檔 179 題／179 cards |
| 4 | `test_exam_ocr_repairs` | 14 份／715 題（初級樣題 70、中級樣題 45）production 修復、code-image annotation、逐頁 direct-view SHA/inventory、reference v2 provenance／完整發布、盲答圖檔 bytes cache、原始 sidecar 不變與 promotion blocker |
| 5 | `test_track_a_ocr_repairs` | 閱讀頁 169 筆精確 inventory＋3 筆 publication overlays＋3 筆 structure contracts、跨頁 provenance、公式、來源圖與導覽搜尋一致性；不依賴本機 cache |
| 6 | `test_track_b_ocr_fixes` | 出題來源 78 筆（71 OCR／抽取＋2 來源數式＋5 provenance）、固定 canonical SHA、5 筆 deterministic page-type override、插入型勘誤與 TB-006 immutable OCR 重建、guide_sections exact rebuild、兩個出題入口拒絕 stale payload、cache 深比對與 fresh-clone 契約 |
| 7 | `npm run build` | tsc 零錯誤 + vite 產出 |
| 8 | `verify_data_alignment --level 初級` | 資料對齊 toc_manifest 與 resource catalog（SSOT） |
| 9 | `verify_data_alignment --level 中級` | 同上 |
| 10 | `audit_resources` | 8 類確定性審核（含三軌 `ocrSemantics`），任一 FAIL 就擋 |
| 11 | `tests/test_exam_flow.py` | 考試：作答、計分、背景計時補正、到期自動交卷 |
| 12 | `tests/test_practice_flow.py` | 章節練習：作答 + localStorage 保存與還原 |
| 13 | `tests/test_routes.py` | 29 條正常路由 + 3 條預期錯誤路由 |

Fresh checkout 不含 gitignored 的 `pages_cache`、`exam_pages_cache`、`page_clean`、`page_extract`、
`guide_tree` 與 Track A reading snapshot。Release gate 因此以 committed canonical／signature
產物為必要層；本機完整 cache 存在時會追加來源重建深比對，partial cache 一律失敗。
Fresh checkout 的考題 sidecar 是 0/715；維護者本機即使有部分 coverage（2026-08-30 盤點為
150/715）也只供
診斷，不是 release input。Promotion 是獨立 gate，必須 715/715 且零 mismatch 才會放行；
coverage 未滿時 `--promotion-gate` 預期阻擋，不影響 verified production JSON。

`data/exam_visual_review/*.json` 是 14 卷逐頁 direct-view 的 committed 報告；
`verify_exam_visual_reviews.py` 以 PDF／question SHA 與完整 page／qid inventory fail-closed，並由考題 repair／audit gate 串入。

三支端對端也可以單獨跑（`python3 tests/test_exam_flow.py`）。

前置：`uv sync && uv run playwright install chromium`

三支都會**自己啟停 dev server**（port 5199）。⚠️ 已經有 server 佔著那個 port 就直接用它、
且結束時不會關它（`devserver.py:63-66`）——所以本機另外開著 dev server 時，測的是那一支。
要指定外部 server 用 `IPAS_TEST_BASE=http://127.0.0.1:5173`。

## test_exam_flow.py 驗什麼

點選作答、鍵盤作答、覆寫、不波及別題、題號盤標記、未答數，
最後**用題庫算出的預期分數**去比對成績頁（Q1=A 正解 A、Q2=D 正解 D → 2 對 = 4 分）。
分數對得上，才算真的驗到 id-keyed 的計分路徑；只檢查「有出現數字」是驗不到錯位的。

## test_routes.py 驗什麼

catalog 展開的 14 份考卷與其餘正常路由逐一開啟，檢查無 console error / pageerror、
內容不是白畫面，且沒有「載入失敗」「NaN」「undefined」「找不到」。另驗證未知 route、
無效科目與無效考卷各自顯示明確的找不到狀態；等待條件也會排除 Suspense skeleton。

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
