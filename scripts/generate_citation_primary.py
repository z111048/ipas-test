#!/usr/bin/env python3
"""Regenerate the curated primary guide citations of every exam question.

Writes ``data/guide_citation_primary.json`` (consumed by
``export_exam_reference_answers.py``) and the internal gap list
``data/audit/guide_content_gaps.json``.  Three steps share one work
directory (raw model outputs are kept there, never in the repo):

    python3 scripts/generate_citation_primary.py prepare  --work-dir DIR
    python3 scripts/generate_citation_primary.py run      --work-dir DIR --budget-usd 5
    python3 scripts/generate_citation_primary.py finalize --work-dir DIR

prepare
    BM25 over every guideContent block of the question's level (query =
    question + correct option text + exported key_concepts; three-block
    window for scoring, tables flattened row by row).  K=20 candidates,
    shown as the block's own text prefixed by 〔chapter｜section heading〕;
    headings, exercise questions and empty blocks are not candidates, chapter
    exercise worked answers are (at most 3, flagged 章末練習解析) but may
    only become secondary.
run
    One ``cshare`` call per question (local gateway CLI, default model
    deepseek-v4.1-flash:1017), at most 4 in parallel.  Ids outside the
    candidate list are dropped; exercise answers / headings chosen as primary
    are moved to secondary.  One retry when the output does not parse, an
    empty primary comes without 1-2 secondary blocks, or a ``why`` breaks the
    reader-facing rules (25 chars, 繁體, no internal wording).  Gateway spend
    (``/key/info``) is read before every call; the run stops at the budget.
finalize
    Binds every chosen block to the sha256 of its current text and writes
    the curated file; refuses to write when validation fails.

``cshare`` is a maintainer-local tool; ``run`` exits with a clear message
when it is not installed.  The curated method name is
``bm25-ds1017-reviewed``: model selection, rule-checked post-processing and a
50-question blind review before publication (2026-11-03).
"""

from __future__ import annotations

import argparse
import collections
import concurrent.futures
import datetime as dt
import json
import math
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any

from guide_block_id_migrations import load_content_tree
from guide_citation_primary import (
    CONTENT_ROOT,
    CURATED_PATH,
    GAPS_PATH,
    MAX_PRIMARY,
    MAX_SECONDARY,
    MAX_SECONDARY_WHEN_EMPTY,
    NON_PRIMARY_KINDS,
    SCHEMA_VERSION,
    WHY_MAX_CHARS,
    block_kind,
    block_text_hash,
    validate_payload,
    why_problems,
)
from resource_catalog import exam_entries, level_entries
from run_codex_exam_reference_answers import question_content_fingerprint


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_DIR = ROOT / 'frontend/src/generated/examReferenceAnswers'
DEFAULT_MODEL = 'deepseek-v4.1-flash:1017'
METHOD = 'bm25-ds1017-reviewed'
K = 20
MAX_EXERCISE_CANDIDATES = 3
CANDIDATE_CHARS = 320
MAX_WORKERS = 4
GATEWAY_KEY_INFO = 'https://llm-share.duotify.com/key/info'
GATEWAY_ENV = Path.home() / '.config/llmshare/env'
SYSTEM_PROMPT = '你是嚴謹的教材出處校對員，只輸出要求的 JSON。'
EXCLUDED_CANDIDATE_KINDS = {'heading', 'exercise_question', 'source_image'}

PROMPT_TEMPLATE = """你是 iPAS AI 應用規劃師考試教材的出處校對員。下面是一道官方考題、它的正確答案與題解重點，以及從學習指引找出的段落清單（每段開頭是代號，〔〕內是所在章節與小節標題，只供定位）。
任務：只挑出「考生讀了就能判斷正確答案、或能排除主要錯誤選項」的段落。

規則：
1. 只能從清單中選代號（如 C3），不得自創；同一概念的重複段落只選一個；最多 3 個 primary、3 個 secondary。
2. primary＝段落本身直接陳述了解題所需的定義、條件、規則或結論；寧缺勿濫，通常 1–2 個就夠。secondary＝同主題的背景說明，有助理解但不足以單獨解題。
3. 只沾到題目關鍵字、卻沒有陳述解題所需定義／條件／結論的段落，不得列為 primary（寧可放 secondary 或不選）。
4. 標示〔章末練習解析〕的段落只能列為 secondary，不得列為 primary。
5. 否定題（問「何者錯誤／不正確／不屬於／最不適合」等）：primary 要選能支撐「正確答案那個選項為何不成立」的段落，例如陳述正確定義而與該選項矛盾的段落。
6. 若沒有任何段落直接支撐答案，primary 回傳空陣列，在 gap 說明教材缺少的概念（例如「教材未介紹 Kendall 相關係數」），而且 secondary 必須給 1–2 個最接近、對理解最有幫助的段落。
7. 有 primary 時，若教材只缺部分細節，可在 gap 簡述；否則 gap 為空字串。
8. why 寫給考生看：不超過 25 個字（標點也算）、繁體中文，說明這段教材如何幫助作答；不得出現代號、「清單」「段落編號」等內部字樣。
只輸出 JSON，不要其他文字：
{{"primary":[{{"id":"…","why":"…"}}],"secondary":[{{"id":"…","why":"…"}}],"gap":"…或空字串"}}

【題目】{question}
【選項】
{options}
【正確答案】{answer}
【題解重點】{key_concepts}
【段落清單】
{candidates}
"""

RETRY_NOTE = """

【上次輸出有問題，請修正後重新只輸出 JSON】
{problems}"""


# --------------------------------------------------------------------- BM25
def flat_text(block: dict[str, Any]) -> str:
    text = str(block.get('text') or block.get('title') or '')
    if not text and block.get('rows'):
        text = ' | '.join(' / '.join(str(cell or '') for cell in row) for row in block['rows'])
    return re.sub(r'\s+', ' ', text).strip()


def tokens(value: str) -> list[str]:
    value = value.lower()
    out = re.findall(r'[a-z0-9][a-z0-9\-\.]*', value)
    for segment in re.findall(r'[一-鿿]+', value):
        out += [segment[i:i + 2] for i in range(len(segment) - 1)] or [segment]
    return out


def load_level_docs(level: str) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for guide_dir in sorted(CONTENT_ROOT.glob(f'{level}-guide*')):
        for path in sorted(guide_dir.glob('*.json')):
            data = json.loads(path.read_text(encoding='utf-8'))
            blocks = data.get('blocks') or []
            heading = str(data.get('title') or '')
            for index, block in enumerate(blocks):
                kind = block_kind(block)
                if kind == 'heading':
                    heading = flat_text(block)
                window = ' '.join(flat_text(item) for item in blocks[max(0, index - 1):index + 2])
                docs.append({
                    'guideKey': guide_dir.name,
                    'nodeId': path.stem,
                    'blockId': str(block.get('id')),
                    'nodeTitle': str(data.get('title') or ''),
                    'heading': heading,
                    'kind': kind,
                    'text': flat_text(block),
                    'window': window,
                })
    return docs


class BM25:
    def __init__(self, docs: list[dict[str, Any]], k1: float = 1.5, b: float = 0.75) -> None:
        self.tf = [collections.Counter(tokens(doc['window'])) for doc in docs]
        self.length = [sum(counter.values()) for counter in self.tf]
        self.avg = sum(self.length) / len(self.length)
        df: collections.Counter[str] = collections.Counter()
        for counter in self.tf:
            df.update(counter.keys())
        total = len(docs)
        self.idf = {word: math.log(1 + (total - n + .5) / (n + .5)) for word, n in df.items()}
        self.k1, self.b = k1, b

    def scores(self, query: str) -> list[float]:
        terms = collections.Counter(tokens(query))
        out = []
        for counter, length in zip(self.tf, self.length):
            value = 0.0
            for word in terms:
                freq = counter.get(word)
                if freq:
                    value += self.idf[word] * freq * (self.k1 + 1) / (
                        freq + self.k1 * (1 - self.b + self.b * length / self.avg))
            out.append(value)
        return out


def _dedupe_key(text: str) -> str:
    return re.sub(r'[\s，。、：:（）()]', '', text)[:80]


def top_candidates(docs: list[dict[str, Any]], bm25: BM25, query: str) -> list[dict[str, Any]]:
    scores = bm25.scores(query)
    order = sorted(range(len(docs)), key=lambda i: -scores[i])
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    exercises = 0
    for i in order:
        if scores[i] <= 0:
            break
        doc = docs[i]
        if doc['kind'] in EXCLUDED_CANDIDATE_KINDS or not doc['text']:
            continue
        if doc['kind'] == 'exercise_answer':
            if exercises >= MAX_EXERCISE_CANDIDATES:
                continue
        key = _dedupe_key(doc['text'])
        if key in seen:  # c / pdf-c tracks repeat the same sentence
            continue
        seen.add(key)
        exercises += doc['kind'] == 'exercise_answer'
        out.append(doc)
        if len(out) >= K:
            break
    return out


# ------------------------------------------------------------------ prepare
def question_number(question_id: str) -> int | None:
    match = re.search(r'_q(\d+)$', question_id)
    return int(match.group(1)) if match else None


def build_items(exams: set[str] | None = None) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    corpora: dict[str, tuple[list[dict[str, Any]], BM25]] = {}
    for level_config in level_entries():
        level = level_config['dataLevel']
        for exam in exam_entries(level=level):
            route = exam['routeKey']
            if exams and route not in exams:
                continue
            questions = json.loads(
                (ROOT / 'data' / level / 'questions' / exam['questionFile']).read_text(encoding='utf-8')
            )['questions']
            references = json.loads((REFERENCE_DIR / f'{route}.json').read_text(encoding='utf-8'))
            ref_by_number = {question_number(key): value for key, value in references.items()}
            if level not in corpora:
                docs = load_level_docs(level)
                corpora[level] = (docs, BM25(docs))
            docs, bm25 = corpora[level]
            for question in questions:
                qid = str(question['id'])
                reference = ref_by_number.get(question_number(qid)) or {}
                answer = str(question.get('answer') or '')
                options = question.get('options') or {}
                answer_text = ' '.join(str(options.get(letter, '')) for letter in answer if letter in options)
                concepts = [str(item) for item in reference.get('key_concepts') or []]
                query = ' '.join([str(question.get('question') or ''), answer_text, *concepts])
                candidates = []
                for index, doc in enumerate(top_candidates(docs, bm25, query), start=1):
                    candidates.append({
                        'cid': f'C{index}',
                        'guideKey': doc['guideKey'],
                        'nodeId': doc['nodeId'],
                        'blockId': doc['blockId'],
                        'kind': doc['kind'],
                        'nodeTitle': doc['nodeTitle'],
                        'heading': doc['heading'],
                        'text': doc['text'],
                    })
                lines = []
                for cand in candidates:
                    tag = '〔章末練習解析〕' if cand['kind'] == 'exercise_answer' else ''
                    lines.append(f"{cand['cid']}〔{cand['nodeTitle']}｜{cand['heading'][:40]}〕{tag}"
                                 f"{cand['text'][:CANDIDATE_CHARS]}")
                prompt = PROMPT_TEMPLATE.format(
                    question=str(question.get('question') or ''),
                    options='\n'.join(f'{key}. {value}' for key, value in options.items()),
                    answer=answer,
                    key_concepts='；'.join(concepts),
                    candidates='\n'.join(lines),
                )
                items.append({
                    'key': f'{route}/{qid}',
                    'level': level,
                    'exam': route,
                    'questionId': qid,
                    'questionFingerprint': question_content_fingerprint(question),
                    'question': str(question.get('question') or ''),
                    'options': options,
                    'answer': answer,
                    'candidates': candidates,
                    'prompt': prompt,
                })
    return items


def cmd_prepare(args: argparse.Namespace) -> None:
    work = args.work_dir
    work.mkdir(parents=True, exist_ok=True)
    items = build_items(set(args.exams) if args.exams else None)
    (work / 'items.json').write_text(json.dumps(items, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    by_exam = collections.Counter(item['exam'] for item in items)
    print(f'prepared {len(items)} questions in {work}: {dict(by_exam)}')


# ---------------------------------------------------------------------- run
def gateway_spend() -> float:
    if not GATEWAY_ENV.exists():
        raise SystemExit(f'Gateway key file not found ({GATEWAY_ENV}); pass --no-budget-check to skip')
    match = re.search(r'LLMSHARE_API_KEY=["\']?([^"\'\n]+)', GATEWAY_ENV.read_text(encoding='utf-8'))
    if not match:
        raise SystemExit(f'LLMSHARE_API_KEY missing in {GATEWAY_ENV}')
    request = urllib.request.Request(GATEWAY_KEY_INFO, headers={'Authorization': f'Bearer {match.group(1)}'})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    return float((payload.get('info') or payload)['spend'])


def parse_output(text: str) -> dict[str, Any]:
    match = re.search(r'\{.*\}', text or '', re.S)
    if not match:
        raise ValueError('no JSON object in output')
    data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError('output is not an object')
    return data


def normalize(item: dict[str, Any], data: dict[str, Any]) -> tuple[dict[str, Any], list[str], list[str]]:
    """Apply the selection rules; return (result, retry problems, notes)."""
    by_cid = {cand['cid']: cand for cand in item['candidates']}
    notes: list[str] = []
    problems: list[str] = []
    picked: dict[str, list[dict[str, Any]]] = {'primary': [], 'secondary': []}
    seen: set[str] = set()
    for section in ('primary', 'secondary'):
        raw = data.get(section) or []
        if not isinstance(raw, list):
            problems.append(f'{section} 必須是陣列')
            continue
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            cid = str(entry.get('id') or '').strip()
            cand = by_cid.get(cid)
            if cand is None:
                notes.append(f'dropped unknown id {cid!r}')
                continue
            if cid in seen:
                continue
            seen.add(cid)
            target = section
            if section == 'primary' and cand['kind'] in NON_PRIMARY_KINDS:
                notes.append(f'{cid} ({cand["kind"]}) moved to secondary')
                target = 'secondary'
            why = str(entry.get('why') or '').strip()
            if target == 'primary' and why.startswith('補充'):
                # 「補充」 marks secondary citations for annotation prominence
                why = why.removeprefix('補充').lstrip('：:，、 ')
                notes.append(f'{cid} primary why lost its 補充 prefix')
            picked[target].append({'cid': cid, 'why': why})
    if len(picked['primary']) > MAX_PRIMARY:
        notes.append('primary truncated')
        picked['primary'] = picked['primary'][:MAX_PRIMARY]
    limit = MAX_SECONDARY if picked['primary'] else MAX_SECONDARY_WHEN_EMPTY
    if len(picked['secondary']) > limit:
        notes.append('secondary truncated')
        picked['secondary'] = picked['secondary'][:limit]
    if not picked['primary'] and not picked['secondary']:
        problems.append('primary 為空時，secondary 必須給 1–2 個最接近的段落')
    for section in ('primary', 'secondary'):
        for entry in picked[section]:
            for problem in why_problems(entry['why']):
                problems.append(f'{entry["cid"]} 的 why 不合規（{problem}）：「{entry["why"]}」'
                                f'，請改為 {WHY_MAX_CHARS} 字內繁體中文')
    gap = data.get('gap')
    result = {**picked, 'gap': gap.strip() if isinstance(gap, str) else ''}
    return result, problems, notes


def call_model(prompt: str, model: str, cshare: str, cwd: Path) -> dict[str, Any]:
    started = time.time()
    proc = subprocess.run(
        [cshare, '-m', model, '-p', prompt, '--bare', '--tools', '', '--system-prompt', SYSTEM_PROMPT,
         '--no-session-persistence', '--output-format', 'json'],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, cwd=cwd, timeout=600,
    )
    seconds = round(time.time() - started, 1)
    try:
        envelope = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {'ok': False, 'error': f'cshare exit {proc.returncode}: {proc.stderr[-500:]}', 'seconds': seconds}
    usage = envelope.get('usage') or {}
    return {
        'ok': not envelope.get('is_error'),
        'text': envelope.get('result') or '',
        'input_tokens': usage.get('input_tokens'),
        'output_tokens': usage.get('output_tokens'),
        'seconds': seconds,
        'error': envelope.get('result') if envelope.get('is_error') else None,
    }


def raw_path(work: Path, item: dict[str, Any]) -> Path:
    return work / 'raw' / f"{item['exam']}__{item['questionId']}.json"


def process_item(item: dict[str, Any], args: argparse.Namespace, cshare: str) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    prompt = item['prompt']
    best: tuple[dict[str, Any], list[str], list[str]] | None = None
    for attempt in range(2):
        call = call_model(prompt, args.model, cshare, args.work_dir)
        record = {'attempt': attempt + 1, **call}
        problems: list[str]
        if call['ok']:
            try:
                result, problems, notes = normalize(item, parse_output(call['text']))
                record.update(result=result, problems=problems, notes=notes)
                if best is None or len(problems) <= len(best[1]):
                    best = (result, problems, notes)
            except (ValueError, json.JSONDecodeError) as error:
                problems = [f'輸出無法解析為 JSON（{error}）']
                record['problems'] = problems
        else:
            problems = [f'call failed: {call.get("error")}']
            record['problems'] = problems
        attempts.append(record)
        if not problems:
            break
        prompt = item['prompt'] + RETRY_NOTE.format(problems='\n'.join(f'- {p}' for p in problems))
    payload = {
        'key': item['key'],
        'model': args.model,
        'attempts': attempts,
        'final': best[0] if best else None,
        'finalProblems': best[1] if best else ['no parsable output'],
        'finalNotes': best[2] if best else [],
    }
    path = raw_path(args.work_dir, item)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return payload


def cmd_run(args: argparse.Namespace) -> None:
    cshare = shutil.which('cshare') or str(Path.home() / '.local/bin/cshare')
    if not Path(cshare).exists():
        raise SystemExit('cshare not found: install the local llm-share gateway CLI (see '
                         '~/projects/local-llm docs) or run on the maintainer machine')
    items = json.loads((args.work_dir / 'items.json').read_text(encoding='utf-8'))
    if args.only:
        items = [item for item in items if item['key'] in set(args.only)]
    todo = [item for item in items if args.redo or not raw_path(args.work_dir, item).exists()]
    if args.limit:
        todo = todo[:args.limit]
    spend_file = args.work_dir / 'spend.json'
    budget_check = not args.no_budget_check
    if budget_check:
        meta = (json.loads(spend_file.read_text(encoding='utf-8')) if spend_file.exists()
                else {'startSpend': gateway_spend()})
        spend_file.write_text(json.dumps(meta) + '\n', encoding='utf-8')
    lock = threading.Lock()
    stop = threading.Event()
    done = 0

    def guarded(item: dict[str, Any]) -> dict[str, Any] | None:
        nonlocal done
        if stop.is_set():
            return None
        if budget_check:
            used = gateway_spend() - meta['startSpend']
            if used >= args.budget_usd:
                stop.set()
                print(f'BUDGET REACHED: {used:.4f} USD', flush=True)
                return None
        payload = process_item(item, args, cshare)
        with lock:
            done += 1
            final = payload['final'] or {}
            print(f"[{done}/{len(todo)}] {item['key']} attempts={len(payload['attempts'])} "
                  f"p={len(final.get('primary') or [])} s={len(final.get('secondary') or [])} "
                  f"problems={len(payload['finalProblems'])}", flush=True)
        return payload

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(args.workers, MAX_WORKERS)) as pool:
        list(pool.map(guarded, todo))
    if budget_check:
        used = gateway_spend() - meta['startSpend']
        meta['lastSpend'] = meta['startSpend'] + used
        spend_file.write_text(json.dumps(meta) + '\n', encoding='utf-8')
        print(f'gateway spend delta since start: {used:.4f} USD')
    if stop.is_set():
        sys.exit(2)


# ----------------------------------------------------------------- finalize
def cmd_finalize(args: argparse.Namespace) -> None:
    items = json.loads((args.work_dir / 'items.json').read_text(encoding='utf-8'))
    content = load_content_tree(CONTENT_ROOT)
    entries: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    missing: list[str] = []
    for item in items:
        path = raw_path(args.work_dir, item)
        payload = json.loads(path.read_text(encoding='utf-8')) if path.exists() else None
        override = (args.work_dir / 'fixes' / path.name)
        if override.exists():  # reviewer-corrected selection (same shape as ``final``)
            final = json.loads(override.read_text(encoding='utf-8'))
        else:
            final = (payload or {}).get('final')
        if not final:
            missing.append(item['key'])
            continue
        by_cid = {cand['cid']: cand for cand in item['candidates']}
        entry: dict[str, Any] = {
            'level': item['level'],
            'exam': item['exam'],
            'questionId': item['questionId'],
            'questionFingerprint': item['questionFingerprint'],
        }
        for section in ('primary', 'secondary'):
            refs = []
            for chosen in final.get(section) or []:
                cand = by_cid[chosen['cid']]
                block = next(b for b in content[cand['guideKey']][cand['nodeId']]
                             if str(b.get('id')) == cand['blockId'])
                refs.append({
                    'guideKey': cand['guideKey'],
                    'nodeId': cand['nodeId'],
                    'blockId': cand['blockId'],
                    'textHash': block_text_hash(block),
                    'why': (chosen['why'].removeprefix('補充').lstrip('：:，、 ')
                            if section == 'primary' else chosen['why']),
                })
            entry[section] = refs
        entry['gap'] = final.get('gap') or ''
        entries.append(entry)
        if entry['gap']:
            gaps.append({
                'level': item['level'], 'exam': item['exam'], 'questionId': item['questionId'],
                'primaryEmpty': not entry['primary'], 'gap': entry['gap'],
            })
    if missing:
        raise SystemExit(f'{len(missing)} questions have no usable output: {missing[:10]}')
    today = args.date or dt.date.today().isoformat()
    payload = {
        'schemaVersion': SCHEMA_VERSION,
        'description': (
            'Curated primary guide citations per exam question (scripts/generate_citation_primary.py). '
            'primary = blocks that directly state the definition/condition/conclusion needed for the '
            'official answer; secondary = related background (chapter exercise answers only here); '
            'gap = internal note on what the guide lacks (also in data/audit/guide_content_gaps.json, '
            'never shown to users). textHash = sha256 of guide_block_id_migrations.block_text(); '
            'export_exam_reference_answers.py fails closed on a missing block or changed text and puts '
            'primary first, demoting older citations to 補充.'
        ),
        'method': METHOD,
        'model': args.model,
        'generatedOn': today,
        'retrieval': f'BM25 over all guideContent blocks of the level, K={K}, '
                     'query=question+correct option+key_concepts',
        'questions': sorted(entries, key=lambda e: (e['level'], e['exam'],
                                                    question_number(e['questionId']) or 0)),
    }
    errors = validate_payload(payload, content)
    if errors:
        raise SystemExit('validation failed:\n  ' + '\n  '.join(errors[:40]))
    CURATED_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    GAPS_PATH.parent.mkdir(parents=True, exist_ok=True)
    GAPS_PATH.write_text(json.dumps({
        'description': 'Internal list of exam concepts the learning guide does not cover (from '
                       'data/guide_citation_primary.json gap). Not shown in the frontend.',
        'generatedOn': today,
        'source': 'data/guide_citation_primary.json',
        'count': len(gaps),
        'primaryEmpty': sum(1 for gap in gaps if gap['primaryEmpty']),
        'gaps': gaps,
    }, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    empty = sum(1 for entry in entries if not entry['primary'])
    print(f'wrote {len(entries)} entries to {CURATED_PATH.relative_to(ROOT)} '
          f'(primary empty={empty}, gaps={len(gaps)})')


# ------------------------------------------------------------------- review
REVIEW_PROMPT = """你是 iPAS AI 應用規劃師考試教材的嚴格出處審查員。下面是一道官方考題、正確答案，以及目前被列為「主要出處」的教材段落（P1、P2…）。
請逐段判斷是否保留為主要出處。

保留條件：段落本身「直接陳述」這題解題所需的關鍵事實（定義、條件、規則或結論），考生讀了就能選出正確答案或排除主要錯誤選項。
答案需要兩段合起來才完整時（例如各講一半），兩段都可保留。
必須降級：只沾到題目關鍵字、只講上位概念或相鄰概念、只是背景或泛論的段落。
例：題目考 XGBoost 樹複雜度懲罰，段落只講 L2 正則化定義 → 降級；考 AutoML，段落只講無程式碼工具 → 降級；考 RFT，段落只講強化學習 → 降級；考災難性遺忘，段落只講微調定義 → 降級。
有降級時，gap 用一句繁體中文寫出教材缺少的概念（例如「教材未說明 XGBoost 的樹複雜度懲罰」）；全部保留則 gap 為空字串。
只輸出 JSON，不要其他文字：
{{"keep":["P1"],"demote":["P2"],"gap":"…或空字串"}}

【題目】{question}
【選項】
{options}
【正確答案】{answer}
【主要出處段落】
{blocks}
"""


SECOND_PASS_NOTE = """
（複審：前一位審查員全部保留。請更嚴格：只要段落沒有明確寫出本題正確答案所依據的那個事實，就降級；有疑問時降級。）
"""


def review_path(work: Path, entry: dict[str, Any], review_pass: int = 1) -> Path:
    folder = 'review' if review_pass == 1 else f'review{review_pass}'
    return work / folder / f"{entry['exam']}__{entry['questionId']}.json"


def review_items(work: Path, review_pass: int = 1) -> list[dict[str, Any]]:
    items = {item['key']: item for item in json.loads((work / 'items.json').read_text(encoding='utf-8'))}
    content = load_content_tree(CONTENT_ROOT)
    payload = json.loads(CURATED_PATH.read_text(encoding='utf-8'))
    out = []
    for entry in payload['questions']:
        if not entry['primary']:
            continue
        if review_pass == 2:
            # second, stricter opinion only where the first pass kept every block
            first = json.loads(review_path(work, entry).read_text(encoding='utf-8'))['verdict']
            if first is None or first['demote']:
                continue
        item = items[f"{entry['exam']}/{entry['questionId']}"]
        lines = []
        for index, ref in enumerate(entry['primary'], start=1):
            blocks = content[ref['guideKey']][ref['nodeId']]
            position = next(i for i, b in enumerate(blocks) if str(b.get('id')) == ref['blockId'])
            heading = ''
            for block in blocks[position::-1]:
                if block_kind(block) == 'heading':
                    heading = flat_text(block)
                    break
            lines.append(f'P{index}〔{heading[:40]}〕{flat_text(blocks[position])[:700]}')
        prompt = REVIEW_PROMPT.format(
            question=item['question'],
            options='\n'.join(f'{k}. {v}' for k, v in item['options'].items()),
            answer=item['answer'],
            blocks='\n'.join(lines),
        )
        if review_pass == 2:
            prompt = prompt.replace('【題目】', SECOND_PASS_NOTE.strip() + '\n\n【題目】', 1)
        out.append({'entry': entry, 'prompt': prompt})
    return out


def cmd_review(args: argparse.Namespace) -> None:
    cshare = shutil.which('cshare') or str(Path.home() / '.local/bin/cshare')
    if not Path(cshare).exists():
        raise SystemExit('cshare not found: the review step needs the local llm-share gateway CLI')
    todo = [r for r in review_items(args.work_dir, args.review_pass)
            if args.redo or not review_path(args.work_dir, r['entry'], args.review_pass).exists()]
    if args.limit:
        todo = todo[:args.limit]
    meta_path = args.work_dir / 'review_spend.json'
    meta = (json.loads(meta_path.read_text(encoding='utf-8')) if meta_path.exists()
            else {'startSpend': gateway_spend()})
    meta_path.write_text(json.dumps(meta) + '\n', encoding='utf-8')
    stop = threading.Event()
    lock = threading.Lock()
    done = 0

    def one(review: dict[str, Any]) -> None:
        nonlocal done
        if stop.is_set():
            return
        used = gateway_spend() - meta['startSpend']
        if used >= args.budget_usd:
            stop.set()
            print(f'BUDGET REACHED: {used:.4f} USD', flush=True)
            return
        entry = review['entry']
        labels = {f'P{i}' for i in range(1, len(entry['primary']) + 1)}
        attempts = []
        verdict = None
        for _ in range(2):
            call = call_model(review['prompt'], args.model, cshare, args.work_dir)
            attempts.append(call)
            if not call['ok']:
                continue
            try:
                data = parse_output(call['text'])
            except (ValueError, json.JSONDecodeError):
                continue
            keep = [x for x in data.get('keep') or [] if x in labels]
            demote = [x for x in data.get('demote') or [] if x in labels and x not in keep]
            if set(keep) | set(demote) != labels:  # unlisted blocks are kept
                keep += sorted(labels - set(keep) - set(demote))
            gap = data.get('gap') if isinstance(data.get('gap'), str) else ''
            verdict = {'keep': keep, 'demote': demote, 'gap': gap.strip()}
            break
        path = review_path(args.work_dir, entry, args.review_pass)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'key': f"{entry['exam']}/{entry['questionId']}", 'model': args.model,
                                    'attempts': attempts, 'verdict': verdict},
                                   ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        with lock:
            done += 1
            print(f"[{done}/{len(todo)}] {entry['exam']}/{entry['questionId']} "
                  f"verdict={verdict and (len(verdict['keep']), len(verdict['demote']))}", flush=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(args.workers, MAX_WORKERS)) as pool:
        list(pool.map(one, todo))
    used = gateway_spend() - meta['startSpend']
    print(f'review gateway spend delta since start: {used:.4f} USD')
    if stop.is_set():
        sys.exit(2)


def cmd_apply_review(args: argparse.Namespace) -> None:
    """Demote reviewed primary blocks to secondary in the curated file."""
    content = load_content_tree(CONTENT_ROOT)
    payload = json.loads(CURATED_PATH.read_text(encoding='utf-8'))
    missing, changed = [], 0
    for entry in payload['questions']:
        if not entry['primary']:
            continue
        path = review_path(args.work_dir, entry)
        verdict = json.loads(path.read_text(encoding='utf-8')).get('verdict') if path.exists() else None
        if verdict is None:
            missing.append(f"{entry['exam']}/{entry['questionId']}")
            continue
        second = review_path(args.work_dir, entry, 2)
        if second.exists():
            other = json.loads(second.read_text(encoding='utf-8')).get('verdict')
            if other and other['demote']:  # either pass demoting is enough
                verdict = {'keep': [x for x in verdict['keep'] if x not in other['demote']],
                           'demote': sorted(set(verdict['demote']) | set(other['demote'])),
                           'gap': other['gap'] or verdict['gap']}
        index = {f'P{i}': ref for i, ref in enumerate(entry['primary'], start=1)}
        demoted = [index[label] for label in sorted(verdict['demote'], key=lambda x: int(x[1:]))]
        if not demoted:
            continue
        changed += 1
        entry['primary'] = [index[label] for label in sorted(verdict['keep'], key=lambda x: int(x[1:]))]
        limit = MAX_SECONDARY if entry['primary'] else MAX_SECONDARY_WHEN_EMPTY
        entry['secondary'] = (demoted + entry['secondary'])[:limit]
        gap = verdict['gap'] or entry['gap']
        if not entry['primary'] and not gap:
            gap = '教材未直接陳述本題解題所需的關鍵事實'
        entry['gap'] = gap
    if missing:
        raise SystemExit(f'{len(missing)} reviews missing: {missing[:10]}')
    payload['method'] = METHOD + '-strict'
    payload['reviewedOn'] = args.date or dt.date.today().isoformat()
    payload['review'] = ('Strict second pass (review subcommand): a primary block stays only when it '
                         'directly states the fact needed for the answer; keyword-only, broader or '
                         'adjacent-concept blocks were demoted to secondary and the missing concept '
                         'recorded in gap.')
    errors = validate_payload(payload, content)
    if errors:
        raise SystemExit('validation failed:\n  ' + '\n  '.join(errors[:40]))
    CURATED_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    write_gaps(payload, payload['reviewedOn'])
    empty = sum(1 for entry in payload['questions'] if not entry['primary'])
    print(f'reviewed: {changed} questions demoted blocks; primary empty={empty}/{len(payload["questions"])}')


def write_gaps(payload: dict[str, Any], today: str) -> None:
    gaps = [{
        'level': e['level'], 'exam': e['exam'], 'questionId': e['questionId'],
        'primaryEmpty': not e['primary'], 'gap': e['gap'],
    } for e in payload['questions'] if e['gap']]
    GAPS_PATH.parent.mkdir(parents=True, exist_ok=True)
    GAPS_PATH.write_text(json.dumps({
        'description': 'Internal list of exam concepts the learning guide does not cover (from '
                       'data/guide_citation_primary.json gap). Not shown in the frontend.',
        'generatedOn': today,
        'source': 'data/guide_citation_primary.json',
        'count': len(gaps),
        'primaryEmpty': sum(1 for gap in gaps if gap['primaryEmpty']),
        'gaps': gaps,
    }, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('prepare', 'run', 'finalize', 'review', 'apply-review'):
        p = sub.add_parser(name)
        p.add_argument('--work-dir', type=Path, required=True)
        p.add_argument('--model', default=DEFAULT_MODEL)
        if name == 'prepare':
            p.add_argument('--exams', nargs='*', help='routeKeys (default: all)')
        if name == 'run':
            p.add_argument('--budget-usd', type=float, default=5.0)
            p.add_argument('--no-budget-check', action='store_true')
            p.add_argument('--workers', type=int, default=MAX_WORKERS)
            p.add_argument('--limit', type=int, default=0)
            p.add_argument('--only', nargs='*', help='item keys exam/questionId')
            p.add_argument('--redo', action='store_true')
        if name in ('finalize', 'apply-review'):
            p.add_argument('--date', help='generatedOn / reviewedOn (default today)')
        if name == 'review':
            p.add_argument('--budget-usd', type=float, default=0.6)
            p.add_argument('--workers', type=int, default=MAX_WORKERS)
            p.add_argument('--limit', type=int, default=0)
            p.add_argument('--redo', action='store_true')
            p.add_argument('--pass', dest='review_pass', type=int, choices=(1, 2), default=1,
                           help='2 = stricter second opinion where pass 1 kept every block')
    args = parser.parse_args()
    args.work_dir = args.work_dir.resolve()
    {'prepare': cmd_prepare, 'run': cmd_run, 'finalize': cmd_finalize, 'review': cmd_review,
     'apply-review': cmd_apply_review}[args.command](args)


if __name__ == '__main__':
    main()
