#!/usr/bin/env python3
"""Condense the reference answers' free-form key_concepts into a controlled vocabulary.

`examReferenceAnswers/*.json` carries `key_concepts` for 565 official/sample questions —
3,034 phrases in total, but they are per-question notes, not labels: 2,489/2,685 distinct
forms (93%) occur exactly once ("Human-over-the-loop：人類位於 AI 系統上層進行監督").
Deterministic normalisation (NFKC, strip bracketed English, cut after the colon) only
gets 2,685 → 2,613 distinct,
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

from resource_catalog import exam_entries, level_entry

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_question_answers import call_gateway, load_env_file  # noqa: E402

BASE = Path(__file__).resolve().parents[1]
REFERENCE_DIR = BASE / 'frontend' / 'src' / 'generated' / 'examReferenceAnswers'
OUT_PATH = BASE / 'data' / 'topics' / 'topics_draft.json'
# Raw per-subject drafts live in their own file: --consolidate must always restart
# from them (consolidating an already-consolidated list compounds merges), but they
# are 90 KB of intermediate output that would bloat the reviewable vocabulary.
DRAFTS_PATH = BASE / 'data' / 'topics' / '_drafts_by_subject.json'
MANUAL_TOPIC_ADDITIONS_PATH = (
    BASE / 'data' / 'topics' / 'manual_topic_additions.json'
)

def catalog_subject_label(exam: dict[str, Any]) -> str:
    data_level = level_entry(level_id=exam['levelId'])['dataLevel']
    if exam['kind'] == 'sample':
        return f'{data_level}樣張'
    match = re.search(r'科目[一二三四五六]', exam['label'])
    return f'{data_level}{match.group(0)}' if match else data_level


# Which frontend exam route belongs to which subject, derived from the catalog so
# newly exported reference-answer files participate without another mapping edit.
SUBJECT_OF_EXAM = {
    exam['routeKey']: catalog_subject_label(exam)
    for exam in exam_entries()
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


PAIRS_PATH = BASE / 'data' / 'topics' / 'merge_pairs.json'
BASELINE_PATH = BASE / 'data' / 'topics' / 'known_duplicate_pairs.json'


def build_pairs_prompt(names: list[str]) -> str:
    listing = '\n'.join(f'- {n}' for n in names)
    return f"""以下是 iPAS AI 應用規劃師考試的受控概念詞彙表，共 {len(names)} 個概念。
請找出「指同一個觀念、應該合併」的配對。

規則：
1. 只輸出配對，不要輸出整份詞彙表。
2. `keep` 與 `drop` 都必須**逐字**出自下面的清單，不可自創或改寫。
3. 只合併真正同義的（同詞異譯、同概念不同寫法）。**層次不同的不要合併**：
   例如「多模態AI」與「多模態生成」是不同層次，「異常偵測」（模型任務）與
   「異常值偵測」（資料清理）是不同工作，都不要合併。
4. 語意相反或範圍相反的絕對不可合併（監督式／非監督式、擬合／過擬合）。
5. `reason` 用一句話說明為什麼是同一個觀念。
6. 不確定就不要輸出——漏掉可以人工補，合錯會靜靜產生事實錯誤。

只輸出 JSON：
{{"pairs":[{{"keep":"保留的名稱","drop":"要併掉的名稱","reason":"一句話"}}]}}

概念清單：
{listing}
"""


def parse_pairs(raw: str | None) -> list[dict[str, str]]:
    if not raw:
        return []
    text = raw.strip()
    if text.startswith('```'):
        text = '\n'.join(text.split('\n')[1:]).rsplit('```', 1)[0]
    start, end = text.find('{'), text.rfind('}')
    if start < 0 or end < 0:
        return []
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return []
    pairs = data.get('pairs')
    return pairs if isinstance(pairs, list) else []


def validate_pairs(pairs: list[dict[str, str]], names: list[str]) -> tuple[list, list]:
    """逐條檢查後回傳 (可採用, 已擋下)。每一條都會被印出來，誤殺要看得見。"""
    known = {normalise(n): n for n in names}
    accepted: list[dict[str, str]] = []
    rejected: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    baseline = json.loads(BASELINE_PATH.read_text(encoding='utf-8')) \
        if BASELINE_PATH.exists() else {'groups': []}
    keep_separate: set[frozenset] = set()
    for group in baseline.get('groups', []):
        for other in group.get('keepSeparate', []):
            keep_separate.add(frozenset({normalise(group['canonical']), normalise(other)}))

    for pair in pairs:
        keep = str(pair.get('keep', '')).strip()
        drop = str(pair.get('drop', '')).strip()
        reason = str(pair.get('reason', '')).strip()
        k, d = normalise(keep), normalise(drop)
        note = None
        if k not in known or d not in known:
            note = '名稱不在詞彙表裡（模型自創或改寫）'
        elif k == d:
            note = 'keep 與 drop 是同一個'
        elif (k, d) in seen or (d, k) in seen:
            note = '重複的配對'
        elif frozenset({k, d}) in keep_separate:
            note = '人工基線標為 keepSeparate（看起來像重複但不是）'
        elif not (safe_to_merge(k, d) or safe_to_merge(d, k)) and (k in d or d in k):
            note = '字串包含但前綴會翻轉語意'
        if note:
            rejected.append({**pair, 'note': note})
            print(f'  擋下「{drop}」→「{keep}」：{note}')
        else:
            seen.add((k, d))
            accepted.append({'keep': known[k], 'drop': known[d], 'reason': reason})
            print(f'  合併「{drop}」→「{keep}」：{reason[:40]}')
    return accepted, rejected


def clusters(pairs: list[tuple[str, str]]) -> dict[str, str]:
    """union-find：回傳 {概念: 叢集代表}。比對用叢集而不是配對——
    「分群演算法/群聚分析/聚類」用哪個當樞紐都是同一件事，不該算成漏掉。"""
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in pairs:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra
    return {x: find(x) for x in parent}


def score_against_baseline(accepted: list[dict[str, str]]) -> dict[str, Any]:
    """對照人工基線：漏太多代表太保守，基線外的新配對要逐條看。"""
    if not BASELINE_PATH.exists():
        return {}
    baseline = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))
    expected_pairs, expected_groups = [], []
    for group in baseline.get('groups', []):
        dups = group.get('duplicates') or []
        if not dups:
            continue
        canon = normalise(group['canonical'])
        expected_groups.append({canon, *(normalise(d) for d in dups)})
        expected_pairs += [(canon, normalise(d)) for d in dups]
    got_pairs = [(normalise(p['keep']), normalise(p['drop'])) for p in accepted]
    got = clusters(got_pairs)

    matched, missed = [], []
    for group in expected_groups:
        roots = {got.get(x) for x in group if x in got}
        if len(roots) == 1 and None not in roots and len([x for x in group if x in got]) == len(group):
            matched.append('｜'.join(sorted(group)))
        else:
            missed.append('｜'.join(sorted(group)))
    expected_flat = {frozenset(p) for p in expected_pairs}
    extra = [f'{a}｜{b}' for a, b in got_pairs
             if frozenset({a, b}) not in expected_flat
             and not any({a, b} <= g for g in expected_groups)]
    return {'baselineGroups': len(expected_groups), 'matchedGroups': len(matched),
            'missed': sorted(missed), 'extra': sorted(extra)}


def apply_recorded_alias_cleanup(topics: list[dict[str, Any]]) -> None:
    """Replay the committed human-reviewed alias removals without another LLM call."""
    cleanup = json.loads(CLEAN_PATH.read_text(encoding='utf-8'))
    by_name = {topic['name']: topic for topic in topics}
    for field in ('removedBecauseCanonicalElsewhere', 'removedBecauseAmbiguous'):
        records = cleanup.get(field)
        if not isinstance(records, list):
            raise SystemExit(f'FAIL alias cleanup 缺少 {field}')
        for record in records:
            topic_name = str(record.get('from') or '')
            alias = str(record.get('alias') or '')
            topic = by_name.get(topic_name)
            if topic is None:
                raise SystemExit(f'FAIL alias cleanup 找不到概念「{topic_name}」')
            aliases = topic.get('aliases') or []
            if alias not in aliases:
                raise SystemExit(
                    f'FAIL alias cleanup 在「{topic_name}」找不到別名「{alias}」'
                )
            aliases.remove(alias)


def apply_manual_topic_additions(
    topics: list[dict[str, Any]],
) -> dict[str, Any]:
    """Apply the signed-off post-draft vocabulary overlay deterministically."""
    overlay = json.loads(MANUAL_TOPIC_ADDITIONS_PATH.read_text(encoding='utf-8'))
    if overlay.get('schemaVersion') != 1:
        raise SystemExit('FAIL manual topic additions schemaVersion 不支援')
    additions = overlay.get('topics')
    removals = overlay.get('removeAliases')
    subject_additions = overlay.get('addSubjects')
    if (
        not isinstance(additions, list)
        or not isinstance(removals, dict)
        or not isinstance(subject_additions, dict)
    ):
        raise SystemExit('FAIL manual topic additions 結構不完整')

    by_name = {topic['name']: topic for topic in topics}
    for topic_name, aliases in removals.items():
        topic = by_name.get(topic_name)
        if topic is None or not isinstance(aliases, list):
            raise SystemExit(f'FAIL manual topic alias removal 無效：「{topic_name}」')
        for alias in aliases:
            if alias not in topic.get('aliases', []):
                raise SystemExit(
                    f'FAIL manual topic alias removal 在「{topic_name}」找不到「{alias}」'
                )
            topic['aliases'].remove(alias)

    for topic_name, subjects in subject_additions.items():
        topic = by_name.get(topic_name)
        if topic is None or not isinstance(subjects, list):
            raise SystemExit(f'FAIL manual topic subject addition 無效：「{topic_name}」')
        for subject in subjects:
            if subject not in topic.get('subjects', []):
                topic['subjects'].append(subject)

    for addition in additions:
        if not isinstance(addition, dict):
            raise SystemExit('FAIL manual topic addition 必須是 object')
        name = str(addition.get('name') or '')
        if not name or name in by_name:
            raise SystemExit(f'FAIL manual topic addition 名稱缺漏或重複：「{name}」')
        for field in ('parent', 'aliases', 'subjects'):
            if field not in addition:
                raise SystemExit(f'FAIL manual topic addition「{name}」缺少 {field}')
        topics.append(addition)
        by_name[name] = addition

    topics.sort(key=lambda topic: (topic['parent'], topic['name']))
    return overlay




def apply_merge_pairs() -> None:
    """把已勾選的合併配對套進詞彙表，產出定案版 topics.json。

    合併鍵只用**正式名稱**，別名只做累積（08 §6：拿別名當合併鍵等於取傳遞閉包，
    一條爛連結讓「欠擬合」吞掉 133 個別名）。每一次合併都印出來。
    草稿 topics_draft.json 不動——定案版是另一個檔，隨時可以重來。
    """
    draft = json.loads(OUT_PATH.read_text(encoding='utf-8'))
    decisions = json.loads(PAIRS_PATH.read_text(encoding='utf-8'))

    by_name = {normalise(t['name']): t for t in draft['topics']}
    if len(by_name) != len(draft['topics']):
        raise SystemExit('FAIL 草稿裡有同名概念，先處理再套用')

    merges: list[tuple[str, list[str], str]] = [
        (p['keep'], [p['drop']], p.get('reason', '')) for p in decisions.get('accepted', [])
    ] + [
        (g['keep'], g['drop'], g.get('reason', ''))
        for g in decisions.get('humanDecision', {}).get('groups', [])
    ]

    missing = [n for keep, drops, _ in merges for n in [keep, *drops]
               if normalise(n) not in by_name]
    if missing:
        raise SystemExit(f'FAIL 這些名稱不在詞彙表裡，不套用：{"、".join(sorted(set(missing)))}')

    # 兩份來源可能鏈狀重疊：模型說「聚類→群聚分析」，人工決定說
    # 「群聚分析、聚類→分群演算法」。先把每個 drop 解析到最終保留名，
    # 只有解析結果不同才是真衝突。
    edge: dict[str, str] = {}
    for keep, drops, _ in merges:
        for drop in drops:
            edge[normalise(drop)] = normalise(keep)

    def resolve(name: str, seen: tuple[str, ...] = ()) -> str:
        if name in seen:
            raise SystemExit(f'FAIL 合併成環：{" → ".join(seen + (name,))}')
        return resolve(edge[name], seen + (name,)) if name in edge else name

    final: dict[str, str] = {}
    for keep, drops, _ in merges:
        for drop in drops:
            key, root = normalise(drop), resolve(normalise(keep))
            if key in final and final[key] != root:
                raise SystemExit(f'FAIL「{drop}」被指派給兩個不同的保留名'
                                 f'（{by_name[final[key]]["name"]} / {by_name[root]["name"]}）')
            final[key] = root

    dropped: set[str] = set()
    for key, root in final.items():
        if key not in dropped:
            target, source = by_name[root], by_name[key]
            drop, keep = source['name'], target['name']
            print(f'  合併「{drop}」→「{keep}」')
            for alias in [source['name'], *source.get('aliases', [])]:
                if alias != target['name'] and alias not in target['aliases']:
                    target['aliases'].append(alias)
            for subject in source.get('subjects', []):
                if subject not in target['subjects']:
                    target['subjects'].append(subject)
            dropped.add(key)

    topics = sorted((t for k, t in by_name.items() if k not in dropped),
                    key=lambda t: (t['parent'], t['name']))
    before, after = len(draft['topics']), len(topics)
    # 檢查「有沒有字串消失」而不是總數：兩個被合併的概念常共用別名，
    # 去重後總數本來就會變少（過擬合／過擬合與泛化 就少了 200 多筆）。
    def strings(items: list[dict]) -> set[str]:
        return {t['name'] for t in items} | {a for t in items for a in t.get('aliases', [])}
    lost = strings(draft['topics']) - strings(topics)
    if lost:
        raise SystemExit(f'FAIL 這些名稱／別名整個消失了：{"、".join(sorted(lost)[:10])}')
    alias_before = sum(len(t.get('aliases', [])) for t in draft['topics'])
    apply_recorded_alias_cleanup(topics)
    manual = apply_manual_topic_additions(topics)
    alias_after = sum(len(t.get('aliases', [])) for t in topics)

    payload = {
        **{k: v for k, v in draft.items() if k != 'topics'},
        'status': 'signed-off',
        'phraseCount': manual.get('phraseCount'),
        'signedOff': manual.get('date'),
        'manualAdditions': {
            'source': str(MANUAL_TOPIC_ADDITIONS_PATH.relative_to(BASE)),
            'date': manual.get('date'),
            'topics': [topic['name'] for topic in manual['topics']],
            'reason': manual.get('reason'),
        },
        'mergedFrom': str(OUT_PATH.relative_to(BASE)),
        'mergeDecisions': str(PAIRS_PATH.relative_to(BASE)),
        'aliasCleanup': str(CLEAN_PATH.relative_to(BASE)),
        'topics': topics,
    }
    FINAL_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8'
    )
    print(f'\n概念 {before} → {len(topics)}（合併 {len(dropped)}、人工補簽 '
          f'{len(manual["topics"])}），'
          f'別名 {alias_before} → {alias_after}')
    try:
        print(f'→ {FINAL_PATH.relative_to(BASE)}')
    except ValueError:
        print(f'→ {FINAL_PATH}')


CLEAN_PATH = BASE / 'data' / 'topics' / 'alias_cleanup.json'
FINAL_PATH = BASE / 'data' / 'topics' / 'topics.json'


def clean_aliases(model: str, timeout: int, max_tokens: int, retries: int) -> None:
    """清掉會讓標籤失準的別名，重寫 topics.json。

    標籤指派靠「別名 → 概念」比對，實測精確度只有 62%、13% 是明確錯誤。
    根因不是指派邏輯，是別名本身（08 §6：alias 是模型自由文字、品質不受控）。
    兩類雜訊，處置不同：

      A. 別名剛好是另一個概念的正式名稱（32 組）。這是**上下位關係**不是同義詞——
         「物件偵測」是「電腦視覺」的別名，於是一題考物件偵測會同時被標上電腦視覺，
         上位概念因此虛胖。確定性移除，不必問模型。
      B. 一個詞同時是多個概念的別名（88 條）。無法確定性決定歸屬，交給模型從
         候選裡挑一個，輸出小、可逐條稽核；挑不出來就整條移除（寧可少標）。

    移除的別名全部記進 alias_cleanup.json，不是靜靜消失。
    """
    vocab = json.loads(FINAL_PATH.read_text(encoding='utf-8'))
    topics = vocab['topics']
    canonical = {normalise(t['name']): t['name'] for t in topics}

    removed_clash: list[dict[str, str]] = []
    for topic in topics:
        kept = []
        for alias in topic.get('aliases', []):
            key = normalise(alias)
            if key in canonical and canonical[key] != topic['name']:
                removed_clash.append({'alias': alias, 'from': topic['name'],
                                      'reason': f'「{canonical[key]}」本身就是一個概念'})
            else:
                kept.append(alias)
        topic['aliases'] = kept
    print(f'A 類（別名是另一個概念的正式名稱）移除 {len(removed_clash)} 條')

    owners: dict[str, list[str]] = {}
    for topic in topics:
        for alias in topic['aliases']:
            owners.setdefault(normalise(alias), []).append(topic['name'])
    ambiguous = {k: v for k, v in owners.items() if len(v) > 1}
    print(f'B 類（一詞多概念）待決 {len(ambiguous)} 條')

    decisions: dict[str, str] = {}
    if ambiguous:
        load_env_file()
        display = {}
        for topic in topics:
            for alias in topic['aliases']:
                display.setdefault(normalise(alias), alias)
        entries = sorted(ambiguous.items())
        for start in range(0, len(entries), 25):
            chunk = entries[start:start + 25]
            listing = '\n'.join(
                f'- 「{display[key]}」候選：{"、".join(names)}' for key, names in chunk)
            prompt = f"""下列詞組同時被登記成多個概念的別名，請為每一個挑出**唯一最貼切**的概念。

規則：
1. `topic` 必須是該詞組候選之一，逐字照抄。
2. 若這個詞組其實跟哪個都不夠貼切，`topic` 給空字串——寧可少標也不要標錯。

只輸出 JSON：{{"picks":[{{"alias":"詞組","topic":"概念"}}]}}

{listing}
"""
            raw = None
            for _ in range(retries + 1):
                raw = call_gateway(prompt, model, timeout, None, max_tokens)
                if raw and '"picks"' in raw:
                    break
            text = (raw or '').strip()
            if text.startswith('```'):
                text = '\n'.join(text.split('\n')[1:]).rsplit('```', 1)[0]
            begin, end = text.find('{'), text.rfind('}')
            if begin < 0:
                raise SystemExit('FAIL 一詞多概念的歸屬沒有結果，詞彙表保持原狀')
            try:
                data = json.loads(text[begin:end + 1])
            except json.JSONDecodeError:
                raise SystemExit('FAIL 歸屬回應無法解析，詞彙表保持原狀')
            for row in data.get('picks') or []:
                alias = normalise(str(row.get('alias', '')))
                pick = str(row.get('topic', '')).strip()
                if alias in ambiguous and pick in ambiguous[alias]:
                    decisions[alias] = pick

    removed_ambiguous: list[dict[str, str]] = []
    for topic in topics:
        kept = []
        for alias in topic['aliases']:
            key = normalise(alias)
            if key in ambiguous and decisions.get(key) != topic['name']:
                removed_ambiguous.append({
                    'alias': alias, 'from': topic['name'],
                    'reason': f'歸給「{decisions[key]}」' if key in decisions else '無法歸屬，整條移除'})
            else:
                kept.append(alias)
        topic['aliases'] = kept
    print(f'B 類移除 {len(removed_ambiguous)} 條'
          f'（歸屬成功 {len(decisions)}／{len(ambiguous)}）')

    CLEAN_PATH.write_text(json.dumps({
        'date': '2026-08-08', 'model': model,
        'removedBecauseCanonicalElsewhere': removed_clash,
        'removedBecauseAmbiguous': removed_ambiguous,
        'ambiguousDecisions': decisions,
    }, ensure_ascii=False, indent=2), encoding='utf-8')

    before = sum(len(t.get('aliases', [])) for t in json.loads(
        FINAL_PATH.read_text(encoding='utf-8'))['topics'])
    after = sum(len(t['aliases']) for t in topics)
    vocab['topics'] = topics
    vocab['aliasCleanup'] = str(CLEAN_PATH.relative_to(BASE))
    FINAL_PATH.write_text(json.dumps(vocab, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'別名 {before} → {after}（移除 {before - after}）')
    print(f'→ {FINAL_PATH.relative_to(BASE)}、{CLEAN_PATH.relative_to(BASE)}')


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
    parser.add_argument('--clean-aliases', action='store_true',
                        help='清掉會讓標籤失準的別名（上下位關係、一詞多概念）')
    parser.add_argument('--apply-pairs', action='store_true',
                        help='把已勾選的合併配對套進詞彙表 → data/topics/topics.json')
    parser.add_argument('--dedupe-pairs', action='store_true',
                        help='語意去重：只輸出合併配對清單（§7-1），不動詞彙表本身')
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

    if args.clean_aliases:
        clean_aliases(args.model, args.timeout, args.max_tokens, args.retries)
        return

    if args.apply_pairs:
        apply_merge_pairs()
        return

    load_env_file()

    if args.dedupe_pairs:
        draft = json.loads(OUT_PATH.read_text(encoding='utf-8'))
        names = [t['name'] for t in draft['topics']]
        # 一次送 204 個概念只挖到 10 組（人工基線 29 組）——清單太長，模型只挑
        # 最明顯的同詞異譯。改成「每個大類各問一次 + 全域再問一次」，聯集起來；
        # 重複的配對會在 validate_pairs 被擋掉，所以多問只會提高召回不會重複合併。
        by_parent: dict[str, list[str]] = collections.defaultdict(list)
        for topic in draft['topics']:
            by_parent[topic.get('parent') or '（未分類）'].append(topic['name'])
        batches = [(f'大類：{parent}', group)
                   for parent, group in sorted(by_parent.items()) if len(group) >= 2]
        batches.append(('全域', names))
        print(f'語意去重：{len(names)} 個概念，分 {len(batches)} 批送審，只要合併配對清單')

        pairs: list[dict[str, str]] = []
        failed: list[str] = []
        for label, group in batches:
            raw = None
            for attempt in range(1, args.retries + 2):
                raw = call_gateway(build_pairs_prompt(group), args.model,
                                   args.timeout, None, args.max_tokens)
                if parse_pairs(raw) or (raw and '"pairs"' in raw):
                    break
                reason = '空回應' if not raw else f'回應無法解析（{len(raw)} 字，可能被截斷）'
                print(f'  {label} 第 {attempt} 次{reason}，重試中')
            got = parse_pairs(raw)
            if not got and not (raw and '"pairs"' in raw):
                failed.append(label)
            print(f'  {label}（{len(group)} 個概念）→ {len(got)} 組')
            pairs += got
        # 分組失敗只回空陣列、程式照樣合併剩下的並印出成功——是這條線踩過的坑。
        if failed:
            raise SystemExit(f'FAIL {len(failed)} 批沒有結果（{"、".join(failed)}），'
                             '不產出看起來完整的部分結果')
        if not pairs:
            raise SystemExit('FAIL 沒有拿到任何配對，詞彙表保持原狀')
        print()

        accepted, rejected = validate_pairs(pairs, names)
        score = score_against_baseline(accepted)
        payload = {
            'status': 'pending-human-review',
            'source': str(OUT_PATH.relative_to(BASE)),
            'model': args.model,
            'topicCount': len(names),
            'note': ('這是待人工勾選的合併配對清單，不是已定案的詞彙表。'
                     '勾掉錯的之後才可以套用，套用後才能做 §7-2 標題。'),
            'accepted': accepted,
            'rejected': rejected,
            'baselineScore': score,
            # 模型不肯合、但人工基線認為該合的組。模型對複合名稱（「AI治理與倫理」
            # vs「負責任AI與倫理」）一律保守，這正是要人來拍板的部分——留在這裡
            # 逐條勾選，不要讓模型自己決定。
            'pendingHumanDecision': [
                {'group': g.split('｜'), 'decision': None} for g in score.get('missed', [])
            ],
        }
        PAIRS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                              encoding='utf-8')
        print(f'\n模型給 {len(pairs)} 組，採用 {len(accepted)}、擋下 {len(rejected)}')
        if score:
            print(f'對照人工基線：{score["matchedGroups"]}/{score["baselineGroups"]} 組命中，'
                  f'基線外的新配對 {len(score["extra"])} 組')
            if score['missed']:
                print(f'  漏掉（需人工判斷是模型太保守還是基線寫錯）：'
                      f'{"、".join(score["missed"][:8])}')
        print(f'→ {PAIRS_PATH.relative_to(BASE)}（待人工勾選）')
        return

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
