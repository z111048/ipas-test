#!/usr/bin/env python3
"""概念熱度：哪個觀念常考、它散落在哪幾章（§7-3）。

輸入都是既有 committed 產物，無 API 花費、可隨時重跑：
    data/topics/question_topics.json          概念標註（已驗收，verdict 逐筆）
    data/topics/topics.json                   受控詞彙表（181 概念 / 8 大類）
    frontend/src/generated/guideExamAnnotations/  官方題 → 講義章節
輸出：
    frontend/src/generated/topicHeat.json

**採計規則：只算 `verdict` 是「正確」的標籤。**
驗收把標籤分成 正確 75%／過廣 22%／錯誤 3%。錯誤已在標註階段濾除；「過廣」
不算錯，但把它算進熱度會讓上位概念虛胖——實測寬鬆採計會把「機率與統計」
推到第 80 名、「機器學習概論」推到第 56 名，這些都是空泛的上位詞。
嚴格採計自動把它們降到 160 名外，代價只是 10 個邊緣概念消失（各 1–5 個標籤）。
兩種數字都輸出（`count` / `countLoose`），前端要改採計規則不必重跑。

⚠️ 與章節熱度同一條規則：**各章題數不可相加**。一題常引用多章，逐章加總會
超過實際題數；`chapters` 是分布，不是可加總的份額。

⚠️ 同一份內容有兩套章節層級：官方大綱章（`*pdf-c{n}`）與學習指引章（其餘），
標註兩邊各記一次，所以「散落章數」若照 `chapterCount` 直接用會虛胖。實測
169 個有 strict 題目的概念裡 138 個兩套都有，平均散落章數 4.5 → 只算指引章 3.1（約 -32%），
而且**沒有任何概念只落在大綱章**（0 個），拆開不會讓概念歸零。因此另出
`guideChapterCount`／`outlineChapterCount`，前端的「散落 N 章」用指引章那個。
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
GENERATED = BASE / 'frontend' / 'src' / 'generated'
TOPICS_PATH = BASE / 'data' / 'topics' / 'topics.json'
ASSIGN_PATH = BASE / 'data' / 'topics' / 'question_topics.json'
ANNOTATION_DIR = GENERATED / 'guideExamAnnotations'
OUT_PATH = GENERATED / 'topicHeat.json'


OUTLINE_NODE = re.compile(r'pdf-c\d+$')


def load(path: Path) -> Any:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def chapter_kind(node_id: str) -> str:
    """官方大綱章 vs 學習指引章——同一份內容的兩套層級，散落章數只該算一邊。"""
    return 'outline' if OUTLINE_NODE.search(node_id) else 'guide'


def main() -> None:
    assignments = load(ASSIGN_PATH)
    if assignments.get('status') != 'verified':
        raise SystemExit('FAIL question_topics.json 不是 verified 狀態，'
                         '先跑 assign_question_topics.py --verify-all')
    vocab = {t['name']: t for t in load(TOPICS_PATH)['topics']}

    # 題目 → 概念（分嚴格與寬鬆兩套）
    strict: dict[str, list[str]] = {}
    loose: dict[str, list[str]] = {}
    for key, entry in assignments['assignments'].items():
        for evidence in entry['evidence']:
            verdict = evidence.get('verdict')
            if verdict == '錯誤':
                continue
            loose.setdefault(key, []).append(evidence['topic'])
            if verdict == '正確':
                strict.setdefault(key, []).append(evidence['topic'])

    # 題目 → 章節（來自官方詳解引文建立的標註）
    chapters: dict[str, set[str]] = defaultdict(set)
    chapter_titles: dict[str, dict[str, str]] = {}
    for path in sorted(ANNOTATION_DIR.glob('*/*.json')):
        data = load(path)
        node_id = data.get('nodeId') or path.stem
        chapter_titles[node_id] = {'guideKey': data.get('guideKey', ''), 'nodeId': node_id}
        for annotations in (data.get('blocks') or {}).values():
            for annotation in annotations:
                # ⚠ 兩份產物的題號不同名：標註用考卷自己的題號（jr_1141_s1_q8），
                # 詳解（也就是概念標註的 key）用 referenceQuestionId（exam1_q8）。
                # 只接 `id` 會有 356/558 題對不到章節，而且看起來像「標註覆蓋不足」。
                exam_key = annotation.get('examKey') or ''
                for qid in (annotation.get('referenceQuestionId'),
                            annotation.get('questionId')):
                    if exam_key and qid:
                        chapters[f'{exam_key}:{qid}'].add(node_id)
                if annotation.get('id'):
                    chapters[annotation['id']].add(node_id)

    counts = Counter()
    counts_loose = Counter()
    per_chapter: dict[str, Counter] = defaultdict(Counter)
    unmapped = 0
    for key, topics in loose.items():
        nodes = chapters.get(key)
        if not nodes:
            unmapped += 1
        for topic in topics:
            counts_loose[topic] += 1
    for key, topics in strict.items():
        for topic in topics:
            counts[topic] += 1
            # sorted()：chapters 的值是 set，直接迭代會讓同票章節的順序隨
            # PYTHONHASHSEED 變動，這份 committed 產物每次重跑都會無故 diff。
            for node_id in sorted(chapters.get(key, ())):
                per_chapter[topic][node_id] += 1

    rows = []
    for name, topic in sorted(vocab.items(), key=lambda kv: -counts[kv[0]]):
        if not counts_loose[name]:
            continue
        spread = per_chapter.get(name, Counter())
        kinds = Counter(chapter_kind(node) for node in spread)
        rows.append({
            'name': name,
            'parent': topic.get('parent', ''),
            'count': counts[name],
            'countLoose': counts_loose[name],
            'chapterCount': len(spread),
            'guideChapterCount': kinds['guide'],
            'outlineChapterCount': kinds['outline'],
            'chapters': [{'nodeId': node, 'count': n,
                          'kind': chapter_kind(node),
                          'guideKey': chapter_titles.get(node, {}).get('guideKey', '')}
                         for node, n in sorted(spread.items(),
                                               key=lambda kv: (-kv[1], kv[0]))],
        })

    payload = {
        'source': {
            'assignments': str(ASSIGN_PATH.relative_to(BASE)),
            'vocabulary': str(TOPICS_PATH.relative_to(BASE)),
            'annotations': str(ANNOTATION_DIR.relative_to(BASE)),
        },
        'countingRule': '只算 verdict=正確 的標籤；countLoose 另含「過廣」供比較',
        'warning': '各章題數不可相加——一題常引用多章，chapters 是分布不是份額',
        'verdictTally': assignments.get('verdictTally'),
        'questionCount': len(assignments['assignments']),
        'questionsWithoutChapter': unmapped,
        'topicCount': len(rows),
        'labelCount': sum(r['count'] for r in rows),
        'labelCountLoose': sum(r['countLoose'] for r in rows),
        'topics': rows,
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'概念 {len(rows)} 個｜標籤 {payload["labelCount"]}'
          f'（寬鬆 {payload["labelCountLoose"]}）｜對不到章節的題目 {unmapped}')
    print('前 8 名（題數／散落指引章數，括號為含大綱章的總數）：')
    for row in rows[:8]:
        print(f'   {row["name"]:20} {row["count"]:>3} 題 / '
              f'{row["guideChapterCount"]} 章（{row["chapterCount"]}）')
    print(f'→ {OUT_PATH.relative_to(BASE)}')


if __name__ == '__main__':
    main()
