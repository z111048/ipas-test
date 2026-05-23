#!/usr/bin/env python3
"""Build per-chapter Codex prompts for middle mock exam generation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from textwrap import dedent

BASE = Path('/home/james/projects/ipas-test')
LEVEL = '中級'
SUBJECT_ORDER = ['mid-s1', 'mid-s3', 'mid-s2']
SUBJECT_NUMBER = {'mid-s1': 1, 'mid-s2': 2, 'mid-s3': 3}
TOTAL = 100


def load_json(path: Path) -> dict:
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding='utf-8')


def allocation(chapters: list[dict]) -> dict[str, int]:
    base = TOTAL // len(chapters)
    remainder = TOTAL % len(chapters)
    return {
        chapter['id']: base + (1 if index < remainder else 0)
        for index, chapter in enumerate(chapters)
    }


def build_prompt(subject: dict, chapter: dict, count: int, output_path: Path) -> str:
    subject_id = subject['id']
    subject_no = SUBJECT_NUMBER[subject_id]
    guide_path = f'data/中級/guide/subject{subject_no}_guide.json'
    current_questions_path = f'data/中級/questions/subject{subject_no}_questions.json'
    official_exam_path = f'data/中級/questions/mock_exam{subject_no}.json'
    sample_exam_path = 'data/中級/questions/sample_exam.json'
    glossary_path = 'frontend/src/generated/middleGlossary.json'
    chapter_json = json.dumps(chapter, ensure_ascii=False, indent=2)

    return dedent(f"""\
    你是 iPAS「AI 應用規劃師（中級）」命題專家。請在 Codex CLI 的 read-only sandbox 內工作。

    ## 任務
    參考官方去年考古題與樣題風格，為下列單一章節產生 {count} 題全新的四選一模擬題。

    ## 科目與章節
    科目：{subject['subject']}（{subject_id}）
    章節資料：
    ```json
    {chapter_json}
    ```

    ## 必讀資料
    請只讀取下列本機檔案，不要連網，不要修改任何檔案：
    - 學習指引章節內容：`{guide_path}`
    - 去年官方公告試題解析：`{official_exam_path}`
    - 中級官方考試樣題解析：`{sample_exam_path}`
    - 目前既有章節題：`{current_questions_path}`（用於避免重複）
    - 中級關鍵字表：`{glossary_path}`（用於術語一致性）

    ## 出題策略
    - 請先從 `{guide_path}` 找出 chapter_id = `{chapter['id']}` 的章節內容，只依此章與其 subtopics 出題。
    - 參考 `{official_exam_path}` 和 `{sample_exam_path}` 的題型、語氣、選項長度與情境敘述方式，但不可抄題、不可只替換名詞。
    - 避免與 `{current_questions_path}` 既有題目高度相似。
    - 本章必須剛好產生 {count} 題。

    ## 題目規則
    - 每題只能有一個正確答案，answer 必須是 A/B/C/D。
    - 題目必須可由學習指引內容或關鍵字表支持，不可捏造教材外知識。
    - 至少混合 3 種題型：概念定義、比較辨析、應用情境、流程順序、錯誤識別、資料/模型治理判斷。
    - 干擾項要合理，不能使用明顯荒謬答案。
    - 難度比例請接近：易 20%、中 55%、難 25%。
    - 題幹與解析使用繁體中文，必要英文術語可保留原文或縮寫。
    - 否定題必須明確標示「何者錯誤」、「何者不適合」或「何者並非」。
    - explanation 必須說明正確答案理由，並至少點出一個錯誤選項的問題。
    - card 必須完整，方便前端複習卡使用。

    ## ID 規則
    - 格式：`{chapter['id']}q{{章內序號三位數}}_codex100`
    - 本章序號從 001 開始。

    ## 輸出格式
    只輸出純 JSON，不要 Markdown，不要說明文字。
    JSON 必須符合：
    {{
      "level": "中級",
      "subject_id": "{subject_id}",
      "chapter_id": "{chapter['id']}",
      "chapter_title": "{chapter['title']}",
      "target_count": {count},
      "questions": [
        {{
          "id": "{chapter['id']}q001_codex100",
          "chapter_id": "{chapter['id']}",
          "chapter_title": "{chapter['title']}",
          "question": "題目文字",
          "options": {{"A": "選項 A", "B": "選項 B", "C": "選項 C", "D": "選項 D"}},
          "answer": "A",
          "explanation": "解析文字",
          "difficulty": "易",
          "type": "概念定義型",
          "tags": ["術語", "章節概念"],
          "source_refs": {{
            "guide_path": "{guide_path}",
            "chapter_id": "{chapter['id']}",
            "basis": "簡述此題依據的教材概念"
          }},
          "card": {{
            "concept": "核心概念摘要",
            "mnemonic": "記憶口訣或聯想",
            "confusion": "常見混淆點",
            "frequency": "高"
          }}
        }}
      ]
    }}

    輸出前請確認 questions 長度剛好是 {count}，且每題 ID、chapter_id、options、answer、card 都完整。
    目標輸出檔案由呼叫端以 `-o {output_path.as_posix()}` 接收；你只需要在最後訊息輸出 JSON。
    """).strip() + '\n'


def build_command(prompt_path: Path, output_path: Path, schema_path: Path) -> str:
    return (
        'codex exec '
        f'--cd {BASE.as_posix()} '
        '--sandbox read-only '
        f'--output-schema {schema_path.as_posix()} '
        f'-o {output_path.as_posix()} '
        f'- < {prompt_path.as_posix()}'
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-dir', default='data/中級/pipeline/codex_chapter_mock_prompts')
    args = parser.parse_args()

    out_dir = BASE / args.out_dir
    prompt_dir = out_dir / 'prompts'
    result_dir = out_dir / 'results'
    result_dir.mkdir(parents=True, exist_ok=True)
    schema_path = BASE / 'schemas' / 'middle_mock_exam_chapter.schema.json'
    manifest = load_json(BASE / 'data' / LEVEL / 'toc_manifest.json')
    subjects = {subject['id']: subject for subject in manifest['subjects']}

    commands = []
    summary = {'level': LEVEL, 'target_per_subject': TOTAL, 'generation_order': SUBJECT_ORDER, 'chapters': []}
    for subject_order, subject_id in enumerate(SUBJECT_ORDER, start=1):
        subject = subjects[subject_id]
        counts = allocation(subject['chapters'])
        for chapter_order, chapter in enumerate(subject['chapters'], start=1):
            count = counts[chapter['id']]
            prefix = f'{subject_order:02d}_{chapter_order:02d}_{chapter["id"]}'
            prompt_path = prompt_dir / f'{prefix}.prompt.md'
            output_path = result_dir / f'{prefix}.json'
            write_text(prompt_path, build_prompt(subject, chapter, count, output_path))
            commands.append(build_command(prompt_path, output_path, schema_path))
            summary['chapters'].append({
                'subject_order': subject_order,
                'chapter_order': chapter_order,
                'subject_id': subject_id,
                'chapter_id': chapter['id'],
                'title': chapter['title'],
                'count': count,
                'prompt': prompt_path.relative_to(BASE).as_posix(),
                'output': output_path.relative_to(BASE).as_posix(),
            })

    write_text(out_dir / 'run_codex_readonly.sh', '#!/usr/bin/env bash\nset -euo pipefail\n\n' + '\n\n'.join(commands) + '\n')
    write_text(out_dir / 'summary.json', json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    print(f'Wrote {len(commands)} chapter prompts to {prompt_dir.relative_to(BASE)}')


if __name__ == '__main__':
    main()
