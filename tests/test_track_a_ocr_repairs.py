#!/usr/bin/env python3
"""Exact, cache-independent regression tests for the 169 Track-A repairs."""

from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import track_a_ocr_repairs as track_a  # noqa: E402
import guide_publication_overlays as publication_overlays  # noqa: E402

audit_generated_track_a = track_a.audit_generated_track_a


class TrackAOcrRepairGateTests(unittest.TestCase):
    @staticmethod
    def fresh_guide3_fragment_routes() -> dict[str, list[dict]]:
        """Minimal cache-free fixture copied from a fresh guide3 tree build."""
        def fragment(
            block_id: str,
            block_type: str,
            text: str,
            page_index: int,
            depth: int,
            marker: str | None = None,
        ) -> dict:
            block = {
                'id': block_id,
                'type': block_type,
                'depth': depth,
                'text': text,
                'pageIndex': page_index,
                'bbox': [0.0, 0.0, 1.0, 1.0],
                'kind': block_type,
                'nodeId': 'fixture',
                'source': 'page_extract',
            }
            if block_type == 'paragraph':
                block['indentFirstLine'] = False
            if marker is not None:
                block['marker'] = marker
            return block

        return {
            'mid-s3c5': [
                fragment(
                    'block-57', 'list_item',
                    '在損失函數中加入L1 正則化項（權重絕對值和），不僅限制係數大',
                    51, 7, '○',
                ),
                fragment(
                    'block-58', 'paragraph',
                    '小，還能將部分係數直接縮減為零，達到特徵選擇（Feature Selection） 的效果。',
                    52, 5,
                ),
                # The historical TA-146 ID now belongs to unrelated content.
                fragment('block-268', 'list_item', '醫學檢測中診斷疾病類', 62, 5, '•'),
                fragment(
                    'block-270', 'paragraph',
                    '不同的分類演算法，各自具備不同的數學假設、優勢與限制。例如，邏輯迴歸簡單易解釋，但無法捕捉複雜的非線性邊界；支援向量機能處理高維度資料，但計算成本較高；集成方法如隨機森林或梯度提升，通常能在準確度上表現優異，',
                    62, 4,
                ),
                fragment(
                    'block-271', 'paragraph',
                    '但缺點是模型較難解釋。依據資料特性、規模、以及解釋需求，挑選合適的分類模型，是建置高效能機器學習系統的關鍵步驟。',
                    63, 4,
                ),
                # The historical TA-147 ID also drifted to a preceding item.
                fragment(
                    'block-777', 'list_item',
                    '構建FP 樹在處理非常龐大且複雜的資料集時可能需要大量記憶體。',
                    87, 7, '○',
                ),
                fragment(
                    'block-780', 'paragraph',
                    '異常偵測（Anomaly Detection）或稱離群值偵測（Outlier Detection）是一種辨識資料集中與大多數資料行為顯著不同的模式或資料點的技術。這些「異常」',
                    87, 5,
                ),
                fragment(
                    'block-781', 'paragraph',
                    '或「離群值」往往具有重要的意義，可能代表著錯誤、欺詐、設備故障、網路入侵，或新穎的、未曾見過的事件。',
                    88, 5,
                ),
            ],
            'mid-s3c6': [
                fragment(
                    'block-114', 'paragraph',
                    '每一層會接收到來自其「後方」層次的梯度資訊，然後利用這些資訊（以及該層自身的計算，特別是激活函數的導數），來計算出屬於自己這一層權重和偏置的梯度，再將相關的梯度傳遞',
                    97, 7,
                ),
                fragment(
                    'block-115', 'paragraph',
                    '給「前方」的層次。這樣，每個參數都能「知道」自己在導致最終錯誤中扮演的角色，以及該如何調整。',
                    98, 7,
                ),
                fragment(
                    'block-396', 'paragraph',
                    '帶遮罩的多頭自注意力機制（Masked Multi-head Self- Attention），確保在生成當前詞時，解碼器只能「關注」已生成的前序詞語，而不能「偷看」未來的詞語。',
                    114, 5,
                ),
                fragment(
                    'block-397', 'paragraph',
                    '編碼器-解碼器（Encoder-Decoder）注意力機制，允許解碼器在',
                    114, 5,
                ),
                fragment(
                    'block-398', 'paragraph',
                    '生成每個詞時，根據自身當前的狀態，動態地「關注」編碼器輸出中的相關資訊。',
                    115, 5,
                ),
                fragment(
                    'block-410', 'list_item',
                    '模型組成機制 Transformer 的創新來自於其獨特的模塊化設計和核心組件。',
                    115, 5, '•',
                ),
                fragment(
                    'block-412', 'paragraph',
                    '注意力機制（Attention Mechanism）是Transformer 最核心的創新，賦',
                    115, 5,
                ),
                fragment(
                    'block-413', 'paragraph',
                    '予模型在處理序列中任何一個元素時，能夠動態地「關注」序列中所有其他相關元素，並根據相關性賦予不同權重。',
                    116, 5,
                ),
            ],
            'mid-s3c7': [
                fragment(
                    'block-35', 'paragraph',
                    '同一觀察單位在資料集中多次出現，常因系統重複寫入、資料整合錯誤或缺',
                    136, 5,
                ),
                fragment('block-36', 'paragraph', '少唯一辨識碼導致。', 137, 5),
            ],
            'mid-s3c12': [
                fragment(
                    'block-45', 'paragraph',
                    '無論是資料偏見還是模型偏見，若企業未能即時辨識並修正，都可能帶來多重風險與負面影響，涉及技術層面、法律責任、商譽及社會信任。常見的潛在影',
                    207, 5,
                ),
                fragment('block-46', 'paragraph', '響包括：', 208, 5),
            ],
        }

    def make_cache_free_tree(self, destination: Path) -> Path:
        """Copy only committed release inputs; intentionally omit every cache."""
        content_source = ROOT / 'frontend/src/generated/guideContent'
        content_destination = destination / 'frontend/src/generated/guideContent'
        shutil.copytree(content_source, content_destination)
        generated_destination = destination / 'frontend/src/generated'
        for filename in ('guideHierarchy.json', 'guideSearchIndex.json'):
            shutil.copy2(ROOT / 'frontend/src/generated' / filename, generated_destination / filename)

        source_urls: set[str] = set()
        for path in content_destination.glob('*/*.json'):
            payload = json.loads(path.read_text(encoding='utf-8'))
            source_urls.update(
                str(block['src'])
                for block in payload.get('blocks') or []
                if block.get('type') == 'source_image' and block.get('src')
            )
        source_urls.update({
            '/pdf-assets/初級/guide1/page_045/page.png',
            '/pdf-assets/中級/guide3/page_093/page.png',
            '/pdf-assets/中級/guide3/page_168/page.png',
        })
        for source_url in source_urls:
            source = ROOT / 'frontend/public' / source_url.lstrip('/')
            target = destination / 'frontend/public' / source_url.lstrip('/')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

        # No data/, page_clean/, page_extract/, or guide_tree/ is copied.  The
        # gitignored reading snapshot is absent as it is on a fresh clone.
        return destination

    def test_fresh_guide3_fragments_rebuild_exact_signed_blocks(self) -> None:
        registry = json.loads(track_a.SIGNATURE_REGISTRY_PATH.read_text(encoding='utf-8'))
        fixtures = self.fresh_guide3_fragment_routes()
        repairs_by_node: dict[str, list[dict]] = {}
        for repair in track_a.OFF_BY_ONE_REPAIRS:
            if repair['level'] == '中級' and repair['key'] == 'guide3' and 145 <= int(repair['id'][3:]) <= 152:
                repairs_by_node.setdefault(repair['node'], []).append(repair)

        for node, source_blocks in fixtures.items():
            with self.subTest(node=node):
                repaired = track_a.apply_track_a_block_repairs(
                    '中級', 'guide3', node, source_blocks,
                    require_prebuilt_matches=True,
                )
                repaired_twice = track_a.apply_track_a_block_repairs(
                    '中級', 'guide3', node, repaired,
                    require_prebuilt_matches=True,
                )
                self.assertEqual(repaired_twice, repaired)
                self.assertEqual(
                    len(repaired),
                    len(source_blocks) - len(repairs_by_node[node]),
                )
                for repair in repairs_by_node[node]:
                    expected = registry['off_by_one'][repair['id']]
                    matches = [
                        block for block in repaired
                        if block.get('trackARepairId') == repair['id']
                    ]
                    self.assertEqual(len(matches), 1)
                    target = matches[0]
                    self.assertEqual(
                        track_a._block_signature_sha256(
                            target.get('type'), track_a._block_text(target),
                        ),
                        expected['blockSignatureSha256'],
                    )
                    self.assertEqual(target.get('pageIndex'), expected['pageIndex'])
                    self.assertEqual(
                        target.get('sourcePageIndexes'),
                        expected['sourcePageIndexes'],
                    )
                    if repair['id'] == 'TA-145':
                        fragment_pages = sorted({
                            block['pageIndex'] for block in source_blocks
                            if block['id'] in {'block-57', 'block-58'}
                        })
                        self.assertEqual(expected['sourcePageIndexes'], [51, 52])
                        self.assertEqual(target['sourcePageIndexes'], fragment_pages)
                    if repair['id'] == 'TA-147':
                        self.assertIn('「異常」 或「離群值」', target['text'])
                decoys = {
                    'mid-s3c5': {'block-268', 'block-777'},
                    'mid-s3c6': {'block-396', 'block-410'},
                }.get(node, set())
                self.assertTrue(all(
                    block.get('trackARepairId') is None
                    for block in repaired
                    if block.get('id') in decoys
                ))

    def test_signed_block_locator_rejects_zero_and_ambiguous_windows(self) -> None:
        pair = self.fresh_guide3_fragment_routes()['mid-s3c7']
        with self.assertRaisesRegex(ValueError, r'TA-151 .* matched 0, expected 1'):
            track_a.apply_track_a_block_repairs(
                '中級', 'guide3', 'mid-s3c7', pair[:1],
                require_prebuilt_matches=True,
            )

        duplicate = copy.deepcopy(pair)
        for block in duplicate:
            block['id'] = f"duplicate-{block['id']}"
        with self.assertRaisesRegex(ValueError, r'TA-151 .* matched 2, expected 1'):
            track_a.apply_track_a_block_repairs(
                '中級', 'guide3', 'mid-s3c7', [*pair, *duplicate],
                require_prebuilt_matches=True,
            )

    def test_intact_signed_block_does_not_depend_on_historical_id(self) -> None:
        pair = self.fresh_guide3_fragment_routes()['mid-s3c7']
        intact = copy.deepcopy(pair[0])
        intact.update({
            'id': 'fresh-shifted-id',
            'text': ''.join(block['text'] for block in pair),
        })
        repaired = track_a.apply_track_a_block_repairs(
            '中級', 'guide3', 'mid-s3c7', [intact],
            require_prebuilt_matches=True,
        )
        self.assertEqual(len(repaired), 1)
        self.assertEqual(repaired[0]['trackARepairId'], 'TA-151')
        self.assertEqual(repaired[0]['trackAOriginalBlockId'], 'block-35')
        self.assertEqual(repaired[0]['sourcePageIndexes'], [136, 137])

    def test_exact_inventory_gate_passes_without_pipeline_caches(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_cache_free_tree(Path(directory))
            result = audit_generated_track_a(root)
        self.assertEqual(result['inventory_total'], 169)
        self.assertEqual(result['checked_total'], 169)
        self.assertEqual(result['remaining'], 0, '\n'.join(result['failures']))
        self.assertEqual(result['publication_overlay_total'], 3)
        self.assertEqual(set(result['publication_overlay_names']), {
            'source-math:X_max',
            'source-math:softmax-z_j',
            'official-errata:perceptron-w_i-x_i',
        })
        self.assertEqual(result['publication_overlay_remaining'], 0)
        self.assertEqual(result['publication_structure_total'], 3)
        self.assertEqual(set(result['publication_structure_names']), {
            'manual-heading:s1c2-hypothesis',
            'manual-heading:s1c4-hierarchy',
            'manual-heading:s2c3-import-strategy',
        })
        self.assertEqual(result['publication_structure_remaining'], 0)
        self.assertEqual(set(result['checked_ids']), {f'TA-{index:03d}' for index in range(1, 170)})
        self.assertTrue(all(value == 0 for value in result['category_remaining'].values()))

    def test_exercise_content_tamper_fails_committed_signature(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_cache_free_tree(Path(directory))
            path = root / 'frontend/src/generated/guideContent/初級-guide1/s1c1.json'
            payload = json.loads(path.read_text(encoding='utf-8'))
            target = next(
                block for block in payload['blocks']
                if block.get('type') == 'question' and str(block.get('text') or '').startswith('6.')
            )
            target['text'] += '（竄改）'
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
            result = audit_generated_track_a(root)
        self.assertGreater(result['remaining'], 0)
        self.assertTrue(any(failure.startswith('TA-051:') for failure in result['failures']))

    def test_chapter_wide_provenance_union_fails_exact_block_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_cache_free_tree(Path(directory))
            path = root / 'frontend/src/generated/guideContent/初級-guide1/s1c1.json'
            payload = json.loads(path.read_text(encoding='utf-8'))
            target = next(
                block for block in payload['blocks']
                if block.get('type') == 'question' and str(block.get('text') or '').startswith('6.')
            )
            target['sourcePageIndexes'] = [25, 26, 27, 28]
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
            result = audit_generated_track_a(root)
        self.assertGreater(result['remaining'], 0)
        self.assertTrue(any(failure.startswith('TA-051:') for failure in result['failures']))

    def test_inventory_ids_are_order_independent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_cache_free_tree(Path(directory))
            registry = json.loads(track_a.SIGNATURE_REGISTRY_PATH.read_text(encoding='utf-8'))
            for key in ('exerciseInventoryIdByRoutePage', 'exercise', 'visuals'):
                registry[key] = dict(reversed(list(registry[key].items())))
            registry_path = root / 'reordered-signatures.json'
            registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding='utf-8')
            reversed_formulas = dict(reversed(list(track_a.FORMULA_INVENTORY_BY_PAGE.items())))
            reversed_visuals = dict(reversed(list(track_a.VISUAL_INVENTORY_BY_PAGE.items())))
            with mock.patch.object(track_a, 'FORMULA_INVENTORY_BY_PAGE', reversed_formulas), \
                    mock.patch.object(track_a, 'VISUAL_INVENTORY_BY_PAGE', reversed_visuals):
                result = audit_generated_track_a(root, signature_registry_path=registry_path)
        self.assertEqual(result['remaining'], 0, '\n'.join(result['failures']))
        self.assertEqual(result['publication_overlay_remaining'], 0)
        self.assertEqual(result['publication_structure_remaining'], 0)
        self.assertEqual(track_a.FORMULA_INVENTORY_BY_PAGE[('初級', 'guide1', 45)]['id'], 'TA-001')
        self.assertEqual(track_a.VISUAL_INVENTORY_BY_PAGE[('中級', 'guide3', 155)]['id'], 'TA-169')

    def test_visual_asset_tamper_fails_exact_sha256(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_cache_free_tree(Path(directory))
            asset = root / 'frontend/public/pdf-assets/初級/guide1/page_054/source_visual_01.jpg'
            asset.write_bytes(asset.read_bytes() + b'tampered')
            result = audit_generated_track_a(root)
        self.assertTrue(any(failure.startswith('TA-153:') for failure in result['failures']))

    def test_visual_src_swap_fails_exact_signature(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_cache_free_tree(Path(directory))
            path = root / 'frontend/src/generated/guideContent/中級-guide2/mid-s2c1.json'
            payload = json.loads(path.read_text(encoding='utf-8'))
            page17 = next(
                block for block in payload['blocks']
                if block.get('type') == 'source_image' and block.get('pageIndex') == 17
            )
            page18 = next(
                block for block in payload['blocks']
                if block.get('type') == 'source_image' and block.get('pageIndex') == 18
            )
            page17['src'], page18['src'] = page18['src'], page17['src']
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
            result = audit_generated_track_a(root)
        self.assertTrue(any(failure.startswith('TA-155:') for failure in result['failures']))
        self.assertTrue(any(failure.startswith('TA-156:') for failure in result['failures']))

    def test_bibliography_row_mutation_fails_exact_signature(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_cache_free_tree(Path(directory))
            path = root / 'frontend/src/generated/guideContent/初級-guide1/s1c4.json'
            payload = json.loads(path.read_text(encoding='utf-8'))
            table = next(block for block in payload['blocks'] if block.get('id') == 'block-192')
            table['rows'][0][0] += '（竄改）'
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
            result = audit_generated_track_a(root)
        self.assertTrue(any(failure.startswith('TA-046:') for failure in result['failures']))

    def test_heading_identity_page_and_provenance_mutations_fail(self) -> None:
        mutations = {
            'pageIndex': 999,
            'sourcePageIndexes': [999],
            'trackARepairId': 'TA-999',
            'trackAOriginalBlockId': 'replacement-block',
        }
        for field, value in mutations.items():
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                root = self.make_cache_free_tree(Path(directory))
                path = root / 'frontend/src/generated/guideContent/初級-guide1/s1c1.json'
                payload = json.loads(path.read_text(encoding='utf-8'))
                target = next(
                    block for block in payload['blocks']
                    if block.get('trackARepairId') == 'TA-048'
                )
                target[field] = value
                path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
                result = audit_generated_track_a(root)
            self.assertTrue(any(failure.startswith('TA-048:') for failure in result['failures']))

    def test_bibliography_semantic_duplicate_with_new_ids_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_cache_free_tree(Path(directory))
            path = root / 'frontend/src/generated/guideContent/初級-guide1/s1c4.json'
            payload = json.loads(path.read_text(encoding='utf-8'))
            for original_id, duplicate_id in (
                ('block-191', 'duplicate-bibliography-heading'),
                ('block-192', 'duplicate-bibliography-table'),
            ):
                duplicate = copy.deepcopy(next(block for block in payload['blocks'] if block.get('id') == original_id))
                duplicate['id'] = duplicate_id
                payload['blocks'].append(duplicate)
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
            result = audit_generated_track_a(root)
        self.assertTrue(any(failure.startswith('TA-046:') for failure in result['failures']))

    def test_visual_duplicate_on_wrong_page_fails_route_wide_uniqueness(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_cache_free_tree(Path(directory))
            path = root / 'frontend/src/generated/guideContent/初級-guide1/s1c4.json'
            payload = json.loads(path.read_text(encoding='utf-8'))
            registry = json.loads(track_a.SIGNATURE_REGISTRY_PATH.read_text(encoding='utf-8'))
            expected_src = registry['visuals']['TA-153']['src']
            duplicate = copy.deepcopy(next(
                block for block in payload['blocks']
                if block.get('type') == 'source_image' and block.get('src') == expected_src
            ))
            duplicate.update({
                'id': 'duplicate-source-image',
                'pageIndex': 999,
                'sourcePageIndexes': [999],
            })
            payload['blocks'].append(duplicate)
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
            result = audit_generated_track_a(root)
        self.assertTrue(any(failure.startswith('TA-153:') for failure in result['failures']))

    def test_publication_source_screenshot_url_swap_fails_exact_signature(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_cache_free_tree(Path(directory))
            path = root / 'frontend/src/generated/guideContent/初級-guide1/s1c3.json'
            payload = json.loads(path.read_text(encoding='utf-8'))
            source_page = next(page for page in payload['sourcePages'] if page.get('index') == 45)
            source_page['image'] = '/pdf-assets/中級/guide3/page_093/page.png'
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
            result = audit_generated_track_a(root)
        self.assertIn('source-math:X_max', result['publication_overlay_failures'])

    def test_each_publication_source_screenshot_byte_tamper_fails_sha256(self) -> None:
        registry = json.loads(track_a.SIGNATURE_REGISTRY_PATH.read_text(encoding='utf-8'))
        for overlay_name, expected in registry['publicationSourceScreenshots'].items():
            with self.subTest(overlay_name=overlay_name), tempfile.TemporaryDirectory() as directory:
                root = self.make_cache_free_tree(Path(directory))
                asset = root / 'frontend/public' / expected['src'].lstrip('/')
                asset.write_bytes(asset.read_bytes() + b'tampered-source-provenance')
                result = audit_generated_track_a(root)
            self.assertIn(overlay_name, result['publication_overlay_failures'])

    def test_publication_overlay_transform_is_idempotent(self) -> None:
        hypothesis_title, hypothesis_depth = publication_overlays.PROMOTE_HEADINGS['s1c2']
        hypothesis_source = f'# 章\n\n{hypothesis_title}\n\n表格'
        hypothesis_once = publication_overlays.apply_publication_markdown_overlays(
            '初級', 'guide1', 's1c2', hypothesis_source,
        )
        hypothesis_twice = publication_overlays.apply_publication_markdown_overlays(
            '初級', 'guide1', 's1c2', hypothesis_once,
        )
        self.assertEqual(hypothesis_once, hypothesis_twice)
        self.assertIn(f'{"#" * hypothesis_depth} {hypothesis_title}', hypothesis_once)

        hypothesis_blocks = [{
            'type': 'table',
            'depth': 3,
            'rows': [[hypothesis_title, ''], ['假說檢定之流程', '說明']],
            'pageIndex': 32,
        }]
        hypothesis_blocks_once = publication_overlays.apply_publication_block_overlays(
            '初級', 'guide1', 's1c2', hypothesis_blocks,
        )
        hypothesis_blocks_twice = publication_overlays.apply_publication_block_overlays(
            '初級', 'guide1', 's1c2', hypothesis_blocks_once,
        )
        self.assertEqual(hypothesis_blocks_once, hypothesis_blocks_twice)
        self.assertEqual(hypothesis_blocks_once[0]['type'], 'heading')
        self.assertEqual(hypothesis_blocks_once[0]['depth'], hypothesis_depth)
        self.assertEqual(hypothesis_blocks_once[0]['anchor'], '假說檢定名詞介紹')

        strategy = publication_overlays.GUIDE_NAVIGATION_HEADINGS[
            'manual-heading:s2c3-import-strategy'
        ]
        old_strategy = strategy['forbiddenTitles'][0]
        strategy_markdown = f'# 章\n\n#### {old_strategy}\n\n內容'
        strategy_once = publication_overlays.apply_publication_markdown_overlays(
            '初級', 'guide2', 's2c3', strategy_markdown,
        )
        strategy_twice = publication_overlays.apply_publication_markdown_overlays(
            '初級', 'guide2', 's2c3', strategy_once,
        )
        self.assertEqual(strategy_once, strategy_twice)
        self.assertNotIn(old_strategy, strategy_once)
        self.assertIn(f'#### {strategy["title"]}', strategy_once)

        strategy_headings = [{'id': 'old', 'level': 4, 'title': old_strategy}]
        strategy_headings_once = publication_overlays.apply_publication_heading_overlays(
            '初級', 'guide2', 's2c3', strategy_headings,
        )
        strategy_headings_twice = publication_overlays.apply_publication_heading_overlays(
            '初級', 'guide2', 's2c3', strategy_headings_once,
        )
        self.assertEqual(strategy_headings_once, strategy_headings_twice)
        self.assertEqual(strategy_headings_once[0]['title'], strategy['title'])
        self.assertEqual(strategy_headings_once[0]['id'], strategy['anchor'])

        strategy_blocks = [{
            'type': 'heading', 'depth': 4, 'title': old_strategy,
            'anchor': 'old', 'pageIndex': 37,
        }]
        strategy_blocks_once = publication_overlays.apply_publication_block_overlays(
            '初級', 'guide2', 's2c3', strategy_blocks,
        )
        strategy_blocks_twice = publication_overlays.apply_publication_block_overlays(
            '初級', 'guide2', 's2c3', strategy_blocks_once,
        )
        self.assertEqual(strategy_blocks_once, strategy_blocks_twice)
        self.assertEqual(strategy_blocks_once[0]['title'], strategy['title'])
        self.assertEqual(strategy_blocks_once[0]['anchor'], strategy['anchor'])

        s1c4_source = ''.join(f'#### {title}\n' for title in publication_overlays.DEMOTE_HEADINGS)
        s1c4_once = publication_overlays.apply_publication_markdown_overlays(
            '初級', 'guide1', 's1c4', s1c4_source,
        )
        s1c4_twice = publication_overlays.apply_publication_markdown_overlays(
            '初級', 'guide1', 's1c4', s1c4_once,
        )
        self.assertEqual(s1c4_once, s1c4_twice)

        headings = [
            *({'title': title, 'level': 3} for title in publication_overlays.DEMOTE_HEADINGS),
            *({'title': title, 'level': 4} for title in publication_overlays.SHORTEN_HEADINGS),
        ]
        headings_once = publication_overlays.apply_publication_heading_overlays(
            '初級', 'guide1', 's1c4', headings,
        )
        headings_twice = publication_overlays.apply_publication_heading_overlays(
            '初級', 'guide1', 's1c4', headings_once,
        )
        self.assertEqual(headings_once, headings_twice)

    def test_publication_block_overlays_fail_closed_on_source_drift(self) -> None:
        with self.assertRaisesRegex(ValueError, 'hypothesis navigation source matched'):
            publication_overlays.apply_publication_block_overlays(
                '初級', 'guide1', 's1c2', [],
            )

        strategy = publication_overlays.GUIDE_NAVIGATION_HEADINGS[
            'manual-heading:s2c3-import-strategy'
        ]
        duplicate = {
            'type': 'heading', 'depth': strategy['depth'], 'title': strategy['title'],
            'anchor': strategy['anchor'], 'pageIndex': strategy['pageIndex'],
        }
        with self.assertRaisesRegex(ValueError, 'import-strategy heading matched 2'):
            publication_overlays.apply_publication_block_overlays(
                '初級', 'guide2', 's2c3', [duplicate, copy.deepcopy(duplicate)],
            )

    def test_publication_structure_drift_fails_cache_free_release_gate(self) -> None:
        mutations = {
            'manual-heading:s1c2-hypothesis': (
                'frontend/src/generated/guideContent/初級-guide1/s1c2.json',
                lambda payload: payload.update({
                    'content': payload['content'].replace(
                        '\n### 假說檢定名詞介紹：\n', '\n假說檢定名詞介紹：\n', 1,
                    ),
                    'headings': [
                        heading for heading in payload['headings']
                        if heading.get('title') != '假說檢定名詞介紹：'
                    ],
                }),
            ),
            'manual-heading:s1c4-hierarchy': (
                'frontend/src/generated/guideContent/初級-guide1/s1c4.json',
                lambda payload: payload.update({
                    'content': payload['content'].replace(
                        f'### {publication_overlays.DEMOTE_HEADINGS[0]}\n',
                        f'#### {publication_overlays.DEMOTE_HEADINGS[0]}\n',
                        1,
                    ),
                }),
            ),
            'manual-heading:s2c3-import-strategy': (
                'frontend/src/generated/guideContent/初級-guide2/s2c3.json',
                lambda payload: payload.update({
                    'content': payload['content'].replace(
                        '\n#### （3） 導入策略與階段規劃\n',
                        '\n#### （3）企業導入階段性實施策略企業需採取\n',
                        1,
                    ),
                }),
            ),
        }
        for failure_name, (relative_path, mutate) in mutations.items():
            with self.subTest(failure_name=failure_name), tempfile.TemporaryDirectory() as directory:
                root = self.make_cache_free_tree(Path(directory))
                path = root / relative_path
                payload = json.loads(path.read_text(encoding='utf-8'))
                mutate(payload)
                path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
                result = audit_generated_track_a(root)
            self.assertIn(failure_name, result['publication_structure_failures'])

    def test_guide_navigation_drift_fails_cache_free_release_gate(self) -> None:
        cases = (
            ('manual-heading:s1c2-hypothesis', 'guideHierarchy.json', 'page'),
            ('manual-heading:s1c2-hypothesis', 'guideSearchIndex.json', 'a'),
            ('manual-heading:s2c3-import-strategy', 'guideHierarchy.json', 'title'),
            ('manual-heading:s2c3-import-strategy', 'guideSearchIndex.json', 't'),
        )
        for contract_name, filename, field in cases:
            contract = publication_overlays.GUIDE_NAVIGATION_HEADINGS[contract_name]
            with self.subTest(contract_name=contract_name, filename=filename), \
                    tempfile.TemporaryDirectory() as directory:
                root = self.make_cache_free_tree(Path(directory))
                path = root / 'frontend/src/generated' / filename
                payload = json.loads(path.read_text(encoding='utf-8'))
                guide = payload['guides'][contract['subjectId']]
                expected_id = f'{contract["node"]}#{contract["anchor"]}'
                if filename == 'guideHierarchy.json':
                    target = guide['nodesById'][expected_id]
                else:
                    target = next(node for node in guide['nodes'] if node['id'] == expected_id)
                target[field] = 'drifted' if field != 'page' else contract['hierarchyPage'] + 1
                path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
                result = audit_generated_track_a(root)
            self.assertIn(contract_name, result['publication_structure_failures'])


if __name__ == '__main__':
    unittest.main()
