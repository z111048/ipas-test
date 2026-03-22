# Changelog

本文件記錄專案的重要變更，格式參考 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.0.0/)。

---

## [Unreleased]

### 全腳本 `--level` 參數支援 + 移除 `guide_to_md.py`

#### 新增
- 所有腳本（`build_manifest.py`、`pdf_vision_extract.py`、`parse_guides.py`、`audit_chapters.py`、`extract_pdfs.py`、`parse_exams_v2.py`、`generate_questions.py`、`multi_ai_pipeline.py`）統一加入 `--level` 參數（預設：`初級`），路徑動態解析為 `data/{level}/`；新增等級時不需修改腳本程式碼

#### 變更
- `scripts/build_manifest.py`：`GUIDES` dict 更名為 `GUIDES_BY_LEVEL`（以等級為 key），支援 `--level` 動態選擇；路徑由硬編碼改為 `BASE / 'data' / level`
- `scripts/extract_pdfs.py`：移除硬編碼 `LEVEL = '初級'`，改由 `--level` 控制；exam PDF 定義改存於 `EXAM_PDFS_BY_LEVEL` dict
- 所有腳本：移除模組頂層的 `DATA = BASE / 'data' / '初級'` 等硬編碼路徑，改在 `main()` 中依 `--level` 動態建構

#### 移除
- `scripts/guide_to_md.py`：Span 提取路線（Route A）已由 Gemini Vision 路線（Route B）全面取代，腳本已刪除

#### 文件
- `CLAUDE.md`、`AGENTS.md`、`README.md`：移除 `guide_to_md.py` 相關說明；所有指令範例加入 `--level` 參數；「擴充為中級」說明更新為無需修改程式碼

---

### pdf_vision_extract 遷移至 Gemini + guide_to_md 練習題過濾 + 章節 subtopics 修訂

#### 新增
- `scripts/pdf_vision_extract.py`：每頁輸出新增 `headings` 欄位（`[{level, title}]`，語義化章節標題），供後續 TOC 建構使用
- `scripts/pdf_vision_extract.py`：提取完成後自動生成 `data/初級/pages_cache/{key}/page_index.json`（彙整各頁 `type`、`headings`，並輸出扁平化 `toc` 結構）
- `scripts/guide_to_md.py`：新增 `filter_practice_lines()` 函式，在 span 提取前自動剔除指引中內嵌的練習題頁（以題號 regex `^\d+[\.、]` 和選項 regex `^[（(][A-D][）)]` 偵測）

#### 變更
- **`scripts/pdf_vision_extract.py`：Vision API 由 Anthropic Claude 遷移至 Google Gemini**
  - API client 改用 `google.genai`（`google-genai>=1.68.0`），需要 `GEMINI_API_KEY` 環境變數
  - 預設模型：`gemini-2.5-flash`，可透過 `GOOGLE_MODEL` 環境變數覆蓋
  - PNG 傳遞方式由 base64 字串改為原始 bytes（`page_to_png_bytes()`）
  - Prompt 結構調整以符合 Gemini API 格式
  - 預估費用：~$2（約 133 頁，較舊版 ~$1.6 略高）
- `scripts/build_manifest.py`：修訂科目一、二各章 subtopics（s1c1 移除 AI 治理/EU AI Act，改為 AI 架構/演算法；s1c2 調整資料處理主題；s2c1 No/Low Code 展開為 6 個子主題；s2c2 生成式 AI 工具增補更多細目）
- `data/初級/toc_manifest.json`：依據上述 subtopics 修訂重新生成，並更新各章 `page_range`
- `pyproject.toml`：新增依賴 `google-genai>=1.68.0`

#### 文件
- `CLAUDE.md`：更新 Vision 路線 B 說明（API key、模型、費用）、依賴清單、`pdf_vision_extract.py` / `guide_to_md.py` 架構說明
- `README.md`：更新目錄結構注釋、路線 B 指令說明、`guide_to_md.py` / `pdf_vision_extract.py` 腳本說明、依賴清單

---

### 解析品質強化：toc_manifest SSOT + LLM 審核 + 前端目錄資料驅動化

#### 核心目標
確立平台終極目標：**根據解析的 MD 教材與官方樣張/歷屆題目，針對特定章節綜合出高品質模擬試題**。PDF→MD 解析品質直接決定出題品質，前處理必須保證每頁正確入庫到對應章節。

#### 新增
- `scripts/build_manifest.py`：唯一包含 `GUIDES` 硬編碼的腳本（章節定義 SSOT），以 PyMuPDF 計算各章 PDF 頁碼範圍，輸出 `data/初級/toc_manifest.json`
- `data/初級/toc_manifest.json`：章節定義靜態 JSON，需提交 repo，所有腳本與前端統一從此讀取
- `scripts/audit_chapters.py`：解析後 LLM 審核腳本（Claude Haiku），確認每章節涵蓋 subtopics、無內容錯置；輸出 `data/初級/guide/subject{N}_audit_report.json`（`overall_status: PASS/WARN/FAIL`）；支援 `--all/--subject/--chapter/--dry-run`

#### 變更
- `scripts/guide_to_md.py`：移除 `GUIDES` dict，改從 `toc_manifest.json` 讀取（`_load_manifest()` + `manifest_to_guides()`）
- `scripts/parse_guides.py`：同上，移除約 113 行重複的 `GUIDES` dict
- `scripts/pdf_vision_extract.py`：同上，移除精簡版 `GUIDES`
- `frontend/src/pages/SubjectOverviewPage.tsx`：移除硬編碼的 `S1_CHAPTERS`/`S2_CHAPTERS`；改從 `toc_manifest.json` 靜態 import，展示 subtopics pills + PDF 頁碼範圍 + 快速連結（📖 學習指引 / ✏️ 練習題）
- `frontend/src/types/index.ts`：新增 `TocChapter`、`TocSubject`、`TocManifest` TypeScript 型別
- `CLAUDE.md`、`AGENTS.md`、`README.md`：全面更新，反映核心目標、toc_manifest SSOT、新腳本說明、audit 驗證步驟

#### 文件
- `CLAUDE.md`：新增「核心目標」段落，Build Pipeline 加入 Step 0（build_manifest）與 Step 3（audit），Architecture 加入 `build_manifest.py` 和 `audit_chapters.py` 說明
- `README.md`：目錄結構、Pipeline 步驟、腳本說明全面更新
- `AGENTS.md`：Project Structure、Build Commands、Testing Guidelines 全面更新

---

### 前端遷移：React + TypeScript + Tailwind CSS v4 + Vite

#### 新增
- `frontend/`：Vite 前端專案，React 19 + TypeScript + Tailwind CSS v4 + React Router v6 (HashRouter) + Zustand v5
  - `frontend/src/pages/`：HomePage、SubjectOverviewPage、PracticePage、ExamPage、GuidePage
  - `frontend/src/components/`：layout（Header、Sidebar、Overlay）、practice（QuestionCard、OptionButton、CardPanel、FreqBar）、exam（ExamIntro、ExamTimer、ExamQuestion、ExamResults）、shared（StatBox、ProgressBar）
  - `frontend/src/store/examStore.ts`：Zustand 考試狀態（phase、userAnswers、secondsRemaining）；timer tick 僅觸發 ExamTimer 重繪，不影響整個題目列表
  - `frontend/src/hooks/useExamTimer.ts`：每秒 tick，時間到自動繳卷
  - `frontend/src/types/index.ts`：Question、Chapter、SubjectQuestions、ExamData、GuideData 等 TypeScript 型別
  - `frontend/vite.config.ts`：build outDir → `../docs`，`@data` alias → `../data/初級`，所有 JSON 靜態 import，不需 runtime fetch
  - `frontend/public/favicon.ico`、`frontend/public/.nojekyll`

#### 變更
- `scripts/build_web.py`：改為呼叫 `cd frontend && npm run build` 的 thin wrapper；不再生成 HTML 字串
- `docs/`：由單一 `index.html`（355 KB）改為 Vite 打包的 `index.html`（~430 B）+ `assets/`（JS ~570 KB、CSS ~21 KB）
- `CLAUDE.md`、`AGENTS.md`、`README.md`：全面更新以反映前端架構、路由結構、dev server 指令

#### 路由（HashRouter）
| Route | 頁面 |
|---|---|
| `#/` | 首頁 |
| `#/subject/:subjectId` | 科目章節總覽 |
| `#/practice/:subjectId/:chapterId` | 章節練習 |
| `#/exam/:examKey` | 模擬考試（mock1/mock2/sample） |
| `#/guide/:subjectId/:chapterId` | 學習指引 |

---

### 變更
- 改用 `uv` 管理虛擬環境與 Python 依賴：新增 `pyproject.toml`、`uv.lock`，`.gitignore` 加入 `.venv/`
- 所有 `python3 scripts/...` 指令改為 `uv run python3 scripts/...`（`multi_ai_pipeline.py` 例外，因其使用 subprocess 呼叫外部 CLI，不依賴虛擬環境）
- clone 後執行 `uv sync` 即可還原環境，不再需要手動 `pip install`

### 新增
- `scripts/multi_ai_pipeline.py`：多 AI 出題流水線，以 subprocess 非互動模式串接三套 CLI 工具
  - 角色分工：Gemini（出題者）→ Codex（審核者）→ Claude（完稿者），可透過 `--creator/reviewer/finalizer` 覆蓋
  - 5 種題型模板：概念定義型、應用情境型、比較辨析型、錯誤識別型、流程步驟型；`select_templates()` 依章節自動選 2–3 種
  - 答題驗證：完稿後三工具並行作答（`ThreadPoolExecutor`），2+ 答錯則寫入 `flagged.json` 供人工審閱
  - 中間產物存至 `data/初級/pipeline/<run_id>/`，最終題目 merge 進 `subject{N}_questions.json`（id 格式 `{chapter_id}q{n}_multi`）
  - 支援 `--subject`、`--chapter`、`--count`、`--dry-run`、`--skip-review`、`--skip-validation`、`--timeout`
- `data/初級/pipeline/` 目錄說明納入文件

### 修復（測試過程）
- `check_available_tools()`：補捉 `subprocess.TimeoutExpired`（`gemini --version` 會 hang，改視為工具存在）
- `call_claude()`：移除不存在的 `--no-permission-prompts` flag，改用 `--dangerously-skip-permissions --tools ""`
- `call_codex()`：改用正確的 `codex exec -c 'sandbox_permissions=[...]' -` 語法（原 `--approval-mode full-auto` 為無效 flag）

### 文件
- `README.md`、`AGENTS.md`、`CLAUDE.md`：補充 `docs/index.html` 必須和 `scripts/build_web.py` 同步重建與提交的規則，並說明題庫入口位於 sidebar／手機版漢堡選單
- 所有 `.md` 更新以反映 `multi_ai_pipeline.py` 的新腳本、CLI 依賴、輸出目錄

### 修復
- 文件澄清：若題目 JSON 沒有 `card` 欄位，前端不會顯示解說圖卡按鈕；這屬於資料狀態，不是 `docs/index.html` 漏 build
- `scripts/build_web.py` / `docs/index.html`：修正學習指引頁段落切分與換行處理的 regex escaping，避免輸出的內嵌 JavaScript 產生不正確的跨行 regex

### Guide 解析路線 A：Span 提取（無 LLM）

#### 新增
- `scripts/guide_to_md.py`：以 PyMuPDF span 字型元數據（尺寸/粗體）進行完全確定性的 6 層結構提取，無需 LLM，不耗 API token；包含行合併、巢狀樹建構、Markdown 序列化、關鍵詞保留率驗證（預設閾值 95%）；支援 `--all/--subject/--chapter/--threshold`
- `scripts/pdf_vision_extract.py`：Claude Vision 逐頁提取，結果快取於 `pages_cache/{key}/page_NNN.json`；支援 `--all/--subject/--dry-run/--force/--page`

#### 輸出（`data/初級/guide/`）
- `subject{N}_guide.json`：前端用（`content_format: 'markdown'`）
- `subject{N}_guide.md`：純 Markdown 全文
- `subject{N}_guide_nested.json`：完整巢狀樹（未來用途）
- `subject{N}_validation_report.json`：關鍵詞保留率報告

---

## [0.3.0] - 2026-03-21

### 新增
- `scripts/parse_guides.py`：將 `guide1/guide2` 萃取 JSON 依官方目錄頁碼分割為章節結構化 JSON，輸出至 `data/初級/guide/subject{1,2}_guide.json`
- `scripts/generate_questions.py`：呼叫 Claude API（`claude-sonnet-4-6`）為各章節生成選擇題（`--subject 1/2`）或補充解說圖卡欄位（`--enrich`）；支援 `--count N`、`--dry-run`
- 解說圖卡 UI：答題後可展開「📌 查看解說圖卡」，顯示核心概念、記憶口訣、常見混淆、出題頻率
- 學習指引側欄與頁面：側欄新增科目一／二各章入口，點擊進入獨立指引頁面
- Question schema 擴充：新增 `card`（`concept/mnemonic/confusion/frequency`）、`difficulty`、`type`、`tags` 欄位
- `data/初級/guide/` 目錄納入文件說明

### 變更
- `scripts/parse_exams_v2.py`：`FW_MAP` 加入全形括號 `（）→()`；無法解析的資料列改以 `WARN` 明確印出；改用 `with open()` 讀檔
- `scripts/build_web.py`：新增學習指引 JSON 載入（`SUBJECT1_GUIDE`／`SUBJECT2_GUIDE` JS 常數）；新增指引頁面 HTML/CSS/JS；新增 `toggleCard()` 函式控制圖卡顯示
- `CLAUDE.md`、`AGENTS.md`、`README.md` 全面更新，反映新腳本、新 schema、新驗證步驟

### 依賴
- 新增選用依賴 `anthropic`（僅 `generate_questions.py` 需要）；需設定 `ANTHROPIC_API_KEY` 環境變數

---

## [0.2.0] - 2026-03-21

### 新增
- `README.md` 詳細記錄三支腳本的實作邏輯、JSON schema、f-string 雙括號規則，以及擴充中級的步驟
- `CHANGELOG.md`（本檔案）

### 變更
- **資料夾結構重組**：
  - 腳本從 `output/` 移至 `scripts/`
  - 原始 PDF 從根目錄移至 `data/初級/pdfs/`
  - 萃取結果移至 `data/初級/extracted/`，題庫移至 `data/初級/questions/`
  - 執行 log 移至 `logs/`
  - `data/<等級>/` 結構為後續擴充中級預留空間
- `scripts/extract_pdfs.py`：新增 `LEVEL` 變數，路徑改指 `data/初級/`；`main()` 加入 `OUT.mkdir()` 確保目錄存在
- `scripts/parse_exams_v2.py`：`OUT` 改指 `data/初級/`
- `scripts/build_web.py`：移除 `output/web/` 雙寫輸出，僅寫入 `docs/index.html`；log 路徑改指 `logs/`
- `.gitignore` 改為明確排除 `data/`、`logs/`，`scripts/`、`CLAUDE.md`、`AGENTS.md` 現納入版本控制
- `AGENTS.md`、`CLAUDE.md` 同步更新所有路徑參照

### 修復
- 章節練習題數量顯示為原文 `{ch.title}` / `{n}題`：Python f-string 中 JS template literal 插值須寫成 `${{variable}}` 才能輸出 `${variable}`

### 移除
- `output/parse_exams.py`（v1，已由 v2 取代）
- `output/web/index.html`（內容與 `docs/index.html` 相同，合併為單一輸出）

---

## [0.1.0] - 2026-03-21

### 新增
- PDF 萃取腳本 `extract_pdfs.py`：以 pdfplumber 為主、PyMuPDF 為備援，支援文字與表格提取
- 題庫解析腳本 `parse_exams_v2.py`：從表格 JSON 解析四選一選擇題，處理全形 A/B/C/D 正規化
- 網站建置腳本 `build_web.py`：將題庫 JSON 內嵌為 JS 常數，產生單一自包含 HTML
- `docs/index.html`：iPAS 初級備考平台，含章節練習、模擬考試、計時、成績解析功能，部署於 GitHub Pages
- 手機版 UI 改善：漢堡選單（drawer 式側欄）、overlay 遮罩、考試 header flex-wrap、表格水平捲動、觸控目標優化
- `CLAUDE.md`、`AGENTS.md`：記錄專案結構、建置指令與開發規範
