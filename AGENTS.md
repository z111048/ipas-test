# Repository Guidelines

## Project Structure & Module Organization

This repository is a content-generation workspace for the iPAS AI exam study materials. Source PDFs live under `data/<等級>/pdfs/`. Scripts are in `scripts/`. Generated artifacts go under `data/<等級>/` and are gitignored.

**Core goal**: Synthesize high-quality mock exam questions from parsed study guide Markdown + official exam samples, per chapter. Parse quality directly determines question quality.

**Single source of truth**: `data/{level}/toc_manifest.json` defines all subject/chapter metadata. Data scripts and the frontend read from it. Never duplicate chapter definitions elsewhere; derive chapter navigation, guide links, and practice links from the manifest.

Data pipeline scripts support `--level` (default `初級`); paths resolve to `data/{level}/`. `scripts/build_web.py` has no `--level` flag because the frontend currently imports `@data` from `data/初級/` at build time.

- `scripts/build_manifest.py`: **SSOT generator** — the only script with hardcoded chapter definitions (`GUIDES_BY_LEVEL` dict, keyed by level). Computes PDF page ranges via PyMuPDF and writes `data/{level}/toc_manifest.json`. Run whenever chapters or PDFs change. Supports `--level`, `--dry-run`.
- `scripts/extract_pdf_pages_structured.py`: **Page-faithful PDF extraction** — converts every PDF page to text, records text/image/table bounding boxes, and crops each detected image/table to PNG under `data/{level}/page_extract/{key}/assets/`. Supports `--level`, `--key`, `--all`, `--force`.
- `scripts/clean_pdf_page_text.py`: **Page text cleanup + hierarchy rebuild** — reads `page_extract/`, applies per-PDF cleanup strategies, removes page headers/footers/page labels/table headers, marks `continues_from_previous` / `continues_to_next`, and writes cleaned page JSON plus complete outlines under `data/{level}/page_clean/{key}/`. Supports `--level`, `--key`, `--all`.
- `scripts/codex_review_pdf_pages.py`: **Codex page review** — uses `codex exec --sandbox read-only` to review cleaned pages and writes per-page review JSON under `data/{level}/codex_page_review/{key}/`. Requires authenticated Codex CLI and network access. Supports `--level`, `--key`, `--all`, `--page`, `--limit`, `--force`, `--with-image`.
- `scripts/build_guide_tree.py`: **Guide tree validator** — builds reviewable guide hierarchy trees from `page_clean/` + `page_extract/`, writes `data/{level}/guide_tree/{key}/tree.json`, `blocks.json`, and `warnings.json`, and validates heading depth, sibling marker continuity, page ranges, and embedded chapter exercises. Supports `--level`, `--key`, `--all`.
- `scripts/export_guide_outline_data.py`: exports cleaned guide PDF hierarchy metadata to `frontend/src/generated/guideOutlines.json` and split per-node content files to `frontend/src/generated/guideContent/{key}/`. Each content JSON includes Markdown fallback plus structured `blocks[]` (`heading`, `paragraph`, `list_item`, `table`, `question`, `answer`) with unbounded `depth` so the frontend can render PDF-internal hierarchy beyond Markdown `h1`-`h6`. The frontend uses the metadata tree for route navigation and dynamic imports content per route; guide pages prefer `blocks[]` for reading layout and side-section anchors. Use `--use-guide-tree` after running `build_guide_tree.py` to export from validated tree/block artifacts instead of rebuilding hierarchy inline.
- `scripts/export_guide_embedded_exercises.py`: extracts official embedded chapter exercises from cleaned guide PDF pages and writes `data/{level}/questions/subject{N}_guide_exercises.json`. These are separate from AI-generated chapter practice questions. Supports `--level`.
- `scripts/export_question_generation_data.py`: exports guide/question seed files for the question-generation pipeline from `frontend/src/generated/guideOutlines.json` + split guide content. Writes `data/{level}/guide/subject{N}_guide.json` and initializes/refreshes `data/{level}/questions/subject{N}_questions.json` while preserving existing questions. Supports `--level`, `--all-levels`.
- `scripts/build_pdf_outline.py`: **PDF outline builder** — analyzes structured page extraction and Vision headings to build reviewable hierarchical outlines under `data/{level}/outline/`. Supports `--level`, `--key`, `--all`.
- `scripts/export_pdf_image_gallery.py`: exports cropped image/table assets from `page_extract/` to `frontend/public/pdf-assets/{level}/` with `gallery.json` for the frontend image viewer. Supports `--level`, `--force`.
- `scripts/pdf_vision_extract.py`: **Guide extraction** — renders each PDF page to PNG and calls Gemini Vision API (`gemini-2.5-flash`). Results cached at `data/{level}/pages_cache/{key}/page_NNN.json`; auto-generates `page_index.json` (TOC) on completion. Requires `GEMINI_API_KEY`. Supports `--level`, `--subject`, `--all`, `--dry-run`, `--force`, `--page`.
- `scripts/gemini_exam_vision_extract.py`: **Exam Vision OCR** — renders official exam/sample PDF pages from `EXAM_PDFS_BY_LEVEL` to PNG and calls Gemini Vision API with an exam-specific schema for questions, answers, shared contexts, and visual references. Results cached at `data/{level}/exam_pages_cache/{key}/page_NNN.json`. Requires `GEMINI_API_KEY`. Supports `--level`, `--key`, `--all`, `--page`, `--force`, `--dry-run`.
- `scripts/parse_guides.py`: **Guide assembly** — assembles chapter JSON from vision cache (preferred) or falls back to regex extraction. Reads chapter definitions from `toc_manifest.json`. Supports `--level`, `--subject`.
- `scripts/audit_chapters.py`: **LLM chapter audit** — reads `subject{N}_guide.json` and calls Claude Haiku to verify each chapter covers its expected subtopics. Outputs `subject{N}_audit_report.json`. Run after guide extraction. Requires `ANTHROPIC_API_KEY`. Supports `--level`, `--subject`, `--all`, `--chapter`, `--dry-run`.
- `scripts/extract_pdfs.py`: extracts text and tables from PDFs into `data/{level}/extracted/`. Guide PDFs from `toc_manifest.json`; exam PDFs from `EXAM_PDFS_BY_LEVEL`. Supports `--level`.
- `scripts/parse_exams_v2.py`: turns extracted content into mock-exam JSON under `data/{level}/questions/`, records original PDF page references, and attaches cropped/page image assets for image-based exam questions from `page_extract/`. Supports `--level`.
- `scripts/generate_questions.py`: calls the Claude API to generate new questions or add `card` fields to existing ones. Requires `ANTHROPIC_API_KEY`. Supports `--level`, `--subject`, `--enrich`.
- `scripts/multi_ai_pipeline.py`: multi-AI pipeline using Gemini (出題) → Codex (審核) → Claude (完稿) CLI tools via subprocess. Includes answer-validation stage where all three AIs answer each question; questions with 2+ wrong answers are flagged to `flagged.json`. Intermediate output goes to `data/{level}/pipeline/<run_id>/`; final questions merged into `subject{N}_questions.json`. Supports `--level`.
- `scripts/render_guide_page_images.py`: renders source PDF pages referenced by guide JSON into `frontend/public/guide-pages/{level}/{key}/` so the site can show original page screenshots for figures, tables, and layout context. Supports `--level`, `--subject`, `--all`, `--force`.
- `scripts/verify_data_alignment.py`: local consistency check for PDF references and app data. Compares the current `toc_manifest.json` against `build_manifest.py` + actual PDF page labels, checks guide/exam PDF references, and verifies guide/question chapter IDs and titles match the manifest. Supports `--level`.
- `scripts/build_web.py`: thin wrapper that runs `npm run build` inside `frontend/`, outputting the React app to `docs/`.
- `frontend/`: Vite project (React 19 + TypeScript + Tailwind CSS v4 + React Router v6 + Zustand). Source in `frontend/src/`; build config in `frontend/vite.config.ts`. JSON data is imported statically via `@data` (points to `data/初級/`) and `@data-mid` (points to `data/中級/`) at build time. Chapter navigation and overview pages read chapter metadata from `toc_manifest.json`. Guide reading pages render `GuideContent.blocks[]` first and fall back to Markdown only when blocks are absent; the “本節階層” sidebar intentionally shows only section heading depths 3–4 (`1.` and `（1）`) while the main content preserves deeper indentation. `frontend/src/generated/` and `frontend/public/` PDF assets are versioned static inputs for the site; regenerate them with the export/render scripts when PDF extraction changes.
- `data/{level}/toc_manifest.json`: committed static file — chapter definitions SSOT. Regenerate with `build_manifest.py --level {level}` when chapters change.
- `data/{level}/extracted/`, `data/{level}/page_extract/`, `data/{level}/page_clean/`, `data/{level}/guide_tree/`, `data/{level}/codex_page_review/`, `data/{level}/outline/`, `data/{level}/questions/`, `data/{level}/guide/`, `data/{level}/analysis/`, `data/{level}/pipeline/`, and `logs/`: generated data, page-faithful extraction, cleaned page text, validated guide tree artifacts, Codex page audit output, outline analysis, exam payloads, guide content, analysis output, pipeline run artifacts, and run logs.

Treat `data/{level}/questions/*.json` and `data/{level}/guide/*.json` as build outputs unless you are intentionally curating content. `docs/` is a local Vite build output and is gitignored; GitHub Pages is built by `.github/workflows/deploy.yml`.

## Build, Test, and Development Commands

This project uses `uv` for dependency management. Run `uv sync` after cloning to set up the virtual environment. Use `uv run` to execute scripts within the environment.

**Step 0 (run when chapters/PDFs change):**
- `uv run python3 scripts/build_manifest.py`: regenerate `data/初級/toc_manifest.json` from embedded GUIDES_BY_LEVEL definition + PDF page calculations.
- `python3 scripts/extract_pdf_pages_structured.py --level 初級 --all --force`: regenerate page-level text, bbox markers, and image/table crops for all PDFs.
- `python3 scripts/clean_pdf_page_text.py --level 初級 --all`: clean page starts/ends, mark page continuation, and rebuild per-PDF hierarchy outlines.
- `python3 scripts/codex_review_pdf_pages.py --level 初級 --key guide1 --page 7 --force`: review one cleaned page with Codex CLI in read-only sandbox; use `--all --limit N` to run in batches across PDFs.
- `python3 scripts/build_guide_tree.py --level 初級 --all`: build validated guide tree/block artifacts and warnings from cleaned page outputs.
- `python3 scripts/export_guide_outline_data.py --use-guide-tree`: refresh frontend guide outline metadata and split guide content imports from validated guide tree artifacts. Omit `--use-guide-tree` only when intentionally using the legacy inline hierarchy path.
- `python3 scripts/export_guide_embedded_exercises.py --level 初級`: extract learning-guide embedded chapter exercises into independent `*_guide_exercises.json` files.
- `python3 scripts/export_question_generation_data.py --level 中級`: refresh question-generation guide seeds and empty/preserved chapter-question files for a level.
- `python3 scripts/build_pdf_outline.py --level 初級 --all`: rebuild reviewable PDF hierarchy outlines from the page extraction.
- `python3 scripts/export_pdf_image_gallery.py --level 初級 --force`: refresh frontend image/table gallery assets.

**Guide pipeline (Vision extraction via Gemini):**
- Step 1: `uv run python3 scripts/pdf_vision_extract.py --level 初級 --all` — render pages to PNG, call Gemini Vision API, cache results.
- Step 2: `uv run python3 scripts/parse_guides.py --level 初級` — assemble chapter JSON from vision cache.
- Step 2b: `python3 scripts/render_guide_page_images.py --level 初級 --all` — render original PDF page screenshots referenced by guide JSON.
- Step 3 (required): `uv run python3 scripts/audit_chapters.py --level 初級 --all` — LLM chapter content audit. Use `--dry-run` to preview prompts.

**Exam pipeline:**
- `uv run python3 scripts/extract_pdfs.py`: extract text and tables from the PDF set into `data/初級/extracted/`.
- `uv run python3 scripts/gemini_exam_vision_extract.py --level 中級 --key exam2 --dry-run`: preview Gemini Vision OCR work for an official exam PDF; remove `--dry-run` to cache per-page structured question OCR.
- `uv run python3 scripts/parse_exams_v2.py`: generate `mock_exam1.json`, `mock_exam2.json`, and `sample_exam.json` from extracted JSON tables.
- `uv run python3 scripts/generate_questions.py --subject 1` (or `--subject 2`, `--enrich`): generate/enrich questions via Claude API (optional).
- `python3 scripts/multi_ai_pipeline.py --level 中級 --subject 1 [--chapter mid-s1c1] [--count 3] [--dry-run]`: run multi-AI pipeline for question generation, review, finalization, and answer validation (optional; requires gemini/codex/claude CLIs; uses subprocess only, no venv needed).
- `python3 scripts/verify_data_alignment.py --level 初級`: verify PDF references, manifest page ranges, guide JSON, question JSON, and guide page screenshots are aligned.

**Frontend:**
- `uv run python3 scripts/build_web.py`: rebuild the frontend via Vite (`npm run build` in `frontend/`), outputting to `docs/`.
- `cd frontend && npm run dev -- --host`: start the Vite dev server (use `--host` to expose to Windows from WSL).

If `frontend/src/` or any data JSON changes, rerun `uv run python3 scripts/build_web.py` or `cd frontend && npm run build` to validate the production build. Do not commit `docs/` unless deployment strategy changes; it is currently gitignored and generated by GitHub Actions.

## Coding Style & Naming Conventions
Follow the existing Python style: 4-space indentation, `snake_case` for functions and variables, short module docstrings, and `Path`-based filesystem access. Keep scripts self-contained and readable; prefer small helper functions over deeply nested logic. Name generated JSON files by content, for example `mock_exam1.json` or `subject2_questions.json`.

## Testing Guidelines

There is no formal automated test suite in this workspace yet. Validate changes by rerunning the pipeline and checking outputs:

- confirm `data/初級/toc_manifest.json` exists and has `page_range` filled for all 7 chapters (not null)
- `python3 scripts/verify_data_alignment.py --level 初級`: should pass before relying on the PDF/manifest/app-data alignment
- `audit_chapters.py`: check `subject{N}_audit_report.json` — `PASS` is ideal; any `WARN`/`FAIL` needs review before generating new questions
- confirm expected files are regenerated in `data/初級/extracted/`, `data/初級/questions/`, `data/初級/guide/`
- `parse_exams_v2.py`: check WARN lines, actual JSON totals, and image-based exam questions with `images[]` attachments; image paths should resolve under `frontend/public/pdf-assets/{level}/`
- `parse_guides.py`: each chapter should have > 1000 chars of content
- `build_guide_tree.py`: `warnings.json` should have zero `fatal` entries; review `warn` entries before trusting newly extracted PDFs.
- `export_guide_outline_data.py --use-guide-tree`: each generated guide content JSON should include non-empty `blocks[]`; spot-check representative pages such as `frontend/src/generated/guideContent/中級-guide1/mid-s1c1.json` for depth 2–8 blocks and verify headings/questions are not conflated.
- spot-check JSON structure and a few rendered questions at `http://localhost:5173/` or in a local production build; verify the card panel appears after answering a question that has `card` data; verify subject overview and sidebar links reflect `toc_manifest.json`
- review `logs/` for extraction or parsing errors
- on narrow/mobile layouts, verify the study-question entry points are still reachable from the sidebar drawer (`☰`)
- frontend: run `cd frontend && npm run build` — zero TypeScript errors and a successful Vite build expected

Remember that the study-question pages are navigated from sidebar `✏️` entries (React Router route `/practice/:subjectId/:chapterId`). If question JSON lacks `card` fields, the card panel button will not render — this is a data state, not a frontend bug.

If you add tests, place them in a top-level `tests/` directory and name files `test_*.py`.

## Commit & Pull Request Guidelines
Git history is not available in this workspace, so use a simple, consistent convention: imperative, scoped commit subjects such as `build: refresh mock exam JSON` or `parser: improve table extraction`. Keep pull requests focused and include:

- a short summary of the content or pipeline change
- affected inputs and regenerated outputs
- screenshots only when frontend rendering changes visually

## Data & Output Handling
Do not edit `.pdf:Zone.Identifier` files. Avoid manual edits to generated logs and derived JSON unless the change is intentionally curated and documented in the PR.
