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

資料 pipeline scripts 支援 `--level` 參數（預設：`初級`），路徑解析為 `data/{level}/`。`build_web.py` 沒有 `--level` 參數，因為前端目前固定以 `@data` 匯入 `data/初級/`。
新增等級時：① 在 `build_manifest.py` 的 `GUIDES_BY_LEVEL` 填入章節定義 ② 執行 `build_manifest.py --level 中級`。

### Step 0：生成章節目錄索引（僅在章節定義或 PDF 異動時執行）

```bash
uv run python3 scripts/build_manifest.py                    # 預設 初級
uv run python3 scripts/build_manifest.py --level 初級       # → data/初級/toc_manifest.json
python3 scripts/extract_pdf_pages_structured.py --level 初級 --all --force
python3 scripts/clean_pdf_page_text.py --level 初級 --all
python3 scripts/export_guide_outline_data.py
python3 scripts/codex_review_pdf_pages.py --level 初級 --key guide1 --page 7 --force
python3 scripts/build_pdf_outline.py --level 初級 --all
python3 scripts/export_pdf_image_gallery.py --level 初級 --force
```

### Guide content pipeline（Vision 提取，主路線）

```bash
# Step 1: PDF 每頁轉圖片送 Gemini Vision，結果快取於 data/{level}/pages_cache/
# 輸出 JSON：{type, headings（語義化標題）, markdown}，並自動生成 page_index.json（TOC）
# 需要 GEMINI_API_KEY；使用 gemini-2.5-flash（可透過 GOOGLE_MODEL 環境變數覆蓋）
uv run python3 scripts/pdf_vision_extract.py --level 初級 --all        # 兩科全跑（約 133 頁）
uv run python3 scripts/pdf_vision_extract.py --level 初級 --subject 1  # 只跑科目一
uv run python3 scripts/pdf_vision_extract.py --level 初級 --subject 1 --dry-run  # 估算費用
uv run python3 scripts/pdf_vision_extract.py --level 初級 --subject 1 --force    # 強制重跑
uv run python3 scripts/pdf_vision_extract.py --level 中級 --chapter mid-s1c1     # 單章（從 toc_manifest 自動解析頁碼範圍）
uv run python3 scripts/pdf_vision_extract.py --level 中級 --page-range 10 25     # 手動指定 1-based 頁碼範圍

# Step 2: 組裝章節 JSON（自動偵測 pages_cache → vision mode；否則 fallback regex mode）
uv run python3 scripts/parse_guides.py --level 初級      # → data/初級/guide/subject{1,2}_guide.json
uv run python3 scripts/parse_guides.py --level 初級 --subject 1  # 只跑科目一
python3 scripts/render_guide_page_images.py --level 初級 --all  # PDF 原頁截圖 → frontend/public/guide-pages/
```

### Guide content quality audit（PDF 更新後執行，審核內容品質）

```bash
# Step A: Gemini Vision 逐頁結構審核（使用 AUDIT_PROMPT，結果獨立於 pages_cache）
uv run python3 scripts/pdf_vision_audit.py --level 中級 --subject 1
uv run python3 scripts/pdf_vision_audit.py --level 中級 --subject 1 --page 6  # 單頁
# → data/{level}/audit_cache/{key}/page_NNN.json（gitignored）

# Step B: Codex CLI 比對 audit_cache 與 subject{N}_guide.json 的標題結構
python3 scripts/codex_audit_compare.py --level 中級 --subject 1
python3 scripts/codex_audit_compare.py --level 中級 --subject 1 --chapter mid-s1c1  # 單章
python3 scripts/codex_audit_compare.py --level 中級 --subject 1 --dry-run
# → data/{level}/audit_compare/{key}/{chapter_id}.json（gitignored）
# status: ok / warn / fail；summary.json 統計各科 fail 數

# Step C: 依審核結果補充 fail 章節（從 audit_cache 重組 Markdown 寫回 guide JSON）
uv run python3 scripts/supplement_guide_from_audit.py --level 中級 --subject 1
uv run python3 scripts/supplement_guide_from_audit.py --level 中級 --all
uv run python3 scripts/supplement_guide_from_audit.py --level 中級 --subject 1 --chapter mid-s1c1
uv run python3 scripts/supplement_guide_from_audit.py --level 中級 --all --strategy all  # 強制覆蓋 ok 章節
uv run python3 scripts/supplement_guide_from_audit.py --level 中級 --subject 1 --source pages_cache  # 從 pages_cache 組裝
```

### Step 3：解析後 LLM 審核（確認章節內容正確入庫）

```bash
uv run python3 scripts/audit_chapters.py --level 初級 --all         # 兩科全審
uv run python3 scripts/audit_chapters.py --level 初級 --subject 1   # 單科
uv run python3 scripts/audit_chapters.py --level 初級 --subject 1 --chapter s1c1  # 單章
uv run python3 scripts/audit_chapters.py --level 初級 --all --dry-run  # 預覽 prompt，不呼叫 API
# → data/初級/guide/subject{1,2}_audit_report.json
# 需要 ANTHROPIC_API_KEY，使用 claude-haiku-4-5
```

### Exam question pipeline

```bash
uv run python3 scripts/extract_pdfs.py --level 初級      # PDFs → data/初級/extracted/*.{txt,json}
uv run python3 scripts/parse_exams_v2.py --level 初級    # extracted JSON → data/初級/questions/*.json
python3 scripts/verify_data_alignment.py --level 初級    # PDF / manifest / guide / questions alignment check
# Optional: generate/enrich questions via Claude API
uv run python3 scripts/generate_questions.py --level 初級 --subject 1
uv run python3 scripts/generate_questions.py --level 初級 --subject 2
uv run python3 scripts/generate_questions.py --level 初級 --enrich      # add card fields
# Optional: multi-AI pipeline (Gemini 出題 → Codex 審核 → Claude 完稿 + 答題驗證)
python3 scripts/multi_ai_pipeline.py --level 初級 --subject 1 --chapter s1c1 --dry-run
python3 scripts/multi_ai_pipeline.py --level 初級 --subject 1 --count 3
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

- **`scripts/extract_pdfs.py`**: Uses `pdfplumber` for layout-aware text/table extraction and `PyMuPDF` as fallback. Writes per-PDF `.txt` and `.json` to `data/{level}/extracted/`. Guide PDFs are read from `toc_manifest.json`; exam PDFs are defined in `EXAM_PDFS_BY_LEVEL`. Supports `--level`.
- **`scripts/extract_pdf_pages_structured.py`**: Page-faithful extraction. Converts every PDF page to text, records text/image/table bbox positions, and crops detected images/tables to PNG under `data/{level}/page_extract/{key}/assets/`. Use this when PDF → txt may lose figures, tables, or layout context.
- **`scripts/clean_pdf_page_text.py`**: Cleans page starts/ends from `page_extract/` with per-PDF strategies, removes headers/footers/page labels/table labels, marks cross-page continuation, and rebuilds per-PDF outlines under `data/{level}/page_clean/{key}/`.
- **`scripts/codex_review_pdf_pages.py`**: Runs Codex CLI (`codex exec --sandbox read-only`) to review cleaned pages and write per-page audit JSON under `data/{level}/codex_page_review/{key}/`. Requires authenticated Codex CLI and network access; supports batching with `--limit`.
- **`scripts/export_guide_outline_data.py`**: Exports cleaned guide outlines to lightweight frontend metadata (`guideOutlines.json`) and split per-node content JSON under `frontend/src/generated/guideContent/{key}/`. GuidePage dynamically imports node content to keep the main bundle smaller. **⚠️ 重要：預設只處理 `初級`；若有中級資料必須加 `--all-levels`，否則 `guideContent/` 被清空後中級檔案不會重建。** 此外，腳本對所有 `（\d+）` 開頭行一律輸出 `####`，無法區分 PDF 中不同嵌套層次的同符號標題；s1c4（科目一 3.4）已手動修正 6 個頂層 heading 為 `###`，重跑後需補回（見下方「已知手動修正」）。
- **`scripts/build_pdf_outline.py`**: Builds reviewable PDF hierarchy outlines from `page_extract/`, using Vision headings when available and regex fallback otherwise. Outputs `data/{level}/outline/{key}_outline.{json,md}`.
- **`scripts/export_pdf_image_gallery.py`**: Copies cropped image/table assets from `page_extract/` into `frontend/public/pdf-assets/{level}/` and writes `gallery.json` for the `#/images` frontend viewer.
- **`scripts/parse_exams_v2.py`**: Parses question/answer tables from the extracted JSON (handles full-width characters A-D and parentheses). Outputs `mock_exam1.json`, `mock_exam2.json`, `sample_exam.json` to `data/{level}/questions/`. Note: `subject1/2_questions.json` are manually curated and not overwritten by this script. Supports `--level`.
- **`scripts/build_manifest.py`**: Single source of truth for chapter definitions. Contains the only hardcoded `GUIDES_BY_LEVEL` dict in the codebase. Opens PDFs to compute `page_range` (0-based) for each chapter and writes `data/{level}/toc_manifest.json`. Run whenever chapters or PDFs change; all other scripts load from this manifest at runtime. Supports `--level`.
- **`scripts/audit_chapters.py`**: LLM-based chapter content audit. Reads `subject{N}_guide.json`, sends each chapter's content + subtopics to Claude Haiku API, and checks whether all subtopics are covered and no content is misplaced. Outputs `subject{N}_audit_report.json` with `overall_status: PASS/WARN/FAIL`. Supports `--level`, `--subject`, `--all`, `--chapter`, `--dry-run`.
- **`scripts/pdf_vision_extract.py`**: Renders each PDF page to PNG (2× scale via PyMuPDF) and calls **Gemini Vision API** (`gemini-2.5-flash`) to extract structured Markdown. Results are cached per page at `data/{level}/pages_cache/{key}/page_NNN.json` (`type`: content/practice/skip, `headings`: `[{level, title}]`, `markdown`, `usage`). After all pages complete, auto-generates `page_index.json` (TOC with chapter boundaries). Re-runs only process missing/failed pages. Requires `GEMINI_API_KEY`. Supports `--level`, `--subject`/`--all`/`--chapter CHAPTER_ID`/`--page-range START END` (mutually exclusive), `--dry-run`, `--force`, `--page`.
- **`scripts/parse_guides.py`**: Assembles chapter JSON from vision cache (preferred) or falls back to regex-based text extraction. **Vision mode**: uses `pages_cache/{key}/` + PyMuPDF page-label map to determine per-chapter page ranges; concatenates LLM markdown. **Regex mode** (emergency fallback when cache <80% complete): splits `extracted/guide{N}.json` on in-document page-number anchors, cleans noise, converts structure via `text_to_markdown()`. Writes `data/{level}/guide/subject{N}_guide.json` with `content_format: 'markdown'`. Supports `--level`, `--subject`.
- **`scripts/generate_questions.py`**: Calls Claude API to generate new questions per chapter (`--subject N`) or add `card` fields to existing questions (`--enrich`). Use `--dry-run` to preview prompts without API calls. Questions follow the extended schema with `card`, `difficulty`, `type`, and `tags` fields. Supports `--level`.
- **`scripts/multi_ai_pipeline.py`**: Multi-AI question generation pipeline using three CLI tools via subprocess. Roles: Gemini (出題者) → Codex (審核者) → Claude (完稿者). After finalization all three AIs independently answer each question; if 2+ answer incorrectly the question is written to `flagged.json` for human review. Intermediate artifacts go to `data/{level}/pipeline/<run_id>/`. Final questions are merged into `subject{N}_questions.json`. Supports `--level`, `--subject`, `--chapter`, `--count`, `--dry-run`, `--skip-review`, `--skip-validation`, `--creator/reviewer/finalizer` overrides.
- **`scripts/render_guide_page_images.py`**: Renders guide JSON `source_pages` from PDF into `frontend/public/guide-pages/{level}/{key}/`. The guide page shows these screenshots in a collapsible section to preserve figures, tables, layout, and cross-page context that plain text extraction can lose.
- **`scripts/verify_data_alignment.py`**: Local consistency check for PDF references and app data. Compares current `toc_manifest.json` against `build_manifest.py` + actual PDF page labels, checks guide/exam PDF references, and verifies guide/question chapter IDs and titles match the manifest. Supports `--level`.
- **`scripts/build_web.py`**: Thin wrapper that runs `npm run build` inside `frontend/`. Vite bundles the React app and outputs to `docs/` (local only). Production deployment is handled by `.github/workflows/deploy.yml` — push to `main` triggers GitHub Actions to build and deploy to GitHub Pages automatically (`docs/` is gitignored).
- **`scripts/pdf_vision_audit.py`**: Second Gemini Vision pass using AUDIT_PROMPT (structured blocks with heading/paragraph/list/table/formula/image types). Distinct from `pdf_vision_extract.py` — purpose is auditing and enrichment, not content replacement. Results cached at `data/{level}/audit_cache/{key}/page_NNN.json` (gitignored). Requires `GEMINI_API_KEY`. Supports `--level`, `--subject`, `--page`, `--force`, `--dry-run`.
- **`scripts/codex_audit_compare.py`**: Compares `audit_cache` heading structure (A) against `subject{N}_guide.json` heading outline (B) via Codex CLI. Reports heading level mismatches, headings present in A but missing from B, and table/image issues. Outputs per-chapter JSON + `summary.json` under `data/{level}/audit_compare/{key}/` (gitignored). status values: `ok`/`warn`/`fail`. Supports `--level`, `--subject`, `--chapter`, `--dry-run`, `--force`.
- **`scripts/supplement_guide_from_audit.py`**: Replaces or supplements fail-status guide chapters with Markdown assembled from `audit_cache` blocks (or optionally `pages_cache` markdown). Keeps warn/ok chapters untouched by default. Backs up original guide as `*.bak`. Supports `--level`, `--subject`, `--all`, `--chapter`, `--strategy {fail,all}`, `--source {audit_cache,pages_cache}`, `--dry-run`.
- **`scripts/build_guide_tree.py`**: Builds reviewable guide hierarchy trees from `page_clean/` outputs. Feeds `export_guide_image_units.py`. Outputs to `data/{level}/guide_tree/{key}/tree.json` (gitignored).
- **`scripts/export_guide_image_units.py`**: Splits guide tree blocks into small topic units for infographic generation. Outputs `data/{level}/image_units/all_image_units.json` and `data/共用/image_units_all_levels.json`.
- **`scripts/generate_images.py`**: Calls Codex image generation API per unit from `image_units`, converts results to WebP, writes to `frontend/public/images/`. Requires authenticated Codex CLI.
- **`scripts/export_guide_images_data.py`**: Exports generated infographic metadata (`frontend/src/generated/guideImages.json`) for frontend rendering. Maps image units → guide node IDs for display in GuidePage.
- **`scripts/export_guide_embedded_exercises.py`**: Extracts embedded practice questions from `page_clean/` pages (numbered Q&A format). Supplements `questions/` with exercises found inline in the study guide PDF.
- **`scripts/gemini_exam_vision_extract.py`**: Extracts structured exam question records from official exam PDF pages via Gemini Vision. Separate from `pdf_vision_extract.py` — targets question/answer-key page types. Cache at `data/{level}/exam_pages_cache/`.
- **`scripts/export_resource_summary.py`**: Exports lightweight frontend resource summary (`frontend/src/generated/resourceSummary.json`) with chapter/question counts and coverage stats for both 初級 and 中級.
- **`scripts/export_question_generation_data.py`**: Exports seed files (guide content + existing questions per chapter) used by the question generation pipeline to provide context for `generate_questions.py` and `multi_ai_pipeline.py`.
- **`scripts/run_codex_exam_reference_answers.py`**: Generates detailed Codex reference answers for official exam questions. Retrieves top-k guide snippets per question via BM25-style token overlap, writes prompts to `data/{level}/pipeline/exam_reference_answers/{exam_key}/prompts/`, and runs `codex exec --sandbox read-only` to produce per-question JSON. Validates output schema (answer, reference_answer, option_analysis A-D, citations). Run without `--run` to write prompts only. After running, call `export_exam_reference_answers.py` to publish to frontend. Supports `--level`, `--exam {key|all}`, `--question-id`, `--limit`, `--force`, `--top-k`, `--timeout`.
- **`scripts/export_exam_reference_answers.py`**: Reads per-question JSON from `data/{level}/pipeline/exam_reference_answers/{exam_key}/outputs/` and merges into `frontend/src/generated/examReferenceAnswers/{route_key}.json`. Exam key → route key mapping defined in `ROUTES_BY_LEVEL`. Supports `--level`.
- **`frontend/`**: Vite project (React 19 + TypeScript + Tailwind CSS v4 + React Router v6 + Zustand). Source in `frontend/src/`. Build config in `frontend/vite.config.ts` — output dir is `../docs`, `@data` alias points to `../data/初級`. All JSON data is imported statically at build time (no runtime fetch). Routes use HashRouter to avoid GitHub Pages 404 issues. Chapter navigation and overview pages import `toc_manifest.json` to render titles, subtopics, PDF page ranges, and quick-links — do not add hardcoded chapter arrays back.
- The study-question pages are reached from sidebar `✏️` items (route `/practice/:subjectId/:chapterId`). On mobile widths the sidebar is hidden behind the `☰` drawer button, so navigation regressions should be checked there too.

**Note:** All scripts use hardcoded absolute `BASE = Path('/home/james/projects/ipas-test')`. Update `BASE` if moving the repo. All other paths are derived from `BASE / 'data' / level`.

## Output Files (Extended)

`data/{level}/toc_manifest.json` — 章節定義 SSOT，由 `build_manifest.py` 生成，需提交到 repo。前端 (`@data/toc_manifest.json`，固定指向 `初級`) 和所有 Python 腳本都從此讀取，不得在其他地方複製章節定義。

Treat `data/{level}/questions/*.json`, `data/{level}/guide/*.json`, and `docs/` as build artifacts. Only edit JSON files manually when intentionally curating content, and document the change.

`data/{level}/guide/` 輸出：
- `subject{N}_guide.json` — 供 `audit_chapters.py`、`codex_audit_compare.py`、`supplement_guide_from_audit.py` 使用的後端章節 JSON（`content_format: 'markdown'`）。**注意：前端 GuidePage 不直接讀此檔**；前端讀的是 `export_guide_outline_data.py` 從 `page_clean/` 生成的 `frontend/src/generated/guideContent/`。
- `subject{N}_audit_report.json` — LLM 章節審核報告；`overall_status: PASS/WARN/FAIL`；由 `audit_chapters.py` 生成

`data/{level}/pages_cache/` — Vision API 每頁快取（gitignored）。`content_format: 'markdown'` JSON 欄位控制前端渲染模式（GuidePage.tsx 用 ReactMarkdown 渲染）。
`data/{level}/audit_cache/` — `pdf_vision_audit.py` 的 AUDIT_PROMPT 逐頁結構快取（gitignored）。與 `pages_cache/` 使用不同 prompt，不可互換。
`data/{level}/audit_compare/` — `codex_audit_compare.py` 的比對報告（gitignored）。每章一個 JSON，`summary.json` 統計 fail/warn/ok 數量。
If `frontend/src/` or any data JSON changes, rerun `uv run python3 scripts/build_web.py` (or `cd frontend && npm run build`) to validate the production build. `docs/` is gitignored and normally should not be committed; GitHub Actions rebuilds it for Pages.

`data/{level}/pipeline/` holds intermediate artifacts from `multi_ai_pipeline.py` runs (draft, review, final, validation, flagged JSON per chapter). These are gitignored and do not need to be committed unless curating a specific run.

Question schema (extended with card fields):
```json
{
  "id": "s1c1q1", "question": "...", "options": {"A":"...","B":"...","C":"...","D":"..."},
  "answer": "C", "explanation": "...",
  "card": {"concept":"...","mnemonic":"...","confusion":"...","frequency":"高/中/低"},
  "difficulty": "易/中/難", "type": "概念定義型", "tags": ["..."],
  "generated_by": "multi_ai_pipeline | generate_questions | manual"
}
```

## Validation (No Automated Tests)

After running the pipeline:
- Check that `data/初級/toc_manifest.json` exists with `page_range` filled (not null) for all 7 chapters
- Run `python3 scripts/verify_data_alignment.py --level 初級`; it should pass before relying on PDF/manifest/app-data/screenshot alignment
- Check that expected files are regenerated under `data/初級/extracted/`, `data/初級/questions/`, `data/初級/guide/`
- `audit_chapters.py`: check `subject{N}_audit_report.json` — `PASS` is ideal; any `WARN` or `FAIL` chapters need review before question generation
- `pdf_vision_extract.py`: check `pages_cache/{key}/summary.json` — `missing` and `error` should be 0; check `page_index.json` exists
- `parse_guides.py`: confirm `[vision mode]` printed (not `[regex mode]`); each chapter should have > 1000 chars
- `parse_exams_v2.py`: exam1 and exam2 currently produce fewer than 50 parsed questions because some PDF rows are not machine-parsed; check WARN lines and actual JSON totals
- Spot-check JSON structure and rendered questions at `http://localhost:5173/` (dev) or a local production build; verify card panel appears after answering a question with `card` data
- On mobile-width layouts, confirm the `☰` drawer still exposes the `✏️` study-question entries
- Review `logs/` for extraction or parsing errors
- Frontend: run `cd frontend && npm run build` (tsc + vite) — zero TypeScript errors expected

If the card panel is missing, verify the underlying question JSON actually contains `card` fields before treating it as a frontend regression.

Future tests should go in `tests/test_*.py`.

## 已知手動修正（重跑 pipeline 後需補回）

### s1c4 本節階層 heading 層級（科目一 3.4 鑑別式AI與生成式AI概念）

**問題**：`export_guide_outline_data.py` 對所有 `（\d+）` 開頭行一律輸出 `####`（h4），但 PDF 原文中此符號同時用於兩個嵌套層次，導致「本節階層」出現 `（1）→（1）` 同層顯示。

**根本原因**：PDF 內各 `（\d+）` 文字區塊的 x 座標完全相同（70.2），無縮排差異可供判斷層次。

**修正方式**：執行以下腳本，將 6 個頂層項目的 heading 從 h4 改回 h3：

```python
import json
from pathlib import Path

s1c4 = Path('frontend/src/generated/guideContent/初級-guide1/s1c4.json')
data = json.loads(s1c4.read_text(encoding='utf-8'))
content = data['content']
fixes = [
    ('#### （1）鑑別式AI 的原理與應用\n',        '### （1）鑑別式AI 的原理與應用\n'),
    ('#### （2）生成式AI 的原理與應用\n',         '### （2）生成式AI 的原理與應用\n'),
    ('#### （3）鑑別式AI 與生成式AI 的技術差異\n','### （3）鑑別式AI 與生成式AI 的技術差異\n'),
    ('#### （1）整合應用的價值\n',               '### （1）整合應用的價值\n'),
    ('#### （2）整合應用的技術優勢\n',            '### （2）整合應用的技術優勢\n'),
    ('#### （3）整合應用的挑戰與解決策略\n',      '### （3）整合應用的挑戰與解決策略\n'),
]
targets = {f.split('\n')[0].lstrip('#').strip() for f, _ in fixes}
for old, new in fixes:
    content = content.replace(old, new)
data['content'] = content
for h in data.get('headings', []):
    if h.get('title') in targets and h.get('level') == 4:
        h['level'] = 3
s1c4.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
```

**觸發時機**：每次執行 `export_guide_outline_data.py`（含 `--all-levels`）後均需補回。

### s1c4 H4 標題截短（本節階層 (1)→(1) 問題）

**問題**：s1c4 在「鑑別式AI原理」與「生成式AI原理」兩個 H3 節下，H4 模型條目仍保有 `（1）（2）...` 前綴，導致 本節階層 顯示「(1) 鑑別式AI…」下方又出現「(1) 邏輯迴歸…」同層視覺。

**修正方式**：執行以下腳本，將 8 個 H4 標題去掉序號前綴並截短為模型名稱：

```python
import json
from pathlib import Path

s1c4 = Path('frontend/src/generated/guideContent/初級-guide1/s1c4.json')
data = json.loads(s1c4.read_text(encoding='utf-8'))
fixes = {
    '（1） 邏輯迴歸（Logistic Regression）是鑑別式AI 中最簡單且最基礎的分類模型': '邏輯迴歸（Logistic Regression）',
    '（2） 支援向量機（Support Vector Machine, SVM）是一種強大的分類模型，其核心': '支援向量機（SVM）',
    '（3） 決策樹（Decision Tree）是一種基於樹形結構進行數據分類的模型。其透過': '決策樹（Decision Tree）',
    '（4） 隨機森林（Random Forest）是決策樹的集成學習方法，其透過構建多棵決策': '隨機森林（Random Forest）',
    '（5） 神經網路（Neural Networks）是一種模擬生物神經系統的非線性模型，透過': '神經網路（Neural Networks）',
    '（1） 生成對抗網路（Generative Adversarial Networks, GAN）是生成式AI 中最具': '生成對抗網路（GAN）',
    '（2） 變分自編碼器（Variational Autoencoders, VAE）是一種基於概率生成模型的': '變分自編碼器（VAE）',
    '（3） 擴散模型（Diffusion Models）是一種基於逐步添加與去除雜訊的數據生成方': '擴散模型（Diffusion Models）',
}
for h in data.get('headings', []):
    if h['title'] in fixes:
        h['title'] = fixes[h['title']]
s1c4.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
```

**觸發時機**：每次執行 `export_guide_outline_data.py`（含 `--all-levels`）後均需補回，**且在 H3 heading 層級修正腳本之後執行**。

## Coding Style

- 4-space indentation, `snake_case`, short module docstrings
- `Path`-based filesystem access (not `os.path` strings)
- Scripts are self-contained; small helper functions over deep nesting

## Commit Convention

Imperative, scoped subjects: `build: refresh mock exam JSON`, `parser: improve table extraction`.
