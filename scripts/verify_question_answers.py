#!/usr/bin/env python3
"""Cross-check generated question answers by having several AI CLIs answer them blind.

Each verifier gets only the stem and the four options (no explanation, no marked
answer, no repo access) and must return a single letter. Options are shuffled per
question with a deterministic per-id seed, so a verifier cannot ride the generator's
A→B→C→D answer rotation and position bias cancels out.

Questions where enough verifiers disagree with the marked answer land in
flagged.json for human adjudication.

Usage:
  python3 scripts/verify_question_answers.py --run-dir data/中級/pipeline/codex_section_prompts
  python3 scripts/verify_question_answers.py --run-dir ... --chapter mid-s2c3 --limit 10
  # two-stage: cheap gateway sweep, then escalate only what it flagged
  python3 scripts/verify_question_answers.py --run-dir ... --workers 8
  python3 scripts/verify_question_answers.py --run-dir ... --only-flagged --threshold 3 \
      --verifiers codex,claude,claude:sonnet,llm:glm-5.2,llm:deepseek-v4-pro

Verifiers (`tool` or `tool:model`):
  codex           codex exec, --output-schema so the letter comes back as JSON
  claude          claude --print --tools '' (no agentic tools)
  claude:sonnet   same, forced onto a different model for family diversity
  llm:<model>     LiteLLM gateway (llm-share.duotify.com, OpenAI-compatible), e.g.
                  llm:glm-5.2 — open-weight models, no vision needed for this task.
                  Needs LLMSHARE_API_KEY (env, or BASE/.env which is gitignored).

⚠️ `codex` is also the generator, so its agreement is the weakest evidence here.
The report keeps a separate non-generator tally (`wrong_count_excl_codex`).
The gemini CLI is not usable on this machine (Code Assist tier ineligible), so the
`llm:` verifiers are how the roster gets back above two model families.

Calibrating a candidate verifier: run it over a chapter whose answers are already
human-verified and read `wrong_by_verifier` in the report — that count is its error
rate against a known-good key (mid-s2c3's 28 questions are the current baseline).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

BASE = Path('/home/james/projects/ipas-test')
DEFAULT_RUN_DIR = BASE / 'data' / '中級' / 'pipeline' / 'codex_section_prompts'
ANSWER_SCHEMA = BASE / 'schemas' / 'question_answer.schema.json'
# Stage 1 default: gateway models, ~2s each. All three scored 28/28 on the
# human-verified mid-s2c3 baseline. Stage 2 escalates flagged questions to
# codex+claude (~40s each) — see --only-flagged.
DEFAULT_VERIFIERS = 'llm:glm-5.2,llm:deepseek-v4-pro,llm:kimi-k2.7-code'
ESCALATION_VERIFIERS = 'codex,claude,claude:sonnet,llm:glm-5.2,llm:deepseek-v4-pro'
LETTERS = ('A', 'B', 'C', 'D')

GATEWAY_URL = 'https://llm-share.duotify.com/v1/chat/completions'
GATEWAY_MAX_TOKENS = 2048  # reasoning models spend tokens before emitting the letter


def load_env_file() -> None:
    """Pull keys out of BASE/.env (gitignored) without overriding the real env.

    Masked placeholder values (the file ships with ellipsis-truncated keys) are
    skipped so they cannot shadow a properly exported variable.
    """
    env_path = BASE / '.env'
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        value = value.strip().strip('"').strip("'")
        if '…' in value or not value:
            continue
        os.environ.setdefault(key.strip(), value)


def load_json(path: Path) -> Any:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


# ---------------------------------------------------------------------------
# Question loading
# ---------------------------------------------------------------------------

def load_questions(run_dir: Path, chapter: str | None) -> list[dict[str, Any]]:
    """Collect questions from every batch output listed in the run's summary.json."""
    summary = load_json(run_dir / 'summary.json')
    questions: list[dict[str, Any]] = []
    for batch in summary.get('batches', []):
        if chapter and batch.get('chapter_id') != chapter:
            continue
        output_path = BASE / batch['output']
        if not output_path.exists():
            print(f'MISS {batch["output"]}: no output yet')
            continue
        data = load_json(output_path)
        for question in data.get('questions', []):
            if not isinstance(question, dict):
                continue
            options = question.get('options')
            if question.get('answer') not in LETTERS or not isinstance(options, dict):
                print(f'SKIP {question.get("id", "?")}: malformed answer/options')
                continue
            if set(options) != set(LETTERS):
                print(f'SKIP {question.get("id", "?")}: options are not exactly A/B/C/D')
                continue
            question['_batch_index'] = batch.get('batch_index')
            question['_output'] = batch['output']
            questions.append(question)
    return questions


# The `images` field is not a reliable marker: several official questions reference
# a figure or a code block that the OCR never attached ("附圖為某資料之分佈圖",
# options that read "程式碼B" / "見下方選項 B 程式碼"). A text-only verifier cannot
# answer those, and its miss says nothing about the answer key — 4 of the first 5
# consensus flags on the 中級 papers were exactly this.
FIGURE_HINT = re.compile(
    r'附圖|如下圖|下圖|上圖|如圖|右圖|左圖|圖中|下方程式|見下方|如下所示|外觀如下'
    r'|程式碼\s*[A-DＡ-Ｄ]\s*$'
)


def needs_figure(question: dict[str, Any]) -> bool:
    if question.get('images'):
        return True
    haystack = question['question'] + ' ' + ' '.join(question.get('options', {}).values())
    return bool(FIGURE_HINT.search(haystack))


def load_questions_from_files(paths: list[Path], include_image_questions: bool
                              ) -> list[dict[str, Any]]:
    """Load official exam papers (mock_*.json / sample_exam.json).

    These carry authoritative answers, which makes them a far better calibration
    set than generated questions. Figure-dependent items are dropped by default:
    a text-only verifier cannot see the image, so its miss says nothing about the key.
    """
    questions: list[dict[str, Any]] = []
    dropped = 0
    for path in paths:
        full = path if path.is_absolute() else BASE / path
        data = load_json(full)
        items = data['questions'] if isinstance(data, dict) else data
        for question in items:
            if not isinstance(question, dict):
                continue
            options = question.get('options')
            if question.get('answer') not in LETTERS or not isinstance(options, dict) \
                    or set(options) != set(LETTERS):
                print(f'SKIP {question.get("id", "?")}: malformed answer/options')
                continue
            if any(not str(text).strip() for text in options.values()):
                # OCR dropped the option bodies (code-block choices come out empty)
                print(f'SKIP {question.get("id", "?")}: blank option text')
                continue
            if needs_figure(question) and not include_image_questions:
                dropped += 1
                continue
            question['_output'] = full.relative_to(BASE).as_posix()
            questions.append(question)
    if dropped:
        print(f'SKIP {dropped} figure/code-dependent question(s); '
              f'use --include-image-questions to keep them')
    return questions


# ---------------------------------------------------------------------------
# Blind prompt construction
# ---------------------------------------------------------------------------

def shuffled_order(question_id: str) -> list[str]:
    """Deterministic per-question permutation of A/B/C/D (same id → same order)."""
    digest = hashlib.md5(question_id.encode('utf-8')).digest()
    remaining = list(LETTERS)
    order: list[str] = []
    for byte in digest[:4]:
        order.append(remaining.pop(byte % len(remaining)))
    return order


def build_prompt(question: dict[str, Any], order: list[str], level: str) -> str:
    """Stem + shuffled options only — no explanation, tags, difficulty or answer."""
    options = question['options']
    lines = [
        f'以下是一道 iPAS {level} AI 應用規劃師認證考試的單選題。',
        '請只輸出你認為正確的選項字母（A、B、C 或 D），不要加任何解釋或說明。',
        '',
    ]
    context = question.get('context')
    if context:  # official papers put shared stems here (第 41~44 題共用情境)
        lines += [f'共用情境：{context}', '']
    lines.append(f'題目：{question["question"]}')
    for slot, source in zip(LETTERS, order):
        lines.append(f'{slot}. {options[source]}')
    lines += ['', '請只回答一個大寫字母：A、B、C 或 D']
    return '\n'.join(lines)


def extract_letter(text: str | None) -> str | None:
    if not text:
        return None
    match = re.search(r'\b([A-D])\b', text[:200]) or re.search(r'[A-D]', text)
    return match.group(0) if match else None


# ---------------------------------------------------------------------------
# Verifier CLIs — each runs in a throwaway cwd so it cannot read the answer key
# ---------------------------------------------------------------------------

def call_codex(prompt: str, model: str | None, timeout: int) -> str | None:
    with tempfile.TemporaryDirectory() as workdir:
        output_path = Path(workdir) / 'answer.json'
        cmd = ['codex', 'exec', '--cd', workdir, '--skip-git-repo-check',
               '--sandbox', 'read-only',
               '--output-schema', ANSWER_SCHEMA.as_posix(),
               '-o', output_path.as_posix(), '-']
        if model:
            cmd[2:2] = ['-m', model]
        try:
            subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                           timeout=timeout, cwd=workdir)
        except subprocess.TimeoutExpired:
            return None
        if not output_path.exists():
            return None
        try:
            return load_json(output_path).get('answer')
        except (json.JSONDecodeError, AttributeError):
            return None


def call_claude(prompt: str, model: str | None, timeout: int) -> str | None:
    with tempfile.TemporaryDirectory() as workdir:
        cmd = ['claude', '--print', '--dangerously-skip-permissions', '--tools', '']
        if model:
            cmd[2:2] = ['--model', model]
        try:
            result = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                                    timeout=timeout, cwd=workdir)
        except subprocess.TimeoutExpired:
            return None
        if result.returncode != 0:
            return None
        return result.stdout.strip() or None


def call_gateway(prompt: str, model: str | None, timeout: int) -> str | None:
    """LiteLLM gateway (OpenAI-compatible). Key comes from LLMSHARE_API_KEY only."""
    api_key = os.environ.get('LLMSHARE_API_KEY')
    if not api_key or not model:
        return None
    body = json.dumps({
        'model': model,
        'max_tokens': GATEWAY_MAX_TOKENS,
        'messages': [{'role': 'user', 'content': prompt}],
    }).encode('utf-8')
    request = urllib.request.Request(
        GATEWAY_URL, data=body, method='POST',
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    try:
        # Empty content happens when a reasoning model spends its budget on
        # reasoning_content; ask() retries, matching llm-test's llm_client.py.
        return payload['choices'][0]['message'].get('content', '').strip() or None
    except (KeyError, IndexError, TypeError):
        return None


CALLERS = {'codex': call_codex, 'claude': call_claude, 'llm': call_gateway}


def parse_verifiers(spec: str) -> list[tuple[str, str, str | None]]:
    """'codex,claude:sonnet' → [(key, tool, model), ...]"""
    verifiers = []
    for item in spec.split(','):
        key = item.strip()
        if not key:
            continue
        tool, _, model = key.partition(':')
        if tool not in CALLERS:
            raise SystemExit(f'unknown verifier tool: {tool} (available: {", ".join(CALLERS)})')
        if tool == 'llm' and not model:
            raise SystemExit('llm verifiers need a model, e.g. llm:glm-5.2')
        verifiers.append((key, tool, model or None))
    if not verifiers:
        raise SystemExit('no verifiers selected')
    return verifiers


def ask(verifier: tuple[str, str, str | None], prompt: str, timeout: int,
        retries: int) -> str | None:
    _, tool, model = verifier
    for _ in range(retries + 1):
        letter = extract_letter(CALLERS[tool](prompt, model, timeout))
        if letter:
            return letter
    return None


def check_tools(verifiers: list[tuple[str, str, str | None]]) -> None:
    for tool in sorted({tool for _, tool, _ in verifiers}):
        if tool == 'llm':
            if not os.environ.get('LLMSHARE_API_KEY'):
                raise SystemExit(
                    'LLMSHARE_API_KEY not set — export it, or put it in '
                    f'{(BASE / ".env").as_posix()} (gitignored; key only ever lives there). '
                    'CLI-only fallback: --verifiers codex,claude,claude:sonnet'
                )
            continue
        try:
            result = subprocess.run([tool, '--version'], capture_output=True,
                                    text=True, timeout=30)
        except FileNotFoundError:
            raise SystemExit(f'{tool} CLI not found in PATH')
        except subprocess.TimeoutExpired:
            print(f'WARN {tool}: --version timed out, assuming available')
            continue
        if result.returncode != 0:
            raise SystemExit(f'{tool} CLI not usable: {result.stderr.strip()[:200]}')


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def verify_question(question: dict[str, Any], verifiers: list[tuple[str, str, str | None]],
                    level: str, timeout: int, retries: int,
                    cached: dict[str, Any] | None = None) -> dict[str, Any]:
    """Answer with `verifiers`, merging into any cached responses for other verifiers.

    Merging matters: adding a cheap gateway model later must not throw away the
    codex/claude answers already paid for.
    """
    question_id = question['id']
    order = shuffled_order(question_id)
    expected_slot = LETTERS[order.index(question['answer'])]
    prompt = build_prompt(question, order, level)

    responses: dict[str, dict[str, Any]] = dict((cached or {}).get('responses', {}))
    if verifiers:
        with ThreadPoolExecutor(max_workers=len(verifiers)) as executor:
            futures = {
                executor.submit(ask, verifier, prompt, timeout, retries): verifier[0]
                for verifier in verifiers
            }
            for future in as_completed(futures):
                key = futures[future]
                slot = future.result()
                responses[key] = {
                    'slot': slot,
                    'answer': order[LETTERS.index(slot)] if slot else None,
                }

    return {
        'question_id': question_id,
        'chapter_id': question.get('chapter_id'),
        'output': question.get('_output'),
        'question_text': question['question'][:80],
        'expected': question['answer'],
        'shuffled_order': order,
        'expected_slot': expected_slot,
        'responses': responses,
    }


def score(result: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    """Recompute the verdict over just the verifiers requested for this run."""
    responses = {k: r for k, r in result['responses'].items() if k in keys}
    expected_slot = result['expected_slot']
    wrong = [k for k, r in responses.items() if r['slot'] and r['slot'] != expected_slot]
    result['wrong'] = wrong
    result['wrong_count'] = len(wrong)
    result['wrong_count_excl_codex'] = len([k for k in wrong if not k.startswith('codex')])
    result['no_answer'] = [k for k, r in responses.items() if not r['slot']]
    return result


def annotate(result: dict[str, Any]) -> dict[str, Any]:
    """Add triage fields derived from the cached responses.

    When the disagreeing verifiers all pick the *same* wrong letter, that is real
    evidence the marked answer is wrong. When they scatter across different letters
    the question is merely hard — calibration on mid-s2c3 showed exactly this shape
    (q012: codex→B, claude:sonnet→A, marked answer D verified correct by hand).
    """
    wrong_answers = {
        result['responses'][key]['answer'] for key in result['wrong']
    }
    result['wrong_consensus'] = len(wrong_answers) == 1 and len(result['wrong']) > 1
    result['wrong_answers'] = sorted(a for a in wrong_answers if a)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--run-dir', type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument('--questions-file', type=Path, nargs='+', default=None,
                        help='verify official exam papers instead of a generation run '
                             '(data/{level}/questions/mock_*.json) — their answers are '
                             'authoritative, so this measures the verifiers themselves')
    parser.add_argument('--out-dir', type=Path, default=None,
                        help='where verification/ goes (default: alongside --run-dir, or '
                             'data/{level}/pipeline/answer_verification for --questions-file)')
    parser.add_argument('--include-image-questions', action='store_true',
                        help='keep figure-dependent questions (verifiers cannot see images)')
    parser.add_argument('--level', default='中級')
    parser.add_argument('--chapter', default=None, help='only verify one chapter_id')
    parser.add_argument('--only-flagged', action='store_true',
                        help='re-verify just the questions in the existing flagged.json '
                             '(stage 2: escalate the cheap sweep to the CLI verifiers)')
    parser.add_argument('--verifiers', default=DEFAULT_VERIFIERS,
                        help=f'comma-separated tool[:model] (default: {DEFAULT_VERIFIERS})')
    parser.add_argument('--threshold', type=int, default=2,
                        help='verifiers that must disagree before flagging (default: 2)')
    parser.add_argument('--limit', type=int, default=None)
    parser.add_argument('--workers', type=int, default=2,
                        help='questions answered concurrently (default: 2)')
    parser.add_argument('--timeout', type=int, default=180)
    parser.add_argument('--retries', type=int, default=1)
    parser.add_argument('--force', action='store_true', help='ignore cached answers')
    args = parser.parse_args()

    load_env_file()
    verifiers = parse_verifiers(args.verifiers)
    check_tools(verifiers)

    run_dir = args.run_dir if args.run_dir.is_absolute() else BASE / args.run_dir
    if args.out_dir is not None:
        out_dir = args.out_dir if args.out_dir.is_absolute() else BASE / args.out_dir
    elif args.questions_file:
        out_dir = BASE / 'data' / args.level / 'pipeline' / 'answer_verification'
    else:
        out_dir = run_dir / 'verification'
    cache_dir = out_dir / 'answers'

    if args.questions_file:
        questions = load_questions_from_files(args.questions_file,
                                              args.include_image_questions)
    else:
        questions = load_questions(run_dir, args.chapter)
    if args.only_flagged:
        flagged_path = out_dir / 'flagged.json'
        if not flagged_path.exists():
            raise SystemExit(f'--only-flagged needs {flagged_path.relative_to(BASE)}')
        wanted = {item['verification']['question_id']
                  for item in load_json(flagged_path).get('items', [])}
        questions = [q for q in questions if q['id'] in wanted]
        print(f'ONLY-FLAGGED {len(questions)} question(s) from the previous stage')
        if not questions:
            print('Nothing to escalate — the previous stage flagged nothing.')
            return
    if args.limit is not None:
        questions = questions[:args.limit]
    if not questions:
        raise SystemExit('no questions to verify')

    keys = [key for key, _, _ in verifiers]
    print(f'Verifying {len(questions)} question(s) with {", ".join(keys)} '
          f'(threshold={args.threshold}, workers={args.workers})')

    pending: list[tuple[dict[str, Any], list, dict | None]] = []
    results: dict[str, dict[str, Any]] = {}
    for question in questions:
        cache_path = cache_dir / f'{question["id"]}.json'
        cached = load_json(cache_path) if cache_path.exists() else None
        if cached and args.force:
            cached = None
        done_keys = set((cached or {}).get('responses', {}))
        missing = [v for v in verifiers if v[0] not in done_keys]
        if cached and not missing:
            results[question['id']] = cached
            continue
        pending.append((question, missing, cached))

    if results:
        print(f'CACHE {len(results)} question(s) already verified (use --force to redo)')
    partial = sum(1 for _, missing, cached in pending if cached and len(missing) < len(verifiers))
    if partial:
        print(f'TOPUP {partial} question(s) only need the new verifier(s)')

    def work(item: tuple[dict[str, Any], list, dict | None]) -> dict[str, Any]:
        question, missing, cached = item
        result = verify_question(question, missing, args.level, args.timeout,
                                 args.retries, cached)
        save_json(cache_dir / f'{question["id"]}.json', result)
        return result

    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(work, item): item[0]['id'] for item in pending}
        for future in as_completed(futures):
            result = score(future.result(), keys)
            results[result['question_id']] = result
            done += 1
            status = 'FLAG' if result['wrong_count'] >= args.threshold else (
                'WARN' if result['wrong_count'] or result['no_answer'] else 'OK')
            detail = ' '.join(
                f'{k}={result["responses"][k]["answer"] or "-"}'
                for k in keys if k in result['responses'])
            print(f'{status:4} [{done}/{len(pending)}] {result["question_id"]} '
                  f'expected={result["expected"]} {detail}')

    ordered = [annotate(score(results[q['id']], keys))
               for q in questions if q['id'] in results]
    flagged = [r for r in ordered if r['wrong_count'] >= args.threshold]
    consensus_flagged = [r for r in flagged if r['wrong_consensus']]
    disagreed = [r for r in ordered if 0 < r['wrong_count'] < args.threshold]
    incomplete = [r for r in ordered if r['no_answer']]

    per_verifier = {
        key: sum(1 for r in ordered if key in r['wrong'])
        for key in keys
    }
    report = {
        'source': ([p.as_posix() for p in args.questions_file] if args.questions_file
                   else run_dir.relative_to(BASE).as_posix()),
        'level': args.level,
        'chapter': args.chapter,
        'verifiers': keys,
        'threshold': args.threshold,
        'total': len(ordered),
        'flagged_count': len(flagged),
        'flagged_consensus_count': len(consensus_flagged),
        'disagreement_only_count': len(disagreed),
        'incomplete_count': len(incomplete),
        'wrong_by_verifier': per_verifier,
        'results': ordered,
    }
    # Stage 2 keeps its own files so the full sweep's report is not clobbered.
    suffix = '_stage2' if args.only_flagged else ''
    report_path = out_dir / f'report{suffix}.json'
    flagged_path_out = out_dir / f'flagged{suffix}.json'
    save_json(report_path, report)

    by_id = {q['id']: q for q in questions}
    save_json(flagged_path_out, {
        'source': report['source'],
        'threshold': args.threshold,
        'flagged_count': len(flagged),
        'flagged_consensus_count': len(consensus_flagged),
        'items': [
            {
                'verification': r,
                'question': {k: v for k, v in by_id[r['question_id']].items()
                             if not k.startswith('_')},
            }
            for r in flagged
        ],
    })

    print(f'\nDone: total={len(ordered)}, flagged={len(flagged)} '
          f'(of which wrong-votes-agree={len(consensus_flagged)}, review these first), '
          f'below-threshold-disagreement={len(disagreed)}, no-answer={len(incomplete)}')
    print(f'Wrong by verifier: {per_verifier}')
    print(f'Report: {report_path.relative_to(BASE)}')
    print(f'Flagged: {flagged_path_out.relative_to(BASE)}')
    raise SystemExit(1 if flagged else 0)


if __name__ == '__main__':
    main()
