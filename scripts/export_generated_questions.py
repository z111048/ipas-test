#!/usr/bin/env python3
"""把小節管線產出的題目併進題庫（`playbook/07` §5-4 一直缺的那一步）。

生成結果原本停在 gitignored 的 `data/{level}/pipeline/` 下，沒有任何 export 步驟，
所以「重生題庫」缺的不是算力而是這段管線。

寫入前**重新驗一次**（不信任上游已驗過，這條線踩過三次靜默失敗）：
    每批都要通過 runner 的 schema 驗證
    id 在本次匯出內唯一
    題幹在本次匯出內不重複（跨檔重複由 audit_resources.py 另外查）
任一項不過就**整批拒絕寫出**，不要產出看起來完整的部分結果。

⚠️ **預設要求整科完整**：只匯出一章會把該科其他章直接抹掉。
要只替換某幾章請明確加 `--replace-chapters`（會與現有題庫合併）。

用法：
    python3 scripts/export_generated_questions.py --run-dir data/初級/pipeline/regen_s1 --dry-run
    python3 scripts/export_generated_questions.py --run-dir ... --replace-chapters s1c4
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_codex_question_batch_generation import validate_batch  # noqa: E402
from verify_batch_answers import verify_path  # noqa: E402

BASE = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> Any:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def normalize_stem(text: Any) -> str:
    import re
    return re.sub(r'\s+', '', str(text or ''))


def chapter_order(level: str, subject_id: str) -> list[dict]:
    """章節順序以 toc_manifest 為準（SSOT，不在這裡複製章節定義）。"""
    manifest = load_json(BASE / 'data' / level / 'toc_manifest.json')
    for subject in manifest['subjects']:
        chapters = subject.get('chapters') or []
        if any(c.get('id', '').startswith(subject_id) for c in chapters):
            return chapters
    return []


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--replace-chapters', help='逗號分隔；只替換這幾章並與現有題庫合併')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--skip-answer-check', action='store_true',
                        help='跳過「必須有通過的答案驗證」這道條件（不建議）')
    args = parser.parse_args()

    run_dir = args.run_dir if args.run_dir.is_absolute() else BASE / args.run_dir
    summary = load_json(run_dir / 'summary.json')
    level, subject_id = summary['level'], summary['subject_id']

    # 1. 逐批重驗，任一批不過就拒絕
    questions: list[dict] = []
    problems: list[str] = []
    for batch in summary['batches']:
        output_path = BASE / batch['output']
        if not output_path.exists():
            problems.append(f'批次 {batch["batch"] if "batch" in batch else batch.get("batch_index")} 沒有輸出')
            continue
        errors = validate_batch(output_path, batch, level)
        if errors:
            problems.append(f'{output_path.name}: {errors[:2]}')
            continue
        # 答案交叉驗證是進題庫的必要條件。沒驗過就不准寫——
        # 「有驗證工具」與「驗證真的擋得住」是兩件事。
        if not args.skip_answer_check:
            check_path = verify_path(output_path)
            if not check_path.exists():
                problems.append(f'{output_path.name}: 沒有答案驗證結果'
                                f'（跑 run_codex_question_batch_generation.py --verify-answers）')
                continue
            check = load_json(check_path)
            if not check.get('ok'):
                problems.append(f"{output_path.name}: 答案驗證 flagged {check.get('flagged')}")
                continue
        questions.extend(load_json(output_path)['questions'])

    if problems:
        print('FAIL 有批次沒通過驗證，不寫出任何東西：')
        for line in problems:
            print(f'   {line}')
        raise SystemExit(1)

    # 2. id 與題幹唯一性
    ids = Counter(q['id'] for q in questions)
    dup_ids = [i for i, n in ids.items() if n > 1]
    stems = Counter(normalize_stem(q.get('question')) for q in questions)
    dup_stems = [s[:30] for s, n in stems.items() if n > 1]
    if dup_ids or dup_stems:
        print(f'FAIL 重複 id {dup_ids}｜重複題幹 {dup_stems}')
        raise SystemExit(1)

    # 3. 完整性：預設要求整科的每一章都有題
    order = chapter_order(level, subject_id)
    by_chapter: dict[str, list[dict]] = {}
    for question in questions:
        by_chapter.setdefault(question['id'].split('q')[0], []).append(question)

    subject_number = subject_id.replace('mid-s', '').replace('s', '')
    out_path = BASE / 'data' / level / 'questions' / f'subject{subject_number}_questions.json'
    replace = [c.strip() for c in (args.replace_chapters or '').split(',') if c.strip()]

    if not replace:
        missing = [c['id'] for c in order if c['id'] not in by_chapter]
        if missing:
            print(f'FAIL 這一科的以下章節沒有題目：{missing}')
            print('   只匯出部分章節會抹掉其他章。要只替換某幾章請加 --replace-chapters。')
            raise SystemExit(1)
        chapters = [{'id': c['id'], 'title': c['title'],
                     'questions': by_chapter.get(c['id'], [])} for c in order]
    else:
        existing = load_json(out_path) if out_path.exists() else {'chapters': []}
        kept = {c['id']: c for c in existing.get('chapters') or []}
        for chapter_id in replace:
            if chapter_id not in by_chapter:
                print(f'FAIL --replace-chapters 指定了 {chapter_id}，但這次沒有它的題目')
                raise SystemExit(1)
            title = next((c['title'] for c in order if c['id'] == chapter_id), chapter_id)
            kept[chapter_id] = {'id': chapter_id, 'title': title,
                                'questions': by_chapter[chapter_id]}
        chapters = [kept[c['id']] for c in order if c['id'] in kept]

    subject_title = next((s['subject'] for s in load_json(BASE / 'data' / level /
                                                          'toc_manifest.json')['subjects']
                          if any(c.get('id', '').startswith(subject_id)
                                 for c in s.get('chapters') or [])), subject_id)
    payload = {'subject': subject_title, 'chapters': chapters}
    total = sum(len(c['questions']) for c in chapters)

    print(f'{level} {subject_id} → {out_path.relative_to(BASE)}')
    for chapter in chapters:
        mark = '（本次重生）' if not replace or chapter['id'] in replace else ''
        print(f'   {chapter["id"]:12} {len(chapter["questions"]):>3} 題 {mark}')
    print(f'   合計 {total} 題' + ('（dry-run，未寫入）' if args.dry_run else ''))
    if not args.dry_run:
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n',
                            encoding='utf-8')


if __name__ == '__main__':
    main()
