<!-- 2026-08-07: 全檔收斂。任務主體（OCR 遷移／勘誤／引文對齊）已完成並合回 main，
     常駐規則已寫進 pipeline-reference.md（§1a 重跑順序、§3 練習題抽取陷阱、§9 教訓）。
     完整的 §1–§12 執行歷史留在 playbook/backups/06-guide-ocr-recalibration.md.bak-2026-08-07。 -->

# 06 — 學習指引 OCR 重新校正

**狀態：任務主體完成，已合回 main（2026-08-07）。** 本檔現在只留「現況 + 待接」；
執行過程、決策理由、踩過的坑寫在
`playbook/backups/06-guide-ocr-recalibration.md.bak-2026-08-07`（564 行），需要考古再開。

**要重跑 pipeline 的話不要看這裡** → `pipeline-reference.md` §1a（OCR 兩軌與完整順序）。

---

## 做完了什麼

716 頁學習指引（5 份指引 + 2 份勘誤表）改用 PaddleOCR-VL 重新解析，取代原本的
Gemini 2.5 Flash vision。成果 `data/{level}/guide_ocr/`（33 MB，committed，視為 SSOT）。

| 項目 | 結果 |
|---|---|
| OCR 成本 / 效能 | 716 頁、4.87 秒/頁、**$0.90**、零死鎖 |
| 公式 | KaTeX + MathJax 雙引擎全量渲染**零解析錯誤** |
| 簡體殘留 | 751 → 8 個（實際 4 處，經查證原稿本來就印簡體） |
| 階層樹 | `guideHierarchy.json`，1,207 節點、最深 6 層 |
| 出題粒度 | 章 → 小節，370 區塊（原本整份講義只有 40% 進得了出題流程） |
| 官方勘誤 | 28 筆中 **26 筆已套用**（剩 2 筆見下） |
| 引文對齊 | `guide_exercises` 179 題**全數**在引用頁逐字命中，0 退化 |

驗證狀態：`verify_data_alignment` 兩級通過、`npm run build` 零 TS 錯誤、
`apply_errata.py` 連跑兩次結果一致（冪等）。

## 剩下的 2 筆勘誤（都需要看原始 PDF 才能決定）

- **初級 3-27（假說檢定名詞表）**：勘誤表自己的巢狀表格 OCR 結構是壞的，「更正後」欄
  只抓到標題、表身沒抓到，無從得知官方要改成什麼。
  （PDF 文字層證實原書印的是「拒絕 H0 → Type II 錯誤（α）」，實為 Type I 之誤。）
- **中級 5-21（Recall 分母 TP+FP → TP+FN）**：`ocr_formulas` 對同頁相同 LaTeX 去重，
  Precision 的 `TP/(TP+FP)` 與 Recall 誤印的 `TP/(TP+FP)` 文字完全相同被併成一筆，
  盲目替換會把**正確的 Precision 改壞**。

## 待接工作（依價值排序）

1. **決定要不要用 `--by-section` 重出題庫**。基礎設施好了但一次都沒跑過——
   到目前為止提升的只有前處理，題庫仍是舊講義文字生出來的。
   建議先單章試跑（挑漂移最大的 `mid-s2c3`，相似度 0.739）驗證品質再決定全量。
   需要 `ANTHROPIC_API_KEY`，量不小（初級科目1 光 `--count 3` 就 111 題）。
2. **上面那 2 筆勘誤**。
3. **`extract_pdfs.py` 的 `REFERENCE_PDFS_BY_LEVEL` 仍缺 `'初級': {'errata': ...}`**
   （PDF 已下載在 `data/初級/pdfs/`，但沒進 pipeline）。
4. **`guideContent` 的 `content` 欄位公式涵蓋只到約六成**（見 `pipeline-reference.md` §10 修正 3）。
   不是閱讀頁的渲染來源，但概念圖卡頁與兩支 export 會讀。
5. **前端還沒用到階層樹**：完整目錄頁、麵包屑。資料都在 `guideHierarchy.json`，
   節以下是既有章節頁的錨點，路由不用動。
6. **四個備份目錄可清**——但 `page_extract_before_ocr_merge/`（193 MB）**先別刪**，
   它是 `verify_question_guide_alignment.py` 的舊版基線，刪了就無法區分
   「本輪造成的退化」與「本來就這樣」。

## 這個任務留給制度的東西（已寫進 pipeline-reference）

- §1a — OCR 兩軌與**完整重跑順序**（勘誤是疊加層、轉接層重跑會沖掉）。
- §3 — `export_guide_embedded_exercises.py` 的三個陷阱（頁眉黏進選項、解析吃到下一章、
  無條件頁尾收束會掉題）。
- §9 — 中文 PDF 文字比對的教訓（兩邊都要 NFKC、題幹與選項分開比、題目常跨頁）。
- §10 修正 4 — 勘誤的全有或全無策略、兩軌格式不同要各寫一筆、安全閥。
