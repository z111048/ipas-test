#!/usr/bin/env python3
"""Generate detailed Codex reference answers for official exam questions.

The script retrieves only the most relevant guide snippets per question, writes
reviewable prompts, and optionally runs Codex CLI in a read-only sandbox.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BASE = Path('/home/james/projects/ipas-test')
SCHEMA_PATH = BASE / 'schemas' / 'exam_reference_answer.schema.json'
DEFAULT_RUN_ROOT = BASE / 'data' / '中級' / 'pipeline' / 'exam_reference_answers'
EXAM_FILES = {
    'exam1': 'mock_exam1.json',
    'exam2': 'mock_exam2.json',
    'exam3': 'mock_exam3.json',
    'sample': 'sample_exam.json',
}
EXAM_ALIASES = {
    'mock_exam1': 'exam1',
    'mock1': 'exam1',
    'mid1': 'exam1',
    'mock_exam2': 'exam2',
    'mock2': 'exam2',
    'mid2': 'exam2',
    'mock_exam3': 'exam3',
    'mock3': 'exam3',
    'mid3': 'exam3',
    'sample_exam': 'sample',
    'midSample': 'sample',
}
EXAM_GUIDE_KEYS = {
    'exam1': ['guide1'],
    'exam2': ['guide2'],
    'exam3': ['guide3'],
    'sample': ['guide1', 'guide2', 'guide3'],
}


@dataclass
class Chunk:
    guide_key: str
    node_id: str
    title: str
    page_label: str | None
    block_ids: list[str]
    text: str
    tokens: Counter[str]


def load_json(path: Path) -> Any:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def normalize_exam_key(key: str) -> str:
    return EXAM_ALIASES.get(key, key)


def available_exams(level: str) -> list[str]:
    questions_dir = BASE / 'data' / level / 'questions'
    result = []
    for exam_key, file_name in EXAM_FILES.items():
        if (questions_dir / file_name).exists():
            result.append(exam_key)
    return result


def flatten_nodes(nodes: list[dict]) -> list[dict]:
    result = []
    for node in nodes:
        result.append(node)
        result.extend(flatten_nodes(node.get('children') or []))
    return result


def block_to_text(block: dict) -> str:
    block_type = block.get('type')
    if block_type == 'heading':
        return block.get('title') or ''
    if block_type == 'table':
        rows = block.get('rows') or []
        return '\n'.join(' | '.join(str(cell or '').strip() for cell in row) for row in rows)
    return block.get('text') or ''


def tokenize(text: str) -> Counter[str]:
    tokens: list[str] = []
    lowered = text.lower()
    for match in re.finditer(r'[a-zA-Z][a-zA-Z0-9_+-]{1,}|[0-9]+(?:\.[0-9]+)?', lowered):
        tokens.append(match.group(0))
    for segment in re.findall(r'[\u4e00-\u9fff]{2,}', text):
        tokens.extend(segment)
        tokens.extend(segment[index:index + 2] for index in range(len(segment) - 1))
        tokens.extend(segment[index:index + 3] for index in range(len(segment) - 2))
    return Counter(tokens)


def node_title_map(tree: dict) -> dict[str, dict]:
    return {node['id']: node for node in flatten_nodes(tree.get('outline') or [])}


def load_guide_chunks(level: str, guide_keys: list[str], max_chunk_chars: int = 1200) -> list[Chunk]:
    chunks: list[Chunk] = []
    for guide_key in guide_keys:
        tree_path = BASE / 'data' / level / 'guide_tree' / guide_key / 'tree.json'
        blocks_path = BASE / 'data' / level / 'guide_tree' / guide_key / 'blocks.json'
        if not tree_path.exists() or not blocks_path.exists():
            raise FileNotFoundError(
                f'Missing guide_tree for {level}/{guide_key}; run '
                f'python3 scripts/build_guide_tree.py --level {level} --key {guide_key}'
            )
        tree = load_json(tree_path)
        blocks_by_node = load_json(blocks_path)
        nodes = node_title_map(tree)
        for node_id, blocks in blocks_by_node.items():
            node = nodes.get(node_id, {})
            title = node.get('title') or node_id
            page_label = node.get('page_label')
            current: list[str] = []
            block_ids: list[str] = []
            current_chars = 0
            for block in blocks:
                text = block_to_text(block).strip()
                if not text:
                    continue
                entry = f'[{block.get("id")}] {text}'
                if current and current_chars + len(entry) > max_chunk_chars:
                    chunk_text = '\n'.join(current)
                    chunks.append(Chunk(
                        guide_key=guide_key,
                        node_id=node_id,
                        title=title,
                        page_label=page_label,
                        block_ids=block_ids[:],
                        text=chunk_text,
                        tokens=tokenize(f'{title}\n{chunk_text}'),
                    ))
                    current = []
                    block_ids = []
                    current_chars = 0
                current.append(entry)
                if block.get('id'):
                    block_ids.append(block['id'])
                current_chars += len(entry)
            if current:
                chunk_text = '\n'.join(current)
                chunks.append(Chunk(
                    guide_key=guide_key,
                    node_id=node_id,
                    title=title,
                    page_label=page_label,
                    block_ids=block_ids[:],
                    text=chunk_text,
                    tokens=tokenize(f'{title}\n{chunk_text}'),
                ))
    return chunks


def question_text(question: dict) -> str:
    options = question.get('options') or {}
    option_text = '\n'.join(f'{key}. {options.get(key, "")}' for key in ('A', 'B', 'C', 'D'))
    parts = [
        question.get('context') or '',
        question.get('question') or '',
        option_text,
    ]
    for block in question.get('context_blocks') or []:
        parts.append(block.get('markdown') or '')
    return '\n'.join(part for part in parts if part)


def retrieve_chunks(question: dict, chunks: list[Chunk], top_k: int) -> list[tuple[float, Chunk]]:
    query_tokens = tokenize(question_text(question))
    if not query_tokens:
        return []
    scored: list[tuple[float, Chunk]] = []
    query_terms = set(query_tokens)
    for chunk in chunks:
        overlap = query_terms & set(chunk.tokens)
        if not overlap:
            continue
        score = 0.0
        for token in overlap:
            score += min(query_tokens[token], 4) * (1 + min(chunk.tokens[token], 6) ** 0.5)
        answer = question.get('answer')
        answer_text = (question.get('options') or {}).get(answer, '') if answer else ''
        for phrase in re.findall(r'[A-Za-z][A-Za-z0-9_+-]{2,}|[\u4e00-\u9fff]{3,}', answer_text):
            if phrase and phrase.lower() in chunk.text.lower():
                score += 8
        scored.append((score, chunk))
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[:top_k]


def build_prompt(level: str, exam_key: str, exam: dict, question: dict, retrieved: list[tuple[float, Chunk]]) -> str:
    options = question.get('options') or {}
    references = []
    for index, (score, chunk) in enumerate(retrieved, start=1):
        references.append(
            f'### R{index}: {chunk.guide_key} / {chunk.node_id} / {chunk.title}'
            f'{f" / page {chunk.page_label}" if chunk.page_label else ""}\n'
            f'block_ids: {", ".join(chunk.block_ids[:12])}\n'
            f'retrieval_score: {score:.2f}\n'
            f'{chunk.text}'
        )
    reference_text = '\n\n'.join(references) if references else '（檢索未找到明確片段，請只依題目與一般概念作答，並將 confidence 設為 low。）'
    return f"""你是 iPAS AI 應用規劃師考試的詳解編輯。請根據題目、正確答案與「檢索到的學習指引片段」撰寫詳細參考答案。

限制：
- 不要假裝看過未提供的整本學習指引；只能引用下方檢索片段與題目本身。
- 請使用繁體中文。
- 必須維持官方題目的正確答案，不要自行改答案；若你懷疑答案有誤，仍填原 answer，並在 notes 說明。
- reference_answer 要能讓考生理解為何正確答案成立，並連結到學習指引概念。
- option_analysis 必須逐一說明 A/B/C/D 正確或錯誤原因。
- citations 只能使用下方 R1..Rn 中的 guide_key、node_id、title、page_label、block_ids。
- 只輸出符合 JSON schema 的 JSON。

題目資訊：
level: {level}
exam_key: {exam_key}
exam: {exam.get('exam')}
question_id: {question.get('id')}
question: {question.get('question')}
options:
A. {options.get('A')}
B. {options.get('B')}
C. {options.get('C')}
D. {options.get('D')}
official_answer: {question.get('answer')}
current_explanation: {question.get('explanation')}

檢索到的學習指引片段：
{reference_text}
"""


def validate_output(path: Path, level: str, exam_key: str, question: dict) -> list[str]:
    errors = []
    try:
        data = load_json(path)
    except Exception as exc:
        return [f'invalid JSON: {exc}']
    if data.get('level') != level:
        errors.append('level mismatch')
    if data.get('exam_key') != exam_key:
        errors.append('exam_key mismatch')
    if data.get('question_id') != question.get('id'):
        errors.append('question_id mismatch')
    if data.get('answer') != question.get('answer'):
        errors.append('answer must match official answer')
    if not isinstance(data.get('reference_answer'), str) or len(data['reference_answer'].strip()) < 80:
        errors.append('reference_answer too short')
    option_analysis = data.get('option_analysis')
    if not isinstance(option_analysis, dict) or set(option_analysis) != {'A', 'B', 'C', 'D'}:
        errors.append('option_analysis must contain A/B/C/D')
    citations = data.get('citations')
    if not isinstance(citations, list) or not citations:
        errors.append('citations must be a non-empty array')
    return errors


def run_codex(prompt_path: Path, output_path: Path, timeout_seconds: int) -> tuple[bool, bool]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    log_path = output_path.with_suffix('.log')
    err_path = output_path.with_suffix('.err')
    with prompt_path.open(encoding='utf-8') as prompt_file:
        log_file = log_path.open('w', encoding='utf-8')
        err_file = err_path.open('w', encoding='utf-8')
        proc = subprocess.Popen(
            [
                'codex',
                'exec',
                '--cd',
                BASE.as_posix(),
                '--sandbox',
                'read-only',
                '--output-schema',
                SCHEMA_PATH.as_posix(),
                '-o',
                output_path.as_posix(),
                '-',
            ],
            stdin=prompt_file,
            stdout=log_file,
            stderr=err_file,
            text=True,
            cwd=BASE,
            start_new_session=True,
        )
        try:
            proc.wait(timeout=timeout_seconds)
            return proc.returncode == 0 or output_path.exists(), False
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            return output_path.exists(), True
        finally:
            log_file.close()
            err_file.close()


def selected_questions(exam: dict, question_id: str | None, limit: int | None) -> list[dict]:
    questions = exam.get('questions') or []
    if question_id:
        questions = [question for question in questions if question.get('id') == question_id]
        if not questions:
            raise ValueError(f'Question id not found: {question_id}')
    if limit is not None:
        questions = questions[:limit]
    return questions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--level', default='中級')
    parser.add_argument('--exam', default='all', help='exam1, exam2, exam3, sample, or all')
    parser.add_argument('--question-id')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--top-k', type=int, default=8)
    parser.add_argument('--run-root', type=Path)
    parser.add_argument('--run', action='store_true', help='Run Codex CLI after writing prompts')
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--timeout', type=int, default=240)
    args = parser.parse_args()

    level = args.level
    run_root = args.run_root or (BASE / 'data' / level / 'pipeline' / 'exam_reference_answers')
    if not run_root.is_absolute():
        run_root = BASE / run_root

    if args.exam == 'all':
        exam_keys = available_exams(level)
    else:
        exam_keys = [normalize_exam_key(args.exam)]

    if not exam_keys:
        raise SystemExit(f'No exam JSON found for level {level}')

    summary: dict[str, Any] = {
        'level': level,
        'run_root': run_root.relative_to(BASE).as_posix(),
        'schema': SCHEMA_PATH.relative_to(BASE).as_posix(),
        'run_codex': args.run,
        'items': [],
    }
    completed = skipped = failed = prompts = 0

    for exam_key in exam_keys:
        file_name = EXAM_FILES.get(exam_key)
        if not file_name:
            raise SystemExit(f'Unsupported exam key: {exam_key}')
        exam_path = BASE / 'data' / level / 'questions' / file_name
        if not exam_path.exists():
            print(f'SKIP {level}/{exam_key}: missing {exam_path.relative_to(BASE)}')
            continue
        guide_keys = EXAM_GUIDE_KEYS[exam_key]
        if level == '初級':
            guide_keys = [key for key in guide_keys if (BASE / 'data' / level / 'guide_tree' / key).exists()]
            if exam_key == 'sample':
                guide_keys = [subject['key'] for subject in load_json(BASE / 'data' / level / 'toc_manifest.json').get('subjects') or []]
        chunks = load_guide_chunks(level, guide_keys)
        exam = load_json(exam_path)
        for question in selected_questions(exam, args.question_id, args.limit):
            qid = question['id']
            prompt_path = run_root / exam_key / 'prompts' / f'{qid}.md'
            output_path = run_root / exam_key / 'outputs' / f'{qid}.json'
            retrieved = retrieve_chunks(question, chunks, args.top_k)
            prompt_path.parent.mkdir(parents=True, exist_ok=True)
            prompt_path.write_text(build_prompt(level, exam_key, exam, question, retrieved), encoding='utf-8')
            prompts += 1

            item = {
                'exam_key': exam_key,
                'question_id': qid,
                'prompt': prompt_path.relative_to(BASE).as_posix(),
                'output': output_path.relative_to(BASE).as_posix(),
                'retrieved': [
                    {
                        'score': round(score, 2),
                        'guide_key': chunk.guide_key,
                        'node_id': chunk.node_id,
                        'title': chunk.title,
                        'page_label': chunk.page_label,
                        'block_ids': chunk.block_ids[:12],
                    }
                    for score, chunk in retrieved
                ],
            }
            summary['items'].append(item)

            if not args.run:
                print(f'PROMPT {exam_key}/{qid}: {prompt_path.relative_to(BASE)}')
                continue

            if output_path.exists() and not args.force:
                errors = validate_output(output_path, level, exam_key, question)
                if not errors:
                    skipped += 1
                    print(f'SKIP {exam_key}/{qid}: valid output exists')
                    continue

            print(f'RUN {exam_key}/{qid}: {len(retrieved)} snippets')
            ok, timed_out = run_codex(prompt_path, output_path, args.timeout)
            if timed_out:
                print(f'WARN {exam_key}/{qid}: timeout after {args.timeout}s')
            if ok and output_path.exists():
                errors = validate_output(output_path, level, exam_key, question)
                if errors:
                    failed += 1
                    print(f'FAIL {exam_key}/{qid}: ' + '; '.join(errors))
                else:
                    completed += 1
                    print(f'PASS {exam_key}/{qid}')
            else:
                failed += 1
                print(f'FAIL {exam_key}/{qid}: no output')

    summary['stats'] = {
        'prompts': prompts,
        'completed': completed,
        'skipped': skipped,
        'failed': failed,
    }
    write_json(run_root / 'summary.json', summary)
    print(
        f'Done: prompts={prompts}, completed={completed}, skipped={skipped}, failed={failed}, '
        f'summary={(run_root / "summary.json").relative_to(BASE)}'
    )
    if failed:
        raise SystemExit(1)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        raise SystemExit(1)
