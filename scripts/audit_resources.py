#!/usr/bin/env python3
"""Deterministic pre-publication audit of everything the site serves.

Layer 1 of the audit mechanism: checks that need no model, no API key and no
judgement — they either hold or they don't. Run before every publish.

  python3 scripts/audit_resources.py            # 全部檢查
  python3 scripts/audit_resources.py --only colab
  python3 scripts/audit_resources.py --json out.json

Exit code is non-zero when any FAIL is found, so it can gate a build.

Layer 2 (answer cross-checking with several models) lives in
`verify_question_answers.py`; layer 3 is the human queue it produces.

Why this exists: the Colab pipeline already detected broken notebooks and wrote
`flagged.json` for 27 chapters — and every one of them was published anyway.
Detecting a defect without blocking it is the same as not detecting it.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterator

BASE = Path(__file__).resolve().parents[1]
ALLOWLIST_PATH = BASE / 'data' / 'audit_allowlist.json'
COMMITTED_REVIEW_PATH = BASE / 'data' / 'notebook_review' / 'committed_review.json'
GENERATED = BASE / 'frontend' / 'src' / 'generated'
LETTERS = ('A', 'B', 'C', 'D')
COMMITTED_REVIEW: dict[str, Any] = {}

# 中英夾雜：只抓「小寫英文單字被中文夾住」，例如「就能直接 conclude 所有組別」。
# 專有名詞與縮寫（Transformer、BERT、IDF、GloVe）是正當術語，不能一起抓——
# 早期版本用 [a-zA-Z]{3,} 產生 483 個誤判，等於沒有這條檢查。
MIXED_SCRIPT = re.compile(r'[一-鿿]\s*[a-z]{4,}\s*[一-鿿]')
ALLOWED_INLINE = re.compile(r'[（(][^）)]*[）)]')


class Report:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def add(self, resource: str, level: str, message: str, item: str = '') -> None:
        self.rows.append({'resource': resource, 'level': level,
                          'item': item, 'message': message})

    def fails(self) -> list[dict[str, Any]]:
        return [r for r in self.rows if r['level'] == 'FAIL']


def load(path: Path) -> Any:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def iter_questions(payload: Any) -> Iterator[dict[str, Any]]:
    """Both layouts: flat {questions:[...]} and {chapters:[{questions:[...]}]}."""
    if isinstance(payload, dict) and 'chapters' in payload:
        for chapter in payload['chapters']:
            yield from (q for q in chapter.get('questions', []) if isinstance(q, dict))
    elif isinstance(payload, dict) and 'questions' in payload:
        yield from (q for q in payload['questions'] if isinstance(q, dict))
    elif isinstance(payload, list):
        yield from (q for q in payload if isinstance(q, dict))


# ---------------------------------------------------------------------------
# Colab notebooks
# ---------------------------------------------------------------------------

def strip_magics(source: str) -> str:
    """Notebook cells legitimately contain !pip / %matplotlib, which ast cannot parse."""
    return '\n'.join('' if line.lstrip().startswith(('!', '%')) else line
                     for line in source.splitlines())


def audit_colab(report: Report) -> None:
    global COMMITTED_REVIEW
    COMMITTED_REVIEW = load(COMMITTED_REVIEW_PATH) if COMMITTED_REVIEW_PATH.exists() else {}
    for level_dir in sorted((GENERATED / 'colabNotebooks').glob('*')):
        if not level_dir.is_dir():
            continue
        level = level_dir.name
        for meta_path in sorted(level_dir.glob('*.json')):
            chapter = meta_path.stem
            ipynb = BASE / 'notebooks' / level / f'{chapter}.ipynb'
            if not ipynb.exists():
                report.add('colab', 'FAIL', '前端有 metadata 但 notebook 檔不存在', chapter)
                continue

            # 有 committed 版本的複查報告就以它為準；flagged.json 是草稿階段的舊帳
            fresh = COMMITTED_REVIEW.get(chapter)
            if fresh is not None:
                execution = fresh.get('execution', {})
                semantic = fresh.get('semantic', {})
                if execution.get('status') in ('error', 'timeout'):
                    report.add('colab', 'FAIL',
                               f'執行失敗：{execution.get("error", execution["status"])}',
                               chapter)
                for mismatch in semantic.get('mismatches', []):
                    report.add('colab', 'WARN',
                               f'cell {mismatch.get("cell")} 說明與程式碼不符：'
                               f'{mismatch.get("claim", "")}', chapter)
                continue

            flagged = (BASE / 'data' / level / 'pipeline' / 'colab_notebooks'
                       / chapter / 'flagged.json')
            if flagged.exists():
                review = load(flagged).get('review', {})
                status = review.get('overall_status', 'unknown')
                bad = [c for c in review.get('cells', [])
                       if c.get('status') in ('fail', 'warn')]
                issues = '；'.join(
                    i if isinstance(i, str) else str(i.get('detail') or i.get('issue') or i)
                    for c in bad for i in c.get('issues', [])[:1])
                # flagged.json 是「當時那份草稿」的審核，committed 的 .ipynb 可能已修過
                # ——實測 27 個 fail 章節的 committed 版本全部通過語法檢查。所以它只能是
                # 「需人工複查語意問題」的待辦，不能當現況判 FAIL。
                report.add('colab', 'WARN',
                           f'草稿審核為 {status}（{len(bad)} 個 cell），'
                           f'需確認 committed 版本是否已解決：{issues[:100]}',
                           chapter)

            # The strongest check: does the published code actually parse?
            notebook = load(ipynb)
            for index, cell in enumerate(notebook.get('cells', [])):
                if cell.get('cell_type') != 'code':
                    continue
                source = ''.join(cell.get('source', []))
                if not source.strip():
                    continue
                try:
                    ast.parse(strip_magics(source))
                except SyntaxError as exc:
                    report.add('colab', 'FAIL',
                               f'cell {index} 無法被 Python 解析：{exc.msg}', chapter)


# ---------------------------------------------------------------------------
# Question banks
# ---------------------------------------------------------------------------

def audit_questions(report: Report) -> None:
    seen_ids: dict[str, str] = {}
    for path in sorted(BASE.glob('data/*/questions/*.json')):
        rel = path.relative_to(BASE).as_posix()
        for question in iter_questions(load(path)):
            qid = str(question.get('id', ''))
            options = question.get('options')
            label = f'{rel}:{qid}'

            if qid and qid in seen_ids and seen_ids[qid] != rel:
                report.add('questions', 'WARN', f'id 與 {seen_ids[qid]} 重複', label)
            if qid:
                seen_ids.setdefault(qid, rel)

            if question.get('answer') not in LETTERS:
                report.add('questions', 'FAIL', 'answer 不是 A/B/C/D', label)
            if not isinstance(options, dict) or set(options) != set(LETTERS):
                report.add('questions', 'FAIL', '選項不是恰好 A/B/C/D', label)
                continue
            if any(not str(v).strip() for v in options.values()):
                report.add('questions', 'FAIL', '有空白選項', label)

            # Mutually exclusive options: two identical (or near-identical) choices
            # make the item unanswerable — s1c1q4 shipped with Human-over-the-loop
            # and Human-on-the-loop as separate options for the same concept.
            texts = {k: re.sub(r'\s+', '', str(v)) for k, v in options.items()}
            for left in LETTERS:
                for right in LETTERS:
                    if left < right and texts[left] and texts[left] == texts[right]:
                        report.add('questions', 'FAIL',
                                   f'選項 {left} 與 {right} 文字完全相同', label)

            # 官方考卷的措辭照抄原卷（pandas、seaborn、token 等），不是我們的缺陷
            official = Path(rel).name.startswith(('mock_', 'sample_'))
            stem = str(question.get('question', ''))
            body = ALLOWED_INLINE.sub('', stem + ''.join(str(v) for v in options.values()))
            if not official and MIXED_SCRIPT.search(body):
                hit = MIXED_SCRIPT.search(body)
                report.add('questions', 'WARN',
                           f'疑似中英夾雜：…{hit.group(0)}…', label)

            card = question.get('card')
            if card is not None and isinstance(card, dict):
                for field in ('concept', 'mnemonic', 'confusion', 'frequency'):
                    if field in card and not str(card[field]).strip():
                        report.add('questions', 'FAIL', f'card.{field} 是空的', label)


# ---------------------------------------------------------------------------
# Reference answers vs the official key
# ---------------------------------------------------------------------------

EXAM_QUESTION_FILES = {
    'jr_1141_s1': '初級/questions/mock_jr_1141_s1.json',
    'jr_1141_s2': '初級/questions/mock_jr_1141_s2.json',
    'jr_1151_s1': '初級/questions/mock_jr_1151_s1.json',
    'jr_1151_s2': '初級/questions/mock_jr_1151_s2.json',
    'jr_1152_s1': '初級/questions/mock_jr_1152_s1.json',
    'jr_1152_s2': '初級/questions/mock_jr_1152_s2.json',
    'mid_1141_s1': '中級/questions/mock_mid_1141_s1.json',
    'mid_1141_s2': '中級/questions/mock_mid_1141_s2.json',
    'mid_1141_s3': '中級/questions/mock_mid_1141_s3.json',
    'sample': '初級/questions/sample_exam.json',
    'midSample': '中級/questions/sample_exam.json',
}


def audit_reference_answers(report: Report) -> None:
    for exam_key, rel in EXAM_QUESTION_FILES.items():
        ref_path = GENERATED / 'examReferenceAnswers' / f'{exam_key}.json'
        question_path = BASE / 'data' / rel
        if not ref_path.exists() or not question_path.exists():
            report.add('referenceAnswers', 'WARN', '找不到對應檔案', exam_key)
            continue
        official = {qid.rsplit('_q', 1)[-1]: (qid, answer)
                    for qid, answer in
                    ((q['id'], q['answer']) for q in iter_questions(load(question_path)))}
        for ref_id, record in load(ref_path).items():
            if not isinstance(record, dict) or 'answer' not in record:
                continue
            number = ref_id.rsplit('_q', 1)[-1]
            if number not in official:
                report.add('referenceAnswers', 'WARN', '對不到題號', f'{exam_key}:{ref_id}')
                continue
            qid, answer = official[number]
            if record['answer'] != answer:
                report.add('referenceAnswers', 'FAIL',
                           f'詳解答案 {record["answer"]} ≠ 官方答案 {answer}',
                           f'{exam_key}:{ref_id}')


# ---------------------------------------------------------------------------
# Images and glossary
# ---------------------------------------------------------------------------

def audit_images(report: Report) -> None:
    path = GENERATED / 'guideImages.json'
    if not path.exists():
        return
    data = load(path)
    missing = 0
    total = 0
    for src in _iter_image_srcs(data):
        total += 1
        if not (BASE / 'frontend' / 'public' / src.lstrip('/')).exists():
            missing += 1
            if missing <= 5:
                report.add('images', 'FAIL', '圖片檔不存在', src)
    if missing > 5:
        report.add('images', 'FAIL', f'另有 {missing - 5} 張圖片檔不存在', '')
    report.add('images', 'INFO', f'檢查 {total} 張圖片參照，缺 {missing} 張', '')


def _iter_image_srcs(node: Any) -> Iterator[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ('src', 'path', 'image') and isinstance(value, str) \
                    and value.startswith('/'):
                yield value
            else:
                yield from _iter_image_srcs(value)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_image_srcs(item)


def audit_glossary(report: Report) -> None:
    path = GENERATED / 'middleGlossary.json'
    if not path.exists():
        return
    seen: set[str] = set()
    count = 0
    for subject_id, subject in load(path).get('subjects', {}).items():
        terms = subject.get('terms', subject) if isinstance(subject, dict) else subject
        for entry in terms if isinstance(terms, list) else []:
            count += 1
            term = str(entry.get('zh') or entry.get('term') or '').strip() \
                if isinstance(entry, dict) else ''
            definition = str(entry.get('definition', '')).strip() \
                if isinstance(entry, dict) else ''
            if not term or not definition:
                report.add('glossary', 'FAIL', '詞條或釋義是空的',
                           f'{subject_id}:{term or "?"}')
            key = unicodedata.normalize('NFKC', term).lower()
            if key and key in seen:
                report.add('glossary', 'WARN', '詞條重複', f'{subject_id}:{term}')
            seen.add(key)
    report.add('glossary', 'INFO', f'檢查 {count} 個詞條', '')


CHECKS = {
    'colab': audit_colab,
    'questions': audit_questions,
    'referenceAnswers': audit_reference_answers,
    'images': audit_images,
    'glossary': audit_glossary,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--only', choices=sorted(CHECKS), nargs='+')
    parser.add_argument('--json', type=Path, help='另存完整報告')
    args = parser.parse_args()

    report = Report()
    for name in (args.only or sorted(CHECKS)):
        CHECKS[name](report)

    allowlist = load(ALLOWLIST_PATH) if ALLOWLIST_PATH.exists() else []
    allowed = 0
    for row in report.rows:
        for entry in allowlist:
            if row['level'] == 'FAIL' and row['resource'] == entry['resource'] \
                    and row['item'] == entry['item'] \
                    and row['message'].startswith(entry.get('messagePrefix', '')):
                row['level'] = 'ALLOWED'
                row['reason'] = entry.get('reason', '')
                allowed += 1
                break
    if allowed:
        print(f'\n{allowed} 項 FAIL 在允許清單內（data/audit_allowlist.json）')

    by_resource: dict[str, dict[str, int]] = {}
    for row in report.rows:
        by_resource.setdefault(row['resource'], {}).setdefault(row['level'], 0)
        by_resource[row['resource']][row['level']] += 1

    for resource, counts in sorted(by_resource.items()):
        summary = ' '.join(f'{level}={counts[level]}' for level in sorted(counts))
        print(f'{resource:18} {summary}')

    fails = report.fails()
    if fails:
        print(f'\n{len(fails)} 項 FAIL（前 20）：')
        for row in fails[:20]:
            print(f'  [{row["resource"]}] {row["item"]}: {row["message"]}')

    if args.json:
        args.json.write_text(json.dumps(report.rows, ensure_ascii=False, indent=2),
                             encoding='utf-8')
        print(f'\n完整報告 → {args.json}')

    raise SystemExit(1 if fails else 0)


if __name__ == '__main__':
    main()
