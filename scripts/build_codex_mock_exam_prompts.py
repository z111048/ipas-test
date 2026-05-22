#!/usr/bin/env python3
"""Build Codex CLI prompts for middle-level mock exam generation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from textwrap import dedent

BASE = Path('/home/james/projects/ipas-test')
LEVEL = '中級'
SUBJECT_ORDER = ['mid-s1', 'mid-s3', 'mid-s2']
SUBJECT_NUMBER = {'mid-s1': 1, 'mid-s2': 2, 'mid-s3': 3}
QUESTION_TOTAL = 100


def load_json(path: Path) -> dict:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')


def chapter_allocation(chapters: list[dict], total: int) -> list[dict]:
    base = total // len(chapters)
    remainder = total % len(chapters)
    rows = []
    for index, chapter in enumerate(chapters):
        rows.append({
            'id': chapter['id'],
            'title': chapter['title'],
            'count': base + (1 if index < remainder else 0),
            'subtopics': chapter.get('subtopics', []),
            'page_range': chapter.get('page_range'),
        })
    return rows


def compact_official_exam(path: Path) -> dict:
    data = load_json(path)
    return {
        'exam': data.get('exam'),
        'total': data.get('total'),
        'questions': [
            {
                'id': q.get('id'),
                'question': q.get('question'),
                'options': q.get('options'),
                'answer': q.get('answer'),
            }
            for q in data.get('questions', [])
        ],
    }


def build_prompt(subject: dict, allocation: list[dict], output_path: Path) -> str:
    subject_id = subject['id']
    subject_no = SUBJECT_NUMBER[subject_id]
    guide_path = f'data/中級/guide/subject{subject_no}_guide.json'
    current_questions_path = f'data/中級/questions/subject{subject_no}_questions.json'
    official_exam_path = f'data/中級/questions/mock_exam{subject_no}.json'
    sample_exam_path = 'data/中級/questions/sample_exam.json'
    glossary_path = 'frontend/src/generated/middleGlossary.json'

    official_exam = compact_official_exam(BASE / official_exam_path)
    sample_exam = compact_official_exam(BASE / sample_exam_path)
    allocation_json = json.dumps(allocation, ensure_ascii=False, indent=2)
    official_preview = json.dumps(official_exam, ensure_ascii=False, indent=2)
    sample_preview = json.dumps(sample_exam, ensure_ascii=False, indent=2)

    return dedent(f"""\
    你是 iPAS「AI 應用規劃師（中級）」命題專家。請在 Codex CLI 的 read-only sandbox 內工作。

    ## 任務
    參考官方去年考古題與樣題風格，為指定科目產生 100 題全新的四選一模擬題。
    本次只處理一個科目：{subject['subject']}（{subject_id}）。

    ## 必讀資料
    請只讀取下列本機檔案，不要連網，不要修改任何檔案：
    - 學習指引章節內容：`{guide_path}`
    - 去年官方公告試題解析：`{official_exam_path}`
    - 中級官方考試樣題解析：`{sample_exam_path}`
    - 目前既有章節題：`{current_questions_path}`（用於避免重複）
    - 中級關鍵字表：`{glossary_path}`（用於術語一致性）

    ## 章節配題
    請依下列分配精準產生題目，總數必須剛好 100 題：
    ```json
    {allocation_json}
    ```

    ## 參考考古題風格
    以下是官方公告試題資料。請學習題型、語氣、難度、選項長度與干擾項設計，但不可抄題、不可只替換名詞。
    ```json
    {official_preview}
    ```

    以下是中級官方樣題資料。請同樣參考題型與語氣，尤其注意跨科整合、情境題與流程判斷題。
    ```json
    {sample_preview}
    ```

    ## 出題規則
    - 每題只能有一個正確答案，answer 必須是 A/B/C/D。
    - 題目必須來自學習指引內容與關鍵字表可支持的概念，不可捏造教材外知識。
    - 每章至少覆蓋 3 種題型，優先混合：概念定義、比較辨析、應用情境、流程順序、錯誤識別、資料/模型治理判斷。
    - 避免與 `{current_questions_path}`、官方公告試題、官方樣題高度相似。
    - 干擾項要合理，不能使用明顯荒謬答案。
    - 難度比例請接近：易 20%、中 55%、難 25%。
    - 題幹與解析使用繁體中文，必要英文術語可保留原文或縮寫。
    - 否定題必須明確標示「何者錯誤」、「何者不適合」或「何者並非」。
    - 每題 explanation 必須說明正確答案理由，並至少點出一個錯誤選項的問題。
    - 每題 card 必須完整，方便前端複習卡使用。

    ## ID 規則
    - 請自行產生穩定 ID。
    - 格式：`{{chapter_id}}q{{章內序號三位數}}_codex100`
    - 例：`mid-s1c1q001_codex100`
    - 每章章內序號從 001 開始。

    ## 輸出格式
    只輸出純 JSON，不要 Markdown，不要說明文字。
    JSON 必須符合下列結構：
    {{
      "level": "中級",
      "subject_id": "{subject_id}",
      "subject": "{subject['subject']}",
      "generation_order": {SUBJECT_ORDER.index(subject_id) + 1},
      "target_total": 100,
      "source_strategy": "參考官方公告試題與中級樣題題型，依學習指引逐章平均分配產生全新題目。",
      "chapter_allocations": [
        {{"id": "章節 ID", "title": "章節標題", "count": 0}}
      ],
      "questions": [
        {{
          "id": "mid-s1c1q001_codex100",
          "chapter_id": "mid-s1c1",
          "chapter_title": "章節標題",
          "question": "題目文字",
          "options": {{"A": "選項 A", "B": "選項 B", "C": "選項 C", "D": "選項 D"}},
          "answer": "A",
          "explanation": "解析文字",
          "difficulty": "易",
          "type": "概念定義型",
          "tags": ["術語", "章節概念"],
          "source_refs": {{
            "guide_path": "{guide_path}",
            "chapter_id": "mid-s1c1",
            "basis": "簡述此題依據的教材概念"
          }},
          "card": {{
            "concept": "核心概念摘要",
            "mnemonic": "記憶口訣或聯想",
            "confusion": "常見混淆點",
            "frequency": "高"
          }}
        }}
      ],
      "quality_checks": {{
        "question_count": 100,
        "chapter_distribution_verified": true,
        "dedupe_checked_against_official_and_existing": true,
        "single_answer_verified": true
      }}
    }}

    ## 最終自檢
    輸出前請自行檢查：
    - questions 長度是否剛好 100。
    - 每章題數是否完全等於章節配題表。
    - 每題 options 是否剛好 A/B/C/D。
    - 每題 answer 是否存在於 options。
    - 每題是否有 explanation、difficulty、type、tags、source_refs、card。
    - 是否有重複題幹或過度近似官方考古題。

    目標輸出檔案由呼叫端以 `-o {output_path.as_posix()}` 接收；你只需要在最後訊息輸出 JSON。
    """).strip() + '\n'


def build_command(prompt_path: Path, output_path: Path, schema_path: Path) -> str:
    codex_command = (
        'codex exec '
        f'--cd {BASE.as_posix()} '
        '--sandbox read-only '
        f'--output-schema {schema_path.as_posix()} '
        f'-o {output_path.as_posix()} '
        f'- < {prompt_path.as_posix()}'
    )
    validate_command = f'python3 scripts/validate_codex_mock_exam_output.py {output_path.as_posix()}'
    return f'{codex_command}\n{validate_command}'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--out-dir',
        default='data/中級/pipeline/codex_mock_exam_prompts',
        help='輸出 prompt 與命令的資料夾',
    )
    args = parser.parse_args()

    out_dir = BASE / args.out_dir
    prompt_dir = out_dir / 'prompts'
    result_dir = out_dir / 'results'
    schema_path = BASE / 'schemas' / 'middle_mock_exam_subject.schema.json'

    manifest = load_json(BASE / 'data' / LEVEL / 'toc_manifest.json')
    subjects = {subject['id']: subject for subject in manifest['subjects']}

    commands = []
    summary = {
        'level': LEVEL,
        'target_per_subject': QUESTION_TOTAL,
        'generation_order': SUBJECT_ORDER,
        'subjects': [],
    }
    for order, subject_id in enumerate(SUBJECT_ORDER, start=1):
        subject = subjects[subject_id]
        allocation = chapter_allocation(subject['chapters'], QUESTION_TOTAL)
        prompt_path = prompt_dir / f'{order:02d}_{subject_id}.prompt.md'
        output_path = result_dir / f'{order:02d}_{subject_id}_codex100.json'
        prompt = build_prompt(subject, allocation, output_path)
        write_text(prompt_path, prompt)
        commands.append(build_command(prompt_path, output_path, schema_path))
        summary['subjects'].append({
            'order': order,
            'id': subject_id,
            'subject': subject['subject'],
            'chapters': len(subject['chapters']),
            'allocation': allocation,
            'prompt': prompt_path.relative_to(BASE).as_posix(),
            'output': output_path.relative_to(BASE).as_posix(),
        })

    write_text(out_dir / 'run_codex_readonly.sh', '#!/usr/bin/env bash\nset -euo pipefail\n\n' + '\n\n'.join(commands) + '\n')
    write_text(out_dir / 'summary.json', json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    print(f'Wrote prompts to {prompt_dir.relative_to(BASE)}')
    print(f'Wrote command file to {(out_dir / "run_codex_readonly.sh").relative_to(BASE)}')
    for command in commands:
        print(command)


if __name__ == '__main__':
    main()
