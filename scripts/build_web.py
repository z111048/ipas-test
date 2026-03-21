#!/usr/bin/env python3
"""Build the iPAS study platform via Vite (React + TypeScript + Tailwind CSS)."""

import subprocess
import sys
from pathlib import Path

ROOT = Path('/home/james/projects/ipas-test')
FRONTEND = ROOT / 'frontend'


def build():
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
    build()
