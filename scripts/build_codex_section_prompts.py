#!/usr/bin/env python3
"""以「小節區塊」為單位產生 Codex 出題 prompt。

    輸入  data/{level}/guide_sections/subject{N}.json （export_guide_sections.py 的產物）
    輸出  {run-dir}/prompts/*.prompt.md ＋ summary.json

跑法（summary.json 的格式與 build_codex_question_batch_prompts.py 相同，
所以直接沿用既有的 runner，連驗證與續跑都不必重寫）：

    python3 scripts/build_codex_section_prompts.py --level 中級 --subject 2 \\
        --chapter mid-s2c3 --count 2
    python3 scripts/run_codex_question_batch_generation.py \\
        --run-dir data/中級/pipeline/codex_section_prompts --limit 3

## 為什麼是小節而不是章

`generate_questions.py` 把章節內容截到 4000 字才餵給模型，一章動輒上萬字——
實測 41 章有 39 章被截斷，整份講義只有 40% 進得了出題流程。改用小節區塊後
覆蓋率 100%，而且**區塊內容直接寫進 prompt**，Codex 不必自己去大檔案裡翻，
出題依據明確得多。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from textwrap import dedent

BASE = Path('/home/james/projects/ipas-test')
DEFAULT_RUN_DIR = 'pipeline/codex_section_prompts'

# 題型固定成 enum：第一輪放任模型自由填，結果同一個概念出現「情境應用型」
# 與「應用情境型」兩種寫法，還多出「判讀型」「概念應用型」，前端要做題型
# 篩選會直接炸掉。
QUESTION_TYPES = ['概念定義型', '情境應用型', '否定型', '比較分析型', '計算判讀型']
# 正解字母逐題輪替。單批只有 2 題，靠 prompt 寫「請平均分布」沒有作用——
# 第一輪 28 題實測 A×10、B×11、C×4、D×3，猜 A/B 就有優勢。
ANSWER_CYCLE = ['A', 'B', 'C', 'D']
# 難度依 20% 易 / 50% 中 / 30% 難 的目標輪替（10 題一循環）
DIFFICULTY_CYCLE = ['中', '難', '易', '中', '中', '難', '中', '易', '中', '難']
SUBJECT_ID = {
    ('初級', 1): 's1', ('初級', 2): 's2',
    ('中級', 1): 'mid-s1', ('中級', 2): 'mid-s2', ('中級', 3): 'mid-s3',
}


def load_json(path: Path):
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def build_prompt(level: str, subject_index: int, subject_id: str, subject_title: str,
                 chapter: dict, chunk: dict, first: int, count: int,
                 previous_outputs: list[str], specs: list[dict]) -> str:
    last = first + count - 1
    spec_lines = '\n'.join(
        f"        - 第 {spec['number']:03d} 題：`type` 必須是 `{spec['type']}`、"
        f"`difficulty` 必須是 `{spec['difficulty']}`、正確答案必須是 `{spec['answer']}`"
        for spec in specs
    )
    types = '、'.join(f'`{t}`' for t in QUESTION_TYPES)
    previous_block = (
        '\n'.join(f'    - `{path}`' for path in previous_outputs)
        if previous_outputs else '    - 無，本批是此章第一批。'
    )
    # 官方題庫要逐檔列出、而且只列真的存在的檔。舊版寫死 `mock_exam1.json`，
    # 中級根本沒有那個檔名（中級是 mock_mid_*），等於「避免與官方題重複」這條
    # 從來沒生效——2026-08-08 在初級抓到兩題生成題與官方題一字不差就是這樣來的。
    official_paths = sorted(
        p.relative_to(BASE).as_posix()
        for p in (BASE / 'data' / level / 'questions').glob('*.json')
        if p.name.startswith(('mock_', 'sample_'))
    )
    official_block = (
        '\n'.join(f'    - `{path}`' for path in official_paths)
        if official_paths else '    - 查無官方題庫檔案，請回報而不要繼續出題。'
    )
    return dedent(f'''\
        你是 iPAS「AI 應用規劃師（{level}）」命題專家。請在 Codex CLI 的 read-only sandbox 內工作。

        重要限制：
        - 不要連網，不要修改任何檔案。
        - 完成分析前不要輸出任何 JSON、狀態訊息或 Markdown。
        - 最後只能輸出一個符合 schema 的純 JSON 物件。

        ## 任務
        依照下方「本批出題範圍」的講義原文，產生 {count} 題全新的四選一模擬題。
        本批題號範圍：{first:03d} 到 {last:03d}。

        ## 科目與章節
        科目：{subject_title}（{subject_id}）
        章節：{chapter['title']}（{chapter['id']}）
        本批小節：{chunk['title']}

        ## 本批出題範圍（講義原文，只依據這段出題）
        ```markdown
        {chunk['content']}
        ```

        ## 參考資料（可讀，用來抓題型與避免重複）
        - 官方歷屆與樣張試題（**出題前必讀，題幹不得與其中任何一題相同或近似**）：
{official_block}
        - 既有章節題（避免重複）：`data/{level}/questions/subject{subject_index}_questions.json`
        - 同章前批 Codex 輸出（若檔案存在，必讀並避免重複）：
{previous_block}

        ## 出題策略
        - **只依據上方「本批出題範圍」的內容出題**，不要跑去用該章其他小節的材料。
          這是小節粒度出題的重點——題目要能對回這一段講義。
        - 參考官方試題的題型、語氣、選項長度與情境敘述方式，但不可抄題、不可只替換名詞。
        - 四個選項都要合理，不要有明顯湊數的干擾項；干擾項要是真的有人會選錯的理由。
        - 若原文含公式或表格，可據以出計算或判讀題，但不要考背誦數字。
        - 本批必須剛好產生 {count} 題，彼此的概念不可重複。

        ## 本批每題的規格（必須完全照做）
{spec_lines}

        說明：
        - `type` 只能從這五種選：{types}。不要自創名稱、不要改字序。
        - **正確答案的字母是指定的**：請把正確內容放在指定的選項位置，其餘三個
          位置放干擾項。這是為了讓整份題庫的答案分布平均，不是提示。
        - 本批兩題的 `type` 已指定為不同題型，請勿混用。

        ## 輸出格式
        - `level` 必須是 `{level}`，`subject_id` 必須是 `{subject_id}`，
          `chapter_id` 必須是 `{chapter['id']}`，`chapter_title` 必須是 `{chapter['title']}`，
          `target_count` 必須是 {count}。
        - 每題 `id` 依序為 `{chapter['id']}q{first:03d}_codex100` 到 `{chapter['id']}q{last:03d}_codex100`。
        - 每題都要有 `source_refs`（指出依據的小節標題）與 `card`
          （`concept`／`mnemonic`／`confusion`／`frequency` 四個欄位都必填）。
        - 中文書寫，術語可附英文縮寫（如 RAG、LLM）。
        ''')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--level', choices=['初級', '中級'], default='中級')
    parser.add_argument('--subject', type=int, required=True)
    parser.add_argument('--chapter', help='只出這一章（如 mid-s2c3）；省略＝整科')
    parser.add_argument('--count', type=int, default=2, help='每個小節區塊出幾題')
    parser.add_argument('--run-dir', default=None)
    args = parser.parse_args()

    subject_id = SUBJECT_ID[(args.level, args.subject)]
    sections_path = BASE / 'data' / args.level / 'guide_sections' / f'subject{args.subject}.json'
    data = load_json(sections_path)
    subject_title = data.get('subject') or subject_id

    run_dir = BASE / 'data' / args.level / (args.run_dir or DEFAULT_RUN_DIR)
    prompts_dir = run_dir / 'prompts'
    results_dir = run_dir / 'results'
    prompts_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    batches = []
    batch_index = 0
    question_ordinal = 0   # 全域計數，讓輪替跨批次連續而不是每批從頭
    for chapter in data['chapters']:
        if args.chapter and chapter['id'] != args.chapter:
            continue
        # 題號在同一章內連續累加，前批輸出會被下一批當成「避免重複」的輸入
        first = 1
        chapter_outputs: list[str] = []
        for chunk in chapter['chunks']:
            batch_index += 1
            stem = f'{batch_index:03d}_{chapter["id"]}_q{first:03d}-{first + args.count - 1:03d}'
            prompt_path = prompts_dir / f'{stem}.prompt.md'
            output_path = results_dir / f'{stem}.json'
            specs = []
            for offset in range(args.count):
                specs.append({
                    'number': first + offset,
                    # 題型錯開一格，同一批的兩題必定不同型
                    'type': QUESTION_TYPES[(question_ordinal + offset) % len(QUESTION_TYPES)],
                    'difficulty': DIFFICULTY_CYCLE[(question_ordinal + offset) % len(DIFFICULTY_CYCLE)],
                    'answer': ANSWER_CYCLE[(question_ordinal + offset) % len(ANSWER_CYCLE)],
                })
            question_ordinal += args.count

            prompt_path.write_text(
                build_prompt(args.level, args.subject, subject_id, subject_title,
                             chapter, chunk, first, args.count, list(chapter_outputs), specs),
                encoding='utf-8')
            batches.append({
                'batch_index': batch_index,
                'subject_id': subject_id,
                'chapter_id': chapter['id'],
                'title': chapter['title'],
                'section_id': chunk['id'],
                'section_title': chunk['title'],
                'section_chars': len(chunk['content']),
                'first_question': first,
                'count': args.count,
                'prompt': prompt_path.relative_to(BASE).as_posix(),
                'output': output_path.relative_to(BASE).as_posix(),
                'previous_outputs': list(chapter_outputs),
                'specs': specs,
            })
            chapter_outputs.append(output_path.relative_to(BASE).as_posix())
            first += args.count

    summary = {
        'level': args.level,
        'subject_id': subject_id,
        'source': sections_path.relative_to(BASE).as_posix(),
        'granularity': 'section',
        'batches': batches,
    }
    (run_dir / 'summary.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    total = sum(b['count'] for b in batches)
    print(f'寫入 {run_dir.relative_to(BASE)}：{len(batches)} 批、共 {total} 題')
    for batch in batches[:5]:
        print(f'  {batch["batch_index"]:03d} {batch["chapter_id"]} '
              f'q{batch["first_question"]:03d}-{batch["first_question"] + batch["count"] - 1:03d} '
              f'（{batch["section_chars"]} 字）{batch["section_title"][:30]}')
    if len(batches) > 5:
        print(f'  …另有 {len(batches) - 5} 批')


if __name__ == '__main__':
    main()
