#!/usr/bin/env python3
"""Parse exam questions from JSON tables (accurate extraction)."""

import json
import re
from pathlib import Path

from extract_pdfs import EXAM_PDFS_BY_LEVEL

BASE = Path('/home/james/projects/ipas-test')

EXAM_TITLES_BY_LEVEL: dict[str, dict[str, str]] = {
    '初級': {
        'exam1': '科目一 模擬考試：人工智慧基礎概論（114年第四梯次公告試題）',
        'exam2': '科目二 模擬考試：生成式AI應用與規劃（114年第四梯次公告試題）',
        'sample': '考試樣題（114年9月版）',
    },
    '中級': {
        'exam1': '中級科目一 模擬考試：人工智慧技術應用與規劃（114年第二梯次公告試題）',
        'exam2': '中級科目二 模擬考試：大數據處理分析與應用（114年第二梯次公告試題）',
        'exam3': '中級科目三 模擬考試：機器學習技術與應用（114年第二梯次公告試題）',
        'sample': '中級考試樣題（114年9月版）',
    },
}

FW_MAP = {'Ａ': 'A', 'Ｂ': 'B', 'Ｃ': 'C', 'Ｄ': 'D', '（': '(', '）': ')'}
IMAGE_HINT_RE = re.compile(
    r'附圖|下圖|圖中|如下圖|圖所示|圖片|圖表|程式碼|虛擬程式碼|欄位概觀|外觀如下|視覺化',
)


def normalize(s: str) -> str:
    for fw, hw in FW_MAP.items():
        s = s.replace(fw, hw)
    return s


def parse_question_cell(
    answer: str,
    cell_text: str,
    qnum: int,
    source_key: str,
    page_index: int | None = None,
) -> dict | None:
    """Parse a single question from table cell text."""
    answer = normalize(answer.strip())
    if answer not in ('A', 'B', 'C', 'D'):
        return None

    text = cell_text.strip()
    # Remove embedded question number (e.g. "\n1.\n" or "1.")
    text = re.sub(r'\n\d+[\.\．]\n', '\n', text)
    text = re.sub(r'^\d+[\.\．]\s*', '', text)

    # Extract options
    opts = {}
    opt_pattern = re.compile(r'\(([A-D])\)(.*?)(?=\([A-D]\)|\Z)', re.DOTALL)
    for m in opt_pattern.finditer(text):
        opt_text = m.group(2).strip()
        opt_text = re.sub(r'[；;]\s*$', '', opt_text)
        opt_text = re.sub(r'\s+', ' ', opt_text).strip()
        opts[m.group(1)] = opt_text

    if len(opts) < 4:
        return None

    # Question text = everything before first option
    q_match = re.match(r'^(.*?)(?=\([A-D]\))', text, re.DOTALL)
    q_text = q_match.group(1).strip() if q_match else ''
    q_text = re.sub(r'\s+', ' ', q_text).strip()

    if not q_text or not opts:
        return None

    question = {
        'id': f'{source_key}_q{qnum}',
        'question': q_text,
        'options': opts,
        'answer': answer,
        'explanation': f'正確答案為({answer})。',
        'source': source_key,
    }
    if page_index is not None:
        question['source_ref'] = {
            'page_index': page_index,
            'page_number': page_index + 1,
        }
    return question


def public_asset_path(level: str, key: str, page_index: int, filename: str) -> str:
    return f'/pdf-assets/{level}/{key}/page_{page_index:03d}/{filename}'


def load_page_image_assets(level: str, key: str) -> dict[int, dict]:
    pages_dir = BASE / 'data' / level / 'page_extract' / key / 'pages'
    if not pages_dir.exists():
        return {}

    assets_by_page: dict[int, dict] = {}
    for page_path in sorted(pages_dir.glob('page_*.json')):
        page = json.loads(page_path.read_text(encoding='utf-8'))
        page_index = page['page_index']
        images = []
        for image in page.get('images', []):
            rel_path = image.get('path')
            if not rel_path:
                continue
            images.append({
                'type': 'image',
                'src': public_asset_path(level, key, page_index, Path(rel_path).name),
                'alt': f'{key} 第 {page_index + 1} 頁圖片 {image.get("id", "")}'.strip(),
                'page_index': page_index,
                'page_number': page_index + 1,
                'bbox': image.get('bbox', []),
            })

        page_image = page.get('page_image') or {}
        page_asset = None
        if page_image.get('path'):
            page_asset = {
                'type': 'page',
                'src': public_asset_path(level, key, page_index, Path(page_image['path']).name),
                'alt': f'{key} 第 {page_index + 1} 頁原始截圖',
                'page_index': page_index,
                'page_number': page_index + 1,
                'bbox': page_image.get('bbox', []),
            }

        if images or page_asset:
            assets_by_page[page_index] = {
                'images': images,
                'page': page_asset,
            }
    return assets_by_page


def question_needs_image(question: dict) -> bool:
    combined = question.get('question', '')
    combined += ' '.join(question.get('options', {}).values())
    return bool(IMAGE_HINT_RE.search(combined))


def attach_exam_images(level: str, key: str, questions: list[dict]) -> None:
    assets_by_page = load_page_image_assets(level, key)
    if not assets_by_page:
        return

    questions_by_page: dict[int, list[dict]] = {}
    for question in questions:
        page_index = (question.get('source_ref') or {}).get('page_index')
        if isinstance(page_index, int):
            questions_by_page.setdefault(page_index, []).append(question)

    attached = 0
    attached_ids: set[str] = set()
    for page_index, page_questions in questions_by_page.items():
        assets = assets_by_page.get(page_index)
        if not assets or not assets['images']:
            continue
        candidates = [question for question in page_questions if question_needs_image(question)]
        if not candidates:
            continue

        if len(candidates) == 1 and len(assets['images']) == 1:
            image_payload = assets['images']
        elif assets['page']:
            # Multiple image-dependent questions can share one PDF page. Use the
            # original page screenshot to avoid assigning the wrong crop.
            image_payload = [assets['page']]
        else:
            image_payload = assets['images']

        for question in candidates:
            question['images'] = image_payload
            attached_ids.add(question['id'])
            attached += 1

    for question in questions:
        if question['id'] in attached_ids or not question_needs_image(question):
            continue
        page_index = (question.get('source_ref') or {}).get('page_index')
        if not isinstance(page_index, int):
            continue
        next_assets = assets_by_page.get(page_index + 1)
        if next_assets and next_assets['images'] and next_assets['page']:
            question['images'] = [next_assets['page']]
            attached_ids.add(question['id'])
            attached += 1

    if attached:
        print(f'  {key}: attached images/page screenshots to {attached} questions')


def parse_exam_json(key: str, data_dir: Path) -> list[dict]:
    """Parse questions from exam JSON using table data."""
    with open(data_dir / 'extracted' / f'{key}.json', encoding='utf-8') as f:
        data = json.load(f)
    questions = []
    pending_answer: str | None = None
    pending_cell = ''
    pending_page_index: int | None = None

    def flush_pending() -> None:
        nonlocal pending_answer, pending_cell
        nonlocal pending_page_index
        if not pending_answer or not pending_cell.strip():
            pending_answer = None
            pending_cell = ''
            pending_page_index = None
            return
        qnum = len(questions) + 1
        q = parse_question_cell(pending_answer, pending_cell, qnum, key, pending_page_index)
        if q:
            questions.append(q)
        else:
            print(
                f"  WARN: {key} row {qnum} skipped "
                f"(answer={pending_answer!r}, cell={pending_cell[:40]!r})"
            )
        pending_answer = None
        pending_cell = ''
        pending_page_index = None

    for page in data['pages']:
        page_index = int(page.get('page', 1)) - 1
        for table in page.get('tables', []):
            for row in table:
                if not row or len(row) < 2:
                    continue
                cells = [str(cell or '').strip() for cell in row]
                # Skip header rows
                if any(cell in ('答案', '題號', '題目', '題 目') for cell in cells):
                    continue

                answer = None
                answer_index = -1
                for index, cell in enumerate(cells):
                    normalized = normalize(cell)
                    if re.match(r'^[A-D]$', normalized):
                        answer = normalized
                        answer_index = index
                        break

                text_cells = [
                    cell for index, cell in enumerate(cells)
                    if index != answer_index and cell and cell not in ('新',)
                ]
                cell = max(text_cells, key=len, default='').strip()

                if answer:
                    flush_pending()
                    pending_answer = answer
                    pending_cell = cell
                    pending_page_index = page_index
                elif pending_answer and cell:
                    pending_cell = f'{pending_cell}\n{cell}'.strip()
                else:
                    continue

    flush_pending()

    print(f"  {key}: {len(questions)} questions parsed")
    return questions


def parse_sample_json(data_dir: Path) -> list[dict]:
    """Parse sample exam from JSON — has different table format."""
    with open(data_dir / 'extracted' / 'sample.json', encoding='utf-8') as f:
        data = json.load(f)
    questions = []

    for page in data['pages']:
        page_index = int(page.get('page', 1)) - 1
        for table in page.get('tables', []):
            for row in table:
                if not row or len(row) < 4:
                    continue
                # Sample format: [qnum, '', '', answer, '', '', question_text, '']
                # or: ['1.', '', '', 'B', '', '', 'question...', '']
                # Find answer (A/B/C/D) and question text
                answer = None
                q_text_cell = None
                for cell in row:
                    s = normalize(str(cell or '').strip())
                    if re.match(r'^[ABCD]$', s) and answer is None:
                        answer = s
                    elif s and len(s) > 10 and '(A)' in s and answer is not None:
                        q_text_cell = s

                if answer and q_text_cell:
                    qnum = len(questions) + 1
                    q = parse_question_cell(answer, q_text_cell, qnum, 'sample', page_index)
                    if q:
                        questions.append(q)

    print(f"  sample: {len(questions)} questions parsed")
    return questions


def save_mock(filename: str, title: str, questions: list[dict], questions_dir: Path):
    mock = {
        'exam': title,
        'total': len(questions),
        'time_limit': '90分鐘',
        'passing_score': 60,
        'questions': questions,
    }
    path = questions_dir / filename
    path.write_text(json.dumps(mock, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Saved {path} ({len(questions)} questions)")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Parse exam questions from extracted JSON')
    parser.add_argument('--level', default='初級',
                        help='資料等級資料夾（預設: 初級）')
    args = parser.parse_args()

    data_dir = BASE / 'data' / args.level
    questions_dir = data_dir / 'questions'
    questions_dir.mkdir(exist_ok=True)

    exam_map = EXAM_PDFS_BY_LEVEL.get(args.level, {})
    titles = EXAM_TITLES_BY_LEVEL.get(args.level, {})
    for key in sorted(exam_map):
        if key == 'sample':
            qs = parse_sample_json(data_dir)
            attach_exam_images(args.level, key, qs)
            save_mock('sample_exam.json', titles.get(key, '考試樣題'), qs, questions_dir)
            continue
        questions = parse_exam_json(key, data_dir)
        attach_exam_images(args.level, key, questions)
        filename = f'mock_{key}.json'
        save_mock(filename, titles.get(key, f'{args.level} {key} 模擬考試'), questions, questions_dir)

    print("\nAll mock exams saved.")


if __name__ == '__main__':
    main()
