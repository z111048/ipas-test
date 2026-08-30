#!/usr/bin/env python3
"""Regression tests for rebuildable exam image/context annotations."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from annotate_exam_code_images import (  # noqa: E402
    ANNOTATIONS,
    MID_1151_S3_TRANSFER_CONTEXT,
    MID_1151_S3_TRANSFER_SRC,
    VGG16_SUMMARY_MARKDOWN,
    annotate_context_blocks,
    annotate_mid1151s3_transfer_group,
    annotate_question_images,
)
from verify_exam_ocr_repairs import known_image_annotation_errors  # noqa: E402


class AnnotateExamCodeImagesTests(unittest.TestCase):
    SAMPLE_CODE_IMAGES = {
        'sample_q30': '/pdf-assets/中級/sample/page_006/image_02_01.png',
        'sample_q45': '/pdf-assets/中級/sample/page_009/image_02_01.png',
    }

    def test_vgg16_summary_is_rebuilt_without_preserved_context_blocks(self) -> None:
        for question_number in (42, 43, 44):
            question = {
                'id': f'mid_1141_s3_q{question_number}',
                'context': '請參考以下 VGG16 模型摘要回答題目。',
            }

            self.assertTrue(annotate_context_blocks(question))
            self.assertEqual(question['context_blocks'], [{
                'title': 'VGG16 模型摘要',
                'language': 'text',
                'markdown': VGG16_SUMMARY_MARKDOWN,
            }])
            self.assertIn('Linear-33 [-1, 4096] 102,764,544', VGG16_SUMMARY_MARKDOWN)
            self.assertIn('Total params: 138,357,544', VGG16_SUMMARY_MARKDOWN)
            self.assertIn('Estimated Total Size (MB): 624.98', VGG16_SUMMARY_MARKDOWN)

            annotated = deepcopy(question)
            self.assertFalse(annotate_context_blocks(annotated))
            self.assertEqual(annotated, question)

    def test_production_q42_to_q44_include_the_full_vgg16_summary(self) -> None:
        path = ROOT / 'data' / '中級' / 'questions' / 'mock_mid_1141_s3.json'
        payload = json.loads(path.read_text(encoding='utf-8'))
        questions = {question['id']: question for question in payload['questions']}

        for question_number in (42, 43, 44):
            question = questions[f'mid_1141_s3_q{question_number}']
            self.assertEqual(question['context_blocks'][0]['markdown'], VGG16_SUMMARY_MARKDOWN)

    def test_mid1151s3_transfer_group_repairs_page_break_association(self) -> None:
        q41_image = {
            'type': 'image',
            'src': '/pdf-assets/中級/mid_1151_s3/page_010/image_03_01.png',
            'placement': 'question',
        }
        stale_transfer_image = {
            'type': 'image',
            'src': MID_1151_S3_TRANSFER_SRC,
            'placement': 'option',
            'option': 'D',
        }
        q41 = {
            'id': 'mid_1151_s3_q41',
            'images': [deepcopy(q41_image), stale_transfer_image],
        }

        self.assertTrue(annotate_mid1151s3_transfer_group(q41))
        self.assertEqual(q41['images'], [q41_image])
        self.assertFalse(annotate_mid1151s3_transfer_group(q41))

        for question_number in (42, 43):
            question = {
                'id': f'mid_1151_s3_q{question_number}',
                'context': None,
            }
            self.assertTrue(annotate_mid1151s3_transfer_group(question))
            self.assertEqual(question['context'], MID_1151_S3_TRANSFER_CONTEXT)
            self.assertEqual(len(question['images']), 1)
            image = question['images'][0]
            self.assertEqual(image['src'], MID_1151_S3_TRANSFER_SRC)
            self.assertEqual(image['placement'], 'context')
            self.assertNotIn('option', image)
            for field, value in ANNOTATIONS[MID_1151_S3_TRANSFER_SRC].items():
                self.assertEqual(image[field], value)

            annotated = deepcopy(question)
            self.assertFalse(annotate_mid1151s3_transfer_group(annotated))
            self.assertEqual(annotated, question)

    def test_production_mid1151s3_transfer_group_is_source_faithful(self) -> None:
        path = ROOT / 'data' / '中級' / 'questions' / 'mock_mid_1151_s3.json'
        payload = json.loads(path.read_text(encoding='utf-8'))
        questions = {question['id']: question for question in payload['questions']}

        q41 = questions['mid_1151_s3_q41']
        self.assertNotIn(
            MID_1151_S3_TRANSFER_SRC,
            [image['src'] for image in q41.get('images', [])],
        )

        for question_number in (42, 43):
            question = questions[f'mid_1151_s3_q{question_number}']
            self.assertEqual(question['context'], MID_1151_S3_TRANSFER_CONTEXT)
            self.assertEqual(
                [image['src'] for image in question['images']],
                [MID_1151_S3_TRANSFER_SRC],
            )
            self.assertEqual(question['images'][0]['placement'], 'context')
            self.assertEqual(
                question['images'][0]['markdown'],
                ANNOTATIONS[MID_1151_S3_TRANSFER_SRC]['markdown'],
            )

    def test_sample_code_annotations_are_rebuilt_and_idempotent(self) -> None:
        questions = [
            {
                'id': question_id,
                'images': [{'type': 'image', 'src': src, 'placement': 'question'}],
            }
            for question_id, src in self.SAMPLE_CODE_IMAGES.items()
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sample_exam.json'
            path.write_text(
                json.dumps({'questions': questions}, ensure_ascii=False),
                encoding='utf-8',
            )

            self.assertEqual(annotate_question_images(path), 6)
            annotated = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(annotate_question_images(path), 0)

        for question in annotated['questions']:
            image = question['images'][0]
            for field, value in ANNOTATIONS[image['src']].items():
                self.assertEqual(image[field], value)

    def test_production_sample_code_annotations_are_current_and_verified(self) -> None:
        path = ROOT / 'data' / '中級' / 'questions' / 'sample_exam.json'
        payload = json.loads(path.read_text(encoding='utf-8'))
        questions = {question['id']: question for question in payload['questions']}

        scoped_questions = {}
        for question_id, src in self.SAMPLE_CODE_IMAGES.items():
            question = questions[question_id]
            image = next(image for image in question['images'] if image['src'] == src)
            for field, value in ANNOTATIONS[src].items():
                self.assertEqual(image[field], value)
            scoped_questions[('中級', 'sample', question_id)] = question

        self.assertEqual(known_image_annotation_errors(scoped_questions), [])

        stale = deepcopy(scoped_questions)
        stale[('中級', 'sample', 'sample_q30')]['images'][0].pop('markdown')
        self.assertEqual(len(known_image_annotation_errors(stale)), 1)
        self.assertIn('sample_q30', known_image_annotation_errors(stale)[0])


if __name__ == '__main__':
    unittest.main()
