# Repository Guidelines

## Project Structure & Module Organization
This repository is a content-generation workspace for the iPAS AI exam study materials. Source PDFs live under `data/<等級>/pdfs/`. Scripts are in `scripts/`. Generated artifacts go under `data/<等級>/` and are gitignored.

- `scripts/extract_pdfs.py`: extracts text and tables from the PDFs into `data/初級/extracted/`.
- `scripts/parse_exams_v2.py`: turns extracted content into mock-exam JSON under `data/初級/questions/`.
- `scripts/build_web.py`: builds the static study site at `docs/index.html`.
- `data/初級/extracted/`, `data/初級/questions/`, `data/初級/analysis/`, and `logs/`: generated data, exam payloads, analysis output, and run logs.

Treat `data/初級/questions/*.json` and `docs/index.html` as build outputs unless you are intentionally curating content.

## Build, Test, and Development Commands
Use Python 3 from the repository root.

- `python3 scripts/extract_pdfs.py`: extract text and tables from the PDF set into `data/初級/extracted/`.
- `python3 scripts/parse_exams_v2.py`: generate `mock_exam1.json`, `mock_exam2.json`, and `sample_exam.json` from extracted JSON tables.
- `python3 scripts/build_web.py`: rebuild the static web app in `docs/index.html`.

Run these in sequence after updating PDFs or question data.

## Coding Style & Naming Conventions
Follow the existing Python style: 4-space indentation, `snake_case` for functions and variables, short module docstrings, and `Path`-based filesystem access. Keep scripts self-contained and readable; prefer small helper functions over deeply nested logic. Name generated JSON files by content, for example `mock_exam1.json` or `subject2_questions.json`.

## Testing Guidelines
There is no formal automated test suite in this workspace yet. Validate changes by rerunning the pipeline and checking outputs:

- confirm expected files are regenerated in `data/初級/extracted/`, `data/初級/questions/`
- spot-check JSON structure and a few rendered questions in `docs/index.html`
- review `logs/` for extraction or parsing errors

If you add tests, place them in a top-level `tests/` directory and name files `test_*.py`.

## Commit & Pull Request Guidelines
Git history is not available in this workspace, so use a simple, consistent convention: imperative, scoped commit subjects such as `build: refresh mock exam JSON` or `parser: improve table extraction`. Keep pull requests focused and include:

- a short summary of the content or pipeline change
- affected inputs and regenerated outputs
- screenshots only when `docs/index.html` changes visually

## Data & Output Handling
Do not edit `.pdf:Zone.Identifier` files. Avoid manual edits to generated logs and derived JSON unless the change is intentionally curated and documented in the PR.
