# iPAS AI 應用規劃師備考平台

針對 iPAS AI 應用規劃師能力鑑定（初級）的靜態備考網站，部署於 GitHub Pages。

---

## 目錄結構

```
ipas-test/
├── scripts/                      # 資料處理腳本
│   ├── build_manifest.py         # ★ 章節定義 SSOT → data/初級/toc_manifest.json
│   ├── guide_to_md.py            # PDF → span 解析 → 章節 Markdown（無 LLM）
│   ├── pdf_vision_extract.py     # PDF → Claude Vision → pages_cache（有 LLM）
│   ├── parse_guides.py           # pages_cache/extracted → 章節 JSON（vision/regex）
│   ├── audit_chapters.py         # 解析後 LLM 審核 → subject{N}_audit_report.json
│   ├── extract_pdfs.py           # PDF → 文字/JSON（供考題 pipeline 使用）
│   ├── parse_exams_v2.py         # JSON 表格 → 模擬考試題庫 JSON
│   ├── generate_questions.py     # Claude API → 章節題目 + 解說圖卡
│   ├── multi_ai_pipeline.py      # 多 AI 出題流水線（Gemini/Codex/Claude CLI）
│   └── build_web.py              # 呼叫 npm run build → docs/
├── frontend/                     # Vite 前端專案
│   ├── src/                      # React + TypeScript 原始碼
│   │   ├── pages/                # 頁面元件（Home、SubjectOverview、Practice、Exam、Guide）
│   │   ├── components/           # UI 元件（layout、practice、exam、shared）
│   │   ├── store/                # Zustand 狀態管理（examStore）
│   │   ├── hooks/                # useExamTimer
│   │   ├── types/                # TypeScript 型別定義
│   │   └── constants/            # 靜態常數（guideNotices）
│   ├── public/                   # 靜態資源（favicon.ico、.nojekyll）
│   ├── vite.config.ts            # 輸出至 ../docs，@data alias → ../data/初級
│   └── package.json              # React 19、TW v4、React Router v6、Zustand v5
├── data/
│   └── 初級/                     # 初級資料（gitignore）
│       ├── pdfs/                 # 原始 PDF 來源
│       ├── extracted/            # 從 PDF 萃取的文字與結構（.txt / .json）
│       ├── questions/            # 題庫 JSON（mock_exam*.json、subject*_questions.json）
│       ├── toc_manifest.json     # ★ 章節定義 SSOT（由 build_manifest.py 生成，需提交）
│       ├── guide/                # 學習指引輸出（subject{N}_guide.json、_audit_report.json 等）
│       ├── analysis/             # 章節／題型分析（exam_analysis.json）
│       └── pipeline/             # multi_ai_pipeline.py 各次執行的中間產物（gitignore）
├── logs/                         # 執行 log（gitignore）
└── docs/                         # GitHub Pages 網站（Vite 建置輸出）
    ├── index.html                # 入口 HTML（434 B）
    └── assets/                   # 打包後的 JS + CSS
```

> 後續擴充中級時，在 `data/` 下新增 `中級/` 資料夾，依相同結構組織 PDF 與題庫，並於 `scripts/` 中以 `LEVEL = '中級'` 切換或建立獨立腳本。

---

## 執行 Pipeline

### 核心目標

**依據解析的 MD 教材與官方樣張／歷屆題目，針對特定章節自動生成高品質模擬試題。**
解析品質直接決定出題品質——每頁必須正確歸入對應章節。

### 指令

從專案根目錄依序執行：

```bash
# 0. 生成章節目錄索引（僅在章節定義或 PDF 異動時需要）
uv run python3 scripts/build_manifest.py   # → data/初級/toc_manifest.json

# ── 學習指引 Guide pipeline（擇一）──────────────────────────────────────

# 路線 A：Span 提取（無 LLM，推薦先跑）
uv run python3 scripts/guide_to_md.py --all              # 兩科全跑
uv run python3 scripts/guide_to_md.py --subject 1 --chapter s1c1  # 單章

# 路線 B：Vision 提取（有 LLM，需 ANTHROPIC_API_KEY）
uv run python3 scripts/pdf_vision_extract.py --all       # 兩科全跑（~$1.6）
uv run python3 scripts/parse_guides.py                   # 組合章節 JSON

# 解析後 LLM 審核（確認頁面→章節對應正確）
uv run python3 scripts/audit_chapters.py --all           # 兩科全審
uv run python3 scripts/audit_chapters.py --all --dry-run # 預覽 prompt
# → data/初級/guide/subject{1,2}_audit_report.json

# ── 考題 Exam pipeline ───────────────────────────────────────────────────

# 1. PDF 萃取（更換 PDF 後才需重新執行）
uv run python3 scripts/extract_pdfs.py

# 2. 解析模擬考試題目（公告試題 / 樣題）
uv run python3 scripts/parse_exams_v2.py

# 3. 解析學習指引章節內容（vision/regex fallback，可替代路線 A/B）
uv run python3 scripts/parse_guides.py

# 4a. （選用）透過 Claude API 生成／補充題目（單一模型）
export ANTHROPIC_API_KEY=sk-ant-...
uv run python3 scripts/generate_questions.py --subject 1   # 生成科目一各章新題
uv run python3 scripts/generate_questions.py --subject 2   # 生成科目二各章新題
uv run python3 scripts/generate_questions.py --enrich      # 補充既有題目的解說圖卡欄位

# 4b. （選用）多 AI 出題流水線（需 gemini / codex / claude CLI 已安裝並完成認證）
# 注意：multi_ai_pipeline.py 使用 subprocess 呼叫外部 CLI，不需要 uv run
python3 scripts/multi_ai_pipeline.py --subject 1 --chapter s1c1 --dry-run  # 預覽 prompt
python3 scripts/multi_ai_pipeline.py --subject 1 --count 3                  # 執行科目一

# 5. 建置網站（Vite 打包 React 前端）
uv run python3 scripts/build_web.py
# 等同於：cd frontend && npm run build
```

僅更新前端 UI 時只需執行最後一步。前端開發時可用 dev server：

```bash
cd frontend && npm run dev -- --host    # http://localhost:5173/（--host 供 WSL 存取）
```

> `docs/` 是 Vite 的建置輸出目錄。只要 `frontend/src/` 或任何資料 JSON 有變動，就必須重新執行 `uv run python3 scripts/build_web.py`，並將更新後的 `docs/` 一起納入 commit。

依賴套件：

```bash
uv sync                                    # Python 依賴（pdfplumber、pymupdf、anthropic）
cd frontend && npm install                 # 前端依賴（React、Vite、Tailwind CSS v4 等）
# multi_ai_pipeline.py 不需額外 Python 套件，但需以下 CLI 工具：
#   gemini  → https://github.com/google-gemini/gemini-cli
#   codex   → https://github.com/openai/codex
#   claude  → npm install -g @anthropic-ai/claude-code
```

---

## 腳本實作說明

### `scripts/extract_pdfs.py`

以 `pdfplumber` 為主要 PDF 解析器，`PyMuPDF`（`fitz`）為備援。

**提取流程：**
1. `extract_with_pdfplumber(pdf_path)` — 使用 `x_tolerance=3, y_tolerance=3` 提取文字，另以 `extract_tables()` 提取表格結構（list of list of str）。若 pdfplumber 無法取得任何文字，退回 `extract_with_pymupdf()`。
2. 每頁輸出一個 dict：`{page, text, tables, width, height}`。
3. 每份 PDF 同時存成 `.txt`（供人工閱覽）與 `.json`（供後續程式解析）。

**鍵名對應（`PDFS` dict）：**

| 鍵 | 說明 |
|---|---|
| `guide1` | 科目一學習指引 |
| `guide2` | 科目二學習指引 |
| `exam1` | 科目一公告試題 |
| `exam2` | 科目二公告試題 |
| `sample` | 考試樣題（114 年 9 月版） |

擴充其他年度或等級時，在 `PDFS` dict 新增鍵值，並更新 `LEVEL` 變數（目前為 `'初級'`）。

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

**章節定義 SSOT**。內嵌所有科目/章節的 metadata（唯一需要硬編碼 `GUIDES` dict 的腳本），以 PyMuPDF 計算每章的 PDF 頁碼範圍（0-based），輸出 `data/初級/toc_manifest.json`。

所有其他腳本（`guide_to_md.py`、`parse_guides.py`、`pdf_vision_extract.py`）和前端（`SubjectOverviewPage.tsx`）均從此 manifest 讀取，不得在他處重複定義章節。

```bash
uv run python3 scripts/build_manifest.py          # 生成 toc_manifest.json
uv run python3 scripts/build_manifest.py --dry-run # 印出 JSON，不寫檔
```

---

### `scripts/guide_to_md.py`

**路線 A：Span 提取（無 LLM）**。以 PyMuPDF 字型尺寸/粗體 flags 分類 6 層結構（L2 ≥18pt bold → `##`、L3 ≥13pt bold → `###`、L4 `（N）` → `####`、L5 `A.` → `#####`、L6 bullet → `-`），產生 Markdown 並驗證關鍵詞保留率（預設 95%）。

**輸出（`data/初級/guide/`）：**
- `subject{N}_guide.json`（前端使用）
- `subject{N}_guide.md`（全文 Markdown）
- `subject{N}_guide_nested.json`（完整巢狀樹）
- `subject{N}_validation_report.json`（關鍵詞保留率報告）

```bash
uv run python3 scripts/guide_to_md.py --all
uv run python3 scripts/guide_to_md.py --subject 1 --chapter s1c1
uv run python3 scripts/guide_to_md.py --subject 1 --threshold 0.90
```

---

### `scripts/audit_chapters.py`

**LLM 章節內容審核**。讀取 `subject{N}_guide.json`，對每章節呼叫 Claude Haiku 審核：subtopics 是否全部覆蓋、是否有內容錯置。輸出 `subject{N}_audit_report.json`（`overall_status: PASS/WARN/FAIL`）。審核 FAIL 的章節需人工確認後才進行出題。

```bash
uv run python3 scripts/audit_chapters.py --all
uv run python3 scripts/audit_chapters.py --subject 1 --chapter s1c1
uv run python3 scripts/audit_chapters.py --all --dry-run  # 預覽 prompt
```

---

### `scripts/parse_guides.py`

**路線 B：Vision 組合**。將 `guide1.json` / `guide2.json` 依官方目錄的章節頁碼分割，輸出章節結構化 JSON 供前端顯示與 LLM 生題使用。

**切割策略：** 官方學習指引每章末頁印有「3-N」頁碼。程式掃描這些頁碼（如 `3-23`、`3-32`、`3-47`）作為章節邊界，比對下一章起始頁碼 - 1。

**清理步驟：** 去除點線目錄行、重複章節頁首（`第三章...`）、PUA Unicode 雜字（`\uf07d`）、獨立頁碼行、獨立章節編號行。

**重要限制：** 官方指引的章節分法與考試章節不完全一致。科目一指引 3.1 將 ETL、資料類型、資料清洗、GDPR 等「考試 s1c2」的主題包含在 3.1 內，指引 3.2 僅涵蓋統計方法。

**輸出（`data/初級/guide/`）：**

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
uv run python3 scripts/generate_questions.py --subject 1 [--count 5] [--dry-run]
uv run python3 scripts/generate_questions.py --subject 2
uv run python3 scripts/generate_questions.py --enrich
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
  "tags": ["Human-in-the-loop", "AI治理"]
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
python3 scripts/multi_ai_pipeline.py --subject 1 --chapter s1c1 --dry-run

# 單章節執行（預設 3 題）
python3 scripts/multi_ai_pipeline.py --subject 1 --chapter s1c1

# 全科目執行，自訂題數與角色
python3 scripts/multi_ai_pipeline.py --subject 2 --count 5 \
  --creator gemini --reviewer codex --finalizer claude

# 跳過審核與驗證（速度最快）
python3 scripts/multi_ai_pipeline.py --subject 1 --skip-review --skip-validation

# 注意：multi_ai_pipeline.py 透過 subprocess 呼叫外部 CLI，不需要 uv run
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

**資料存取方式：** 前端以 Vite 的 `@data` alias（指向 `data/初級/`）靜態 import 所有 7 個 JSON 檔案，在 build time 打包進 JS bundle，不需 runtime fetch。

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

1. 建立 GitHub repo，將本目錄推上 `main` branch。
2. `Settings → Pages → Deploy from branch`，選 `main`，Folder 選 `/docs`。
3. 每次執行 `uv run python3 scripts/build_web.py` 並 push `docs/` 後即自動更新。
   - Vite 使用 HashRouter，GitHub Pages 不需額外設定 404 重導向。

---

## 擴充為中級

1. 在 `data/中級/pdfs/` 放入中級 PDF。
2. 複製並修改 `scripts/extract_pdfs.py`，將 `LEVEL = '初級'` 改為 `LEVEL = '中級'`，更新 `PDFS` 對應新檔名。
3. 在 `scripts/build_manifest.py` 的 `GUIDES` dict 加入中級章節定義，重新執行生成 manifest。
4. 同步修改 `parse_exams_v2.py` 的 `OUT` 路徑；`parse_guides.py`、`guide_to_md.py` 會自動從 manifest 讀取新定義。
5. `generate_questions.py` 的 `DATA` 路徑亦需對應更新。
5. 在 `scripts/build_web.py` 載入中級題庫與學習指引，並加入網頁 UI。
