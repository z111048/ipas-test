#!/usr/bin/env python3
"""把定案詞彙表（data/topics/topics.json）的概念指派到官方考古題（§7-2）。

兩段式，**先確定性再模型**：

  1. 別名比對    詞彙表是從這些題目的 `key_concepts` 收斂出來的，所以八成的題目
                 光靠「別名 → 概念」的字串比對就標得到（實測 447/559 = 80%），
                 這一段零 API 花費、完全可重現、每一筆都指得出是哪個詞組命中的。
  2. 模型指派    只處理比對不到的那 112 題，且**限定只能從詞彙表挑**——
                 自由文字標籤會漂移（playbook/07 §3：放任模型自由填 題型，
                 同一個概念出現 7 種寫法）。

每題最多 3 個概念。超過就依「首次命中位置 → 是否正式名稱 → 命中次數」排序取前三，
這是確定性規則，不是再問一次模型（理由見 deterministic 的 docstring）。

⚠️ 這一步的精確度上限是**別名品質**：別名是模型自由文字產出的，08 §6 已警告過
不可拿來當合併鍵，拿來當標籤鍵風險類似。輸出的 `aliasQuality` 把兩種雜訊量出來
（一詞指向多概念、A 的正式名稱是 B 的別名），不要當成沒事。

用法：
    python3 scripts/assign_question_topics.py --dry-run     # 只看確定性覆蓋率
    python3 scripts/assign_question_topics.py               # 含模型補標
    python3 scripts/assign_question_topics.py --models glm-5.2,deepseek-v4-pro,kimi-k2.7-code
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_topic_vocabulary import normalise  # noqa: E402
from verify_question_answers import call_gateway, load_env_file  # noqa: E402

BASE = Path(__file__).resolve().parents[1]
REFERENCE_DIR = BASE / 'frontend' / 'src' / 'generated' / 'examReferenceAnswers'
VOCAB_PATH = BASE / 'data' / 'topics' / 'topics.json'
OUT_PATH = BASE / 'data' / 'topics' / 'question_topics.json'
MAX_TOPICS = 3
BATCH_SIZE = 12


def load_json(path: Path) -> Any:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def build_lookup(topics: list[dict]) -> dict[str, list[str]]:
    """{正規化過的名稱或別名: [概念名]}。一個別名可能指向多個概念，全部保留——
    這裡不做取捨，取捨在排序那步，才看得出是為什麼留下的。"""
    lookup: dict[str, list[str]] = {}
    for topic in topics:
        for name in [topic['name'], *topic.get('aliases', [])]:
            key = normalise(name)
            if topic['name'] not in lookup.setdefault(key, []):
                lookup[key].append(topic['name'])
    return lookup


def deterministic(phrases: list[str], lookup: dict[str, list[str]]) -> list[dict]:
    """別名比對。回傳帶證據的指派：每個概念記下是哪些詞組命中的。

    排序以**首次命中的位置**為主鍵：`key_concepts` 是詳解按重要性寫下來的，
    排在前面的是這題真正在考的，後面常是拿來對照的概念。
    早期版本用「命中次數」排序，exam1_q5 的「交叉驗證」（唯一精準的概念）
    直接被兩個廣義概念擠出前三。
    也試過「正式名稱命中優先」，反而更糟：exam1_q7 的「非監督式學習」「強化學習」
    只是題目的對照組，卻因為是正式名稱被拉到最前面。
    """
    hits: dict[str, list[str]] = {}
    order: dict[str, int] = {}
    exact: set[str] = set()
    for index, phrase in enumerate(phrases):
        key = normalise(phrase)
        for name in lookup.get(key, ()):
            hits.setdefault(name, []).append(phrase)
            order.setdefault(name, index)
            if normalise(name) == key:
                exact.add(name)
    ranked = sorted(hits, key=lambda n: (order[n], n not in exact, -len(hits[n]), n))
    return [{'topic': n, 'via': hits[n], 'source': 'alias',
             'exactName': n in exact} for n in ranked[:MAX_TOPICS]]


def alias_quality(topics: list[dict]) -> dict[str, Any]:
    """別名品質報告。別名是模型自由文字產出的（08 §6 已警告不可當合併鍵），
    這裡拿來當**標籤鍵**風險類似，所以把兩種雜訊量出來讓人看得見：
      - 一個詞同時指向多個概念（標了會雙重計數）
      - A 的正式名稱是 B 的別名（可能是殘留重複，也可能只是上下位關係）
    """
    canonical = {normalise(t['name']): t['name'] for t in topics}
    lookup: dict[str, list[str]] = {}
    for topic in topics:
        for name in [topic['name'], *topic.get('aliases', [])]:
            lookup.setdefault(normalise(name), []).append(topic['name'])
    ambiguous = {k: v for k, v in lookup.items() if len(v) > 1}
    clashes = [{'name': canonical[normalise(alias)], 'aliasOf': topic['name']}
               for topic in topics for alias in topic.get('aliases', [])
               if normalise(alias) in canonical
               and canonical[normalise(alias)] != topic['name']]
    return {'lookupEntries': len(lookup), 'ambiguousEntries': len(ambiguous),
            'canonicalNameUsedAsAlias': len(clashes),
            'clashes': sorted(clashes, key=lambda c: c['name'])}


def build_prompt(names: list[str], items: list[tuple[str, str, list[str]]]) -> str:
    listing = '\n'.join(f'- {n}' for n in names)
    blocks = []
    for qid, summary, phrases in items:
        kc = '、'.join(phrases) if phrases else '（無）'
        blocks.append(f'### {qid}\n原始概念詞組：{kc}\n詳解摘要：{summary}')
    body = '\n\n'.join(blocks)
    return f"""以下是 iPAS AI 應用規劃師考試的受控概念詞彙表，共 {len(names)} 個概念。
請為每一題挑出 1 到 {MAX_TOPICS} 個**最能代表這題考什麼觀念**的概念。

規則：
1. 只能從下面的清單挑，**逐字照抄**，不可自創、不可改寫、不可合併兩個名稱。
2. 寧可只挑 1 個準確的，也不要湊到 3 個。
3. 挑不出來就給空陣列，不要硬塞——標錯比沒標更難發現。

只輸出 JSON：
{{"assignments":[{{"id":"題號","topics":["概念1","概念2"]}}]}}

概念清單：
{listing}

題目：
{body}
"""


def parse_assignments(raw: str | None) -> dict[str, list[str]]:
    if not raw:
        return {}
    text = raw.strip()
    if text.startswith('```'):
        text = '\n'.join(text.split('\n')[1:]).rsplit('```', 1)[0]
    start, end = text.find('{'), text.rfind('}')
    if start < 0:
        return {}
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return {}
    out: dict[str, list[str]] = {}
    for row in data.get('assignments') or []:
        qid = str(row.get('id', '')).strip()
        topics = [str(t).strip() for t in (row.get('topics') or []) if str(t).strip()]
        if qid:
            out[qid] = topics
    return out


def build_verify_prompt(items: list[tuple[str, str, list[str]]]) -> str:
    blocks = []
    for qid, summary, topics in items:
        listed = '\n'.join(f'  - {t}' for t in topics)
        blocks.append(f'### {qid}\n詳解摘要：{summary}\n目前標的概念：\n{listed}')
    body = '\n\n'.join(blocks)
    return f"""以下每一題都已經被標上 1~3 個概念標籤。請逐個標籤判斷它標得對不對。

每個標籤給一個評價：
- `正確`：確實是這題在考的觀念
- `過廣`：方向沒錯，但太籠統，不足以說明這題考什麼
- `錯誤`：這題根本不是在考這個

只輸出 JSON：
{{"reviews":[{{"id":"題號","verdicts":[{{"topic":"概念名","verdict":"正確"}}]}}]}}

{body}
"""


def parse_reviews(raw: str | None) -> dict[str, dict[str, str]]:
    if not raw:
        return {}
    text = raw.strip()
    if text.startswith('```'):
        text = '\n'.join(text.split('\n')[1:]).rsplit('```', 1)[0]
    start, end = text.find('{'), text.rfind('}')
    if start < 0:
        return {}
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return {}
    out: dict[str, dict[str, str]] = {}
    for row in data.get('reviews') or []:
        qid = str(row.get('id', '')).strip()
        if not qid:
            continue
        out[qid] = {str(v.get('topic', '')).strip(): str(v.get('verdict', '')).strip()
                    for v in (row.get('verdicts') or [])}
    return out


def verify_all(args, questions: dict[str, dict]) -> None:
    """全量驗收：逐個標籤評 正確／過廣／錯誤，**濾掉錯誤**、保留過廣但標記。

    抽驗 60 題量到「正確 61%、過廣 26%、錯誤 13%」——13% 標錯會直接污染概念
    熱度統計，不能就這樣上。根因是別名品質（08 §6 早就寫過 alias 是自由文字、
    品質不受控），這裡用驗收把它擋在資料進入統計之前。
    """
    data = load_json(OUT_PATH)
    keys = sorted(data['assignments'])
    items = [(k, str(questions[k].get('reference_answer') or '')[:260],
              data['assignments'][k]['topics']) for k in keys]
    print(f'全量驗收 {len(items)} 題')

    load_env_file()
    model = args.models.split(',')[0].strip()
    verdicts: dict[str, dict[str, str]] = {}
    failed = []
    for start in range(0, len(items), BATCH_SIZE):
        batch = items[start:start + BATCH_SIZE]
        raw = None
        for _ in range(args.retries + 1):
            raw = call_gateway(build_verify_prompt(batch), model,
                               args.timeout, None, args.max_tokens)
            if parse_reviews(raw):
                break
        got = parse_reviews(raw)
        if not got:
            failed.append(start // BATCH_SIZE + 1)
            continue
        verdicts.update(got)
    if failed:
        raise SystemExit(f'FAIL {len(failed)} 批沒有結果（批 {"、".join(map(str, failed))}），'
                         '不產出部分驗收結果')

    tally = Counter()
    for key in keys:
        entry = data['assignments'][key]
        kept, dropped = [], []
        for evidence in entry['evidence']:
            verdict = verdicts.get(key, {}).get(evidence['topic'], '未評')
            evidence['verdict'] = verdict
            tally[verdict] += 1
            (dropped if verdict == '錯誤' else kept).append(evidence['topic'])
        entry['topics'] = kept
        if dropped:
            entry['droppedAsWrong'] = dropped
    total = sum(tally.values())
    empty = [k for k in keys if not data['assignments'][k]['topics']]
    data.update({
        'status': 'verified',
        'verifiedBy': model,
        'verdictTally': dict(tally),
        'labelsBefore': total,
        'labelsAfter': total - tally['錯誤'],
        'questionsLeftWithNoTopic': sorted(empty),
    })
    OUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print('標籤 ' + str(total) + '：' + '、'.join(f'{k} {v}（{v / total:.0%}）'
                                                for k, v in tally.most_common()))
    print(f'濾掉錯誤 {tally["錯誤"]} 個 → 剩 {total - tally["錯誤"]} 個；'
          f'因此變成沒有標籤的題目 {len(empty)} 題')
    print(f'→ {OUT_PATH.relative_to(BASE)}')


def verify_sample(args, questions: dict[str, dict]) -> None:
    """抽樣量測「別名比對」標得準不準。

    別名是模型自由文字產出的，沒有理由假設它精確。與其寫「應該還可以」，
    不如抽一批出來讓模型逐個標籤評 正確／過廣／錯誤，得到一個可以寫進報告的數字。
    抽樣是每隔 k 筆取一筆（確定性），不用亂數，這樣重跑結果一樣。
    """
    data = load_json(OUT_PATH)
    alias_keys = [k for k, v in data['assignments'].items()
                  if v['evidence'][0]['source'] == 'alias']
    step = max(1, len(alias_keys) // args.verify_sample)
    picked = alias_keys[::step][:args.verify_sample]
    items = [(k, str(questions[k].get('reference_answer') or '')[:260],
              data['assignments'][k]['topics']) for k in picked]
    print(f'抽驗 {len(items)} 題（每 {step} 筆取 1，確定性抽樣）')

    load_env_file()
    model = args.models.split(',')[0].strip()
    verdicts: dict[str, dict[str, str]] = {}
    for start in range(0, len(items), BATCH_SIZE):
        batch = items[start:start + BATCH_SIZE]
        raw = None
        for _ in range(args.retries + 1):
            raw = call_gateway(build_verify_prompt(batch), model,
                               args.timeout, None, args.max_tokens)
            if parse_reviews(raw):
                break
        got = parse_reviews(raw)
        if not got:
            raise SystemExit(f'FAIL 抽驗批 {start // BATCH_SIZE + 1} 沒有結果，不產出部分數字')
        verdicts.update(got)

    tally = Counter()
    bad: list[dict] = []
    for qid, summary, topics in items:
        for topic in topics:
            verdict = verdicts.get(qid, {}).get(topic, '未評')
            tally[verdict] += 1
            if verdict in ('過廣', '錯誤'):
                bad.append({'question': qid, 'topic': topic, 'verdict': verdict})
    total = sum(tally.values())
    print(f'\n標籤 {total} 個：' + '、'.join(f'{k} {v}（{v / total:.0%}）'
                                            for k, v in tally.most_common()))
    report = {'sampled': len(items), 'labels': total, 'tally': dict(tally),
              'model': model, 'problems': bad}
    path = OUT_PATH.with_name('question_topics_sample_review.json')
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'→ {path.relative_to(BASE)}')
    for row in bad[:8]:
        print(f'   {row["verdict"]}  {row["question"]}  {row["topic"]}')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--models', default='glm-5.2',
                        help='逗號分隔；給 3 個就做 2/3 共識驗收')
    parser.add_argument('--timeout', type=int, default=300)
    parser.add_argument('--max-tokens', type=int, default=4000)
    parser.add_argument('--retries', type=int, default=2)
    parser.add_argument('--dry-run', action='store_true', help='只做別名比對，不呼叫模型')
    parser.add_argument('--verify-all', action='store_true',
                        help='全量驗收既有指派，濾掉「錯誤」的標籤')
    parser.add_argument('--verify-sample', type=int, default=0,
                        help='抽驗既有指派的精確度（給樣本數），不重跑指派')
    args = parser.parse_args()

    vocab = load_json(VOCAB_PATH)
    if vocab.get('status') != 'signed-off':
        raise SystemExit(f'FAIL {VOCAB_PATH.name} 不是 signed-off 狀態，不拿來標題目')
    topics = vocab['topics']
    names = [t['name'] for t in topics]
    valid = {normalise(n): n for n in names}
    lookup = build_lookup(topics)

    questions: dict[str, dict] = {}
    for path in sorted(REFERENCE_DIR.glob('*.json')):
        if path.stem == 'stats':
            continue
        for qid, entry in load_json(path).items():
            questions[f'{path.stem}:{qid}'] = entry

    if args.verify_all:
        verify_all(args, questions)
        return
    if args.verify_sample:
        verify_sample(args, questions)
        return

    assigned: dict[str, dict] = {}
    pending: list[tuple[str, str, list[str]]] = []
    for key, entry in questions.items():
        phrases = [str(p) for p in (entry.get('key_concepts') or [])]
        hits = deterministic(phrases, lookup)
        if hits:
            assigned[key] = {'topics': [h['topic'] for h in hits], 'evidence': hits}
        else:
            summary = str(entry.get('reference_answer') or '')[:300]
            pending.append((key, summary, phrases))

    print(f'題目 {len(questions)}｜別名比對標到 {len(assigned)}'
          f'（{len(assigned) / len(questions):.1%}）｜待模型指派 {len(pending)}')
    if args.dry_run:
        return

    load_env_file()
    models = [m.strip() for m in args.models.split(',') if m.strip()]
    votes: dict[str, Counter] = {key: Counter() for key, _, _ in pending}
    rejected: list[dict] = []

    for model in models:
        failed = []
        for start in range(0, len(pending), BATCH_SIZE):
            batch = pending[start:start + BATCH_SIZE]
            raw = None
            for attempt in range(1, args.retries + 2):
                raw = call_gateway(build_prompt(names, batch), model,
                                   args.timeout, None, args.max_tokens)
                if parse_assignments(raw):
                    break
                reason = '空回應' if not raw else f'回應無法解析（{len(raw)} 字，可能被截斷）'
                print(f'  {model} 批 {start // BATCH_SIZE + 1} 第 {attempt} 次{reason}，重試中')
            result = parse_assignments(raw)
            if not result:
                failed.append(start // BATCH_SIZE + 1)
                continue
            for qid, picked in result.items():
                if qid not in votes:
                    continue
                for name in picked[:MAX_TOPICS]:
                    key = normalise(name)
                    if key in valid:
                        votes[qid][valid[key]] += 1
                    else:
                        rejected.append({'question': qid, 'model': model, 'topic': name,
                                         'note': '不在詞彙表裡（自創或改寫）'})
        if failed:
            raise SystemExit(f'FAIL {model} 有 {len(failed)} 批沒有結果（批 '
                             f'{"、".join(map(str, failed))}），不產出部分結果')
        print(f'  {model} 完成 {len(pending)} 題')

    need = 2 if len(models) >= 3 else 1
    filled = 0
    for key, _, _ in pending:
        picked = [name for name, count in votes[key].most_common(MAX_TOPICS) if count >= need]
        if picked:
            filled += 1
            assigned[key] = {'topics': picked, 'evidence': [
                {'topic': n, 'votes': votes[key][n], 'source': 'model'} for n in picked]}

    coverage = len(assigned) / len(questions)
    payload = {
        'status': 'draft',
        'date': None,
        'vocabulary': str(VOCAB_PATH.relative_to(BASE)),
        'models': models,
        'consensusRequired': need,
        'questionCount': len(questions),
        'assignedCount': len(assigned),
        'coverage': round(coverage, 4),
        'byAlias': sum(1 for v in assigned.values() if v['evidence'][0]['source'] == 'alias'),
        'byModel': filled,
        'unassigned': sorted(set(questions) - set(assigned)),
        'rejectedTopics': rejected,
        'aliasQuality': alias_quality(topics),
        'assignments': dict(sorted(assigned.items())),
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\n別名 {payload["byAlias"]}｜模型 {filled}（需 {need}/{len(models)} 票）｜'
          f'仍未標 {len(payload["unassigned"])}｜覆蓋率 {coverage:.1%}')
    if rejected:
        print(f'⚠ 擋下 {len(rejected)} 個不在詞彙表裡的標籤（模型自創），已記在 rejectedTopics')
    quality = payload['aliasQuality']
    print(f'別名品質：{quality["lookupEntries"]} 條查找鍵，'
          f'指向多個概念 {quality["ambiguousEntries"]}、'
          f'「正式名稱同時是別名」{quality["canonicalNameUsedAsAlias"]} 組'
          f'（別名是模型自由文字，這是這步的精確度上限）')
    print(f'→ {OUT_PATH.relative_to(BASE)}')


if __name__ == '__main__':
    main()
