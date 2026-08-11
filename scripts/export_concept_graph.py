#!/usr/bin/env python3
"""概念關聯圖：一個概念是什麼、考過哪些題、和哪些概念一起出現、講義在哪一章。

輸入全是既有 committed 產物，無 API 花費、可隨時重跑、輸出確定性：
    data/topics/topics.json                       受控詞彙表（名稱與上位分類）
    data/topics/question_topics.json               官方考卷標註（已驗收）
    data/topics/practice_question_topics.json      章節練習＋指引練習標註（已驗收）
    frontend/src/generated/topicHeat.json          概念 → 講義章節
    frontend/src/generated/{primary,middle}Glossary.json  名詞解釋
    data/{level}/questions/*.json                  題幹文字與練習頁路由
輸出：
    frontend/src/generated/conceptGraph.json

**採計規則與 topicHeat 一致：只算 `verdict` 是「正確」的標籤。**「過廣」不算錯，
但把上位詞算進來會讓每個概念都連到所有東西，圖會糊掉。

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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
GENERATED = BASE / 'frontend' / 'src' / 'generated'
TOPICS_PATH = BASE / 'data' / 'topics' / 'topics.json'
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
    'sample': ('初級', 'sample_exam.json'),
    'midSample': ('中級', 'sample_exam.json'),
}
QUESTION_NUMBER = re.compile(r'_q(\d+)$')
# 章節 id 藏在題號裡：mid-s1c4gq001 → 章節 mid-s1c4、科目 mid-s1
CHAPTER_IN_ID = re.compile(r'^(((?:mid-)?s\d+)c\d+)')
MAX_QUESTIONS_PER_CONCEPT = 40


def load(path: Path) -> Any:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def correct_labels(path: Path) -> dict[str, list[str]]:
    """題目 → 被判「正確」的概念。非 verified 的檔案直接拒絕，不猜。"""
    data = load(path)
    if data.get('status') != 'verified':
        raise SystemExit(f'FAIL {path.name} 不是 verified 狀態，不拿來建圖')
    out = {}
    for key, entry in data['assignments'].items():
        names = sorted({e['topic'] for e in entry.get('evidence', [])
                        if e.get('verdict') == '正確'})
        if names:
            out[key] = names
    return out


def paper_file(paper: str) -> tuple[str, str] | None:
    if paper in PAPER_FILES:
        return PAPER_FILES[paper]
    level = '中級' if paper.startswith('mid') else '初級'
    return (level, f'mock_{paper}.json')


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
                'level': level,
                'source': '官方考卷',
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

    topics = {t['name']: t for t in load(TOPICS_PATH)['topics']}
    official = correct_labels(OFFICIAL_PATH)
    practice = correct_labels(PRACTICE_PATH)
    heat = {t['name']: t for t in load(HEAT_PATH)['topics']}
    glossary = glossary_entries()
    official_index = build_official_index()
    practice_index = build_practice_index()

    refs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    counts: dict[str, Counter] = defaultdict(Counter)
    missing = Counter()
    for key, names in official.items():
        paper, _, qid = key.partition(':')
        number = QUESTION_NUMBER.search(qid)
        info = official_index.get(f'{paper}|{number.group(1)}') if number else None
        for name in names:
            counts[name]['official'] += 1
            if info:
                refs[name].append({'id': qid, **info})
            else:
                missing['official'] += 1
    for key, names in practice.items():
        _, _, qid = key.partition(':')
        info = practice_index.get(qid)
        for name in names:
            counts[name]['practice'] += 1
            if info:
                refs[name].append({'id': qid, **info})
            else:
                missing['practice'] += 1

    # 共現邊：兩個概念被標在同一題上幾次
    edges: Counter = Counter()
    for names in itertools.chain(official.values(), practice.values()):
        for a, b in itertools.combinations(sorted(names), 2):
            edges[(a, b)] += 1
    related: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (a, b), weight in edges.items():
        related[a].append({'name': b, 'weight': weight})
        related[b].append({'name': a, 'weight': weight})

    concepts = []
    for name in sorted(counts, key=lambda n: (-counts[n]['official'] - counts[n]['practice'], n)):
        total = counts[name]['official'] + counts[name]['practice']
        if total < args.min_questions:
            continue
        chapters = [c for c in heat.get(name, {}).get('chapters', [])
                    if c.get('kind') == 'guide']
        concepts.append({
            'name': name,
            'parent': topics.get(name, {}).get('parent', ''),
            'questionCount': {'official': counts[name]['official'],
                              'practice': counts[name]['practice']},
            'glossary': glossary.get(name, []),
            'chapters': chapters,
            'related': sorted(related.get(name, []),
                              key=lambda r: (-r['weight'], r['name']))[:12],
            'questions': sorted(refs.get(name, []),
                                key=lambda q: (q['source'], q['id']))[:MAX_QUESTIONS_PER_CONCEPT],
        })

    payload = {
        'generatedAt': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'source': {
            'official': str(OFFICIAL_PATH.relative_to(BASE)),
            'practice': str(PRACTICE_PATH.relative_to(BASE)),
            'vocabulary': str(TOPICS_PATH.relative_to(BASE)),
        },
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
    print(f'→ {OUT_PATH.relative_to(BASE)}（{OUT_PATH.stat().st_size / 1024:.0f} KB）')


if __name__ == '__main__':
    main()
