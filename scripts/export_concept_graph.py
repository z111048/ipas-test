#!/usr/bin/env python3
"""概念關聯圖：一個概念是什麼、考過哪些題、和哪些概念一起出現、講義在哪一章。

輸入全是既有 committed 產物，無 API 花費、可隨時重跑、輸出確定性（不寫時間戳）：
    data/topics/topics.json                       受控詞彙表（穩定 id、名稱與上位分類）
    data/topics/topic_id_assignments.json          id 指派帳本（只取 previousNames 供舊連結解析）
    data/topics/question_topics.json               官方考卷標註（已驗收）
    data/topics/practice_question_topics.json      章節練習＋指引練習標註（已驗收）
    frontend/src/generated/topicHeat.json          概念 → 講義章節
    frontend/src/generated/{primary,middle}Glossary.json  名詞解釋
    data/{level}/questions/*.json                  題幹文字與練習頁路由
輸出：
    frontend/src/generated/conceptGraph.json

**採計規則與 topicHeat 一致：只算 `verdict` 是「正確」的標籤。**「過廣」不算錯，
但把上位詞算進來會讓每個概念都連到所有東西，圖會糊掉。

**穩定 id（LP-210C）**：概念以詞彙表的 `id` 為鍵（共現邊以 id 配對），`name` 只作顯示；
每個概念另帶帳本的 `previousNames`，前端 `/concepts?c=` 舊的中文名稱連結靠它解析到同一概念。
標註檔的 `topicId` 與名稱必須和詞彙表一致，否則拒絕建圖（改名後先跑
`assign_question_topics.py --backfill-ids`）。

⚠️ `questionCount` 分成 `official` 與 `practice` 兩個數字，**不要相加當熱度用**。
topicHeat 的熱度定義是「被官方考卷考幾題」，出題配額與名詞解釋選詞都吃那個數字；
練習題是我們自己出的，混進去會讓熱度失真。這裡分開列，前端要顯示哪個自己決定。

用法：
    python3 scripts/export_concept_graph.py
    python3 scripts/export_concept_graph.py --min-questions 1   # 預設 1，收錄所有有題目的概念
"""

from __future__ import annotations

import argparse
import itertools
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from resource_catalog import exam_entries, level_entry

BASE = Path(__file__).resolve().parents[1]
GENERATED = BASE / 'frontend' / 'src' / 'generated'
TOPICS_PATH = BASE / 'data' / 'topics' / 'topics.json'
LEDGER_PATH = BASE / 'data' / 'topics' / 'topic_id_assignments.json'
OFFICIAL_PATH = BASE / 'data' / 'topics' / 'question_topics.json'
PRACTICE_PATH = BASE / 'data' / 'topics' / 'practice_question_topics.json'
HEAT_PATH = GENERATED / 'topicHeat.json'
OUT_PATH = GENERATED / 'conceptGraph.json'
GLOSSARY_FILES = {'初級': GENERATED / 'primaryGlossary.json',
                  '中級': GENERATED / 'middleGlossary.json'}

# 考卷 key（examReferenceAnswers 的檔名，同時也是前端 /exam/:examKey 的路由 key）
# → 題庫檔。114 年第二梯次那三份在標註裡沿用舊題號（exam1_q7），與題庫檔的
# mid_1141_s1_q7 對不上，所以下面一律用「卷別 ＋ 題號數字」配對，不比字串。
PAPER_FILES = {
    exam['routeKey']: (
        level_entry(level_id=exam['levelId'])['dataLevel'],
        exam['questionFile'],
    )
    for exam in exam_entries()
}
QUESTION_NUMBER = re.compile(r'_q(\d+)$')
# 章節 id 藏在題號裡：mid-s1c4gq001 → 章節 mid-s1c4、科目 mid-s1
CHAPTER_IN_ID = re.compile(r'^(((?:mid-)?s\d+)c\d+)')
MAX_QUESTIONS_PER_CONCEPT = 40


def load(path: Path) -> Any:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def correct_labels(path: Path, name_of: dict[str, str]) -> dict[str, list[str]]:
    """題目 → 被判「正確」的概念 **id**。非 verified 的檔案直接拒絕，不猜。

    標籤的 `topicId`／`topic` 要和詞彙表一致：缺 id 是還沒回填，名稱對不上是概念改名後
    標註檔還沒更新——兩種都 FAIL，不要用名稱猜。
    """
    data = load(path)
    if data.get('status') != 'verified':
        raise SystemExit(f'FAIL {path.name} 不是 verified 狀態，不拿來建圖')
    out = {}
    for key, entry in data['assignments'].items():
        identities = set()
        for evidence in entry.get('evidence', []):
            identity = evidence.get('topicId')
            if identity is None:
                raise SystemExit(f'FAIL {path.name} 的 {key} 沒有 topicId，'
                                 '先跑 assign_question_topics.py --backfill-ids')
            if name_of.get(identity) != evidence['topic']:
                raise SystemExit(f'FAIL {path.name} 的 {key}：「{evidence["topic"]}」（{identity}）'
                                 '與詞彙表不一致，先跑 assign_question_topics.py --backfill-ids')
            if evidence.get('verdict') == '正確':
                identities.add(identity)
        if identities:
            out[key] = sorted(identities)
    return out


def previous_names(topics: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    """id → 帳本裡的舊正式名稱。帳本是 topics.json 的策展輸入，和詞彙表對不上就 FAIL。"""
    if not LEDGER_PATH.exists():
        raise SystemExit(f'FAIL 找不到 id 指派帳本 {LEDGER_PATH.name}，舊名稱連結無從解析')
    out: dict[str, list[str]] = {}
    for entry in load(LEDGER_PATH).get('assignments', []):
        topic = topics.get(entry.get('id'))
        if topic is None:
            continue   # 已 retired 或尚未折進詞彙表的指派，不屬於這張圖
        if entry.get('canonicalName') != topic['name']:
            raise SystemExit(f'FAIL 帳本說 {entry["id"]} 是「{entry.get("canonicalName")}」，'
                             f'詞彙表卻是「{topic["name"]}」；先重建詞彙表再建圖')
        out[topic['id']] = list(entry.get('previousNames') or [])
    return out


def paper_file(paper: str) -> tuple[str, str] | None:
    return PAPER_FILES.get(paper)


def build_official_index() -> dict[str, dict[str, Any]]:
    """`卷別:題號` → 題幹與路由。配對靠題號數字，不靠 id 字串（見 PAPER_FILES）。"""
    index: dict[str, dict[str, Any]] = {}
    for paper in {p.stem for p in (GENERATED / 'examReferenceAnswers').glob('*.json')}:
        target = paper_file(paper)
        if not target:
            continue
        level, filename = target
        path = BASE / 'data' / level / 'questions' / filename
        if not path.exists():
            continue
        data = load(path)
        items = data.get('questions') or [q for c in data.get('chapters', [])
                                          for q in c.get('questions', [])]
        by_number = {}
        for question in items:
            match = QUESTION_NUMBER.search(str(question.get('id', '')))
            if match:
                by_number[match.group(1)] = question
        for qid_number, question in by_number.items():
            # 路由帶的是題庫裡的正式 id，不是標註檔的題號——114 年那三份標註沿用
            # 舊寫法（exam1_q7），前端拿它找不到題目
            canonical = str(question.get('id', ''))
            index[f'{paper}|{qid_number}'] = {
                # id 也要是題庫的正式 id：refs 是 {'id': 標註題號, **info}，
                # info 覆蓋在後，所以這一行就是彈窗查得到題目的關鍵
                'id': canonical,
                'level': level,
                'source': '官方考卷',
                # kind／examKey 讓前端的題目彈窗知道要動態載哪一份題庫，
                # 不必把 1,561 題的選項與解析全部塞進 conceptGraph.json
                'kind': 'exam',
                'examKey': paper,
                'route': f'/exam/{paper}?q={canonical}',
                'stem': str(question.get('question', ''))[:70],
            }
    return index


def build_practice_index() -> dict[str, dict[str, Any]]:
    """練習題 id → 題幹與練習頁路由（章節練習 / 學習指引練習兩種）。"""
    index: dict[str, dict[str, Any]] = {}
    for level in ('初級', '中級'):
        directory = BASE / 'data' / level / 'questions'
        for path in sorted(directory.glob('subject*_questions.json')) + \
                sorted(directory.glob('subject*_guide_exercises.json')):
            guide_set = path.stem.endswith('guide_exercises')
            data = load(path)
            items = data.get('questions') or [q for c in data.get('chapters', [])
                                              for q in c.get('questions', [])]
            for question in items:
                qid = question.get('id')
                if not qid:
                    continue
                # 章節練習有 chapter_id 欄位，學習指引練習沒有——它的章節編在 id 裡
                # （mid-s1c4gq001 / s1c1gq001），少了這個 fallback 會有 205 筆引用
                # 連不到練習頁
                chapter = question.get('chapter_id') or ''
                if not chapter:
                    match = CHAPTER_IN_ID.match(str(qid))
                    chapter = match.group(1) if match else ''
                subject_match = CHAPTER_IN_ID.match(chapter)
                if not chapter or not subject_match:
                    continue
                subject = subject_match.group(2)
                route = (f'/practice/{subject}/{chapter}'
                         + ('/guide' if guide_set else '') + f'?q={qid}')
                index[qid] = {
                    'level': level,
                    'source': '學習指引練習' if guide_set else '章節練習',
                    'kind': 'practice',
                    'subjectId': subject,
                    'chapterId': chapter,
                    'practiceSet': 'guide' if guide_set else '',
                    'route': route,
                    'stem': str(question.get('question', ''))[:70],
                }
    return index


def glossary_entries() -> dict[str, list[dict[str, str]]]:
    entries: dict[str, list[dict[str, str]]] = defaultdict(list)
    for level, path in GLOSSARY_FILES.items():
        if not path.exists():
            continue
        for subject_id, subject in load(path)['subjects'].items():
            for term in subject['terms']:
                entries[term['zh']].append({
                    'level': level, 'subject': subject_id,
                    'subjectName': subject['subject'],
                    'en': term.get('en', ''), 'definition': term['definition'],
                    'example': term.get('example', ''),
                })
    return entries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--min-questions', type=int, default=1,
                        help='至少幾題才收錄這個概念（預設 1）')
    args = parser.parse_args()

    vocabulary = load(TOPICS_PATH)
    without_id = [t['name'] for t in vocabulary['topics'] if not t.get('id')]
    if without_id:
        raise SystemExit(f'FAIL 詞彙表有 {len(without_id)} 個概念沒有穩定 id（例如「{without_id[0]}」），'
                         '先完成 LP-210B（build_topic_vocabulary.py --apply-pairs）')
    topics = {t['id']: t for t in vocabulary['topics']}
    if len(topics) != len(vocabulary['topics']):
        raise SystemExit('FAIL 詞彙表的穩定 id 有重複')
    name_of = {identity: topic['name'] for identity, topic in topics.items()}
    former = previous_names(topics)
    official = correct_labels(OFFICIAL_PATH, name_of)
    practice = correct_labels(PRACTICE_PATH, name_of)
    heat = {}
    for row in load(HEAT_PATH)['topics']:
        if 'id' not in row:
            raise SystemExit('FAIL topicHeat.json 沒有 id，先重跑 export_topic_heat.py')
        heat[row['id']] = row
    glossary = glossary_entries()
    official_index = build_official_index()
    practice_index = build_practice_index()

    refs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    counts: dict[str, Counter] = defaultdict(Counter)
    missing = Counter()
    # 以下一律以 id 為鍵；名稱只在輸出時查表。
    for key, identities in official.items():
        paper, _, qid = key.partition(':')
        number = QUESTION_NUMBER.search(qid)
        info = official_index.get(f'{paper}|{number.group(1)}') if number else None
        for identity in identities:
            counts[identity]['official'] += 1
            if info:
                refs[identity].append({'id': qid, **info})
            else:
                missing['official'] += 1
    for key, identities in practice.items():
        _, _, qid = key.partition(':')
        info = practice_index.get(qid)
        for identity in identities:
            counts[identity]['practice'] += 1
            if info:
                refs[identity].append({'id': qid, **info})
            else:
                missing['practice'] += 1

    # 共現邊：兩個概念被標在同一題上幾次（以 id 配對，改名不影響邊）
    edges: Counter = Counter()
    for identities in itertools.chain(official.values(), practice.values()):
        for a, b in itertools.combinations(sorted(identities), 2):
            edges[(a, b)] += 1
    related: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (a, b), weight in edges.items():
        related[a].append({'id': b, 'name': name_of[b], 'weight': weight})
        related[b].append({'id': a, 'name': name_of[a], 'weight': weight})

    concepts = []
    for identity in sorted(counts, key=lambda i: (-counts[i]['official'] - counts[i]['practice'],
                                                  name_of[i])):
        total = counts[identity]['official'] + counts[identity]['practice']
        if total < args.min_questions:
            continue
        name = name_of[identity]
        chapters = [c for c in heat.get(identity, {}).get('chapters', [])
                    if c.get('kind') == 'guide']
        concepts.append({
            'id': identity,
            'name': name,
            # 帳本裡的舊正式名稱：前端拿 ?c=<舊名> 來時靠這個對到同一概念
            'previousNames': former.get(identity, []),
            'parent': topics[identity].get('parent', ''),
            'questionCount': {'official': counts[identity]['official'],
                              'practice': counts[identity]['practice']},
            'glossary': glossary.get(name, []),
            'chapters': chapters,
            'related': sorted(related.get(identity, []),
                              key=lambda r: (-r['weight'], r['name']))[:12],
            'questions': sorted(refs.get(identity, []),
                                key=lambda q: (q['source'], q['id']))[:MAX_QUESTIONS_PER_CONCEPT],
        })

    # 不寫時間戳：這是 committed 產物，重跑要位元相同才看得出真正的差異（08 §7-3 的教訓）。
    payload = {
        'source': {
            'official': str(OFFICIAL_PATH.relative_to(BASE)),
            'practice': str(PRACTICE_PATH.relative_to(BASE)),
            'vocabulary': str(TOPICS_PATH.relative_to(BASE)),
            'ledger': str(LEDGER_PATH.relative_to(BASE)),
        },
        'stableIds': vocabulary.get('stableIds'),
        'countingRule': '只算 verdict=正確 的標籤；official 與 practice 分開計，不可相加當熱度',
        'conceptCount': len(concepts),
        'questionCount': {'official': len(official), 'practice': len(practice)},
        'edgeCount': len(edges),
        'strongEdgeCount': sum(1 for w in edges.values() if w >= 2),
        'concepts': concepts,
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'概念 {len(concepts)}｜共現邊 {len(edges)}（權重≥2 共 {payload["strongEdgeCount"]}）'
          f'｜題目 官方 {len(official)} ＋ 練習 {len(practice)}')
    if missing:
        print(f'⚠ 對不到題庫因此沒有題幹的引用：{dict(missing)}')
    with_glossary = sum(1 for c in concepts if c['glossary'])
    print(f'有名詞解釋的概念 {with_glossary}/{len(concepts)}｜'
          f'有講義章節的 {sum(1 for c in concepts if c["chapters"])}/{len(concepts)}')
    try:
        print(f'→ {OUT_PATH.relative_to(BASE)}（{OUT_PATH.stat().st_size / 1024:.0f} KB）')
    except ValueError:
        print(f'→ {OUT_PATH}（{OUT_PATH.stat().st_size / 1024:.0f} KB）')  # 測試會把輸出指到 repo 外


if __name__ == '__main__':
    main()
