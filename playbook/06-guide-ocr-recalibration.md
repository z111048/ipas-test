<!-- 2026-08-02: 新增。學習指引高精度 OCR 重新校正的任務計畫（一次性文件，完工後移入 playbook/backups/）。 -->
<!-- 2026-08-06: 填掉 §3 決策（OCR 與校正已實際執行完畢），新增 §7 記錄成果位置與待接工作。
     §4 階段 0 之後的步驟尚未開始；本專案目錄除了新增一份初級勘誤表 PDF 之外都沒動。 -->

# 06 — 學習指引 OCR 重新校正（任務計畫）

**狀態**：**階段 0–2 完成（2026-08-06）；階段 3 刻意未跑，勘誤表未套用** — 見 §8。
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

---

## §8 轉接執行紀錄（2026-08-06，接在 §7 之後）

### 一個推翻 §2 前提的事實：guideContent 不是從 pages_cache 來的

`data/{level}/guide/` 與前端 `guideContent/` 是**兩條來源不同的軌**，§2 的「介面契約」只涵蓋前者：

| | Track A（前端 GuidePage 讀的） | Track B（出題用） |
|---|---|---|
| 來源 | `data/{level}/page_clean/{key}/pages/*.json`（`clean_pdf_page_text.py`，PDF **文字層** + bbox） | `data/{level}/pages_cache/{key}/*.json`（本次換成 PaddleOCR） |
| 產物 | `export_guide_outline_data.py` → `frontend/src/generated/guideContent/` | `parse_guides.py` → `data/{level}/guide/subject*_guide.json` |
| 消費者 | GuidePage | `generate_questions` / codex 出題與審核 prompts / colab / audit |

所以換掉 `pages_cache/` **只提升出題品質，前端閱讀頁一個字都不會變**。
`export_guide_outline_data.py --all-levels`（§4 階段 3）這次**刻意沒跑**：它的輸入 `page_clean/`
本次完全沒動，跑了是 no-op，卻要冒 §5.1 的 rmtree 風險與 s1c4 手動修正被沖掉的成本。
未來若要讓前端也吃到新 OCR，那是另一件事——得改 Track A 的來源，不是重跑 export。

### 已完成

1. **階段 0 基線**：兩級 `verify_data_alignment` 皆 passed（初級 2 科 7 章、中級 3 科 34 章）、
   `npm run build` 零 TS 錯誤。舊快取備份在 `data/{level}/pages_cache_gemini_backup/`（711 檔 3.2 MB），
   guide JSON 備份在 `data/{level}/guide_before_ocr_backup/`。
   中級 `.bak` diff 過：各科僅 1–3 章有差異，是 supplement 的清理，無不可重生的人工策展。
   **這些備份目錄未 tracked 也未 gitignored**，`git add .` 會誤收，刪了也救不回——要處理。
2. **轉接層 `scripts/ocr_extract.py`**（新增）：706 頁全數轉入 `pages_cache/`。
3. **`parse_guides.py` 兩級重跑**：41 章全部走 vision mode、全部有內容。

### 標題規則（§3.3 決策定案：方案 C）

決策前查證到的關鍵事實：**`pages_cache` 的 `headings` 欄位下游沒有任何人讀**
（`load_chapter_pages_vision` 只用 `idx`/`markdown`/`type`；章節切分靠 SSOT manifest + PDF 頁碼標）。
真正有下游影響的是 **markdown 正文裡的 `#` 標記**——它會進 `guide/subject*.json` 的 content，
成為出題與審核 prompt 的輸入。所以規則以正文標記為主，headings 欄位順帶產出。

規則是**不對稱**的（用全 716 頁實測校準）：

- 已有 `#` 的行 → 信任它是標題，只重算層級。PaddleOCR 的層級會亂（把 `3.1` 標成 `###`、
  把 `（1）` 標成 `##`），改為 `第X章`/`N.N`→2、`一、`/`N.`→3、`（N）`→4、`a.`→5。
- 沒有 `#` 的行 → **只有 `a.`/`A.` 型且 ≤40 字且無句末標點才提升**。實測 plain 的
  `第X章`、`N.N` 全部是目錄行（`..... 3-3`），plain 的 `（N）` 全部是正文段落（最短也超過 40 字），
  plain 的 `N.` 幾乎全是練習頁題號——一律不提升。

已知取捨：**沒有前綴的純文字標題抓不到**（如「獨立樣本 t 檢定（Independent-samples t-test）」），
Gemini 版抓得到。全書 35 頁屬於這種（`ocr_extract.py` 的報告會列出來）。寧可漏抓不要誤判。

### 其他必須知道的處理

- **`type` 沿用備份的 Gemini 快取**（按 idx 對應），讓本次只改動 markdown 文字一個變數，
  章節組裝行為與舊版相同。同時跑一套規則判定當交叉檢查：716 頁只有 10 頁不一致，全在
  前後襯頁（目錄尾、參考書目），採 Gemini 判定。
- **插圖標籤剝除**：PaddleOCR 輸出 `<img src="imgs/...">` 114 個，指向 paddleocr-test 的本機檔，
  搬過來是死連結。原圖仍在 `paddleocr-test/output/<stem>_ocr/`，日後做原頁對照再接。
- **`parse_guides.py` 的 `_page_asset_path` 改用 `/pdf-assets/` 慣例**（原為 `/guide-pages/`）。
  原因：`/guide-pages/` 只鋪過初級（13 MB），中級沒有，重建後 verify 報 490 筆缺圖；
  而 `/pdf-assets/` 兩級齊全（初級 173 + 中級 690 張）、且是 `export_guide_outline_data.py`
  與前端（guideContent、pdfGallery）唯一在用的慣例。**前端從不引用 `/guide-pages/`**，
  `render_guide_page_images.py` 因此變成沒有消費者的腳本（未刪，但別再依賴）。

### 品質數據（新 vs 舊，41 章合計）

| | 舊（Gemini） | 新（PaddleOCR） |
|---|---|---|
| 字數 | 392,734 | 405,117（+3.2%） |
| 公式 `$…$` | 33 | **358** |
| 表格 `<table>` | 26 | 29 |
| 標題 `##`–`######` | 1,075 | 1,362 |

**舊版把「模擬考題」混進講義正文**：`mid-s3c3`、`mid-s3c12`、`mid-s2c13` 等章各掉約 20%
字數，逐字比對後確認掉的是單一整塊練習題（例：舊 `mid-s3c3` 的 source_pages 含 24–37，
把 practice 頁也算進去了）。新版正確排除。這是修正不是遺失——也代表舊的出題輸入
一直被練習題污染。

抽驗發現原稿 OCR 仍有錯字：初級科目1 p28 的「考**礎**解析」（應為「考題解析」）。

### 待接（照順序）

1. **兩份勘誤表的套用/標註**（§1、§7.4）——完全沒做。中級 `errata` 與初級新增的那份都要。
   `extract_pdfs.py` 的 `REFERENCE_PDFS_BY_LEVEL` 還缺 `'初級': {'errata': ...}` 條目。
2. 決定備份目錄怎麼處置（gitignore 或納管），別讓它們懸在未追蹤狀態。
3. `guide_exercises` / 章節練習題引用的講義片段是否還對得上（§4 階段 4 最後一條，未驗）。
4. 是否要把 Track A 也換成新 OCR ——需要改 `page_clean` 的來源，範圍比本次大。

---

## §9 Track A 遷移（2026-08-06，接在 §8 之後）

**使用者定調**：學習指引以新 OCR 為單一真相來源，前端閱讀頁也要納入，末端產物可重做。

### OCR 成果已複製進本專案

`data/{level}/guide_ocr/{key}/`（初級 6.3 MB、中級 26 MB，含 errata），
結構 `pages/page_NNNN/page_NNNN.{md,_res.json}` + `merged.md`。
**不再依賴 paddleocr-test 專案**（`ocr_extract.py` 的來源路徑已改）。
沒複製 `viewer_data/`、`logs/`、`progress.json`（paddleocr-test 自用）。

### 為什麼 Track A 是「合併」而不是「取代」

實測比對後確認 PaddleOCR **不能**取代 PDF 文字層：

| | PDF 文字層 | PaddleOCR |
|---|---|---|
| 條列符號 | 5,803 個，三層階層乾淨（• 1769 / ◦ 2028 / ○ 2004） | 1,577 個，**流失 72.8%**，塌成 ■/◆/○/• 且不一致 |
| 字元 | 原稿無損 | 抽驗有殘留錯字（侷→侗、考題→考礎）、異體字偏離（佈→布） |
| 公式 | 攤平成數學斜體碼點亂碼 | **LaTeX**，KaTeX/MathJax 雙引擎驗過 |
| 表格 | 列偵測會吃掉上下標（「H₁」） | **完整 HTML**，表頭與 rowspan 都在 |

條列符號與 x 縮排是 `guideContent` 巢狀清單深度的依據，全換 OCR 會讓閱讀頁結構退化。
所以 `scripts/merge_guide_ocr.py` 只注入 OCR 贏的那三項，一個字都不改文字層內容。

### 做了什麼

1. **`scripts/merge_guide_ocr.py`**（新增）：
   - 表格：OCR 的 `<table>` 解析成 rows（含 rowspan 展開、字面 `\n` 轉真換行），
     以 bbox IoU 比對換掉 `page_extract` 的 PDF 偵測版。**44/45 換成功**，只換不新增
     （新增的表格沒有對應 PNG 資產，前端會 404）。座標比例逐頁算（OCR 像素 / PDF point ≈ 4.001）。
   - 公式：抽出 417 個（682 行內 + 63 顯示式去重後）寫成
     `data/{level}/ocr_formulas/{key}/page_NNN.json`，格式刻意做成既有
     `collect_formula_blocks()` 吃得下的樣子，沿用 audit_cache 的注入管線。
   - 首次執行備份 `page_extract` 到 `page_extract_before_ocr_merge/`。
2. **`export_guide_outline_data.py`** 三處改動：
   - `load_audit_formula_pages()` 合併 `audit_cache` 與 `ocr_formulas`（OCR 優先、去重）。
   - 拿掉 `high_confidence_formula_for_text` 的**頁級**開關。原本「整頁都沒有快取公式才啟用」
     太寬，一頁只要有任何公式進快取，整頁其他區塊就拿不到規則表救援——這是我加了
     `ocr_formulas` 之後才暴露的退步，逐區塊的 `not block.get('formulas')` 已經夠。
   - 新增 `inject_formulas_into_markdown()`，把 `content` 裡的公式亂碼換成 `$$latex$$`（見 §10 修正 3）。
3. **`GuidePage.tsx`** 新增 `GuideTableCell`：表格儲存格原本是純文字渲染，
   OCR 表格帶 `$\mu_1 \neq \mu_2$` 會裸露成原始碼。含 `$` 的儲存格才過 KaTeX，其餘走純文字
   （保留 `whitespace-pre-line` 的換行）。
4. 重建 `page_clean` → `guideContent`（`--all-levels`）→ 補回 s1c4 兩個修正。

### 結果

| | 舊 | 新 |
|---|---|---|
| guideContent 檔數 / blocks / headings | 64 / 16,997 / — | 64 / 16,998 / 完全一致 |
| block 公式（閱讀頁實際渲染的） | 200（相異 latex 96） | **273（相異 128）** |
| 表格儲存格 | 1,385（含 LaTeX 0） | 1,409（含 LaTeX 92） |

`verify_data_alignment` 兩級通過、`npm run build` 零 TS 錯誤。

### 已知未收斂

`content` 欄位的公式覆蓋只做到約六成（詳見 `pipeline-reference.md` §10 修正 3）。
`content` 不是閱讀頁渲染來源，但概念圖卡頁與兩支 export 腳本會讀。
舊版留在 `frontend/src/generated/guideContent_before_ocr_merge/` 可隨時比對。

### 待接

1. **兩份勘誤表的套用/標註**——仍未做（§7.4）。`data/{level}/guide_ocr/errata/` 已有 OCR 成果，
   `extract_pdfs.py` 的 `REFERENCE_PDFS_BY_LEVEL` 還缺 `'初級'` 條目。
2. 題庫（章節練習題、精選 100 題）依使用者決定**先不重出**，只需驗引文是否仍對得上。
3. 四個備份目錄（`pages_cache_gemini_backup`、`guide_before_ocr_backup`、
   `page_extract_before_ocr_merge`、`guideContent_before_ocr_merge`）目前未追蹤也未 gitignore，
   要決定納管或忽略。

---

## §10 勘誤表套用（2026-08-06，接在 §9 之後）

§1 要求的「勘誤內容要套用或至少標註」——兩份都做了，操作手冊寫在
`pipeline-reference.md` §10 修正 4，這裡只記錄決策與結果。

### 三支新腳本

| 腳本 | 做什麼 |
|---|---|
| `build_errata.py` | 勘誤表 OCR → `data/{level}/errata_corrections.json`（28 筆：初級 7、中級 21） |
| `apply_errata.py` | 套進 `pages_cache`（Track B）與 `page_extract`（Track A） |
| `apply_manual_guide_fixes.py` | 把 §10 修正 1、2 從「複製貼上執行」變成腳本 |

### 三個關鍵決策

1. **不改 `guide_ocr`**。那是 OCR 的忠實紀錄，要能對回原稿印的內容（原稿印錯也照實還原）。
   勘誤是官方事後更正，屬於疊加層，套在兩條軌的轉接產物上。代價是重跑轉接層會沖掉勘誤，
   所以執行順序有硬性要求（見 pipeline-reference §10 修正 4）。
2. **用印刷頁碼限縮範圍**。勘誤表給的是「3-25」這種印刷頁碼，先用 `page_extract` 的
   `page_label` 換成頁序，替換只在那一頁進行。「反饋→回饋」這種單字更正若全書套用會誤傷。
3. **全有或全無**。一筆勘誤的片段沒有全部定位到就整筆不動——只改一半會產生新舊混雜的段落，
   比不改更糟。這讓覆蓋率數字變難看，但那是誠實的數字。

### 結果

28 筆中：**7 筆兩軌完整套用**、5 筆只成功套用其中一軌、其餘需人工處理
（清單 `data/{level}/errata_unresolved.json`，含 `reason` 欄位）。
片段層級 Track B 套用 19 處、Track A 11 處。
已驗證勘誤流到最終產物且無舊字殘留（如「個性化推薦→個人化推薦」、「即時反饋→即時回饋」）。

覆蓋率有限的原因不是程式問題，是**勘誤表對「原內容」的轉錄與講義實際文字有出入**
（標點、條列符號、斷行），以及整段改寫類的勘誤本來就難以自動定位。

### 踩到的三個坑（都已修，留紀錄避免重犯）

1. **只正規化「針」不正規化「草堆」**：`flexible_pattern` 把要找的片段做了 NFKC
   （全形逗號→ASCII），卻拿去比對未正規化的原文，全部落空。改成兩邊都正規化、
   保留索引對照再映射回原字串替換（`normalize_with_map` / `find_span`）。
2. **片段互相覆蓋**：相鄰更正各自展開上下文後會咬到對方，先替換的把後面的比對基準改掉。
   修法有兩層——`context_pairs` 合併重疊區段，`apply_pairs` 一次掃描定位後由**後往前**替換。
3. **同一片段在每個 block 重複套用**：`apply_to_page_extract` 逐 block 套用時沒把已套用的
   片段移除。

### 仍待處理

1. `errata_unresolved.json` 的人工處理（初級 6 筆、中級 15 筆）。其中值得優先看的是
   **初級 3-31 第 3 題答案由 (B) 改為 (A)**——這是答案更正，錯了會直接影響作答，
   而它目前**沒有**自動套用成功。
2. `extract_pdfs.py` 的 `REFERENCE_PDFS_BY_LEVEL` 仍缺 `'初級': {'errata': ...}` 條目。
3. 題庫引文對齊未驗（依使用者決定不重出題）。
4. 五個備份目錄未追蹤也未 gitignore。

---

## §11 交接（2026-08-06 收工）

**分支 `guide-ocr-recalibration`，9 個 commit，工作區乾淨，尚未 push、尚未合回 main。**

驗證狀態：`verify_data_alignment` 兩級通過、`npm run build` 零 TS 錯誤、
s1c4 手動修正在位、勘誤抽驗 7 項全部「新版出現、舊字零殘留」、
`apply_errata.py` 連跑兩次結果完全一致（冪等）。

### 這輪完成了什麼

| commit | 內容 |
|---|---|
| `cdadbbc` | 716 頁 OCR 納入為 SSOT（`data/{level}/guide_ocr/`，33 MB） |
| `9568bc7` | 兩軌轉接層（`ocr_extract.py` / `merge_guide_ocr.py`）＋ s1c4 修正腳本化 |
| `4157aff` | 勘誤表解析與套用 |
| `97a38fd` | 重建講義資料與 guideContent |
| `ca9125b` | 文件 |
| `cd0856f` | **完整階層樹**（`guideHierarchy.json`，1,207 節點、最深 6 層） |
| `4fba648` | 側欄改用階層樹，修掉章頁面的空連結 |
| `35a034b` | **出題改小節粒度**（370 區塊，解決「整份講義只有 40% 進得了出題流程」） |
| `a29a997` | 勘誤人工校對，28 筆中 26 筆已套用 |

### ⚠️ 重跑時的硬性順序（最容易踩）

勘誤是**疊加層**，套在兩軌的轉接產物上；重跑轉接層會把勘誤沖掉。完整順序：

```bash
# Track B（出題）
python3 scripts/ocr_extract.py
# Track A（前端閱讀頁）— 會先備份 page_extract 到 page_extract_before_ocr_merge/
python3 scripts/merge_guide_ocr.py
# 勘誤（自動 + 人工覆寫），冪等
python3 scripts/apply_errata.py
# 下游
uv run python3 scripts/parse_guides.py --level 初級   # 中級同樣跑一次
python3 scripts/clean_pdf_page_text.py --level {lv} --key {key}   # 逐 key
uv run python3 scripts/export_guide_outline_data.py --all-levels  # ⚠ 必帶 --all-levels
python3 scripts/apply_manual_guide_fixes.py                        # ⚠ 緊接著跑
python3 scripts/export_guide_hierarchy.py
python3 scripts/export_guide_sections.py
python3 scripts/verify_data_alignment.py --level 初級 / 中級
cd frontend && npm run build
```

要從乾淨狀態重跑 `merge_guide_ocr.py`，得先把 `page_extract_before_ocr_merge/`
複製回 `page_extract/`——那支腳本只在備份不存在時才備份，直接重跑會疊在已合併的結果上。

### 待接工作（依價值排序）

1. **驗證題庫引文對齊**（唯一還沒做的驗收項）。講義文字這輪大幅變動（公式、表格、
   勘誤、練習題不再混進正文），`guide_exercises` 與精選 100 題引用的講義片段可能對不上。
   先寫個比對腳本量規模，再決定要不要重跑對齊。**這是合回 main 前該做的。**
2. **決定要不要用 `--by-section` 重出題庫**。基礎設施好了但沒跑過，需要 `ANTHROPIC_API_KEY`
   且量不小（初級科目1 光是 `--count 3` 就 111 題）。使用者這輪明確說先不重出。
3. **剩下 2 筆勘誤**（理由見 `pipeline-reference.md` §3，兩筆都需要看原始 PDF 才能決定）。
4. **`extract_pdfs.py` 的 `REFERENCE_PDFS_BY_LEVEL` 仍缺 `'初級': {'errata': ...}`**。
5. **`guideContent` 的 `content` 欄位公式涵蓋只到約六成**（見 `pipeline-reference.md` §10 修正 3）。
   `content` 不是閱讀頁的渲染來源（GuidePage 走 `blocks`），但概念圖卡頁與兩支 export 會讀。
6. **前端還沒用到階層樹的其他可能**：完整目錄頁、麵包屑。資料都在 `guideHierarchy.json`，
   節以下是既有章節頁的錨點，路由不用動。
7. 四個備份目錄（含 193 MB 的 `page_extract_before_ocr_merge/`）已 gitignore，
   確認無誤後可刪；其中兩個備份的是 tracked 檔案，git 歷史本來就有。

### 這輪學到、寫進制度的三件事

- `data/{level}/guide/subject{N}_guide.json` **有兩個生產者**互相覆寫
  （`parse_guides.py` 寫 OCR 版、`export_question_generation_data.py` 寫 guideContent 版）。
- 重跑 `export_guide_outline_data.py` 會沖掉手工補的東西。s1c4 已腳本化；
  2026-06-10 手工補的 98 處 `$$` 公式已改為自動產生但只涵蓋約六成。
- 比對中文 PDF 文字一定要**兩邊都 NFKC 正規化**（全形標點、CJK 相容字「數」是 U+F969），
  而且**替換要映射回原字串**。只正規化其中一邊會全部落空——這輪踩了兩次。
