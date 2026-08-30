#!/usr/bin/env python3
"""量測題庫與（重新 OCR 後的）學習指引之間的引文對齊狀況。

唯讀腳本：只讀資料、只輸出報告，不修改任何題庫或講義檔案。

量三件事：
1. 章節引用完整性 —— 題庫裡的 chapter_id / chapter_title 是否仍對得上 SSOT
   （toc_manifest.json）與現行 guide JSON。
2. guide_exercises 的頁碼引文 —— 每題（題幹＋選項）是否仍能在所引頁面的
   現行文字裡找到；找不到就往整份講義找，再往舊版（OCR 前備份）找，
   藉此區分「頁碼偏移」「OCR 改寫」「本來就對不上」。
3. 章節正文漂移 —— 新舊 guide JSON 的 content 相似度，用來判斷 codex100
   （精選 100 題）那類「引用章節但沒有逐字引文」的題目風險有多高；
   同時檢查練習題是否仍混在章節正文裡。

用法：
    python3 scripts/verify_question_guide_alignment.py                 # 兩級都跑
    python3 scripts/verify_question_guide_alignment.py --level 初級
    python3 scripts/verify_question_guide_alignment.py --json out.json
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
LEVELS = ('初級', '中級')

# 題幹在頁面上的比對門檻（normalized 後的最長共同子串涵蓋率）
EXACT = 0.95
PARTIAL = 0.60
# 引用頁往前後找幾頁（PDF 抽頁偶有 ±1 偏移）
PAGE_WINDOW = 1


def load_json(path: Path) -> Any:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def normalize(text: str) -> str:
    """NFKC + 去所有空白 + 統一常見標點。比對中文 PDF 文字時兩邊都要正規化。"""
    if not text:
        return ''
    text = unicodedata.normalize('NFKC', text)
    text = re.sub(r'\s+', '', text)
    text = text.translate(str.maketrans('（）［］｛｝「」『』：；，。？！、~〜－—–',
                                        '()[]{}""\'\':;,.?!,~~---'))
    return text


ANCHOR = 12          # 錨點長度（中文 12 字已足夠唯一）
MAX_ANCHORS = 24     # 一題最多取幾個錨點


def _local_coverage(needle: str, window: str) -> float:
    matcher = SequenceMatcher(None, needle, window, autojunk=False)
    match = matcher.find_longest_match(0, len(needle), 0, len(window))
    return match.size / len(needle)


def coverage(needle: str, haystack: str) -> float:
    """needle 有多少比例能在 haystack 裡找到（以最長共同子串衡量）。

    整份講義有數十萬字，直接跑 SequenceMatcher 會爆時間；先用錨點定位，
    再只在候選視窗內做精確比對。
    """
    if not needle or not haystack:
        return 0.0
    if needle in haystack:
        return 1.0
    if len(haystack) <= 4 * len(needle) + 2000:
        return _local_coverage(needle, haystack)

    step = max(ANCHOR, len(needle) // MAX_ANCHORS)
    positions: set[int] = set()
    for start in range(0, max(1, len(needle) - ANCHOR + 1), step):
        anchor = needle[start:start + ANCHOR]
        found = haystack.find(anchor)
        while found != -1 and len(positions) < 64:
            positions.add(max(0, found - start - ANCHOR))
            found = haystack.find(anchor, found + 1)
    if not positions:
        return 0.0

    span = 2 * len(needle) + 200
    best = 0.0
    for pos in sorted(positions):
        best = max(best, _local_coverage(needle, haystack[pos:pos + span]))
        if best >= 0.99:
            break
    return best


def ratio(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b, autojunk=False).ratio()


# --------------------------------------------------------------------------
# 資料載入
# --------------------------------------------------------------------------

def guide_key_for_subject(level: str, subject_index: int) -> str:
    return f'guide{subject_index}'


def load_page_texts(level: str, key: str) -> dict[int, str]:
    """現行頁面文字：優先 page_clean 的 cleaned_text，缺就退回 page_extract 的 text。"""
    pages: dict[int, str] = {}
    clean_dir = BASE / f'data/{level}/page_clean/{key}/pages'
    extract_dir = BASE / f'data/{level}/page_extract/{key}/pages'
    for directory, field in ((clean_dir, 'cleaned_text'), (extract_dir, 'text')):
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob('page_*.json')):
            index = int(path.stem.split('_')[-1])
            if index in pages and pages[index]:
                continue
            data = load_json(path)
            pages[index] = data.get(field) or ''
    return pages


def load_old_page_texts(level: str, key: str) -> dict[int, str]:
    """OCR 合併前的頁面文字備份（merge_guide_ocr.py 留下的）。"""
    pages: dict[int, str] = {}
    directory = BASE / f'data/{level}/page_extract_before_ocr_merge/{key}/pages'
    if not directory.is_dir():
        return pages
    for path in sorted(directory.glob('page_*.json')):
        pages[int(path.stem.split('_')[-1])] = load_json(path).get('text') or ''
    return pages


def load_guides(level: str, backup: bool = False) -> dict[str, dict[str, Any]]:
    """回傳 {chapter_id: chapter}，來源為 guide/subject{N}_guide.json。"""
    folder = 'guide_before_ocr_backup' if backup else 'guide'
    directory = BASE / f'data/{level}/{folder}'
    chapters: dict[str, dict[str, Any]] = {}
    for path in sorted(directory.glob('subject*_guide.json')):
        if path.name.endswith('.bak'):
            continue
        data = load_json(path)
        for chapter in data.get('chapters', []):
            chapters[chapter['id']] = chapter
    return chapters


def load_manifest_chapters(level: str) -> dict[str, dict[str, Any]]:
    data = load_json(BASE / f'data/{level}/toc_manifest.json')
    chapters: dict[str, dict[str, Any]] = {}
    for subject in data.get('subjects', []):
        for chapter in subject.get('chapters', []):
            chapters[chapter['id']] = chapter
    return chapters


def iter_questions(payload: Any) -> list[dict[str, Any]]:
    """題庫檔案有 chapters[].questions[] 與 exam.questions[] 兩種形狀。"""
    questions: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        for chapter in payload.get('chapters', []) or []:
            for question in chapter.get('questions', []) or []:
                merged = dict(question)
                merged.setdefault('chapter_id', chapter.get('id'))
                merged.setdefault('chapter_title', chapter.get('title'))
                questions.append(merged)
    return questions


def chapter_text(chapter: dict[str, Any] | None) -> str:
    if not chapter:
        return ''
    content = chapter.get('content')
    if isinstance(content, list):
        content = '\n'.join(str(item) for item in content)
    parts = [content or '']
    for sub in chapter.get('subtopics', []) or []:
        if isinstance(sub, dict):
            parts.append(str(sub.get('title') or ''))
            parts.append(str(sub.get('content') or ''))
        else:
            parts.append(str(sub))
    return '\n'.join(parts)


# --------------------------------------------------------------------------
# 檢查
# --------------------------------------------------------------------------

def check_chapter_refs(level: str, guides: dict[str, dict[str, Any]],
                       manifest: dict[str, dict[str, Any]]) -> dict[str, Any]:
    broken: list[dict[str, Any]] = []
    title_mismatch: list[dict[str, Any]] = []
    total = 0

    for path in sorted((BASE / f'data/{level}/questions').glob('*.json')):
        if path.name.startswith('mock_') or path.name in {'sample_exam.json'}:
            continue  # 歷屆／樣張題引用的是考題 PDF，不是講義
        payload = load_json(path)
        for question in iter_questions(payload):
            chapter_id = question.get('chapter_id')
            if not chapter_id:
                continue
            total += 1
            known = guides.get(chapter_id) or manifest.get(chapter_id)
            if not known:
                broken.append({'file': path.name, 'id': question.get('id'),
                               'chapter_id': chapter_id})
                continue
            cited_title = question.get('chapter_title')
            if cited_title and normalize(cited_title) != normalize(known.get('title', '')):
                title_mismatch.append({'file': path.name, 'id': question.get('id'),
                                       'chapter_id': chapter_id,
                                       'cited': cited_title,
                                       'current': known.get('title')})
    return {'checked': total, 'broken_chapter_id': broken,
            'title_mismatch': title_mismatch}


def check_guide_exercises(level: str) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for path in sorted((BASE / f'data/{level}/questions').glob('subject*_guide_exercises.json')):
        subject_index = int(re.search(r'subject(\d+)', path.name).group(1))
        key = guide_key_for_subject(level, subject_index)
        pages = {index: normalize(text) for index, text in load_page_texts(level, key).items()}
        old_pages = {index: normalize(text) for index, text in load_old_page_texts(level, key).items()}

        payload = load_json(path)
        for question in iter_questions(payload):
            stem = question.get('question') or ''
            options = question.get('options') or {}
            # 題幹與四個選項在頁面上被「（A）」之類的標記隔開，必須分開比對再加權，
            # 串成一條字串比會被最長共同子串低估。
            parts = [normalize(stem)] + [normalize(options.get(k, '')) for k in 'ABCD']
            parts = [p for p in parts if p]
            stem_probe = normalize(stem)
            ref = question.get('source_ref') or {}
            cited = ref.get('question_page')

            weight = sum(len(p) for p in parts)

            def score_against(text: str) -> float:
                if not text or not weight:
                    return 0.0
                return sum(len(p) * coverage(p, text) for p in parts) / weight

            def score_from(corpus: dict[int, str], index: int) -> float:
                # 題目常跨頁（選項 C/D 印在下一頁），單頁比會低估；先比單頁，
                # 不滿分再補比「本頁＋下一頁」。
                score = score_against(corpus.get(index, ''))
                if score < EXACT and corpus.get(index + 1):
                    score = max(score, score_against(
                        corpus.get(index, '') + '\n' + corpus[index + 1]))
                return score

            def best_over(corpus: dict[int, str]) -> tuple[float, int | None]:
                best, best_index = 0.0, None
                for index in corpus:
                    score = score_from(corpus, index)
                    if score > best:
                        best, best_index = score, index
                    if best >= 0.999:
                        break
                return best, best_index

            at_page = 0.0
            best_page = None
            if isinstance(cited, int):
                # 依 |offset| 由小到大，讓引用頁本身優先勝出；否則跨頁串接會讓
                # 前一頁也拿到滿分，整批被誤標成「頁碼偏移」。
                for offset in sorted(range(-PAGE_WINDOW, PAGE_WINDOW + 1), key=abs):
                    score = score_from(pages, cited + offset)
                    if score > at_page:
                        at_page, best_page = score, cited + offset
                    if at_page >= EXACT:
                        break

            # 引用頁已命中就不必再掃全書（掃全書是這支腳本的主要成本）。
            if at_page >= EXACT:
                whole_score, whole_page = at_page, best_page
            else:
                whole_score, whole_page = best_over(pages)
            old_at_page = score_from(old_pages, cited) if isinstance(cited, int) else 0.0
            old_score = old_at_page if old_at_page >= EXACT else best_over(old_pages)[0]

            record = {
                'file': path.name,
                'id': question.get('id'),
                'chapter_id': question.get('chapter_id'),
                'cited_page': cited,
                'coverage_at_cited_page': round(at_page, 3),
                'matched_page': best_page,
                'coverage_whole_guide': round(whole_score, 3),
                'best_page_in_guide': whole_page,
                'coverage_old_guide': round(old_score, 3),
                'regression': round(whole_score - old_score, 3),
                'coverage_stem_only': round(max(
                    (coverage(stem_probe, text) for text in pages.values()), default=0.0), 3),
            }

            if at_page >= EXACT and best_page == cited:
                record['status'] = 'ok'
            elif at_page >= EXACT:
                record['status'] = 'page_shifted'
            elif record['coverage_whole_guide'] >= EXACT:
                record['status'] = 'moved_in_guide'
            elif record['coverage_whole_guide'] >= PARTIAL:
                record['status'] = 'text_drifted'
            elif record['coverage_old_guide'] >= PARTIAL:
                record['status'] = 'lost_in_new_ocr'
            else:
                record['status'] = 'never_matched'
            results.append(record)
    return {'exercises': results}


def check_chapter_drift(level: str, guides: dict[str, dict[str, Any]],
                        old_guides: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """章節正文新舊相似度，並檢查練習題是否仍混在正文裡。"""
    exercise_probes: dict[str, list[str]] = {}
    for path in sorted((BASE / f'data/{level}/questions').glob('subject*_guide_exercises.json')):
        for question in iter_questions(load_json(path)):
            chapter_id = question.get('chapter_id')
            if chapter_id:
                exercise_probes.setdefault(chapter_id, []).append(
                    normalize(question.get('question') or ''))

    rows: list[dict[str, Any]] = []
    for chapter_id, chapter in sorted(guides.items()):
        new_text = normalize(chapter_text(chapter))
        old_text = normalize(chapter_text(old_guides.get(chapter_id)))
        probes = exercise_probes.get(chapter_id, [])
        rows.append({
            'chapter_id': chapter_id,
            'title': chapter.get('title'),
            'old_chars': len(old_text),
            'new_chars': len(new_text),
            'similarity': round(ratio(old_text, new_text), 3),
            'exercises_in_old_body': sum(1 for p in probes if p and coverage(p, old_text) >= EXACT),
            'exercises_in_new_body': sum(1 for p in probes if p and coverage(p, new_text) >= EXACT),
            'exercise_count': len(probes),
        })
    return {'chapters': rows}


def check_codex100(level: str, guides: dict[str, dict[str, Any]],
                   old_guides: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """精選 100 題沒有逐字引文，只能量它所引章節的漂移程度與 tag 命中率。"""
    rows: list[dict[str, Any]] = []
    cache: dict[str, tuple[str, str, float]] = {}

    def chapter_pair(chapter_id: str) -> tuple[str, str, float]:
        if chapter_id not in cache:
            new = normalize(chapter_text(guides.get(chapter_id)))
            old = normalize(chapter_text(old_guides.get(chapter_id)))
            cache[chapter_id] = (new, old, ratio(old, new))
        return cache[chapter_id]

    for path in sorted((BASE / f'data/{level}/questions').glob('subject*_codex100_questions.json')):
        for question in iter_questions(load_json(path)):
            refs = question.get('source_refs') or {}
            chapter_id = refs.get('chapter_id') or question.get('chapter_id')
            chapter = guides.get(chapter_id)
            new_text, old_text, similarity = chapter_pair(chapter_id or '')
            tags = [normalize(t) for t in (question.get('tags') or []) if t]
            hit = sum(1 for t in tags if t and t in new_text)
            hit_old = sum(1 for t in tags if t and t in old_text)
            rows.append({
                'file': path.name,
                'id': question.get('id'),
                'chapter_id': chapter_id,
                'chapter_exists': chapter is not None,
                'chapter_similarity': round(similarity, 3),
                'tags': len(tags),
                'tags_in_new': hit,
                'tags_in_old': hit_old,
            })
    return {'questions': rows}


# --------------------------------------------------------------------------
# 報告
# --------------------------------------------------------------------------

def summarize(level: str, report: dict[str, Any]) -> None:
    print(f'\n{"=" * 68}\n{level}\n{"=" * 68}')

    refs = report['chapter_refs']
    print(f'\n[1] 章節引用完整性：檢查 {refs["checked"]} 題')
    print(f'    chapter_id 失效：{len(refs["broken_chapter_id"])}')
    print(f'    章節標題與現行不符：{len(refs["title_mismatch"])}')
    for row in refs['broken_chapter_id'][:5]:
        print(f'      ! {row["file"]} {row["id"]} → {row["chapter_id"]}')
    for row in refs['title_mismatch'][:5]:
        print(f'      ~ {row["chapter_id"]}：題庫「{row["cited"]}」／現行「{row["current"]}」')

    exercises = report['guide_exercises']['exercises']
    print(f'\n[2] guide_exercises 引文對齊：共 {len(exercises)} 題')
    order = ['ok', 'page_shifted', 'moved_in_guide', 'text_drifted',
             'lost_in_new_ocr', 'never_matched']
    label = {
        'ok': '引用頁仍逐字命中',
        'page_shifted': '命中但頁碼偏移',
        'moved_in_guide': '全書逐字命中、不在引用頁',
        'text_drifted': '只部分命中（文字被改寫）',
        'lost_in_new_ocr': '舊版找得到、新版找不到',
        'never_matched': '新舊都找不到（擷取時就已改寫）',
    }
    counts = {status: 0 for status in order}
    for row in exercises:
        counts[row['status']] += 1
    for status in order:
        if counts[status]:
            print(f'    {label[status]:<24} {counts[status]:>4}')
    regressed = sorted((r for r in exercises if r['regression'] <= -0.05),
                       key=lambda r: r['regression'])
    preexisting = [r for r in exercises
                   if r['status'] not in ('ok', 'page_shifted') and r['regression'] > -0.05]
    print(f'    ── 本輪 OCR 造成的退化（新版比舊版差）：{len(regressed)} 題')
    for row in regressed:
        print(f'      ! {row["id"]} p{row["cited_page"]}：'
              f'舊版 {row["coverage_old_guide"]} → 新版 {row["coverage_whole_guide"]}'
              f'（{row["regression"]:+.3f}）')
    print(f'    ── 對不上但舊版就這樣（非本輪造成）：{len(preexisting)} 題')
    for row in preexisting[:5]:
        print(f'      ~ {row["id"]} p{row["cited_page"]} 全書 {row["coverage_whole_guide"]}'
              f' / 舊版 {row["coverage_old_guide"]}')
    if len(preexisting) > 5:
        print(f'      …另有 {len(preexisting) - 5} 題，見 JSON 報告')

    chapters = report['chapter_drift']['chapters']
    print(f'\n[3] 章節正文漂移：共 {len(chapters)} 章')
    if chapters:
        avg = sum(row['similarity'] for row in chapters) / len(chapters)
        low = [row for row in chapters if row['similarity'] < 0.5]
        print(f'    新舊平均相似度 {avg:.3f}；相似度 <0.5 的章節 {len(low)} 個')
        for row in sorted(chapters, key=lambda r: r['similarity'])[:5]:
            print(f'      {row["chapter_id"]} {row["title"]}：'
                  f'{row["similarity"]:.3f}（{row["old_chars"]}→{row["new_chars"]} 字）')
        in_old = sum(row['exercises_in_old_body'] for row in chapters)
        in_new = sum(row['exercises_in_new_body'] for row in chapters)
        total_ex = sum(row['exercise_count'] for row in chapters)
        print(f'    練習題混入正文：舊版 {in_old}/{total_ex} → 新版 {in_new}/{total_ex}')

    codex = report['codex100']['questions']
    if codex:
        print(f'\n[4] 精選 100 題章節引用：共 {len(codex)} 題')
        missing = [row for row in codex if not row['chapter_exists']]
        drifted = [row for row in codex if row['chapter_similarity'] < 0.5]
        worse = [row for row in codex if row['tags_in_new'] < row['tags_in_old']]
        better = [row for row in codex if row['tags_in_new'] > row['tags_in_old']]
        tags_total = sum(row['tags'] for row in codex)
        tags_hit = sum(row['tags_in_new'] for row in codex)
        print(f'    引用章節不存在：{len(missing)}')
        print(f'    所引章節相似度 <0.5：{len(drifted)}')
        print(f'    tag 在新版章節命中率：{tags_hit}/{tags_total}'
              f'（{tags_hit / tags_total:.1%}）' if tags_total else '')
        print(f'    tag 命中新版比舊版少：{len(worse)}；多：{len(better)}')


def run_level(level: str) -> dict[str, Any]:
    guides = load_guides(level)
    old_guides = load_guides(level, backup=True)
    manifest = load_manifest_chapters(level)
    return {
        'level': level,
        'chapter_refs': check_chapter_refs(level, guides, manifest),
        'guide_exercises': check_guide_exercises(level),
        'chapter_drift': check_chapter_drift(level, guides, old_guides),
        'codex100': check_codex100(level, guides, old_guides),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--level', choices=LEVELS, help='只跑單一級別（預設兩級都跑）')
    parser.add_argument('--json', type=Path, help='把完整報告寫成 JSON')
    args = parser.parse_args()

    levels = [args.level] if args.level else list(LEVELS)
    reports = []
    for level in levels:
        report = run_level(level)
        summarize(level, report)
        reports.append(report)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(reports, ensure_ascii=False, indent=2) + '\n',
                             encoding='utf-8')
        print(f'\n完整報告 → {args.json}')


if __name__ == '__main__':
    main()
