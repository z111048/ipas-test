#!/usr/bin/env python3
"""Build the iPAS study platform via Vite (React + TypeScript + Tailwind CSS).

Runs the deterministic resource audit first and refuses to build on FAIL —
detecting a defect without blocking it is the same as not detecting it.
Known, deliberately accepted exceptions belong in data/audit_allowlist.json;
`--skip-audit` exists for local iteration and should not be used to publish.
"""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path('/home/james/projects/ipas-test')
FRONTEND = ROOT / 'frontend'


def audit() -> None:
    result = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'audit_resources.py')],
                            cwd=ROOT, check=False)
    if result.returncode != 0:
        print('ERROR: 資源審核未通過，已中止 build。修好問題，或把刻意接受的例外'
              '寫進 data/audit_allowlist.json（要寫理由）。', file=sys.stderr)
        sys.exit(1)


def build(skip_audit: bool = False):
    if skip_audit:
        print('WARNING: 已跳過資源審核，這個產物不應該發佈')
    else:
        audit()

    if not FRONTEND.exists():
        print('ERROR: frontend/ directory not found', file=sys.stderr)
        sys.exit(1)

    result = subprocess.run(
        ['npm', 'run', 'build'],
        cwd=FRONTEND,
        check=False,
    )
    if result.returncode != 0:
        print('ERROR: Vite build failed', file=sys.stderr)
        sys.exit(1)

    docs_path = ROOT / 'docs' / 'index.html'
    size = docs_path.stat().st_size / 1024
    print(f'Done — docs/index.html ({size:.1f} KB)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-audit', action='store_true',
                        help='本機迭代用；跳過審核的產物不要發佈')
    build(parser.parse_args().skip_audit)
