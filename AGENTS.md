# Repository Guidelines

## Project Structure & Module Organization

This repository is a content-generation workspace for the iPAS AI exam study materials. Source PDFs live under `data/<等級>/pdfs/`. Scripts are in `scripts/`. Generated artifacts go under `data/<等級>/` and are gitignored.

**Core goal**: Synthesize high-quality mock exam questions from parsed study guide Markdown + official exam samples, per chapter. Parse quality directly determines question quality.

**Single source of truth**: `data/{level}/toc_manifest.json` defines all subject/chapter metadata. All scripts and the frontend read from it. Never duplicate chapter definitions elsewhere.

All scripts support `--level` (default `初級`); paths resolve to `data/{level}/`.

- `scripts/build_manifest.py`: **SSOT generator** — the only script with hardcoded chapter definitions (`GUIDES_BY_LEVEL` dict, keyed by level). Computes PDF page ranges via PyMuPDF and writes `data/{level}/toc_manifest.json`. Run whenever chapters or PDFs change. Supports `--level`, `--dry-run`.
- `scripts/pdf_vision_extract.py`: **Guide extraction** — renders each PDF page to PNG and calls Gemini Vision API (`gemini-2.5-flash`). Results cached at `data/{level}/pages_cache/{key}/page_NNN.json`; auto-generates `page_index.json` (TOC) on completion. Requires `GEMINI_API_KEY`. Supports `--level`, `--subject`, `--all`, `--dry-run`, `--force`, `--page`.
- `scripts/parse_guides.py`: **Guide assembly** — assembles chapter JSON from vision cache (preferred) or falls back to regex extraction. Reads chapter definitions from `toc_manifest.json`. Supports `--level`, `--subject`.
- `scripts/audit_chapters.py`: **LLM chapter audit** — reads `subject{N}_guide.json` and calls Claude Haiku to verify each chapter covers its expected subtopics. Outputs `subject{N}_audit_report.json`. Run after guide extraction. Requires `ANTHROPIC_API_KEY`. Supports `--level`, `--subject`, `--all`, `--chapter`, `--dry-run`.
- `scripts/extract_pdfs.py`: extracts text and tables from PDFs into `data/{level}/extracted/`. Guide PDFs from `toc_manifest.json`; exam PDFs from `EXAM_PDFS_BY_LEVEL`. Supports `--level`.
- `scripts/parse_exams_v2.py`: turns extracted content into mock-exam JSON under `data/{level}/questions/`. Supports `--level`.
- `scripts/generate_questions.py`: calls the Claude API to generate new questions or add `card` fields to existing ones. Requires `ANTHROPIC_API_KEY`. Supports `--level`, `--subject`, `--enrich`.
- `scripts/multi_ai_pipeline.py`: multi-AI pipeline using Gemini (出題) → Codex (審核) → Claude (完稿) CLI tools via subprocess. Includes answer-validation stage where all three AIs answer each question; questions with 2+ wrong answers are flagged to `flagged.json`. Intermediate output goes to `data/{level}/pipeline/<run_id>/`; final questions merged into `subject{N}_questions.json`. Supports `--level`.
- `scripts/build_web.py`: thin wrapper that runs `npm run build` inside `frontend/`, outputting the React app to `docs/`.
- `frontend/`: Vite project (React 19 + TypeScript + Tailwind CSS v4 + React Router v6 + Zustand). Source in `frontend/src/`; build config in `frontend/vite.config.ts`. All JSON data imported statically via `@data` alias (points to `data/初級/`) at build time. `SubjectOverviewPage.tsx` reads chapter metadata from `toc_manifest.json`.
- `data/{level}/toc_manifest.json`: committed static file — chapter definitions SSOT. Regenerate with `build_manifest.py --level {level}` when chapters change.
- `data/{level}/extracted/`, `data/{level}/questions/`, `data/{level}/guide/`, `data/{level}/analysis/`, `data/{level}/pipeline/`, and `logs/`: generated data, exam payloads, guide content, analysis output, pipeline run artifacts, and run logs.

Treat `data/{level}/questions/*.json`, `data/{level}/guide/*.json`, and `docs/` as build outputs unless you are intentionally curating content.

## Build, Test, and Development Commands

This project uses `uv` for dependency management. Run `uv sync` after cloning to set up the virtual environment. Use `uv run` to execute scripts within the environment.

**Step 0 (run when chapters/PDFs change):**
- `uv run python3 scripts/build_manifest.py`: regenerate `data/初級/toc_manifest.json` from embedded GUIDES definition + PDF page calculations.

**Guide pipeline (choose Route A or B):**
- Route A: `uv run python3 scripts/guide_to_md.py --all` — deterministic span extraction, no LLM.
- Route B: `uv run python3 scripts/pdf_vision_extract.py --all` then `uv run python3 scripts/parse_guides.py` — LLM vision extraction + assembly.
- Audit (required after either route): `uv run python3 scripts/audit_chapters.py --all` — LLM chapter content audit. Use `--dry-run` to preview prompts.

**Exam pipeline:**
- `uv run python3 scripts/extract_pdfs.py`: extract text and tables from the PDF set into `data/初級/extracted/`.
- `uv run python3 scripts/parse_exams_v2.py`: generate `mock_exam1.json`, `mock_exam2.json`, and `sample_exam.json` from extracted JSON tables.
- `uv run python3 scripts/generate_questions.py --subject 1` (or `--subject 2`, `--enrich`): generate/enrich questions via Claude API (optional).
- `python3 scripts/multi_ai_pipeline.py --subject 1 [--chapter s1c1] [--count 3] [--dry-run]`: run multi-AI pipeline for question generation, review, finalization, and answer validation (optional; requires gemini/codex/claude CLIs; uses subprocess only, no venv needed).

**Frontend:**
- `uv run python3 scripts/build_web.py`: rebuild the frontend via Vite (`npm run build` in `frontend/`), outputting to `docs/`.
- `cd frontend && npm run dev -- --host`: start the Vite dev server (use `--host` to expose to Windows from WSL).

If `frontend/src/` or any data JSON changes, rerun `uv run python3 scripts/build_web.py` and commit the regenerated `docs/` in the same change.

## Coding Style & Naming Conventions
Follow the existing Python style: 4-space indentation, `snake_case` for functions and variables, short module docstrings, and `Path`-based filesystem access. Keep scripts self-contained and readable; prefer small helper functions over deeply nested logic. Name generated JSON files by content, for example `mock_exam1.json` or `subject2_questions.json`.

## Testing Guidelines

There is no formal automated test suite in this workspace yet. Validate changes by rerunning the pipeline and checking outputs:

- confirm `data/初級/toc_manifest.json` exists and has `page_range` filled for all 7 chapters (not null)
- `guide_to_md.py`: check `subject{N}_validation_report.json` — `overall_passed` should be `true`; each chapter > 1000 chars
- `audit_chapters.py`: check `subject{N}_audit_report.json` — `overall_status` should be `PASS`; any `WARN`/`FAIL` needs review before generating questions
- confirm expected files are regenerated in `data/初級/extracted/`, `data/初級/questions/`, `data/初級/guide/`
- `parse_exams_v2.py`: exam1 and exam2 should each produce ~50 questions; check for WARN lines
- `parse_guides.py`: each chapter should have > 1000 chars of content
- spot-check JSON structure and a few rendered questions at `http://localhost:5173/` or in `docs/`; verify the card panel appears after answering a question that has `card` data; verify `SubjectOverviewPage` shows subtopics and page ranges from `toc_manifest.json`
- review `logs/` for extraction or parsing errors
- on narrow/mobile layouts, verify the study-question entry points are still reachable from the sidebar drawer (`☰`)
- frontend: run `cd frontend && npm run build` — zero TypeScript errors and a successful Vite build expected

Remember that the study-question pages are navigated from sidebar `✏️` entries (React Router route `/practice/:subjectId/:chapterId`). If question JSON lacks `card` fields, the card panel button will not render — this is a data state, not a frontend bug.

If you add tests, place them in a top-level `tests/` directory and name files `test_*.py`.

## Commit & Pull Request Guidelines
Git history is not available in this workspace, so use a simple, consistent convention: imperative, scoped commit subjects such as `build: refresh mock exam JSON` or `parser: improve table extraction`. Keep pull requests focused and include:

- a short summary of the content or pipeline change
- affected inputs and regenerated outputs
- screenshots only when `docs/index.html` changes visually

## Data & Output Handling
Do not edit `.pdf:Zone.Identifier` files. Avoid manual edits to generated logs and derived JSON unless the change is intentionally curated and documented in the PR.
