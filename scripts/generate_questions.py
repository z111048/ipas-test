#!/usr/bin/env python3
"""
Generate exam questions with explanation cards using the Claude API.

Modes:
  --subject 1          Generate new questions for all chapters of subject 1
  --subject 2          Generate new questions for all chapters of subject 2
  --enrich             Add 'card' fields to existing questions that lack them
  --count N            Questions per chapter when generating (default: 5)
  --dry-run            Print prompts without calling the API

Requirements:
  pip install anthropic
  export ANTHROPIC_API_KEY=sk-...
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import anthropic
except ImportError:
    sys.exit("anthropic package not found. Run: pip install anthropic")

BASE = Path('/home/james/projects/ipas-test')
DATA = BASE / 'data' / '初級'
GUIDE_DIR = DATA / 'guide'
QUESTIONS_DIR = DATA / 'questions'

MODEL = 'claude-sonnet-4-6'
MAX_CONTENT_CHARS = 4000  # guide content chars fed to LLM per chapter

QUESTION_SCHEMA = """{
  "question": "題目文字（完整句子，以「下列」、「關於」等開頭）",
  "options": {"A": "選項A", "B": "選項B", "C": "選項C", "D": "選項D"},
  "answer": "A",
  "explanation": "完整解說（2-4 句，說明為何正確及其他選項錯誤的原因）",
  "card": {
    "concept": "核心概念摘要（1-2 句，直接點出最重要知識點）",
    "mnemonic": "記憶口訣或聯想技巧（簡短易記）",
    "confusion": "最常見的混淆點（與哪個概念容易搞混，以及辨別方式）",
    "frequency": "高"
  },
  "difficulty": "中",
  "type": "概念定義型",
  "tags": ["標籤1", "標籤2"]
}"""

QUESTION_TYPES = [
    '概念定義型（下列哪一敘述正確？）',
    '情境應用型（某企業...最適合哪種方法？）',
    '否定型（下列何者「不」正確？）',
    '比較分析型（A 與 B 的主要差異是？）',
]

DIFFICULTY_DIST = '難度分布：20% 易 / 50% 中 / 30% 難'

FREQ_GUIDE = (
    '高 = 過去考試出現 3 次以上，'
    '中 = 出現 1-2 次，'
    '低 = 未出現但屬重要概念'
)


def build_generate_prompt(chapter: dict, analysis: dict, count: int) -> str:
    content = chapter['content'][:MAX_CONTENT_CHARS]
    subtopics = '、'.join(chapter['subtopics'])
    q_types = '\n'.join(f'  - {t}' for t in QUESTION_TYPES)
    common_topics = '、'.join(analysis.get('common_topics', [])[:8])

    return f"""你是一位 iPAS 初級 AI 應用規劃師認證考試的命題專家。

請根據以下學習指引內容，為「{chapter['title']}」章節出 {count} 道四選一選擇題。

## 章節重點子主題
{subtopics}

## 常見高頻考題主題（請優先覆蓋）
{common_topics}

## 指引原文（前 {MAX_CONTENT_CHARS} 字元）
{content}

## 出題要求
- 題型混合：{q_types}
- {DIFFICULTY_DIST}
- 每題選項 A-D 均需合理，避免明顯錯誤的干擾選項
- 中文書寫，術語可附英文縮寫（如 RAG、LLM）
- 出題角度應模擬真實考試，避免超出指引範圍

## card 欄位說明
- concept：1-2 句核心知識點，適合快速複習
- mnemonic：讓人記憶深刻的口訣/聯想技巧
- confusion：最常見的混淆點與辨別方式
- frequency：{FREQ_GUIDE}

## 輸出格式
請輸出純 JSON 陣列（不加任何說明文字），格式如下：
[
  {QUESTION_SCHEMA},
  ...
]"""


def build_enrich_prompt(question: dict) -> str:
    opts = '\n'.join(f"({k}) {v}" for k, v in question['options'].items())
    return f"""請為以下 iPAS 考試題目生成解說圖卡（card）欄位。

題目：{question['question']}
{opts}
正確答案：({question['answer']})
解說：{question.get('explanation', '')}

請輸出純 JSON 物件（不加任何說明文字），格式如下：
{{
  "concept": "核心概念摘要（1-2 句）",
  "mnemonic": "記憶口訣或聯想技巧",
  "confusion": "最常見的混淆點與辨別方式",
  "frequency": "高/中/低"
}}"""


def call_claude(client: anthropic.Anthropic, prompt: str) -> str:
    message = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        messages=[{'role': 'user', 'content': prompt}],
    )
    return message.content[0].text


def parse_json_response(text: str) -> object:
    """Extract and parse JSON from LLM response (strips markdown fences)."""
    text = text.strip()
    if text.startswith('```'):
        lines = text.split('\n')
        # Remove opening and closing fence
        text = '\n'.join(lines[1:-1] if lines[-1].strip() == '```' else lines[1:])
    return json.loads(text)


def load_analysis(subject_num: int) -> dict:
    path = DATA / 'analysis' / 'exam_analysis.json'
    if path.exists():
        data = json.loads(path.read_text(encoding='utf-8'))
        key = f'subject{subject_num}'
        return data.get(key, {})
    return {}


def generate_for_subject(
    client: anthropic.Anthropic,
    subject_num: int,
    count: int,
    dry_run: bool,
):
    guide_path = GUIDE_DIR / f'subject{subject_num}_guide.json'
    if not guide_path.exists():
        sys.exit(f"Guide not found: {guide_path}\nRun parse_guides.py first.")

    questions_path = QUESTIONS_DIR / f'subject{subject_num}_questions.json'
    if not questions_path.exists():
        sys.exit(f"Questions file not found: {questions_path}")

    guide = json.loads(guide_path.read_text(encoding='utf-8'))
    subject_data = json.loads(questions_path.read_text(encoding='utf-8'))
    analysis = load_analysis(subject_num)

    # Build a set of existing chapter ids for easy lookup
    chapter_map = {ch['id']: ch for ch in subject_data.get('chapters', [])}

    for chapter in guide['chapters']:
        ch_id = chapter['id']
        print(f"\nGenerating {count} questions for {ch_id} ({chapter['title']})...")

        prompt = build_generate_prompt(chapter, analysis, count)

        if dry_run:
            print("--- PROMPT (dry-run) ---")
            print(prompt[:800], '...')
            print("--- END ---")
            continue

        try:
            raw = call_claude(client, prompt)
            new_questions = parse_json_response(raw)
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

        if not isinstance(new_questions, list):
            print(f"  ERROR: expected list, got {type(new_questions)}")
            continue

        # Assign ids and source
        existing = chapter_map.get(ch_id, {})
        existing_count = len(existing.get('questions', []))
        for i, q in enumerate(new_questions, existing_count + 1):
            q['id'] = f'{ch_id}q{i}_gen'
            q.setdefault('source', 'generated')

        # Append to existing chapter or create new chapter entry
        if ch_id in chapter_map:
            chapter_map[ch_id].setdefault('questions', []).extend(new_questions)
        else:
            chapter_map[ch_id] = {
                'id': ch_id,
                'title': chapter['title'],
                'questions': new_questions,
            }

        print(f"  Added {len(new_questions)} questions to {ch_id}")

    if dry_run:
        return

    # Rebuild chapters list preserving original order
    original_ids = [ch['id'] for ch in subject_data.get('chapters', [])]
    guide_ids = [ch['id'] for ch in guide['chapters']]
    all_ids = original_ids + [i for i in guide_ids if i not in original_ids]

    subject_data['chapters'] = [
        chapter_map[i] for i in all_ids if i in chapter_map
    ]

    questions_path.write_text(
        json.dumps(subject_data, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    print(f"\nSaved {questions_path}")


def enrich_cards(client: anthropic.Anthropic, dry_run: bool):
    """Add 'card' field to questions that are missing it."""
    for subject_num in [1, 2]:
        questions_path = QUESTIONS_DIR / f'subject{subject_num}_questions.json'
        if not questions_path.exists():
            continue

        subject_data = json.loads(questions_path.read_text(encoding='utf-8'))
        enriched = 0
        errors = 0

        for chapter in subject_data.get('chapters', []):
            for q in chapter.get('questions', []):
                if 'card' in q:
                    continue  # Already has card

                print(f"  Enriching {q['id']}...")
                prompt = build_enrich_prompt(q)

                if dry_run:
                    print("  --- PROMPT (dry-run) ---")
                    print(prompt[:400], '...')
                    continue

                try:
                    raw = call_claude(client, prompt)
                    card = parse_json_response(raw)
                    q['card'] = card
                    enriched += 1
                except Exception as e:
                    print(f"  ERROR on {q['id']}: {e}")
                    errors += 1

        if dry_run:
            continue

        questions_path.write_text(
            json.dumps(subject_data, ensure_ascii=False, indent=2), encoding='utf-8'
        )
        print(f"subject{subject_num}: enriched {enriched} questions, {errors} errors")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--subject', type=int, choices=[1, 2], help='Generate new questions for subject 1 or 2')
    group.add_argument('--enrich', action='store_true', help='Add card fields to existing questions')
    parser.add_argument('--count', type=int, default=5, help='Questions per chapter (default: 5)')
    parser.add_argument('--dry-run', action='store_true', help='Print prompts without calling API')
    args = parser.parse_args()

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    if args.subject:
        generate_for_subject(client, args.subject, args.count, args.dry_run)
    elif args.enrich:
        enrich_cards(client, args.dry_run)


if __name__ == '__main__':
    main()
