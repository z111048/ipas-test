# Repository Guidelines

## Project Structure & Module Organization
This repository is a content-generation workspace for the iPAS AI exam study materials. Source PDFs live under `data/<等級>/pdfs/`. Scripts are in `scripts/`. Generated artifacts go under `data/<等級>/` and are gitignored.

- `scripts/extract_pdfs.py`: extracts text and tables from the PDFs into `data/初級/extracted/`.
- `scripts/parse_exams_v2.py`: turns extracted content into mock-exam JSON under `data/初級/questions/`.
- `scripts/parse_guides.py`: splits guide extracted JSON into chapter-structured JSON under `data/初級/guide/`.
- `scripts/generate_questions.py`: calls the Claude API to generate new questions or add `card` fields to existing ones. Requires `ANTHROPIC_API_KEY`.
- `scripts/multi_ai_pipeline.py`: multi-AI pipeline using Gemini (出題) → Codex (審核) → Claude (完稿) CLI tools via subprocess. Includes answer-validation stage where all three AIs answer each question; questions with 2+ wrong answers are flagged to `flagged.json`. Intermediate output goes to `data/初級/pipeline/<run_id>/`; final questions are merged into `subject{N}_questions.json`.
- `scripts/build_web.py`: builds the static study site at `docs/index.html`, inlining all question and guide JSON.
- `data/初級/extracted/`, `data/初級/questions/`, `data/初級/guide/`, `data/初級/analysis/`, `data/初級/pipeline/`, and `logs/`: generated data, exam payloads, guide content, analysis output, pipeline run artifacts, and run logs.

Treat `data/初級/questions/*.json`, `data/初級/guide/*.json`, and `docs/index.html` as build outputs unless you are intentionally curating content.

## Build, Test, and Development Commands
Use Python 3 from the repository root.

- `python3 scripts/extract_pdfs.py`: extract text and tables from the PDF set into `data/初級/extracted/`.
- `python3 scripts/parse_exams_v2.py`: generate `mock_exam1.json`, `mock_exam2.json`, and `sample_exam.json` from extracted JSON tables.
- `python3 scripts/parse_guides.py`: generate `subject1_guide.json` and `subject2_guide.json` under `data/初級/guide/`.
- `python3 scripts/generate_questions.py --subject 1` (or `--subject 2`, `--enrich`): generate/enrich questions via Claude API (optional).
- `python3 scripts/multi_ai_pipeline.py --subject 1 [--chapter s1c1] [--count 3] [--dry-run]`: run multi-AI pipeline for question generation, review, finalization, and answer validation (optional; requires gemini/codex/claude CLIs).
- `python3 scripts/build_web.py`: rebuild the static web app in `docs/index.html`.

Run the first three in sequence after updating PDFs. Run `build_web.py` alone when only the UI changes.
If `scripts/build_web.py` or any inlined JSON changes, rerun `python3 scripts/build_web.py` and commit the regenerated `docs/index.html` in the same change.

## Coding Style & Naming Conventions
Follow the existing Python style: 4-space indentation, `snake_case` for functions and variables, short module docstrings, and `Path`-based filesystem access. Keep scripts self-contained and readable; prefer small helper functions over deeply nested logic. Name generated JSON files by content, for example `mock_exam1.json` or `subject2_questions.json`.

## Testing Guidelines
There is no formal automated test suite in this workspace yet. Validate changes by rerunning the pipeline and checking outputs:

- confirm expected files are regenerated in `data/初級/extracted/`, `data/初級/questions/`, `data/初級/guide/`
- `parse_exams_v2.py`: exam1 and exam2 should each produce ~50 questions; check for WARN lines
- `parse_guides.py`: each chapter should have > 1000 chars of content
- spot-check JSON structure and a few rendered questions in `docs/index.html`; verify the card panel appears after answering a question that has `card` data
- review `logs/` for extraction or parsing errors
- on narrow/mobile layouts, verify the study-question entry points are still reachable from the sidebar drawer (`☰`)

Remember that the study-question pages are navigated from sidebar `✏️` entries. If question JSON lacks `card` fields, the card panel button will not render even though the feature still exists in the HTML/JS.

If you add tests, place them in a top-level `tests/` directory and name files `test_*.py`.

## Commit & Pull Request Guidelines
Git history is not available in this workspace, so use a simple, consistent convention: imperative, scoped commit subjects such as `build: refresh mock exam JSON` or `parser: improve table extraction`. Keep pull requests focused and include:

- a short summary of the content or pipeline change
- affected inputs and regenerated outputs
- screenshots only when `docs/index.html` changes visually

## Data & Output Handling
Do not edit `.pdf:Zone.Identifier` files. Avoid manual edits to generated logs and derived JSON unless the change is intentionally curated and documented in the PR.
