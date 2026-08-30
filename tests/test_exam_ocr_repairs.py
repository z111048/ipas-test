#!/usr/bin/env python3
"""Regression tests for production exam OCR repairs and Vision promotion gates."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from parse_exams_v2 import (  # noqa: E402
    parse_exam_json,
    parse_question_cell,
    parse_sample_json,
    save_mock,
)
import reconcile_exam_vision_sidecar as sidecar  # noqa: E402
import verify_question_answers as answer_verifier  # noqa: E402
from resource_catalog import exam_entries  # noqa: E402
from verify_exam_ocr_repairs import verify  # noqa: E402
from verify_exam_visual_reviews import verify as verify_visual_reviews  # noqa: E402
from verify_question_answers import (  # noqa: E402
    cache_matches_question,
    question_fingerprint,
)
from test_exam_reference_answer_cache import ExamReferenceAnswerCacheTests  # noqa: E402,F401
from test_annotate_exam_code_images import AnnotateExamCodeImagesTests  # noqa: E402, F401


class ExamOcrRepairTests(unittest.TestCase):
    def test_answer_verification_cache_is_bound_to_question_content(self) -> None:
        question = {
            'id': 'sample_q22',
            'question': '原題幹',
            'options': {key: f'選項 {key}' for key in 'ABCD'},
            'answer': 'C',
            'source': 'sample',
            'source_ref': {'page_index': 3, 'page_number': 4},
        }
        cached = {'question_fingerprint': question_fingerprint(question)}
        self.assertTrue(cache_matches_question(cached, question))

        shifted_question = {
            **question,
            'question': '補回跨頁題後，同一題號代表另一道題',
        }
        self.assertFalse(cache_matches_question(cached, shifted_question))

        shifted_page = {
            **question,
            'source_ref': {'page_index': 4, 'page_number': 5},
        }
        self.assertFalse(cache_matches_question(cached, shifted_page))
        shifted_source = {**question, 'source': 'another_exam'}
        self.assertFalse(cache_matches_question(cached, shifted_source))
        self.assertFalse(cache_matches_question({}, question))

    def test_answer_verification_cache_tracks_explicit_image_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = (
                root / 'frontend' / 'public' / 'pdf-assets' / '中級' / 'sample'
                / 'page_000' / 'image_01_01.png'
            )
            image.parent.mkdir(parents=True)
            image.write_bytes(b'first image bytes')
            question = {
                'id': 'sample_q1',
                'question': '請依附圖作答。',
                'options': {key: f'選項 {key}' for key in 'ABCD'},
                'answer': 'A',
                'source': 'sample',
                'source_ref': {'page_index': 0, 'page_number': 1},
                'images': [{
                    'src': '/pdf-assets/中級/sample/page_000/image_01_01.png',
                }],
            }

            with patch.object(answer_verifier, 'BASE', root):
                images = answer_verifier.resolve_images(question, '中級')
                result = answer_verifier.verify_question(
                    question, [], '中級', timeout=1, retries=0, images=images,
                )
                self.assertTrue(
                    answer_verifier.cache_matches_question(result, question, images)
                )
                self.assertEqual(
                    result['image_inputs'][0]['path'],
                    'frontend/public/pdf-assets/中級/sample/page_000/image_01_01.png',
                )
                self.assertEqual(
                    result['image_inputs'][0]['sha256'],
                    hashlib.sha256(b'first image bytes').hexdigest(),
                )

                # The path and question metadata are unchanged; only the exact
                # bytes sent to the Vision model differ.
                image.write_bytes(b'second image bytes')
                self.assertFalse(
                    answer_verifier.cache_matches_question(result, question, images)
                )

                image.unlink()
                fallback = image.with_name('image_02_01.png')
                fallback.write_bytes(b'unrelated page fallback')
                self.assertEqual(
                    answer_verifier.resolve_images(question, '中級'),
                    [image],
                    'a missing declared image must not be replaced by a page fallback',
                )
                self.assertFalse(
                    answer_verifier.cache_matches_question(result, question, images)
                )
                with self.assertRaises(FileNotFoundError):
                    answer_verifier.verify_question(
                        question, [], '中級', timeout=1, retries=0, images=images,
                    )

    def test_answer_verification_cache_tracks_page_fallback_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            asset_root = root / 'frontend' / 'public' / 'pdf-assets' / '中級' / 'sample'
            for page in (0, 1):
                image = asset_root / f'page_{page:03d}' / 'image_01_01.png'
                image.parent.mkdir(parents=True)
                image.write_bytes(b'identical image bytes')
            question = {
                'id': 'sample_q1',
                'question': '請依該頁圖片作答。',
                'options': {key: f'選項 {key}' for key in 'ABCD'},
                'answer': 'A',
                'source': 'sample',
                'source_ref': {'page_index': 0, 'page_number': 1},
            }

            with patch.object(answer_verifier, 'BASE', root):
                first_images = answer_verifier.resolve_images(question, '中級')
                cached = {
                    'question_fingerprint': answer_verifier.question_fingerprint(
                        question, first_images
                    ),
                }
                self.assertTrue(
                    answer_verifier.cache_matches_question(
                        cached, question, first_images
                    )
                )

                next_page = {
                    **question,
                    'source_ref': {'page_index': 1, 'page_number': 2},
                }
                next_images = answer_verifier.resolve_images(next_page, '中級')
                self.assertNotEqual(first_images, next_images)
                self.assertFalse(
                    answer_verifier.cache_matches_question(
                        cached, next_page, next_images
                    )
                )

    def test_answer_verification_table_crop_tracks_source_bytes(self) -> None:
        from PIL import Image, ImageDraw

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            page_dir = (
                root / 'frontend' / 'public' / 'pdf-assets' / '中級' / 'sample'
                / 'page_000'
            )
            page_dir.mkdir(parents=True)
            table = page_dir / 'table_01.png'
            Image.new('RGB', (20, 10), 'white').save(table)
            crop_dir = root / 'crops'
            question = {
                'id': 'sample_q1',
                'question': '請依程式碼作答。',
                'options': {
                    'A': '程式碼 A',
                    'B': '程式碼 B',
                    'C': '程式碼 C',
                    'D': '程式碼 D',
                },
                'answer': 'A',
                'source': 'sample',
                'source_ref': {'page_index': 0, 'page_number': 1},
            }

            with patch.object(answer_verifier, 'BASE', root):
                first_images = answer_verifier.resolve_images(
                    question, '中級', allow_table_crops=True, cache_dir=crop_dir,
                )
                cached = {
                    'question_fingerprint': answer_verifier.question_fingerprint(
                        question, first_images
                    ),
                }

                # Same table path, different source bytes. The content-addressed
                # crop path must change even if the edited pixels are discarded
                # with the printed answer column.
                edited = Image.new('RGB', (20, 10), 'white')
                ImageDraw.Draw(edited).rectangle((0, 0, 1, 9), fill='black')
                edited.save(table)
                next_images = answer_verifier.resolve_images(
                    question, '中級', allow_table_crops=True, cache_dir=crop_dir,
                )
                self.assertNotEqual(first_images, next_images)
                self.assertFalse(
                    answer_verifier.cache_matches_question(
                        cached, question, next_images
                    )
                )

    def test_formula_parentheses_are_not_option_boundaries(self) -> None:
        cell = (
            '題幹\n'
            '(A)信賴度=P(A∩B)；\n'
            '(B)支援度=P(B|A)；\n'
            '(C)提升度=P(A∩B) / [P(A)×P(B)]；\n'
            '(D)提升度=1'
        )
        question = parse_question_cell('D', cell, 18, 'fixture')
        self.assertIsNotNone(question)
        assert question is not None
        self.assertEqual(question['options']['A'], '信賴度=P(A∩B)')
        self.assertEqual(question['options']['B'], '支援度=P(B|A)')
        self.assertIn('[P(A)×P(B)]', question['options']['C'])

    def test_compact_semicolon_options_still_parse(self) -> None:
        question = parse_question_cell(
            'C', '附圖程式碼計算何者？\n(A)MAE；(B)MSE；(C)RMSE；(D)R²', 1, 'fixture'
        )
        self.assertIsNotNone(question)
        assert question is not None
        self.assertEqual(question['options'], {'A': 'MAE', 'B': 'MSE', 'C': 'RMSE', 'D': 'R²'})

    def test_targeted_rebuild_uses_atomic_write_and_preserves_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            output = output_dir / 'mock_fixture.json'
            output.write_text('{"old": true}\n', encoding='utf-8')
            output.chmod(0o640)
            save_mock('mock_fixture.json', 'fixture', [], output_dir)
            payload = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(payload['total'], 0)
            self.assertEqual(output.stat().st_mode & 0o777, 0o640)
            self.assertEqual(list(output_dir.glob('*.tmp')), [])

    def test_sample_parser_keeps_questions_split_across_pages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            extracted = data_dir / 'extracted'
            extracted.mkdir()
            payload = {
                'pages': [
                    {
                        'page': 1,
                        'tables': [[
                            ['1.', None, None, 'B', None, None,
                             '跨頁題幹？\n(A)選項甲\n(B)選項乙', None],
                        ]],
                    },
                    {
                        'page': 2,
                        'tables': [[
                            ['', None, None, '', None, None,
                             '(C)選項丙\n(D)選項丁', None],
                            ['2.', None, None, 'A', None, None,
                             '下一題題幹？\n(A)甲\n(B)乙\n(C)丙\n(D)丁', None],
                        ]],
                    },
                ],
            }
            (extracted / 'sample.json').write_text(
                json.dumps(payload, ensure_ascii=False), encoding='utf-8'
            )
            questions = parse_sample_json(data_dir)

        self.assertEqual([question['id'] for question in questions], ['sample_q1', 'sample_q2'])
        self.assertEqual(questions[0]['options']['D'], '選項丁')
        self.assertEqual(questions[0]['source_ref']['page_index'], 0)

    def test_affected_parsed_questions_are_source_faithful(self) -> None:
        def dummy_cell(number: int) -> str:
            return (
                f'第 {number} 題的完整測試題幹？\n'
                '(A)選項甲；\n(B)選項乙；\n(C)選項丙；\n(D)選項丁'
            )

        s2_cells = [dummy_cell(number) for number in range(1, 19)]
        s2_cells[17] = (
            '某零售企業的 AI工程師正在用關聯規則學習分析購物籃\n18.\n'
            '資料，下列敘述何者正確？\n'
            '(A)信賴度=P(A∩B)，即A與B 同時出現的機率，範圍[0,1]；\n'
            '(B)支援度=P(B|A)，即 A出現時 B 也出現的條件機率，範圍[0,1]；\n'
            '(C)提升度=P(A∩B) / [P(A)×P(B)]，範圍固定在[0,1]之間；\n'
            '(D)提升度=1 表示 A 與 B 獨立'
        )

        s3_cells = [dummy_cell(number) for number in range(1, 43)]
        s3_cells[2] = (
            '某工程師在撰寫 Transformer 的 Attention 層時，需手動驗證矩陣維度是否相容。\n'
            '3.\n輸入矩陣 Q已攤平成形狀為(1, 10)，Query投影權重矩陣 W 形狀為(10, 64)。執\n'
            'Q\n行Q x W 後輸出的形狀為何？\nQ\n'
            '(A)(1, 64)；\n(B)(10, 10)；\n(C)(64, 1)；\n(D)維度不相容，無法相乘'
        )
        s3_cells[41] = (
            '觀察程式中行(A)將所有既有權重的梯度計算關閉，這在遷移學習中屬於哪一種標\n'
            '42.\n準策略？\n'
            '(A)全面微調；\n(B)零樣本學習；\n(C)特徵萃取；\n(D)知識蒸餾'
        )

        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            extracted = data_dir / 'extracted'
            extracted.mkdir()
            fixtures = {
                'mid_1151_s2': ('D', s2_cells),
                'mid_1151_s3': ('C', s3_cells),
            }
            for key, (target_answer, cells) in fixtures.items():
                rows = [
                    [target_answer if index == len(cells) else 'A', None, None, cell]
                    for index, cell in enumerate(cells, start=1)
                ]
                (extracted / f'{key}.json').write_text(
                    json.dumps({'pages': [{'page': 1, 'tables': [rows]}]}, ensure_ascii=False),
                    encoding='utf-8',
                )

            s2 = {
                question['id']: question
                for question in parse_exam_json('mid_1151_s2', data_dir)
            }
            s3 = {
                question['id']: question
                for question in parse_exam_json('mid_1151_s3', data_dir)
            }

        self.assertEqual(
            s2['mid_1151_s2_q18']['options']['A'],
            '信賴度=P(A∩B)，即A與B 同時出現的機率，範圍[0,1]',
        )
        self.assertIn('W_Q 形狀為 (10, 64)', s3['mid_1151_s3_q3']['question'])
        self.assertIn('將所有既有權重的梯度計算關閉', s3['mid_1151_s3_q42']['question'])

    def test_current_production_repairs_and_source_issue_notices(self) -> None:
        summary, errors = verify()
        self.assertEqual(errors, [], '\n'.join(errors))
        self.assertEqual(summary['catalog_exams'], 14)
        self.assertEqual(summary['production_questions'], 715)
        self.assertEqual(summary['source_issues_visible'], 2)
        self.assertEqual(summary['visual_reviewed_exams'], 14)
        self.assertEqual(summary['visual_reviewed_questions'], 715)

    def test_every_exam_has_a_current_page_by_page_visual_review(self) -> None:
        summary, errors = verify_visual_reviews()
        self.assertEqual(errors, [], '\n'.join(errors))
        self.assertEqual(summary['catalog_exams'], 14)
        self.assertEqual(summary['reviewed_exams'], 14)
        self.assertEqual(summary['reviewed_pages'], 199)
        self.assertEqual(summary['reviewed_questions'], 715)

    def test_source_issue_explanations_have_a_results_render_path(self) -> None:
        results_component = (
            ROOT / 'frontend' / 'src' / 'components' / 'exam' / 'ExamResults.tsx'
        ).read_text(encoding='utf-8')
        self.assertIn('{q.explanation && (', results_component)
        self.assertIn('{q.explanation}', results_component)

        junior = json.loads(
            (ROOT / 'data' / '初級' / 'questions' / 'sample_exam.json').read_text(encoding='utf-8')
        )
        middle = json.loads(
            (ROOT / 'data' / '中級' / 'questions' / 'mock_mid_1151_s2.json').read_text(encoding='utf-8')
        )
        for payload, qid in ((junior, 'sample_q22'), (middle, 'mid_1151_s2_q49')):
            question = next(question for question in payload['questions'] if question['id'] == qid)
            self.assertEqual(question['explanation'], question['source_issue']['note'])

    def test_sidecar_overlay_repairs_cached_fields_without_mutating_raw_cache(self) -> None:
        raw_cache = ROOT / 'data' / '中級' / 'exam_pages_cache' / 'mid_1151_s2' / 'page_003.json'
        before = hashlib.sha256(raw_cache.read_bytes()).hexdigest() if raw_cache.exists() else None
        payload = sidecar.build_overlay(exam_entries())
        after = hashlib.sha256(raw_cache.read_bytes()).hexdigest() if raw_cache.exists() else None

        self.assertEqual(before, after)
        self.assertEqual(payload['summary']['production_questions'], 715)
        self.assertEqual(
            payload['summary']['cached_questions']
            + payload['summary']['missing_cache_questions'],
            715,
        )
        self.assertEqual(payload['summary']['overlay_field_mismatches'], 0)
        self.assertFalse(payload['summary']['promotion_ready'])

        q12 = next(
            (record for record in payload['records'] if record['id'] == 'mid_1151_s2_q12'),
            None,
        )
        if q12 is not None:
            self.assertEqual(q12['verified']['answer'], 'C')
            self.assertIn('A', q12['vision_merged']['answer_candidates'])
            self.assertIn('answer', q12['raw_mismatch_fields'])

    def test_verified_overlay_corrects_a_wrong_raw_answer_without_repo_cache(self) -> None:
        entry = {
            'levelId': 'middle',
            'key': 'mid_1151_s2',
            'questionFile': 'fixture.json',
            'expectedQuestions': 1,
        }
        production = [{
            'id': 'mid_1151_s2_q12',
            'question': '經 PDF 核對的題幹',
            'options': {key: f'選項 {key}' for key in 'ABCD'},
            'answer': 'C',
        }]
        raw_question = {
            'number': 1,
            'question': '經 PDF 核對的題幹',
            'options': {key: f'選項 {key}' for key in 'ABCD'},
            'answer': 'A',
        }
        raw = {1: [{'page_index': 0, 'value': raw_question}]}
        raw_answers = {1: [{'page_index': 1, 'value': 'A'}]}
        with (
            patch.object(sidecar, 'load_production_questions', return_value=('中級', production)),
            patch.object(sidecar, 'load_raw_candidates', return_value=(raw, raw_answers, ['fixture'])),
        ):
            payload = sidecar.build_overlay([entry])

        record = payload['records'][0]
        self.assertEqual(record['verified']['answer'], 'C')
        self.assertEqual(record['vision_merged']['answer_candidates'], ['A'])
        self.assertIn('answer', record['raw_mismatch_fields'])
        self.assertEqual(payload['summary']['overlay_field_mismatches'], 0)
        self.assertTrue(payload['summary']['promotion_ready'])

    def test_promotion_gate_blocks_incomplete_or_absent_cache(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / 'scripts' / 'reconcile_exam_vision_sidecar.py'),
                '--level', 'all', '--promotion-gate',
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        summary = json.loads(result.stdout)
        self.assertGreater(summary['missing_cache_questions'], 0)
        self.assertIn('PROMOTION BLOCKED', result.stderr)

    def test_runtime_does_not_read_raw_sidecar(self) -> None:
        runtime_paths = [ROOT / 'scripts' / 'parse_exams_v2.py']
        runtime_paths.extend((ROOT / 'frontend' / 'src').rglob('*.ts'))
        runtime_paths.extend((ROOT / 'frontend' / 'src').rglob('*.tsx'))
        offenders = [
            str(path.relative_to(ROOT)) for path in runtime_paths
            if 'exam_pages_cache' in path.read_text(encoding='utf-8')
        ]
        self.assertEqual(offenders, [], f'raw sidecar leaked into runtime: {offenders}')


if __name__ == '__main__':
    unittest.main()
