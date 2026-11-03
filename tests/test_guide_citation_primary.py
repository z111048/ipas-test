#!/usr/bin/env python3
"""Contract for curated primary guide citations (data/guide_citation_primary.json).

2026-11-03: the exported reference-answer citations used to be whole chunks
copied by the answer generator (about 12% strictly on point in a blind
review).  The curated file now supplies the primary blocks; this test pins
its schema, its binding to the current guideContent, the reader-facing
``why`` rules, and that the export really puts the curated primary first.
Run directly or through tests/test_resource_catalog.py (run_all item 1).
"""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from guide_block_id_migrations import load_content_tree  # noqa: E402
from guide_citation_primary import (  # noqa: E402
    CONTENT_ROOT,
    CURATED_PATH,
    GAPS_PATH,
    SUPPLEMENT_PREFIX,
    block_kind,
    load_node_meta,
    merge_answer_citations,
    validate_payload,
    why_problems,
)
from resource_catalog import exam_entries, level_entries  # noqa: E402

REFERENCE_DIR = ROOT / 'frontend/src/generated/examReferenceAnswers'


def question_number(question_id: str) -> int:
    return int(question_id.rsplit('_q', 1)[1])


class GuideCitationPrimaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads(CURATED_PATH.read_text(encoding='utf-8'))
        cls.content = load_content_tree(CONTENT_ROOT)
        cls.entries = {(e['exam'], e['questionId']): e for e in cls.payload['questions']}
        cls.blocks = {
            (guide, node, str(block.get('id'))): block
            for guide, nodes in cls.content.items()
            for node, blocks in nodes.items()
            for block in blocks
        }

    def test_schema_and_block_binding_are_valid(self) -> None:
        self.assertEqual(validate_payload(self.payload, self.content), [])
        self.assertNotEqual(self.payload['method'], 'manual')
        self.assertRegex(self.payload['generatedOn'], r'^\d{4}-\d{2}-\d{2}$')

    def test_every_published_question_is_curated(self) -> None:
        expected = set()
        for level_config in level_entries():
            level = level_config['dataLevel']
            for exam in exam_entries(level=level):
                questions = json.loads(
                    (ROOT / 'data' / level / 'questions' / exam['questionFile']).read_text(encoding='utf-8')
                )['questions']
                expected |= {(exam['routeKey'], str(q['id'])) for q in questions}
        self.assertEqual(len(expected), 815)
        self.assertEqual(set(self.entries), expected)

    def test_primary_never_cites_chapter_exercises_or_headings(self) -> None:
        for entry in self.payload['questions']:
            for ref in entry['primary']:
                block = self.blocks[(ref['guideKey'], ref['nodeId'], ref['blockId'])]
                self.assertNotIn(block_kind(block), {'exercise_answer', 'exercise_question', 'heading'},
                                 f"{entry['exam']}/{entry['questionId']}")
            for ref in entry['secondary']:
                block = self.blocks[(ref['guideKey'], ref['nodeId'], ref['blockId'])]
                self.assertNotEqual(block_kind(block), 'exercise_question')

    def test_why_is_reader_facing(self) -> None:
        for entry in self.payload['questions']:
            for ref in entry['primary'] + entry['secondary']:
                self.assertEqual(why_problems(ref['why']), [], f"{entry['questionId']}: {ref['why']}")
        for text in ('依候選 C3 判斷', '此段 id 為', '本模型認為', '这段说明'):
            self.assertTrue(why_problems(text), text)
        for text in ('ID3 以資訊增益選分裂屬性', 'C4.5 改用增益比', '生成式 AI 可產生新內容'):
            self.assertEqual(why_problems(text), [], text)

    def test_empty_primary_has_one_or_two_secondary(self) -> None:
        for entry in self.payload['questions']:
            if not entry['primary']:
                self.assertIn(len(entry['secondary']), (1, 2), entry['questionId'])
                self.assertTrue(entry['gap'].strip(), entry['questionId'])

    def test_validation_fails_closed_on_stale_or_invalid_entries(self) -> None:
        entry = next(e for e in self.payload['questions'] if e['primary'])
        cases = {}
        changed = copy.deepcopy(entry)
        changed['primary'][0]['textHash'] = 'sha256:' + '0' * 64
        cases['textHash mismatch'] = changed
        gone = copy.deepcopy(entry)
        gone['primary'][0]['blockId'] = 'block-999999'
        cases['not in the current guideContent'] = gone
        leaky = copy.deepcopy(entry)
        leaky['primary'][0]['why'] = '候選 C2 直接說明'
        cases['internal wording'] = leaky
        exercise_key = next(key for key, block in self.blocks.items()
                            if block_kind(block) == 'exercise_answer' and key[0].startswith(entry['level']))
        exercise = copy.deepcopy(entry)
        exercise['primary'][0].update(guideKey=exercise_key[0], nodeId=exercise_key[1], blockId=exercise_key[2])
        cases['may only be secondary'] = exercise
        empty = copy.deepcopy(entry)
        empty['primary'], empty['secondary'] = [], []
        cases['empty primary needs'] = empty
        for message, bad in cases.items():
            payload = {**self.payload, 'questions': [bad]}
            errors = validate_payload(payload, self.content)
            self.assertTrue(any(message in error for error in errors), (message, errors))

    def test_export_puts_curated_primary_first_and_demotes_the_rest(self) -> None:
        checked = with_primary = 0
        for level_config in level_entries():
            level = level_config['dataLevel']
            for exam in exam_entries(level=level):
                route = exam['routeKey']
                answers = json.loads((REFERENCE_DIR / f'{route}.json').read_text(encoding='utf-8'))
                by_number = {question_number(key): value for key, value in answers.items()}
                for (entry_route, question_id), entry in self.entries.items():
                    if entry_route != route:
                        continue
                    citations = by_number[question_number(question_id)].get('citations') or []
                    checked += 1
                    curated_primary = {(r['guideKey'], r['nodeId'], r['blockId']) for r in entry['primary']}
                    primary_citations = [c for c in citations
                                         if not str(c.get('why_relevant') or '').startswith('補充')]
                    exported_primary = {
                        (f"{level}-{c['guide_key']}", c['node_id'], block_id)
                        for c in primary_citations for block_id in c.get('block_ids') or []
                    }
                    self.assertEqual(exported_primary, curated_primary, f'{route}/{question_id}')
                    if entry['primary']:
                        with_primary += 1
                        first = citations[0]
                        self.assertIn((f"{level}-{first['guide_key']}", first['node_id'], first['block_ids'][0]),
                                      curated_primary, f'{route}/{question_id}')
                        self.assertEqual(citations[:len(primary_citations)], primary_citations)
                    # a curated block is cited exactly once per question (older
                    # citations may still overlap each other, as before 2026-11-03)
                    keys = [(f"{level}-{c['guide_key']}", c['node_id'], b)
                            for c in citations for b in c.get('block_ids') or []]
                    for ref in entry['primary'] + entry['secondary']:
                        key = (ref['guideKey'], ref['nodeId'], ref['blockId'])
                        self.assertEqual(keys.count(key), 1, f'{route}/{question_id} {key}')
        self.assertEqual(checked, 815)
        self.assertGreater(with_primary, 0)

    def test_merge_dedupes_and_prefixes_older_citations(self) -> None:
        entry = next(e for e in self.payload['questions'] if e['primary'])
        ref = entry['primary'][0]
        level = entry['level']
        guide_key = ref['guideKey'].removeprefix(f'{level}-')
        answer = {'citations': [
            {'guide_key': guide_key, 'node_id': ref['nodeId'], 'title': 't', 'page_label': None,
             'block_ids': [ref['blockId']], 'why_relevant': '舊引用'},
            {'guide_key': guide_key, 'node_id': ref['nodeId'], 'title': 't', 'page_label': None,
             'block_ids': [ref['blockId'], 'block-x'], 'why_relevant': '補充舊說明'},
        ]}
        merged = merge_answer_citations(level, answer, entry, load_node_meta())['citations']
        older = merged[-1]
        self.assertEqual(older['block_ids'], ['block-x'])
        self.assertEqual(older['why_relevant'], '補充舊說明')
        self.assertFalse(merged[0]['why_relevant'].startswith(SUPPLEMENT_PREFIX))
        self.assertTrue(all(c['why_relevant'].startswith('補充') for c in merged[len({
            (r['guideKey'], r['nodeId']) for r in entry['primary']}):]))

    def test_gap_list_stays_internal(self) -> None:
        gaps = json.loads(GAPS_PATH.read_text(encoding='utf-8'))
        expected = sum(1 for e in self.payload['questions'] if e['gap'])
        self.assertEqual(gaps['count'], expected)
        self.assertEqual(len(gaps['gaps']), expected)
        frontend = ROOT / 'frontend/src'
        for path in frontend.rglob('*'):
            if path.suffix in {'.ts', '.tsx', '.json'} and path.is_file():
                text = path.read_text(encoding='utf-8')
                self.assertNotIn('guide_content_gaps', text, path)
        reference_text = ''.join(p.read_text(encoding='utf-8') for p in REFERENCE_DIR.glob('*.json'))
        for gap in gaps['gaps'][:200]:
            self.assertNotIn(gap['gap'], reference_text)


if __name__ == '__main__':
    unittest.main()
