#!/usr/bin/env python3
"""學習指引「本章脈絡」資料：驗證 data/context_maps/ 並匯出給前端。

來源（人工策展、committed）：
  data/context_maps/chapters/<nodeId>.json   每章一份脈絡圖（格式見 data/context_maps/SCHEMA.md）
  data/context_maps/source_notes.json         已核對 PDF 的原書疑誤註記
輸出（產物）：
  frontend/src/generated/contextMaps/<nodeId>.json

驗證規則（任一不符即 exit 1，不寫任何檔）：
  * 章節必須存在於 guideOutlines.json（不在此硬編章節清單）。
  * 每個知識點、關係的引用句，去空白後必須逐字出現在所引區塊（6–40 字）。
  * 重點（gist）裡的數字必須出現在所引區塊原文。
  * concept 必須在受控詞彙表，且一章只能掛在一個知識點（避免考題數重複顯示）。
  * 文案不得透露教材由 AI 生成。
  * 疑誤註記的 contains 必須仍在該區塊原文（區塊編號變動時 fail closed）。

衍生欄位：每個知識點的考題數（conceptGraph）、引用頁碼、本章考古題常考但圖上沒有的概念；
初級章節裡原文找不到的概念，若中級脈絡圖有對應知識點，附上中級章節的段落連結。

用法：
  python3 scripts/export_context_maps.py           # 驗證並寫出
  python3 scripts/export_context_maps.py --check   # 只驗證，並確認產物與來源一致
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
SOURCE_DIR = BASE / 'data/context_maps/chapters'
NOTES_PATH = BASE / 'data/context_maps/source_notes.json'
GENERATED = BASE / 'frontend/src/generated'
OUT_DIR = GENERATED / 'contextMaps'

BANNED_COPY = re.compile(r'AI\s*生成|模型產生|由\s*AI|人工智慧生成|機器生成')
EXAM_ONLY_MIN = 3


def ws(value: str) -> str:
    return re.sub(r'\s+', '', value)


def block_text(block: dict[str, Any]) -> str:
    text = ' '.join(str(block.get(key) or '') for key in ('text', 'title', 'marker'))
    text += ' ' + re.sub(r'</?[A-Za-z][^<>]*>', ' ', str(block.get('html') or ''))
    if block.get('rows'):
        text += ' ' + json.dumps(block['rows'], ensure_ascii=False)
    return text


def block_number(block_id: str) -> int:
    return int(block_id.split('-')[1])


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def vocabulary(graph: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], set[str]]:
    by_name: dict[str, dict[str, Any]] = {}
    for concept in graph['concepts']:
        for name in [concept['name'], *concept.get('previousNames', [])]:
            by_name[name] = concept
    names = set(by_name)
    topics_path = BASE / 'data/topics/topics.json'
    if topics_path.exists():
        def walk(value: Any) -> None:
            if isinstance(value, dict):
                if isinstance(value.get('name'), str):
                    names.add(value['name'])
                for item in value.values():
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)
        walk(load_json(topics_path))
    return by_name, names


def build() -> tuple[dict[str, dict[str, Any]], list[str]]:
    outlines = load_json(GENERATED / 'guideOutlines.json')['guides']
    route_by_key = {guide['key']: subject_id for subject_id, guide in outlines.items()}
    graph = load_json(GENERATED / 'conceptGraph.json')
    by_name, names = vocabulary(graph)
    notes_by_node: dict[str, list[dict[str, Any]]] = {}
    for note in load_json(NOTES_PATH)['notes']:
        notes_by_node.setdefault(note['nodeId'], []).append(note)

    errors: list[str] = []
    maps: dict[str, dict[str, Any]] = {}

    for path in sorted(SOURCE_DIR.glob('*.json')):
        data = load_json(path)
        chapter = data['chapter']
        nid, guide_key = chapter['nodeId'], chapter['guideKey']
        where = f'{path.name}'
        subject_id = route_by_key.get(guide_key)
        if path.stem != nid:
            errors.append(f'{where}: 檔名與 nodeId {nid} 不符')
        if not subject_id or nid not in outlines[subject_id]['nodesById']:
            errors.append(f'{where}: 章節 {guide_key}/{nid} 不在 guideOutlines.json')
            continue
        content_ref = outlines[subject_id]['nodesById'][nid]['contentRef']
        content = load_json(GENERATED / 'guideContent' / guide_key / content_ref)
        blocks = {block_number(block['id']): block for block in content['blocks']}
        err: list[str] = []

        def page(number: int) -> int | None:
            block = blocks.get(number)
            return block['pageIndex'] + 1 if block and isinstance(block.get('pageIndex'), int) else None

        def check_quote(number: int, quote: str, label: str) -> None:
            if number not in blocks:
                err.append(f'{label}: block {number} 不存在')
                return
            if not 6 <= len(ws(quote)) <= 40:
                err.append(f'{label}: 引用長度 {len(ws(quote))} 不在 6–40')
            if ws(quote) not in ws(block_text(blocks[number])):
                err.append(f'{label}: 引用不在 block-{number} 原文：「{quote}」')

        lanes = {lane['id'] for lane in data['lanes']}
        if not 2 <= len(lanes) <= 4:
            err.append(f'分區數 {len(lanes)} 不在 2–4')
        if not 3 <= len(data['story']) <= 5:
            err.append(f'脈絡線站數 {len(data["story"])} 不在 3–5')
        nodes = {node['id']: node for node in data['nodes']}
        if len(nodes) != len(data['nodes']):
            err.append('知識點 id 重複')
        if not 12 <= len(nodes) <= 30:
            err.append(f'知識點數 {len(nodes)} 不在 12–30')
        if sum(node.get('lane') is None for node in data['nodes']) != 1:
            err.append('核心知識點必須恰好一個')
        concept_counts: dict[str, int] = {}
        for item in graph['concepts']:
            for ref in item['chapters']:
                if ref['nodeId'] == nid:
                    concept_counts[item['name']] = ref['count']
        for node in data['nodes']:
            label = f'知識點 {node["id"]}'
            if node.get('lane') is not None and node['lane'] not in lanes:
                err.append(f'{label}: 分區不存在')
            parent = node.get('parent')
            if parent is not None and (parent not in nodes or nodes[parent].get('lane') not in (None, node.get('lane'))):
                err.append(f'{label}: parent {parent} 不合法')
            if len(node['gist']) > 60:
                err.append(f'{label}: 重點 {len(node["gist"])} 字，超過 60')
            if not node.get('src'):
                err.append(f'{label}: 沒有出處')
            for src in node.get('src', []):
                check_quote(src['block'], src['quote'], label)
                src['page'] = page(src['block'])
            cited = ''.join(ws(block_text(blocks[src['block']])) for src in node.get('src', []) if src['block'] in blocks)
            for number in re.findall(r'\d+(?:\.\d+)?', node['gist']):
                if number not in cited:
                    err.append(f'{label}: 重點中的數字 {number} 不在引用原文')
            concept = node.get('concept')
            if concept and concept not in names:
                err.append(f'{label}: concept「{concept}」不在詞彙表')
            canonical = by_name.get(concept or '')
            node['exam'] = concept_counts.get(canonical['name'], 0) if canonical else 0
        for concept, count in Counter(node.get('concept') for node in data['nodes'] if node.get('concept')).items():
            if count > 1:
                err.append(f'concept「{concept}」掛在 {count} 個知識點')
        for index, edge in enumerate(data['edges']):
            label = f'關係 {index} {edge["a"]}→{edge["b"]}'
            if edge['a'] not in nodes or edge['b'] not in nodes:
                err.append(f'{label}: 知識點不存在')
            if edge['kind'] not in ('flow', 'cross'):
                err.append(f'{label}: kind 不合法')
            if len(edge['label']) > 14:
                err.append(f'{label}: 標籤超過 14 字')
            check_quote(edge['block'], edge['quote'], label)
            edge['page'] = page(edge['block'])
        if sum(edge['kind'] == 'cross' for edge in data['edges']) < 5:
            err.append('跨段落關聯少於 5 條')
        if not 3 <= len(data['confusions']) <= 8:
            err.append('易混淆組數不在 3–8')
        for pair in data['confusions']:
            if len(pair['text']) > 70:
                err.append(f'易混淆 {pair["a"]}: 說明超過 70 字')
            for number in pair['blocks']:
                if number not in blocks:
                    err.append(f'易混淆 {pair["a"]}: block {number} 不存在')
            pair['pages'] = sorted({p for p in (page(number) for number in pair['blocks']) if p})
        for gap in data['gaps']:
            if gap['block'] not in blocks:
                err.append(f'缺口 {gap["name"]}: block 不存在')
            gap['page'] = page(gap['block'])
        texts = [data['headline'], data['lede'], *(s['title'] + s['text'] for s in data['story']),
                 *(n['label'] + n['gist'] for n in data['nodes']), *(c['text'] for c in data['confusions'])]
        for text in texts:
            if BANNED_COPY.search(text):
                err.append(f'文案不得透露生成方式：{text[:30]}')

        used = {canonical['name'] for node in data['nodes']
                if (canonical := by_name.get(node.get('concept') or ''))}
        chapter_text = ws(''.join(block_text(block) for block in blocks.values()))
        data['examOnly'] = [
            {'name': name, 'count': count, 'mentioned': ws(name) in chapter_text}
            for name, count in sorted(concept_counts.items(), key=lambda item: (-item[1], item[0]))
            if count >= EXAM_ONLY_MIN and name not in used
        ]

        notes = []
        for note in notes_by_node.pop(nid, []):
            number = note['block']
            if number not in blocks or note['contains'] not in block_text(blocks[number]):
                err.append(f'疑誤註記 block-{number}: 原文已找不到「{note["contains"]}」')
                continue
            notes.append({'block': number, 'page': page(number), 'text': note['text']})
        data['notes'] = notes
        data['chapter'] = {**chapter, 'subjectId': subject_id, 'title': outlines[subject_id]['nodesById'][nid]['title']}
        errors += [f'{nid}: {message}' for message in err]
        maps[nid] = data

    for nid in notes_by_node:
        errors.append(f'疑誤註記指向沒有脈絡圖的章節 {nid}')

    link_cross_level(maps, by_name, graph)
    return maps, errors


def link_cross_level(
    maps: dict[str, dict[str, Any]], by_name: dict[str, dict[str, Any]], graph: dict[str, Any],
) -> None:
    """初級章節原文找不到的考古題概念 → 中級脈絡圖上有同一概念的知識點。"""
    counts = {(item['name'], ref['nodeId']): ref['count'] for item in graph['concepts'] for ref in item['chapters']}
    targets: dict[str, list[tuple[int, str, dict[str, Any]]]] = {}
    for nid, data in maps.items():
        if not data['chapter']['guideKey'].startswith('中級'):
            continue
        for node in data['nodes']:
            canonical = by_name.get(node.get('concept') or '')
            if canonical:
                targets.setdefault(canonical['name'], []).append((counts.get((canonical['name'], nid), 0), nid, node))
    for data in maps.values():
        if not data['chapter']['guideKey'].startswith('初級'):
            continue
        for item in data['examOnly']:
            if item['mentioned']:
                continue
            # 只連到中級脈絡圖上掛了同一概念的知識點（概念對應經過審查）。不用詞面比對備援：
            # 初級考的「任務分解」是代理式 AI 拆解任務，中級正文同名的卻是專案管理的時程規劃。
            if item['name'] not in targets:
                continue
            _, nid, node = sorted(targets[item['name']], key=lambda entry: (-entry[0], entry[1]))[0]
            target = maps[nid]['chapter']
            item['link'] = {
                'subjectId': target['subjectId'],
                'chapterId': nid,
                'block': node['src'][0]['block'],
                'chapterTitle': target['title'],
                'label': node['label'],
            }


def serialize(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=1) + '\n'


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--check', action='store_true', help='只驗證，並確認產物與來源一致')
    args = parser.parse_args()
    maps, errors = build()
    if errors:
        for message in errors:
            print(f'✗ {message}')
        print(f'{len(errors)} 個錯誤，未寫出任何檔案')
        return 1
    expected = {f'{nid}.json': serialize(data) for nid, data in maps.items()}
    if args.check:
        actual = {path.name: path.read_text(encoding='utf-8') for path in OUT_DIR.glob('*.json')} if OUT_DIR.exists() else {}
        stale = sorted(name for name in expected.keys() | actual.keys() if expected.get(name) != actual.get(name))
        if stale:
            print(f'✗ 產物與來源不一致，請重跑 export_context_maps.py：{", ".join(stale[:10])}')
            return 1
        print(f'✓ {len(maps)} 章脈絡圖驗證通過，產物一致')
        return 0
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in OUT_DIR.glob('*.json'):
        if path.name not in expected:
            path.unlink()
    for name, text in expected.items():
        target = OUT_DIR / name
        if not target.exists() or target.read_text(encoding='utf-8') != text:
            target.write_text(text, encoding='utf-8')
    nodes = sum(len(data['nodes']) for data in maps.values())
    links = sum('link' in item for data in maps.values() for item in data['examOnly'])
    notes = sum(len(data['notes']) for data in maps.values())
    print(f'✓ 寫出 {len(maps)} 章（知識點 {nodes}、跨級連結 {links}、疑誤註記 {notes}）→ {OUT_DIR.relative_to(BASE)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
