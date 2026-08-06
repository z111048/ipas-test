<!-- 2026-08-02: 新增。學習指引高精度 OCR 重新校正的任務計畫（一次性文件，完工後移入 playbook/backups/）。 -->
<!-- 2026-08-06: 填掉 §3 決策（OCR 與校正已實際執行完畢），新增 §7 記錄成果位置與待接工作。
     §4 階段 0 之後的步驟尚未開始；本專案目錄除了新增一份初級勘誤表 PDF 之外都沒動。 -->

# 06 — 學習指引 OCR 重新校正（任務計畫）

**狀態**：**OCR 與校正已完成（2026-08-06）；轉接回本專案的工作尚未開始** — 見 §7。
成果在另一個專案：`/home/james/projects/paddleocr-test/output/ipas*_ocr/`，
完整交接文件 `paddleocr-test/HANDOFF_ipas學習指引_2026-08-06.md`。
**性質**：一次性專案計畫，不是常規制度。完工後移到 `playbook/backups/`，把學到的規則寫回
`pipeline-reference.md`。

**目標**：用高精度 OCR 工具取代現行 Gemini 2.5 Flash vision，重新解析 5 份學習指引共 706 頁，
提升 `guideContent` 的文字保真度（表格、公式、圖說、程式碼），讓下游出題品質跟著上去。

---

## §1 標的清單（2026-08-02 盤點）

| key | 級別 | 檔名關鍵字 | 頁數 | 章節數 | 現有 page_*.json |
|---|---|---|---|---|---|
| guide1 | 初級 | 科目1_人工智慧基礎概論 | 71 | 4 | 71 ✅ |
| guide2 | 初級 | 科目2_生成式AI應用與規劃 | 62 | 3 | 62 ✅ |
| guide1 | 中級 | 科目1人工智慧技術應用規劃 | 168 | 9 | 168 ✅ |
| guide2 | 中級 | 科目2大數據處理分析與應用 | 182 | 13 | 182 ✅ |
| guide3 | 中級 | 科目3機器學習技術與應用 | 223 | 12 | 223 ✅ |
| | | **合計** | **706** | **41** | 706 |

PDF 位置：`data/{level}/pdfs/`。每個 cache 目錄另有 `page_index.json` 與 `summary.json`
兩個非頁面檔（新 OCR 若不產出這兩檔，先確認 `parse_guides.py` 不依賴它們——目前的
`load_chapter_pages_vision` 只 glob `page_*.json` 並跳過 `page_index.json`）。

**必須一起處理**：`data/中級/pdfs/AI應用規劃師(中級)_學習指引勘誤表_1150410_*.pdf`（7 頁，
已抽取為 `data/中級/extracted/errata.json`）。新 OCR 完成後，勘誤內容要套用或至少標註，
否則校正得再準也是準確重現了錯誤原文。

---

## §2 關鍵介面契約（這決定了工作量有多小）

下游**完全不需要改**，只要新 OCR 產出同格式的檔案落在同位置：

```
data/{level}/pages_cache/{key}/page_NNN.json
```

每檔的 JSON 欄位（見 `scripts/parse_guides.py:372` `load_chapter_pages_vision`）：

| 欄位 | 型別 | 用途 | 是否必要 |
|---|---|---|---|
| `idx` | int | 0-based 頁序，組裝時用來對齊 PDF 頁 | **必要** |
| `markdown` | str | 該頁正文 Markdown | **必要** |
| `headings` | list | 該頁偵測到的標題 | 必要（可空陣列） |
| `type` | str | 頁面類型（正文/練習頁等） | 必要 |
| `usage` | obj | token 用量計費紀錄 | 可省（僅記帳用） |

`parse_guides.py` 的偵測邏輯是：`pages_cache/{key}/` 存在 → 走 vision mode；不存在 → 退回
regex mode。所以**只要能寫出這個格式，換任何 OCR 工具都不必動 parse_guides 以後的任何一支腳本**。

→ 開工第一步不是選工具，是寫一支 `scripts/ocr_extract.py`（或改寫
`pdf_vision_extract.py` 加 `--engine`），把新工具的輸出轉成上表格式。

現行實作參考：`scripts/pdf_vision_extract.py`
（`MODEL = gemini-2.5-flash`、`page_to_png_bytes(scale=2.0)` ≈ 144 dpi）。
渲染解析度偏低是現行品質瓶頸之一，新工具若吃圖片，scale 建議先試 3.0–4.0。

---

## §3 決策（2026-08-06 已定案並執行完畢）

1. **選哪套 OCR？** → **PaddleOCR-VL 3.6.0，在 RunPod RTX 4090 上跑**，
   流程沿用 `paddleocr-test` 專案（該專案 CLAUDE.md 有完整的死鎖對策與參數）。
   實測 716 頁 4.87 秒/頁、**總計 $0.90**、零死鎖重啟。繁體準確率高（見 §7 校正數據）、
   表格輸出 HTML `<table>`、公式輸出 LaTeX、圖片抽成 `imgs/*.jpg`。
2. **輸出格式** → 每頁同時有 Markdown（`page_NNNN.md`）與**帶座標的 JSON**
   （`page_NNNN_res.json` 的 `parsing_res_list[]`：`block_label` / `block_bbox` / `block_content`）。
   座標資訊保留在來源端，轉接層先只取 `markdown`（現行 schema 沒有吃座標的欄位）；
   未來若要做前端原頁對照，資料已經在那裡不必重跑。
3. **標題偵測誰做？** → **尚未定案，這是唯一還沒決定的一題**，見 §7 末。
4. **範圍** → **5 份全做，另加 2 份勘誤表**（中級那份原本就在計畫內；初級那份是這次
   核對官方頁面才發現本機缺、已補下載）。共 **7 份 716 頁**，未採 pilot 分階段。
5. **舊快取** → 決定照原建議做：整包備份到 `data/{level}/pages_cache_gemini_backup/`
   再開跑（`pages_cache/` 是 gitignored，刪了救不回、重建花錢；備份約 3.2 MB）。
   **但這步還沒執行**——轉接工作尚未開始，`pages_cache/` 目前完全沒動，見 §7 第一步。

---

## §4 執行步驟（決定完之後照這個順序）

### 階段 0 — 建立基線（不動任何資料）
```bash
python3 scripts/verify_data_alignment.py --level 初級
python3 scripts/verify_data_alignment.py --level 中級
cd frontend && npm run build     # 確認零 TS 錯誤
```
- 兩者現在若已有 warn/fail，**先記錄下來**，否則之後分不清是舊問題還是新 OCR 造成的。
- 備份舊快取（見 §3.5）。
- 中級 `data/中級/guide/subject{1,2,3}_guide.json.bak`（6/8–6/9 的 supplement 產物）
  先跟現版 diff 一次，確認裡面有沒有刻意策展、不能被重跑沖掉的內容。

### 階段 1 — 轉接層 + Pilot（單科）
1. 寫 `scripts/ocr_extract.py`，輸出符合 §2 schema。
2. 先跑 10 頁（挑含表格、公式、程式碼、圖說的頁），與備份的舊快取逐頁對照。
3. 品質不達標就回到 §3.1 換工具，不要硬著頭皮跑完 706 頁。
4. 達標後跑完整一科 → `parse_guides.py --level X --subject N` → 目視檢查章節 JSON。

### 階段 2 — 全量重跑
1. 5 份全跑 OCR。
2. `parse_guides.py`（逐級別逐科）。
3. `render_guide_page_images.py --level X --all`（原頁截圖，若 PDF 沒換其實可跳過）。
4. 中級勘誤表內容套用（§1）。

### 階段 3 — 下游重建（順序不可調換）
```bash
uv run python3 scripts/export_guide_outline_data.py --all-levels   # ⚠ 見下方警告
# 跑完立刻補回 s1c4 的兩個手動 heading 修正（腳本在 pipeline-reference.md §10）
```
接著依 `pipeline-reference.md` §1–§2 重建 `frontend/src/generated/guideContent/`，
再視情況重跑 §2 的品質審核（audit → compare → supplement → LLM review）。

### 階段 4 — 驗收
- [ ] `verify_data_alignment.py` 初級＋中級皆通過（或不劣於階段 0 基線）
- [ ] `cd frontend && npm run build` 零 TS 錯誤
- [ ] 41 章節在前端 GuidePage 全部可開、無空章節、無破圖
- [ ] 抽驗 10 頁：表格結構、公式、程式碼區塊比舊版好而非壞
- [ ] s1c4 兩個手動修正確實還在
- [ ] `guide_exercises` / 章節練習題引用的講義片段仍能對上（引文若對不上要重跑對齊）

---

## §5 風險與不可逆點

1. **`export_guide_outline_data.py` 不帶 `--all-levels` → 中級 `guideContent/` 被 rmtree 永久刪除。**
   （CLAUDE.md 不變量 3）
2. **`pages_cache/` 是 gitignored**：不先備份就 `--force` 重跑，舊的 Gemini 結果永遠拿不回來，
   之後想 A/B 只能重付一次錢。
3. **s1c4 手動修正每次重跑都會被沖掉**，必補。
4. **下游連動廣**：guideContent → 章節練習題 → 精選 100 題的引文對齊，
   都可能因為講義文字變動而失準。階段 4 最後一條驗收就是在擋這個。
5. **中級 guide JSON 的 `.bak`**：裡面若有人工策展內容，全量重跑會覆蓋。階段 0 先 diff。

---

## §6 現況備忘（開工時可直接引用）

- 其他資源已齊備、無須動：歷屆試題 12 份、官方樣題 2 份、簡章 1 份。
- 題庫產物：初級 13 檔、中級 16 檔，本次不主動重生成，只在階段 4 驗收引文對齊。
- 前端 `frontend/src/generated/` 約 21 MB，其中 `guideContent/` 8.5 MB 是 GuidePage 真正讀的來源，
  **不是** `data/*/guide/*.json`（雙軌，改一邊不影響另一邊）。
- 未追蹤目錄 `data/中級/exam_pages_cache/` 與本任務無關，是考題 vision 快取。
- 資料 pipeline 最後活動：2026-06-16。

---

## §7 OCR 成果與待接工作（2026-08-06 追加）

### 成果在哪裡

`/home/james/projects/paddleocr-test/output/<stem>_ocr/`，逐頁檔案是
`pages/page_NNNN/page_NNNN.md` 與 `page_NNNN_res.json`，另有全書 `merged.md`。
原始頁面圖 `paddleocr-test/input/<stem>_imgs/page_NNNN.png`（288 DPI）。

| paddleocr-test stem | 頁數 | 本專案 key |
|---|---|---|
| `ipas初級_科目1_人工智慧基礎概論` | 71 | 初級 `guide1` |
| `ipas初級_科目2_生成式AI應用與規劃` | 62 | 初級 `guide2` |
| `ipas中級_科目1_人工智慧技術應用規劃` | 168 | 中級 `guide1` |
| `ipas中級_科目2_大數據處理分析與應用` | 182 | 中級 `guide2` |
| `ipas中級_科目3_機器學習技術與應用` | 223 | 中級 `guide3` |
| `ipas中級_學習指引勘誤表` | 7 | 中級 `errata` |
| `ipas初級_學習指引勘誤表` | 3 | **無**（見下方「兩個新增事實」） |

頁碼對應直接：`page_NNNN` 就是 PDF 第 NNNN 頁（1-based），轉成 schema 的 `idx` 要減 1。

品質數據（校正後）：公式經 KaTeX 與 MathJax 兩個獨立引擎全量渲染**零解析錯誤**；
簡體字從 751 個降到 8 個（僅 4 個實際位置，且那 4 處經查證是原稿本來就印簡體，
包含參考書目的日文出版社名「株式会社」）。

### 待接工作（照這個順序，前兩步不可跳）

1. **§4 階段 0 基線** — `verify_data_alignment.py` 兩級 + `npm run build` 先記錄現況；
   備份 `pages_cache/` 到 `pages_cache_gemini_backup/`（§3.5）。**目前完全沒做。**
2. **寫轉接層** `scripts/ocr_extract.py` — 讀 paddleocr-test 的逐頁 md，輸出 §2 schema 到
   `data/{level}/pages_cache/{key}/page_NNN.json`。下游一支腳本都不必改。
3. 之後照 §4 階段 2–4 走（含 `export_guide_outline_data.py --all-levels` 與 s1c4 手動修正）。
4. **兩份勘誤表的套用/標註**（§1 的要求，現在是兩份不是一份）。

### 唯一還沒定案的決策（§3.3 標題偵測）

新 OCR 給的 `block_label`（`doc_title` / `paragraph_title`）**語意不可靠**——實測會把粗體引言
標成 `paragraph_title`，同一種章標題有時是 `doc_title` 有時是 `paragraph_title`。
**建議**改用內容規則判章：`^第[一二三四五六七八九十百0-9]+章`，
即 `paddleocr-test/scripts/build_viewer_data.py` 的 `build_toc()` 已經在用的那套。
以這批書實測抽出的章節項目數為中級 33 / 38 / 36、初級 17 / 15，與 §1 記載的 41 章
（僅計正式章）數量級相符。**動手前請使用者確認這條路線。**

### 兩個新增事實

1. **官方有一份初級勘誤表，本機原本缺**，已補下載至
   `data/初級/pdfs/AI應用規劃師(初級)學習指引勘誤表11404_20251222101819.pdf`（3 頁，已 OCR）。
   `extract_pdfs.py` 的 `REFERENCE_PDFS_BY_LEVEL` 目前只有中級 errata，
   要補 `'初級': {'errata': ...}` 條目它才會進 pipeline。
   （這是本次唯一動到本專案目錄的事——新增一個 PDF 檔，沒有改任何程式或資料產物。）
2. 官方頁面其餘檔案與本機檔名逐字相符（5 份學習指引、12 份歷屆試題、2 份樣題、簡章），
   只有歷屆試題檔名被下載工具截掉尾端的 `.11.20)`，內容對應正確。

> 教訓 2026-08-06：`check_opencc_damage.py` 這類「非台灣標準用字」掃描器報的 auto 規則
> 不可直接 `--fix`。根因：這批學習指引原稿自己就印「分佈」（中級科目2：分佈 274 次、
> 分布 0 次），照 auto 規則改成「分布」會偏離原稿。規則：PDF 有文字層時，一律先用
> 文字層查原稿實際印什麼再決定；簡繁校正也用同一原則（工具見 `paddleocr-test/scripts/
> verify_simplified_against_pdf.py`，替換字取自原稿而非 opencc 轉換表）。
