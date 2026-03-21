# Changelog

本文件記錄專案的重要變更，格式參考 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.0.0/)。

---

## [Unreleased]

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
