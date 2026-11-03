#!/usr/bin/env python3
"""節慶主題機制（frontend/src/features/seasonal/）的純函式檢查。

2026-11-03 加入（萬聖節主題）。日期區間判斷（含首尾、跨年）、台北時間換日與
``?seasonal=`` 覆寫解析都是純函式，用 tests/frontend_checks/seasonal_schedule_check.cjs
以 frontend 自己的 typescript 轉譯真正的 schedule.ts 後執行，不另寫一份等價邏輯。

另做兩條靜態防線：裝飾元件一律 aria-hidden；安靜路由（學習指引、文章閱讀）不得從清單消失。
Run directly or through tests/test_resource_catalog.py (run_all item 1)；驗收總數維持 21 項。
"""

from __future__ import annotations

import re
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEASONAL = ROOT / 'frontend' / 'src' / 'features' / 'seasonal'
CHECK = ROOT / 'tests' / 'frontend_checks' / 'seasonal_schedule_check.cjs'


class SeasonalThemeTests(unittest.TestCase):
    def test_schedule_pure_functions(self) -> None:
        # 沒有 node／frontend 依賴是環境缺件，不是通過。
        self.assertIsNotNone(shutil.which('node'), 'node 不在 PATH')
        self.assertTrue((ROOT / 'frontend/node_modules/typescript').is_dir(),
                        'frontend/node_modules 未安裝（cd frontend && npm ci）')
        result = subprocess.run(['node', str(CHECK)], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_decorative_svgs_are_hidden_from_assistive_tech(self) -> None:
        art = (SEASONAL / 'halloween' / 'art.tsx').read_text(encoding='utf-8')
        svgs = re.findall(r'<svg\b[^>]*>', art)
        self.assertGreater(len(svgs), 0)
        for tag in svgs:
            self.assertIn('aria-hidden="true"', tag)

    def test_reading_and_exam_areas_stay_quiet(self) -> None:
        themes = (SEASONAL / 'themes.ts').read_text(encoding='utf-8')
        for prefix in ("'/guide/'", "'/articles/'"):
            self.assertIn(prefix, themes)
        provider = (SEASONAL / 'SeasonalProvider.tsx').read_text(encoding='utf-8')
        self.assertRegex(provider, r'const quiet = focusMode \|\| isQuietPath\(pathname\)')

    def test_copy_does_not_mention_generation(self) -> None:
        # CLAUDE.md 不變量 2：使用者可見文案不得透露內容由 AI 生成。
        for path in SEASONAL.rglob('*.tsx'):
            text = path.read_text(encoding='utf-8')
            strings = re.findall(r"'[^'\n]*'|\"[^\"\n]*\"|>[^<>{}\n]+<", text)
            for s in strings:
                self.assertNotRegex(s, r'AI|生成', f'{path.name}: {s}')


if __name__ == '__main__':
    unittest.main()
