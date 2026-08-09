#!/usr/bin/env python3
"""Cross-check glossary definitions by having several LLMs review each entry blind.

Each reviewer sees one entry (zh / en / definition / example) with no repo access
and no sight of the other reviewers, and returns a verdict plus the concrete error
it found. Entries where enough reviewers say the definition is wrong land in
flagged.json for human adjudication — same two-stage shape as
`verify_question_answers.py`, whose gateway client this reuses.

Usage:
  python3 scripts/verify_glossary_terms.py --glossary frontend/src/generated/middleGlossary.json
  python3 scripts/verify_glossary_terms.py --limit 5 --verifiers llm:glm-5.2
  # gate self-test: corrupt N entries on purpose, the run must flag every one of them
  python3 scripts/verify_glossary_terms.py --self-test

Verdicts each reviewer may return:
  ok      definition is factually correct and the example fits the term
  minor   correct but imprecise/incomplete wording
  wrong   factually wrong, or describes a different concept, or the example
          contradicts the definition

`wrong` votes are what flags an entry (`--threshold`, default 2). `minor` votes are
reported separately: they are style signal, not a correctness gate, because
reviewers disagree wildly on how much nuance a 60-character definition owes.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_question_answers import (  # noqa: E402  (shared gateway client)
    call_gateway,
    load_env_file,
    load_json,
    save_json,
)

BASE = Path('/home/james/projects/ipas-test')
DEFAULT_GLOSSARY = BASE / 'frontend' / 'src' / 'generated' / 'middleGlossary.json'
DEFAULT_OUT = BASE / 'data' / 'audit' / 'glossary_review'
# Same roster that scored 28/28 on the mid-s2c3 answer baseline.
DEFAULT_VERIFIERS = 'llm:glm-5.2,llm:deepseek-v4-pro,llm:kimi-k2.7-code'
VERDICTS = ('ok', 'minor', 'wrong')

PROMPT = """你是一位人工智慧領域的技術審稿人，正在審核一份專業術語詞彙表的單一詞條。

詞條：
- 中文名稱：{zh}
- 英文名稱：{en}
- 釋義：{definition}
- 應用例句：{example}

請判斷這個詞條的「釋義」是否在技術上正確，以及「應用例句」是否確實在描述同一個概念。

判定標準：
- ok：釋義正確，例句與該術語相符。用字精簡但不失真的釋義算 ok。
- minor：釋義方向正確，但用詞不精確或漏掉關鍵條件，讀者不會被誤導成別的概念。
- wrong：釋義在技術上錯誤、或其實描述的是另一個概念、或例句與釋義互相矛盾。

只回傳 JSON，不要有其他文字：
{{"verdict": "ok|minor|wrong", "issue": "若非 ok，用一句話指出具體錯在哪；ok 則空字串", "correct_definition": "若 verdict 是 wrong，寫出你認為正確的一句話釋義；否則空字串"}}
"""


def extract_verdict(raw: str | None) -> dict[str, str] | None:
    """Pull the JSON object out of a reply that may be fenced or prose-wrapped."""
    if not raw:
        return None
    text = re.sub(r'^```(?:json)?|```$', '', raw.strip(), flags=re.MULTILINE).strip()
    match = re.search(r'\{.*\}', text, flags=re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    verdict = str(data.get('verdict', '')).strip().lower()
    if verdict not in VERDICTS:
        return None
    return {
        'verdict': verdict,
        'issue': str(data.get('issue', '')).strip(),
        'correct_definition': str(data.get('correct_definition', '')).strip(),
    }


def ask(model: str, entry: dict[str, str], timeout: int, retries: int
        ) -> dict[str, str] | None:
    prompt = PROMPT.format(zh=entry['zh'], en=entry.get('en', ''),
                           definition=entry['definition'], example=entry.get('example', ''))
    for _ in range(retries + 1):
        verdict = extract_verdict(call_gateway(prompt, model, timeout))
        if verdict:
            return verdict
    return None


def load_entries(glossary_path: Path) -> list[dict[str, Any]]:
    data = load_json(glossary_path)
    entries = []
    for subject_id, subject in data['subjects'].items():
        for index, term in enumerate(subject['terms']):
            entries.append({
                'subject': subject_id,
                'index': index,
                'zh': term['zh'],
                'en': term.get('en', ''),
                'definition': term['definition'],
                'example': term.get('example', ''),
            })
    return entries


# Deliberate corruptions for --self-test. Each swaps in a definition that is wrong
# in a different way, so a pass proves the gate catches more than one failure mode.
CORRUPTIONS = [
    ('精確率', '在所有實際為正例的樣本中，被模型正確預測為正例的比例。'),   # this is recall
    ('中位數', '將一組數值全部相加後除以個數所得到的代表值。'),              # this is the mean
    ('過度擬合', '模型在訓練資料與測試資料上表現都很差，代表模型複雜度不足。'),  # underfitting
    ('監督式學習', '在沒有標註答案的資料中，讓模型自行找出群集與結構的學習方式。'),  # unsupervised
]


def apply_corruptions(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_zh = {e['zh']: e for e in entries}
    picked = []
    for zh, bad_definition in CORRUPTIONS:
        entry = by_zh.get(zh)
        if entry is None:
            raise SystemExit(f'self-test needs the term "{zh}" but the glossary has no such entry')
        corrupted = dict(entry)
        corrupted['definition'] = bad_definition
        corrupted['_corrupted'] = True
        picked.append(corrupted)
    # Pair each corrupted entry with its untouched twin: a gate that flags
    # everything is as useless as one that flags nothing.
    for zh, _ in CORRUPTIONS:
        clean = dict(by_zh[zh])
        clean['_corrupted'] = False
        picked.append(clean)
    return picked


def review(entries: list[dict[str, Any]], models: list[str], timeout: int,
           retries: int, workers: int) -> list[dict[str, Any]]:
    # Key on the entry's position in this run, not (subject, index): --self-test
    # feeds a corrupted entry and its clean twin, which share subject+index and
    # would otherwise collide into one result.
    for uid, entry in enumerate(entries):
        entry['_uid'] = uid
    jobs = [(entry, model) for entry in entries for model in models]
    results: dict[tuple[int, str], dict[str, str] | None] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(ask, model, entry, timeout, retries): (entry, model)
                   for entry, model in jobs}
        done = 0
        for future in as_completed(futures):
            entry, model = futures[future]
            results[(entry['_uid'], model)] = future.result()
            done += 1
            print(f'\r  reviewed {done}/{len(jobs)}', end='', flush=True)
    print()

    reviewed = []
    for entry in entries:
        votes = {}
        for model in models:
            votes[model] = results.get((entry['_uid'], model))
        record = dict(entry)
        record['votes'] = votes
        record['wrong_count'] = sum(1 for v in votes.values() if v and v['verdict'] == 'wrong')
        record['minor_count'] = sum(1 for v in votes.values() if v and v['verdict'] == 'minor')
        record['no_reply_count'] = sum(1 for v in votes.values() if v is None)
        reviewed.append(record)
    return reviewed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--glossary', default=str(DEFAULT_GLOSSARY))
    parser.add_argument('--out-dir', default=str(DEFAULT_OUT))
    parser.add_argument('--verifiers', default=DEFAULT_VERIFIERS)
    parser.add_argument('--threshold', type=int, default=2,
                        help='how many "wrong" votes flag an entry (default 2)')
    parser.add_argument('--timeout', type=int, default=120)
    parser.add_argument('--retries', type=int, default=1)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--term', action='append', default=[],
                        help='review only these terms (repeatable); use after fixing '
                             'a flagged entry instead of re-running all of them')
    parser.add_argument('--self-test', action='store_true',
                        help='review deliberately corrupted entries plus their clean '
                             'twins; exits non-zero unless every corruption is flagged '
                             'and every clean twin is not')
    args = parser.parse_args()

    load_env_file()
    models = []
    for item in args.verifiers.split(','):
        key = item.strip()
        if not key:
            continue
        tool, _, model = key.partition(':')
        if tool != 'llm' or not model:
            raise SystemExit(f'only llm:<model> verifiers are supported here, got "{key}"')
        models.append(model)
    if not models:
        raise SystemExit('no verifiers selected')

    entries = load_entries(Path(args.glossary))
    if args.term:
        entries = [e for e in entries if e['zh'] in set(args.term)]
        if not entries:
            raise SystemExit(f'no entry matches {args.term} in {args.glossary}')
    if args.self_test:
        entries = apply_corruptions(entries)
    elif args.limit:
        entries = entries[:args.limit]

    print(f'{len(entries)} entries × {len(models)} reviewers')
    reviewed = review(entries, models, args.timeout, args.retries, args.workers)

    if args.self_test:
        caught = [e for e in reviewed if e['_corrupted'] and e['wrong_count'] >= args.threshold]
        missed = [e for e in reviewed if e['_corrupted'] and e['wrong_count'] < args.threshold]
        false_alarm = [e for e in reviewed
                       if not e['_corrupted'] and e['wrong_count'] >= args.threshold]
        print(f'\nself-test: caught {len(caught)}/{len([e for e in reviewed if e["_corrupted"]])} '
              f'corruptions, {len(false_alarm)} false alarm(s) on clean entries')
        for entry in missed:
            print(f'  MISS  {entry["zh"]}: wrong_count={entry["wrong_count"]}')
        for entry in false_alarm:
            issues = [v['issue'] for v in entry['votes'].values() if v and v['issue']]
            print(f'  FALSE {entry["zh"]}: {issues}')
        save_json(Path(args.out_dir) / 'self_test.json', reviewed)
        raise SystemExit(0 if not missed and not false_alarm else 1)

    flagged = [e for e in reviewed if e['wrong_count'] >= args.threshold]
    minor = [e for e in reviewed if e not in flagged and e['minor_count'] >= 2]
    out_dir = Path(args.out_dir)
    save_json(out_dir / 'review.json', reviewed)
    save_json(out_dir / 'flagged.json', flagged)

    print(f'\nflagged (≥{args.threshold} wrong votes): {len(flagged)}/{len(reviewed)}')
    for entry in flagged:
        print(f'  {entry["subject"]} {entry["zh"]}')
        for model, vote in entry['votes'].items():
            if vote and vote['verdict'] == 'wrong':
                print(f'    [{model}] {vote["issue"]}')
    print(f'majority-minor (no wrong consensus): {len(minor)}')
    for entry in minor:
        print(f'  {entry["subject"]} {entry["zh"]}')
    no_reply = sum(e['no_reply_count'] for e in reviewed)
    if no_reply:
        print(f'⚠️ {no_reply} reviewer call(s) returned nothing')
    print(f'→ {out_dir}/review.json, flagged.json')


if __name__ == '__main__':
    main()
