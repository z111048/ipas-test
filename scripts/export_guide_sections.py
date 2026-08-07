#!/usr/bin/env python3
"""把每一章的講義內容依小節切片，讓出題可以鎖定小節而不是整章。

    輸入  data/{level}/guide/subject{N}_guide.json      （章節內容，Track B）
          frontend/src/generated/guideHierarchy.json    （完整階層樹）
    輸出  data/{level}/guide_sections/subject{N}.json

## 為什麼需要這支

`generate_questions.py` 把章節內容截斷到 `MAX_CONTENT_CHARS = 4000` 才餵給模型，
但一章動輒上萬字——2026-08-06 實測 **41 章有 39 章被截斷，整份講義只有 40%
進得了出題流程**，最長的 mid-s1c1（36,918 字）只看得到 11%。
章的粒度太粗是根因，切到小節之後每片大多在幾百到兩千字，整章都能覆蓋到。

## 怎麼切

階層樹的標題文字有 95% 能在章節內容中原樣找到（實測 1,081/1,142），
所以用「依序定位標題、切出兩個標題之間的區段」的方式切片：
  * 定位是**正規化後比對**（NFKC + 去空白），因為這些 PDF 大量使用全形標點與
    CJK 相容字（「數」是 U+F969），不正規化會全部落空；比對完再映射回原字串取片段。
  * 從上一個標題的結束位置往後找，順序才不會錯亂（同名標題在一章裡會重複出現）。
  * 找不到的標題不會造成內容遺失——它只是沒有自己的切點，文字併入前一個小節。

章首在第一個標題之前的文字會獨立成一個 `intro` 小節，不會被丟掉。
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path

BASE = Path('/home/james/projects/ipas-test')
HIERARCHY = BASE / 'frontend' / 'src' / 'generated' / 'guideHierarchy.json'


def load_json(path: Path):
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def normalize_with_map(text: str) -> tuple[str, list[int]]:
    """回傳 (正規化後字串, 每個字元對應的原字串索引)。"""
    out: list[str] = []
    index_map: list[int] = []
    for i, ch in enumerate(text):
        for c in unicodedata.normalize('NFKC', ch):
            if c.isspace():
                continue
            out.append(c)
            index_map.append(i)
    return ''.join(out), index_map


def normalize(text: str) -> str:
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', text))


class ContentIndex:
    """對一章的內容做一次正規化，之後重複在上面找標題。"""

    def __init__(self, content: str) -> None:
        self.content = content
        self.norm, self.index_map = normalize_with_map(content)

    def find(self, needle: str, from_norm_pos: int = 0) -> tuple[int, int, int] | None:
        """回傳 (原字串起點, 原字串終點, 正規化字串終點)，找不到回傳 None。"""
        needle_norm = normalize(needle)
        if not needle_norm:
            return None
        pos = self.norm.find(needle_norm, from_norm_pos)
        if pos < 0:
            return None
        start = self.index_map[pos]
        end = self.index_map[pos + len(needle_norm) - 1] + 1
        return start, end, pos + len(needle_norm)


def hierarchy_sections(guide: dict, chapter_id: str) -> list[dict]:
    """回傳該章底下所有標題節點，文件順序、附層級與頁碼。"""
    out: list[dict] = []

    def walk(node_id: str) -> None:
        for child_id in guide['nodesById'].get(node_id, {}).get('childIds', []):
            node = guide['nodesById'][child_id]
            if node.get('kind') != 'heading':
                continue
            out.append({
                'id': child_id,
                'title': node['title'],
                'level': node.get('headingLevel') or node.get('depth'),
                'page': node.get('page'),
                'anchor': node.get('anchor'),
                'recovered': bool(node.get('recovered')),
            })
            walk(child_id)

    walk(chapter_id)
    return out


def slice_chapter(chapter: dict, sections: list[dict]) -> tuple[list[dict], int]:
    """把章節內容依標題切成小節，回傳 (小節清單, 沒定位到的標題數)。"""
    content = chapter.get('content') or ''
    if not content.strip():
        return [], 0

    index = ContentIndex(content)
    located: list[dict] = []
    cursor = 0
    unlocated = 0
    for section in sections:
        found = index.find(section['title'], cursor)
        if not found:
            unlocated += 1
            continue
        start, _end, norm_end = found
        cursor = norm_end
        located.append({**section, 'start': start})

    out: list[dict] = []
    # 第一個標題之前的文字（章首導言）不能丟
    head_end = located[0]['start'] if located else len(content)
    intro = content[:head_end].strip()
    if intro:
        out.append({
            'id': f'{chapter["id"]}#intro',
            'title': f'{chapter["title"]}（章首）',
            'level': 2,
            'page': None,
            'anchor': None,
            'recovered': False,
            'content': intro,
        })

    for i, section in enumerate(located):
        end = located[i + 1]['start'] if i + 1 < len(located) else len(content)
        body = content[section['start']:end].strip()
        if not body:
            continue
        out.append({
            'id': section['id'],
            'title': section['title'],
            'level': section['level'],
            'page': section['page'],
            'anchor': section['anchor'],
            'recovered': section['recovered'],
            'content': body,
        })
    return out, unlocated


def build_chunks(sections: list[dict], target_chars: int) -> list[dict]:
    """把小節合併成適合出題的區塊。

    切到最細之後中位數只有 180 字，撐不起一道題目；直接用整章又會被
    `generate_questions.py` 的 4000 字上限截掉。所以在階層上做貪婪切分：
    **一個標題連同其下所有子標題的完整範圍**若不超過 target 就整塊輸出，
    超過就往下一層拆。結果是互不重疊、合起來剛好蓋滿整章的區塊。
    """
    if not sections:
        return []

    # 每個小節的「完整範圍」= 到下一個同層或更淺的標題為止（涵蓋所有子標題）
    spans: list[tuple[int, int]] = []
    for i, section in enumerate(sections):
        end = len(sections)
        for j in range(i + 1, len(sections)):
            if sections[j]['level'] <= section['level']:
                end = j
                break
        spans.append((i, end))

    chunks: list[dict] = []

    def emit(start: int, end: int) -> None:
        """輸出 sections[start:end) 這一段，太大就沿子標題拆開。"""
        body = '\n\n'.join(s['content'] for s in sections[start:end]).strip()
        if not body:
            return
        head = sections[start]
        if len(body) <= target_chars or end - start <= 1:
            chunks.append({
                'id': head['id'],
                'title': head['title'],
                'level': head['level'],
                'page': head['page'],
                'anchor': head['anchor'],
                'sectionCount': end - start,
                'content': body,
            })
            return

        # 拆成「自己的文字」＋各個直屬子標題的完整範圍
        cursor = start + 1
        children: list[tuple[int, int]] = []
        while cursor < end:
            child_level = sections[cursor]['level']
            child_end = cursor + 1
            while child_end < end and sections[child_end]['level'] > child_level:
                child_end += 1
            children.append((cursor, child_end))
            cursor = child_end

        own_body = sections[start]['content'].strip()
        if own_body:
            chunks.append({
                'id': head['id'],
                'title': head['title'],
                'level': head['level'],
                'page': head['page'],
                'anchor': head['anchor'],
                'sectionCount': 1,
                'content': own_body,
            })
        for child_start, child_end in children:
            emit(child_start, child_end)

    cursor = 0
    while cursor < len(sections):
        _, end = spans[cursor]
        emit(cursor, end)
        cursor = end
    return chunks


def merge_small_chunks(chunks: list[dict], target_chars: int, min_chars: int) -> list[dict]:
    """把過短的區塊併進相鄰區塊。

    上面的切分只會往下拆、不會回頭合併，於是留下一堆只有標題沒有內文的碎塊
    （實測 372 個區塊裡有 94 個不到 300 字，最短的只有 17 字）。這種區塊
    出不了題，但每一個都要花一次 API 呼叫，所以在這裡往後併——保留第一個
    區塊的 id／標題／錨點當進入點，內容依序接起來。
    """
    merged: list[dict] = []
    for chunk in chunks:
        if merged and len(merged[-1]['content']) < min_chars:
            previous = merged[-1]
            combined = f"{previous['content']}\n\n{chunk['content']}".strip()
            # 併起來若會超過上限，寧可留著短的，也不要製造超過 4000 字的區塊
            # （generate_questions.py 會截斷）
            if len(combined) <= target_chars:
                previous['content'] = combined
                previous['sectionCount'] += chunk['sectionCount']
                previous['mergedTitles'] = previous.get('mergedTitles', []) + [chunk['title']]
                continue
        merged.append(dict(chunk))
    return merged


def export_level(level: str, subjects: tuple[int, ...], target_chars: int,
                 min_chars: int) -> None:
    hierarchy = load_json(HIERARCHY)['guides']
    out_dir = BASE / 'data' / level / 'guide_sections'
    out_dir.mkdir(parents=True, exist_ok=True)

    for subject_index in subjects:
        guide_path = BASE / 'data' / level / 'guide' / f'subject{subject_index}_guide.json'
        if not guide_path.exists():
            continue
        guide_data = load_json(guide_path)
        chapters = guide_data['chapters'] if isinstance(guide_data, dict) else guide_data

        # 章節 id 在哪一個科目的階層樹裡
        guide_by_chapter = {}
        for subject_id, guide in hierarchy.items():
            for node_id, node in guide['nodesById'].items():
                if node.get('kind') == 'section':
                    guide_by_chapter[node_id] = guide

        out_chapters = []
        total_sections = total_unlocated = 0
        for chapter in chapters:
            guide = guide_by_chapter.get(chapter['id'])
            sections = hierarchy_sections(guide, chapter['id']) if guide else []
            sliced, unlocated = slice_chapter(chapter, sections)
            total_sections += len(sliced)
            total_unlocated += unlocated
            chunks = merge_small_chunks(build_chunks(sliced, target_chars),
                                        target_chars, min_chars)
            out_chapters.append({
                'id': chapter['id'],
                'title': chapter['title'],
                'charCount': len(chapter.get('content') or ''),
                'sections': sliced,
                'chunks': chunks,
            })

        payload = {
            'level': level,
            'subject': guide_data.get('subject') if isinstance(guide_data, dict) else None,
            'chapters': out_chapters,
        }
        out_path = out_dir / f'subject{subject_index}.json'
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

        sizes = sorted(len(k['content']) for c in out_chapters for k in c['chunks'])
        n_chunks = len(sizes)
        print(f'{level}/subject{subject_index}: {len(out_chapters)} 章 → {total_sections} 小節 → '
              f'{n_chunks} 出題區塊（中位數 {sizes[n_chunks // 2] if sizes else 0} 字、'
              f'最長 {sizes[-1] if sizes else 0}、超過 {target_chars} 字的 '
              f'{sum(1 for x in sizes if x > target_chars)} 個、標題沒定位到 {total_unlocated} 個）')


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--level', choices=['初級', '中級'], help='預設兩級都跑')
    ap.add_argument('--target-chars', type=int, default=3000,
                    help='出題區塊的目標大小（預設 3000，generate_questions 上限是 4000）')
    ap.add_argument('--min-chars', type=int, default=300,
                    help='低於這個字數的區塊往後併（出不了題卻要花一次 API 呼叫）')
    args = ap.parse_args()

    for level in ([args.level] if args.level else ['初級', '中級']):
        export_level(level, (1, 2, 3), args.target_chars, args.min_chars)


if __name__ == '__main__':
    main()
