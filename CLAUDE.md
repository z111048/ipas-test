# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

A content-generation workspace for iPAS AI exam study materials (初級 AI 應用規劃師). Source PDFs live under `data/初級/pdfs/`. The pipeline extracts them into structured JSON, then assembles a single-file static web app deployed via GitHub Pages.

## Build Pipeline

Run from the repository root in sequence after updating PDFs or question data:

```bash
python3 scripts/extract_pdfs.py      # PDFs → data/初級/extracted/*.{txt,json}
python3 scripts/parse_exams_v2.py    # extracted JSON → data/初級/questions/*.json
python3 scripts/parse_guides.py      # guide JSON → data/初級/guide/subject{1,2}_guide.json
# Optional: generate/enrich questions via Claude API
python3 scripts/generate_questions.py --subject 1   # generate new questions for subject 1
python3 scripts/generate_questions.py --subject 2   # generate new questions for subject 2
python3 scripts/generate_questions.py --enrich      # add card fields to existing questions
python3 scripts/build_web.py         # all JSON → docs/index.html
```

Dependencies: `pdfplumber`, `PyMuPDF` (`fitz`), `anthropic` (for `generate_questions.py` only).
`generate_questions.py` requires `ANTHROPIC_API_KEY` environment variable.

## Architecture

- **`scripts/extract_pdfs.py`**: Uses `pdfplumber` for layout-aware text/table extraction and `PyMuPDF` as fallback. Writes per-PDF `.txt` and `.json` to `data/初級/extracted/`. The `LEVEL` variable controls which data subdirectory is used.
- **`scripts/parse_exams_v2.py`**: Parses question/answer tables from the extracted JSON (handles full-width characters A-D and parentheses). Outputs `mock_exam1.json`, `mock_exam2.json`, `sample_exam.json` to `data/初級/questions/`. Note: `subject1/2_questions.json` are manually curated and not overwritten by this script.
- **`scripts/parse_guides.py`**: Splits guide1/guide2 extracted JSON into chapter-structured data using in-document page number anchors. Writes `data/初級/guide/subject{1,2}_guide.json`. Chapter content is used as LLM context for question generation.
- **`scripts/generate_questions.py`**: Calls Claude API to generate new questions per chapter (`--subject N`) or add `card` fields to existing questions (`--enrich`). Use `--dry-run` to preview prompts without API calls. Questions follow the extended schema with `card`, `difficulty`, `type`, and `tags` fields.
- **`scripts/build_web.py`**: Inlines all question and guide JSON as JS constants into a self-contained single HTML file. Writes only to `docs/index.html`. The site is deployed from `docs/` on the `main` branch via GitHub Pages.
- The study-question pages are reached from sidebar `✏️` items. On mobile widths the sidebar is hidden behind the `☰` drawer button, so navigation regressions should be checked there too.

**Note:** All scripts use hardcoded absolute paths to `/home/james/projects/ipas-test`. Update `BASE`/`ROOT`/`OUT` variables if moving the repo.

## Output Files (Extended)

Treat `data/初級/questions/*.json`, `data/初級/guide/*.json`, and `docs/index.html` as build artifacts. Only edit them manually when intentionally curating content, and document the change.
If `scripts/build_web.py` or any inlined data changes, rerun `python3 scripts/build_web.py` and commit the regenerated `docs/index.html` together with the source change.

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
- Check that expected files are regenerated under `data/初級/extracted/`, `data/初級/questions/`, `data/初級/guide/`
- `parse_guides.py`: each chapter should have > 1000 chars of content
- `parse_exams_v2.py`: exam1 and exam2 should each produce ~50 questions (check for WARN lines)
- Spot-check JSON structure and rendered questions in `docs/index.html`; verify card panel appears after answering a question with `card` data
- On mobile-width layouts, confirm the `☰` drawer still exposes the `✏️` study-question entries
- Review `logs/` for extraction or parsing errors

If the card panel is missing, verify the underlying question JSON actually contains `card` fields before treating it as a frontend regression.

Future tests should go in `tests/test_*.py`.

## Coding Style

- 4-space indentation, `snake_case`, short module docstrings
- `Path`-based filesystem access (not `os.path` strings)
- Scripts are self-contained; small helper functions over deep nesting

## Commit Convention

Imperative, scoped subjects: `build: refresh mock exam JSON`, `parser: improve table extraction`.
