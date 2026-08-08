#!/usr/bin/env python3
"""Re-check the notebooks that are actually committed, not the drafts.

`data/{level}/pipeline/colab_notebooks/{chapter}/flagged.json` records the review of
the *draft* produced by `generate_colab_notebooks.py`. 27 chapters are marked `fail`
there, yet every committed notebook parses cleanly — the drafts were fixed or
regenerated afterwards and the review was never refreshed. A stale FAIL is worse than
no review: the next person either panics or learns to ignore it.

Two passes over the committed `.ipynb`:

  執行  cumulative execution — cells are concatenated in order and run as one script,
        so cross-cell state is real. The pipeline's own checker runs each cell in
        isolation and then swallows every NameError as "depends on a previous cell",
        which is exactly how a genuinely undefined variable slips through.
  語意  a gateway model reads each cell's explanation next to its code and reports
        only mismatches (e.g. "示範等寬分箱" over bins whose widths differ).

Usage:
  python3 scripts/review_committed_notebooks.py --exec-only
  python3 scripts/review_committed_notebooks.py --python /path/to/venv/bin/python
  python3 scripts/review_committed_notebooks.py --chapter mid-s2c6
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_question_answers import call_gateway, load_env_file  # noqa: E402

BASE = Path(__file__).resolve().parents[1]
OUT_DIR = BASE / 'data' / 'notebook_review'
DEFAULT_MODEL = 'glm-5.2'
# 目前最長的 code cell 約 3,300 字；留餘裕讓語意審核看到完整程式碼。
CELL_CHAR_LIMIT = 6000


def load(path: Path) -> Any:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def code_cells(notebook: dict[str, Any]) -> list[tuple[int, str, str]]:
    """(index, source, preceding markdown) for every non-empty code cell."""
    cells = []
    last_markdown = ''
    for index, cell in enumerate(notebook.get('cells', [])):
        source = ''.join(cell.get('source', []))
        if cell.get('cell_type') == 'markdown':
            last_markdown = source
        elif cell.get('cell_type') == 'code' and source.strip():
            cells.append((index, source, last_markdown))
    return cells


def runnable(source: str) -> str:
    """Drop shell/magic lines; they are valid in Colab but not in plain Python."""
    return '\n'.join('' if line.lstrip().startswith(('!', '%')) else line
                     for line in source.splitlines())


# Colab injects these; plain Python does not. Without the shim every notebook that
# calls display() fails for a reason that says nothing about the notebook — 7 of the
# first 9 "failures" were exactly this.
COLAB_PREAMBLE = """
import builtins
def _display(*args, **kwargs):
    for arg in args:
        print(arg)
builtins.display = _display
def get_ipython():
    return None
builtins.get_ipython = get_ipython
import matplotlib
matplotlib.use('Agg')
"""


def execution_check(path: Path, python: str, timeout: int) -> dict[str, Any]:
    """Run the whole notebook as one script. TODO cells are placeholders, so skip."""
    notebook = load(path)
    parts, skipped = [], 0
    for index, source, _ in code_cells(notebook):
        if '# TODO' in source:
            skipped += 1
            continue
        parts.append(f'# --- cell {index} ---\n{runnable(source)}')
    script = COLAB_PREAMBLE + '\n\n' + '\n\n'.join(parts)
    if not script.strip():
        return {'status': 'empty', 'skippedCells': skipped}

    with tempfile.TemporaryDirectory() as workdir:
        script_path = Path(workdir) / 'notebook.py'
        script_path.write_text(script, encoding='utf-8')
        try:
            result = subprocess.run([python, script_path.as_posix()],
                                    capture_output=True, text=True,
                                    timeout=timeout, cwd=workdir,
                                    env={'MPLBACKEND': 'Agg', 'PATH': '/usr/bin:/bin'})
        except subprocess.TimeoutExpired:
            return {'status': 'timeout', 'skippedCells': skipped}
    if result.returncode == 0:
        return {'status': 'ok', 'skippedCells': skipped}
    if 'ModuleNotFoundError' in result.stderr:
        # Colab ships far more packages than this checker's venv; a missing import
        # here is a checker-environment fact, not a notebook defect.
        missing = result.stderr.strip().splitlines()[-1]
        return {'status': 'skipped', 'skippedCells': skipped, 'error': missing}
    tail = [line for line in result.stderr.strip().splitlines() if line.strip()]
    cell = ''
    for line in script.splitlines():
        if line.startswith('# --- cell '):
            cell = line
    return {'status': 'error', 'skippedCells': skipped,
            'error': tail[-1] if tail else '', 'traceTail': tail[-4:],
            'lastCellMarker': cell}


SEMANTIC_PROMPT = """以下是一份給 iPAS 中級考生的教學 Notebook。
請只找出**說明與程式碼不一致**的地方——說明宣稱做了某件事，但程式碼實際上做的是別的事。

不要report：風格建議、可以更好的寫法、缺少註解、效能問題。只要「說明與程式碼不符」。

只輸出 JSON，不要說明文字：
{{"mismatches":[{{"cell":3,"claim":"說明宣稱等寬分箱","actual":"bins=[20,30,40,50,70] 最後一組寬度為 20","severity":"high"}}]}}
沒有問題就輸出 {{"mismatches":[]}}

Notebook「{title}」：
{body}
"""


def semantic_check(path: Path, model: str, timeout: int) -> dict[str, Any]:
    notebook = load(path)
    blocks = []
    for index, source, markdown in code_cells(notebook):
        explanation = markdown.strip()[:600]
        # 截斷必須看得見：第一版截在 1500 字，模型看到半截程式碼就回報「程式碼中斷」
        # 「未執行 fit_predict」等假瑕疵（mid-s3c4/s3c9/s3c11 三筆誤報都是這樣來的）。
        body = source if len(source) <= CELL_CHAR_LIMIT else (
            source[:CELL_CHAR_LIMIT] + f'\n# …（本 cell 尚有 {len(source) - CELL_CHAR_LIMIT} '
            '字未顯示，請勿據此判斷程式碼未完成）')
        blocks.append(f'### cell {index}\n說明：{explanation}\n```python\n{body}\n```')
    prompt = SEMANTIC_PROMPT.format(title=path.stem, body='\n\n'.join(blocks))
    # gateway 會間歇性回空內容（推理模型把預算花在 reasoning_content）。單次呼叫失敗
    # 就記成 no-response，一輪下來有 9 本沒審到，而摘要看起來像全部通過。
    for _ in range(3):
        raw = call_gateway(prompt, model, timeout, None, 4000)
        if raw:
            break
    if not raw:
        return {'status': 'no-response'}
    text = raw.strip()
    if text.startswith('```'):
        text = '\n'.join(text.split('\n')[1:]).rsplit('```', 1)[0]
    start, end = text.find('{'), text.rfind('}')
    if start < 0:
        return {'status': 'unparsed', 'raw': raw[:200]}
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return {'status': 'unparsed', 'raw': raw[:200]}
    return {'status': 'ok', 'mismatches': data.get('mismatches', [])}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--python', default=sys.executable,
                        help='執行檢查用的直譯器（需有 pandas/sklearn/matplotlib）')
    parser.add_argument('--chapter', help='只檢查一章')
    parser.add_argument('--exec-only', action='store_true')
    parser.add_argument('--semantic-only', action='store_true')
    parser.add_argument('--model', default=DEFAULT_MODEL)
    parser.add_argument('--timeout', type=int, default=180)
    parser.add_argument('--workers', type=int, default=3)
    args = parser.parse_args()

    load_env_file()
    notebooks = sorted(BASE.glob('notebooks/*/*.ipynb'))
    if args.chapter:
        notebooks = [p for p in notebooks if p.stem == args.chapter]
    if not notebooks:
        raise SystemExit('找不到 notebook')
    print(f'檢查 {len(notebooks)} 本 committed notebook')

    # 併進既有報告，不要覆蓋：--chapter 只跑一章時整份覆蓋掉，其餘章節會退回讀
    # 過期的 flagged.json，看起來像「28 章仍有問題」。
    out_path = OUT_DIR / 'committed_review.json'
    results: dict[str, dict[str, Any]] = load(out_path) if out_path.exists() else {}

    if not args.semantic_only:
        for path in notebooks:
            outcome = execution_check(path, args.python, args.timeout)
            results.setdefault(path.stem, {})['execution'] = outcome
            mark = {'ok': 'OK  ', 'error': 'FAIL', 'timeout': 'TIME',
                    'empty': '----'}.get(outcome['status'], '????')
            detail = outcome.get('error', '')
            print(f'{mark} 執行 {path.stem:12} {detail[:90]}')

    if not args.exec_only:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {executor.submit(semantic_check, path, args.model, args.timeout): path
                       for path in notebooks}
            for future in as_completed(futures):
                path = futures[future]
                outcome = future.result()
                results.setdefault(path.stem, {})['semantic'] = outcome
                bad = outcome.get('mismatches', [])
                if outcome['status'] != 'ok':
                    # 「沒審成」不可以印成「0 處不符」——那正是把失敗讀成通過。
                    print(f"???? 語意 {path.stem:12} 未取得結果（{outcome['status']}）")
                    continue
                mark = 'WARN' if bad else 'OK  '
                first = f"cell {bad[0]['cell']}: {bad[0].get('claim','')}" if bad else ''
                print(f'{mark} 語意 {path.stem:12} {len(bad)} 處不符 {first[:70]}')

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')

    exec_fail = [k for k, v in results.items()
                 if v.get('execution', {}).get('status') in ('error', 'timeout')]
    sem_fail = [k for k, v in results.items() if v.get('semantic', {}).get('mismatches')]
    sem_missing = [k for k, v in results.items()
                   if v.get('semantic', {}).get('status') not in (None, 'ok')]
    print(f'\n執行失敗 {len(exec_fail)}：{", ".join(exec_fail) or "無"}')
    print(f'說明與程式碼不符 {len(sem_fail)}：{", ".join(sem_fail) or "無"}')
    print(f'語意審核未完成 {len(sem_missing)}：{", ".join(sem_missing) or "無"}（未完成 ≠ 通過，需重跑）')
    print(f'報告 → {out_path.relative_to(BASE)}')
    raise SystemExit(1 if exec_fail else 0)


if __name__ == '__main__':
    main()
