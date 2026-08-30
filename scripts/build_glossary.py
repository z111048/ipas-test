#!/usr/bin/env python3
"""Generate glossary entries for the concepts that actually get examined.

Term list comes from the signed-off vocabulary's heat table (`topicHeat.json`), so
what lands in the glossary is driven by how often a concept appears in official
papers — not by an author's guess. Each entry is written from source excerpts:
the study-guide chapters where the concept lives (primary) plus the reference
answers of questions labelled with it (secondary). A term with no usable excerpt
is reported, never invented.

Subject ids and names come from `data/{level}/toc_manifest.json` (invariant 1) —
this script must not carry its own chapter/subject table.

Usage:
  # 1. see what would be generated, no API calls
  python3 scripts/build_glossary.py --level 初級 --dry-run
  # 2. generate into data/{level}/pipeline/glossary/generated.json
  python3 scripts/build_glossary.py --level 初級 --min-count 3
  # 3. merge into the frontend bundle (existing entries are kept, never overwritten)
  python3 scripts/build_glossary.py --level 初級 --apply

Existing entries are preserved by default: the 62 中級 terms shipped before this
script existed have been reviewed and pass `verify_glossary_terms.py`, so there is
nothing to gain from re-rolling them. `--regenerate` overrides that.

After --apply, always run:
  python3 scripts/verify_glossary_terms.py --glossary <the written file>
  python3 scripts/audit_resources.py
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

BASE = Path(__file__).resolve().parents[1]
GENERATED = BASE / 'frontend' / 'src' / 'generated'
HEAT = GENERATED / 'topicHeat.json'
GUIDE_CONTENT = GENERATED / 'guideContent'
EXAM_ANSWERS = GENERATED / 'examReferenceAnswers'
ASSIGNMENTS = BASE / 'data' / 'topics' / 'question_topics.json'
GLOSSARY_FILE = {'初級': GENERATED / 'primaryGlossary.json',
                 '中級': GENERATED / 'middleGlossary.json'}

# Generator is deliberately NOT in the default verifier roster of
# verify_glossary_terms.py — a model grading its own prose is not a check.
DEFAULT_MODEL = 'glm-5.2'
GUIDE_EXCERPT_CHARS = 700
EXAM_EXCERPT_CHARS = 500
MAX_GUIDE_EXCERPTS = 3
MAX_EXAM_EXCERPTS = 2

PROMPT = """你正在替台灣 iPAS AI 應用規劃師（{level}）考試的學習網站撰寫一則名詞解釋。

術語：{name}

以下是這個術語在官方學習指引與歷屆試題詳解中的原文片段。片段的作用是告訴你**這份教材
與考試強調這個概念的哪一面**，請用它決定用詞與著重點，但**釋義本身必須是這個術語通行、
完整的定義**——不要把某一題的特定情境當成定義，也不要寫出與片段矛盾的內容。

{sources}

請輸出一則詞條，要求：
- definition：一句話、60～90 個中文字，說明這個概念「是什麼」，不要舉例、不要贅述歷史。
  即使片段只談到這個概念的某個側面，定義仍要涵蓋它的核心意義。
- example：一句話的實際應用情境，要與 definition 描述的是同一個概念。
- en：這個術語通行的英文名稱（可含常見縮寫，例如「Retrieval-Augmented Generation, RAG」）；
  若本來就是英文或縮寫術語，寫出全稱。
- 用詞為台灣繁體中文用語。

若上面的片段不足以支撐一則正確的釋義，請把 insufficient 設為 true 並讓其他欄位留空。

只回傳 JSON，不要有其他文字：
{{"zh": "{name}", "en": "...", "definition": "...", "example": "...", "insufficient": false}}
"""


# ---------------------------------------------------------------------------
# Term selection
# ---------------------------------------------------------------------------

def guide_keys_for_level(level: str) -> dict[str, tuple[str, str]]:
    """guideKey → (subject_id, subject_name), straight from the manifest (SSOT)."""
    manifest = load_json(BASE / 'data' / level / 'toc_manifest.json')
    return {f'{level}-{s["key"]}': (s['id'], s['subject']) for s in manifest['subjects']}


def select_terms(level: str, min_count: int) -> list[dict[str, Any]]:
    """Heat-table topics that this level's chapters actually cover.

    A topic is filed under whichever of the level's subjects carries the most of
    its questions; ties break on the subject id so the output is stable.
    """
    heat = load_json(HEAT)
    keys = guide_keys_for_level(level)
    terms = []
    for topic in heat['topics']:
        by_subject: dict[str, int] = {}
        chapters: list[str] = []
        for chapter in topic['chapters']:
            entry = keys.get(chapter.get('guideKey') or '')
            if not entry:
                continue
            subject_id = entry[0]
            by_subject[subject_id] = by_subject.get(subject_id, 0) + chapter['count']
            if chapter.get('kind') == 'guide':
                chapters.append(chapter['nodeId'])
        if not by_subject or topic['count'] < min_count:
            continue
        subject_id = sorted(by_subject.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        terms.append({
            'name': topic['name'],
            'count': topic['count'],
            'subject': subject_id,
            'subjectName': next(v[1] for v in keys.values() if v[0] == subject_id),
            'guideChapters': sorted(set(chapters)),
        })
    terms.sort(key=lambda t: (-t['count'], t['name']))
    return terms


# ---------------------------------------------------------------------------
# Source excerpts
# ---------------------------------------------------------------------------

def split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]


_PARAGRAPH_CACHE: dict[Path, list[str]] = {}


def chapter_paragraphs(path: Path) -> list[str]:
    """Chapter files run 100KB–1MB; parse each one once per run."""
    if path not in _PARAGRAPH_CACHE:
        _PARAGRAPH_CACHE[path] = split_paragraphs(load_json(path).get('content', ''))
    return _PARAGRAPH_CACHE[path]


def load_aliases() -> dict[str, list[str]]:
    """Canonical topic name → its signed-off aliases.

    The guide rarely spells a concept the way the vocabulary does ("檢索增強生成"
    vs "RAG"); without the aliases, matching on the canonical name alone leaves
    a third of the terms with no guide excerpt at all.
    """
    topics = load_json(BASE / 'data' / 'topics' / 'topics.json')['topics']
    return {t['name']: t.get('aliases', []) for t in topics}


def guide_excerpts(term: dict[str, Any], level: str, aliases: dict[str, list[str]]
                   ) -> list[dict[str, str]]:
    """Paragraphs that mention the concept, from its own chapters first.

    Only matching paragraphs are carried forward, so the prompt stays about this
    concept instead of about the whole chapter. If the concept's own chapters
    never name it, the rest of the same subject's guide is searched — a concept
    can be examined out of a chapter that only alludes to it.
    """
    needles = [term['name']] + aliases.get(term['name'], [])
    excerpts: list[dict[str, str]] = []

    def collect(path: Path) -> None:
        for paragraph in chapter_paragraphs(path):
            if len(excerpts) >= MAX_GUIDE_EXCERPTS:
                return
            if any(needle in paragraph for needle in needles):
                excerpts.append({'source': f'{path.parent.name}/{path.stem}',
                                 'text': paragraph[:GUIDE_EXCERPT_CHARS]})

    guide_dirs = sorted(GUIDE_CONTENT.glob(f'{level}-guide*'))
    for chapter_id in term['guideChapters']:
        for guide_dir in guide_dirs:
            path = guide_dir / f'{chapter_id}.json'
            if path.exists():
                collect(path)
    if not excerpts:
        for guide_dir in guide_dirs:
            for path in sorted(guide_dir.glob('*.json')):
                collect(path)
    return excerpts[:MAX_GUIDE_EXCERPTS]


def build_exam_index(level: str) -> dict[str, list[tuple[str, str]]]:
    """topic → [(question_id, reference answer text)] for this level's papers."""
    prefix = 'jr_' if level == '初級' else 'mid_'
    answers: dict[str, dict[str, Any]] = {}
    for path in EXAM_ANSWERS.glob('*.json'):
        answers[path.stem] = load_json(path)
    index: dict[str, list[tuple[str, str]]] = {}
    for key, record in load_json(ASSIGNMENTS)['assignments'].items():
        paper, _, question_id = key.partition(':')
        if not paper.startswith(prefix):
            continue
        text = (answers.get(paper, {}).get(question_id, {}) or {}).get('reference_answer', '')
        if not text:
            continue
        for topic in record.get('topics', []):
            # qualify with the paper: `exam1_q43` exists in both jr_1141_s1 and
            # mid_1141_s1, so the bare id is not a traceable citation
            index.setdefault(topic, []).append((f'{paper}:{question_id}', text))
    return index


def format_sources(guide: list[dict[str, str]], exam: list[dict[str, str]]) -> str:
    lines = []
    if guide:
        lines.append('【學習指引原文】')
        for item in guide:
            lines.append(f'（{item["source"]}）{item["text"]}')
    if exam:
        lines.append('\n【歷屆試題詳解】')
        for item in exam:
            lines.append(f'（{item["source"]}）{item["text"]}')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def extract_entry(raw: str | None) -> dict[str, Any] | None:
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
    if not isinstance(data, dict):
        return None
    return data


def generate(term: dict[str, Any], level: str, model: str, timeout: int, retries: int
             ) -> dict[str, Any]:
    prompt = PROMPT.format(level=level, name=term['name'], sources=term['_sources_text'])
    for _ in range(retries + 1):
        data = extract_entry(call_gateway(prompt, model, timeout, max_tokens=2048))
        if data is None:
            continue
        if data.get('insufficient'):
            return {'status': 'insufficient', 'term': term['name']}
        entry = {k: str(data.get(k, '')).strip() for k in ('zh', 'en', 'definition', 'example')}
        entry['zh'] = entry['zh'] or term['name']
        if not entry['definition'] or not entry['example']:
            continue
        return {'status': 'ok', 'term': term['name'], 'entry': entry}
    return {'status': 'failed', 'term': term['name']}


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------

def merge(level: str, generated: dict[str, Any], regenerate: bool) -> dict[str, Any]:
    path = GLOSSARY_FILE[level]
    keys = guide_keys_for_level(level)
    subject_names = {sid: name for sid, name in keys.values()}
    if path.exists():
        bundle = load_json(path)
    else:
        bundle = {'level': level, 'subjects': {}}
    for subject_id in sorted(subject_names):
        bundle['subjects'].setdefault(subject_id,
                                      {'subject': subject_names[subject_id], 'terms': []})

    added = kept = 0
    for record in generated['results']:
        if record['status'] != 'ok':
            continue
        subject = bundle['subjects'][record['subject']]
        existing = {t['zh']: t for t in subject['terms']}
        entry = dict(record['entry'])
        entry['sources'] = record['sources']
        if record['term'] in existing and not regenerate:
            kept += 1
            continue
        if record['term'] in existing:
            subject['terms'] = [t for t in subject['terms'] if t['zh'] != record['term']]
        subject['terms'].append(entry)
        added += 1
    for subject in bundle['subjects'].values():
        subject['terms'].sort(key=lambda t: t['zh'])
    save_json(path, bundle)
    total = sum(len(s['terms']) for s in bundle['subjects'].values())
    print(f'→ {path.relative_to(BASE)}: {total} 詞條（新增 {added}，保留既有 {kept}）')
    return bundle


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--level', required=True, choices=['初級', '中級'])
    parser.add_argument('--min-count', type=int, default=3,
                        help='minimum official-question count for a concept to earn a '
                             'glossary entry (default 3)')
    parser.add_argument('--model', default=DEFAULT_MODEL)
    parser.add_argument('--timeout', type=int, default=180)
    parser.add_argument('--retries', type=int, default=1)
    parser.add_argument('--workers', type=int, default=6)
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--dry-run', action='store_true',
                        help='list the terms and their source coverage, make no API calls')
    parser.add_argument('--apply', action='store_true',
                        help='merge an existing generated.json into the frontend bundle')
    parser.add_argument('--regenerate', action='store_true',
                        help='overwrite entries that already exist (default: keep them)')
    args = parser.parse_args()

    load_env_file()
    out_dir = BASE / 'data' / args.level / 'pipeline' / 'glossary'
    out_path = out_dir / 'generated.json'

    if args.apply:
        if not out_path.exists():
            raise SystemExit(f'nothing to apply: {out_path} does not exist')
        merge(args.level, load_json(out_path), args.regenerate)
        return

    terms = select_terms(args.level, args.min_count)
    existing: set[str] = set()
    glossary_path = GLOSSARY_FILE[args.level]
    if glossary_path.exists() and not args.regenerate:
        existing = {t['zh'] for s in load_json(glossary_path)['subjects'].values()
                    for t in s['terms']}
    pending = [t for t in terms if t['name'] not in existing]
    if args.limit:
        pending = pending[:args.limit]

    exam_index = build_exam_index(args.level)
    aliases = load_aliases()
    no_source = []
    for term in pending:
        guide = guide_excerpts(term, args.level, aliases)
        exam = [{'source': qid, 'text': text[:EXAM_EXCERPT_CHARS]}
                for qid, text in exam_index.get(term['name'], [])[:MAX_EXAM_EXCERPTS]]
        term['_guide'] = guide
        term['_exam'] = exam
        term['_sources_text'] = format_sources(guide, exam)
        if not guide and not exam:
            no_source.append(term['name'])

    print(f'{args.level}：熱度 ≥{args.min_count} 的概念 {len(terms)} 個，'
          f'已有詞條 {len(terms) - len([t for t in terms if t["name"] not in existing])} 個，'
          f'待生成 {len(pending)} 個')
    with_guide = len([t for t in pending if t['_guide']])
    print(f'  有講義原文可用 {with_guide}／有詳解可用 '
          f'{len([t for t in pending if t["_exam"]])}／兩者皆無 {len(no_source)}')
    if no_source:
        print(f'  無來源（不生成）：{"、".join(no_source)}')
    if args.dry_run:
        for term in pending[:40]:
            print(f'  {term["count"]:3d}  {term["subject"]}  {term["name"]}  '
                  f'(guide {len(term["_guide"])}, exam {len(term["_exam"])})')
        return

    runnable = [t for t in pending if t['_sources_text']]
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(generate, term, args.level, args.model,
                               args.timeout, args.retries): term for term in runnable}
        done = 0
        for future in as_completed(futures):
            term = futures[future]
            record = future.result()
            record['subject'] = term['subject']
            record['count'] = term['count']
            sources = [e['source'] for e in term['_guide']] + [e['source'] for e in term['_exam']]
            record['sources'] = list(dict.fromkeys(sources))  # same chapter can supply 2 paragraphs
            results.append(record)
            done += 1
            print(f'\r  generated {done}/{len(runnable)}', end='', flush=True)
    print()
    results.sort(key=lambda r: (-r['count'], r['term']))

    generated = {'level': args.level, 'model': args.model, 'minCount': args.min_count,
                 'results': results,
                 'noSource': no_source}
    save_json(out_path, generated)
    ok = len([r for r in results if r['status'] == 'ok'])
    print(f'生成成功 {ok}／{len(runnable)}；'
          f'來源不足 {len([r for r in results if r["status"] == "insufficient"])}、'
          f'失敗 {len([r for r in results if r["status"] == "failed"])}')
    print(f'→ {out_path.relative_to(BASE)}（用 --apply 併進前端 bundle）')


if __name__ == '__main__':
    main()
