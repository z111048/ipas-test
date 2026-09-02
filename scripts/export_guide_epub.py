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
import hashlib
import html
import zipfile
from pathlib import Path

from export_notebooklm_pack import (
    GENERATED,
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


def esc(text: str) -> str:
    return html.escape(text or "", quote=False)


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
            level = min(max(item["level"], 3), 6)
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


def markdown_table_to_html(text: str) -> str:
    rows = [line for line in text.split("\n") if line.strip().startswith("|")]
    if len(rows) < 2:
        return f"<p>{esc(text)}</p>"

    def cells(line: str) -> list[str]:
        return [c.strip().replace("\\|", "|") for c in line.strip().strip("|").split("|")]

    head = cells(rows[0])
    body = [cells(line) for line in rows[2:]]
    out = ["<table>", "<thead><tr>"]
    out.extend(f"<th>{esc(c)}</th>" for c in head)
    out.append("</tr></thead><tbody>")
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


def build_book(level: str, subject_id: str, outlines: dict, hierarchy: dict,
               errata, counter: Counter) -> tuple[str, bytes, dict]:
    guide = outlines["guides"][subject_id]
    nodes = guide.get("nodesById") or {}
    hier_nodes = ((hierarchy.get("guides") or {}).get(subject_id) or {}).get("nodesById") or {}
    content_dir = GENERATED / "guideContent" / guide["key"]
    subject_title = guide.get("subject") or subject_id
    book_title = f"iPAS AI應用規劃師（{level}）學習指引・{subject_title}"

    loaded = {}
    for node_id in guide.get("flat") or []:
        path = content_dir / f"{node_id}.json"
        if path.exists():
            loaded[node_id] = load_json(path)

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

    payload = write_epub(book_title, level, subject_title, documents, assets, errata, counter)
    filename = f"{level}-{subject_title.replace('：', '-').replace('/', '／')}.epub"
    return filename, payload, {"chapters": len(documents), "images": len(assets)}


def write_epub(title: str, level: str, subject_title: str,
               documents, assets: dict[str, Path], errata, counter: Counter) -> bytes:
    uid = "urn:uuid:" + hashlib.sha1(title.encode("utf-8")).hexdigest()[:32]
    files: dict[str, bytes] = {}

    files["META-INF/container.xml"] = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
        '  <rootfiles><rootfile full-path="OEBPS/content.opf" '
        'media-type="application/oebps-package+xml"/></rootfiles>\n</container>\n'
    ).encode("utf-8")
    files["OEBPS/style.css"] = STYLESHEET.encode("utf-8")

    front = (
        f"<h1>{esc(title)}</h1>\n"
        f'<p class="note">{esc(FRONT_NOTE)}</p>\n'
    )
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
            f"<body>\n{apply_errata(content, errata, counter)}\n</body>\n</html>\n"
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
                  f"（{stats['chapters']} 章、{stats['images']} 張插圖）")
            lines.append(f"- `{filename}`（{stats['chapters']} 章、內嵌 {stats['images']} 張插圖）")
        print(f"{level}：官方勘誤套用 {sum(counter.values())} 處")

    (out_dir / "說明.md").write_text(README.format(files="\n".join(lines)), encoding="utf-8")
    print(f"\n→ {out_dir}（另含 說明.md）")


if __name__ == "__main__":
    main()
