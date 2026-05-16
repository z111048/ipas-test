# iPAS AI 應用規劃師備考平台

針對 iPAS AI 應用規劃師能力鑑定（初級）的靜態備考網站，部署於 GitHub Pages。

---

## 目錄結構

```
ipas-test/
├── scripts/                      # 資料處理腳本
│   ├── build_manifest.py         # ★ 章節定義 SSOT → data/{level}/toc_manifest.json
│   ├── extract_pdf_pages_structured.py # PDF 逐頁文字 + 圖表 bbox + 裁切圖檔
│   ├── build_pdf_outline.py      # 從逐頁抽取結果建立 PDF 階層目錄
│   ├── clean_pdf_page_text.py    # 清理逐頁文字 + 重建 page_clean 目錄
│   ├── export_guide_outline_data.py # 匯出前端 PDF 目錄 metadata + 拆分內容
│   ├── export_pdf_image_gallery.py # 匯出圖表檢視頁所需 public assets + manifest
│   ├── pdf_vision_extract.py     # PDF → Gemini Vision → pages_cache + page_index.json（有 LLM）
│   ├── parse_guides.py           # pages_cache/extracted → 章節 JSON（vision/regex）
│   ├── audit_chapters.py         # 解析後 LLM 審核 → subject{N}_audit_report.json
│   ├── extract_pdfs.py           # PDF → 文字/JSON（供考題 pipeline 使用）
│   ├── parse_exams_v2.py         # JSON 表格 → 模擬考試題庫 JSON
│   ├── generate_questions.py     # Claude API → 章節題目 + 解說圖卡
│   ├── multi_ai_pipeline.py      # 多 AI 出題流水線（Gemini/Codex/Claude CLI）
│   ├── render_guide_page_images.py # 學習指引 PDF 原頁截圖 → frontend/public/guide-pages/
│   ├── verify_data_alignment.py  # 檢查 PDF / manifest / guide / questions 是否一致
│   └── build_web.py              # 呼叫 npm run build → docs/
├── frontend/                     # Vite 前端專案
│   ├── src/                      # React + TypeScript 原始碼
│   │   ├── pages/                # 頁面元件（Home、SubjectOverview、Practice、Exam、Guide）
│   │   ├── generated/            # 版控的前端靜態資料（guide outline/content、gallery manifest）
│   ├── public/                   # 版控的靜態 PDF 圖片/表格/原頁截圖資源
│   │   ├── components/           # UI 元件（layout、practice、exam、shared）
│   │   ├── store/                # Zustand 狀態管理（examStore）
│   │   ├── hooks/                # useExamTimer
│   │   ├── types/                # TypeScript 型別定義
│   │   └── constants/            # 靜態常數（guideNotices）
│   ├── public/                   # 靜態資源（favicon.ico、.nojekyll）
│   ├── vite.config.ts            # 輸出至 ../docs，@data alias → ../data/初級
│   └── package.json              # React 19、TW v4、React Router v6、Zustand v5
├── data/
│   └── 初級/                     # 初級資料（manifest 與 curated JSON 可提交；bulk 產物 gitignored）
│       ├── pdfs/                 # 原始 PDF 來源
│       ├── extracted/            # 從 PDF 萃取的文字與結構（.txt / .json）
│       ├── questions/            # 題庫 JSON（mock_exam*.json、subject*_questions.json）
│       ├── toc_manifest.json     # ★ 章節定義 SSOT（由 build_manifest.py 生成，需提交）
│       ├── guide/                # 學習指引輸出（subject{N}_guide.json、_audit_report.json 等）
│       ├── page_extract/         # 逐頁 PDF 結構抽取與圖表裁切（gitignore）
│       ├── outline/              # PDF 階層目錄分析結果（gitignore）
│       ├── analysis/             # 章節／題型分析（exam_analysis.json）
│       └── pipeline/             # multi_ai_pipeline.py 各次執行的中間產物（gitignore）
├── logs/                         # 執行 log（gitignore）
└── docs/                         # 本機 Vite 建置輸出（gitignored；GitHub Actions 會重新 build）
    ├── index.html                # 入口 HTML（434 B）
    └── assets/                   # 打包後的 JS + CSS
```

> 後續擴充中級時，在 `data/` 下新增 `中級/` 資料夾，依相同結構組織 PDF 與題庫，並於 `scripts/build_manifest.py` 的 `GUIDES_BY_LEVEL` 與 `scripts/extract_pdfs.py` 的 `EXAM_PDFS_BY_LEVEL` 補上對應資料。資料 pipeline scripts 已支援 `--level 中級`。

---

## 執行 Pipeline

### 核心目標

**依據解析的 MD 教材與官方樣張／歷屆題目，針對特定章節自動生成高品質模擬試題。**
解析品質直接決定出題品質——每頁必須正確歸入對應章節。

### 指令

從專案根目錄依序執行：

```bash
# 0. 生成章節目錄索引（僅在章節定義或 PDF 異動時需要）
uv run python3 scripts/build_manifest.py                    # 預設 初級
uv run python3 scripts/build_manifest.py --level 初級       # → data/初級/toc_manifest.json

# 0b. 逐頁保真抽取：文字 + 圖片/表格位置 + 圖表裁切
python3 scripts/extract_pdf_pages_structured.py --level 初級 --all --force
python3 scripts/clean_pdf_page_text.py --level 初級 --all
python3 scripts/export_guide_outline_data.py
python3 scripts/build_pdf_outline.py --level 初級 --all
python3 scripts/export_pdf_image_gallery.py --level 初級 --force

# ── 學習指引 Guide pipeline（Vision 提取，需 GEMINI_API_KEY）────────────

# Step 1: PDF 逐頁送 Gemini Vision（結果快取於 pages_cache/）
uv run python3 scripts/pdf_vision_extract.py --level 初級 --all       # 兩科全跑（~$2）
uv run python3 scripts/pdf_vision_extract.py --level 初級 --subject 1 # 只跑科目一

# Step 2: 組合章節 JSON
uv run python3 scripts/parse_guides.py --level 初級                   # 組合章節 JSON
python3 scripts/render_guide_page_images.py --level 初級 --all       # 產生網站用 PDF 原頁截圖

# Step 3: 解析後 LLM 審核（確認頁面→章節對應正確）
uv run python3 scripts/audit_chapters.py --level 初級 --all           # 兩科全審
uv run python3 scripts/audit_chapters.py --level 初級 --all --dry-run # 預覽 prompt
# → data/初級/guide/subject{1,2}_audit_report.json

# ── 考題 Exam pipeline ───────────────────────────────────────────────────

# 1. PDF 萃取（更換 PDF 後才需重新執行）
uv run python3 scripts/extract_pdfs.py --level 初級

# 2. 解析模擬考試題目（公告試題 / 樣題）
uv run python3 scripts/parse_exams_v2.py --level 初級

# 3. 檢查 PDF 參考、manifest、學習指引與題庫章節是否對齊
python3 scripts/verify_data_alignment.py --level 初級

# 4a. （選用）透過 Claude API 生成／補充題目（單一模型）
export ANTHROPIC_API_KEY=sk-ant-...
uv run python3 scripts/generate_questions.py --level 初級 --subject 1   # 生成科目一各章新題
uv run python3 scripts/generate_questions.py --level 初級 --subject 2   # 生成科目二各章新題
uv run python3 scripts/generate_questions.py --level 初級 --enrich      # 補充既有題目的解說圖卡欄位

# 4b. （選用）多 AI 出題流水線（需 gemini / codex / claude CLI 已安裝並完成認證）
# 注意：multi_ai_pipeline.py 使用 subprocess 呼叫外部 CLI，不需要 uv run
python3 scripts/multi_ai_pipeline.py --level 初級 --subject 1 --chapter s1c1 --dry-run  # 預覽 prompt
python3 scripts/multi_ai_pipeline.py --level 初級 --subject 1 --count 3                  # 執行科目一

# 5. 建置網站（Vite 打包 React 前端）
uv run python3 scripts/build_web.py
# 等同於：cd frontend && npm run build
```

僅更新前端 UI 時只需執行最後一步。前端開發時可用 dev server：

```bash
cd frontend && npm run dev -- --host    # http://localhost:5173/（--host 供 WSL 存取）
```

> `docs/` 是 Vite 的本機建置輸出目錄，已 gitignored。只要 `frontend/src/` 或任何資料 JSON 有變動，就重新執行 `uv run python3 scripts/build_web.py` 或 `cd frontend && npm run build` 驗證 production build；push 到 `main` 後 GitHub Actions 會重新 build 並部署。

依賴套件：

```bash
uv sync                                    # Python 依賴（pdfplumber、pymupdf、anthropic、google-genai）
cd frontend && npm install                 # 前端依賴（React、Vite、Tailwind CSS v4 等）
# multi_ai_pipeline.py 不需額外 Python 套件，但需以下 CLI 工具：
#   gemini  → https://github.com/google-gemini/gemini-cli
#   codex   → https://github.com/openai/codex
#   claude  → npm install -g @anthropic-ai/claude-code
```

---

## 腳本實作說明

### `scripts/extract_pdf_pages_structured.py`

逐頁抽取所有 PDF，保留純文字以外的版面資訊：

- 每頁輸出 `data/{level}/page_extract/{key}/pages/page_NNN.json` 與 `.md`
- `text`：該頁文字層內容
- `blocks`：文字 block 與 bbox
- `images`：圖片 bbox 與裁切 PNG 路徑
- `tables`：表格 bbox、裁切 PNG 路徑與抽出的 rows
- `markers`：依頁面座標排序的 image/table 位置標記

```bash
python3 scripts/extract_pdf_pages_structured.py --level 初級 --all --force
python3 scripts/extract_pdf_pages_structured.py --level 初級 --key guide1
```

這個輸出用來彌補 PDF → txt 的資訊遺失：圖、表、版面位置、跨頁脈絡都可透過 bbox 與裁切圖回查。

---

### `scripts/build_pdf_outline.py`

讀取 `page_extract/` 的逐頁 JSON，建立可審核的 PDF 階層目錄：

- guide PDF 若已有 `pages_cache/{key}/page_*.json`，優先使用 Vision headings 建立 L2/L3/L4 階層
- 否則 fallback 到文字規則：章名、`3.1`、`（1）`、`A.` 等模式
- 輸出 `data/{level}/outline/{key}_outline.json` 與 `.md`

```bash
python3 scripts/build_pdf_outline.py --level 初級 --all
python3 scripts/build_pdf_outline.py --level 初級 --key guide1
```

---

### `scripts/clean_pdf_page_text.py`

讀取 `page_extract/`，針對不同 PDF key 套用清理策略，產出可審核的逐頁文字與階層目錄：

- 移除頁首、頁尾、頁碼、PDF 頁籤、表格欄名等非正文內容
- 判斷 `continues_from_previous` 與 `continues_to_next`
- guide PDF 會用目錄頁回填 `3.1` / `3.2` 等標題文字
- 輸出 `data/{level}/page_clean/{key}/pages/page_NNN.json`
- 輸出 `data/{level}/page_clean/{key}/outline.json` 與 `.md`

```bash
python3 scripts/clean_pdf_page_text.py --level 初級 --all
python3 scripts/clean_pdf_page_text.py --level 初級 --key guide1
```

---

### `scripts/codex_review_pdf_pages.py`

使用 Codex CLI 在 read-only sandbox 中逐頁審核 `page_clean/` 結果，並輸出結構化 JSON：

- 檢查開頭/結尾是否清乾淨
- 判斷跨頁延續
- 確認章節階層是否漏判或誤判
- 輸出 `data/{level}/codex_page_review/{key}/page_NNN.json`
- schema 在 `scripts/codex_page_review.schema.json`

```bash
python3 scripts/codex_review_pdf_pages.py --level 初級 --key guide1 --page 7 --force
python3 scripts/codex_review_pdf_pages.py --level 初級 --all --limit 5
python3 scripts/codex_review_pdf_pages.py --level 初級 --key guide1 --with-image
```

執行此腳本需要已登入的 `codex` CLI 與網路權限。腳本會使用臨時 `CODEX_HOME=/tmp/ipas-codex-page-review-home`，但 Codex 代理本身仍以 `--sandbox read-only` 執行。

---

### `scripts/export_guide_outline_data.py`

將 `page_clean/{key}/outline.json` 匯出成前端使用的完整 PDF 目錄資料：

- `frontend/src/generated/guideOutlines.json`：只放目錄 metadata、parent/children、route、page range、content ref
- `frontend/src/generated/guideContent/{key}/{nodeId}.json`：單一節點正文與 PDF 原頁截圖索引
- 匯出時會驗證 node id 唯一、parent/child 關係、depth、page range、content file 是否存在

```bash
python3 scripts/export_guide_outline_data.py
```

前端 Sidebar、SubjectOverviewPage、GuidePage 共用這份 metadata tree；GuidePage 會依 route 動態載入單一 content JSON，避免把整份學習指引正文打包進主 bundle。

---

### `scripts/export_pdf_image_gallery.py`

將 `page_extract/` 裡裁切出的圖片與表格複製到 `frontend/public/pdf-assets/{level}/`，並產生 `gallery.json`。前端 route `#/images` 會讀取這份 manifest，提供 PDF key、類型、頁碼篩選與大圖檢視。

```bash
python3 scripts/export_pdf_image_gallery.py --level 初級 --force
```

---

## 考試及格標準

初級同時報考兩科時，兩科平均達 70 分視為及格，但任一單科不得低於 60 分。單科成績達 70 分以上者，保留及格單科成績自應考日起三年度有效。首頁「考試說明」採用此規則顯示；模擬考 JSON 的 `passing_score` 目前仍用於單份模擬卷結果門檻。

---

### `scripts/extract_pdfs.py`

以 `pdfplumber` 為主要 PDF 解析器，`PyMuPDF`（`fitz`）為備援。

**提取流程：**
1. `extract_with_pdfplumber(pdf_path)` — 使用 `x_tolerance=3, y_tolerance=3` 提取文字，另以 `extract_tables()` 提取表格結構（list of list of str）。若 pdfplumber 無法取得任何文字，退回 `extract_with_pymupdf()`。
2. 每頁輸出一個 dict：`{page, text, tables, width, height}`。
3. 每份 PDF 同時存成 `.txt`（供人工閱覽）與 `.json`（供後續程式解析）。

**鍵名對應（學習指引來自 `toc_manifest.json`，考試 PDF 來自 `EXAM_PDFS_BY_LEVEL`）：**

| 鍵 | 說明 |
|---|---|
| `guide1` | 科目一學習指引 |
| `guide2` | 科目二學習指引 |
| `exam1` | 科目一公告試題 |
| `exam2` | 科目二公告試題 |
| `sample` | 考試樣題（114 年 9 月版） |

擴充其他年度或等級時，在 `EXAM_PDFS_BY_LEVEL` dict 新增對應 PDF 檔名；學習指引 PDF 則從 `toc_manifest.json` 讀取。

---

### `scripts/parse_exams_v2.py`

從 `extracted/*.json` 的表格資料解析選擇題。

**表格格式假設：**
- 公告試題（exam1/exam2）：每列 `[答案, 題目全文]`，答案欄為 A/B/C/D（含全形 Ａ/Ｂ/Ｃ/Ｄ 與全形括號 `（）`，以 `FW_MAP` 正規化）。
- 樣題（sample）：每列有 8 個以上欄位，程式尋找符合 `[ABCD]` 的欄位作為答案，並尋找包含 `(A)` 且長度 > 10 的欄位作為題目全文。

**`parse_question_cell()` 解析邏輯：**
1. 移除嵌入的題號（`\n1.\n` 等格式）。
2. 以 regex `\(([A-D])\)(.*?)(?=\([A-D]\)|\Z)` 提取四個選項。
3. 第一個 `(A)` 之前的文字為題幹。
4. 少於 4 個選項的資料列直接丟棄，並印出 WARN 訊息。

**輸出 JSON 格式（模擬考 `mock_exam*.json`）：**

```json
{
  "exam": "科目一 模擬考試：...",
  "total": 50,
  "time_limit": "90分鐘",
  "passing_score": 60,
  "questions": [
    {
      "id": "exam1_q1",
      "question": "題幹文字",
      "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
      "answer": "B",
      "explanation": "正確答案為(B)。",
      "source": "exam1"
    }
  ]
}
```

> **已知限制**：pdfplumber 有時將選項抽取到不同 row，導致 exam1/exam2 各有約 9–11 題無法解析（WARN 列出）。`subject*_questions.json` 為手工整理，不被此腳本覆寫。

---

### `scripts/build_manifest.py`

**章節定義 SSOT**。內嵌所有科目/章節的 metadata（唯一需要硬編碼 `GUIDES_BY_LEVEL` dict 的腳本），以 PyMuPDF 計算每章的 PDF 頁碼範圍（0-based），輸出 `data/{level}/toc_manifest.json`。支援 `--level`。

資料腳本（例如 `parse_guides.py`、`pdf_vision_extract.py`）和前端章節導覽／總覽均從此 manifest 讀取，不得在他處重複定義章節。

```bash
uv run python3 scripts/build_manifest.py                    # 預設 初級
uv run python3 scripts/build_manifest.py --level 初級       # → data/初級/toc_manifest.json
uv run python3 scripts/build_manifest.py --dry-run          # 印出 JSON，不寫檔
```

---

### `scripts/audit_chapters.py`

**LLM 章節內容審核**。讀取 `subject{N}_guide.json`，對每章節呼叫 Claude Haiku 審核：subtopics 是否全部覆蓋、是否有內容錯置。輸出 `subject{N}_audit_report.json`（`overall_status: PASS/WARN/FAIL`）。審核 FAIL 的章節需人工確認後才進行出題。支援 `--level`。

```bash
uv run python3 scripts/audit_chapters.py --level 初級 --all
uv run python3 scripts/audit_chapters.py --level 初級 --subject 1 --chapter s1c1
uv run python3 scripts/audit_chapters.py --level 初級 --all --dry-run  # 預覽 prompt
```

---

### `scripts/parse_guides.py`

**Vision 組合**。從 `pages_cache/` 讀取 Gemini Vision 快取（preferred），或 fallback 到 regex 模式解析 `extracted/guide{N}.json`。依 `toc_manifest.json` 章節頁碼範圍輸出章節結構化 JSON。支援 `--level`、`--subject`。

**輸出（`data/{level}/guide/`）：**

```json
{
  "subject": "科目一：人工智慧基礎概論",
  "chapters": [
    {
      "id": "s1c1",
      "title": "人工智慧概念",
      "subtopics": ["AI定義與分類", "..."],
      "content": "原文文字（約 5,000–15,000 字元）"
    }
  ]
}
```

---

### `scripts/generate_questions.py`

呼叫 Claude API 自動生成帶解說圖卡的題目，或為既有題目補充 `card` 欄位。

**執行模式：**

```bash
uv run python3 scripts/generate_questions.py --level 初級 --subject 1 [--count 5] [--dry-run]
uv run python3 scripts/generate_questions.py --level 初級 --subject 2
uv run python3 scripts/generate_questions.py --level 初級 --enrich
```

**擴充後的題目 JSON schema：**

```json
{
  "id": "s1c1q1",
  "question": "...",
  "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
  "answer": "C",
  "explanation": "完整解說",
  "card": {
    "concept": "核心概念摘要（1–2 句）",
    "mnemonic": "記憶口訣",
    "confusion": "常見混淆點與辨別方式",
    "frequency": "高/中/低"
  },
  "difficulty": "易/中/難",
  "type": "概念定義型",
  "tags": ["Human-in-the-loop", "AI治理"],
  "generated_by": "multi_ai_pipeline | generate_questions | manual"
}
```

---

### `scripts/multi_ai_pipeline.py`

以三套 CLI 工具分擔角色，透過 subprocess 非互動模式串接成出題流水線。

**角色分工（預設，可透過 CLI 覆蓋）：**

| 角色 | 預設工具 | 說明 |
|------|---------|------|
| 出題者 (Creator) | `gemini` | 依章節內容與題型模板產生草稿題目 |
| 審核者 (Reviewer) | `codex` | 逐題評分（答案正確性、干擾項品質、清晰度等） |
| 完稿者 (Finalizer) | `claude` | 依審核意見修正並輸出最終 JSON |

**5 種題型模板：** 概念定義型 / 應用情境型 / 比較辨析型 / 錯誤識別型 / 流程步驟型
`select_templates()` 依章節 subtopics 數量與關鍵字自動選 2–3 種。

**答題驗證：** 完稿後，三工具以 `ThreadPoolExecutor` 並行各自作答，
若 2 個以上答錯同一題，該題寫入 `flagged.json` 供人工審閱，不自動刪除。

**每次執行的輸出目錄結構：**

```
data/初級/pipeline/<run_id>/subject1/
  s1c1/
    draft.json        ← 出題草稿
    review.json       ← 審核意見
    final.json        ← 最終題目
    validation.json   ← 各 AI 作答記錄
    flagged.json      ← 有問題的題目（僅在有 flag 時產生）
  pipeline_summary.json
```

通過驗證的題目自動 merge 進 `data/初級/questions/subject{N}_questions.json`，
id 格式為 `{chapter_id}q{n}_multi`，以區別手工策展題目（`q{n}` 無後綴）。

**常用指令：**

```bash
# 乾跑確認 prompt 內容
python3 scripts/multi_ai_pipeline.py --level 初級 --subject 1 --chapter s1c1 --dry-run

# 單章節執行（預設 3 題）
python3 scripts/multi_ai_pipeline.py --level 初級 --subject 1 --chapter s1c1

# 全科目執行，自訂題數與角色
python3 scripts/multi_ai_pipeline.py --level 初級 --subject 2 --count 5 \
  --creator gemini --reviewer codex --finalizer claude

# 跳過審核與驗證（速度最快）
python3 scripts/multi_ai_pipeline.py --level 初級 --subject 1 --skip-review --skip-validation

# 注意：multi_ai_pipeline.py 透過 subprocess 呼叫外部 CLI，不需要 uv run
```

---

### `scripts/verify_data_alignment.py`

本地一致性檢查，用來確認 PDF 參考資料與系統使用的章節資料沒有分岔：

- 重新依 `build_manifest.py` 與目前 PDF 頁碼標籤計算 manifest，並與 `data/{level}/toc_manifest.json` 比對（忽略 `generated_at`）。
- 檢查 manifest 內的學習指引 PDF 與 `extract_pdfs.py` 的考試 PDF 檔名是否存在。
- 檢查 `subject{N}_guide.json` 與 `subject{N}_questions.json` 的章節 ID / title 是否符合 manifest，且章節題庫不是空的。
- 檢查 guide JSON 內的 PDF 原頁截圖路徑是否存在於 `frontend/public/guide-pages/`。

```bash
python3 scripts/verify_data_alignment.py --level 初級
```

---

### `scripts/render_guide_page_images.py`

將 `subject{N}_guide.json` 內的 `source_pages` 渲染成 PNG，輸出至 `frontend/public/guide-pages/{level}/{key}/`。網站學習指引頁會以可展開區塊顯示這些原頁截圖，用來保留純文字抽取會遺失的圖、表、版面與跨頁脈絡。

```bash
python3 scripts/render_guide_page_images.py --level 初級 --all
python3 scripts/render_guide_page_images.py --level 初級 --subject 1 --force
```

---

### `scripts/build_web.py`

Thin wrapper，呼叫 `frontend/` 下的 `npm run build`，讓 Vite 將 React 前端打包輸出至 `docs/`。

**輸出結構：**

```
docs/
├── index.html          # 入口 HTML（僅 ~430 B，引用 assets/）
└── assets/
    ├── index-*.js      # 所有 JS（含 React、Router、資料 JSON，~570 KB）
    └── index-*.css     # 所有 CSS（Tailwind，~21 KB）
```

**資料存取方式：** 前端以 Vite 的 `@data` alias（指向 `data/初級/`）靜態 import 所有 JSON 檔案（toc_manifest、questions × 5、guide × 2），在 build time 打包進 JS bundle，不需 runtime fetch。

**網站導覽（React Router HashRouter）：**
- `#/` 首頁 → 各科目總覽、考試說明
- `#/subject/s1` / `#/subject/s2` → 科目章節總覽
- `#/practice/:subjectId/:chapterId` → 章節練習（sidebar `✏️` 入口）
- `#/exam/:examKey` → 模擬考試（`mock1`、`mock2`、`sample`）
- `#/guide/:subjectId/:chapterId` → 學習指引
- 手機版 sidebar 收進左上角 `☰` 漢堡選單。
- 題目若無 `card` 欄位，前端不顯示「📌 查看解說圖卡」按鈕；屬資料狀態而非 UI 問題。

---

## GitHub Pages 部署

部署由 `.github/workflows/deploy.yml` 自動處理，push 到 `main` 即觸發。

**首次設定：**
1. 建立 GitHub repo，推上 `main` branch。
2. `Settings → Pages → Source` 選 **GitHub Actions**（不是 branch/docs）。

**後續流程：**
- push `main` → Actions 自動 build（`npm ci && npm run build`）→ deploy 到 Pages。
- `docs/` 已 gitignored，不需手動 build 或 commit build artifacts。
- 本機開發仍可用 `uv run python3 scripts/build_web.py` 預覽 production build。

---

## 擴充為中級

1. 在 `data/中級/pdfs/` 放入中級 PDF。
2. 在 `scripts/build_manifest.py` 的 `GUIDES_BY_LEVEL` dict 加入中級章節定義，執行 `uv run python3 scripts/build_manifest.py --level 中級` 生成 manifest。
3. 資料 pipeline scripts 已支援 `--level 中級`，直接以 `--level 中級` 執行各 pipeline 步驟即可（不需修改程式碼）。
4. 在 `scripts/build_web.py` 載入中級題庫與學習指引，並加入網頁 UI。
