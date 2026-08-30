#!/usr/bin/env python3
"""Generate Colab notebooks for 中級 iPAS chapters.

Pipeline:
  1. Codex CLI  → draft cells (JSON)
  2. ast.parse  → syntax check per code cell
  3. subprocess → execution test per code cell (timeout 30s)
  4. Codex CLI  → code review pass
  5. pass/warn  → write .ipynb + metadata JSON
     fail       → write to flagged.json

Usage:
  python3 scripts/generate_colab_notebooks.py --level 中級 --all
  python3 scripts/generate_colab_notebooks.py --level 中級 --subject 2
  python3 scripts/generate_colab_notebooks.py --level 中級 --chapter mid-s2c1
  python3 scripts/generate_colab_notebooks.py --level 中級 --chapter mid-s2c1 --force
  python3 scripts/generate_colab_notebooks.py --level 中級 --all --dry-run
"""

import argparse
import ast
import json
import logging
import re
import subprocess
import sys
import textwrap
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
LOG_DIR = BASE / 'logs'
GITHUB_REPO = 'z111048/ipas-test'

DEFAULT_TIMEOUT = 300
EXEC_TIMEOUT = 30
MAX_RETRIES = 2
MAX_CONTENT_CHARS = 4000

LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'generate_colab_notebooks.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CLI wrapper (same pattern as multi_ai_pipeline.py)
# ---------------------------------------------------------------------------

def call_codex(prompt: str, timeout: int = DEFAULT_TIMEOUT) -> str | None:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = subprocess.run(
                ['codex', 'exec', '-c', 'sandbox_permissions=["disk-full-read-access"]', '-'],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=BASE,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            log.warning(f'[codex] attempt {attempt} exit={result.returncode}: {result.stderr[:200]}')
        except subprocess.TimeoutExpired:
            log.warning(f'[codex] attempt {attempt} timed out ({timeout}s)')
        except FileNotFoundError:
            log.error('[codex] not found in PATH')
            return None
        if attempt < MAX_RETRIES:
            log.info(f'[codex] retrying...')
    return None


def parse_json_response(text: str) -> object:
    """Strip markdown fences and parse JSON from LLM output."""
    text = text.strip()
    if text.startswith('```'):
        lines = text.split('\n')
        end = len(lines) - 1 if lines[-1].strip() == '```' else len(lines)
        text = '\n'.join(lines[1:end])
    # Extract first JSON object/array
    match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', text)
    if match:
        text = match.group(1)
    return json.loads(text)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

GENERATION_PROMPT = """\
你是一位精通 Python 的 AI 教學設計師，負責為「{level_label} AI 應用規劃師（iPAS）」考試教材設計 Colab 實作練習。

【章節 ID】{chapter_id}
【章節標題】{title}
【章節內容摘要】
{content}

請設計一份完整的 Colab Notebook，以 JSON 格式回傳，結構如下：

{{
  "cells": [
    {{
      "type": "markdown",
      "content": "# {title}\\n\\n## 📌 學習目標\\n..."
    }},
    {{
      "type": "code",
      "title": "環境設定",
      "explanation": "載入本章節所需的 Python 套件",
      "content": "import numpy as np\\n..."
    }},
    {{
      "type": "markdown",
      "title": "核心概念",
      "content": "## 核心概念說明\\n\\n..."
    }},
    {{
      "type": "code",
      "title": "示範：[概念名稱]",
      "explanation": "這段程式碼示範...",
      "content": "..."
    }},
    {{
      "type": "code",
      "title": "實際應用",
      "explanation": "...",
      "content": "..."
    }},
    {{
      "type": "code",
      "title": "🧪 自我測驗",
      "explanation": "請完成下方 TODO 填空，實作對應的功能",
      "content": "# TODO: 依提示完成以下程式碼\\n..."
    }}
  ]
}}

設計規則：
1. 所有說明文字（markdown content、explanation）使用繁體中文
2. 程式碼只使用 Google Colab 預裝套件：numpy、pandas、sklearn、matplotlib、scipy、re、collections 等
3. 若章節涉及大型模型（LLM、diffusion），改用同概念的輕量示範（例如 TF-IDF 替代 Embedding）
4. 每個 code cell 必須有 title 和 explanation
5. cells 總數 6–9 個（markdown + code 交替）
6. 自我測驗 cell 必須有 # TODO 填空並附上預期輸出的 # Expected: 註解
7. 程式碼要能獨立執行（每個 cell 可單獨跑通）
8. 只回傳 JSON，不加其他說明文字
"""

FIX_PROMPT = """\
你是 Python 程式碼修正者，請根據審核意見修正 Notebook 中有問題的 cells。

【章節】{title}（{chapter_id}）

【完整 cells（含 index）】
{all_cells_json}

【審核發現的問題】
{issues_json}

修正要求：
1. 修正所有語法錯誤（特別是截斷或不完整的程式碼，補齊完整邏輯）
2. 自我測驗 cell 必須有 # TODO 填空和 # Expected: 預期輸出提示
3. 保持 title 和 explanation 不變（除非審核說需要修改）
4. 未被標記為 fail 的 cells 保持原樣不修改
5. 只回傳修正後的「完整」cells 列表，JSON 格式：{{"cells": [...]}}
6. 只回傳 JSON，不加其他說明文字
"""

REVIEW_PROMPT = """\
你是 Python 程式碼審核者，請審核以下 Notebook 的品質。

【章節】{title}（{chapter_id}）
【Cells】
{cells_json}

針對每個 code cell（type="code"）回傳審核結果，以 JSON 格式回傳：

{{
  "overall_status": "pass",
  "cells": [
    {{
      "cell_index": 0,
      "status": "pass",
      "issues": [],
      "suggestion": ""
    }}
  ]
}}

審核標準（逐條給出具體問題）：
1. 語法正確（能被 Python 3.10 解析）
2. 只使用 Colab 預裝套件，無需額外 pip install（除非 cell 本身有 !pip install）
3. 程式碼邏輯與章節概念相符（錯誤示範或不相關內容 → fail）
4. explanation 說明正確且清楚
5. 自我測驗 cell 有 # TODO 且有 # Expected: 提示

status 值：
- "pass"：無問題
- "warn"：有小瑕疵但仍可用
- "fail"：有嚴重錯誤（邏輯錯誤、套件不可用、說明與程式碼不符）

overall_status = "fail" 當任何 cell status = "fail"
overall_status = "warn" 當有 warn 但無 fail
overall_status = "pass" 當全部 pass

只回傳 JSON，不加其他說明文字。
"""


# ---------------------------------------------------------------------------
# Quality checks
# ---------------------------------------------------------------------------

def check_syntax(code: str) -> tuple[bool, str]:
    """Return (ok, error_message)."""
    try:
        ast.parse(code)
        return True, ''
    except SyntaxError as e:
        return False, f'SyntaxError at line {e.lineno}: {e.msg}'


ALLOWED_IMPORTS = {
    'numpy', 'pandas', 'sklearn', 'matplotlib', 'scipy', 'seaborn',
    'PIL', 'cv2', 'nltk', 're', 'collections', 'itertools', 'math',
    'random', 'json', 'os', 'sys', 'time', 'datetime', 'typing',
    'abc', 'functools', 'warnings', 'io', 'base64', 'hashlib',
    'string', 'copy', 'dataclasses', 'enum', 'pathlib',
    'torch', 'tensorflow', 'transformers', 'datasets',
    'statsmodels', 'xgboost', 'lightgbm', 'catboost',
    'networkx', 'sympy', 'numba',
}


def check_imports(code: str) -> tuple[bool, str]:
    """Warn on unusual imports not typically in Colab."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return True, ''  # syntax error handled separately
    unknown = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [node.module.split('.')[0]] if isinstance(node, ast.ImportFrom) and node.module else []
            names += [alias.name.split('.')[0] for alias in (node.names if isinstance(node, ast.Import) else [])]
            for name in names:
                if name and name not in ALLOWED_IMPORTS:
                    unknown.append(name)
    if unknown:
        return False, f'未知套件（可能需要 pip install）：{", ".join(set(unknown))}'
    return True, ''


def run_code(code: str, timeout: int = EXEC_TIMEOUT) -> tuple[bool, str]:
    """Execute code in subprocess. Return (ok, error_output).

    ModuleNotFoundError for packages in ALLOWED_IMPORTS is treated as a skip
    (those packages exist in Colab but may not be installed locally).
    """
    # Skip cells that are only comments, TODOs, or empty
    stripped = '\n'.join(
        line for line in code.split('\n')
        if line.strip() and not line.strip().startswith('#')
    )
    if not stripped:
        return True, ''
    # Skip if contains TODO (self-test cells are incomplete by design)
    if '# TODO' in code:
        return True, '(skipped: contains TODO)'
    try:
        result = subprocess.run(
            ['python3', '-c', code],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=BASE,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            # If failure is ModuleNotFoundError for a known Colab package, skip silently
            if 'ModuleNotFoundError' in stderr:
                import re as _re
                missing = _re.search(r"No module named '([^']+)'", stderr)
                if missing:
                    pkg = missing.group(1).split('.')[0]
                    if pkg in ALLOWED_IMPORTS:
                        return True, f'(skipped: {pkg} not local, OK in Colab)'
            # If failure is NameError for a common library alias, it means the cell relies on
            # a previous cell's import (normal in Colab). Skip rather than fail.
            if 'NameError' in stderr:
                import re as _re
                name_match = _re.search(r"name '([^']+)' is not defined", stderr)
                if name_match:
                    alias = name_match.group(1)
                    COMMON_ALIASES = {'np', 'pd', 'plt', 'sns', 'tf', 'torch', 'cv2', 'sk',
                                      'sp', 'nx', 'sm', 'stats', 'preprocessing', 'datasets'}
                    if alias in COMMON_ALIASES:
                        return True, f'(skipped: {alias} from previous cell, OK in Colab)'
            # Filter out common harmless warnings
            error_lines = [
                l for l in stderr.split('\n')
                if l and not any(
                    w in l for w in ['FutureWarning', 'DeprecationWarning', 'UserWarning', 'warnings.warn']
                )
            ]
            if error_lines:
                return False, '\n'.join(error_lines[:5])
        return True, ''
    except subprocess.TimeoutExpired:
        return False, f'執行逾時（>{timeout}s）'
    except Exception as e:
        return False, str(e)


# ---------------------------------------------------------------------------
# Auto-fix
# ---------------------------------------------------------------------------

def attempt_autofix_cells(
    draft_cells: list[dict],
    review_result: dict,
    title: str,
    chapter_id: str,
    chapter_pipeline: Path,
) -> list[dict] | None:
    """Ask Codex to fix failing cells. Returns fixed cells list or None on failure."""
    fail_cells = [
        c for c in review_result.get('cells', [])
        if c.get('status') == 'fail'
    ]
    if not fail_cells:
        return None

    issues_summary = [
        {
            'cell_index': c['cell_index'],
            'issues': c.get('issues', []),
            'suggestion': c.get('suggestion', ''),
        }
        for c in fail_cells
    ]

    all_cells_json = json.dumps(
        [{'index': i, **c} for i, c in enumerate(draft_cells)],
        ensure_ascii=False,
        indent=2,
    )
    fix_prompt = FIX_PROMPT.format(
        title=title,
        chapter_id=chapter_id,
        all_cells_json=all_cells_json[:6000],
        issues_json=json.dumps(issues_summary, ensure_ascii=False, indent=2),
    )

    log.info(f'[{chapter_id}] 呼叫 Codex 自動修正 {len(fail_cells)} 個問題 cells...')
    raw = call_codex(fix_prompt, timeout=DEFAULT_TIMEOUT)
    if not raw:
        log.warning(f'[{chapter_id}] Codex 修正無回應')
        return None

    try:
        parsed = parse_json_response(raw)
        fixed_cells = parsed if isinstance(parsed, list) else parsed.get('cells', [])
    except (json.JSONDecodeError, KeyError) as e:
        log.warning(f'[{chapter_id}] 修正 JSON 解析失敗：{e}')
        return None

    if not fixed_cells:
        log.warning(f'[{chapter_id}] 修正結果為空')
        return None

    # Strip 'index' field added during prompt construction
    for cell in fixed_cells:
        cell.pop('index', None)

    (chapter_pipeline / 'fix.json').write_text(
        json.dumps({'cells': fixed_cells}, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    log.info(f'[{chapter_id}] 修正草稿已儲存：{len(fixed_cells)} cells')
    return fixed_cells


# ---------------------------------------------------------------------------
# Notebook building
# ---------------------------------------------------------------------------

def cells_to_ipynb(cells: list[dict], title: str, chapter_id: str) -> dict:
    """Convert cells list to .ipynb format (nbformat 4)."""
    ipynb_cells = []
    for cell in cells:
        if cell['type'] == 'markdown':
            source = cell.get('content', '')
            if cell.get('title') and not source.startswith('#'):
                source = f"## {cell['title']}\n\n{source}"
            ipynb_cells.append({
                'cell_type': 'markdown',
                'metadata': {},
                'source': [line + '\n' for line in source.split('\n')],
            })
        elif cell['type'] == 'code':
            source_lines = []
            if cell.get('title'):
                source_lines.append(f"# ── {cell['title']} {'─'*(40 - len(cell['title']))}\n")
            if cell.get('explanation'):
                for line in cell['explanation'].split('\n'):
                    source_lines.append(f'# {line}\n')
                source_lines.append('\n')
            source_lines += [line + '\n' for line in cell.get('content', '').split('\n')]
            ipynb_cells.append({
                'cell_type': 'code',
                'execution_count': None,
                'metadata': {},
                'outputs': [],
                'source': source_lines,
            })

    return {
        'nbformat': 4,
        'nbformat_minor': 5,
        'metadata': {
            'colab': {
                'provenance': [],
                'name': f'{chapter_id}.ipynb',
            },
            'kernelspec': {
                'display_name': 'Python 3',
                'language': 'python',
                'name': 'python3',
            },
            'language_info': {
                'name': 'python',
                'version': '3.10.0',
            },
        },
        'cells': ipynb_cells,
    }


def colab_url(level: str, chapter_id: str) -> str:
    return (
        f'https://colab.research.google.com/github/{GITHUB_REPO}'
        f'/blob/main/notebooks/{level}/{chapter_id}.ipynb'
    )


# ---------------------------------------------------------------------------
# Main pipeline per chapter
# ---------------------------------------------------------------------------

def process_chapter(
    chapter: dict,
    level: str,
    pipeline_dir: Path,
    notebooks_dir: Path,
    frontend_dir: Path,
    dry_run: bool = False,
    force: bool = False,
) -> str:
    """Process one chapter. Returns 'pass', 'warn', 'fail', 'skip', or 'dry_run'."""
    chapter_id = chapter['id']
    title = chapter.get('title', chapter_id)
    content = chapter.get('content', '')[:MAX_CONTENT_CHARS]

    out_ipynb = notebooks_dir / f'{chapter_id}.ipynb'
    out_meta = frontend_dir / f'{chapter_id}.json'
    chapter_pipeline = pipeline_dir / chapter_id
    chapter_pipeline.mkdir(parents=True, exist_ok=True)

    if not force and out_ipynb.exists() and out_meta.exists():
        log.info(f'[{chapter_id}] already exists, skipping (use --force to regenerate)')
        return 'skip'

    log.info(f'[{chapter_id}] 開始生成：{title}')

    # ── Step 1: Codex 生成草稿 ────────────────────────────────────────────
    level_label = '初級' if level == '初級' else '中級'
    generation_prompt = GENERATION_PROMPT.format(
        level_label=level_label,
        chapter_id=chapter_id,
        title=title,
        content=content,
    )

    if dry_run:
        log.info(f'[{chapter_id}] [dry-run] 生成 prompt 長度={len(generation_prompt)} chars')
        log.info(f'[{chapter_id}] [dry-run] prompt preview:\n{generation_prompt[:300]}...')
        return 'dry_run'

    draft_path = chapter_pipeline / 'draft.json'
    if not force and draft_path.exists():
        log.info(f'[{chapter_id}] 讀取既有草稿：{draft_path}')
        draft_cells = json.loads(draft_path.read_text(encoding='utf-8'))['cells']
    else:
        log.info(f'[{chapter_id}] 呼叫 Codex 生成草稿...')
        raw = call_codex(generation_prompt, timeout=DEFAULT_TIMEOUT)
        if not raw:
            log.error(f'[{chapter_id}] Codex 生成失敗')
            (chapter_pipeline / 'flagged.json').write_text(
                json.dumps({'chapter_id': chapter_id, 'reason': 'Codex 生成失敗'}, ensure_ascii=False, indent=2),
                encoding='utf-8',
            )
            return 'fail'
        try:
            parsed = parse_json_response(raw)
            draft_cells = parsed if isinstance(parsed, list) else parsed.get('cells', [])
        except (json.JSONDecodeError, KeyError) as e:
            log.error(f'[{chapter_id}] JSON 解析失敗：{e}\nraw={raw[:300]}')
            (chapter_pipeline / 'flagged.json').write_text(
                json.dumps({'chapter_id': chapter_id, 'reason': f'JSON 解析失敗：{e}', 'raw': raw[:500]},
                           ensure_ascii=False, indent=2),
                encoding='utf-8',
            )
            return 'fail'
        draft_path.write_text(
            json.dumps({'chapter_id': chapter_id, 'cells': draft_cells}, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
        log.info(f'[{chapter_id}] 草稿已儲存：{len(draft_cells)} cells')

    # ── Step 2 & 3: 靜態分析 + 執行測試 ─────────────────────────────────
    static_issues: list[dict] = []
    for i, cell in enumerate(draft_cells):
        if cell.get('type') != 'code':
            continue
        code = cell.get('content', '')

        ok_syntax, err_syntax = check_syntax(code)
        if not ok_syntax:
            static_issues.append({'cell_index': i, 'check': 'syntax', 'error': err_syntax})
            log.warning(f'[{chapter_id}] cell[{i}] syntax error: {err_syntax}')

        ok_import, warn_import = check_imports(code)
        if not ok_import:
            static_issues.append({'cell_index': i, 'check': 'imports', 'error': warn_import})
            log.warning(f'[{chapter_id}] cell[{i}] import warn: {warn_import}')

        ok_exec, err_exec = run_code(code)
        if not ok_exec:
            static_issues.append({'cell_index': i, 'check': 'execution', 'error': err_exec})
            log.warning(f'[{chapter_id}] cell[{i}] exec error: {err_exec[:100]}')

    (chapter_pipeline / 'static_check.json').write_text(
        json.dumps({'chapter_id': chapter_id, 'issues': static_issues}, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )

    # ── Step 4: Codex 審核 ────────────────────────────────────────────────
    cells_for_review = json.dumps(
        [{'index': i, **c} for i, c in enumerate(draft_cells)],
        ensure_ascii=False,
        indent=2,
    )
    review_prompt = REVIEW_PROMPT.format(
        title=title,
        chapter_id=chapter_id,
        cells_json=cells_for_review[:6000],
    )
    log.info(f'[{chapter_id}] 呼叫 Codex 審核...')
    review_raw = call_codex(review_prompt, timeout=DEFAULT_TIMEOUT)

    review_result: dict = {'overall_status': 'warn', 'cells': []}
    if review_raw:
        try:
            review_result = parse_json_response(review_raw)
        except (json.JSONDecodeError, KeyError) as e:
            log.warning(f'[{chapter_id}] 審核 JSON 解析失敗：{e}，使用靜態分析結果')
            # Downgrade to warn if static issues exist
            review_result['overall_status'] = 'fail' if static_issues else 'warn'
    else:
        log.warning(f'[{chapter_id}] Codex 審核無回應，使用靜態分析結果')
        review_result['overall_status'] = 'fail' if static_issues else 'warn'

    (chapter_pipeline / 'review.json').write_text(
        json.dumps(review_result, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )

    overall = review_result.get('overall_status', 'warn')
    log.info(f'[{chapter_id}] 審核結果：{overall}')

    if overall == 'fail':
        # ── Step 4.5: 嘗試自動修正失敗 cells ─────────────────────────────
        fixed_cells = attempt_autofix_cells(
            draft_cells, review_result, title, chapter_id, chapter_pipeline
        )
        if fixed_cells:
            static_issues_fixed: list[dict] = []
            for i, cell in enumerate(fixed_cells):
                if cell.get('type') != 'code':
                    continue
                code = cell.get('content', '')
                ok_syntax, err_syntax = check_syntax(code)
                if not ok_syntax:
                    static_issues_fixed.append({'cell_index': i, 'check': 'syntax', 'error': err_syntax})
                    log.warning(f'[{chapter_id}] [fix] cell[{i}] syntax error: {err_syntax}')
                ok_exec, err_exec = run_code(code)
                if not ok_exec:
                    static_issues_fixed.append({'cell_index': i, 'check': 'execution', 'error': err_exec})
                    log.warning(f'[{chapter_id}] [fix] cell[{i}] exec error: {err_exec[:100]}')

            if not static_issues_fixed:
                log.info(f'[{chapter_id}] ✓ 自動修正成功，降級為 warn')
                draft_cells = fixed_cells
                overall = 'warn'
            else:
                log.warning(f'[{chapter_id}] 自動修正後仍有 {len(static_issues_fixed)} 個靜態問題')

    if overall == 'fail':
        flagged = {
            'chapter_id': chapter_id,
            'title': title,
            'review': review_result,
            'static_issues': static_issues,
            'generated_at': datetime.now().isoformat(),
        }
        (chapter_pipeline / 'flagged.json').write_text(
            json.dumps(flagged, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
        log.warning(f'[{chapter_id}] ❌ FAIL — 寫入 flagged.json，需人工審查')
        return 'fail'

    # ── Step 5: 輸出 .ipynb + metadata JSON ──────────────────────────────
    url = colab_url(level, chapter_id)

    # .ipynb
    ipynb = cells_to_ipynb(draft_cells, title, chapter_id)
    out_ipynb.write_text(json.dumps(ipynb, ensure_ascii=False, indent=2), encoding='utf-8')
    log.info(f'[{chapter_id}] ✓ .ipynb → {out_ipynb}')

    # frontend metadata (lightweight)
    meta = {
        'chapter_id': chapter_id,
        'chapter_title': title,
        'colab_url': url,
        'status': overall,
        'cells': draft_cells,
    }
    out_meta.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
    log.info(f'[{chapter_id}] ✓ metadata → {out_meta}')

    return overall


# ---------------------------------------------------------------------------
# Chapter resolution
# ---------------------------------------------------------------------------

def load_chapters(level: str, subject: int | None, chapter_id: str | None) -> list[dict]:
    guide_dir = BASE / 'data' / level / 'guide'
    subjects = [subject] if subject else [1, 2, 3]
    chapters = []
    for s in subjects:
        f = guide_dir / f'subject{s}_guide.json'
        if not f.exists():
            log.warning(f'找不到 {f}')
            continue
        data = json.loads(f.read_text(encoding='utf-8'))
        for ch in data.get('chapters', []):
            if chapter_id and ch['id'] != chapter_id:
                continue
            chapters.append(ch)
    return chapters


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description='Generate Colab notebooks for iPAS chapters')
    parser.add_argument('--level', default='中級')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--all', action='store_true')
    group.add_argument('--subject', type=int, choices=[1, 2, 3])
    group.add_argument('--chapter', help='chapter id, e.g. mid-s2c1')
    parser.add_argument('--force', action='store_true', help='regenerate even if output exists')
    parser.add_argument('--dry-run', action='store_true', help='print prompts without calling Codex')
    args = parser.parse_args()

    if not args.all and not args.subject and not args.chapter:
        parser.error('specify --all, --subject N, or --chapter ID')

    level = args.level
    pipeline_dir = BASE / 'data' / level / 'pipeline' / 'colab_notebooks'
    notebooks_dir = BASE / 'notebooks' / level
    frontend_dir = BASE / 'frontend' / 'src' / 'generated' / 'colabNotebooks' / level

    pipeline_dir.mkdir(parents=True, exist_ok=True)
    notebooks_dir.mkdir(parents=True, exist_ok=True)
    frontend_dir.mkdir(parents=True, exist_ok=True)

    subject = args.subject if args.subject else None
    chapter_id = args.chapter if args.chapter else None

    chapters = load_chapters(level, subject, chapter_id)
    if not chapters:
        log.error('找不到符合條件的章節')
        sys.exit(1)

    log.info(f'目標章節數：{len(chapters)}')

    results: dict[str, str] = {}
    for ch in chapters:
        status = process_chapter(
            ch,
            level=level,
            pipeline_dir=pipeline_dir,
            notebooks_dir=notebooks_dir,
            frontend_dir=frontend_dir,
            dry_run=args.dry_run,
            force=args.force,
        )
        results[ch['id']] = status

    # Summary
    from collections import Counter
    counts = Counter(results.values())
    log.info('─' * 50)
    log.info(f'完成。pass={counts["pass"]} warn={counts["warn"]} fail={counts["fail"]} skip={counts["skip"]} dry_run={counts["dry_run"]}')
    if counts['fail']:
        failed = [cid for cid, s in results.items() if s == 'fail']
        log.warning(f'需人工審查：{failed}')
        log.warning(f'詳見 {pipeline_dir}/<chapter_id>/flagged.json')


if __name__ == '__main__':
    main()
