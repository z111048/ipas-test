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


if __name__ == '__main__':
    unittest.main()
