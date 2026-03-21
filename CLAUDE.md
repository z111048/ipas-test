# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

A content-generation workspace for iPAS AI exam study materials (初級 AI 應用規劃師). Source PDFs live at the repository root. The pipeline extracts them into structured JSON, then assembles a single-file static web app deployed via GitHub Pages.

## Build Pipeline

Run from the repository root in sequence after updating PDFs or question data:

```bash
python3 scripts/extract_pdfs.py      # PDFs → data/初級/extracted/*.{txt,json}
python3 scripts/parse_exams_v2.py    # extracted JSON → data/初級/questions/*.json
python3 scripts/build_web.py         # questions JSON → docs/index.html
```

Dependencies: `pdfplumber`, `PyMuPDF` (`fitz`).

## Architecture

- **`scripts/extract_pdfs.py`**: Uses `pdfplumber` for layout-aware text/table extraction and `PyMuPDF` as fallback. Writes per-PDF `.txt` and `.json` to `data/初級/extracted/`. The `LEVEL` variable controls which data subdirectory is used.
- **`scripts/parse_exams_v2.py`**: Parses question/answer tables from the extracted JSON (handles full-width characters A-D). Outputs `mock_exam1.json`, `mock_exam2.json`, `sample_exam.json`, `subject1_questions.json`, `subject2_questions.json` to `data/初級/questions/`.
- **`scripts/build_web.py`**: Inlines all question JSON as JS constants into a self-contained single HTML file. Writes only to `docs/index.html`. The site is deployed from `docs/` on the `main` branch via GitHub Pages.

**Note:** All scripts use hardcoded absolute paths to `/home/james/projects/ipas-test`. Update `BASE`/`ROOT`/`OUT` variables if moving the repo.

## Validation (No Automated Tests)

After running the pipeline:
- Check that expected files are regenerated under `data/初級/extracted/`, `data/初級/questions/`
- Spot-check JSON structure and rendered questions in `docs/index.html`
- Review `logs/` for extraction or parsing errors

Future tests should go in `tests/test_*.py`.

## Coding Style

- 4-space indentation, `snake_case`, short module docstrings
- `Path`-based filesystem access (not `os.path` strings)
- Scripts are self-contained; small helper functions over deep nesting

## Output Files

Treat `data/初級/questions/*.json` and `docs/index.html` as build artifacts. Only edit them manually when intentionally curating content, and document the change.

## Commit Convention

Imperative, scoped subjects: `build: refresh mock exam JSON`, `parser: improve table extraction`.
