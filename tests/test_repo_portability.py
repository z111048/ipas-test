#!/usr/bin/env python3
"""Reject machine-specific repository roots in executable project files."""

from __future__ import annotations

import ast
import re
import sys
import warnings
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON_FILES = sorted((ROOT / 'scripts').glob('*.py')) + sorted((ROOT / 'tests').glob('*.py'))
FRONTEND_CONFIGS = [
    ROOT / 'frontend' / 'vite.config.ts',
    *sorted((ROOT / 'frontend').glob('tsconfig*.json')),
]
UNIX_HOME = '/' + 'home/'
MAC_HOME = '/' + 'Users/'
WINDOWS_HOME = re.compile(r'[A-Za-z]:[\\/](?:Users|home)[\\/]', re.IGNORECASE)


def machine_specific_lines(path: Path) -> list[int]:
    lines = path.read_text(encoding='utf-8').splitlines()
    return [
        index
        for index, line in enumerate(lines, start=1)
        if UNIX_HOME in line or MAC_HOME in line or WINDOWS_HOME.search(line)
    ]


def subprocess_calls_without_cwd(path: Path) -> list[int]:
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', SyntaxWarning)
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    missing: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        owner = node.func.value
        if (
            isinstance(owner, ast.Name)
            and owner.id == 'subprocess'
            and node.func.attr in {'run', 'Popen', 'check_call', 'check_output'}
            and not any(keyword.arg == 'cwd' for keyword in node.keywords)
        ):
            missing.append(node.lineno)
    return missing


def main() -> int:
    failures: list[str] = []
    for path in [*PYTHON_FILES, *FRONTEND_CONFIGS]:
        for line_number in machine_specific_lines(path):
            failures.append(f'{path.relative_to(ROOT)}:{line_number}')
    for path in PYTHON_FILES:
        for line_number in subprocess_calls_without_cwd(path):
            failures.append(f'{path.relative_to(ROOT)}:{line_number} (subprocess 缺少 cwd)')

    if failures:
        print('FAIL：發現機器專屬路徑或 cwd 未明確的 subprocess：')
        for failure in failures:
            print(f'  - {failure}')
        return 1

    print(
        f'PASS：{len(PYTHON_FILES)} 支 Python 檔與 {len(FRONTEND_CONFIGS)} 份前端設定'
        '皆無機器專屬根路徑，subprocess 皆明確指定 cwd'
    )
    return 0


if __name__ == '__main__':
    sys.exit(main())
