#!/usr/bin/env python3
"""單一生成批次的答案交叉驗證，供 runner 與 export 當閘門用。

為什麼要有這支：`verify_question_answers.py` 是「跑完再稽核」的形狀，而稽核出來
不阻擋等於沒稽核（`audit_resources.py` 的 docstring 就是這句）。這支把驗證變成
**批次的驗證條件之一**——不過的批次算失敗、重跑會重生，`export_generated_questions.py`
也會拒絕把它寫進題庫。

判定沿用既有邏輯（選項依題 id 決定性洗牌、verifier 只看題幹與選項、盲答），
結果寫在輸出檔旁邊 `<batch>.verify.json`，所以：
    可續跑（已驗過就不重驗）
    可稽核（每題誰投什麼票都留著）

⚠️ 三個 verifier 在官方初級考卷上校準為 0/50 錯（2026-08-09），但那份卷對它們偏易；
它們能抓「答案明顯錯」，不保證抓得出「兩個選項都說得通」的細緻錯誤。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_question_answers import (  # noqa: E402
    annotate,
    load_env_file,
    needs_figure,
    parse_verifiers,
    score,
    verify_question,
)

BASE = Path(__file__).resolve().parents[1]
DEFAULT_VERIFIERS = 'llm:glm-5.2,llm:deepseek-v4-pro,llm:kimi-k2.7-code'


def verify_path(output_path: Path) -> Path:
    return output_path.with_suffix('.verify.json')


def verify_batch_answers(output_path: Path, level: str,
                         verifiers_spec: str = DEFAULT_VERIFIERS,
                         threshold: int = 2, timeout: int = 180,
                         retries: int = 1, force: bool = False) -> dict[str, Any]:
    """回傳 `{ok, flagged, checked, skipped, results}`。

    `ok=False` 代表這批不該進題庫。**驗不到也不算過**（例如 verifier 全部失敗），
    否則又回到「檢查不出來就放行」。
    """
    out_path = verify_path(output_path)
    if out_path.exists() and not force:
        with out_path.open(encoding='utf-8') as f:
            return json.load(f)

    load_env_file()
    verifiers = parse_verifiers(verifiers_spec)
    keys = [name for name, _, _ in verifiers]

    with output_path.open(encoding='utf-8') as f:
        questions = json.load(f)['questions']

    results: list[dict[str, Any]] = []
    flagged: list[str] = []
    skipped: list[str] = []
    for question in questions:
        if needs_figure(question):
            # 純文字 verifier 看不到圖，硬答等於製造假訊號
            skipped.append(question['id'])
            continue
        raw = verify_question(question, verifiers, level, timeout, retries)
        scored = annotate(score(raw, keys))
        results.append(scored)
        if len(scored['no_answer']) == len(keys):
            flagged.append(question['id'])      # 驗不到不算過
        elif scored['wrong_count'] >= threshold:
            flagged.append(question['id'])

    payload = {
        'ok': not flagged,
        'level': level,
        'verifiers': keys,
        'threshold': threshold,
        'checked': len(results),
        'skipped': skipped,
        'flagged': flagged,
        # 不同意的 verifier 都選同一個錯誤選項才是「標記答案真的錯」的證據；
        # 各選各的只代表題目難（`annotate` 的 docstring 有校準案例）。人工先看這批。
        'flaggedConsensus': [r['question_id'] for r in results
                             if r['question_id'] in flagged and r.get('wrong_consensus')],
        'results': results,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n',
                        encoding='utf-8')
    return payload


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('output', type=Path, help='批次輸出 JSON')
    parser.add_argument('--level', required=True)
    parser.add_argument('--verifiers', default=DEFAULT_VERIFIERS)
    parser.add_argument('--threshold', type=int, default=2)
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()

    result = verify_batch_answers(
        args.output if args.output.is_absolute() else BASE / args.output,
        args.level, args.verifiers, args.threshold, force=args.force)
    print(f"{'OK' if result['ok'] else 'FAIL'} 驗 {result['checked']} 題"
          f"｜flagged {len(result['flagged'])} {result['flagged']}"
          f"｜跳過圖片題 {len(result['skipped'])}")
    raise SystemExit(0 if result['ok'] else 1)
