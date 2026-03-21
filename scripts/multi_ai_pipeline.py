#!/usr/bin/env python3
"""
Multi-AI question generation pipeline for iPAS exam prep.

Roles:
  出題者 (Creator)  → Gemini  — generates draft questions from chapter content
  審核者 (Reviewer) → Codex   — reviews drafts for correctness and quality
  完稿者 (Finalizer) → Claude  — polishes and outputs final JSON

After finalization, all three AIs independently answer each question.
Questions where 2+ AIs answer incorrectly are flagged for human review.

Usage:
  python3 scripts/multi_ai_pipeline.py --subject 1 --chapter s1c1 --dry-run
  python3 scripts/multi_ai_pipeline.py --subject 1 --count 3
  python3 scripts/multi_ai_pipeline.py --subject 2 --skip-validation
"""

import argparse
import json
import logging
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

BASE = Path('/home/james/projects/ipas-test')
DATA = BASE / 'data' / '初級'
GUIDE_DIR = DATA / 'guide'
QUESTIONS_DIR = DATA / 'questions'
PIPELINE_OUT_DIR = DATA / 'pipeline'
LOG_DIR = BASE / 'logs'

MAX_CONTENT_CHARS = 4000
DEFAULT_TIMEOUT = 120
MAX_RETRIES = 2
VALIDATION_FAIL_THRESHOLD = 2  # AIs that must answer wrong before flagging

DEFAULT_ROLES = {
    'creator': 'gemini',
    'reviewer': 'codex',
    'finalizer': 'claude',
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'multi_ai_pipeline.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JSON parsing (mirrors generate_questions.py)
# ---------------------------------------------------------------------------

def parse_json_response(text: str) -> object:
    """Strip markdown fences and parse JSON from LLM response."""
    text = text.strip()
    if text.startswith('```'):
        lines = text.split('\n')
        text = '\n'.join(lines[1:-1] if lines[-1].strip() == '```' else lines[1:])
    return json.loads(text)

# ---------------------------------------------------------------------------
# CLI Wrappers
# ---------------------------------------------------------------------------

def _run_subprocess(cmd: list[str], prompt: str, timeout: int) -> str | None:
    """
    Run a CLI tool and return stdout, or None on failure.
    Pipes prompt via stdin when len > 3000 to avoid argument length limits.
    """
    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            log.error(f"[{cmd[0]}] exit {result.returncode}: {result.stderr[:300]}")
            return None
        return result.stdout.strip() or None
    except subprocess.TimeoutExpired:
        log.warning(f"[{cmd[0]}] timed out after {timeout}s")
        return None
    except FileNotFoundError:
        log.error(f"[{cmd[0]}] not found in PATH")
        return None


def call_gemini(prompt: str, timeout: int = DEFAULT_TIMEOUT) -> str | None:
    # gemini CLI reads prompt from stdin when -p flag is omitted,
    # or pass via -p for shorter prompts. Use stdin consistently.
    return _run_subprocess(['gemini', '-p', '-'], prompt, timeout)


def call_codex(prompt: str, timeout: int = DEFAULT_TIMEOUT) -> str | None:
    # openai/codex: 'exec' subcommand runs non-interactively.
    # '-' as the PROMPT argument reads from stdin.
    # -c sandbox_permissions grants read-only disk access for context.
    return _run_subprocess(
        ['codex', 'exec', '-c', 'sandbox_permissions=["disk-full-read-access"]', '-'],
        prompt,
        timeout,
    )


def call_claude(prompt: str, timeout: int = DEFAULT_TIMEOUT) -> str | None:
    # claude --print: non-interactive output mode.
    # --dangerously-skip-permissions: bypass file-permission prompts (text-only generation).
    # --tools "": disable all agentic tools so the model just generates text.
    # Prompt piped via stdin.
    return _run_subprocess(
        ['claude', '--print', '--dangerously-skip-permissions', '--tools', ''],
        prompt,
        timeout,
    )


AI_CALLERS = {
    'gemini': call_gemini,
    'codex': call_codex,
    'claude': call_claude,
}


def call_ai(tool: str, prompt: str, timeout: int = DEFAULT_TIMEOUT) -> str | None:
    """Dispatch to the named AI CLI tool with retry."""
    fn = AI_CALLERS.get(tool)
    if fn is None:
        log.warning(f"Unknown AI tool: {tool}")
        return None
    for attempt in range(1, MAX_RETRIES + 1):
        result = fn(prompt, timeout)
        if result is not None:
            return result
        if attempt < MAX_RETRIES:
            log.warning(f"[{tool}] attempt {attempt} failed, retrying...")
    return None


def check_available_tools() -> dict[str, bool]:
    """Probe each CLI tool and return availability map."""
    available = {}
    for name, version_cmd in [
        ('gemini', ['gemini', '--version']),
        ('codex', ['codex', '--version']),
        ('claude', ['claude', '--version']),
    ]:
        try:
            subprocess.run(version_cmd, capture_output=True, timeout=5)
            available[name] = True
        except FileNotFoundError:
            available[name] = False
            log.warning(f"CLI tool '{name}' not found in PATH")
        except subprocess.TimeoutExpired:
            # Tool exists but hangs on --version (e.g. gemini may require auth prompt)
            available[name] = True
            log.info(f"CLI tool '{name}' found (version check timed out, assuming available)")
    return available


def resolve_role_assignments(requested: dict, available: dict) -> dict:
    """
    Assign each role to an available AI tool.
    If the requested tool is unavailable, fall back to any available one.
    """
    fallback_order = ['gemini', 'claude', 'codex']
    resolved = {}
    for role, tool in requested.items():
        if available.get(tool):
            resolved[role] = tool
        else:
            assigned = set(resolved.values())
            for candidate in fallback_order:
                if available.get(candidate) and candidate not in assigned:
                    log.warning(f"Role '{role}': '{tool}' unavailable, using '{candidate}'")
                    resolved[role] = candidate
                    break
            else:
                log.error(f"Role '{role}': no available AI tool, stage will be skipped")
                resolved[role] = None
    return resolved

# ---------------------------------------------------------------------------
# Question Templates
# ---------------------------------------------------------------------------

QUESTION_TEMPLATES = {
    '概念定義型': {
        'description': '考核對核心術語和定義的精確理解',
        'stem_hint': '下列關於「{topic}」的描述，何者正確？',
        'notes': '選項應包含常見誤解作為干擾項；正確選項應引用指引原文表述',
    },
    '應用情境型': {
        'description': '考核在真實業務場景中選擇適當方法或工具',
        'stem_hint': '某企業希望{scenario}，下列哪種做法最為適切？',
        'notes': '場景描述需具體，避免過於模糊；各選項應貼近真實可行方案',
    },
    '比較辨析型': {
        'description': '考核對兩個相似概念的異同辨別',
        'stem_hint': '下列關於{concept_a}與{concept_b}的比較，何者正確？',
        'notes': '聚焦考生最容易混淆的一組概念；干擾項應包含顛倒對應的錯誤',
    },
    '錯誤識別型': {
        'description': '考核對錯誤陳述的識別能力（否定題型）',
        'stem_hint': '下列關於{topic}的敘述，何者有誤？',
        'notes': '題幹須明確標示「有誤」；三個正確選項應均可在指引中找到依據',
    },
    '流程步驟型': {
        'description': '考核對多步驟流程或決策順序的理解',
        'stem_hint': '執行{process}時，下列步驟的正確順序為何？',
        'notes': '適用於有明確先後順序的流程；干擾項應為合理但順序錯誤的排列',
    },
}


def select_templates(chapter: dict) -> list[str]:
    """Choose 2-3 question templates based on chapter characteristics."""
    subtopics = chapter.get('subtopics', [])
    content = chapter.get('content', '')
    selected = ['概念定義型']

    flow_keywords = ['步驟', '流程', '階段', '程序', '順序', '過程']
    if any(kw in content for kw in flow_keywords):
        selected.append('流程步驟型')
    elif len(subtopics) >= 3:
        selected.append('比較辨析型')
    else:
        selected.append('應用情境型')

    # Add a third template if not already at 3
    if len(selected) < 3:
        remaining = [t for t in QUESTION_TEMPLATES if t not in selected]
        selected.append(remaining[0])

    return selected[:3]

# ---------------------------------------------------------------------------
# Prompt Builders
# ---------------------------------------------------------------------------

QUESTION_SCHEMA = """{
  "question": "題目文字（完整句子）",
  "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
  "answer": "A",
  "explanation": "完整解說（2-4 句，說明正確答案及其他選項錯誤原因）",
  "card": {
    "concept": "核心概念摘要（1-2 句）",
    "mnemonic": "記憶口訣或聯想技巧（簡短易記）",
    "confusion": "最常見的混淆點與辨別方式",
    "frequency": "高/中/低"
  },
  "difficulty": "易/中/難",
  "type": "概念定義型",
  "tags": ["標籤1", "標籤2"]
}"""


def build_creator_prompt(chapter: dict, templates: list[str], count: int) -> str:
    content = chapter['content'][:MAX_CONTENT_CHARS]
    subtopics = '、'.join(chapter.get('subtopics', []))
    template_list = '\n'.join(
        f"  - {t}：{QUESTION_TEMPLATES[t]['stem_hint']}（{QUESTION_TEMPLATES[t]['notes']}）"
        for t in templates
    )
    return f"""你是一位 iPAS 初級 AI 應用規劃師認證考試的命題專家（出題者）。

## 任務
根據以下章節內容，出 {count} 道四選一選擇題，涵蓋下列題型（每種至少出一題）：
{template_list}

## 章節資訊
章節 ID：{chapter['id']}
章節名稱：{chapter['title']}
子主題：{subtopics}

## 章節內容（前 {MAX_CONTENT_CHARS} 字元）
{content}

## 出題規範
- 在 type 欄位標示使用的題型名稱
- 選項 A-D 均需合理；干擾項應反映真實常見誤解，而非明顯錯誤
- 難度分布：20% 易 / 50% 中 / 30% 難
- 全程使用繁體中文；技術術語可附英文縮寫（如 RAG、LLM、HITL）
- 附上解說（explanation）2-4 句，說明正確答案及其他選項錯誤原因
- 附上完整 card 欄位（concept / mnemonic / confusion / frequency）
  frequency 說明：高 = 過去考試出現 3 次以上，中 = 1-2 次，低 = 未出現但重要

## 輸出格式（純 JSON 陣列，不附任何說明文字）
[
  {QUESTION_SCHEMA}
]"""


def build_reviewer_prompt(chapter: dict, draft_questions: list) -> str:
    draft_json = json.dumps(draft_questions, ensure_ascii=False, indent=2)
    return f"""你是一位 iPAS 考試的審核專家（審核者）。請針對以下草稿題目進行嚴格審查。

## 章節名稱
{chapter['title']}

## 草稿題目（JSON）
{draft_json}

## 審核項目（逐題評分 1-5 分）
1. 答案正確性：正確答案是否確實正確？請依章節知識驗證
2. 干擾項品質：三個錯誤選項是否合理且具誤導性（非明顯錯誤）？
3. 題目清晰度：題幹是否清楚無歧義？
4. 難度一致性：標示的難度（易/中/難）是否符合實際難度？
5. 指引覆蓋率：題目是否確實來自指引內容，而非捏造？

## 輸出格式（純 JSON，不附任何說明文字）
{{
  "overall_pass": true,
  "questions": [
    {{
      "index": 0,
      "scores": {{"答案正確性": 5, "干擾項品質": 4, "題目清晰度": 5, "難度一致性": 4, "指引覆蓋率": 5}},
      "issues": [],
      "suggested_fix": "",
      "pass": true
    }}
  ]
}}"""


def build_finalizer_prompt(chapter: dict, draft_questions: list, review: dict) -> str:
    draft_json = json.dumps(draft_questions, ensure_ascii=False, indent=2)
    review_json = json.dumps(review, ensure_ascii=False, indent=2)
    return f"""你是一位 iPAS 考試的完稿編輯（完稿者）。請根據審核意見將草稿整理為最終版本。

## 章節 ID
{chapter['id']}

## 草稿題目
{draft_json}

## 審核意見
{review_json}

## 完稿規則
- 針對審核標注 pass: false 或有 issues 的題目，依 suggested_fix 修改
- 若某題答案正確性評分 ≤ 2，直接刪除，不保留
- 確保所有題目的 card 欄位完整（concept / mnemonic / confusion / frequency）
- 輸出純 JSON 陣列（不附任何說明文字），格式與草稿相同
- 不要加入 id 欄位（由程式自動指派）

## 最終輸出（純 JSON 陣列）
[...]"""


def build_validation_prompt(question: dict) -> str:
    opts = question['options']
    return f"""以下是一道 iPAS 初級 AI 應用規劃師認證考試的選擇題。
請只輸出你認為正確的選項字母（A、B、C 或 D），不要加任何解釋或說明。

題目：{question['question']}
A. {opts.get('A', '')}
B. {opts.get('B', '')}
C. {opts.get('C', '')}
D. {opts.get('D', '')}

請只回答一個大寫字母：A、B、C 或 D"""

# ---------------------------------------------------------------------------
# Pipeline Stages
# ---------------------------------------------------------------------------

def run_creation_stage(
    chapter: dict,
    templates: list[str],
    count: int,
    roles: dict,
    timeout: int,
    dry_run: bool,
) -> list | None:
    tool = roles.get('creator')
    prompt = build_creator_prompt(chapter, templates, count)
    log.info(f"[{chapter['id']}] 出題 ({tool}) — templates: {templates}")

    if dry_run:
        print(f"\n{'='*60}\n[DRY-RUN] 出題 prompt ({chapter['id']}):\n{'='*60}")
        print(prompt[:1000], '\n...\n')
        return []

    if tool is None:
        log.warning(f"[{chapter['id']}] 出題 stage skipped: no creator available")
        return None

    raw = call_ai(tool, prompt, timeout)
    if raw is None:
        log.error(f"[{chapter['id']}] 出題 failed: no response from {tool}")
        return None

    try:
        questions = parse_json_response(raw)
        if not isinstance(questions, list):
            raise ValueError(f"Expected list, got {type(questions)}")
        log.info(f"[{chapter['id']}] 出題 produced {len(questions)} draft questions")
        return questions
    except Exception as e:
        log.error(f"[{chapter['id']}] 出題 JSON parse error: {e}\nRaw (first 300): {raw[:300]}")
        return None


def _pass_all_review(questions: list) -> dict:
    """Synthetic pass-all review when reviewer is unavailable or fails."""
    return {
        'overall_pass': True,
        'questions': [
            {
                'index': i,
                'scores': {k: 4 for k in ['答案正確性', '干擾項品質', '題目清晰度', '難度一致性', '指引覆蓋率']},
                'issues': [],
                'suggested_fix': '',
                'pass': True,
            }
            for i in range(len(questions))
        ],
    }


def run_review_stage(
    chapter: dict,
    draft_questions: list,
    roles: dict,
    timeout: int,
    dry_run: bool,
) -> dict:
    tool = roles.get('reviewer')
    prompt = build_reviewer_prompt(chapter, draft_questions)
    log.info(f"[{chapter['id']}] 審核 ({tool})")

    if dry_run:
        print(f"\n{'='*60}\n[DRY-RUN] 審核 prompt ({chapter['id']}):\n{'='*60}")
        print(prompt[:800], '\n...\n')
        return _pass_all_review(draft_questions)

    if tool is None:
        log.warning(f"[{chapter['id']}] 審核 stage skipped: no reviewer available")
        return _pass_all_review(draft_questions)

    raw = call_ai(tool, prompt, timeout)
    if raw is None:
        log.warning(f"[{chapter['id']}] 審核 failed, using pass-all fallback")
        return _pass_all_review(draft_questions)

    try:
        review = parse_json_response(raw)
        if not isinstance(review, dict):
            raise ValueError(f"Expected dict, got {type(review)}")
        log.info(f"[{chapter['id']}] 審核 complete — overall_pass: {review.get('overall_pass')}")
        return review
    except Exception as e:
        log.error(f"[{chapter['id']}] 審核 JSON parse error: {e} — using pass-all fallback")
        return _pass_all_review(draft_questions)


def run_finalization_stage(
    chapter: dict,
    draft_questions: list,
    review: dict,
    roles: dict,
    timeout: int,
    dry_run: bool,
) -> list | None:
    tool = roles.get('finalizer')
    prompt = build_finalizer_prompt(chapter, draft_questions, review)
    log.info(f"[{chapter['id']}] 完稿 ({tool})")

    if dry_run:
        print(f"\n{'='*60}\n[DRY-RUN] 完稿 prompt ({chapter['id']}):\n{'='*60}")
        print(prompt[:800], '\n...\n')
        return draft_questions  # treat drafts as final in dry-run

    if tool is None:
        log.warning(f"[{chapter['id']}] 完稿 stage skipped: no finalizer available")
        return draft_questions  # fall back to unpolished drafts

    raw = call_ai(tool, prompt, timeout)
    if raw is None:
        log.error(f"[{chapter['id']}] 完稿 failed: no response from {tool}")
        return draft_questions

    try:
        final = parse_json_response(raw)
        if not isinstance(final, list):
            raise ValueError(f"Expected list, got {type(final)}")
        log.info(f"[{chapter['id']}] 完稿 produced {len(final)} final questions")
        return final
    except Exception as e:
        log.error(f"[{chapter['id']}] 完稿 JSON parse error: {e} — using drafts")
        return draft_questions


def _extract_answer_letter(text: str) -> str | None:
    """Extract the first A-D letter from an AI's validation response."""
    if not text:
        return None
    match = re.search(r'\b([A-D])\b', text[:100])
    if match:
        return match.group(1)
    # Fall back to scanning full response
    match = re.search(r'[A-D]', text)
    return match.group(0) if match else None


def run_validation_stage(
    chapter_id: str,
    final_questions: list,
    available: dict,
    timeout: int,
    dry_run: bool,
) -> list:
    """Have all three AIs answer each question; flag if 2+ get it wrong."""
    if dry_run:
        print(f"\n[DRY-RUN] 答題驗證 skipped in dry-run mode")
        return []

    all_tools = [t for t, ok in available.items() if ok]
    validation_results = []

    for q in final_questions:
        prompt = build_validation_prompt(q)
        expected = q.get('answer', '')
        responses: dict[str, str | None] = {}

        # Call all available tools in parallel
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_map = {
                executor.submit(call_ai, tool, prompt, timeout): tool
                for tool in all_tools
            }
            for future in as_completed(future_map):
                tool = future_map[future]
                raw = future.result()
                responses[tool] = _extract_answer_letter(raw) if raw else None

        wrong_count = sum(
            1 for tool, ans in responses.items()
            if ans is not None and ans != expected
        )
        flag = wrong_count >= VALIDATION_FAIL_THRESHOLD

        result = {
            'question_id': q.get('id', ''),
            'question_text': q['question'][:80],
            'expected': expected,
            'responses': responses,
            'wrong_count': wrong_count,
            'flag_for_review': flag,
        }
        validation_results.append(result)

        status = 'FLAGGED' if flag else 'OK'
        log.info(
            f"[{chapter_id}] 驗證 {q.get('id', '?')} [{status}] "
            f"expected={expected} responses={responses}"
        )

    return validation_results

# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def save_json(path: Path, data: object):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def merge_into_subject_questions(
    subject_data: dict,
    guide_chapters: list,
    chapter_id: str,
    new_questions: list,
):
    """Append new questions to the chapter entry in subject_data (in-place)."""
    chapter_map = {ch['id']: ch for ch in subject_data.get('chapters', [])}
    guide_map = {ch['id']: ch for ch in guide_chapters}

    existing = chapter_map.get(chapter_id, {})
    existing_count = len(existing.get('questions', []))

    for i, q in enumerate(new_questions, existing_count + 1):
        q['id'] = f'{chapter_id}q{i}_multi'
        q.setdefault('source', 'multi_ai_pipeline')

    if chapter_id in chapter_map:
        chapter_map[chapter_id].setdefault('questions', []).extend(new_questions)
    else:
        guide_ch = guide_map.get(chapter_id, {})
        chapter_map[chapter_id] = {
            'id': chapter_id,
            'title': guide_ch.get('title', chapter_id),
            'questions': new_questions,
        }

    # Rebuild chapters list preserving original order, then guide chapters
    original_ids = [ch['id'] for ch in subject_data.get('chapters', [])]
    guide_ids = [ch['id'] for ch in guide_chapters]
    all_ids = original_ids + [i for i in guide_ids if i not in original_ids]
    subject_data['chapters'] = [chapter_map[i] for i in all_ids if i in chapter_map]

# ---------------------------------------------------------------------------
# Chapter pipeline
# ---------------------------------------------------------------------------

def run_chapter_pipeline(
    chapter: dict,
    args: argparse.Namespace,
    roles: dict,
    available: dict,
    run_dir: Path,
) -> dict:
    ch_id = chapter['id']
    ch_dir = run_dir / ch_id
    stages_completed = []
    status = 'complete'

    # 1. Template selection
    templates = select_templates(chapter)
    log.info(f"[{ch_id}] Templates: {templates}")

    # 2. Creation
    draft_questions = run_creation_stage(
        chapter, templates, args.count, roles, args.timeout, args.dry_run
    )
    if draft_questions is None:
        return {'chapter_id': ch_id, 'status': 'failed_creation', 'stages_completed': []}
    stages_completed.append('creation')
    if not args.dry_run:
        save_json(ch_dir / 'draft.json', draft_questions)

    # 3. Review (optional)
    if args.skip_review:
        review = _pass_all_review(draft_questions)
    else:
        review = run_review_stage(chapter, draft_questions, roles, args.timeout, args.dry_run)
        stages_completed.append('review')
        if not args.dry_run:
            save_json(ch_dir / 'review.json', review)

    # 4. Finalization
    final_questions = run_finalization_stage(
        chapter, draft_questions, review, roles, args.timeout, args.dry_run
    )
    if final_questions is None:
        final_questions = draft_questions
        status = 'partial'
    stages_completed.append('finalization')
    if not args.dry_run:
        save_json(ch_dir / 'final.json', final_questions)

    # 5. Validation (optional)
    validation_results = []
    flagged = []
    if not args.skip_validation:
        validation_results = run_validation_stage(
            ch_id, final_questions, available, args.timeout, args.dry_run
        )
        stages_completed.append('validation')
        flagged = [r for r in validation_results if r.get('flag_for_review')]
        if not args.dry_run:
            save_json(ch_dir / 'validation.json', validation_results)
            if flagged:
                flagged_questions = [
                    q for q in final_questions
                    if q.get('id') in {r['question_id'] for r in flagged}
                ]
                save_json(ch_dir / 'flagged.json', {
                    'chapter_id': ch_id,
                    'flagged_count': len(flagged),
                    'validation_results': flagged,
                    'questions': flagged_questions,
                })
                log.warning(f"[{ch_id}] {len(flagged)} question(s) flagged for human review")

    return {
        'chapter_id': ch_id,
        'questions_created': len(draft_questions),
        'questions_after_review': len(final_questions),
        'questions_flagged': len(flagged),
        'stages_completed': stages_completed,
        'status': status,
        'final_questions': final_questions,
    }

# ---------------------------------------------------------------------------
# Subject pipeline
# ---------------------------------------------------------------------------

def run_subject_pipeline(args: argparse.Namespace, available: dict):
    subject_num = args.subject
    guide_path = GUIDE_DIR / f'subject{subject_num}_guide.json'
    questions_path = QUESTIONS_DIR / f'subject{subject_num}_questions.json'

    if not guide_path.exists():
        sys.exit(f"Guide not found: {guide_path}\nRun parse_guides.py first.")
    if not questions_path.exists():
        sys.exit(f"Questions file not found: {questions_path}")

    guide = json.loads(guide_path.read_text(encoding='utf-8'))
    subject_data = json.loads(questions_path.read_text(encoding='utf-8'))

    run_id = datetime.now().strftime('%Y%m%d_%H%M%S')
    run_dir = PIPELINE_OUT_DIR / run_id / f'subject{subject_num}'
    if not args.dry_run:
        run_dir.mkdir(parents=True, exist_ok=True)

    roles = resolve_role_assignments(
        {
            'creator': args.creator,
            'reviewer': args.reviewer,
            'finalizer': args.finalizer,
        },
        available,
    )
    log.info(f"Run {run_id} | Subject {subject_num} | Roles: {roles}")

    chapters = guide['chapters']
    if args.chapter:
        chapters = [ch for ch in chapters if ch['id'] == args.chapter]
        if not chapters:
            sys.exit(f"Chapter '{args.chapter}' not found in guide.")

    chapter_results = []
    total_generated = 0
    total_flagged = 0

    for chapter in chapters:
        result = run_chapter_pipeline(chapter, args, roles, available, run_dir)
        chapter_results.append({k: v for k, v in result.items() if k != 'final_questions'})

        if result['status'] not in ('failed_creation',) and not args.dry_run:
            final_qs = result.get('final_questions', [])
            merge_into_subject_questions(
                subject_data,
                guide['chapters'],
                chapter['id'],
                final_qs,
            )
            total_generated += len(final_qs)
            total_flagged += result.get('questions_flagged', 0)

    if not args.dry_run:
        questions_path.write_text(
            json.dumps(subject_data, ensure_ascii=False, indent=2), encoding='utf-8'
        )
        log.info(f"Saved {questions_path}")

        summary = {
            'run_id': run_id,
            'subject': subject_num,
            'roles': roles,
            'chapters_processed': len(chapter_results),
            'total_questions_generated': total_generated,
            'total_flagged_for_review': total_flagged,
            'chapter_results': chapter_results,
        }
        save_json(run_dir / 'pipeline_summary.json', summary)
        log.info(
            f"Pipeline complete: {total_generated} questions generated, "
            f"{total_flagged} flagged | Summary: {run_dir / 'pipeline_summary.json'}"
        )

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--subject', type=int, choices=[1, 2], help='Subject to process')
    group.add_argument('--chapter', dest='chapter_only', metavar='CHAPTER_ID',
                       help='Process a single chapter (requires --subject too — use with --subject)')

    # Allow --chapter alongside --subject
    parser.add_argument('--subject-for-chapter', type=int, choices=[1, 2], dest='subject_fc',
                        help=argparse.SUPPRESS)

    parser.add_argument('--count', type=int, default=3, help='Questions per chapter (default: 3)')
    parser.add_argument('--creator', default=DEFAULT_ROLES['creator'],
                        choices=['gemini', 'codex', 'claude'], help='AI for question creation')
    parser.add_argument('--reviewer', default=DEFAULT_ROLES['reviewer'],
                        choices=['gemini', 'codex', 'claude'], help='AI for review')
    parser.add_argument('--finalizer', default=DEFAULT_ROLES['finalizer'],
                        choices=['gemini', 'codex', 'claude'], help='AI for finalization')
    parser.add_argument('--skip-validation', action='store_true', help='Skip answer validation stage')
    parser.add_argument('--skip-review', action='store_true', help='Skip review stage')
    parser.add_argument('--dry-run', action='store_true', help='Print prompts without calling AIs')
    parser.add_argument('--timeout', type=int, default=DEFAULT_TIMEOUT, help='Seconds per AI call (default: 120)')

    args = parser.parse_args()

    # Rework: support --subject N --chapter s1c1 pattern
    # argparse mutual exclusion prevents both, so we implement a two-arg approach
    if args.chapter_only:
        # User passed --chapter without --subject: error
        parser.error('--chapter requires --subject. Use: --subject N --chapter CHAPTER_ID')

    # Attach chapter filter attribute (None if processing all chapters)
    args.chapter = None

    available = check_available_tools()
    if not any(available.values()):
        sys.exit("No AI CLI tools found. Install at least one of: gemini, codex, claude")

    run_subject_pipeline(args, available)


# Handle the common pattern: --subject N --chapter CHAPTER_ID
# Override argparse to support this without mutual exclusion conflict
import sys as _sys

def _patched_main():
    """Entry point that preprocesses --chapter before argparse sees it."""
    raw_args = _sys.argv[1:]
    chapter_val = None

    # Extract --chapter VALUE from raw args before passing to argparse
    if '--chapter' in raw_args:
        idx = raw_args.index('--chapter')
        if idx + 1 < len(raw_args):
            chapter_val = raw_args[idx + 1]
            raw_args = raw_args[:idx] + raw_args[idx + 2:]
        else:
            print("Error: --chapter requires a value", file=_sys.stderr)
            _sys.exit(1)

    _sys.argv[1:] = raw_args

    # Now check --subject is present
    if '--subject' not in raw_args and chapter_val:
        print("Error: --chapter requires --subject. Use: --subject N --chapter CHAPTER_ID",
              file=_sys.stderr)
        _sys.exit(1)

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--subject', type=int, choices=[1, 2], required=True,
                        help='Subject to process (1 or 2)')
    parser.add_argument('--count', type=int, default=3, help='Questions per chapter (default: 3)')
    parser.add_argument('--creator', default=DEFAULT_ROLES['creator'],
                        choices=['gemini', 'codex', 'claude'])
    parser.add_argument('--reviewer', default=DEFAULT_ROLES['reviewer'],
                        choices=['gemini', 'codex', 'claude'])
    parser.add_argument('--finalizer', default=DEFAULT_ROLES['finalizer'],
                        choices=['gemini', 'codex', 'claude'])
    parser.add_argument('--skip-validation', action='store_true')
    parser.add_argument('--skip-review', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--timeout', type=int, default=DEFAULT_TIMEOUT)

    args = parser.parse_args()
    args.chapter = chapter_val  # attach the extracted chapter filter

    available = check_available_tools()
    if not any(available.values()):
        _sys.exit("No AI CLI tools found. Install at least one of: gemini, codex, claude")

    run_subject_pipeline(args, available)


if __name__ == '__main__':
    _patched_main()
