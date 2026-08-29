#!/usr/bin/env python3
"""跑完整套驗收。每個重構階段結束時應該全綠才算完成。

    python3 tests/run_all.py
    python3 tests/run_all.py --skip-browser    # 只跑靜態檢查（沒裝 playwright 時）

7 項驗收，分兩層：
  1. npm run build            —— tsc 零錯誤 + vite 產出
  2. verify_data_alignment    —— 資料對齊 toc_manifest（SSOT），初級與中級各一次
  3. audit_resources          —— 7 項確定性審核，任一 FAIL 就擋
  4. 端對端測試               —— 考試流程、章節練習、全路由（需要 playwright）

前兩道是 CLAUDE.md 不變量 5 訂的；後兩道是 2026-08-29 補的，理由見 tests/README.md。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


def run(label: str, cmd: list[str], cwd: Path = BASE) -> tuple[str, bool, float]:
    started = time.monotonic()
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    elapsed = time.monotonic() - started
    ok = result.returncode == 0
    print(f'  {"✓" if ok else "✗"} {label:<40} {elapsed:5.1f}s')
    if not ok:
        tail = (result.stdout + result.stderr).strip().splitlines()[-15:]
        for line in tail:
            print(f'      {line}')
    return label, ok, elapsed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--skip-browser', action='store_true',
                        help='跳過需要 playwright 的端對端測試')
    args = parser.parse_args()

    results = []

    print('\n=== 靜態 ===')
    results.append(run('npm run build（tsc + vite）',
                       ['npm', 'run', 'build'], cwd=BASE / 'frontend'))
    for level in ('初級', '中級'):
        results.append(run(f'verify_data_alignment --level {level}',
                           [sys.executable, 'scripts/verify_data_alignment.py', '--level', level]))
    results.append(run('audit_resources（7 項）',
                       [sys.executable, 'scripts/audit_resources.py']))

    if not args.skip_browser:
        print('\n=== 端對端（會自己啟停 dev server）===')
        results.append(run('test_exam_flow', [sys.executable, 'tests/test_exam_flow.py']))
        results.append(run('test_practice_flow', [sys.executable, 'tests/test_practice_flow.py']))
        results.append(run('test_routes', [sys.executable, 'tests/test_routes.py']))
    else:
        print('\n=== 端對端：已跳過（--skip-browser）===')

    failed = [label for label, ok, _ in results if not ok]
    total = sum(elapsed for _, _, elapsed in results)
    print(f'\n{"=" * 56}')
    print(f'{len(results) - len(failed)}/{len(results)} 通過，共 {total:.0f}s')
    if failed:
        print('✗ 失敗：' + '、'.join(failed))
        return 1
    print('✓ 全部通過（已跳過端對端）' if args.skip_browser else '✓ 全部通過')
    return 0


if __name__ == '__main__':
    sys.exit(main())
