#!/usr/bin/env python3
"""Condense the reference answers' free-form key_concepts into a controlled vocabulary.

`examReferenceAnswers/*.json` carries `key_concepts` for 561 official questions —
3,018 phrases in total, but they are per-question notes, not labels: 87% occur exactly
once ("Human-over-the-loop：人類位於 AI 系統上層進行監督"). Deterministic normalisation
(NFKC, strip bracketed English, cut after the colon) only gets 2,678 → 2,607 distinct,
so collapsing them is a semantic job.

This script asks a gateway model to fold each subject's phrases into ~30–60 canonical
topics with aliases and a parent group, then merges the per-subject drafts by alias.
The output is a DRAFT for human review — the point of a controlled vocabulary is that
someone signs off on it. Free-form tags drift (see playbook/07 §3: letting the model
choose 題型 freely produced 7 spellings of the same label).

Usage:
  python3 scripts/build_topic_vocabulary.py [--model glm-5.2] [--limit-exams N]
  python3 scripts/build_topic_vocabulary.py --show     # print the existing draft
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_question_answers import call_gateway, load_env_file  # noqa: E402

BASE = Path(__file__).resolve().parents[1]
REFERENCE_DIR = BASE / 'frontend' / 'src' / 'generated' / 'examReferenceAnswers'
OUT_PATH = BASE / 'data' / 'topics' / 'topics_draft.json'
# Raw per-subject drafts live in their own file: --consolidate must always restart
# from them (consolidating an already-consolidated list compounds merges), but they
# are 90 KB of intermediate output that would bloat the reviewable vocabulary.
DRAFTS_PATH = BASE / 'data' / 'topics' / '_drafts_by_subject.json'

# Which subject each exam key belongs to, so the vocabulary keeps subject provenance.
SUBJECT_OF_EXAM = {
    'jr_1141_s1': '初級科目一', 'jr_1151_s1': '初級科目一', 'jr_1152_s1': '初級科目一',
    'jr_1141_s2': '初級科目二', 'jr_1151_s2': '初級科目二', 'jr_1152_s2': '初級科目二',
    'mid_1141_s1': '中級科目一', 'mid_1141_s2': '中級科目二', 'mid_1141_s3': '中級科目三',
    'sample': '初級樣張', 'midSample': '中級樣張',
}


def normalise(phrase: str) -> str:
    text = unicodedata.normalize('NFKC', phrase)
    text = re.split(r'[：:]', text)[0]
    text = re.sub(r'[（(][^）)]*[）)]', '', text)
    return re.sub(r'\s+', '', text).strip('。，、 ')


def collect() -> dict[str, collections.Counter]:
    """subject → Counter(normalised phrase → occurrences)."""
    by_subject: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for path in sorted(REFERENCE_DIR.glob('*.json')):
        exam_key = path.stem
        subject = SUBJECT_OF_EXAM.get(exam_key)
        if not subject:
            continue
        for question in json.loads(path.read_text(encoding='utf-8')).values():
            if not isinstance(question, dict):
                continue
            for phrase in question.get('key_concepts') or []:
                cleaned = normalise(phrase)
                if cleaned:
                    by_subject[subject][cleaned] += 1
    return by_subject


def build_prompt(subject: str, phrases: collections.Counter) -> str:
    listing = '\n'.join(f'{count}\t{phrase}'
                        for phrase, count in phrases.most_common())
    return f"""你在為 iPAS AI 應用規劃師考試教材建立**受控概念詞彙表**。

以下是從「{subject}」歷屆試題詳解抽出的概念詞組，格式為「出現次數<TAB>詞組」。
這些是逐題筆記，同一個概念常有多種寫法，需要收斂成可以當標籤用的標準概念。

收斂規則：
- 產出 30~60 個標準概念，數量寧少勿多；只出現一次的細碎詞組要併進上位概念。
- 每個概念要能當作題目標籤：名稱簡短（2~12 字）、是名詞或名詞片語，不要寫成句子。
- 中文為主，英文只放在 aliases。
- 每個概念指定一個 parent 大類（如「機器學習基礎」「模型評估」「生成式AI應用」
  「資料處理」「AI治理與風險」等，大類自己歸納，總數控制在 6~10 個）。
- aliases 放同義寫法與英文，方便之後把原始詞組對回標準概念。

只輸出 JSON，不要任何說明文字：
{{"topics":[{{"name":"過擬合","parent":"模型評估","aliases":["overfitting","過度擬合","泛化能力不足"]}}]}}

詞組清單（共 {len(phrases)} 個）：
{listing}
"""


def parse_topics(raw: str | None) -> list[dict[str, Any]]:
    if not raw:
        return []
    text = raw.strip()
    if text.startswith('```'):
        text = '\n'.join(text.split('\n')[1:])
        text = text.rsplit('```', 1)[0]
    start, end = text.find('{'), text.rfind('}')
    if start < 0 or end < 0:
        return []
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return []
    topics = data.get('topics')
    return topics if isinstance(topics, list) else []


def merge(drafts: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Fold per-subject drafts together, keyed by canonical NAME only.

    ⚠️ Do not key on aliases. They are free-form model output, and merging on a shared
    alias takes the transitive closure: one bad link collapsed 「欠擬合」、「過擬合」、
    「特徵工程」、「資料標準化」 into a single entry with 133 aliases.
    """
    merged: dict[str, dict[str, Any]] = {}
    for subject, topics in drafts.items():
        for topic in topics:
            name = str(topic.get('name', '')).strip()
            if not name:
                continue
            key = normalise(name)
            entry = merged.setdefault(key, {'name': name, 'parent': topic.get('parent', ''),
                                            'aliases': [], 'subjects': []})
            for alias in topic.get('aliases', []):
                alias = str(alias).strip()
                if alias and alias != entry['name'] and alias not in entry['aliases']:
                    entry['aliases'].append(alias)
            if subject not in entry['subjects']:
                entry['subjects'].append(subject)
    return sorted(merged.values(), key=lambda t: (t['parent'], t['name']))


def build_parent_prompt(parents: list[str]) -> str:
    """Only the parent names go to the model — a small input with a small output.

    Asking for the whole re-organised vocabulary in one JSON (130 topics with aliases)
    reliably came back empty: the model spends its budget on reasoning and returns an
    empty string. Keep LLM calls to the part that genuinely needs judgement.
    """
    listing = '\n'.join(f'- {parent}' for parent in parents)
    return f"""以下是一份 iPAS 考試概念詞彙表的大類清單，由多個科目分別產出，命名各自為政，
出現多組同義大類（例如「模型評估」「模型評估與優化」「模型評估與監控」「模型評估與選擇」）。

請把它們歸併成 **6~10 個**命名一致、彼此不重疊的大類，並給出每個原大類對應到哪一個新大類。

只輸出 JSON，不要說明文字：
{{"map":{{"模型評估與優化":"模型評估與調校","模型評估與監控":"模型評估與調校"}}}}

原大類清單（共 {len(parents)} 個）：
{listing}
"""


def parse_map(raw: str | None) -> dict[str, str]:
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
    mapping = data.get('map')
    return {str(k): str(v) for k, v in mapping.items()} if isinstance(mapping, dict) else {}


# Chinese modifiers that flip or narrow the meaning: 「非監督式學習」contains
# 「監督式學習」but is its opposite. Substring containment alone merged those two.
MEANING_CHANGING_PREFIX = ('非', '半', '自', '反', '無', '未', '不', '逆', '弱', '多')


def safe_to_merge(shorter: str, longer: str) -> bool:
    if shorter not in longer:
        return False
    extra = longer.replace(shorter, '', 1)
    return not any(ch in extra for ch in MEANING_CHANGING_PREFIX)


def dedupe_concepts(topics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge duplicates by NAME only (equal, or one contains the other).

    Aliases are deliberately not merge keys — see merge(). Every merge is printed so a
    reviewer can spot a bad one instead of discovering it inside a 133-alias blob.
    """
    survivors: list[dict[str, Any]] = []
    for topic in sorted(topics, key=lambda t: (len(t['name']), t['name'])):
        name = normalise(topic['name'])
        target = next((s for s in survivors
                       if normalise(s['name']) == name
                       or (len(name) >= 4 and len(normalise(s['name'])) >= 4
                           and (safe_to_merge(normalise(s['name']), name)
                                or safe_to_merge(name, normalise(s['name']))))),
                      None)
        if target is None:
            survivors.append({'name': topic['name'], 'parent': topic.get('parent', ''),
                              'aliases': list(dict.fromkeys(topic.get('aliases', []))),
                              'subjects': list(topic.get('subjects', []))})
            continue
        print(f'  合併「{topic["name"]}」→「{target["name"]}」')
        for alias in [topic['name'], *topic.get('aliases', [])]:
            if alias != target['name'] and alias not in target['aliases']:
                target['aliases'].append(alias)
        for subject in topic.get('subjects', []):
            if subject not in target['subjects']:
                target['subjects'].append(subject)
    return survivors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--model', default='glm-5.2')
    parser.add_argument('--timeout', type=int, default=300)
    parser.add_argument('--max-tokens', type=int, default=8000)
    parser.add_argument('--retries', type=int, default=2)
    parser.add_argument('--workers', type=int, default=2,
                        help='網關併發；調高容易拿到空回應（實測 4 併發時 7 組有 4 組失敗）')
    parser.add_argument('--remap', action='store_true',
                        help='重新向模型要一次大類歸併（預設沿用已存的，保持可重現）')
    parser.add_argument('--consolidate', action='store_true',
                        help='對既有草稿再跑一次統整（合併同義大類與重複概念）')
    parser.add_argument('--show', action='store_true', help='print the existing draft')
    args = parser.parse_args()

    if args.show:
        draft = json.loads(OUT_PATH.read_text(encoding='utf-8'))
        by_parent: dict[str, list[str]] = collections.defaultdict(list)
        for topic in draft['topics']:
            by_parent[topic['parent']].append(topic['name'])
        for parent, names in sorted(by_parent.items()):
            print(f'\n## {parent}（{len(names)}）')
            print('   ' + '、'.join(names))
        print(f'\n合計 {len(draft["topics"])} 個概念，{len(by_parent)} 個大類')
        return

    load_env_file()

    if args.consolidate:
        draft = json.loads(OUT_PATH.read_text(encoding='utf-8'))
        # Always restart from the per-subject drafts. Consolidating an already
        # consolidated list compounds merges on every rerun.
        cached = json.loads(DRAFTS_PATH.read_text(encoding='utf-8')) \
            if DRAFTS_PATH.exists() else None
        before = merge(cached) if cached else draft['topics']
        parents = sorted({t.get('parent', '') for t in before if t.get('parent')})

        # The parent grouping is an LLM call, so it differs run to run (7 groups one
        # time, 8 the next). Reuse the stored mapping unless --remap is given, or the
        # vocabulary silently reorganises itself on every rerun.
        mapping: dict[str, str] = {} if args.remap else draft.get('parentMap', {})
        if mapping:
            print(f'沿用已存的大類歸併（{len(set(mapping.values()))} 個大類）；'
                  f'要重新歸併請加 --remap')
        for attempt in range(1, args.retries + 2 if not mapping else 1):
            raw = call_gateway(build_parent_prompt(parents), args.model,
                               args.timeout, None, args.max_tokens)
            mapping = parse_map(raw)
            if mapping:
                break
            # Distinguish "model returned nothing" from "returned truncated JSON":
            # the second means max_tokens is too small, and retrying will not help.
            reason = '空回應' if not raw else f'回應無法解析（{len(raw)} 字，可能被截斷）'
            print(f'  大類歸併第 {attempt} 次{reason}，重試中')
        if not mapping:
            raise SystemExit('FAIL 大類歸併沒有產出，草稿保持原狀')

        unmapped = [p for p in parents if p not in mapping]
        if unmapped:
            print(f'WARN {len(unmapped)} 個大類沒被歸併，維持原名：{"、".join(unmapped)}')
        for topic in before:
            topic['parent'] = mapping.get(topic.get('parent', ''), topic.get('parent', ''))

        topics = sorted(dedupe_concepts(before), key=lambda t: (t['parent'], t['name']))
        draft.update({'topics': topics, 'consolidated': True, 'parentMap': mapping})
        OUT_PATH.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'統整：{len(before)} 概念 / {len(parents)} 大類 → '
              f'{len(topics)} 概念 / {len({t["parent"] for t in topics})} 大類')
        return

    by_subject = collect()
    print(f'{sum(len(c) for c in by_subject.values())} 個相異詞組，'
          f'{len(by_subject)} 個科目分組')

    def condense(subject: str) -> list[dict[str, Any]]:
        prompt = build_prompt(subject, by_subject[subject])
        for attempt in range(1, args.retries + 2):
            topics = parse_topics(call_gateway(prompt, args.model, args.timeout,
                                               None, args.max_tokens))
            if topics:
                return topics
            print(f'  {subject}: 第 {attempt} 次無結果，重試中')
        return []

    drafts: dict[str, list[dict[str, Any]]] = {}
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(condense, subject): subject for subject in by_subject}
        for future in as_completed(futures):
            subject = futures[future]
            drafts[subject] = future.result()
            print(f'  {subject}: {len(by_subject[subject])} 詞組 → {len(drafts[subject])} 概念')

    failed = [subject for subject, topics in drafts.items() if not topics]
    if failed:
        # A vocabulary missing whole subjects looks complete but silently drops their
        # concepts — refuse to write rather than ship a partial one.
        raise SystemExit(f'FAIL 這些分組沒有產出，草稿未寫出：{", ".join(failed)}')

    topics = merge(drafts)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    DRAFTS_PATH.write_text(json.dumps(drafts, ensure_ascii=False, indent=2), encoding='utf-8')
    OUT_PATH.write_text(json.dumps({
        'status': 'draft',
        'model': args.model,
        'source': 'frontend/src/generated/examReferenceAnswers key_concepts',
        'phraseCount': sum(sum(c.values()) for c in by_subject.values()),
        'topics': topics,
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\n合併後 {len(topics)} 個概念 → {OUT_PATH.relative_to(BASE)}')
    print('這是草稿，請人工過目後才定案（--show 可分類印出）')


if __name__ == '__main__':
    main()
