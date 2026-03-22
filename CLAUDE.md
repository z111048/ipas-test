# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

A content-generation workspace for iPAS AI exam study materials (初級 AI 應用規劃師). Source PDFs live under `data/初級/pdfs/`. The pipeline extracts them into structured JSON, then assembles a single-file static web app deployed via GitHub Pages.

## 核心目標

本平台的最終目標是：**根據解析完成的 MD 教材（study guide）與官方提供的樣張/歷屆題目，針對特定章節綜合出高品質模擬試題。**

PDF→MD 解析品質直接決定出題品質，因此前處理必須正確：
- 每個頁面必須被正確歸入對應章節，避免章節內容混入或缺漏
- 解析後須執行 LLM 審核（`audit_chapters.py`），確認各章節涵蓋預定 subtopics
- `data/初級/toc_manifest.json` 是所有腳本與前端共用的章節定義單一真實來源（SSOT），由 `build_manifest.py` 生成

## Build Pipeline

### Step 0：生成章節目錄索引（僅在章節定義或 PDF 異動時執行）

```bash
uv run python3 scripts/build_manifest.py   # → data/初級/toc_manifest.json
```

### Guide content pipeline

兩條路線，擇一使用：

**路線 A：Span 提取（無 LLM，推薦先跑）**
```bash
# 完全確定性、不耗 API token；以 PyMuPDF 字型尺寸/粗體判斷 6 層結構
uv run python3 scripts/guide_to_md.py --all              # 兩科全跑
uv run python3 scripts/guide_to_md.py --subject 1        # 只跑科目一
uv run python3 scripts/guide_to_md.py --subject 1 --chapter s1c1  # 單章
uv run python3 scripts/guide_to_md.py --subject 1 --threshold 0.90  # 調低驗證門檻
# → data/初級/guide/subject{1,2}_guide.json
#   data/初級/guide/subject{1,2}_guide.md
#   data/初級/guide/subject{1,2}_guide_nested.json
#   data/初級/guide/subject{1,2}_validation_report.json
```

**路線 B：Vision 提取（LLM，當 span 效果不足時使用）**
```bash
# Step 1: PDF 每頁轉圖片送 Gemini Vision，結果快取於 data/初級/pages_cache/
# 輸出 JSON：{type, headings（語義化標題）, markdown}，並自動生成 page_index.json（TOC）
# 需要 GEMINI_API_KEY；使用 gemini-2.5-flash（可透過 GOOGLE_MODEL 環境變數覆蓋）
uv run python3 scripts/pdf_vision_extract.py --all        # 兩科全跑（約 133 頁，~$2）
uv run python3 scripts/pdf_vision_extract.py --subject 1  # 只跑科目一
uv run python3 scripts/pdf_vision_extract.py --subject 1 --dry-run  # 估算費用
uv run python3 scripts/pdf_vision_extract.py --subject 1 --force    # 強制重跑所有頁

# Step 2: 組裝章節 JSON（自動偵測 pages_cache → vision mode；否則 fallback regex mode）
uv run python3 scripts/parse_guides.py      # → data/初級/guide/subject{1,2}_guide.json
```

### Step 3：解析後 LLM 審核（確認章節內容正確入庫）

```bash
uv run python3 scripts/audit_chapters.py --all         # 兩科全審
uv run python3 scripts/audit_chapters.py --subject 1   # 單科
uv run python3 scripts/audit_chapters.py --subject 1 --chapter s1c1  # 單章
uv run python3 scripts/audit_chapters.py --all --dry-run  # 預覽 prompt，不呼叫 API
# → data/初級/guide/subject{1,2}_audit_report.json
# 需要 ANTHROPIC_API_KEY，使用 claude-haiku-4-5
```

### Exam question pipeline

```bash
uv run python3 scripts/extract_pdfs.py      # PDFs → data/初級/extracted/*.{txt,json}
uv run python3 scripts/parse_exams_v2.py    # extracted JSON → data/初級/questions/*.json
# Optional: generate/enrich questions via Claude API
uv run python3 scripts/generate_questions.py --subject 1
uv run python3 scripts/generate_questions.py --subject 2
uv run python3 scripts/generate_questions.py --enrich      # add card fields
# Optional: multi-AI pipeline (Gemini 出題 → Codex 審核 → Claude 完稿 + 答題驗證)
python3 scripts/multi_ai_pipeline.py --subject 1 --chapter s1c1 --dry-run
python3 scripts/multi_ai_pipeline.py --subject 1 --count 3
```

### Frontend

```bash
cd frontend && npm run dev -- --host   # dev server，--host 讓 Windows 可存取
uv run python3 scripts/build_web.py   # production build → docs/
```

Dependencies are managed via `uv` (see `pyproject.toml`). Run `uv sync` to install after cloning.
Python packages: `pdfplumber`, `PyMuPDF` (`fitz`), `anthropic`, `google-genai`.
`pdf_vision_extract.py` requires `GEMINI_API_KEY` environment variable (uses `gemini-2.5-flash`; override model with `GOOGLE_MODEL`).
`generate_questions.py` and `audit_chapters.py` require `ANTHROPIC_API_KEY` environment variable.
`multi_ai_pipeline.py` requires the `gemini`, `codex`, and `claude` CLI tools to be installed and authenticated. Uses subprocess only — no Python packages needed, so `uv run` is not required.
Frontend dependencies: run `cd frontend && npm install` after cloning (requires Node.js).

## Architecture

- **`scripts/extract_pdfs.py`**: Uses `pdfplumber` for layout-aware text/table extraction and `PyMuPDF` as fallback. Writes per-PDF `.txt` and `.json` to `data/初級/extracted/`. The `LEVEL` variable controls which data subdirectory is used.
- **`scripts/parse_exams_v2.py`**: Parses question/answer tables from the extracted JSON (handles full-width characters A-D and parentheses). Outputs `mock_exam1.json`, `mock_exam2.json`, `sample_exam.json` to `data/初級/questions/`. Note: `subject1/2_questions.json` are manually curated and not overwritten by this script.
- **`scripts/build_manifest.py`**: Single source of truth for chapter definitions. Contains the only hardcoded `GUIDES` dict in the codebase. Opens PDFs to compute `page_range` (0-based) for each chapter and writes `data/初級/toc_manifest.json`. Run whenever chapters or PDFs change; all other scripts load from this manifest at runtime.
- **`scripts/audit_chapters.py`**: LLM-based chapter content audit. Reads `subject{N}_guide.json`, sends each chapter's content + subtopics to Claude Haiku API, and checks whether all subtopics are covered and no content is misplaced. Outputs `subject{N}_audit_report.json` with `overall_status: PASS/WARN/FAIL`. Supports `--subject`, `--all`, `--chapter`, `--dry-run`.
- **`scripts/guide_to_md.py`**: Deterministic span-based guide extractor — no LLM required. Uses PyMuPDF font size/bold flags to classify 6 heading levels (L2 ≥18pt bold → `##`, L3 ≥13pt bold → `###`, L4 bold `（N）` → `####`, L5 bold `A.` → `#####`, L6 bullet → `-`, L0 body). Strips in-guide practice question sections (`filter_practice_lines()`) before processing. Merges continuation lines, builds a nested tree, serialises to Markdown + JSON. Validates key term retention (default threshold 95%). Outputs `subject{N}_guide.json`, `subject{N}_guide.md`, `subject{N}_guide_nested.json`, `subject{N}_validation_report.json` to `data/初級/guide/`. Supports `--subject`, `--all`, `--chapter`, `--threshold`.
- **`scripts/pdf_vision_extract.py`**: Renders each PDF page to PNG (2× scale via PyMuPDF) and calls **Gemini Vision API** (`gemini-2.5-flash`) to extract structured Markdown. Results are cached per page at `data/初級/pages_cache/{key}/page_NNN.json` (`type`: content/practice/skip, `headings`: `[{level, title}]`, `markdown`, `usage`). After all pages complete, auto-generates `page_index.json` (TOC with chapter boundaries). Re-runs only process missing/failed pages. Requires `GEMINI_API_KEY`. Supports `--subject`, `--all`, `--dry-run`, `--force`, `--page`.
- **`scripts/parse_guides.py`**: Assembles chapter JSON from vision cache (preferred) or falls back to regex-based text extraction. **Vision mode**: uses `pages_cache/{key}/` + PyMuPDF page-label map to determine per-chapter page ranges; concatenates LLM markdown. **Regex mode** (fallback when cache <80% complete): splits `extracted/guide{N}.json` on in-document page-number anchors, cleans noise, converts structure via `text_to_markdown()`. Writes `data/初級/guide/subject{1,2}_guide.json` with `content_format: 'markdown'`.
- **`scripts/generate_questions.py`**: Calls Claude API to generate new questions per chapter (`--subject N`) or add `card` fields to existing questions (`--enrich`). Use `--dry-run` to preview prompts without API calls. Questions follow the extended schema with `card`, `difficulty`, `type`, and `tags` fields.
- **`scripts/multi_ai_pipeline.py`**: Multi-AI question generation pipeline using three CLI tools via subprocess. Roles: Gemini (出題者) → Codex (審核者) → Claude (完稿者). After finalization all three AIs independently answer each question; if 2+ answer incorrectly the question is written to `flagged.json` for human review. Intermediate artifacts go to `data/初級/pipeline/<run_id>/`. Final questions are merged into `subject{N}_questions.json`. Supports `--subject`, `--chapter`, `--count`, `--dry-run`, `--skip-review`, `--skip-validation`, `--creator/reviewer/finalizer` overrides.
- **`scripts/build_web.py`**: Thin wrapper that runs `npm run build` inside `frontend/`. Vite bundles the React app and outputs to `docs/` (HTML + `assets/` JS/CSS). The site is deployed from `docs/` on the `main` branch via GitHub Pages.
- **`frontend/`**: Vite project (React 19 + TypeScript + Tailwind CSS v4 + React Router v6 + Zustand). Source in `frontend/src/`. Build config in `frontend/vite.config.ts` — output dir is `../docs`, `@data` alias points to `../data/初級`. All JSON data is imported statically at build time (no runtime fetch). Routes use HashRouter to avoid GitHub Pages 404 issues. `SubjectOverviewPage.tsx` imports `toc_manifest.json` to render chapter subtopics, PDF page ranges, and quick-links — do not add hardcoded chapter arrays back.
- The study-question pages are reached from sidebar `✏️` items (route `/practice/:subjectId/:chapterId`). On mobile widths the sidebar is hidden behind the `☰` drawer button, so navigation regressions should be checked there too.

**Note:** All scripts use hardcoded absolute paths to `/home/james/projects/ipas-test`. Update `BASE`/`ROOT`/`OUT` variables if moving the repo.

## Output Files (Extended)

`data/初級/toc_manifest.json` — 章節定義 SSOT，由 `build_manifest.py` 生成，需提交到 repo。前端 (`@data/toc_manifest.json`) 和所有 Python 腳本都從此讀取，不得在其他地方複製章節定義。

Treat `data/初級/questions/*.json`, `data/初級/guide/*.json`, and `docs/` as build artifacts. Only edit JSON files manually when intentionally curating content, and document the change.

`data/初級/guide/` 輸出：
- `subject{N}_guide.json` — 前端使用的章節 JSON（`content_format: 'markdown'`）
- `subject{N}_guide.md` — 純 Markdown 全文（除錯/閱讀用）；僅路線 A 輸出
- `subject{N}_guide_nested.json` — 完整巢狀樹（未來用途）；僅路線 A 輸出
- `subject{N}_validation_report.json` — 關鍵詞保留率驗證報告；`overall_passed: true` 表示通過；僅路線 A 輸出
- `subject{N}_audit_report.json` — LLM 章節審核報告；`overall_status: PASS/WARN/FAIL`；由 `audit_chapters.py` 生成

`data/初級/pages_cache/` — Vision API 每頁快取（gitignored）。`content_format: 'markdown'` JSON 欄位控制前端渲染模式（GuidePage.tsx 用 ReactMarkdown 渲染）。
If `frontend/src/` or any data JSON changes, rerun `uv run python3 scripts/build_web.py` (or `cd frontend && npm run build`) and commit the regenerated `docs/` together with the source change.

`data/初級/pipeline/` holds intermediate artifacts from `multi_ai_pipeline.py` runs (draft, review, final, validation, flagged JSON per chapter). These are gitignored and do not need to be committed unless curating a specific run.

Question schema (extended with card fields):
```json
{
  "id": "s1c1q1", "question": "...", "options": {"A":"...","B":"...","C":"...","D":"..."},
  "answer": "C", "explanation": "...",
  "card": {"concept":"...","mnemonic":"...","confusion":"...","frequency":"高/中/低"},
  "difficulty": "易/中/難", "type": "概念定義型", "tags": ["..."]
}
```

## Validation (No Automated Tests)

After running the pipeline:
- Check that `data/初級/toc_manifest.json` exists with `page_range` filled (not null) for all 7 chapters
- Check that expected files are regenerated under `data/初級/extracted/`, `data/初級/questions/`, `data/初級/guide/`
- `audit_chapters.py`: check `subject{N}_audit_report.json` — `overall_status` should be `PASS`; any `WARN` or `FAIL` chapters need review before question generation
- `guide_to_md.py`: check `subject{N}_validation_report.json` — `overall_passed` should be `true`; each chapter should log `PASS` with retention ≥ 95%
- `pdf_vision_extract.py`: check `pages_cache/{key}/summary.json` — `missing` and `error` should be 0
- `parse_guides.py`: confirm `[vision mode]` printed (not `[regex mode]`); each chapter should have > 1000 chars
- `parse_exams_v2.py`: exam1 and exam2 should each produce ~50 questions (check for WARN lines)
- Spot-check JSON structure and rendered questions at `http://localhost:5173/` (dev) or `docs/index.html` (build); verify card panel appears after answering a question with `card` data
- On mobile-width layouts, confirm the `☰` drawer still exposes the `✏️` study-question entries
- Review `logs/` for extraction or parsing errors
- Frontend: run `cd frontend && npm run build` (tsc + vite) — zero TypeScript errors expected

If the card panel is missing, verify the underlying question JSON actually contains `card` fields before treating it as a frontend regression.

Future tests should go in `tests/test_*.py`.

## Coding Style

- 4-space indentation, `snake_case`, short module docstrings
- `Path`-based filesystem access (not `os.path` strings)
- Scripts are self-contained; small helper functions over deep nesting

## Commit Convention

Imperative, scoped subjects: `build: refresh mock exam JSON`, `parser: improve table extraction`.
