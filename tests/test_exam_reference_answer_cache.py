#!/usr/bin/env python3
"""Regression tests for content-addressed exam reference-answer caching."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import export_exam_reference_answers as exporter  # noqa: E402
from run_codex_exam_reference_answers import (  # noqa: E402
    build_prompt,
    file_sha256,
    legacy_question_content_fingerprint,
    output_question_fingerprint,
    output_provenance_path,
    prompt_question_fingerprint,
    question_content_fingerprint,
    targeted_rerun_collisions,
    validate_output,
    write_output_provenance,
)


def make_question(question_id: str, stem: str, answer: str = 'A') -> dict:
    return {
        'id': question_id,
        'question': stem,
        'options': {key: f'{stem} 選項 {key}' for key in 'ABCD'},
        'answer': answer,
    }


def make_prompt(question: dict) -> str:
    options = question['options']
    return (
        'question_id: fixture\n'
        f'question: {question["question"]}\n'
        'options:\n'
        f'A. {options["A"]}\n'
        f'B. {options["B"]}\n'
        f'C. {options["C"]}\n'
        f'D. {options["D"]}\n'
        f'official_answer: {question["answer"]}\n'
        'current_explanation: fixture\n'
    )


def make_output(question_id: str, answer: str, reference_answer: str = 'generated') -> dict:
    return {
        'level': '初級',
        'exam_key': 'sample',
        'question_id': question_id,
        'answer': answer,
        'reference_answer': reference_answer * 90,
        'option_analysis': {key: f'{key} analysis' for key in 'ABCD'},
        'key_concepts': ['fixture'],
        'citations': [{'fixture': True}],
        'confidence': 'high',
        'notes': '',
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')


class ExamReferenceAnswerCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        # q2 is newly restored; the old q2 content is now canonical q3. Both
        # deliberately share answer A so id/answer-only validation cannot help.
        self.current_questions = [
            make_question('sample_q1', '第一題', 'B'),
            make_question('sample_q2', '補回的跨頁題', 'A'),
            make_question('sample_q3', '原本的第二題', 'A'),
        ]

    def test_legacy_maps_by_content_but_canonical_rerun_stays_in_place(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            by_fingerprint, _ = exporter.question_fingerprint_index(
                self.current_questions, label='初級/sample'
            )

            legacy_root = root / 'legacy'
            legacy_output = legacy_root / 'outputs' / 'sample_q2.json'
            legacy_prompt = legacy_root / 'prompts' / 'sample_q2.md'
            write_json(legacy_output, make_output('sample_q2', 'A'))
            legacy_prompt.parent.mkdir(parents=True)
            legacy_prompt.write_text(make_prompt(self.current_questions[2]), encoding='utf-8')
            os.utime(legacy_prompt, (1, 1))
            os.utime(legacy_output, (2, 2))

            resolved_legacy = exporter.canonical_question_for_output(
                legacy_output,
                legacy_prompt,
                by_fingerprint,
                label='初級/sample',
            )
            self.assertEqual(resolved_legacy['id'], 'sample_q3')

            canonical_root = root / 'canonical'
            canonical_output = canonical_root / 'outputs' / 'sample_q2.json'
            write_json(canonical_output, make_output('sample_q2', 'A'))
            write_output_provenance(
                canonical_output,
                question_content_fingerprint(self.current_questions[1]),
                'sample_q2',
            )
            resolved_canonical = exporter.canonical_question_for_output(
                canonical_output,
                canonical_root / 'prompts' / 'sample_q2.md',
                by_fingerprint,
                label='初級/sample',
            )
            self.assertEqual(resolved_canonical['id'], 'sample_q2')

    def test_v2_fingerprint_covers_context_visuals_and_source_identity(self) -> None:
        question = {
            **self.current_questions[1],
            'explanation': '官方解析',
            'context': '共用 ResNet 題組',
            'context_blocks': [{'type': 'code', 'markdown': 'model = resnet50()'}],
            'images': [{'src': '/pdf-assets/sample/page_001/image_01.png'}],
            'source': 'sample',
            'source_ref': {'page_index': 1, 'page_number': 2},
        }
        fingerprint = question_content_fingerprint(question)
        for field, replacement in (
            ('context', '共用 VGG16 題組'),
            ('context_blocks', [{'type': 'code', 'markdown': 'model = vgg16()'}]),
            ('images', [{'src': '/pdf-assets/sample/page_002/image_01.png'}]),
            ('source_ref', {'page_index': 2, 'page_number': 3}),
        ):
            changed = {**question, field: replacement}
            self.assertNotEqual(
                question_content_fingerprint(changed), fingerprint, field
            )

        prompt = build_prompt('初級', 'sample', {'exam': 'fixture'}, question, [])
        with tempfile.TemporaryDirectory() as directory:
            prompt_path = Path(directory) / 'prompt.md'
            prompt_path.write_text(prompt, encoding='utf-8')
            self.assertEqual(prompt_question_fingerprint(prompt_path), fingerprint)

    def test_v1_provenance_and_legacy_prompt_remain_migratable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output_path = root / 'outputs' / 'sample_q2.json'
            prompt_path = root / 'prompts' / 'sample_q2.md'
            write_json(output_path, make_output('sample_q2', 'A'))
            prompt_path.parent.mkdir(parents=True)
            prompt_path.write_text(make_prompt(self.current_questions[2]), encoding='utf-8')
            legacy_fingerprint = legacy_question_content_fingerprint(
                self.current_questions[2]
            )
            write_json(output_provenance_path(output_path), {
                'schemaVersion': 1,
                'questionIdAtGeneration': 'sample_q2',
                'questionFingerprint': legacy_fingerprint,
                'outputSha256': file_sha256(output_path),
            })

            self.assertEqual(
                output_question_fingerprint(output_path, prompt_path),
                legacy_fingerprint,
            )
            by_fingerprint, _ = exporter.question_fingerprint_index(
                self.current_questions, label='初級/sample'
            )
            self.assertEqual(by_fingerprint[legacy_fingerprint]['id'], 'sample_q3')

    def test_cache_rejects_same_id_and_answer_when_content_changed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / 'sample_q2.json'
            write_json(output_path, make_output('sample_q2', 'A'))
            stale_fingerprint = question_content_fingerprint(self.current_questions[2])
            errors = validate_output(
                output_path,
                '初級',
                'sample',
                self.current_questions[1],
                cached_question_fingerprint=stale_fingerprint,
                require_content_fingerprint=True,
            )
            self.assertIn('question content fingerprint mismatch', errors)
            self.assertNotIn('answer must match official answer', errors)

            current_fingerprint = question_content_fingerprint(self.current_questions[1])
            self.assertEqual(
                validate_output(
                    output_path,
                    '初級',
                    'sample',
                    self.current_questions[1],
                    cached_question_fingerprint=current_fingerprint,
                    require_content_fingerprint=True,
                ),
                [],
            )

    def test_generation_transcript_recovers_legacy_content_after_prompt_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output_path = root / 'outputs' / 'sample_q2.json'
            prompt_path = root / 'prompts' / 'sample_q2.md'
            raw = make_output('sample_q2', 'A')
            write_json(output_path, raw)
            output_path.with_suffix('.log').write_text(
                json.dumps(raw, ensure_ascii=False), encoding='utf-8'
            )
            output_path.with_suffix('.err').write_text(
                make_prompt(self.current_questions[2]), encoding='utf-8'
            )
            prompt_path.parent.mkdir(parents=True)
            prompt_path.write_text(make_prompt(self.current_questions[1]), encoding='utf-8')
            for path in (output_path, output_path.with_suffix('.log'), output_path.with_suffix('.err')):
                os.utime(path, (2, 2))
            os.utime(prompt_path, (3, 3))

            self.assertEqual(
                output_question_fingerprint(output_path, prompt_path),
                legacy_question_content_fingerprint(self.current_questions[2]),
            )

    def test_targeted_rerun_refuses_to_overwrite_shifted_legacy_carrier(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_root = Path(directory)
            output_path = run_root / 'sample/outputs/sample_q2.json'
            write_json(output_path, make_output('sample_q2', 'A'))
            write_output_provenance(
                output_path,
                question_content_fingerprint(self.current_questions[2]),
                'sample_q2',
            )

            collisions = targeted_rerun_collisions(
                run_root,
                'sample',
                self.current_questions,
                [self.current_questions[1]],
            )
            self.assertEqual(
                collisions,
                ['sample_q2: existing output still carries canonical sample_q3'],
            )
            self.assertEqual(
                targeted_rerun_collisions(
                    run_root,
                    'sample',
                    self.current_questions,
                    self.current_questions,
                ),
                [],
            )

    def test_hash_bound_provenance_rejects_modified_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output_path = root / 'outputs' / 'sample_q2.json'
            prompt_path = root / 'prompts' / 'sample_q2.md'
            write_json(output_path, make_output('sample_q2', 'A'))
            write_output_provenance(
                output_path,
                question_content_fingerprint(self.current_questions[1]),
                'sample_q2',
            )
            raw = json.loads(output_path.read_text(encoding='utf-8'))
            raw['notes'] = 'modified after generation'
            write_json(output_path, raw)

            with self.assertRaisesRegex(ValueError, 'output changed after provenance'):
                output_question_fingerprint(output_path, prompt_path)

    def test_canonical_generated_answer_supersedes_temporary_overlay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            question_path = root / 'data/初級/questions/sample_exam.json'
            write_json(question_path, {'questions': self.current_questions})
            outputs_dir = root / 'data/初級/pipeline/exam_reference_answers/sample/outputs'
            for question in self.current_questions:
                output_path = outputs_dir / f'{question["id"]}.json'
                write_json(
                    output_path,
                    make_output(question['id'], question['answer'], question['id']),
                )
                write_output_provenance(
                    output_path,
                    question_content_fingerprint(question),
                    question['id'],
                )

            overlay_path = root / 'data/exam_reference_answer_overlays.json'
            write_json(overlay_path, {
                'schemaVersion': 2,
                'exams': {
                    '初級/sample': {
                        'sample_q2': {
                            'questionFingerprint': question_content_fingerprint(
                                self.current_questions[1]
                            ),
                            'answer': 'A',
                            'reference_answer': 'temporary overlay',
                        },
                    },
                },
            })
            exam_config = {
                'key': 'sample',
                'routeKey': 'sample',
                'questionFile': 'sample_exam.json',
            }
            export_dir = root / 'export'
            with (
                patch.object(exporter, 'ROOT', root),
                patch.object(exporter, 'OVERLAY_PATH', overlay_path),
                patch.object(exporter, 'exam_entries', return_value=[exam_config]),
            ):
                stats = exporter.export_reference_answers('初級', export_dir)

            exported = json.loads((export_dir / 'sample.json').read_text(encoding='utf-8'))
            self.assertEqual(list(exported), ['sample_q1', 'sample_q2', 'sample_q3'])
            self.assertTrue(exported['sample_q2']['reference_answer'].startswith('sample_q2'))
            self.assertEqual(stats['elementary']['sample'], 3)

    def test_overlay_rejects_same_id_and_answer_after_content_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = {**self.current_questions[1], 'context': '原共用題組'}
            changed = {**original, 'context': '修正後的共用題組'}
            current_questions = [self.current_questions[0], changed, self.current_questions[2]]
            write_json(
                root / 'data/初級/questions/sample_exam.json',
                {'questions': current_questions},
            )
            outputs_dir = root / 'data/初級/pipeline/exam_reference_answers/sample/outputs'
            for question in (current_questions[0], current_questions[2]):
                output_path = outputs_dir / f'{question["id"]}.json'
                write_json(output_path, make_output(question['id'], question['answer']))
                write_output_provenance(
                    output_path,
                    question_content_fingerprint(question),
                    question['id'],
                )
            overlay_path = root / 'data/exam_reference_answer_overlays.json'
            write_json(overlay_path, {
                'schemaVersion': 2,
                'exams': {
                    '初級/sample': {
                        'sample_q2': {
                            'questionFingerprint': question_content_fingerprint(original),
                            'answer': 'A',
                            'reference_answer': 'stale overlay',
                        },
                    },
                },
            })
            exam_config = {
                'key': 'sample',
                'routeKey': 'sample',
                'questionFile': 'sample_exam.json',
            }
            with (
                patch.object(exporter, 'ROOT', root),
                patch.object(exporter, 'OVERLAY_PATH', overlay_path),
                patch.object(exporter, 'exam_entries', return_value=[exam_config]),
            ):
                with self.assertRaisesRegex(ValueError, 'overlay content fingerprint mismatch'):
                    exporter.export_reference_answers('初級', root / 'export')

    def test_exporter_rejects_incomplete_production_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_json(
                root / 'data/初級/questions/sample_exam.json',
                {'questions': self.current_questions},
            )
            outputs_dir = root / 'data/初級/pipeline/exam_reference_answers/sample/outputs'
            for question in self.current_questions[:2]:
                output_path = outputs_dir / f'{question["id"]}.json'
                write_json(output_path, make_output(question['id'], question['answer']))
                write_output_provenance(
                    output_path,
                    question_content_fingerprint(question),
                    question['id'],
                )
            exam_config = {
                'key': 'sample',
                'routeKey': 'sample',
                'questionFile': 'sample_exam.json',
            }
            with (
                patch.object(exporter, 'ROOT', root),
                patch.object(exporter, 'OVERLAY_PATH', root / 'no-overlays.json'),
                patch.object(exporter, 'exam_entries', return_value=[exam_config]),
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    r'published=2, production=3, missing=\[\'sample_q3\'\]',
                ):
                    exporter.export_reference_answers('初級', root / 'export')

    def test_canonical_output_replaces_matching_legacy_but_legacy_only_key_is_stable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            question = make_question('jr_1141_s1_q1', '既有官方題', 'B')
            write_json(
                root / 'data/初級/questions/mock_jr_1141_s1.json',
                {'questions': [question]},
            )
            outputs_dir = (
                root / 'data/初級/pipeline/exam_reference_answers/jr_1141_s1/outputs'
            )
            legacy_output = outputs_dir / 'exam1_q1.json'
            legacy_raw = make_output('exam1_q1', 'B', 'legacy')
            legacy_raw['exam_key'] = 'exam1'
            write_json(legacy_output, legacy_raw)
            fingerprint = question_content_fingerprint(question)
            write_output_provenance(legacy_output, fingerprint, 'exam1_q1')

            exam_config = {
                'key': 'jr_1141_s1',
                'routeKey': 'jr_1141_s1',
                'questionFile': 'mock_jr_1141_s1.json',
                'legacyReferencePrefix': 'exam1',
            }
            overlay_path = root / 'data/no-overlays.json'
            export_dir = root / 'export'
            patches = (
                patch.object(exporter, 'ROOT', root),
                patch.object(exporter, 'OVERLAY_PATH', overlay_path),
                patch.object(exporter, 'exam_entries', return_value=[exam_config]),
            )
            with patches[0], patches[1], patches[2]:
                exporter.export_reference_answers('初級', export_dir)
            legacy_only = json.loads(
                (export_dir / 'jr_1141_s1.json').read_text(encoding='utf-8')
            )
            self.assertEqual(list(legacy_only), ['exam1_q1'])

            canonical_output = outputs_dir / 'jr_1141_s1_q1.json'
            canonical_raw = make_output('jr_1141_s1_q1', 'B', 'canonical')
            canonical_raw['exam_key'] = 'jr_1141_s1'
            write_json(canonical_output, canonical_raw)
            write_output_provenance(
                canonical_output, fingerprint, 'jr_1141_s1_q1'
            )
            notice = StringIO()
            patches = (
                patch.object(exporter, 'ROOT', root),
                patch.object(exporter, 'OVERLAY_PATH', overlay_path),
                patch.object(exporter, 'exam_entries', return_value=[exam_config]),
            )
            with patches[0], patches[1], patches[2], redirect_stdout(notice):
                exporter.export_reference_answers('初級', export_dir)
            replaced = json.loads(
                (export_dir / 'jr_1141_s1.json').read_text(encoding='utf-8')
            )
            self.assertEqual(list(replaced), ['jr_1141_s1_q1'])
            self.assertTrue(
                replaced['jr_1141_s1_q1']['reference_answer'].startswith('canonical')
            )
            self.assertIn('canonical outputs replaced 1 legacy duplicate', notice.getvalue())

            legacy_raw['answer'] = 'A'
            write_json(legacy_output, legacy_raw)
            write_output_provenance(legacy_output, fingerprint, 'exam1_q1')
            patches = (
                patch.object(exporter, 'ROOT', root),
                patch.object(exporter, 'OVERLAY_PATH', overlay_path),
                patch.object(exporter, 'exam_entries', return_value=[exam_config]),
            )
            with patches[0], patches[1], patches[2]:
                with self.assertRaisesRegex(ValueError, 'official answer mismatch'):
                    exporter.export_reference_answers('初級', export_dir)

            legacy_raw['answer'] = 'B'
            write_json(legacy_output, legacy_raw)
            write_output_provenance(legacy_output, fingerprint, 'exam1_q1')
            conflicting_fingerprint = question_content_fingerprint(
                make_question('jr_1141_s1_q1', '不同題目內容', 'B')
            )
            write_output_provenance(
                canonical_output, conflicting_fingerprint, 'jr_1141_s1_q1'
            )
            patches = (
                patch.object(exporter, 'ROOT', root),
                patch.object(exporter, 'OVERLAY_PATH', overlay_path),
                patch.object(exporter, 'exam_entries', return_value=[exam_config]),
            )
            with patches[0], patches[1], patches[2]:
                with self.assertRaisesRegex(ValueError, 'no longer matches any current question'):
                    exporter.export_reference_answers('初級', export_dir)


if __name__ == '__main__':
    unittest.main()
