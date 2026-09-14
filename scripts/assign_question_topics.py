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

**穩定 id（LP-210C）**：輸出的每個正式名稱旁都同時寫詞彙表的穩定 id
（`topics`↔`topicIds`、`evidence[].topicId`、`droppedAsWrong`↔`droppedAsWrongIds`），
名稱欄位保留給舊讀取器；快取也帶 id（`topic-cache/v2`），概念改名後仍對得回來。
`--backfill-ids` 不呼叫模型，只把既有標註檔與快取補上 id（純新增、冪等、寫入前先證明無損）。

用法：
    python3 scripts/assign_question_topics.py --dry-run     # 只看確定性覆蓋率
    python3 scripts/assign_question_topics.py               # 含模型補標
    python3 scripts/assign_question_topics.py --models glm-5.2,deepseek-v4-pro,kimi-k2.7-code
    python3 scripts/assign_question_topics.py --backfill-ids                    # 官方卷標註＋快取補 id
    python3 scripts/assign_question_topics.py --source practice --backfill-ids  # 練習題那份
"""

from __future__ import annotations

import argparse
import json
import sys
import time
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
# 練習題的標籤**另外存一份**：topicHeat 的「熱度」定義是「這個概念被官方考卷考幾題」，
# 把章節練習與指引練習混進同一份會讓熱度膨脹，而出題配額、glossary 選詞都吃那個數字。
PRACTICE_OUT_PATH = BASE / 'data' / 'topics' / 'practice_question_topics.json'
VERIFY_CACHE = BASE / 'data' / 'topics' / '_verify_cache.json'
# 指派也要能續跑。2026-08-10：590 題跑到第 50 批時有 13 批被網關打成空回應，
# 「不產出部分結果」是對的，但連同 37 批成功的也一起丟掉就不對了——
# 嚴格（不完整就不寫出）與可續跑是兩回事，驗收那段早就有快取，這段漏了。
ASSIGN_CACHE = BASE / 'data' / 'topics' / '_assign_cache.json'
MAX_TOPICS = 3
BATCH_SIZE = 12
# 驗收一題要評 1~3 個標籤，輸出量是指派的三倍，批要更小才不會被 max_tokens 截掉
VERIFY_BATCH_SIZE = 6
# 快取格式。v1 是名稱型（指派：`模型|題號 → [名稱]`；驗收：`題號 → {名稱: 判定}`），
# 概念一改名就只能靠 normalise 對齊、會靜默錯位。v2 每筆同時帶穩定 id，讀到 v1 會就地升級。
CACHE_FORMAT = 'topic-cache/v2'


def load_json(path: Path) -> Any:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def write_json_atomic(path: Path, payload: Any, *, indent: int | None = 2,
                      trailing_newline: bool = False) -> None:
    """先寫同目錄暫存檔再 replace：快取是 gitignored 的付費產物，寫到一半被中斷不能剩半截。"""
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=indent)
                   + ('\n' if trailing_newline else ''), encoding='utf-8')
    tmp.replace(path)


# --- 穩定 id（LP-210C）-----------------------------------------------------

def topic_ids(vocab: dict) -> dict[str, str]:
    """正式名稱 → 穩定 id。任一概念沒有 id、或 id 重複，整份拒絕——半套的 id 比沒有更糟。"""
    ids: dict[str, str] = {}
    owners: dict[str, str] = {}
    for topic in vocab['topics']:
        identity = topic.get('id')
        if not isinstance(identity, str) or not identity.strip():
            raise SystemExit(f'FAIL 概念「{topic["name"]}」沒有穩定 id。詞彙表要先完成 LP-210B'
                             '（build_topic_vocabulary.py --apply-pairs 會把帳本折回來）')
        if identity in owners:
            raise SystemExit(f'FAIL topic id「{identity}」同時屬於「{owners[identity]}」與「{topic["name"]}」')
        owners[identity] = topic['name']
        ids[topic['name']] = identity
    return ids


def stable_ids_of(vocab: dict) -> dict[str, Any]:
    """詞彙表的 `stableIds` 出處區塊（帳本路徑、指派日、格式），原樣複製進產物。"""
    block = vocab.get('stableIds')
    return dict(block) if isinstance(block, dict) else {'source': str(VOCAB_PATH.relative_to(BASE))}


def resolve_topic_id(name: str, ids: dict[str, str], valid: dict[str, str]) -> str | None:
    """模型回的字串 → id。先比正式名稱，再用 normalise（「生成式 AI」＝「生成式AI」）；
    對不到就 None——那是模型自創的名稱，指派那段本來就會把它記進 rejectedTopics。"""
    if name in ids:
        return ids[name]
    canonical = valid.get(normalise(name))
    return ids[canonical] if canonical else None


def canonicalise_names(payload: dict, by_id: dict[str, str]) -> dict:
    """已帶 id 的欄位以 id 為準，把名稱換成詞彙表**目前**的正式名稱；沒有 id 的欄位不動。

    這是 id 存在的理由：概念改名後，重跑 `--backfill-ids` 就把舊名稱換掉，
    不必重跑模型；詞彙表不認得的 id 保留原名稱，交給後面的名稱檢查去 FAIL。
    """
    def rename(names: list[str], identities: Any) -> list[str]:
        if not isinstance(identities, list) or len(identities) != len(names):
            return names
        return [by_id.get(identity, name) for name, identity in zip(names, identities)]

    out = dict(payload)
    assignments: dict[str, Any] = {}
    for key, entry in payload['assignments'].items():
        row = dict(entry)
        if 'topics' in entry:
            row['topics'] = rename(entry['topics'], entry.get('topicIds'))
        if 'droppedAsWrong' in entry:
            row['droppedAsWrong'] = rename(entry['droppedAsWrong'], entry.get('droppedAsWrongIds'))
        if 'evidence' in entry:
            row['evidence'] = [{**ev, 'topic': by_id.get(ev.get('topicId'), ev['topic'])}
                               for ev in entry['evidence']]
        assignments[key] = row
    out['assignments'] = assignments
    return out


def attach_topic_ids(payload: dict, ids: dict[str, str], by_id: dict[str, str],
                     stable_ids: dict[str, Any]) -> dict:
    """標註輸出：每個正式名稱旁同時寫 id，名稱欄位保留給舊讀取器。

    先依既有 id 把名稱更新到目前的正式名稱（`canonicalise_names`），再處理理應是正式名稱的
    位置（`topics`、`evidence[].topic`、`droppedAsWrong`）：對不到詞彙表就 FAIL 而不是寫 null
    ——標註檔裡出現不在詞彙表的名稱是資料壞了，不是可以帶著走的狀態。
    `rejectedTopics` 本來就是「不在詞彙表」的名稱，不帶 id。
    重複套用是冪等的（先拆舊 id 再重算），`strip_topic_ids` 是它的反函式。
    """
    def id_of(name: str, where: str) -> str:
        if name not in ids:
            raise SystemExit(f'FAIL {where}：「{name}」不是詞彙表的正式名稱，對不到 id'
                             '（概念改名時帶著 id 重跑 --backfill-ids 會自動更新名稱；'
                             '沒有 id 的舊標註要人工對回正式名稱）')
        return ids[name]

    payload = canonicalise_names(payload, by_id)
    out: dict[str, Any] = {}
    for field, value in payload.items():
        if field == 'stableIds':
            continue
        out[field] = value
        if field == 'vocabulary':
            out['stableIds'] = stable_ids
    out.setdefault('stableIds', stable_ids)
    assignments: dict[str, Any] = {}
    for key, entry in payload['assignments'].items():
        row: dict[str, Any] = {}
        for field, value in entry.items():
            if field in ('topicIds', 'droppedAsWrongIds'):
                continue
            if field == 'evidence':
                value = [{'topic': ev['topic'], 'topicId': id_of(ev['topic'], f'{key} evidence'),
                          **{k: v for k, v in ev.items() if k not in ('topic', 'topicId')}}
                         for ev in value]
            row[field] = value
            if field == 'topics':
                row['topicIds'] = [id_of(n, f'{key} topics') for n in value]
            elif field == 'droppedAsWrong':
                row['droppedAsWrongIds'] = [id_of(n, f'{key} droppedAsWrong') for n in value]
        assignments[key] = row
    out['assignments'] = assignments
    return out


def strip_topic_ids(payload: dict) -> dict:
    """拆掉 attach_topic_ids 加的所有欄位，用來證明回填是純新增（拆掉後要與原檔相等）。"""
    out = {k: v for k, v in payload.items() if k != 'stableIds'}
    out['assignments'] = {
        key: {field: ([{k: v for k, v in ev.items() if k != 'topicId'} for ev in value]
                      if field == 'evidence' else value)
              for field, value in entry.items() if field not in ('topicIds', 'droppedAsWrongIds')}
        for key, entry in payload['assignments'].items()}
    return out


def _cache_record(kind: str, name: str, identity: str | None, verdict: str | None = None) -> dict[str, Any]:
    record: dict[str, Any] = {'topic': name, 'topicId': identity}
    if kind == 'verify':
        record['verdict'] = verdict
    return record


def load_cache(path: Path, kind: str, ids: dict[str, str], by_id: dict[str, str],
               valid: dict[str, str]) -> dict[str, list[dict[str, Any]]]:
    """讀指派／驗收快取成 v2 紀錄（`鍵 → [{topic, topicId[, verdict]}]`）；不寫檔。

    v1（名稱型）就地升級：名稱**逐字保留**、id 由名稱解析（對不到就 None）。
    v2 紀錄若已帶詞彙表認得的 id 就以 id 為準——概念改名後名稱對不上，id 還在；
    id 對不到（例如帳本曾拒絕）才回頭用名稱解析，所以上次沒對到的這次可能對得到。
    """
    if not path.exists():
        return {}
    data = load_json(path)
    if isinstance(data, dict) and data.get('format') == CACHE_FORMAT:
        if data.get('kind') != kind:
            raise SystemExit(f'FAIL {path.name} 是 {data.get("kind")!r} 快取，不是 {kind}')
        entries: dict[str, list[dict[str, Any]]] = {}
        for key, records in (data.get('entries') or {}).items():
            entries[key] = []
            for record in records:
                identity = record.get('topicId')
                if identity not in by_id:
                    identity = resolve_topic_id(record['topic'], ids, valid)
                entries[key].append(_cache_record(kind, record['topic'], identity, record.get('verdict')))
        return entries
    if kind == 'assign':
        return {key: [_cache_record(kind, name, resolve_topic_id(name, ids, valid)) for name in names]
                for key, names in data.items()}
    return {key: [_cache_record(kind, name, resolve_topic_id(name, ids, valid), verdict)
                  for name, verdict in judged.items()]
            for key, judged in data.items()}


def legacy_cache_view(kind: str, data: Any) -> Any:
    """任一格式的快取 → v1 形狀。v2 轉回 v1 必須與原 v1 相等，才叫無損。"""
    entries = data['entries'] if isinstance(data, dict) and data.get('format') == CACHE_FORMAT else data
    if kind == 'assign':
        return {key: [r['topic'] if isinstance(r, dict) else r for r in records]
                for key, records in entries.items()}
    return {key: ({r['topic']: r['verdict'] for r in records} if isinstance(records, list) else records)
            for key, records in entries.items()}


def align_cached(topics: list[str], records: list[dict[str, Any]], ids: dict[str, str]) -> dict[str, str]:
    """驗收快取紀錄 → {這題目前的正式名稱: 判定}。

    id 優先：概念改名後名稱對不上，id 還在，判定就跟著搬到新名稱；沒有 id 的舊紀錄
    才退回 normalise 比對。對不到這題任何現有標籤的紀錄丟掉（那個標籤已不在這題上）。
    """
    by_topic_id = {ids[t]: t for t in topics}
    by_norm = {normalise(t): t for t in topics}
    aligned: dict[str, str] = {}
    for record in records:
        canonical = by_topic_id.get(record.get('topicId')) or by_norm.get(normalise(record['topic']))
        if canonical:
            aligned[canonical] = record['verdict']
    return aligned


def save_cache(path: Path, kind: str, entries: dict[str, list[dict[str, Any]]],
               stable_ids: dict[str, Any]) -> None:
    write_json_atomic(path, {'format': CACHE_FORMAT, 'kind': kind, 'stableIds': stable_ids,
                             'entries': entries}, indent=None)


def _canonical_text(payload: Any) -> str:
    """鍵序敏感的比對用：同樣的資料、不同的欄位順序，這裡會視為不同。"""
    return json.dumps(payload, ensure_ascii=False, sort_keys=False)


def backfill_ids(ids: dict[str, str], by_id: dict[str, str], valid: dict[str, str],
                 stable_ids: dict[str, Any]) -> None:
    """LP-210C：不呼叫模型，把既有標註檔與兩個快取改成同時帶 id。

    每個檔案都先在記憶體裡證明「拆掉 id 後與原檔相等」才寫；證明不成立就 FAIL 不寫。
    快取是 gitignored 的付費產物，這裡只新增欄位、不刪任何一筆，且寫入是原子的。
    """
    written: list[str] = []
    if OUT_PATH.exists():
        before = load_json(OUT_PATH)
        after = attach_topic_ids(before, ids, by_id, stable_ids)
        # 證明：拆掉 id 後，與「原檔依自帶 id 更新名稱」的結果**連鍵序都**相等——除了 id 欄位
        # 與 id 指定的改名之外，什麼都沒動（比序列化字串，dict == 看不到欄位重排）。
        if _canonical_text(strip_topic_ids(after)) != _canonical_text(strip_topic_ids(canonicalise_names(before, by_id))):
            raise SystemExit(f'FAIL {OUT_PATH.name} 回填後拆掉 id 與原檔不相等，拒絕寫入')
        renamed = sorted({(name, by_id[identity])
                          for entry in before['assignments'].values()
                          for name, identity in zip(entry.get('topics', []), entry.get('topicIds') or [])
                          if identity in by_id and by_id[identity] != name})
        labels = sum(len(entry['evidence']) for entry in after['assignments'].values())
        if after != before:
            # 保留原檔的結尾換行慣例（人工策展過的檔案有、腳本寫的沒有），diff 才是純新增
            write_json_atomic(OUT_PATH, after,
                              trailing_newline=OUT_PATH.read_bytes().endswith(b'\n'))
            written.append(OUT_PATH.name)
        print(f'{OUT_PATH.name}：{len(after["assignments"])} 題、{labels} 個標籤全部帶 id'
              + ('' if after != before else '（已是最新，未改動）'))
        for old, new in renamed:
            print(f'  依 id 更新改名：「{old}」→「{new}」')
    else:
        print(f'⚠ {OUT_PATH.name} 不存在，略過')
    for path, kind in ((ASSIGN_CACHE, 'assign'), (VERIFY_CACHE, 'verify')):
        if not path.exists():
            print(f'  {path.name}：不存在，略過')
            continue
        before = load_json(path)
        entries = load_cache(path, kind, ids, by_id, valid)
        after = {'format': CACHE_FORMAT, 'kind': kind, 'stableIds': stable_ids, 'entries': entries}
        if _canonical_text(legacy_cache_view(kind, after)) != _canonical_text(legacy_cache_view(kind, before)):
            raise SystemExit(f'FAIL {path.name} 轉換後的名稱／判定與原檔不相等，拒絕寫入')
        records = [record for group in entries.values() for record in group]
        unresolved = sorted({r['topic'] for r in records if r['topicId'] is None})
        if after != before:
            save_cache(path, kind, entries, stable_ids)
            written.append(path.name)
        note = (f'；{len(unresolved)} 個名稱對不到詞彙表（模型自創，原字串保留、id 為 null）：'
                f'{"、".join(unresolved[:5])}' if unresolved else '')
        print(f'  {path.name}：{len(entries)} 筆、{len(records)} 個標籤，'
              f'{sum(1 for r in records if r["topicId"])} 個帶 id{note}'
              + ('' if after != before else '（已是最新，未改動）'))
    print('已寫入：' + ('、'.join(written) if written else '（無變動）'))


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


def resolve_ids(returned: dict[str, Any], expected: set[str]) -> dict[str, Any]:
    """把模型回的題號對回我們的 key。

    我們的 key 是 `{考卷}:{題號}`，但 sample 卷的題號本身就叫 `sample_q27`，
    模型看到 `sample:sample_q27` 會自動把它縮成 `sample_q27` 回來——對不上就被
    靜默丟掉，46 個判定因此蒸發，而且看起來只是「這批沒評完」。
    只在**這一批的範圍內**做尾綴比對，跨卷同名（exam1_q1 同時存在於初級與中級）
    才不會亂配；配到兩個以上就不配。
    """
    out: dict[str, Any] = {}
    for raw_id, value in returned.items():
        if raw_id in expected:
            out[raw_id] = value
            continue
        candidates = [k for k in expected if k.split(':', 1)[-1] == raw_id]
        if len(candidates) == 1:
            out[candidates[0]] = value
    return out


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


def verify_all(args, questions: dict[str, dict], ids: dict[str, str], by_id: dict[str, str],
               valid: dict[str, str], stable_ids: dict[str, Any]) -> None:
    """全量驗收：逐個標籤評 正確／過廣／錯誤，**濾掉錯誤**、保留過廣但標記。

    抽驗 60 題量到「正確 61%、過廣 26%、錯誤 13%」——13% 標錯會直接污染概念
    熱度統計，不能就這樣上。根因是別名品質（08 §6 早就寫過 alias 是自由文字、
    品質不受控），這裡用驗收把它擋在資料進入統計之前。
    """
    if args.limit:
        # items 是標註檔的全部題目，最後也會把全部題目的 verdict 重寫；只驗一部分會把其他題洗成「未評」。
        raise SystemExit('FAIL --verify-all 不支援 --limit：驗收是全量的，只跑一部分會把其他題的判定洗成「未評」。'
                         '要試跑請用 --out 指到 repo 外的複本。')
    # 先依 id 把名稱更新到詞彙表目前的正式名稱，名稱對不到詞彙表就在花 API 錢之前 FAIL，
    # 不然 align_cached()／persist() 會以裸 KeyError 收場。
    data = attach_topic_ids(load_json(OUT_PATH), ids, by_id, stable_ids)
    keys = sorted(data['assignments'])
    missing_questions = [k for k in keys if k not in questions]
    if missing_questions:
        raise SystemExit(f'FAIL 標註檔有 {len(missing_questions)} 題不在目前的題目集合裡（例如 {missing_questions[0]}），'
                         '--source 是否選對？')
    items = [(k, str(questions[k].get('reference_answer') or '')[:260],
              data['assignments'][k]['topics']) for k in keys]
    print(f'全量驗收 {len(items)} 題')

    load_env_file()
    model = (args.verify_model or args.models.split(',')[0]).strip()
    if model in [m.strip() for m in args.models.split(',')]:
        print(f'⚠ 驗收模型 {model} 也是出標籤的模型之一——自己驗自己，'
              f'數字會偏樂觀。用 --verify-model 指定一個沒參與指派的模型。')
    # 驗收結果落快取，重跑只補沒評到的。93 批裡 8 批被 gateway 抽風打掉，
    # 整份丟掉重跑等於把 85 批的結果也扔了；嚴格（不完整就不寫出）與可續跑
    # 是兩回事，兩個都要。
    def align(topics: list[str], judged: dict[str, str]) -> dict[str, str]:
        """把模型回的概念名對回詞彙表的正式寫法。

        ⚠ 模型會回「生成式 AI」而詞彙表寫「生成式AI」——差一個空白。用字串相等
        比對，122 題會永遠對不上、永遠重試，而且會被誤讀成「模型沒評」
        （2026-08-10 就是這樣卡住的）。normalise 是指派那段用的同一套正規化。
        """
        by_norm = {normalise(t): t for t in topics}
        aligned = {}
        for name, verdict in judged.items():
            canonical = by_norm.get(normalise(name))
            if canonical:
                aligned[canonical] = verdict
        return aligned

    # 快取整份讀進來、本輪沒跑到的題原樣寫回去。舊版每寫一批就把快取整份重寫成「只含本輪題目、
    # 且對齊成本輪標籤」的版本：只要標註檔的題目集合比快取小（例如用 --out 做的小複本、
    # 或標註檔被裁過）又至少跑到一批，快取裡其他題的判定就全部消失。
    # 本輪題目上已不在該題的舊紀錄仍會被濾掉（那個標籤已不屬於這題），這與舊版意圖相同。
    cache = load_cache(VERIFY_CACHE, 'verify', ids, by_id, valid)
    verdicts: dict[str, dict[str, str]] = {qid: align_cached(topics, cache.get(qid, []), ids)
                                           for qid, _, topics in items}
    todo = [item for item in items
            if any(t not in verdicts.get(item[0], {}) for t in item[2])]
    if cache:
        print(f'  快取已有 {len(cache)} 題，本輪只需評 {len(todo)} 題')

    def persist() -> None:
        for qid, judged in verdicts.items():
            cache[qid] = [_cache_record('verify', name, ids[name], verdict)
                          for name, verdict in judged.items()]
        save_cache(VERIFY_CACHE, 'verify', cache, stable_ids)
    items_to_run, items = todo, items
    incomplete = []
    # ⚠ 驗收批要比指派批小。第一版沿用 BATCH_SIZE=12（一批最多 36 個標籤要評），
    # 模型「有回應」但只評了一部分，326 個標籤（29%）變成「未評」卻照樣寫檔——
    # 批次回了一半就當成功，正是這條線一再踩的坑。現在**逐批檢查每一題都有評到**。
    batch_size = max(1, VERIFY_BATCH_SIZE)

    def unjudged(batch, got):
        """哪些題還沒被評完。

        ⚠ 只檢查「這題有沒有回應」不夠：模型會回一題卻只評它三個標籤裡的一個，
        剩下的靜靜變成「未評」（2026-08-10 實測 880 個標籤裡 149 個，17%）。
        判準必須是**每一個標籤都有評價**。
        """
        return sorted(qid for qid, _, topics in batch
                      if any(t not in got.get(qid, {}) for t in topics))

    for start in range(0, len(items_to_run), batch_size):
        batch = items_to_run[start:start + batch_size]
        want = {qid for qid, _, _ in batch}
        # 從快取裡已有的部分判定起算，模型這次少回一個標籤不會把上次評到的洗掉
        got: dict[str, dict[str, str]] = {qid: dict(verdicts.get(qid, {})) for qid, _, _ in batch}
        for _ in range(args.retries + 1):
            raw = call_gateway(build_verify_prompt(batch), model,
                               args.timeout, None, args.max_tokens)
            fresh = resolve_ids(parse_reviews(raw), want)
            topics_of = {qid: topics for qid, _, topics in batch}
            for qid, verdicts_for_q in fresh.items():   # 累積多次嘗試的結果
                got.setdefault(qid, {}).update(align(topics_of.get(qid, []), verdicts_for_q))
            if not unjudged(batch, got):
                break
        missing = unjudged(batch, got)
        if missing:
            incomplete.append((start // batch_size + 1, missing))
        verdicts.update(got)
        persist()
    if incomplete:
        detail = '、'.join(f'批{n}缺{len(m)}題' for n, m in incomplete[:6])
        raise SystemExit(f'FAIL {len(incomplete)} 批沒有評完（{detail}），不產出部分驗收結果。'
                         f'已評的結果留在 {VERIFY_CACHE}，'
                         f'直接重跑同一個指令會只補沒評到的那些')

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
    write_json_atomic(OUT_PATH, attach_topic_ids(data, ids, by_id, stable_ids))
    print('標籤 ' + str(total) + '：' + '、'.join(f'{k} {v}（{v / total:.0%}）'
                                                for k, v in tally.most_common()))
    print(f'濾掉錯誤 {tally["錯誤"]} 個 → 剩 {total - tally["錯誤"]} 個；'
          f'因此變成沒有標籤的題目 {len(empty)} 題')
    try:
        print(f'→ {OUT_PATH.relative_to(BASE)}')
    except ValueError:
        print(f'→ {OUT_PATH}')  # --out 可以指到 repo 外（試跑）


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
        got = resolve_ids(parse_reviews(raw), {qid for qid, _, _ in batch})
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


def load_practice_questions() -> dict[str, dict]:
    """章節練習與學習指引練習（590 題）。

    這些題沒有 `reference_answer`（那是官方考卷專屬的 codex 詳解），改用
    題幹＋正解選項＋解析＋圖卡概念組出等價的判讀依據，並塞回 `reference_answer`
    欄位，這樣指派與驗收兩段程式碼都不必分岔。
    """
    questions: dict[str, dict] = {}
    for level in ('初級', '中級'):
        pattern = BASE / 'data' / level / 'questions'
        for path in sorted(pattern.glob('subject*_questions.json')) + \
                sorted(pattern.glob('subject*_guide_exercises.json')):
            data = load_json(path)
            items = data.get('questions') or [q for c in data.get('chapters', [])
                                              for q in c.get('questions', [])]
            for q in items:
                qid = q.get('id')
                if not qid:
                    continue
                answer = (q.get('options') or {}).get(q.get('answer'), '')
                concept = (q.get('card') or {}).get('concept', '')
                summary = f"題目：{q.get('question', '')}\n正解：{answer}\n" \
                          f"解析：{q.get('explanation', '')}"
                if concept:
                    summary += f"\n重點概念：{concept}"
                questions[f'{level}-{path.stem}:{qid}'] = {'reference_answer': summary}
    return questions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--models', default='glm-5.2',
                        help='逗號分隔；給 3 個就做 2/3 共識驗收')
    parser.add_argument('--timeout', type=int, default=300)
    parser.add_argument('--max-tokens', type=int, default=4000)
    parser.add_argument('--retries', type=int, default=2)
    parser.add_argument('--model-all', action='store_true',
                        help='全部題目都走模型（不用別名比對）。量測顯示模型讀詳解的'
                             '正確率 73%%，別名比對只有 60%%——key_concepts 本身混了對照組概念')
    parser.add_argument('--dry-run', action='store_true', help='只做別名比對，不呼叫模型')
    parser.add_argument('--verify-all', action='store_true',
                        help='全量驗收既有指派，濾掉「錯誤」的標籤')
    parser.add_argument('--batch-size', type=int, default=BATCH_SIZE,
                        help=f'每次呼叫塞幾題（預設 {BATCH_SIZE}）。網關不穩時調小')
    parser.add_argument('--source', choices=['exam', 'practice'], default='exam',
                        help='exam＝官方考卷（讀 examReferenceAnswers，預設）；'
                             'practice＝章節練習＋指引練習 590 題，另存一份輸出')
    parser.add_argument('--verify-model', default='',
                        help='驗收用的模型。留空會用 --models 的第一個，那等於讓出標籤的'
                             '模型驗自己（2026-08-09 的舊資料就是這樣跑的），**不要沿用**')
    parser.add_argument('--limit', type=int, default=0,
                        help='只跑 N 題（跨考卷等距抽樣，可重現）。試跑用，務必搭配 --out')
    parser.add_argument('--out', default='',
                        help='輸出路徑；預設寫 data/topics/question_topics.json。'
                             '試跑一定要指定別的路徑，否則會蓋掉正式資料')
    parser.add_argument('--verify-sample', type=int, default=0,
                        help='抽驗既有指派的精確度（給樣本數），不重跑指派')
    parser.add_argument('--backfill-ids', action='store_true',
                        help='不呼叫模型：把既有標註檔與快取補上詞彙表的穩定 id（純新增、冪等）。'
                             '搭配 --source 決定官方卷或練習題那份')
    args = parser.parse_args()

    global OUT_PATH, VERIFY_CACHE, ASSIGN_CACHE
    if args.source == 'practice':
        OUT_PATH = PRACTICE_OUT_PATH
        VERIFY_CACHE = VERIFY_CACHE.with_name('_verify_cache_practice.json')
        ASSIGN_CACHE = ASSIGN_CACHE.with_name('_assign_cache_practice.json')
    if args.out:
        requested_output = Path(args.out)
        OUT_PATH = requested_output if requested_output.is_absolute() else BASE / requested_output

    vocab = load_json(VOCAB_PATH)
    if vocab.get('status') != 'signed-off':
        raise SystemExit(f'FAIL {VOCAB_PATH.name} 不是 signed-off 狀態，不拿來標題目')
    topics = vocab['topics']
    names = [t['name'] for t in topics]
    valid = {normalise(n): n for n in names}
    lookup = build_lookup(topics)
    ids = topic_ids(vocab)
    by_id = {identity: name for name, identity in ids.items()}
    stable_ids = stable_ids_of(vocab)

    if args.backfill_ids:
        backfill_ids(ids, by_id, valid, stable_ids)
        return

    if args.source == 'practice':
        questions = load_practice_questions()
    else:
        questions = {}
        for path in sorted(REFERENCE_DIR.glob('*.json')):
            if path.stem == 'stats':
                continue
            for qid, entry in load_json(path).items():
                questions[f'{path.stem}:{qid}'] = entry

    if args.limit and args.limit < len(questions):
        # 等距抽樣而不是取前 N 題：sorted 的前 N 題全都落在同一份考卷上，
        # 那量到的是那份卷的難易度，不是標註品質
        keys = sorted(questions)
        stride = len(keys) / args.limit
        picked = [keys[int(i * stride)] for i in range(args.limit)]
        questions = {k: questions[k] for k in picked}
        print(f'--limit {args.limit}：跨 {len({k.split(":")[0] for k in picked})} 份考卷等距抽樣')

    if args.verify_all:
        verify_all(args, questions, ids, by_id, valid, stable_ids)
        return
    if args.verify_sample:
        verify_sample(args, questions)
        return

    assigned: dict[str, dict] = {}
    pending: list[tuple[str, str, list[str]]] = []
    for key, entry in questions.items():
        phrases = [str(p) for p in (entry.get('key_concepts') or [])]
        hits = [] if args.model_all else deterministic(phrases, lookup)
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
    cache = load_cache(ASSIGN_CACHE, 'assign', ids, by_id, valid)
    if cache:
        print(f'  指派快取已有 {len(cache)} 筆（模型|題號），本輪只補沒跑到的')

    for model in models:
        failed = []
        batch_size = max(1, args.batch_size)
        for start in range(0, len(pending), batch_size):
            batch = [item for item in pending[start:start + batch_size]
                     if f'{model}|{item[0]}' not in cache]
            if not batch:
                continue
            raw = None
            for attempt in range(1, args.retries + 2):
                raw = call_gateway(build_prompt(names, batch), model,
                                   args.timeout, None, args.max_tokens)
                if parse_assignments(raw):
                    break
                reason = '空回應' if not raw else f'回應無法解析（{len(raw)} 字，可能被截斷）'
                print(f'  {model} 批 {start // batch_size + 1} 第 {attempt} 次{reason}，重試中',
                      flush=True)
                time.sleep(5 * attempt)   # 空回應多半是網關限流，立刻重打只會再被打回
            result = resolve_ids(parse_assignments(raw), {qid for qid, _, _ in batch})
            if not result:
                failed.append(start // batch_size + 1)
                continue
            for qid, picked in result.items():
                cache[f'{model}|{qid}'] = [_cache_record('assign', name, resolve_topic_id(name, ids, valid))
                                           for name in picked[:MAX_TOPICS]]
            save_cache(ASSIGN_CACHE, 'assign', cache, stable_ids)
        for qid, _, _ in pending:
            for record in cache.get(f'{model}|{qid}', []):
                # id 優先（改名後仍對得回來），沒有 id 的舊紀錄才用 normalise 比對
                canonical = by_id.get(record.get('topicId')) or valid.get(normalise(record['topic']))
                if canonical:
                    votes[qid][canonical] += 1
                else:
                    rejected.append({'question': qid, 'model': model, 'topic': record['topic'],
                                     'note': '不在詞彙表裡（自創或改寫）'})
        if failed:
            raise SystemExit(f'FAIL {model} 有 {len(failed)} 批沒有結果（批 '
                             f'{"、".join(map(str, failed))}），不產出部分結果。'
                             f'成功的批已存進 {ASSIGN_CACHE.name}，重跑同一個指令只會補這幾批')
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
    write_json_atomic(OUT_PATH, attach_topic_ids(payload, ids, by_id, stable_ids))
    print(f'\n別名 {payload["byAlias"]}｜模型 {filled}（需 {need}/{len(models)} 票）｜'
          f'仍未標 {len(payload["unassigned"])}｜覆蓋率 {coverage:.1%}')
    if rejected:
        print(f'⚠ 擋下 {len(rejected)} 個不在詞彙表裡的標籤（模型自創），已記在 rejectedTopics')
    quality = payload['aliasQuality']
    print(f'別名品質：{quality["lookupEntries"]} 條查找鍵，'
          f'指向多個概念 {quality["ambiguousEntries"]}、'
          f'「正式名稱同時是別名」{quality["canonicalNameUsedAsAlias"]} 組'
          f'（別名是模型自由文字，這是這步的精確度上限）')
    try:
        print(f'→ {OUT_PATH.relative_to(BASE)}')
    except ValueError:
        print(f'→ {OUT_PATH}')  # --out 可以指到 repo 外（試跑）


if __name__ == '__main__':
    main()
