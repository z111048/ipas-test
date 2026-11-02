#!/usr/bin/env python3
"""Regression tests for the 2026-11-01 OCR-merged guide rebuild fixes.

Cache-free: every fixture is inline, so these run on a fresh checkout.

* s1c2 hypothesis overlay for the OCR source shape (title paragraph + 名稱｜說明
  table continued on the next page with a nested Type I/II sub-table), and the
  same table repair on the aggregate PDF-chapter node s1pdf-c3.
* recover_header_row() must not replace an OCR table's printed header.
* Body lines sticking out of an OCR table bbox are kept (caption/lead-in above,
  first paragraph line below); lines inside the table are still filtered.
* TA-128: a list item wrapped onto the next page with the same marker/depth.
* TA-106..108: audited tables are located by provenance, not by block id.
* TA-048..050: natively present headings still carry their inventory identity.
* Exporter --defer-track-a-review never defers overlay/structure contracts.
* Type-I/II checks compare JSON-escaped fragments (``$ \\alpha $``).

Finalize (2026-11-01 review findings):
* merge_guide_ocr keeps ``\\ne``/``\\neq`` inside ``$…$`` (it published
  ``$ \\mu⏎eq \\mu_{0} $``); cell breaks outside math still convert.
* TABLE_CELL_REPAIRS (en dash / ＋ / full-width gloss parentheses / H₀ /
  分佈 / L23 fill-down) fail closed and are present in the live content.
* Signed TA-109..152 window merges are mirrored on the aggregate PDF-chapter
  routes; CONTINUATION_MERGES covers the reviewed 「責／任」 split.
* The s2c3 import-strategy heading overlay hands 「企業需採取」 back.
* Live published content keeps every finalize fix (release gate).

Round 2 (2026-11-02 content repair): TA-048 printed title, numbered section
headings restored from page images, aggregate s1pdf-c3/s2pdf-c3 composed from
their children, same-page continuation merges, scoped text repair, PDPA list
split, parenthesis spacing (see Round2ContentRepairTests).
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import export_guide_outline_data as exporter  # noqa: E402
import merge_guide_ocr  # noqa: E402
import guide_publication_overlays as overlays  # noqa: E402
import track_a_ocr_repairs as track_a  # noqa: E402


TITLE = '假說檢定名詞介紹：'


def hypothesis_source_blocks() -> list[dict]:
    """The guide-tree shape produced from the OCR-merged page_extract."""
    return [
        {'id': 'block-19', 'type': 'table', 'pageIndex': 31, 'bbox': [73, 197, 523, 417],
         'rows': [['', '類別變數', '連續變數'], ['無因果關係', '• 敘述性統計', '• 主成份分析']]},
        {'id': 'block-20', 'type': 'paragraph', 'kind': 'paragraph', 'text': TITLE,
         'pageIndex': 31, 'bbox': [101.8, 421.61, 218.23, 434.9]},
        {'id': 'block-21', 'type': 'table', 'pageIndex': 31, 'sourcePageIndexes': [31],
         'bbox': [72.97, 426.26, 523.47, 778.76],
         'rows': [['名稱', '說明'],
                  ['假說檢定之流程', '猜想（假定）→蒐集資料→檢定作決策（接受或拒絕猜想）'],
                  ['假設檢定\n( testing hypothesis )', '基於母體之一組隨機樣本 X，以決定兩個假設中何者該拒絕。']]},
        {'id': 'block-22', 'type': 'table', 'pageIndex': 32, 'sourcePageIndexes': [32],
         'bbox': [72.94, 86.83, 523.44, 525.83],
         'rows': [['名稱', '說明', '', ''],
                  ['接受域\n(acceptance region)', '• 接受域：使虛無假設被接受之集合。', '', ''],
                  ['檢定 (test)', '• 決定一檢定，即表決定拒絕域及接受域。\n• 統計檢定之可能結果：', '', ''],
                  ['檢定 (test)', '$ H_0 $為真', '$ H_0 $為假', ''],
                  ['檢定 (test)', '接受 $ H_0 $', '正確', 'Type II 錯誤 ( $ \\beta $)'],
                  ['檢定 (test)', '拒絕 $ H_0 $', 'Type I 錯誤 ( $ \\alpha $)', '正確'],
                  ['檢定 (test)', '$ \\alpha=P $ (拒絕 $ H_0 $ | $ H_0 $為真)', '', ''],
                  ['顯著水準\n(significance level)', '• $ \\alpha $ 稱為顯著水準。', '', ''],
                  ['p 值\n(p-value)', '• p 值又稱觀測大小。', '', '']]},
        {'id': 'block-23', 'type': 'table', 'pageIndex': 32, 'sourcePageIndexes': [32],
         'bbox': [193.41, 233.0, 523.41, 341.0],
         'rows': [['', 'H 為真\n0', 'H 為假\n0'], ['接受 H\n0', '正確', 'Type II 錯誤（β）'],
                  ['拒絕 H\n0', 'Type II 錯誤（α）', '正確']]},
        {'id': 'block-24', 'type': 'list_item', 'pageIndex': 32, 'text': '探索式資料分析…'},
    ]


class HypothesisOverlayTests(unittest.TestCase):
    def test_ocr_shape_promotes_title_and_publishes_one_table_plus_subtable(self) -> None:
        once = overlays.apply_publication_block_overlays('初級', 'guide1', 's1c2', hypothesis_source_blocks())
        twice = overlays.apply_publication_block_overlays('初級', 'guide1', 's1c2', copy.deepcopy(once))
        self.assertEqual(once, twice)
        types = [block['type'] for block in once]
        self.assertEqual(types, ['table', 'heading', 'table', 'table', 'list_item'])
        heading, merged, sub = once[1], once[2], once[3]
        contract = overlays.GUIDE_NAVIGATION_HEADINGS['manual-heading:s1c2-hypothesis']
        self.assertEqual(heading['title'], TITLE)
        self.assertNotIn('text', heading)
        self.assertEqual(heading['anchor'], contract['anchor'])
        self.assertEqual(heading['publicationOverlayId'], 'manual-heading:s1c2-hypothesis')
        # One 2-column table spanning both pages, header kept once, 檢定 once.
        self.assertEqual(merged['sourcePageIndexes'], [31, 32])
        self.assertTrue(all(len(row) == 2 for row in merged['rows']))
        self.assertEqual(merged['rows'][0], ['名稱', '說明'])
        firsts = [row[0] for row in merged['rows']]
        self.assertEqual(firsts.count('檢定 (test)'), 1)
        self.assertEqual(firsts.count('名稱'), 1)
        self.assertLess(firsts.index('檢定 (test)'), firsts.index('顯著水準\n(significance level)'))
        test_cell = merged['rows'][firsts.index('檢定 (test)')][1]
        self.assertIn('統計檢定之可能結果', test_cell)
        self.assertIn('alpha=P', test_cell)
        # The PDF-text duplicate (pre-errata Type II α) is gone; the OCR
        # sub-table with its restored empty corner cell remains once.
        serialized = json.dumps(once, ensure_ascii=False)
        self.assertNotIn('Type II 錯誤（α）', serialized)
        self.assertEqual(sub['rows'][0], ['', '$ H_0 $為真', '$ H_0 $為假'])
        self.assertEqual(sub['rows'][2], ['拒絕 $ H_0 $', 'Type I 錯誤 ( $ \\alpha $)', '正確'])

    def test_aggregate_chapter_repairs_table_and_mirrors_title_heading(self) -> None:
        result = overlays.apply_publication_block_overlays('初級', 'guide1', 's1pdf-c3', hypothesis_source_blocks())
        self.assertEqual([block['type'] for block in result], ['table', 'heading', 'table', 'table', 'list_item'])
        mirror = result[1]
        contract = overlays.GUIDE_NAVIGATION_HEADINGS['manual-heading:s1c2-hypothesis']
        self.assertEqual(mirror['title'], TITLE)
        self.assertNotIn('text', mirror)
        self.assertEqual(mirror['anchor'], contract['anchor'])
        self.assertEqual(mirror['depth'], contract['depth'])
        self.assertEqual(mirror['publicationMirrorOverlayId'], 'manual-heading:s1c2-hypothesis')
        # s1c2 alone owns the navigation contract.
        self.assertNotIn('publicationOverlayId', mirror)
        self.assertEqual(result[2]['sourcePageIndexes'], [31, 32])
        self.assertEqual(
            result, overlays.apply_publication_block_overlays('初級', 'guide1', 's1pdf-c3', copy.deepcopy(result)),
        )

    def test_ocr_shape_fails_closed_on_drift(self) -> None:
        drifted = hypothesis_source_blocks()
        drifted[4]['bbox'] = [10, 10, 20, 20]  # sub-table no longer inside its parent
        with self.assertRaisesRegex(ValueError, 'no longer inside'):
            overlays.apply_publication_block_overlays('初級', 'guide1', 's1c2', drifted)
        drifted = hypothesis_source_blocks()
        del drifted[3]['rows'][5]  # rowspan shape changed
        with self.assertRaisesRegex(ValueError, 'rowspan shape changed'):
            overlays.apply_publication_block_overlays('初級', 'guide1', 's1c2', drifted)
        drifted = hypothesis_source_blocks()
        drifted[3]['rows'][5][2] = 'Type II 錯誤 ( $ \\alpha $)'  # errata not applied
        with self.assertRaisesRegex(ValueError, 'sub-table cells changed'):
            overlays.apply_publication_block_overlays('初級', 'guide1', 's1c2', drifted)
        drifted = hypothesis_source_blocks()
        drifted.insert(2, dict(drifted[1]))  # duplicated title
        with self.assertRaisesRegex(ValueError, 'hypothesis navigation source matched'):
            overlays.apply_publication_block_overlays('初級', 'guide1', 's1c2', drifted)


    def test_markdown_tables_mirror_block_overlay(self) -> None:
        source = hypothesis_source_blocks()
        final = overlays.apply_publication_block_overlays('初級', 'guide1', 's1c2', copy.deepcopy(source))
        html = exporter.table_rows_to_html
        markdown = '\n\n'.join([
            '### ' + TITLE,
            html(source[2]['rows']), html(source[3]['rows']), html(source[4]['rows']),
            '• 探索式資料分析',
        ])
        once = exporter.sync_hypothesis_markdown_tables('初級', 'guide1', 's1c2', markdown, final)
        self.assertEqual(once, exporter.sync_hypothesis_markdown_tables('初級', 'guide1', 's1c2', once, final))
        self.assertEqual(once.count('<table'), 2)
        self.assertIn(html(final[2]['rows']), once)
        self.assertIn(html(final[3]['rows']), once)
        self.assertNotIn('Type II 錯誤（α）', once)
        self.assertTrue(once.endswith('• 探索式資料分析'))
        broken = markdown.replace(html(source[4]['rows']), '')
        with self.assertRaisesRegex(ValueError, 'Markdown table'):
            exporter.sync_hypothesis_markdown_tables('初級', 'guide1', 's1c2', broken, final)


class TableExtractionTests(unittest.TestCase):
    def test_ocr_table_header_is_never_replaced_by_text_layer(self) -> None:
        table = {'rows_source': 'guide_ocr', 'bbox': [72.94, 86.83, 523.44, 525.83],
                 'rows': [['名稱', '說明', '', ''], ['接受域', 'x', '', '']]}
        blocks = [{'text': '接受域', 'bbox': [100, 100, 150, 112]}]
        self.assertIsNone(exporter.recover_header_row(table, blocks))
        pdf_table = dict(table)
        pdf_table.pop('rows_source')
        self.assertEqual(exporter.recover_header_row(pdf_table, blocks)[0], '接受域')

    def test_body_lines_outside_ocr_table_bbox_are_kept(self) -> None:
        table = {'rows_source': 'guide_ocr', 'bbox': [73, 197, 523, 417],
                 'rows': [['', '類別變數', '連續變數'], ['無因果關係', '敘述性統計', '主成份分析']]}
        caption = {'text': '常見的統計方法可做以下分類：', 'bbox': [101.8, 192.14, 281.23, 205.43]}
        below = {'text': '舉例來說，若要檢驗某食品的平均含鈉量', 'bbox': [115.8, 410.0, 518.3, 422.0]}
        inside = {'text': '敘述性統計', 'bbox': [200, 250, 260, 262]}
        edge_cell = {'text': '類別變數', 'bbox': [250, 192, 300, 205]}
        for block in (caption, below, inside, edge_cell):
            self.assertTrue(exporter.block_overlaps_table(block, table['bbox']))
        self.assertTrue(exporter.is_line_outside_ocr_table(caption, table))
        self.assertTrue(exporter.is_line_outside_ocr_table(below, table))
        self.assertFalse(exporter.is_line_outside_ocr_table(inside, table))
        self.assertFalse(exporter.is_line_outside_ocr_table(edge_cell, table))  # text is in the cells
        pdf_table = {key: value for key, value in table.items() if key != 'rows_source'}
        self.assertFalse(exporter.is_line_outside_ocr_table(caption, pdf_table))


def _sig(block_type: str, content: str) -> str:
    payload = json.dumps({'type': block_type, 'content': content}, ensure_ascii=False,
                         sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()


class TrackARebuildTests(unittest.TestCase):
    def test_same_marker_list_item_wrap_matches_signed_window(self) -> None:
        first = {'id': 'block-409', 'type': 'list_item', 'depth': 9, 'marker': '-', 'pageIndex': 44,
                 'text': '「法國的首都在柏', 'kind': 'list_item', 'nodeId': 'n', 'source': 'page_extract',
                 'bbox': [0, 0, 1, 1]}
        wrap = dict(first, id='block-410', pageIndex=45, text='林」，這就是模型幻覺的例子。')
        nxt = dict(first, id='block-411', pageIndex=45, text='在智慧客服系統中…')
        digest = _sig('list_item', '「法國的首都在柏林」，這就是模型幻覺的例子。')
        found = track_a._off_by_one_signature_candidates([first, wrap, nxt], expected_digest=digest, expected_page=45)
        self.assertEqual([(c['kind'], c['start'], c['end']) for c in found], [('window', 0, 1)])
        other_marker = dict(wrap, marker='•')
        self.assertEqual(
            track_a._off_by_one_signature_candidates([first, other_marker, nxt], expected_digest=digest, expected_page=45),
            [],
        )
        deeper = dict(wrap, depth=10)
        self.assertEqual(
            track_a._off_by_one_signature_candidates([first, deeper, nxt], expected_digest=digest, expected_page=45),
            [],
        )

    def test_table_provenance_is_located_by_pages_not_historical_id(self) -> None:
        blocks = [
            {'id': 'block-95', 'type': 'paragraph', 'text': '當完成分詞…', 'pageIndex': 18},
            {'id': 'block-99', 'type': 'table', 'rows': [['a']], 'pageIndex': 18, 'sourcePageIndexes': [18, 19]},
        ]
        with mock.patch.object(track_a, 'OFF_BY_ONE_REPAIRS', []):
            repaired = track_a.apply_track_a_block_repairs('中級', 'guide1', 'mid-s1c1', blocks)
        self.assertNotIn('trackARepairId', repaired[0])
        self.assertEqual(repaired[1]['trackARepairId'], 'TA-107')
        self.assertEqual(repaired[1]['trackAOriginalBlockId'], 'block-95')
        ambiguous = blocks + [dict(blocks[1], id='block-100')]
        with mock.patch.object(track_a, 'OFF_BY_ONE_REPAIRS', []), \
                self.assertRaisesRegex(ValueError, 'TA-107 merged table provenance'):
            track_a.apply_track_a_block_repairs('中級', 'guide1', 'mid-s1c1', ambiguous)

    def test_native_heading_keeps_inventory_identity(self) -> None:
        blocks = [
            {'id': 'block-6', 'type': 'paragraph', 'text': '…', 'pageIndex': 39},
            {'id': 'block-7', 'type': 'heading', 'depth': 3, 'title': '1. 機器學習基本理論', 'pageIndex': 39},
            {'id': 'block-8', 'type': 'heading', 'depth': 4, 'title': '（1）基本原理', 'pageIndex': 39},
        ]
        with mock.patch.object(track_a, 'OFF_BY_ONE_REPAIRS', []), \
                mock.patch.object(track_a, 'CONTINUATION_MERGES', []):
            repaired = track_a.apply_track_a_block_repairs('初級', 'guide1', 's1c3', blocks)
        headings = [block for block in repaired if block.get('title') == '1. 機器學習基本理論']
        self.assertEqual(len(headings), 1)  # no second, inserted heading
        self.assertEqual(headings[0]['trackARepairId'], 'TA-049')
        self.assertEqual(headings[0]['trackAOriginalBlockId'], 'block-7')
        self.assertEqual(headings[0]['sourcePageIndexes'], [39])

    def test_type_i_checks_compare_json_escaped_latex(self) -> None:
        good = [{'type': 'table', 'pageIndex': 32, 'rows': [['拒絕', 'Type I 錯誤 ( $ \\alpha $)']]}]
        # Accepted in its LaTeX serialization (previously never matched).
        track_a.apply_text_repairs('初級', 'guide1', copy.deepcopy(good), node='s1c2', strict=True)
        bad = json.dumps([{'rows': [['Type II 錯誤 ( $ \\alpha $)']]}], ensure_ascii=False)
        self.assertNotIn('Type II 錯誤 ( $ \\alpha $)', bad)  # the old raw check was blind
        self.assertIn(track_a._json_fragment('Type II 錯誤 ( $ \\alpha $)'), bad)


class DeferredReviewTests(unittest.TestCase):
    def test_only_named_inventory_items_can_be_deferred(self) -> None:
        semantic = {
            'failures': ['TA-106: table mismatch', 'TA-107: table mismatch'],
            'publication_overlay_failures': [],
            'publication_structure_failures': [],
        }
        deferred = frozenset({'TA-106', 'TA-107'})
        self.assertEqual(exporter._undeferred_track_a_failures(semantic, deferred), [])
        self.assertEqual(
            exporter._undeferred_track_a_failures(semantic, frozenset({'TA-106'})),
            ['TA-107: table mismatch'],
        )
        semantic['publication_structure_failures'] = ['manual-heading:s1c2-hypothesis']
        self.assertEqual(
            exporter._undeferred_track_a_failures(semantic, deferred),
            ['manual-heading:s1c2-hypothesis'],
        )


class FinalizeReviewTests(unittest.TestCase):
    CONTENT = ROOT / 'frontend/src/generated/guideContent'

    def _blocks(self, guide: str, node: str) -> list[dict]:
        return json.loads((self.CONTENT / guide / f'{node}.json').read_text(encoding='utf-8'))['blocks']

    def test_ocr_cell_newlines_keep_latex_ne_commands(self) -> None:
        html = ('<table><tr><td>雙尾檢定</td><td>$ \\mu\\neq \\mu_{0} $</td>'
                '<td>規則式方法\\n( Rule-based )</td><td>$ \\mu d\\ne 0 $</td></tr></table>')
        rows = merge_guide_ocr.parse_table_html(html)
        self.assertEqual(rows[0][1], '$ \\mu\\neq \\mu_{0} $')
        self.assertNotIn('\n', rows[0][1])
        self.assertNotIn('\n', rows[0][3])
        self.assertIn('\\ne 0', rows[0][3])
        self.assertEqual(rows[0][2], '規則式方法\n( Rule-based )')

    def test_table_cell_repairs_apply_and_fail_closed(self) -> None:
        table = {'type': 'table', 'pageIndex': 32, 'sourcePageIndexes': [32],
                 'rows': [['項目', '虛無假設（ $ H_o $）'], ['功能', '若 $ H_o $ 被拒絕']]}
        other = {'type': 'table', 'pageIndex': 36, 'sourcePageIndexes': [36],
                 'rows': [['情境', '虛無假設（ $ H_o $）']]}
        repaired = track_a.apply_table_cell_repairs(
            '中級', 'guide2', 'mid-s2c3', [copy.deepcopy(table), copy.deepcopy(other)])
        self.assertNotIn('H_o', json.dumps(repaired, ensure_ascii=False))
        self.assertEqual(repaired[0]['rows'][1][1], '若 $ H_0 $ 被拒絕')
        # idempotent on already repaired rows
        self.assertEqual(track_a.apply_table_cell_repairs('中級', 'guide2', 'mid-s2c3', repaired), repaired)
        drifted = dict(table, rows=[['項目', '虛無假設']])
        with self.assertRaisesRegex(ValueError, 'table-cell repair source'):
            track_a.apply_table_cell_repairs('中級', 'guide2', 'mid-s2c3', [drifted, copy.deepcopy(other)])
        with self.assertRaisesRegex(ValueError, 'has no table'):
            track_a.apply_table_cell_repairs('中級', 'guide2', 'mid-s2c3', [])

    def test_fill_down_restores_page_break_merged_cell(self) -> None:
        rows = [['科目', '評鑑主題', '評鑑內容'],
                ['L22', 'L221', 'L22102 機率分布與資料分佈模型'],
                ['L23', 'L232', 'L23203 深度學習原理與框架'],
                ['', 'L233', 'L23301 數據準備與特徵工程']]
        table = {'type': 'table', 'pageIndex': 4, 'sourcePageIndexes': [4, 5], 'rows': rows}
        repaired = track_a.apply_table_cell_repairs('中級', 'guide2', 'mid-s2pdf-c1', [table])
        self.assertEqual(repaired[0]['rows'][3][0], 'L23')
        self.assertEqual(repaired[0]['rows'][1][2], 'L22102 機率分佈與資料分佈模型')

    def test_continuation_merge_joins_reviewed_split_only(self) -> None:
        head = {'id': 'block-136', 'type': 'paragraph', 'pageIndex': 131,
                'text': '企業應…這不僅僅是對於資料準確性或技術有效性的責'}
        tail = {'id': 'block-137', 'type': 'paragraph', 'pageIndex': 132,
                'text': '任，還包括對模型在決策過程中對使用者、社會及環境造成的任何負面影響的責任。'}
        merged = track_a.apply_continuation_merges('中級', 'guide1', 'mid-s1c7', [head, tail])
        self.assertEqual(len(merged), 1)
        self.assertIn('有效性的責任，還包括', merged[0]['text'])
        self.assertEqual((merged[0]['pageIndex'], merged[0]['sourcePageIndexes']), (132, [131, 132]))
        self.assertEqual(track_a.apply_continuation_merges('中級', 'guide1', 'mid-s1c7', merged), merged)
        with self.assertRaisesRegex(ValueError, 'continuation merge'):
            track_a.apply_continuation_merges('中級', 'guide1', 'mid-s1c7', [head])

    def test_signed_window_is_mirrored_on_other_routes(self) -> None:
        first = {'id': 'block-1', 'type': 'paragraph', 'pageIndex': 44, 'text': '前半句「法國的首都在柏',
                 'kind': 'paragraph', 'nodeId': 'n', 'source': 'page_extract', 'bbox': [0, 0, 1, 1]}
        wrap = dict(first, id='block-2', pageIndex=45, text='林」。')
        digest = _sig('paragraph', '前半句「法國的首都在柏林」。')
        repair = {'id': 'TA-900', 'level': '中級', 'key': 'guide1', 'node': 'mid-s1c1', 'block': 'block-1', 'page': 45}
        signatures = {'TA-900': {'blockSignatureSha256': digest, 'pageIndex': 45, 'sourcePageIndexes': [44, 45]}}
        with mock.patch.object(track_a, 'OFF_BY_ONE_REPAIRS', [repair]), \
                mock.patch.object(track_a, '_off_by_one_signatures', return_value=signatures), \
                mock.patch.object(track_a, 'CONTINUATION_MERGES', []), \
                mock.patch.object(track_a, 'BLOCK_TEXT_REPAIRS', []):
            mirrored = track_a.apply_track_a_block_repairs('中級', 'guide1', 'mid-s1pdf-c3', [first, wrap])
            untouched = track_a.apply_track_a_block_repairs('中級', 'guide1', 'mid-s1pdf-c3', [dict(first)])
        self.assertEqual(len(mirrored), 1)
        self.assertEqual(mirrored[0]['trackAMirrorRepairId'], 'TA-900')
        self.assertNotIn('trackARepairId', mirrored[0])
        self.assertEqual(mirrored[0]['sourcePageIndexes'], [44, 45])
        self.assertEqual(len(untouched), 1)  # no match: route left as is

    def test_import_strategy_overlay_returns_spilled_words(self) -> None:
        blocks = [
            {'id': 'block-1', 'type': 'heading', 'depth': 4, 'pageIndex': 37,
             'title': '（3）企業導入階段性實施策略企業需採取'},
            {'id': 'block-2', 'type': 'paragraph', 'pageIndex': 37, 'text': '分階段策略，平衡短期效益與長期發展：'},
        ]
        result = overlays.apply_publication_block_overlays('初級', 'guide2', 's2c3', blocks)
        self.assertEqual(result[0]['title'], '（3）企業導入階段性實施策略')
        self.assertEqual(result[1]['text'], '企業需採取分階段策略，平衡短期效益與長期發展：')

    def test_import_strategy_markdown_follows_errata_on_owner_and_aggregate(self) -> None:
        # Page 3-32 heading per official errata (2026-11-02 user decision);
        # Markdown and sidebar headings of s2c3 and the aggregate s2pdf-c3
        # both get it, and 「企業需採取」 goes back to the paragraph.
        source = ('# 章\n\n#### （3）企業導入階段性實施策略企業需採取\n\n'
                  '分階段策略，平衡短期效益與長期發展：\n\n• 試點應用')
        for node in ('s2c3', 's2pdf-c3'):
            once = overlays.apply_publication_markdown_overlays('初級', 'guide2', node, source)
            twice = overlays.apply_publication_markdown_overlays('初級', 'guide2', node, once)
            self.assertEqual(once, twice, node)
            self.assertIn('\n#### （3）企業導入階段性實施策略\n\n企業需採取分階段策略，', once, node)
            headings = overlays.apply_publication_heading_overlays(
                '初級', 'guide2', node,
                [{'id': 'x', 'level': 4, 'title': '（3）企業導入階段性實施策略企業需採取'}],
            )
            self.assertEqual(headings, [{'id': '3企業導入階段性實施策略', 'level': 4,
                                         'title': '（3）企業導入階段性實施策略'}], node)
        with self.assertRaisesRegex(ValueError, 'spill'):
            overlays.apply_publication_markdown_overlays(
                '初級', 'guide2', 's2c3', '#### （3）企業導入階段性實施策略企業需採取\n\n• 試點應用',
            )

    def test_live_content_keeps_finalize_fixes(self) -> None:
        def serialized(guide: str, node: str) -> str:
            return json.dumps(self._blocks(guide, node), ensure_ascii=False)
        for node in ('mid-s2c3', 'mid-s2pdf-c3'):
            text = serialized('中級-guide2', node)
            self.assertNotIn('H_o', text, node)
            self.assertNotIn('eq \\\\mu', text.replace('\\\\neq \\\\mu', ''), node)
        for repair in track_a.TABLE_CELL_REPAIRS:
            for node in repair['nodes']:
                text = json.dumps([b.get('rows') for b in self._blocks(f"{repair['level']}-{repair['key']}", node)
                                   if b.get('type') == 'table'], ensure_ascii=False)
                for old, new in repair['replacements']:
                    self.assertIn(json.dumps(new, ensure_ascii=False)[1:-1], text, (node, new))
        for guide, node in (('中級-guide1', 'mid-s1c7'), ('中級-guide1', 'mid-s1pdf-c4')):
            self.assertIn('技術有效性的責任，還包括', serialized(guide, node))
        self.assertIn('首都在柏林', serialized('中級-guide1', 'mid-s1pdf-c3'))
        s2c3 = self._blocks('初級-guide2', 's2c3')
        self.assertTrue(any(b.get('text', '').startswith('企業需採取分階段策略') for b in s2c3))
        s1c2 = serialized('初級-guide1', 's1c2')
        self.assertIn('（拒絕 $ H_0 $ | $ H_0 $為真）', s1c2)
        self.assertIn('Type I 錯誤（$ \\\\alpha $）', s1c2)
        self.assertIn('以 T=T（X）表之', s1c2)
        self.assertIn('檢定（test）', s1c2)


class Round2ContentRepairTests(unittest.TestCase):
    """2026-11-02 content-repair round (each item checked on page images)."""

    @staticmethod
    def _live(guide: str, node: str) -> list[dict]:
        path = ROOT / 'frontend/src/generated/guideContent' / guide / f'{node}.json'
        return json.loads(path.read_text(encoding='utf-8'))['blocks']

    def test_same_page_continuation_merge_is_exact_and_idempotent(self) -> None:
        head = {'id': 'block-1', 'type': 'paragraph', 'depth': 6, 'pageIndex': 55,
                'text': '是一種強大的分類模型，其核心'}
        tail = {'id': 'block-2', 'type': 'paragraph', 'depth': 5, 'pageIndex': 55,
                'text': '思想在於尋找一個能夠最大化類別間隔的超平面，從而達到最優的分類效果。'}
        merges = [entry for entry in track_a.CONTINUATION_MERGES
                  if entry['head'] == '是一種強大的分類模型，其核心']
        with mock.patch.object(track_a, 'CONTINUATION_MERGES', merges):
            merged = track_a.apply_continuation_merges('初級', 'guide1', 's1c4', [head, tail])
            self.assertEqual(len(merged), 1)
            self.assertEqual(merged[0]['text'], head['text'] + tail['text'])
            self.assertEqual((merged[0]['depth'], merged[0]['pageIndex']), (6, 55))
            self.assertEqual(merged[0]['sourcePageIndexes'], [55])
            self.assertEqual(track_a.apply_continuation_merges('初級', 'guide1', 's1pdf-c3', merged), merged)
            moved = dict(tail, pageIndex=56)  # a different page is a different shape
            with self.assertRaisesRegex(ValueError, 'continuation merge'):
                track_a.apply_continuation_merges('初級', 'guide1', 's1c4', [head, moved])

    def test_block_text_repair_fails_closed(self) -> None:
        block = {'type': 'list_item', 'pageIndex': 52, 'text': '支援「雙重標註 」，即由兩位標註者'}
        repaired = track_a.apply_block_text_repairs('中級', 'guide1', 'mid-s1c2', [block])
        self.assertEqual(repaired[0]['text'], '支援「雙重標註」，即由兩位標註者')
        self.assertEqual(track_a.apply_block_text_repairs('中級', 'guide1', 'mid-s1c2', repaired), repaired)
        with self.assertRaisesRegex(ValueError, 'text repair source'):
            track_a.apply_block_text_repairs('中級', 'guide1', 'mid-s1pdf-c3', [dict(block, pageIndex=53)])

    def test_pdpa_list_split_matches_errata_structure(self) -> None:
        split = track_a.LIST_ITEM_SPLITS[0]
        joined = f"{split['lead']}◦ " + ' ◦ '.join(split['items']) + f" {split['closing']}"
        source = {'id': 'block-70', 'type': 'list_item', 'depth': 5, 'marker': '•', 'pageIndex': 127,
                  'text': joined, 'kind': 'list_item', 'nodeId': 'mid-s1c7', 'source': 'page_extract'}
        result = track_a.apply_list_item_splits('中級', 'guide1', 'mid-s1c7', [source])
        self.assertEqual([b['type'] for b in result], ['list_item'] * 7 + ['paragraph'])
        self.assertEqual([b.get('depth') for b in result], [5] + [6] * 7)
        self.assertEqual([b.get('marker') for b in result[1:7]], ['◦'] * 6)
        self.assertEqual(result[0]['text'], split['lead'])
        self.assertEqual(result[-1]['text'], split['closing'])
        self.assertEqual(track_a.apply_list_item_splits('中級', 'guide1', 'mid-s1c7', result), result)
        with self.assertRaisesRegex(ValueError, 'list split'):
            track_a.apply_list_item_splits('中級', 'guide1', 'mid-s1pdf-c4', [dict(source, text=joined + '。')])

    def test_section_marker_heading_returns_glyph_spill(self) -> None:
        blocks = [
            {'type': 'paragraph', 'depth': 7, 'text': '2.', 'pageIndex': 61},
            {'type': 'paragraph', 'depth': 7, 'text': 'AI AI 鑑別式AI 與生成式AI 是人工智慧技術的重要支柱。',
             'pageIndex': 61},
        ]
        result = exporter.post_process_guide_blocks('s1c4', '鑑別式AI 與生成式AI 概念', copy.deepcopy(blocks))
        self.assertEqual(result[0]['title'], '2. 鑑別式 AI 與生成式 AI 的整合應用')
        self.assertEqual(result[1]['text'], '鑑別式AI 與生成式AI 是人工智慧技術的重要支柱。')
        broken = copy.deepcopy(blocks)
        broken[1]['text'] = '鑑別式AI 與生成式AI 是人工智慧技術的重要支柱。'
        with self.assertRaisesRegex(ValueError, 'heading spill'):
            exporter.post_process_guide_blocks('s1c4', '鑑別式AI 與生成式AI 概念', broken)

    def test_aggregate_composition_requires_exact_tiling(self) -> None:
        import build_guide_tree
        child = lambda node_id, start, end: {'id': node_id, 'page_range': [start, end], 'children': []}
        node = {'id': 's1pdf-c3', 'page_range': [7, 12], 'children': [child('a', 7, 9), child('b', 10, 12)]}
        blocks = {'a': [{'id': 'block-1', 'type': 'paragraph', 'text': '甲'}],
                  'b': [{'id': 'block-1', 'type': 'heading', 'title': '乙'}]}
        composed = build_guide_tree.compose_aggregate_blocks('初級', node, blocks)
        self.assertEqual([b['id'] for b in composed], ['block-1', 'block-2'])
        self.assertEqual({b['nodeId'] for b in composed}, {'s1pdf-c3'})
        gap = dict(node, children=[child('a', 7, 9), child('b', 11, 12)])
        with self.assertRaisesRegex(ValueError, 'tiling'):
            build_guide_tree.compose_aggregate_blocks('初級', gap, blocks)
        short = dict(node, page_range=[7, 13])
        with self.assertRaisesRegex(ValueError, 'parent ends'):
            build_guide_tree.compose_aggregate_blocks('初級', short, blocks)

    def test_live_content_keeps_round2_repairs(self) -> None:
        s1c1 = self._live('初級-guide1', 's1c1')
        sections = [(b['title'], b['pageIndex']) for b in s1c1 if b['type'] == 'heading' and b.get('depth') == 3]
        self.assertEqual(sections[:7], [
            ('1. 人工智慧的應用領域', 6), ('2. 人工智慧的架構', 8), ('3. 資料處理與分析', 9),
            ('4. 演算法', 16), ('5. 機器學習', 17), ('6. 深度學習', 19), ('7. 生成式人工智慧', 22),
        ])
        for node, titles in (
            ('s1c3', ['2. 機器學習的類型', '3. 機器學習核心過程']),
            ('s1c4', ['2. 鑑別式 AI 與生成式 AI 的整合應用']),
        ):
            published = {b.get('title') for b in self._live('初級-guide1', node) if b['type'] == 'heading'}
            self.assertTrue(set(titles) <= published, node)
        for guide, aggregate, children in (
            ('初級-guide1', 's1pdf-c3', ['s1c1', 's1c2', 's1c3', 's1c4']),
            ('初級-guide2', 's2pdf-c3', ['s2c1', 's2c2', 's2c3']),
        ):
            blocks = self._live(guide, aggregate)
            self.assertFalse(
                [b['id'] for b in blocks if b['type'] in ('answer', 'question') and len(b.get('text') or '') > 1500],
                aggregate,
            )
            child_text = [b.get('text') for child in children for b in self._live(guide, child)
                          if b['type'] in ('paragraph', 'list_item')]
            # s1pdf-c3 prints the hypothesis title as a mirror heading (s1c2 owns the contract).
            own_text = [b.get('text') for b in blocks
                        if b['type'] in ('paragraph', 'list_item') and b.get('text') != '假說檢定名詞介紹：']
            self.assertEqual(own_text, child_text, aggregate)
            self.assertTrue(any(b['type'] == 'heading' and b['title'].startswith('3.2 ') for b in blocks), aggregate)
        serialized = json.dumps(self._live('初級-guide1', 's1c2'), ensure_ascii=False)
        self.assertIn('以 T=T（X）表之', serialized)
        self.assertNotIn('檢定 （test）', serialized)
        mid_s1c2 = json.dumps(self._live('中級-guide1', 'mid-s1c2'), ensure_ascii=False)
        self.assertIn('「雙重標註」，', mid_s1c2)
        self.assertIn('特徵擷取與比對。其流程包括：', mid_s1c2)
        for node in ('mid-s1c7', 'mid-s1pdf-c4'):
            items = [b for b in self._live('中級-guide1', node) if b.get('trackAListSplit')]
            self.assertEqual(len(items), 8, node)
        for node in ('mid-s1c5', 'mid-s1pdf-c4'):
            self.assertIn('系統整合的核心人才？', json.dumps(self._live('中級-guide1', node), ensure_ascii=False))


class Round3PageAndHeadingTests(unittest.TestCase):
    """Round 3 batch 2 (2026-11-02 user decisions)."""

    def test_frontend_shows_start_page_of_cross_page_blocks(self) -> None:
        # Cross-page merged blocks keep the later page as data pageIndex; the
        # frontend shows sourcePageIndexes[0].  Every page label must go
        # through utils/guideBlockPage.ts, never read pageIndex directly.
        helper = ROOT / 'frontend/src/utils/guideBlockPage.ts'
        self.assertIn('sourcePageIndexes?.[0]', helper.read_text(encoding='utf-8'))
        offenders = []
        for path in sorted((ROOT / 'frontend/src').rglob('*.ts*')):
            relative = path.relative_to(ROOT / 'frontend/src').as_posix()
            if relative.startswith('generated/') or path == helper:
                continue
            text = path.read_text(encoding='utf-8')
            if '.pageIndex' in text or "['pageIndex']" in text or '["pageIndex"]' in text:
                offenders.append(relative)
        self.assertEqual(offenders, [])
        # Data contract the helper relies on: a non-empty int list whose
        # first page is never after the data pageIndex.
        for path in sorted((ROOT / 'frontend/src/generated/guideContent').glob('*/*.json')):
            for block in json.loads(path.read_text(encoding='utf-8')).get('blocks') or []:
                pages = block.get('sourcePageIndexes')
                if pages is None:
                    continue
                where = f"{path.parent.name}/{path.stem}/{block.get('id')}"
                self.assertTrue(pages and all(isinstance(page, int) for page in pages), where)
                if isinstance(block.get('pageIndex'), int):
                    self.assertLessEqual(pages[0], block['pageIndex'], where)

    def test_live_page_3_32_heading_follows_errata(self) -> None:
        # Page image 初級/guide2/page_037 prints 「（3） 資源與基礎設施評估」; the
        # official errata (data/初級/errata_corrections.json) corrects it.
        errata = json.loads((ROOT / 'data/初級/errata_corrections.json').read_text(encoding='utf-8'))
        self.assertTrue(any(
            entry.get('key') == 'guide2' and entry.get('page_label') == '3-32'
            and str(entry.get('corrected') or '').startswith('（3）企業導入階段性實施策略企業需採取')
            for entry in errata
        ))
        title = '（3）企業導入階段性實施策略'
        for node in ('s2c3', 's2pdf-c3'):
            path = ROOT / f'frontend/src/generated/guideContent/初級-guide2/{node}.json'
            payload = json.loads(path.read_text(encoding='utf-8'))
            body = json.dumps({k: payload[k] for k in ('content', 'headings', 'blocks')}, ensure_ascii=False)
            self.assertNotIn('導入策略與階段規劃', body, node)
            self.assertNotIn('實施策略企業需採取', body, node)
            self.assertIn(f'#### {title}\n\n企業需採取分階段策略', payload['content'], node)
            self.assertEqual(
                [h for h in payload['headings'] if h['title'] == title],
                [{'id': '3企業導入階段性實施策略', 'level': 4, 'title': title}], node,
            )
        units = json.loads((ROOT / 'data/共用/image_units_all_levels.json').read_text(encoding='utf-8'))
        unit = next(u for u in units['units'] if u['id'] == 'guide2-s2c3-img-004')
        self.assertEqual(unit['title'], title)
        self.assertEqual(unit['headingPath'][-1], title)


if __name__ == '__main__':
    unittest.main()
