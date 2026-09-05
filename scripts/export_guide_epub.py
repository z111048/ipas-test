#!/usr/bin/env python3
"""把 5 份官方學習指引各匯出成一個 EPUB（初級 2 本、中級 3 本）。

跟 export_notebooklm_pack.py 的差別：這裡只出**學習指引正文**，不含考題、練習題、
詳解與名詞解釋；而且 EPUB 可以內嵌圖片，所以原書的 17 張插圖會真的放進去，
不像 Markdown 版只能留一行位置標記。

內容來源與處理方式與 export_notebooklm_pack.py 完全相同（共用同一批函式）：
從 Track A 的 `blocks[]` 重建（`.content` 的標題被降級成裸編號，不能用），
再自己套一次官方勘誤（勘誤只存在於 `.content`，沒有進 blocks）。

輸出：exports/epub/{檔名}.epub（產物，不進版控）
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import html
import re
import zipfile
from pathlib import Path

from export_notebooklm_pack import (
    GENERATED,
    PLACEHOLDER_HEAD,
    LEVELS,
    REPO,
    apply_errata,
    block_items,
    clean_text,
    errata_rules,
    leaf_index,
    load_json,
    parent_only_blocks,
    prune_items,
    squash,
)
from collections import Counter

ASSET_ROOT = REPO / "frontend" / "public"
MEDIA_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
               ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml"}

STYLESHEET = """\
html { font-size: 100%; }
body { font-family: serif; line-height: 1.7; margin: 0 5%; }
h1 { font-size: 1.6em; line-height: 1.35; margin: 1.4em 0 .2em; }
h2 { font-size: 1.3em; line-height: 1.4; margin: 1.8em 0 .4em;
     border-bottom: 1px solid #bbb; padding-bottom: .2em; }
h3 { font-size: 1.12em; margin: 1.5em 0 .3em; }
h4 { font-size: 1.02em; margin: 1.3em 0 .3em; }
h5, h6 { font-size: .98em; margin: 1.1em 0 .3em; color: #333; }
p { margin: .55em 0; text-align: justify; }
p.folio { font-size: .78em; color: #777; margin: 1.1em 0 .3em;
          border-left: 3px solid #ccc; padding-left: .6em; text-align: left; }
p.tex { font-family: monospace; font-size: .9em; background: #f4f4f4;
        padding: .5em .7em; text-align: left; white-space: pre-wrap; }
ul { margin: .4em 0; padding-left: 1.2em; }
li { margin: .25em 0; }
li.d4 { margin-left: .9em; }
li.d5 { margin-left: 1.8em; }
li.d6 { margin-left: 2.7em; }
table { border-collapse: collapse; width: 100%; margin: .9em 0; font-size: .86em; }
th, td { border: 1px solid #999; padding: .32em .5em; text-align: left;
         vertical-align: top; }
th { background: #eee; }
figure { margin: 1.1em 0; text-align: center; }
figure img { max-width: 100%; }
figcaption { font-size: .82em; color: #555; margin-top: .4em; }
p.note { font-size: .85em; color: #444; background: #f6f6f6;
         padding: .7em .9em; border-left: 3px solid #999; text-align: left; }
"""

FRONT_NOTE = (
    "本電子書整理自經濟部 iPAS「AI 應用規劃師」官方學習指引。原始 PDF 的章節標題、"
    "部分小標題與表格表頭是圖片而非文字，此版本的文字由頁面影像辨識還原，"
    "小節標題用字可能與書上印的略有出入，公式、表格與跨頁順序也可能有殘留錯誤。"
    "〔原書 X-Y 頁〕標的是講義的印刷頁碼，可據以回頭核對原始 PDF。"
    "任何與官方 PDF 不一致之處，以官方 PDF 為準。"
)

SCOPE_NOTE = (
    "【收錄範圍】本書只收學習指引的正文。原書各章章末的模擬考題與解析共 {exercises} 題"
    "未收錄，需要練習題請看原始 PDF。"
)

ERRATA_NOTE = (
    "【官方勘誤】本書適用官方勘誤 {total} 筆：{applied} 筆由本工具套用、"
    "{already} 筆內文已是修正後的內容、{unknown} 筆無法確認"
    "（勘誤原文與影像辨識還原的文字有出入，或該筆勘誤指向未收錄的頁面）。"
    "無法確認的部分請以官方勘誤表為準。"
)


def esc(text: str) -> str:
    return html.escape(text or "", quote=False)


def errata_state(original: str, corrected: str, flat: str) -> str:
    """內文目前是勘誤前還是勘誤後的版本？回傳 corrected / original / unknown。

    不能用整段字串的相似度判斷：多數勘誤是詞級小修（反饋→回饋、支持→支援），
    original 與 corrected 有九成以上字元相同，整段比對兩邊都會「命中」。
    正確做法是只看**兩者相異的片段**，各自加上前後文再去內文裡找。
    """
    o, c = squash(original), squash(corrected)
    if not o or not c:
        return "unknown"
    ctx = 6
    votes = {"corrected": 0, "original": 0}
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, o, c).get_opcodes():
        if tag == "equal":
            continue
        o_probe = o[max(0, i1 - ctx):i2 + ctx]
        c_probe = c[max(0, j1 - ctx):j2 + ctx]
        if len(o_probe) < 6 or len(c_probe) < 6:
            continue
        in_o, in_c = o_probe in flat, c_probe in flat
        if in_c and not in_o:
            votes["corrected"] += 1
        elif in_o and not in_c:
            votes["original"] += 1
    if votes["corrected"] and not votes["original"]:
        return "corrected"
    if votes["original"] and not votes["corrected"]:
        return "original"
    return "unknown"


def items_to_xhtml(items, images: dict[str, str]) -> list[str]:
    """把中介 item 串轉成 XHTML；連續的 list_item 併成一個 <ul>。"""
    out: list[str] = []
    open_list = False

    def close_list() -> None:
        nonlocal open_list
        if open_list:
            out.append("</ul>")
            open_list = False

    for item in items:
        kind = item["t"]
        text = item["text"]
        if kind == "heading":
            close_list()
            # 用 depth 而非 level：小節標題已是 h2，來源 depth 3 就該是 h3。
            # level 是給 Markdown 版用的（那邊沒有 h2 這一層），沿用會讓全書從 h2 直接跳 h4。
            level = min(max(item.get("depth") or 3, 3), 6)
            out.append(f'<h{level}>{esc(text)}</h{level}>')
            continue
        if kind == "page":
            close_list()
            out.append(f'<p class="folio">{esc(text)}</p>')
            continue

        if text.startswith("|"):  # markdown 表格
            close_list()
            out.append(markdown_table_to_html(text))
            continue
        if text.startswith("> 【原書插圖】"):
            close_list()
            out.append(image_figure(text, images))
            continue
        if text.lstrip().startswith("- "):
            stripped = text.lstrip()
            depth = 3 + (len(text) - len(stripped)) // 2
            if not open_list:
                out.append("<ul>")
                open_list = True
            body = stripped[2:]
            out.append(f'<li class="d{min(depth, 6)}">{inline(body)}</li>')
            continue

        close_list()
        if text.startswith("$$") or text.startswith("$"):
            out.append(f'<p class="tex">{esc(text)}</p>')
        else:
            out.append(f"<p>{inline(text)}</p>")
    close_list()
    return out


def inline(text: str) -> str:
    """段落內可能夾著 $$ 公式區塊（block_body 用兩個換行接起來）。"""
    parts = text.split("\n\n")
    rendered = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if part.startswith("$"):
            rendered.append(f'<span class="tex">{esc(part)}</span>')
        else:
            rendered.append(esc(part))
    return "<br />".join(rendered)


SPLIT_CELLS = re.compile(r"(?<!\\)\|")   # 跳脫過的 \| 是儲存格內容，不是欄位分隔


def markdown_table_to_html(text: str) -> str:
    rows = [line for line in text.split("\n") if line.strip().startswith("|")]
    if len(rows) < 2:
        return f"<p>{esc(text)}</p>"

    def cells(line: str) -> list[str]:
        # 先依「未跳脫的 |」切欄，再還原跳脫；順序顛倒的話書名裡的
        # 「圖解 AI | 機器學習…」會被切成兩欄並留下反斜線
        inner = line.strip()
        inner = re.sub(r"^\|", "", inner)
        inner = re.sub(r"(?<!\\)\|$", "", inner)
        return [c.strip().replace("\\|", "|") for c in SPLIT_CELLS.split(inner)]

    head = cells(rows[0])
    body = [cells(line) for line in rows[2:]]
    # render_table 判定這張表沒有真表頭時會補「欄1/欄2…」佔位——不要輸出 <thead>，
    # 否則等於憑空捏造一個表頭給讀者
    fake = all(re.fullmatch(rf"{PLACEHOLDER_HEAD}\d+", c or "") for c in head) if head else False
    out = ["<table>"]
    if not fake:
        out.append("<thead><tr>")
        out.extend(f"<th>{esc(c)}</th>" for c in head)
        out.append("</tr></thead>")
    out.append("<tbody>")
    for row in body:
        out.append("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in row) + "</tr>")
    out.append("</tbody></table>")
    return "".join(out)


def image_figure(text: str, images: dict[str, str]) -> str:
    """把 Markdown 版的插圖佔位換成真的 <img>，找不到檔案就退回文字說明。"""
    caption = text.replace("> 【原書插圖】", "").strip()
    src = images.pop("__next__", None)
    if not src:
        return f'<p class="note">{esc(caption)}</p>'
    return (f'<figure><img src="../{src}" alt="{html.escape(caption, quote=True)}" />'
            f"<figcaption>{esc(caption)}</figcaption></figure>")


def collect_images(node: dict) -> list[tuple[str, Path]]:
    found = []
    for block in node.get("blocks") or []:
        if block.get("type") != "source_image":
            continue
        src = (block.get("src") or "").lstrip("/")
        path = ASSET_ROOT / src
        if path.exists():
            found.append((src, path))
    return found


FRONT_MATTER_NOTE = (
    "本章是原書正文之前的「序」與「職能基準」。這兩頁不在學習指引的章節結構內，"
    "文字改由另一條頁面辨識軌還原，未經與正文相同的校對流程，"
    "表格與細節請以官方 PDF 為準。"
)

TOC_LEADER = re.compile(r"\.{4,}")          # 目錄頁的點線


def _sanitize_track_b_html(fragment: str) -> str:
    """Track B 的 markdown 夾帶原始 HTML 表格，屬性帶單引號且有裸 <br>——先清成合法 XHTML。"""
    out = re.sub(r"<(table|tr|td|th)\b[^>]*>", r"<\1>", fragment)
    out = re.sub(r"<br\s*/?>", "<br />", out)
    out = re.sub(r"<(?!/?(?:table|tr|td|th|br\s*/)\b)[^>]*>", "", out)
    return out


def render_front_matter(level: str, guide_key: str, body_start_page: int) -> str:
    """把正文之前的「序」「職能基準」補成一章。

    這兩頁從來沒進過 Track A 的章節樹（章節樹從第一章才開始），
    所以五本 EPUB 一直缺這段——連帶讓指向「職能基準」頁的官方勘誤永遠無從套用。
    封面與目錄不收：封面沒有內文，目錄由 EPUB 自己的 nav 取代。
    """
    cache = REPO / "data" / level / "pages_cache" / guide_key
    if not cache.is_dir():
        return ""
    parts: list[str] = []
    for page_index in range(0, max(0, body_start_page - 1)):
        path = cache / f"page_{page_index:03d}.json"
        if not path.is_file():
            continue
        markdown = str(load_json(path).get("markdown") or "").strip()
        if len(re.findall(r"[一-鿿]", markdown)) < 60:
            continue                      # 封面之類幾乎沒有內文的頁
        if len(TOC_LEADER.findall(markdown)) >= 3:
            continue                      # 目錄頁
        for chunk in re.split(r"\n{2,}", markdown):
            chunk = chunk.strip()
            if not chunk:
                continue
            heading = re.match(r"^(#{1,6})\s+(.*)$", chunk)
            if heading:
                # Track B 的最上層是 ###，而本章的 h1 是「書前資料」——
                # 直接照搬會變成 h1 → h3 的跳階
                level_tag = min(max(len(heading.group(1)) - 1, 2), 6)
                parts.append(f"<h{level_tag}>{esc(clean_text(heading.group(2)))}</h{level_tag}>")
            elif chunk.lstrip().startswith("<table"):
                parts.append(_sanitize_track_b_html(chunk))
            else:
                parts.append(f"<p>{esc(clean_text(chunk))}</p>")
    if not parts:
        return ""
    return (f"<h1>書前資料</h1>\n<p class=\"note\">{esc(FRONT_MATTER_NOTE)}</p>\n"
            + "\n".join(parts))


def build_book(level: str, subject_id: str, outlines: dict, hierarchy: dict,
               errata, counter: Counter) -> tuple[str, bytes, dict]:
    guide = outlines["guides"][subject_id]
    nodes = guide.get("nodesById") or {}
    hier_nodes = ((hierarchy.get("guides") or {}).get(subject_id) or {}).get("nodesById") or {}
    content_dir = GENERATED / "guideContent" / guide["key"]
    subject_title = guide.get("subject") or subject_id
    book_title = f"iPAS AI應用規劃師（{level}）學習指引・{subject_title}"

    loaded = {}
    exercises = 0
    for node_id in guide.get("flat") or []:
        path = content_dir / f"{node_id}.json"
        if path.exists():
            loaded[node_id] = load_json(path)
            if not (nodes.get(node_id) or {}).get("children"):
                # 章末練習題被 block_items 刻意排除，書前說明要向讀者交代題數
                exercises += sum(1 for b in (loaded[node_id].get("blocks") or [])
                                 if b.get("type") == "question")

    leaf_prints, corpus = leaf_index(loaded, nodes)

    assets: dict[str, Path] = {}
    documents: list[tuple[str, str, list[tuple[str, str]]]] = []  # (title, xhtml, [(anchor,title)])
    body: list[str] = []
    current_title = None
    current_anchors: list[tuple[str, str]] = []

    def flush() -> None:
        if current_title is None:
            return
        documents.append((current_title, "\n".join(body), list(current_anchors)))

    for node_id in guide.get("flat") or []:
        node = loaded.get(node_id)
        if node is None:
            continue
        meta = nodes.get(node_id) or {}
        hier = hier_nodes.get(node_id) or {}
        is_parent = bool(meta.get("children"))

        if hier.get("kind") == "chapter" or is_parent:
            flush()
            current_title = clean_text(hier.get("title") or meta.get("title") or node_id)
            body = [f"<h1>{esc(current_title)}</h1>"]
            current_anchors = []

        if is_parent:
            own = {
                "sourcePages": node.get("sourcePages"),
                "blocks": parent_only_blocks(node, leaf_prints, corpus),
            }
            items = [
                item for item in prune_items(block_items(own))
                if not (item["t"] == "body" and squash(current_title).endswith(squash(item["text"])))
            ]
            body.extend(items_to_xhtml(items, {}))
            continue

        if hier.get("kind") != "chapter":
            number = meta.get("number")
            title = clean_text(meta.get("title") or node.get("title") or node_id)
            heading = f"{number} {title}".strip() if number else title
            anchor = f"sec-{node_id}"
            current_anchors.append((anchor, heading))
            body.append(f'<h2 id="{anchor}">{esc(heading)}</h2>')

        node_images = collect_images(node)
        image_map: dict[str, str] = {}
        queue = list(node_images)
        for src, path in node_images:
            assets[f"images/{Path(src).parent.name}_{Path(src).name}"] = path

        rendered = []
        for item in prune_items(block_items(node, skip_chapter_heading=True)):
            if item["t"] == "body" and item["text"].startswith("> 【原書插圖】"):
                if queue:
                    src, _path = queue.pop(0)
                    image_map["__next__"] = f"images/{Path(src).parent.name}_{Path(src).name}"
            rendered.extend(items_to_xhtml([item], image_map))
        body.extend(rendered)

    flush()

    body_start = min(
        (page.get("page") for node in loaded.values()
         for page in (node.get("sourcePages") or [])
         if isinstance(page, dict) and page.get("page")),
        default=5,
    )
    front_matter = render_front_matter(level, (guide.get("key") or "").split("-")[-1], body_start)
    if front_matter:
        documents.insert(0, ("書前資料", front_matter, []))

    payload = write_epub(book_title, level, subject_title, documents, assets, errata,
                         counter, exercises=exercises,
                         guide_key=(guide.get("key") or "").split("-")[-1])
    filename = f"{level}-{subject_title.replace('：', '-').replace('/', '／')}.epub"
    return filename, payload, {"chapters": len(documents), "images": len(assets),
                               "exercises": exercises}


def write_epub(title: str, level: str, subject_title: str,
               documents, assets: dict[str, Path], errata, counter: Counter,
               exercises: int = 0, guide_key: str = "") -> bytes:
    uid = "urn:uuid:" + hashlib.sha1(title.encode("utf-8")).hexdigest()[:32]
    files: dict[str, bytes] = {}

    files["META-INF/container.xml"] = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
        '  <rootfiles><rootfile full-path="OEBPS/content.opf" '
        'media-type="application/oebps-package+xml"/></rootfiles>\n</container>\n'
    ).encode("utf-8")
    files["OEBPS/style.css"] = STYLESHEET.encode("utf-8")

    # 勘誤要先套用完才知道實際命中幾處——書前說明要報這個數字，
    # 不能像以前那樣只寫「已套用官方勘誤」卻拿不出筆數（實測 28 筆只中 4 筆）
    book_counter: Counter = Counter()
    # 命中筆數要在替換前用 pattern 逐條數——counter 的 key 是「key + page_label」，
    # 同一頁有兩筆勘誤時會併成一個 key，直接數 key 會少算
    # 只算**本書**適用的勘誤：errata 是整個等級的，直接用 len() 會把別本的也算進來
    mine = [r for r in errata if not guide_key or (r[2].get("key") or "") == guide_key]
    raw_all = "\n".join(c for _, c, _ in documents)
    flat = squash(raw_all)
    applied = already = unknown = 0
    for pattern, corrected, entry in mine:
        if pattern.search(raw_all):
            applied += 1                       # 這一輪由本工具替換
            continue
        state = errata_state(entry.get("original", ""), corrected, flat)
        if state == "corrected":
            already += 1                       # 上游（Track A／overlay）早就修好了
        else:
            unknown += 1                       # 仍是原文，或兩者都比對不到
    unmatched = unknown
    documents = [(t, apply_errata(c, errata, book_counter), a) for t, c, a in documents]
    counter.update(book_counter)

    notes = [FRONT_NOTE]
    if exercises:
        notes.append(SCOPE_NOTE.format(exercises=exercises))
    if mine:
        notes.append(ERRATA_NOTE.format(total=len(mine), applied=applied,
                                        already=already, unknown=unknown))
    front = f"<h1>{esc(title)}</h1>\n" + "\n".join(
        f'<p class="note">{esc(n)}</p>' for n in notes) + "\n"
    documents = [("書前說明", front, [])] + list(documents)

    spine, manifest, nav_items = [], [], []
    for index, (chapter_title, content, anchors) in enumerate(documents):
        name = f"text/ch{index:02d}.xhtml"
        page = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE html>\n'
            '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="zh-TW" lang="zh-TW">\n'
            f"<head><meta charset=\"utf-8\"/><title>{esc(chapter_title)}</title>"
            '<link rel="stylesheet" type="text/css" href="../style.css"/></head>\n'
            f"<body>\n{content}\n</body>\n</html>\n"
        )
        files[f"OEBPS/{name}"] = page.encode("utf-8")
        item_id = f"ch{index:02d}"
        manifest.append(f'<item id="{item_id}" href="{name}" media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="{item_id}"/>')
        nav_items.append((name, chapter_title, anchors))

    for index, (name, path) in enumerate(sorted(assets.items())):
        files[f"OEBPS/{name}"] = path.read_bytes()
        media = MEDIA_TYPES.get(path.suffix.lower(), "image/png")
        manifest.append(f'<item id="img{index:03d}" href="{name}" media-type="{media}"/>')

    nav_body = ["<nav epub:type=\"toc\" id=\"toc\"><h1>目次</h1><ol>"]
    for name, chapter_title, anchors in nav_items:
        nav_body.append(f'<li><a href="{name}">{esc(chapter_title)}</a>')
        if anchors:
            nav_body.append("<ol>")
            nav_body.extend(f'<li><a href="{name}#{a}">{esc(t)}</a></li>' for a, t in anchors)
            nav_body.append("</ol>")
        nav_body.append("</li>")
    nav_body.append("</ol></nav>")
    files["OEBPS/nav.xhtml"] = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE html>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" '
        'xml:lang="zh-TW" lang="zh-TW">\n<head><meta charset="utf-8"/><title>目次</title>'
        '<link rel="stylesheet" type="text/css" href="style.css"/></head>\n<body>\n'
        + "\n".join(nav_body) + "\n</body>\n</html>\n"
    ).encode("utf-8")

    opf = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="pub-id">\n'
        '  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
        f'    <dc:identifier id="pub-id">{uid}</dc:identifier>\n'
        f"    <dc:title>{esc(title)}</dc:title>\n"
        "    <dc:language>zh-TW</dc:language>\n"
        "    <dc:creator>經濟部產業人才能力鑑定 iPAS</dc:creator>\n"
        f"    <dc:subject>{esc(level)}</dc:subject>\n"
        f"    <dc:description>{esc(subject_title)}　學習指引正文</dc:description>\n"
        '    <meta property="dcterms:modified">2026-09-03T00:00:00Z</meta>\n'
        "  </metadata>\n  <manifest>\n"
        '    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>\n'
        '    <item id="css" href="style.css" media-type="text/css"/>\n    '
        + "\n    ".join(manifest)
        + "\n  </manifest>\n  <spine>\n    "
        + "\n    ".join(spine)
        + "\n  </spine>\n</package>\n"
    )
    files["OEBPS/content.opf"] = opf.encode("utf-8")

    import io
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        # mimetype 必須是第一個檔且不壓縮，否則部分閱讀器會拒收
        archive.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip",
                         compress_type=zipfile.ZIP_STORED)
        for name, payload in files.items():
            archive.writestr(name, payload, compress_type=zipfile.ZIP_DEFLATED)
    return buffer.getvalue()


README = """\
# iPAS AI 應用規劃師 學習指引（EPUB）

這五個檔案是經濟部 iPAS「AI 應用規劃師」官方學習指引的全文，
初級 2 本、中級 3 本，可以直接上傳到 NotebookLM，或用一般電子書閱讀器開啟。

## 檔案

{files}

## 為什麼不直接用原始 PDF

原始 PDF 的章節標題、約三成的小標題與表格表頭是**圖片**不是文字。
直接匯入的話，「3.1 人工智慧概念」只會剩下「3.1」，表格會塌成交錯的欄位，
公式的分子分母會各佔一行。這五個 EPUB 的文字是由頁面影像辨識還原的，
標題、表格與公式都是完整的，原書的插圖也內嵌在書裡。

## 使用方式

1. 到 notebooklm.google.com 新增一個 notebook。
2. 上傳你要用的 EPUB（初級與中級建議分開兩個 notebook）。
3. 開始提問。問題愈具體愈好，例如
   「用學習指引的原文解釋鑑別式 AI 與生成式 AI 的差異，並指出是哪一章」。

## 讀這份資料時要知道的事

- 文字是影像辨識還原的，小節標題用字可能與書上印的略有出入，
  公式、表格與跨頁順序也可能有殘留錯誤。**以官方 PDF 為準。**
- 每換一頁會標〔原書 3-24 頁〕，那是講義的印刷頁碼，方便回頭核對原書。
- 原書插圖只有 17 張被單獨切出並內嵌，其餘圖表沒有進到書裡。
  需要判讀圖形時仍要看原始 PDF。
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="把 5 份學習指引匯出成 EPUB")
    parser.add_argument("--level", choices=["初級", "中級", "all"], default="all")
    parser.add_argument("--out", default=str(REPO / "exports" / "epub"))
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    outlines = load_json(GENERATED / "guideOutlines.json")
    hierarchy = load_json(GENERATED / "guideHierarchy.json")

    lines = []
    for level in (list(LEVELS) if args.level == "all" else [args.level]):
        manifest = load_json(REPO / "data" / level / "toc_manifest.json")
        errata = errata_rules(level)
        counter: Counter = Counter()
        for subject in manifest.get("subjects") or []:
            subject_id = subject.get("id")
            if subject_id not in (outlines.get("guides") or {}):
                continue
            filename, payload, stats = build_book(level, subject_id, outlines, hierarchy,
                                                  errata, counter)
            (out_dir / filename).write_bytes(payload)
            size_mb = len(payload) / 1024 / 1024
            print(f"  {size_mb:6.2f} MB  {filename}"
                  f"（{stats['chapters']} 章、{stats['images']} 張插圖、"
                  f"排除 {stats['exercises']} 題章末練習）")
            lines.append(f"- `{filename}`（{stats['chapters']} 章、內嵌 {stats['images']} 張插圖）")
        print(f"{level}：官方勘誤套用 {sum(counter.values())} 處")

    (out_dir / "說明.md").write_text(README.format(files="\n".join(lines)), encoding="utf-8")
    print(f"\n→ {out_dir}（另含 說明.md）")


if __name__ == "__main__":
    main()
