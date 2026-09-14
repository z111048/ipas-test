#!/usr/bin/env python3
"""Production bundle must contain no DEV preview pointer, body, marker, or Lab asset.

Also runs the pure-TS concept URL resolver (frontend/src/data/conceptLookup.ts) under Node
directly: the ``/concepts?c=`` legacy-name compatibility layer has three strictly ordered
stages, and real data currently never reaches the third (``previousNames`` are all empty),
so only a fixture can prove the order.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
GENERATED = ROOT / "frontend/src/generated/learning"
SOURCE = ROOT / "frontend/src/features/learning/data.ts"


def fail(message: str) -> None:
    print(f"✗ {message}")
    raise SystemExit(1)


if not (DOCS / "index.html").exists():
    fail("docs/ production build 不存在；先執行 frontend/npm run build")

source = SOURCE.read_text()
if "../../generated/learning/releases/**/*.json" not in source or "previews/**/*.json" in source:
    fail("production loader 必須只枚舉 releases，不可枚舉 previews")

POINTER = GENERATED / "preview.json"
if not POINTER.exists():
    # Fresh checkout（CI）沒有 gitignored 的 preview 指標；照 E2E 的做法先建一次 preview。
    # 只寫 gitignored 路徑（previews/、preview.json），不碰 production current.json。
    built = subprocess.run([sys.executable, "scripts/build_learning_content.py", "--preview"],
                           cwd=ROOT, capture_output=True, text=True)
    if built.returncode != 0 or not POINTER.exists():
        fail("無法建立 learning preview 指標：" + (built.stdout + built.stderr).strip()[-400:])
pointer = json.loads(POINTER.read_text())
release = GENERATED / Path(pointer["manifestPath"]).parent
index = json.loads((release / "index.json").read_text())
first_unit = json.loads((release / index["units"][0]["path"]).read_text())
body_marker = first_unit["bodyMarkdown"][80:180].encode()
needles = {
    "preview releaseId": pointer["releaseId"].encode(),
    "preview DOM marker": b"data-learning-preview",
    "preview Chinese banner": "開發預覽".encode(),
    "preview authored body": body_marker,
}
files = [path for path in DOCS.rglob("*") if path.is_file()]
for label, needle in needles.items():
    hits = [str(path.relative_to(ROOT)) for path in files if needle in path.read_bytes()]
    if hits:
        fail(f"{label} 洩漏到 production bundle: {hits[:3]}")

for suffix in (".ipynb", ".csv"):
    emitted = [str(path.relative_to(ROOT)) for path in files if path.suffix == suffix]
    if emitted:
        fail(f"preview Lab {suffix} 被輸出到 production: {emitted[:3]}")

print("✓ production bundle 未包含 preview pointer/body/marker/Lab assets")

# /concepts?c= 解析順序（LP-210C）。.cjs 用 frontend 的 typescript 轉譯 conceptLookup.ts，Node 20 也能跑；沒有 node 就是環境缺件，不是通過。
lookup_check = ROOT / "tests/frontend_checks/concept_lookup_check.cjs"
result = subprocess.run(["node", str(lookup_check)], cwd=ROOT, capture_output=True, text=True)
sys.stdout.write(result.stdout)
if result.returncode != 0:
    sys.stdout.write(result.stderr)
    fail("conceptLookup.ts 的 ?c= 解析順序檢查未通過")
