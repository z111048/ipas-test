#!/usr/bin/env python3
"""把學習指引的階層接成一棵完整的樹。

## 為什麼需要這支

現有資料裡階層是**斷成兩段**的：

  guideOutlines.json     科目 → 章 → 節（64 個節點），到「節」就停了
  guideContent/*.json    節以下的 2,131 個標題只存在於各章的 blocks[]／headings[]，
                         彼此之間沒有父子關係，也接不回 outline

兩段都是好的——2026-08-06 實測記號與層級的對應幾乎完美
（`N.` → h3 100%、`（N）` → h4 99%、`A.` → h5 100%、`a.` → h6 100%，
唯一的 6 個例外是 s1c4 那個刻意的手動修正）。缺的只是把它們接起來。

接起來之後：
  * 前端可以做完整目錄、麵包屑、深層側欄，而且**路由完全不用動**——
    節以下的節點是既有章節頁裡的錨點（`{route}#{anchor}`）。
  * 出題可以鎖定到小節而不是整章。這是本專案的核心目標
    （CLAUDE.md：「針對特定章節綜合出高品質模擬試題」），
    章的粒度太粗，一章動輒上萬字。

## 怎麼接

heading block 帶 `pageIndex`，outline 節點帶 `pageRange`，所以每個標題都掛到
**pageRange 包含它、且最深的那個 outline 節點**底下。不能直接掛給章，
因為章的 pageRange 涵蓋其下所有節，會整批重複。

標題之間再用 `depth` 以堆疊法還原父子關係。

## 輸出

`frontend/src/generated/guideHierarchy.json`

    {"guides": {<subjectId>: {"rootIds": [...], "nodesById": {...}, "flat": [...]}}}

每個節點：
    id / parentId / depth / kind(chapter|section|heading) / title / page / childIds
    route、pageRange 只有章/節節點有；標題節點沿用所屬章節的 route，範圍就是 page 本身。
    anchor 只有標題節點有，連結是 `{所屬章節 route}#{anchor}`。
    recovered=true 表示這個標題是從 guide_ocr 補回的，頁面上沒有對應區塊、捲不過去。

輸出刻意不縮排也不留可推導欄位——前端會把整份打進 GuidePage 的 chunk
（860 KB → 439 KB，gzip 87 KB → 68 KB）。

本腳本只讀既有產物、不改任何來源資料，可以隨時重跑。
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path

BASE = Path('/home/james/projects/ipas-test')
GENERATED = BASE / 'frontend' / 'src' / 'generated'
OUTLINES = GENERATED / 'guideOutlines.json'
CONTENT_DIR = GENERATED / 'guideContent'
OUT_PATH = GENERATED / 'guideHierarchy.json'


def load_json(path: Path):
    with path.open(encoding='utf-8') as f:
        return json.load(f)


def normalize(text: str) -> str:
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', text))


# 「1. 人工智慧的應用領域」這一層。Track A 的抽取在初級整本只認出 6 個，
# 但原書其實有（guide_ocr 的 page_0007 就有 `### 1. 人工智慧的應用領域`）。
SECTION_NUM_TITLE = re.compile(r'^\d+[.、]\s*\D')
# 練習頁的題號與答案行長得一樣，靠 pages_cache 的 type 濾掉整頁
ANSWER_LIKE = re.compile(r'Ans|答案|解析')


def ocr_page_headings(level: str, key: str) -> dict[int, list[str]]:
    """回傳 {1-based 頁碼: [該頁所有標題, 依原文順序]}，用來決定同頁內的先後。"""
    pages_dir = BASE / 'data' / level / 'guide_ocr' / key / 'pages'
    if not pages_dir.exists():
        return {}
    out: dict[int, list[str]] = {}
    for md_path in sorted(pages_dir.glob('page_[0-9]*/page_[0-9]*.md')):
        page_no = int(re.search(r'page_(\d+)\.md$', md_path.name).group(1))
        titles = [
            m.group(1).strip()
            for m in (re.match(r'^#{1,6}\s+(.*)$', line.strip())
                      for line in md_path.read_text(encoding='utf-8').splitlines())
            if m
        ]
        if titles:
            out[page_no] = titles
    return out


def ocr_numbered_titles(level: str, key: str) -> dict[int, list[str]]:
    """從 guide_ocr 撈出 `N.` 層標題，回傳 {1-based 頁碼: [標題, ...]}。

    Track A（page_extract → export_guide_outline_data）在部分書漏掉整個 `N.` 層，
    導致 `（N）` 直接掛到節底下、同一節出現好幾組重複的（1)(2)(3)。
    guide_ocr 有這些標題，這裡只拿來補洞，不覆蓋既有結果。
    """
    pages_dir = BASE / 'data' / level / 'guide_ocr' / key / 'pages'
    if not pages_dir.exists():
        return {}

    # 練習頁（模擬考題／考題解析）整頁跳過——題號行與小節標題無法從文字分辨
    skip_pages: set[int] = set()
    cache_dir = BASE / 'data' / level / 'pages_cache' / key
    if cache_dir.exists():
        for path in cache_dir.glob('page_[0-9]*.json'):
            page = load_json(path)
            if page.get('type') != 'content':
                skip_pages.add(page['idx'] + 1)

    out: dict[int, list[str]] = {}
    for md_path in sorted(pages_dir.glob('page_[0-9]*/page_[0-9]*.md')):
        page_no = int(re.search(r'page_(\d+)\.md$', md_path.name).group(1))
        if page_no in skip_pages:
            continue
        titles = []
        for line in md_path.read_text(encoding='utf-8').splitlines():
            match = re.match(r'^#{1,6}\s+(.*)$', line.strip())
            if not match:
                continue
            title = match.group(1).strip()
            if SECTION_NUM_TITLE.match(title) and not ANSWER_LIKE.search(title):
                titles.append(title)
        if titles:
            out[page_no] = titles
    return out


def deepest_node_for_page(nodes_by_id: dict, flat: list[str], page: int) -> str | None:
    """回傳 pageRange 包含 page 的最深節點；同深度取頁範圍最窄的。"""
    best = None
    best_key = None
    for node_id in flat:
        node = nodes_by_id[node_id]
        page_range = node.get('pageRange') or []
        if len(page_range) != 2:
            continue
        start, end = page_range
        if not (start <= page <= end):
            continue
        key = (node.get('depth', 0), -(end - start))
        if best_key is None or key > best_key:
            best, best_key = node_id, key
    return best


def chapter_headings(content: dict) -> list[dict]:
    """合併 blocks 與 headings[] 兩個來源，取得該章最完整的標題清單。

    兩者互補，缺一不可（2026-08-06 實測）：
      * `blocks` 的 heading 型區塊有 `pageIndex` 與 `anchor`，但**不一定完整**——
        例如初級 s1c1 的 blocks 只到 A. 層（61 個），缺整個 a. 層。
      * `headings[]` 由 content markdown 的 `#` 行解析，有 a. 層（81 個），
        但**沒有頁碼**，而且有些章整個是空的——例如中級 mid-s2c8 的 headings[] 是 []，
        該章的標題全在 blocks 裡。

    兩者的層級尺度一致（節=2、`N.`=3、`（N）`=4、`A.`=5、`a.`=6）。

    兩邊各自都是文件順序，但交錯合併需要對齊、容易錯位。改用比較穩的做法：
    **以項目較多的那一邊當主幹**（它比較完整），另一邊只用來按 anchor 補頁碼。
    主幹缺頁碼的項目沿用前一個已知頁——標題本來就依文件順序排列，不會跳頁。
    """
    block_items = []
    page_by_anchor: dict[str, int] = {}
    for block in content.get('blocks') or []:
        if block.get('type') != 'heading':
            continue
        title = (block.get('title') or '').strip()
        anchor = block.get('anchor')
        if not title or not anchor:
            continue
        if isinstance(block.get('pageIndex'), int):
            page_by_anchor.setdefault(anchor, block['pageIndex'])
        block_items.append({
            'title': title,
            'anchor': anchor,
            'depth': int(block.get('depth') or 2),
            'pageIndex': block.get('pageIndex'),
        })

    markdown_items = []
    for heading in content.get('headings') or []:
        anchor = heading.get('id')
        title = (heading.get('title') or '').strip()
        if not anchor or not title:
            continue
        markdown_items.append({
            'title': title,
            'anchor': anchor,
            'depth': int(heading.get('level') or 2),
            'pageIndex': page_by_anchor.get(anchor),
        })

    spine = markdown_items if len(markdown_items) > len(block_items) else block_items

    out: list[dict] = []
    seen: set[str] = set()
    last_page: int | None = None
    for item in spine:
        if item['anchor'] in seen:
            continue
        seen.add(item['anchor'])
        page_index = item.get('pageIndex')
        if isinstance(page_index, int):
            last_page = page_index
        else:
            item = {**item, 'pageIndex': last_page}
        out.append(item)
    return out


def slugify_anchor(text: str) -> str:
    """與 export_guide_outline_data.slugify_heading 同規則，錨點才對得上。"""
    slug = re.sub(r'\s+', '-', normalize(text).lower())
    slug = re.sub(r'[^0-9a-z一-鿿\-]+', '', slug)
    return slug.strip('-')


def fill_missing_section_layer(items: list[dict], page_range, numbered_titles: dict[int, list[str]],
                               covered_by_child, stats: dict,
                               page_headings: dict[int, list[str]] | None = None) -> list[dict]:
    """用 guide_ocr 的 `N.` 標題補回 Track A 漏抓的那一層，依頁碼插入正確位置。"""
    if not page_range or len(page_range) != 2 or not numbered_titles:
        return items

    existing = {normalize(i['title']) for i in items}
    additions: list[dict] = []
    for page in range(page_range[0], page_range[1] + 1):
        if covered_by_child(page):
            continue
        for title in numbered_titles.get(page, []):
            if normalize(title) in existing:
                continue
            existing.add(normalize(title))
            additions.append({
                'title': title,
                'anchor': slugify_anchor(title) or f'section-{page}',
                'depth': 3,
                'page': page,
                'recovered': True,
            })

    if not additions:
        return items
    stats['recovered'] = stats.get('recovered', 0) + len(additions)

    # 插回文件順序。只用頁碼不夠——同一頁常有多個標題，補回的「3. 資料處理與分析」
    # 會被插到同頁但實際在它前面的「E. 專家系統」之前，把 E. 變成它的子項。
    # 所以同頁內改用 OCR 該頁的標題順序決定先後。
    merged = list(items)
    for addition in sorted(additions, key=lambda a: a['page']):
        page = addition['page']
        order = [normalize(t) for t in (page_headings or {}).get(page, [])]
        try:
            own_rank = order.index(normalize(addition['title']))
        except ValueError:
            own_rank = -1

        index = None
        for i, item in enumerate(merged):
            item_page = item.get('page') or 0
            if item_page > page:
                index = i
                break
            if item_page < page:
                continue
            # 同一頁：比 OCR 順序，排在它後面的第一個既有標題就是插入點
            try:
                rank = order.index(normalize(item['title']))
            except ValueError:
                continue
            if own_rank >= 0 and rank > own_rank:
                index = i
                break
        merged.insert(len(merged) if index is None else index, addition)
    return merged


def build_guide(subject_id: str, guide: dict) -> dict:
    nodes_by_id = guide['nodesById']
    flat = guide['flat']
    # guide_ocr 用的是 sourceKey（guide1），guide['key'] 是 guideContent 的目錄名（初級-guide1）
    numbered_titles = ocr_numbered_titles(guide['level'], guide['sourceKey'])
    page_headings = ocr_page_headings(guide['level'], guide['sourceKey'])
    stats: dict = {}

    out_nodes: dict[str, dict] = {}
    out_flat: list[str] = []
    root_ids: list[str] = []

    # 1) outline 的章/節原樣搬過來
    for node_id in flat:
        src = nodes_by_id[node_id]
        out_nodes[node_id] = {
            'id': node_id,
            'parentId': src.get('parentId'),
            'depth': src.get('depth', 1),
            'kind': 'chapter' if src.get('depth', 1) <= 1 else 'section',
            'title': src.get('title') or '',
            'number': src.get('number'),
            'route': src.get('route'),
            'anchor': None,
            'href': src.get('route'),
            'page': (src.get('pageRange') or [None])[0],
            'pageRange': src.get('pageRange'),
            'childIds': [],
        }
        if not src.get('parentId'):
            root_ids.append(node_id)

    for node_id in flat:
        parent = out_nodes[node_id]['parentId']
        if parent and parent in out_nodes:
            out_nodes[parent]['childIds'].append(node_id)

    # 2) 每個 outline 節點只收自己 content 裡的標題。
    #    章的 pageRange 涵蓋其下所有節，content 也是節的聯集，所以有子節點的章
    #    只保留「子節點頁範圍沒涵蓋到」的標題（通常是章首那一兩頁），其餘留給節。
    #    早期版本改成「依頁碼掛給最深節點」，結果同一個節會同時收到來自章與節兩份
    #    抽取結果，兩邊的標題清單不同，合併後順序被打亂。
    collected: dict[str, list[dict]] = {}
    for node_id in flat:
        node = nodes_by_id[node_id]
        content_ref = node.get('contentRef')
        if not content_ref:
            continue
        content_path = CONTENT_DIR / guide['key'] / content_ref
        if not content_path.exists():
            continue

        child_ranges = [
            nodes_by_id[c].get('pageRange') or []
            for c in (node.get('children') or [])
        ]

        def covered_by_child(page: int | None) -> bool:
            return page is not None and any(
                len(r) == 2 and r[0] <= page <= r[1] for r in child_ranges
            )

        items = []
        for heading in chapter_headings(load_json(content_path)):
            page_index = heading.get('pageIndex')
            page = (page_index + 1) if isinstance(page_index, int) else None
            if covered_by_child(page):
                continue
            items.append({**heading, 'page': page})

        items = fill_missing_section_layer(items, node.get('pageRange'), numbered_titles,
                                           covered_by_child, stats, page_headings)
        if items:
            collected[node_id] = items

    # 3) 標題之間用 depth 堆疊還原父子關係，接在 outline 節點底下
    for owner_id, headings in collected.items():
        owner = out_nodes[owner_id]
        base_depth = owner['depth']
        stack: list[tuple[int, str]] = []  # (heading depth, node id)

        for index, heading in enumerate(headings, start=1):
            # 節本身的標題（例如「3.1 敘述性統計…」）就是 owner，不再另建節點
            if heading['title'].endswith(owner['title']) or heading['title'] == owner['title']:
                continue

            while stack and stack[-1][0] >= heading['depth']:
                stack.pop()
            parent_id = stack[-1][1] if stack else owner_id

            node_id = f'{owner_id}#{heading["anchor"]}'
            if node_id in out_nodes:
                node_id = f'{node_id}-{index}'
            out_nodes[node_id] = {
                'id': node_id,
                'parentId': parent_id,
                'depth': out_nodes[parent_id]['depth'] + 1,
                'kind': 'heading',
                'title': heading['title'],
                'number': None,
                'route': owner['route'],
                'anchor': heading['anchor'],
                'href': f'{owner["route"]}#{heading["anchor"]}',
                'page': heading['page'],
                'pageRange': [heading['page'], heading['page']] if heading['page'] else None,
                'childIds': [],
                'headingLevel': heading['depth'],
                'recovered': bool(heading.get('recovered')),
            }
            out_nodes[parent_id]['childIds'].append(node_id)
            stack.append((heading['depth'], node_id))

        _ = base_depth  # 保留變數名以說明 depth 是相對 owner 累加的

    # 4) 依樹序重排 flat
    def walk(node_id: str) -> None:
        out_flat.append(node_id)
        for child in out_nodes[node_id]['childIds']:
            walk(child)

    for node_id in root_ids:
        walk(node_id)

    return {
        'level': guide['level'],
        'subjectId': subject_id,
        'key': guide['key'],
        'subject': guide.get('subject'),
        'rootIds': root_ids,
        'nodesById': out_nodes,
        'flat': out_flat,
        'stats': {
            'recoveredFromOcr': stats.get('recovered', 0),
            'total': len(out_nodes),
            'outline': len(flat),
            'headings': len(out_nodes) - len(flat),
            'maxDepth': max((n['depth'] for n in out_nodes.values()), default=0),
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--print-tree', metavar='SUBJECT_ID',
                    help='把某一科的樹印出來檢查，如 s1 / mid-s2')
    args = ap.parse_args()

    outlines = load_json(OUTLINES)
    guides = {
        subject_id: build_guide(subject_id, guide)
        for subject_id, guide in outlines['guides'].items()
    }

    if args.print_tree:
        guide = guides[args.print_tree]
        for node_id in guide['flat']:
            node = guide['nodesById'][node_id]
            marker = '§' if node['kind'] == 'heading' else '#'
            print('  ' * node['depth'] + f'{marker} {node["title"][:56]}'
                  + (f'  p{node["page"]}' if node['page'] else ''))
        return

    # 前端會把整份 JSON 打進 GuidePage 的 chunk，所以把可推導或恆為 null 的欄位拿掉：
    #   href   = route + '#' + anchor
    #   route（標題節點）= 所屬章節節點的 route
    #   pageRange（標題節點）= [page, page]
    # 需要這些欄位的消費端自己組回來即可。indent 也拿掉（縮排佔了近三成體積）。
    for guide in guides.values():
        for node in guide['nodesById'].values():
            node.pop('href', None)
            if node['kind'] == 'heading':
                node.pop('route', None)
                node.pop('pageRange', None)
            if node.get('number') is None:
                node.pop('number', None)
            if not node.get('recovered'):
                node.pop('recovered', None)

    OUT_PATH.write_text(
        json.dumps({'levels': outlines.get('levels'), 'guides': guides},
                   ensure_ascii=False, separators=(',', ':')),
        encoding='utf-8')
    total = sum(g['stats']['total'] for g in guides.values())
    print(f'寫入 {OUT_PATH.relative_to(BASE)}（{total} 節點）')
    for subject_id, guide in guides.items():
        s = guide['stats']
        print(f'  {subject_id:<8} 共 {s["total"]:>4}（章節 {s["outline"]}、標題 {s["headings"]}）'
              f' 最深 {s["maxDepth"]} 層')


if __name__ == '__main__':
    main()
