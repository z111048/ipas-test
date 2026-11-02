#!/usr/bin/env python3
"""Regression tests for guide/gallery producer and partial-export safety."""

from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

BASE = Path(__file__).resolve().parents[1]
SCRIPTS = BASE / 'scripts'
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import export_guide_outline_data as outline_export  # noqa: E402
import export_guide_embedded_exercises as exercise_export  # noqa: E402
import export_pdf_image_gallery as gallery_export  # noqa: E402
import export_question_generation_data as seed_export  # noqa: E402
import parse_guides  # noqa: E402
import publish_assets  # noqa: E402
import build_guide_block_id_migrations as migration_builder  # noqa: E402
import export_exam_reference_answers as reference_export  # noqa: E402
import export_guide_images_data as images_export  # noqa: E402
from cjk_parentheses import normalize_block_parentheses, normalize_cjk_parentheses  # noqa: E402
from guide_block_id_migrations import (  # noqa: E402
    BlockIdMigration,
    BlockIdMigrationError,
    guide_content_sha256,
    load_content_tree,
    reference_answers_digest,
    sha256_bytes,
)
from run_codex_exam_reference_answers import (  # noqa: E402
    question_content_fingerprint,
    write_output_provenance,
)


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def minimal_guide(level: str, subject_id: str, key: str, content_ref: str) -> dict:
    node_id = f'{subject_id}c1'
    return {
        'level': level,
        'subjectId': subject_id,
        'key': key,
        'sourceKey': key.split('-', 1)[-1],
        'subject': subject_id,
        'pdf': 'guide.pdf',
        'root': [node_id],
        'nodesById': {
            node_id: {
                'id': node_id,
                'parentId': None,
                'depth': 0,
                'order': 0,
                'number': '1',
                'title': node_id,
                'pageLabel': '1-1',
                'pageRange': [1, 1],
                'route': f'/guide/{subject_id}/{node_id}',
                'contentRef': content_ref,
                'children': [],
            },
        },
        'flat': [node_id],
        'stats': {},
    }


def valid_guide_content(node_id: str, marker: str) -> dict:
    return {
        'id': node_id,
        'title': node_id,
        'content': f'# {marker}',
        'contentFormat': 'markdown',
        'headings': [],
        'blocks': [{'id': 'block-1', 'type': 'paragraph', 'text': marker}],
        'sourcePages': [],
        'marker': marker,
    }


class ParseGuideSourceSafetyTest(unittest.TestCase):
    def test_regex_fallback_requires_explicit_opt_in(self) -> None:
        guides = {
            1: {
                'key': 'guide1',
                'pdf': 'missing.pdf',
                'subject': 'subject',
                'chapters': [{
                    'id': 's1c1',
                    'title': 'chapter',
                    'subtopics': [],
                    'start_page': '2-1',
                    'page_range': None,
                }],
            },
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(RuntimeError, '--allow-regex-fallback'):
                parse_guides.parse_guide(
                    1, guides, root / 'pdfs', root / 'pages_cache', root,
                    '初級',
                )

            write_json(root / 'extracted' / 'guide1.json', {
                'pages': [{'text': '這是明確開啟後才允許使用的舊版抽取內容。'}],
            })
            result = parse_guides.parse_guide(
                1, guides, root / 'pdfs', root / 'pages_cache', root,
                '初級', allow_regex_fallback=True,
            )
            self.assertEqual(result['source_track'], 'legacy_regex')
            self.assertEqual(result['source_mode'], 'regex')

    @unittest.skipUnless(parse_guides._FITZ_AVAILABLE, 'PyMuPDF required')
    def test_canonical_track_rejects_missing_or_error_cache_pages(self) -> None:
        guides = {
            1: {
                'key': 'guide1',
                'pdf': 'guide.pdf',
                'subject': 'subject',
                'chapters': [{
                    'id': 's1c1',
                    'title': 'chapter',
                    'subtopics': [],
                    'start_page': '1-1',
                    'page_range': [0, 4],
                }],
            },
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pdf_path = root / 'pdfs' / 'guide.pdf'
            pdf_path.parent.mkdir(parents=True)
            doc = parse_guides.fitz.open()
            for page_number in range(1, 6):
                page = doc.new_page()
                page.insert_text((72, 72), f'1-{page_number}')
            doc.save(pdf_path)
            doc.close()

            cache_dir = root / 'pages_cache' / 'guide1'
            for idx in range(4):
                write_json(cache_dir / f'page_{idx:03d}.json', {
                    'idx': idx,
                    'type': 'content',
                    'markdown': f'page {idx}',
                })

            with self.assertRaisesRegex(RuntimeError, 'complete'):
                parse_guides.parse_guide(
                    1, guides, root / 'pdfs', root / 'pages_cache', root,
                    '初級',
                )

            write_json(cache_dir / 'page_004.json', {
                'idx': 4,
                'type': 'error',
                'error': 'OCR failed',
            })
            with self.assertRaisesRegex(RuntimeError, 'complete'):
                parse_guides.parse_guide(
                    1, guides, root / 'pdfs', root / 'pages_cache', root,
                    '初級',
                )


class GuideProducerSafetyTest(unittest.TestCase):
    def test_track_a_export_does_not_overwrite_canonical_track_b(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old_base = seed_export.BASE
            seed_export.BASE = root
            try:
                write_json(root / 'data' / '初級' / 'toc_manifest.json', {
                    'subjects': [{
                        'id': 's1', 'key': 'guide1', 'subject': 'subject',
                        'chapters': [{
                            'id': 's1c1', 'title': 'chapter',
                            'subtopics': [], 'page_range': [1, 1],
                        }],
                    }],
                })
                write_json(root / 'frontend' / 'src' / 'generated' / 'guideOutlines.json', {
                    'guides': {
                        's1': {
                            'key': '初級-guide1',
                            'nodesById': {'s1c1': {'contentRef': 's1c1.json'}},
                        },
                    },
                })
                write_json(
                    root / 'frontend' / 'src' / 'generated' / 'guideContent'
                    / '初級-guide1' / 's1c1.json',
                    {'content': '# chapter\n\nTrack A', 'contentFormat': 'markdown'},
                )
                canonical = root / 'data' / '初級' / 'guide' / 'subject1_guide.json'
                write_json(canonical, {'producer': 'parse_guides', 'sentinel': True})

                seed_export.export_level('初級')

                self.assertEqual(json.loads(canonical.read_text(encoding='utf-8'))['producer'], 'parse_guides')
                reading = canonical.with_name('subject1_reading_guide.json')
                self.assertTrue(reading.exists())
                self.assertEqual(json.loads(reading.read_text(encoding='utf-8'))['chapters'][0]['content'], 'Track A')
            finally:
                seed_export.BASE = old_base

    def test_question_seed_writer_preserves_final_newline(self) -> None:
        payload = {'level': '中級', 'subject': '中文', 'chapters': [{'id': 's3c1', 'questions': []}]}
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode('utf-8')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with_newline = root / 'with_newline.json'
            with_newline.write_bytes(body + b'\n')
            seed_export.write_json(with_newline, payload)
            self.assertEqual(with_newline.read_bytes(), body + b'\n')

            without_newline = root / 'without_newline.json'
            without_newline.write_bytes(body)
            seed_export.write_json(without_newline, payload)
            self.assertEqual(without_newline.read_bytes(), body)

            fresh = root / 'nested' / 'fresh.json'
            seed_export.write_json(fresh, payload)
            self.assertEqual(fresh.read_bytes(), body + b'\n')

    def test_question_seed_export_keeps_committed_bytes(self) -> None:
        for level in ('初級', '中級'):
            manifest = json.loads((BASE / 'data' / level / 'toc_manifest.json').read_text(encoding='utf-8'))
            questions_dir = BASE / 'data' / level / 'questions'
            for index, subject in enumerate(manifest.get('subjects', []), start=1):
                path = questions_dir / f'subject{index}_questions.json'
                if not path.exists():
                    continue
                with self.subTest(path=path.relative_to(BASE).as_posix()):
                    original = path.read_bytes()
                    rebuilt = seed_export.build_question_seed(level, subject, path)
                    with tempfile.TemporaryDirectory() as temp:
                        target = Path(temp) / path.name
                        target.write_bytes(original)
                        seed_export.write_json(target, rebuilt)
                        self.assertEqual(target.read_bytes(), original)


class EmbeddedExerciseBoundarySafetyTest(unittest.TestCase):
    @staticmethod
    def subject() -> dict:
        return {
            'id': 's1',
            'chapters': [{
                'id': 's1c1',
                'title': 'chapter',
                'page_range': [1, 10],
            }],
        }

    def test_appendix_heading_stops_question_and_answer_state_machines(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            question_page = root / 'questions/page_005.json'
            appendix_question_page = root / 'questions/page_006.json'
            write_json(question_page, {
                'cleaned_text': (
                    '1. 下列何者屬於正常正文？\n'
                    '（A）參考書目管理 （B）模型訓練 （C）資料清理 （D）模型部署\n'
                    '2. 此題在附件前尚未完整\n（A）甲 （B）乙 （C）丙'
                ),
                'continues_to_next': True,
            })
            write_json(appendix_question_page, {
                'cleaned_text': (
                    '附件 本學習指引參考書目\n'
                    '（D）不應被當成第四個選項\n'
                    '99. 附件中的數字不可成為題目'
                ),
                'continues_to_next': True,
            })
            questions = exercise_export.parse_questions(
                [question_page, appendix_question_page], self.subject(), set(),
            )
            self.assertEqual([question['number'] for question in questions], [1])
            self.assertEqual(questions[0]['options']['A'], '參考書目管理')

            answer_page = root / 'answers/page_005.json'
            appendix_answer_page = root / 'answers/page_006.json'
            write_json(answer_page, {
                'cleaned_text': (
                    '1. Ans（B）\n'
                    '解析：正常說明可以提到一般參考書目，但不是附件標題。'
                ),
                'continues_to_next': True,
            })
            write_json(appendix_answer_page, {
                'cleaned_text': (
                    '附件 本學習指引參考書目\n書名\n作者\n'
                    '99. Ans（A）\n附件內容不可成為答案'
                ),
                'continues_to_next': True,
            })
            answers = exercise_export.parse_answers(
                [answer_page, appendix_answer_page], self.subject(), set(),
            )
            self.assertEqual([answer['number'] for answer in answers], [1])
            self.assertEqual(
                answers[0]['explanation'],
                '解析：正常說明可以提到一般參考書目，但不是附件標題。',
            )

    def test_prewrite_gate_rejects_bleed_id_drift_and_card_loss(self) -> None:
        previous = {
            'chapters': [{
                'id': 's1c1',
                'questions': [{
                    'id': 's1c1gq001',
                    'question': '題目',
                    'options': {'A': '甲', 'B': '乙', 'C': '丙', 'D': '丁'},
                    'explanation': '正常解析',
                    'card': {'concept': '概念', 'confusion': '混淆'},
                }],
            }],
        }
        rebuilt = copy.deepcopy(previous)
        exercise_export.validate_export_payload(rebuilt, previous)

        bleed = copy.deepcopy(rebuilt)
        bleed['chapters'][0]['questions'][0]['explanation'] += '附件 本學習指引參考書目書名作者'
        with self.assertRaisesRegex(ValueError, 'bibliography appendix bleed'):
            exercise_export.validate_export_payload(bleed, previous)

        with self.assertRaisesRegex(ValueError, 'question IDs changed'):
            exercise_export.validate_export_payload({'chapters': []}, previous)

        missing_card = copy.deepcopy(rebuilt)
        missing_card['chapters'][0]['questions'][0].pop('card')
        with self.assertRaisesRegex(ValueError, 'card was not preserved exactly'):
            exercise_export.validate_export_payload(missing_card, previous)

    def test_committed_production_has_179_clean_carded_questions(self) -> None:
        level_counts: dict[str, int] = {}
        card_count = 0
        paths = sorted(BASE.glob('data/*/questions/subject*_guide_exercises.json'))
        self.assertEqual(len(paths), 5)
        for path in paths:
            payload = json.loads(path.read_text(encoding='utf-8'))
            exercise_export.validate_export_payload(payload)
            questions = exercise_export.payload_questions(payload)
            level = path.parts[-3]
            level_counts[level] = level_counts.get(level, 0) + len(questions)
            card_count += sum(isinstance(question.get('card'), dict) for question in questions)
        self.assertEqual(level_counts, {'初級': 69, '中級': 110})
        self.assertEqual(sum(level_counts.values()), 179)
        self.assertEqual(card_count, 179)


class GuideOutlineTransactionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.old_base = outline_export.BASE
        self.old_export_level = outline_export.export_level
        outline_export.BASE = self.root
        self.generated = self.root / 'frontend' / 'src' / 'generated'

    def tearDown(self) -> None:
        outline_export.BASE = self.old_base
        outline_export.export_level = self.old_export_level
        self.temp.cleanup()

    def seed_live_outputs(self) -> Path:
        initial_ref = self.generated / 'guideContent' / '初級-guide1' / 'old.json'
        middle_ref = self.generated / 'guideContent' / '中級-guide2' / 'keep.json'
        write_json(initial_ref, valid_guide_content('s1c1', 'old'))
        write_json(middle_ref, valid_guide_content('mid-s2c1', 'keep'))
        write_json(self.generated / 'guideOutlines.json', {
            'levels': ['初級', '中級'],
            'guides': {
                's1': minimal_guide('初級', 's1', '初級-guide1', 'old.json'),
                'mid-s2': minimal_guide('中級', 'mid-s2', '中級-guide2', 'keep.json'),
            },
        })
        return middle_ref

    def test_partial_level_export_preserves_other_level(self) -> None:
        self.seed_live_outputs()

        def fake_export(level: str, content_dir: Path) -> dict:
            self.assertEqual(level, '初級')
            write_json(
                content_dir / '初級-guide1' / 'new.json',
                valid_guide_content('s1c1', 'new'),
            )
            return {'s1': minimal_guide('初級', 's1', '初級-guide1', 'new.json')}

        outline_export.export_level = fake_export
        result = outline_export.export(['初級'])

        self.assertEqual(set(result['guides']), {'s1', 'mid-s2'})
        self.assertTrue((self.generated / 'guideContent' / '中級-guide2' / 'keep.json').exists())
        self.assertTrue((self.generated / 'guideContent' / '初級-guide1' / 'new.json').exists())
        self.assertFalse((self.generated / 'guideContent' / '初級-guide1' / 'old.json').exists())

    def test_validation_failure_keeps_live_outputs_unchanged(self) -> None:
        self.seed_live_outputs()
        before_outline = (self.generated / 'guideOutlines.json').read_bytes()
        before_initial = (self.generated / 'guideContent' / '初級-guide1' / 'old.json').read_bytes()
        before_middle = (self.generated / 'guideContent' / '中級-guide2' / 'keep.json').read_bytes()

        def invalid_export(_level: str, content_dir: Path) -> dict:
            write_json(content_dir / '初級-guide1' / 'partial.json', {'partial': True})
            return {
                's1': minimal_guide('初級', 's1', '初級-guide1', 'missing.json'),
            }

        outline_export.export_level = invalid_export
        with self.assertRaisesRegex(ValueError, 'missing content file'):
            outline_export.export(['初級'])

        self.assertEqual((self.generated / 'guideOutlines.json').read_bytes(), before_outline)
        self.assertEqual((self.generated / 'guideContent' / '初級-guide1' / 'old.json').read_bytes(), before_initial)
        self.assertEqual((self.generated / 'guideContent' / '中級-guide2' / 'keep.json').read_bytes(), before_middle)
        self.assertFalse(any(path.name.startswith('.guideContent.staging-') for path in self.generated.iterdir()))

    def test_invalid_content_schema_keeps_live_outputs_unchanged(self) -> None:
        self.seed_live_outputs()
        content_dir = self.generated / 'guideContent'
        outlines_path = self.generated / 'guideOutlines.json'
        before_outline = outlines_path.read_bytes()
        before_initial = (content_dir / '初級-guide1' / 'old.json').read_bytes()
        before_middle = (content_dir / '中級-guide2' / 'keep.json').read_bytes()

        def invalid_export(_level: str, staged_dir: Path) -> dict:
            write_json(staged_dir / '初級-guide1' / 'invalid.json', {
                'id': 's1c1',
                'content': '# looks present',
                'contentFormat': 'markdown',
                'blocks': [],
                'sourcePages': [],
            })
            return {'s1': minimal_guide('初級', 's1', '初級-guide1', 'invalid.json')}

        outline_export.export_level = invalid_export
        with self.assertRaisesRegex(ValueError, 'blocks must be a non-empty'):
            outline_export.export(['初級'])

        self.assertEqual(outlines_path.read_bytes(), before_outline)
        self.assertEqual((content_dir / '初級-guide1' / 'old.json').read_bytes(), before_initial)
        self.assertEqual((content_dir / '中級-guide2' / 'keep.json').read_bytes(), before_middle)
        self.assertFalse((content_dir / '初級-guide1' / 'invalid.json').exists())

    def test_commit_failure_rolls_back_both_live_outputs(self) -> None:
        self.seed_live_outputs()
        content_dir = self.generated / 'guideContent'
        outlines_path = self.generated / 'guideOutlines.json'
        before_outline = outlines_path.read_bytes()
        before_initial = (content_dir / '初級-guide1' / 'old.json').read_bytes()
        staged_content = self.generated / '.guideContent.manual-staging'
        write_json(staged_content / '初級-guide1' / 'new.json', {'new': True})

        with self.assertRaises(FileNotFoundError):
            outline_export._commit_staged_outputs(
                staged_content,
                content_dir,
                self.generated / '.missing-staged-outlines.json',
                outlines_path,
            )

        self.assertEqual(outlines_path.read_bytes(), before_outline)
        self.assertEqual((content_dir / '初級-guide1' / 'old.json').read_bytes(), before_initial)
        self.assertFalse((content_dir / '初級-guide1' / 'new.json').exists())

    def test_commit_failure_rolls_back_existing_and_new_public_assets(self) -> None:
        self.seed_live_outputs()
        content_dir = self.generated / 'guideContent'
        outlines_path = self.generated / 'guideOutlines.json'
        before_outline = outlines_path.read_bytes()
        before_initial = (content_dir / '初級-guide1' / 'old.json').read_bytes()
        public_root = self.root / 'frontend' / 'public'
        existing_relative = Path('pdf-assets/初級/guide1/page_001/existing.bin')
        new_relative = Path('pdf-assets/初級/guide1/page_001/new.bin')
        existing_live = public_root / existing_relative
        existing_live.parent.mkdir(parents=True, exist_ok=True)
        existing_live.write_bytes(b'live-existing')

        staged_content = self.generated / '.guideContent.manual-staging-assets'
        write_json(staged_content / '初級-guide1' / 'new.json', {'new': True})
        staged_public = self.root / 'frontend' / '.track-a-public.staging-manual'
        (staged_public / existing_relative).parent.mkdir(parents=True, exist_ok=True)
        (staged_public / existing_relative).write_bytes(b'staged-existing')
        (staged_public / new_relative).write_bytes(b'staged-new')

        with self.assertRaises(FileNotFoundError):
            outline_export._commit_staged_outputs(
                staged_content,
                content_dir,
                self.generated / '.missing-staged-outlines-assets.json',
                outlines_path,
                staged_public_root=staged_public,
                public_root=public_root,
                asset_relative_paths=[existing_relative, new_relative],
            )

        self.assertEqual(outlines_path.read_bytes(), before_outline)
        self.assertEqual((content_dir / '初級-guide1' / 'old.json').read_bytes(), before_initial)
        self.assertEqual(existing_live.read_bytes(), b'live-existing')
        self.assertFalse((public_root / new_relative).exists())
        self.assertFalse(staged_public.exists())
        self.assertFalse(any(path.name.startswith('.track-a-assets.backup-') for path in public_root.iterdir()))

    def test_staged_publication_structure_failure_prevents_all_live_commits(self) -> None:
        self.seed_live_outputs()
        content_dir = self.generated / 'guideContent'
        outlines_path = self.generated / 'guideOutlines.json'
        before_outline = outlines_path.read_bytes()
        before_initial = (content_dir / '初級-guide1' / 'old.json').read_bytes()
        before_middle = (content_dir / '中級-guide2' / 'keep.json').read_bytes()
        public_root = self.root / 'frontend' / 'public'
        existing_relative = Path('pdf-assets/初級/guide1/page_001/existing.bin')
        new_relative = Path('pdf-assets/中級/guide1/page_001/new.bin')
        existing_live = public_root / existing_relative
        existing_live.parent.mkdir(parents=True, exist_ok=True)
        existing_live.write_bytes(b'live-existing')

        def fake_export(level: str, staged_dir: Path) -> dict:
            subject_id = 's1' if level == '初級' else 'mid-s1'
            node_id = f'{subject_id}c1'
            content_key = f'{level}-guide1'
            content_ref = f'{node_id}.json'
            write_json(staged_dir / content_key / content_ref, valid_guide_content(node_id, level))
            return {subject_id: minimal_guide(level, subject_id, content_key, content_ref)}

        def fake_stage(_levels: list[str], staged_public: Path) -> list[Path]:
            for relative, content in (
                (existing_relative, b'staged-existing'),
                (new_relative, b'staged-new'),
            ):
                target = staged_public / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
            return [existing_relative, new_relative]

        semantic_failure = {
            'remaining': 0,
            'failures': [],
            'publication_overlay_remaining': 0,
            'publication_overlay_failures': [],
            'publication_structure_remaining': 1,
            'publication_structure_failures': ['manual-heading:s1c2-hypothesis'],
        }
        outline_export.export_level = fake_export
        with mock.patch.object(outline_export, '_stage_track_a_visual_assets', fake_stage), \
                mock.patch.object(outline_export, 'audit_generated_track_a', return_value=semantic_failure):
            with self.assertRaisesRegex(ValueError, 'staged Track-A semantic gate failed'):
                outline_export.export(['初級', '中級'])

        self.assertEqual(outlines_path.read_bytes(), before_outline)
        self.assertEqual((content_dir / '初級-guide1' / 'old.json').read_bytes(), before_initial)
        self.assertEqual((content_dir / '中級-guide2' / 'keep.json').read_bytes(), before_middle)
        self.assertEqual(existing_live.read_bytes(), b'live-existing')
        self.assertFalse((public_root / new_relative).exists())
        self.assertFalse(any(path.name.startswith('.track-a-public.staging-') for path in (self.root / 'frontend').iterdir()))
        self.assertFalse(any(path.name.startswith('.guideContent.staging-') for path in self.generated.iterdir()))


class GalleryPartialMergeTest(unittest.TestCase):
    def test_partial_level_manifest_keeps_other_levels(self) -> None:
        existing = {
            'levels': ['初級', '中級'],
            'items': [
                {'level': '初級', 'key': 'guide1', 'type': 'image', 'page_number': 1, 'asset_id': 'old'},
                {'level': '中級', 'key': 'guide2', 'type': 'table', 'page_number': 2, 'asset_id': 'keep'},
            ],
        }
        replacement = {
            'level': '初級',
            'items': [
                {'level': '初級', 'key': 'guide1', 'type': 'image', 'page_number': 3, 'asset_id': 'new'},
            ],
        }
        merged = gallery_export.merge_gallery_manifests(existing, [replacement])
        self.assertEqual(merged['levels'], ['初級', '中級'])
        self.assertEqual({item['asset_id'] for item in merged['items']}, {'new', 'keep'})
        self.assertEqual(merged['total'], 2)

    def test_single_level_export_calls_manifest_writer(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old_base = gallery_export.BASE
            gallery_export.BASE = root
            try:
                (root / 'data' / '初級' / 'page_extract').mkdir(parents=True)
                manifest = gallery_export.export_gallery('初級', force=False)
                written = json.loads(
                    (root / 'frontend' / 'src' / 'generated' / 'pdfGallery.json')
                    .read_text(encoding='utf-8')
                )
                self.assertEqual(manifest['level'], '初級')
                self.assertEqual(written['levels'], ['初級'])
                self.assertEqual(written['items'], [])
            finally:
                gallery_export.BASE = old_base


class AssetPublishConfigurationTest(unittest.TestCase):
    def test_dotenv_bucket_is_resolved_after_loading(self) -> None:
        previous_bucket = os.environ.pop('R2_BUCKET', None)
        old_base = publish_assets.BASE
        try:
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                publish_assets.BASE = root
                (root / '.env').write_text('R2_BUCKET=project-assets\n', encoding='utf-8')
                publish_assets.load_dotenv()
                self.assertEqual(publish_assets.configured_bucket(None), 'project-assets')
                self.assertEqual(publish_assets.configured_bucket('cli-assets'), 'cli-assets')
        finally:
            publish_assets.BASE = old_base
            if previous_bucket is None:
                os.environ.pop('R2_BUCKET', None)
            else:
                os.environ['R2_BUCKET'] = previous_bucket


class CjkParenthesisNormalizationTest(unittest.TestCase):
    """User decision 2026-11-01: half-width → full-width only in Chinese context."""

    POSITIVE = {
        '規則式方法\n( Rule-based )': '規則式方法\n（Rule-based）',
        '虛無假設 (B) 我們在 95% 的信心水準': '虛無假設 （B） 我們在 95% 的信心水準',
        '(1)基本原理': '（1）基本原理',
        'AI(人工智慧)': 'AI（人工智慧）',
        # 2026-11-02: no space between Chinese text and a converted pair (3-27 image).
        '人工智慧 (Artificial Intelligence, AI) 是': '人工智慧（Artificial Intelligence, AI）是',
        '<td>分詞<br />(Tokenization)</td>': '<td>分詞<br />（Tokenization）</td>',
        '選項(1)(B)': '選項（1）（B）',
        '說明(見(A)項)': '說明（見（A）項）',
        '(2022 年)': '（2022 年）',
        '檢定 (test)': '檢定（test）',
        # 2026-11-01 review: math spans inside a Chinese parenthetical are opaque.
        'Type I 錯誤 ( $ \\alpha $)': 'Type I 錯誤（$ \\alpha $）',
        '$ \\alpha=P $ (拒絕 $ H_0 $ | $ H_0 $為真)': '$ \\alpha=P $ （拒絕 $ H_0 $ | $ H_0 $為真）',
        # 2026-11-02: a spaced function application directly followed by Chinese
        # text is printed full-width without spaces (初級 guide1 3-27).
        '以 T=T (X) 表之': '以 T=T（X）表之',
        # Enumerator/option labels keep their separating spaces.
        '下列何者？ (A) 甲 (B) 乙': '下列何者？ （A） 甲 （B） 乙',
    }
    NEGATIVE = [
        'f(x)',
        'f(x) 的值域',
        'TF(t, d)= 文檔d 中的出現次數',
        '座標 (x, y) 表示位置',
        'This is (very) good.',
        'Call print(x) then (optionally) exit.',
        '`print("你好")` 會輸出',
        'print("你好") 會輸出',
        '$f(x)$ 的值',
        '公式 $$P(A|B) = \\frac{P(A \\cap B)}{P(B)}$$ 成立',
        '\\(x\\) 是變數',
        '( $ a $ = 0.05 ) 顯著',
        'P($A$) 的值',
        'P ( $ A $) 的值',
        '計算 E($X$)',
        '[連結](#31人工智慧)',
        '中位數= 𝑥(𝑛+1 2 )',
        '( 𝑘) 二項係數',
        '令 T=T (X)',
        '以 T=T (X)\n表之',
        'T=T (X), P (A)',
        '(p < 0.05) 顯著',
        '給定詞序列 S = (ω1, ω2)',
        '最後一項 m) 不成對',
        '空括號 ( ) 不動',
        '變數 (x) 代表輸入',
        '(1, 2) 是座標',
    ]

    def test_chinese_context_is_converted(self) -> None:
        for source, expected in self.POSITIVE.items():
            with self.subTest(source=source):
                self.assertEqual(normalize_cjk_parentheses(source), expected)

    def test_latin_math_code_and_latex_are_untouched(self) -> None:
        for source in self.NEGATIVE:
            with self.subTest(source=source):
                self.assertEqual(normalize_cjk_parentheses(source), source)

    def test_idempotent(self) -> None:
        for source in [*self.POSITIVE, *self.POSITIVE.values(), *self.NEGATIVE]:
            once = normalize_cjk_parentheses(source)
            self.assertEqual(normalize_cjk_parentheses(once), once, source)

    def test_block_fields_and_table_html_follow_rows(self) -> None:
        table = {
            'id': 'block-1', 'type': 'table', 'anchor': 'keep-(a)',
            'rows': [['技術階段'], ['規則式方法\n( Rule-based )']],
        }
        table['html'] = outline_export.table_rows_to_html(table['rows'])
        heading = {
            'id': 'block-2', 'type': 'heading', 'title': '(1)基本原理', 'anchor': '1基本原理',
        }
        image = {'id': 'block-3', 'type': 'source_image', 'alt': '原圖 (A)圖'}
        formula = {
            'id': 'block-4', 'type': 'paragraph', 'text': '公式如下 (見下)',
            'formulas': [{'latex': 'f(x) = (a+b)'}],
        }
        published = outline_export.normalize_published_block_parentheses(
            [table, heading, image, formula]
        )
        self.assertEqual(published[0]['rows'][1][0], '規則式方法\n（Rule-based）')
        self.assertEqual(published[0]['html'], outline_export.table_rows_to_html(published[0]['rows']))
        self.assertIn('（Rule-based）', published[0]['html'])
        self.assertEqual(published[0]['anchor'], 'keep-(a)')
        self.assertEqual(published[1]['title'], '（1）基本原理')
        self.assertEqual(published[1]['anchor'], '1基本原理')
        self.assertEqual(published[2], image)  # alt is a Track A source signature
        self.assertEqual(published[3]['text'], '公式如下（見下）')
        self.assertEqual(published[3]['formulas'], formula['formulas'])
        self.assertEqual(table['rows'][1][0], '規則式方法\n( Rule-based )')  # input not mutated
        self.assertEqual(
            outline_export.normalize_published_block_parentheses(published), published
        )
        self.assertEqual(normalize_block_parentheses(published[1]), published[1])


def content_block(block_id: str, text: str, page: int = 1, block_type: str = 'paragraph') -> dict:
    return {'id': block_id, 'type': block_type, 'text': text, 'pageIndex': page}


class GuideBlockIdMigrationTest(unittest.TestCase):
    """Old citation/heading ids are remapped at export and fail closed."""

    GUIDE = '初級-guide1'
    NODE = 's1c1'

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        # Rebuild inserted 「新段落」 at the top, so every id shifted by one;
        # old block-3 (one giant block) was split and is unmapped.
        self.content = {self.GUIDE: {self.NODE: [
            content_block('block-1', '新段落'),
            content_block('block-2', '第一段'),
            content_block('block-3', '第二段'),
            content_block('block-4', '眾數代表出現頻率最高的數值', 2),
            content_block('block-5', '平均數受極端值影響', 2),
        ]}}
        self.questions = [
            {'id': 'sample_q1', 'question': '題一', 'options': {'A': 'a', 'B': 'b'}, 'answer': 'A'},
            {'id': 'sample_q2', 'question': '題二', 'options': {'A': 'a', 'B': 'b'}, 'answer': 'B'},
        ]

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def citation(*block_ids: str, why: str = '說明') -> dict:
        return {'guide_key': 'guide1', 'node_id': 's1c1', 'title': 't', 'page_label': '1-1',
                'block_ids': list(block_ids), 'why_relevant': why}

    def answers(self) -> dict:
        return {
            'sample_q1': {'answer': 'A', 'citations': [self.citation('block-1', 'block-2')]},
            'sample_q2': {'answer': 'B', 'citations': [
                self.citation('block-3', why='說明眾數'),
                self.citation('block-2'),
            ]},
        }

    def table(self, answers: dict | None = None, **changes) -> dict:
        table = {
            'schemaVersion': 1,
            'from': {'gitRef': 'fixture'},
            'to': {'guideSha256': {self.GUIDE: guide_content_sha256(self.content[self.GUIDE])}},
            'blocks': {self.GUIDE: {self.NODE: {
                'block-1': {'new': 'block-2', 'method': 'exact'},
                'block-2': {'new': 'block-3', 'method': 'normalized'},
                'block-3': {'new': None, 'method': 'unmapped', 'ratio': 0.2},
            }}},
            'citationScope': {'初級/sample': reference_answers_digest(answers or self.answers())},
            'citationScopeExcluded': [],
            'imageUnitsScope': {},
            'citations': [],
        }
        table.update(changes)
        return table

    def override(self, action: str = 'remove', **changes) -> dict:
        entry = {
            'level': '初級', 'exam': 'sample', 'questionId': 'sample_q2', 'citationIndex': 0,
            'guideKey': self.GUIDE, 'nodeId': self.NODE, 'oldBlockId': 'block-3',
            'action': action, 'reason': 'fixture',
        }
        if action == 'remap':
            entry['newBlockIds'] = ['block-4']
        entry.update(changes)
        return entry

    def test_remap_and_override_removal_keep_other_citations(self) -> None:
        migration = BlockIdMigration(self.table(), [self.override('remove')], self.content)
        migrated, stats = migration.migrate_reference_answers('初級', 'sample', self.answers())
        self.assertEqual(migrated['sample_q1']['citations'][0]['block_ids'], ['block-2', 'block-3'])
        q2 = migrated['sample_q2']['citations']
        self.assertEqual(len(q2), 1)  # the citation that only had block-3 is dropped
        self.assertEqual(q2[0]['block_ids'], ['block-3'])
        self.assertEqual(stats['droppedCitations'], 1)
        migration.check_unused_overrides('初級', ['sample'])

    def test_manual_remap_and_auto_citation_resolution(self) -> None:
        manual = BlockIdMigration(self.table(), [self.override('remap')], self.content)
        migrated, _ = manual.migrate_reference_answers('初級', 'sample', self.answers())
        self.assertEqual(migrated['sample_q2']['citations'][0]['block_ids'], ['block-4'])

        auto = self.table(citations=[{
            'level': '初級', 'exam': 'sample', 'questionId': 'sample_q2', 'citationIndex': 0,
            'guideKey': self.GUIDE, 'nodeId': self.NODE, 'oldBlockId': 'block-3',
            'newBlockIds': ['block-4'], 'method': 'auto-citation',
        }])
        migrated, _ = BlockIdMigration(auto, [], self.content).migrate_reference_answers(
            '初級', 'sample', self.answers()
        )
        self.assertEqual(migrated['sample_q2']['citations'][0]['block_ids'], ['block-4'])

    def test_unmapped_without_override_fails_closed(self) -> None:
        migration = BlockIdMigration(self.table(), [], self.content)
        with self.assertRaisesRegex(BlockIdMigrationError, 'block-3 is unmapped'):
            migration.migrate_reference_answers('初級', 'sample', self.answers())

    def test_unknown_id_fails_closed_even_without_table(self) -> None:
        answers = {'sample_q1': {'answer': 'A', 'citations': [self.citation('block-99')]}}
        with self.assertRaisesRegex(BlockIdMigrationError, 'block-99'):
            BlockIdMigration(None, [], self.content).migrate_reference_answers(
                '初級', 'sample', answers
            )
        removal = self.override('remove', questionId='sample_q1', oldBlockId='block-99')
        migrated, _ = BlockIdMigration(None, [removal], self.content).migrate_reference_answers(
            '初級', 'sample', answers
        )
        self.assertEqual(migrated['sample_q1']['citations'], [])

    def test_out_of_scope_input_is_validated_but_never_remapped(self) -> None:
        table = self.table(citationScope={})
        regenerated = {'sample_q1': {'answer': 'A', 'citations': [self.citation('block-2')]}}
        migrated, _ = BlockIdMigration(table, [], self.content).migrate_reference_answers(
            '初級', 'sample', regenerated
        )
        self.assertEqual(migrated, regenerated)

    def test_changed_scope_input_or_stale_content_fails(self) -> None:
        changed = self.answers()
        changed['sample_q1']['citations'][0]['why_relevant'] = 'regenerated'
        with self.assertRaisesRegex(BlockIdMigrationError, 'exclude-citation-scope'):
            BlockIdMigration(self.table(), [], self.content).migrate_reference_answers(
                '初級', 'sample', changed
            )
        stale = copy.deepcopy(self.content)
        stale[self.GUIDE][self.NODE][0]['text'] = '再次改版'
        with self.assertRaisesRegex(BlockIdMigrationError, 'stale'):
            BlockIdMigration(self.table(), [], stale)

    def test_citation_block_ids_follow_document_order(self) -> None:
        # 2026-11-02: the guide link scrolls to the first listed block, so an
        # override/auto remap that lists blocks out of order must be re-sorted.
        answers = {
            'sample_q1': {'answer': 'A', 'citations': [
                self.citation('block-5', 'block-2', 'block-4'),
                self.citation('block-3'),
            ]},
            'sample_q2': {'answer': 'B'},
        }
        ordered, reordered = reference_export.order_citation_block_ids('初級', answers, self.content)
        self.assertEqual(reordered, 1)
        self.assertEqual(
            ordered['sample_q1']['citations'][0]['block_ids'], ['block-2', 'block-4', 'block-5'],
        )
        self.assertEqual(ordered['sample_q1']['citations'][1]['block_ids'], ['block-3'])
        self.assertEqual(ordered['sample_q2'], {'answer': 'B'})
        self.assertEqual(answers['sample_q1']['citations'][0]['block_ids'], ['block-5', 'block-2', 'block-4'])
        again, second = reference_export.order_citation_block_ids('初級', ordered, self.content)
        self.assertEqual((again, second), (ordered, 0))

    def test_unused_override_is_rejected(self) -> None:
        migration = BlockIdMigration(
            self.table(), [self.override('remove'), self.override('remove', questionId='sample_q9')],
            self.content,
        )
        migration.migrate_reference_answers('初級', 'sample', self.answers())
        with self.assertRaisesRegex(BlockIdMigrationError, 'sample_q9'):
            migration.check_unused_overrides('初級', ['sample'])

    def write_reference_fixture(self) -> Path:
        run_root = self.root / 'data/初級/pipeline/exam_reference_answers/sample'
        write_json(self.root / 'data/初級/questions/sample_exam.json', {'questions': self.questions})
        for question, answer in zip(self.questions, self.answers().values()):
            output = run_root / 'outputs' / f"{question['id']}.json"
            write_json(output, {
                'level': '初級', 'exam_key': 'sample', 'question_id': question['id'],
                'answer': question['answer'], 'citations': answer['citations'],
            })
            write_output_provenance(output, question_content_fingerprint(question), question['id'])
        return run_root

    def run_reference_export(self, migration: BlockIdMigration) -> Path:
        self.write_reference_fixture()
        out = self.root / 'out'
        exam = {'key': 'sample', 'routeKey': 'sample', 'questionFile': 'sample_exam.json'}
        with mock.patch.object(reference_export, 'ROOT', self.root), \
                mock.patch.object(reference_export, 'OVERLAY_PATH', self.root / 'none.json'), \
                mock.patch.object(reference_export, 'exam_entries', lambda level: [exam]):
            reference_export.export_reference_answers('初級', out, migration=migration)
        return out

    def test_reference_exporter_rewrites_citations_and_fails_closed(self) -> None:
        compact = {
            question['id']: {'answer': question['answer'], 'citations': answer['citations']}
            for question, answer in zip(self.questions, self.answers().values())
        }
        migration = BlockIdMigration(self.table(compact), [self.override('remap')], self.content)
        out = self.run_reference_export(migration)
        published = json.loads((out / 'sample.json').read_text(encoding='utf-8'))
        self.assertEqual(published['sample_q1']['citations'][0]['block_ids'], ['block-2', 'block-3'])
        self.assertEqual(published['sample_q2']['citations'][0]['block_ids'], ['block-4'])
        self.assertEqual(published['sample_q2']['citations'][1]['block_ids'], ['block-3'])

        failing = BlockIdMigration(self.table(compact), [], self.content)
        (out / 'sample.json').unlink()
        with self.assertRaises(BlockIdMigrationError):
            self.run_reference_export(failing)
        self.assertFalse((out / 'sample.json').exists())

    def test_image_heading_ids_are_remapped_in_scope_and_validated(self) -> None:
        # Both ids the unit can land on are headings titled after the unit
        # (numbering differs), so the heading-alignment check passes either way.
        blocks = self.content[self.GUIDE][self.NODE]
        blocks[0] = {**blocks[0], 'type': 'heading', 'title': 'A. 資料清洗'}
        blocks[1] = {**blocks[1], 'type': 'heading', 'title': '（1）資料清洗'}
        units_file = self.root / 'units.json'
        public = self.root / 'images'
        (public / 'a.webp').parent.mkdir(parents=True)
        (public / 'a.webp').write_bytes(b'x')
        unit = {'id': 'u1', 'level': '初級', 'guideKey': 'guide1', 'sourceNodeId': 's1c1',
                'headingBlockId': 'block-1', 'title': '1. 資料清洗', 'output': 'a.webp'}
        write_json(units_file, {'units': [unit]})
        scope = {units_file.as_posix(): sha256_bytes(units_file.read_bytes())}
        migration = BlockIdMigration(self.table(imageUnitsScope=scope), [], self.content)
        result = images_export.export_images(units_file, self.root / 'img.json', public, migration=migration)
        self.assertEqual(result['images'][0]['headingBlockId'], 'block-2')

        out_of_scope = BlockIdMigration(self.table(), [], self.content)
        result = images_export.export_images(units_file, self.root / 'img.json', public, migration=out_of_scope)
        self.assertEqual(result['images'][0]['headingBlockId'], 'block-1')

        write_json(units_file, {'units': [{**unit, 'headingBlockId': 'block-77'}]})
        with self.assertRaisesRegex(BlockIdMigrationError, 'block-77'):
            images_export.export_images(units_file, self.root / 'img.json', public, migration=out_of_scope)
        with self.assertRaisesRegex(BlockIdMigrationError, 'changed since'):
            images_export.export_images(units_file, self.root / 'img.json', public, migration=migration)

    def test_image_heading_alignment_fails_closed_with_reasoned_allowlist(self) -> None:
        blocks = self.content[self.GUIDE][self.NODE]
        blocks[0] = {**blocks[0], 'type': 'heading', 'title': '（2）金融：'}
        content = self.content
        unit = {'id': 'u1', 'level': '初級', 'guideKey': 'guide1', 'sourceNodeId': 's1c1',
                'headingBlockId': 'block-1', 'title': '（2） 金融：'}
        check = images_export.check_heading_alignment
        check([unit], content, allowlist={})  # NFKC + whitespace-insensitive match

        paragraph = {**unit, 'headingBlockId': 'block-2'}
        with self.assertRaisesRegex(images_export.HeadingAlignmentError, 'paragraph block, not a heading'):
            check([paragraph], content, allowlist={})
        wrong_heading = {**unit, 'title': '（3）製造業：'}
        with self.assertRaisesRegex(images_export.HeadingAlignmentError, 'does not match unit title'):
            check([wrong_heading], content, allowlist={})
        with self.assertRaisesRegex(images_export.HeadingAlignmentError, 'block does not exist'):
            check([{**unit, 'headingBlockId': 'block-99'}], content, allowlist={})

        allow = {'u1': {'headingBlockId': 'block-2', 'reason': '原書此圖卡錨定段落'}}
        check([paragraph], content, allowlist=allow)
        for bad_allow, message in [
            ({'u1': {'headingBlockId': 'block-2', 'reason': ' '}}, 'lacks a reason'),
            ({'u1': {'headingBlockId': 'block-3', 'reason': 'x'}}, 'entry is for block-3'),
            ({'u9': {'headingBlockId': 'block-2', 'reason': 'x'}}, 'no such image unit'),
        ]:
            with self.assertRaisesRegex(images_export.HeadingAlignmentError, message):
                check([paragraph], content, allowlist=bad_allow)
        with self.assertRaisesRegex(images_export.HeadingAlignmentError, 'already aligned'):
            check([unit], content, allowlist={'u1': {'headingBlockId': 'block-1', 'reason': 'x'}})

        # export_images runs the check after migration and writes nothing on failure.
        units_file = self.root / 'units.json'
        public = self.root / 'images'
        (public / 'a.webp').parent.mkdir(parents=True)
        (public / 'a.webp').write_bytes(b'x')
        write_json(units_file, {'units': [{**paragraph, 'output': 'a.webp'}]})
        out = self.root / 'img.json'
        migration = BlockIdMigration(self.table(), [], content)
        with self.assertRaises(images_export.HeadingAlignmentError):
            images_export.export_images(units_file, out, public, migration=migration)
        self.assertFalse(out.exists())

    def test_published_image_units_are_anchored_to_their_headings(self) -> None:
        units = json.loads(
            (BASE / 'data/共用/image_units_all_levels.json').read_text(encoding='utf-8')
        )['units']
        content = load_content_tree(BASE / 'frontend/src/generated/guideContent')
        images_export.check_heading_alignment(units, content)
        published = json.loads(
            (BASE / 'frontend/src/generated/guideImages.json').read_text(encoding='utf-8')
        )['images']
        images_export.check_heading_alignment(published, content)
        self.assertEqual(len(published), len(units))


class GuideBlockIdMigrationBuilderTest(unittest.TestCase):
    def test_node_mapping_methods_and_split_block_window(self) -> None:
        old = [
            content_block('block-1', '標題', block_type='heading'),
            content_block('block-2', '規則式方法\n( Rule-based )'),
            content_block('block-3', '舊的巨型區塊：眾數代表出現頻率最高的數值。平均數受極端值影響。'),
            content_block('block-4', '機器學習是一種從資料中學習規律的方法'),
            content_block('block-5', '結尾'),
        ]
        new = [
            content_block('block-1', '插入的新段落'),
            content_block('block-2', '標題', block_type='heading'),
            content_block('block-3', '規則式方法\n（Rule-based）'),
            content_block('block-4', '眾數代表出現頻率最高的數值。'),
            content_block('block-5', '平均數受極端值影響。'),
            content_block('block-6', '機器學習是一種從資料中學習規律的方法論'),
            content_block('block-7', '結尾'),
        ]
        mapping = migration_builder.map_node(old, new, 0.8)
        self.assertEqual(mapping['block-1'], {'new': 'block-2', 'method': 'exact'})
        self.assertEqual(mapping['block-2'], {'new': 'block-3', 'method': 'normalized'})
        self.assertEqual(mapping['block-3']['method'], 'unmapped')
        self.assertIsNone(mapping['block-3']['new'])
        self.assertEqual(mapping['block-4']['method'], 'fuzzy')
        self.assertEqual(mapping['block-4']['new'], 'block-6')
        self.assertEqual(mapping['block-5'], {'new': 'block-7', 'method': 'exact'})
        self.assertIsNone(migration_builder.table_entry('block-5', {'new': 'block-5', 'method': 'exact'}))

        window = migration_builder.old_block_window(old, new, mapping, 'block-3')
        self.assertEqual([block['id'] for block in window], ['block-4', 'block-5'])
        resolved = migration_builder.resolve_unmapped_citation(
            old[2], window, new, {'why_relevant': '說明眾數是出現頻率最高的數值'}, None, 0.3,
        )
        self.assertEqual(resolved['status'], 'resolved')
        self.assertEqual(resolved['newBlockIds'], ['block-4'])
        ambiguous = migration_builder.resolve_unmapped_citation(
            old[2], window, new, {'why_relevant': '完全無關的內容'}, None, 0.3,
        )
        self.assertEqual(ambiguous['status'], 'unresolved')
        missing = migration_builder.resolve_unmapped_citation(
            None, None, new, {'why_relevant': 'x'}, None, 0.3,
        )
        self.assertEqual(missing['status'], 'unresolved')

    def test_table_dump_is_deterministic_json(self) -> None:
        payload = {'b': {'block-2': {'new': 'block-3', 'method': 'exact'}}, 'a': [1, 2]}
        text = migration_builder.dump_table(payload)
        self.assertEqual(json.loads(text), payload)
        self.assertIn('"block-2": {"new": "block-3", "method": "exact"}', text)
        self.assertEqual(text, migration_builder.dump_table(json.loads(text)))


if __name__ == '__main__':
    unittest.main()
