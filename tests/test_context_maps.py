#!/usr/bin/env python3
"""「本章脈絡」資料契約（data/context_maps/ → frontend/src/generated/contextMaps/）。

* 來源全數通過逐字引用驗證，產物與來源一致（export_context_maps.py --check）。
* 初級→中級連結與疑誤註記指向存在的章節與區塊。
* 對外文案不透露生成方式（CLAUDE.md 不變量 2）。
在 run_all 的 test_track_a_ocr_repairs 項內執行（不新增閘門數）。
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / 'frontend/src/generated'


class ContextMapContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.maps = {path.stem: json.loads(path.read_text(encoding='utf-8'))
                    for path in sorted((GENERATED / 'contextMaps').glob('*.json'))}
        cls.outlines = json.loads((GENERATED / 'guideOutlines.json').read_text(encoding='utf-8'))['guides']

    def blocks(self, subject_id: str, chapter_id: str) -> set[str]:
        guide = self.outlines[subject_id]
        node = guide['nodesById'][chapter_id]
        content = json.loads((GENERATED / 'guideContent' / guide['key'] / node['contentRef']).read_text(encoding='utf-8'))
        return {block['id'] for block in content['blocks']}

    def test_export_check_passes(self) -> None:
        result = subprocess.run([sys.executable, 'scripts/export_context_maps.py', '--check'],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_every_map_has_source_chapter(self) -> None:
        sources = {path.stem for path in (ROOT / 'data/context_maps/chapters').glob('*.json')}
        self.assertEqual(set(self.maps), sources)
        self.assertGreaterEqual(len(self.maps), 41)

    def test_links_and_notes_point_to_existing_blocks(self) -> None:
        linked = 0
        for nid, data in self.maps.items():
            chapter = data['chapter']
            own = self.blocks(chapter['subjectId'], nid)
            for note in data['notes']:
                self.assertIn(f'block-{note["block"]}', own, nid)
            for item in data['examOnly']:
                link = item.get('link')
                if not link:
                    continue
                linked += 1
                self.assertTrue(chapter['guideKey'].startswith('初級'), nid)
                self.assertIn(f'block-{link["block"]}', self.blocks(link['subjectId'], link['chapterId']), nid)
        self.assertGreater(linked, 0)

    def test_copy_does_not_reveal_generation(self) -> None:
        banned = re.compile(r'AI\s*生成|模型產生|由\s*AI|人工智慧生成|機器生成')
        for nid, data in self.maps.items():
            texts = [data['headline'], data['lede'], *(n['gist'] for n in data['nodes']),
                     *(c['text'] for c in data['confusions']), *(n['text'] for n in data['notes'])]
            for text in texts:
                self.assertIsNone(banned.search(text), f'{nid}: {text}')


if __name__ == '__main__':
    unittest.main()
