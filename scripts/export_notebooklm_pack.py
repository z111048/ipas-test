#!/usr/bin/env python3
"""把講義、公告試題、參考詳解、練習題與名詞解釋匯出成 NotebookLM 可直接匯入的 Markdown。

為什麼不直接丟原始 PDF：這 5 本學習指引的章節標題、28.5% 的「N.」小標題與表格表頭在 PDF 裡是
圖片化文字（內容流中只有「3.1」這種裸編號），任何純文字層解析器都讀不到；公式被攤平、
表格塌成交錯欄、每頁夾入頁首頁尾。本 repo 的 Track A production 內容
（frontend/src/generated/guideContent/）已由頁面影像辨識復原標題與表格、轉成 LaTeX 公式，
所以匯出的是這一軌。

兩個必須知道的來源特性：
1. leaf 節點的 `.content` 字串同樣帶著「標題被降級成裸編號」的缺陷，完整標題只在 `.blocks[]`。
   本腳本一律從 blocks 重建，不使用 `.content`。
2. 但官方勘誤只套在 `.content`，沒有套進 `blocks[]`。所以本腳本在輸出前自己再跑一次
   errata_corrections.json 的字串替換，並把實際套用筆數寫進檔頭，不做無根據的宣稱。

輸入（全部是既有產物，本腳本只讀不寫）：
  frontend/src/generated/guideOutlines.json          章節樹（判定 leaf、章號、頁碼）
  frontend/src/generated/guideHierarchy.json         大章標題（第三章…，blocks 裡沒有）
  frontend/src/generated/guideContent/<key>/*.json   講義正文 blocks（Track A production）
  frontend/src/generated/examReferenceAnswers/*.json 逐題參考詳解
  frontend/src/generated/{primary,middle}Glossary.json 名詞解釋
  frontend/src/generated/topicHeat.json              考點熱度
  data/resource_catalog.json                         考卷 SSOT
  data/{level}/toc_manifest.json                     章節 SSOT
  data/{level}/errata_corrections.json               官方勘誤
  data/{level}/questions/*.json                      公告試題／章節練習／學習指引練習

輸出：exports/notebooklm/{level}/*.md（產物，不進版控）
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GENERATED = REPO / "frontend" / "src" / "generated"

LEVELS = {"初級": "junior", "中級": "middle"}
GLOSSARY_FILE = {"初級": "primaryGlossary.json", "中級": "middleGlossary.json"}

# 單檔字元上限。NotebookLM 官方 FAQ 載明單一來源上限 500,000 words / 200MB，
# 這裡取更保守的值，超過就照考卷邊界拆檔。
MAX_FILE_CHARS = 400_000

INTERNAL_TAG = re.compile(r"^(mid-)?s\d+(c\d+)?$")
STRUCTURAL_TAG = {"章首導覽", "章節導覽", "前言與章節導覽"}
CODEX_SUFFIX = re.compile(r"_codex100$")
# 講義裡少量 Unicode 數學字母數字符號（𝑦𝑖、𝑛）是 PDF 公式被攤平的殘留；
# 整段 NFKC 會連全形括號一起改掉，所以只正規化這個區塊。
MATH_ALPHANUMERIC = re.compile(r"[\U0001D400-\U0001D7FF]")
# Wingdings/Symbol 私用區碼點，在任何字型下都是豆腐字。
PRIVATE_USE = re.compile(r"[-]")

# 參考詳解是以檢索到的講義段落為依據寫成的，行文裡留下了「檢索片段」這類工作術語。
# 對讀者而言那是雜訊，指涉的東西就是講義本身。
RAG_GUARDS = [
    "程式碼片段", "程式片段", "影片片段", "文字片段", "文件片段", "音訊片段", "語音片段",
    "視訊片段", "圖像片段", "影像片段", "局部片段", "時間片段", "資料片段", "句子片段",
]
RAG_PHRASES = [
    ("檢索到的片段", "講義段落"),
    ("檢索片段", "講義段落"),
    ("檢索結果", "講義段落"),
    ("此片段", "這段講義"),
    ("該片段", "該段講義"),
    ("這些片段", "這些講義段落"),
]
RAG_SUFFIX = re.compile(r"片段(中|裡|說明|指出|列出|提到|雖未|未|顯示|所述)")

GUIDE_NOTE = (
    "本檔整理自經濟部 iPAS 官方學習指引。原 PDF 的章節標題、部分小標題與表格表頭是圖片，"
    "文字層讀不到，這裡的文字是由頁面影像辨識還原的，小節標題的用字可能與書上印的略有出入；"
    "公式、表格與跨頁順序也可能有殘留錯誤。任何與官方 PDF 不一致的地方，以官方 PDF 為準。"
)
EXAM_NOTE = (
    "題目、選項與答案照錄自經濟部 iPAS 官方公告試題。官方只公布答案、未公布解析，"
    "「參考詳解」是本教材自行編寫的解析，不代表官方立場；與官方答案不符時以官方為準。"
)
PRACTICE_NOTE = (
    "依講義章節整理的練習題，用來檢查每一章的觀念是否讀懂。這些不是官方考題，"
    "官方題請看「10-官方試題與參考詳解」。"
)
EXERCISE_NOTE = "這是官方學習指引 PDF 章末附的練習題與解答，屬於官方素材。"
GLOSSARY_NOTE = (
    "名詞釋義由本教材依講義與歷屆考題內容整理，方便快速查閱；正式定義以官方學習指引原文為準。"
)


def load_json(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def squash(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def clean_text(text: str) -> str:
    """把數學斜體字元換回 ASCII，並清掉私用區豆腐字。"""
    if not text:
        return text
    text = MATH_ALPHANUMERIC.sub(lambda m: unicodedata.normalize("NFKC", m.group(0)), text)
    return PRIVATE_USE.sub("", text)


def strip_rag_phrases(text: str) -> str:
    """參考詳解的行文留有「檢索片段」這類工作術語，對讀者是雜訊；指涉的就是講義本身。
    但「程式碼片段」「影片片段」這些是考科名詞，不能一起換掉，所以先護起來。"""
    guards = {}
    for index, term in enumerate(RAG_GUARDS):
        if term in text:
            token = f"\x00{index}\x00"
            guards[token] = term
            text = text.replace(term, token)
    for needle, replacement in RAG_PHRASES:
        text = text.replace(needle, replacement)
    text = RAG_SUFFIX.sub(r"講義段落\1", text)
    for token, term in guards.items():
        text = text.replace(token, term)
    return text


EXPLANATION_PREFIX = re.compile(r"^(?:解析[:：]\s*)+")


def strip_explanation_prefix(text: str | None) -> str:
    """來源的 explanation 有時已經帶「解析：」前綴，甚至帶兩層。"""
    return EXPLANATION_PREFIX.sub("", clean_text((text or "").strip()))


def clean_id(value: str) -> str:
    return CODEX_SUFFIX.sub("", value or "")


# --- 官方勘誤 -----------------------------------------------------------------

def errata_rules(level: str) -> list[tuple[re.Pattern, str, dict]]:
    """勘誤的 original 字串與講義的空白排版不一定一致，所以比對時允許任意空白。"""
    path = REPO / "data" / level / "errata_corrections.json"
    if not path.exists():
        return []
    rows = load_json(path)
    rows = rows if isinstance(rows, list) else rows.get("corrections") or []
    rules = []
    for entry in rows:
        original, corrected = entry.get("original"), entry.get("corrected")
        if not original or not corrected:
            continue
        squashed = squash(original)
        if len(squashed) < 8:
            continue  # 太短的字串容易誤傷
        pattern = re.compile(r"\s*".join(re.escape(char) for char in squashed))
        rules.append((pattern, corrected.strip(), entry))
    return rules


def apply_errata(text: str, rules, counter: Counter) -> str:
    for pattern, corrected, entry in rules:
        # corrected 可能含 LaTeX 反斜線，要用 lambda 當替換字串，否則會被當成跳脫序列
        text, hits = pattern.subn(lambda _match, value=corrected: value, text)
        if hits:
            counter[f"{entry.get('key', '')} {entry.get('page_label', '')}"] += hits
    return text


# --- 講義 ---------------------------------------------------------------------

ENUMERATOR = re.compile(r"^(?:\d{1,2}[.、]|[（(]\d{1,2}[）)]|[A-Za-z][.、])")


def block_fingerprint(block: dict) -> str:
    return squash((block.get("text") or "") + (block.get("title") or ""))


def leaf_index(loaded: dict, nodes: dict) -> tuple[set, str]:
    """子章 block 的精確指紋，加上一份子章全文（用來抓跨頁被切一半的段落）。"""
    prints, parts = set(), []
    for node_id, node in loaded.items():
        if (nodes.get(node_id) or {}).get("children"):
            continue
        for block in node.get("blocks") or []:
            merged = block_fingerprint(block)
            prints.add((block.get("type"), merged))
            parts.append(merged)
    return prints, "".join(parts)


def parent_only_blocks(node: dict, prints: set, corpus: str) -> list[dict]:
    """父節點的 block 絕大多數與子章重複，只留下真正獨有的（＝章導言）。"""
    kept = []
    for block in node.get("blocks") or []:
        merged = block_fingerprint(block)
        if (block.get("type"), merged) in prints:
            continue
        # 章導言常在句首多一個「1.」「（1）」之類的編號，去掉才對得上子章正文
        bare = ENUMERATOR.sub("", merged)
        if len(bare) >= 10 and (merged in corpus or bare in corpus):
            continue
        kept.append(block)
    return kept


def page_labels(node: dict) -> dict[int, dict]:
    return {p["index"]: p for p in node.get("sourcePages") or [] if "index" in p}


def source_tables(node: dict) -> dict[int, list[list]]:
    """sourcePages 版的表格保有真正的表頭，blocks 版常常把表頭攤平成空白。"""
    out: dict[int, list[list]] = {}
    for page in node.get("sourcePages") or []:
        for table in page.get("tables") or []:
            rows = table.get("rows")
            if rows and page.get("index") is not None:
                out.setdefault(page["index"], rows)
    return out


def formula_markdown(block: dict) -> list[str]:
    formulas = block.get("formulas")
    if not formulas:
        latex = block.get("latex")
        if isinstance(latex, list):
            formulas = [{"latex": item, "display": True} for item in latex]
        elif latex:
            formulas = [{"latex": latex, "display": True}]
    out = []
    for formula in formulas or []:
        latex = (formula.get("latex") or "").strip()
        if latex:
            out.append(f"${latex}$" if formula.get("display") is False else f"$$\n{latex}\n$$")
    return out


def residual_prose(text: str) -> str:
    """formulaOnly 的 text 是被攤平的公式，但有時後面還黏著一整句正文，不能一起丟。"""
    cleaned = clean_text(text or "")
    # 從最後一個數學殘骸之後切，保留仍有實質中文的尾巴
    tail = re.split(r"[=∑∫√∏≈≤≥\)\]]\s*", cleaned)[-1].strip()
    tail = re.sub(r"^[^\u4e00-\u9fff]+", "", tail)  # 去掉開頭殘留的符號與單字母
    return tail if len(re.findall(r"[一-鿿]", tail)) >= 8 else ""


def block_body(block: dict) -> str:
    formulas = formula_markdown(block)
    text = clean_text((block.get("text") or "").strip())
    if not formulas:
        return text
    if block.get("formulaOnly"):
        tail = residual_prose(block.get("text") or "")
        return "\n\n".join(formulas + ([tail] if tail else []))
    return "\n\n".join(([text] if text else []) + formulas)


# 沒有真表頭時補一列**空的**表頭（markdown 表格語法一定要有表頭列）。
# 早期是補「欄1/欄2/欄3」，但那等於對讀者與 NotebookLM 注入不存在的欄位名稱；
# EPUB 端據「表頭整列皆空」判斷這張表沒有真表頭，不輸出 <thead>。


def looks_like_header(row: list[str], nxt: list[str] | None) -> bool:
    """rows[0] 真的是表頭嗎？

    來源表格常常根本沒有表頭列——第一列可能是圖說、跨頁續接內容，
    或被 Track A 攤平成空白。盲目拿 rows[0] 當表頭會**憑空捏造一個表頭**，
    並把真正的第一筆資料吃掉。2026-09-05 稽核：34 張表有 14 張中招。
    """
    filled = [c for c in row if c]
    if len(filled) <= max(1, len(row) - 2):
        return False                      # 幾乎全空
    if row and row[0].rstrip().endswith(("：", ":")):
        return False                      # 其實是圖說，例如「常見的統計方法可做以下分類：」
    if len(filled) != len(set(filled)):
        return False                      # 重複欄名，例如 ['', 'AI', 'AI']
    if nxt and row and not row[0] and not nxt[0]:
        return False                      # 表頭被切成兩列，交給 merge_split_header 處理
    return True


def merge_split_header(rows: list[list[str]]) -> list[list[str]] | None:
    """表頭跨兩行被切成兩列時併回一列。

    例：rows[0]=['', 'AI', 'AI']、rows[1]=['', 'Generative AI', 'Discriminative AI']
    ——原書是「生成式 AI（Generative AI）」這種兩行儲存格，Track A 切成了兩列。
    """
    if len(rows) < 3 or len(rows[0]) != len(rows[1]):
        return None
    if rows[0][0] or rows[1][0]:
        return None
    if not any(rows[0][1:]) or not any(rows[1][1:]):
        return None
    merged = [" ".join(x for x in (a, b) if x).strip() for a, b in zip(rows[0], rows[1])]
    return [merged] + rows[2:]


TOC_LEADER = re.compile(r"\.{4,}")
HTML_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
HTML_CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)


def _html_table_to_rows(fragment: str) -> list[list[str]]:
    """Track B 的 markdown 夾帶原始 HTML 表格，轉成 rows 好交給 render_table。"""
    rows = []
    for row in HTML_ROW.findall(fragment):
        cells = [clean_text(re.sub(r"<[^>]+>", " ", cell)) for cell in HTML_CELL.findall(row)]
        if cells:
            rows.append(cells)
    return rows


def render_front_matter(level: str, guide_key: str, body_start_page: int) -> str:
    """正文之前的「序」與「職能基準」。

    這兩頁從來不在章節樹裡（樹從第一章才開始），Track A 因此完全沒有它們，
    連帶讓指向「職能基準」頁的官方勘誤永遠無從套用。改由 Track B 的
    `pages_cache` 補回。封面與目錄不收：封面沒有內文，目錄由本檔自己的標題結構取代。
    """
    cache = REPO / "data" / level / "pages_cache" / guide_key
    if not cache.is_dir():
        return ""
    out: list[str] = []
    for page_index in range(0, max(0, body_start_page - 1)):
        path = cache / f"page_{page_index:03d}.json"
        if not path.is_file():
            continue
        markdown = str(load_json(path).get("markdown") or "").strip()
        if len(re.findall(r"[一-鿿]", markdown)) < 60 or len(TOC_LEADER.findall(markdown)) >= 3:
            continue
        for chunk in re.split(r"\n{2,}", markdown):
            chunk = chunk.strip()
            if not chunk:
                continue
            heading = re.match(r"^(#{1,6})\s+(.*)$", chunk)
            if heading:
                out.append(f"\n### {clean_text(heading.group(2))}\n")
            elif chunk.lstrip().startswith("<table"):
                table = render_table(_html_table_to_rows(chunk))
                if table:
                    out.append(table)
            else:
                out.append(clean_text(chunk))
    if not out:
        return ""
    return ("\n## 書前資料\n\n"
            "> 本節是原書正文之前的「序」與「職能基準」，不在學習指引的章節結構內；\n"
            "> 文字由另一條頁面辨識軌還原，未經與正文相同的校對流程，細節以官方 PDF 為準。\n\n"
            + "\n\n".join(out) + "\n")


def render_table(rows: list[list]) -> str:
    if not rows:
        return ""
    width = max(len(row) for row in rows)

    def cell(value) -> str:
        return clean_text(re.sub(r"\s*\n\s*", " ", str(value or ""))).replace("|", "\\|").strip()

    body = [[cell(v) for v in row] + [""] * (width - len(row)) for row in rows]
    merged = merge_split_header(body)
    if merged is not None:
        body = merged
    # 沒有可用的表頭時補一列佔位——EPUB 端會據此不輸出 <thead>，
    # 而不是把第一列資料誤當表頭（markdown 表格語法一定要有表頭列）
    if not looks_like_header(body[0], body[1] if len(body) > 1 else None):
        body.insert(0, [""] * width)
    lines = ["| " + " | ".join(body[0]) + " |", "|" + "---|" * width]
    lines.extend("| " + " | ".join(row) + " |" for row in body[1:])
    return "\n".join(lines)


def block_items(node: dict, skip_chapter_heading: bool = False) -> list[dict]:
    """把一個節點的 blocks 轉成中介 item 串，之後再統一清掉空標題與孤兒頁碼標記。"""
    labels = page_labels(node)
    tables = source_tables(node)
    items: list[dict] = []
    last_page = None

    for block in node.get("blocks") or []:
        kind = block.get("type")
        if kind in {"question", "answer"}:
            continue  # 章末練習題另成一檔（21-），留在講義裡會讓同一批題目出現兩次

        page_index = block.get("pageIndex")
        if page_index is not None and page_index != last_page:
            meta = labels.get(page_index)
            if meta and meta.get("label"):
                # label 另外帶著：EPUB 端要拿它做 epub:type="pagebreak" 的錨點與 page-list
                items.append({"t": "page", "label": str(meta["label"]),
                              "text": f"〔原書 {meta['label']} 頁 · PDF 第 {meta['page']} 頁〕"})
            last_page = page_index

        if kind == "heading":
            depth = block.get("depth") or 3
            if depth <= 2 and skip_chapter_heading:
                continue  # 節標題已經由 outline 那邊印過，這裡再印一次就是重複
            title = clean_text(block.get("title") or "")
            if title:
                # depth 3/4/5 → #### / ##### / ######，不壓平，否則父子標題會變成兄弟
                items.append({"t": "heading", "level": min(depth + 1, 6), "depth": depth, "text": title})
            continue

        if kind == "table":
            rows = tables.get(page_index) if not any(block.get("rows", [[]])[0]) else None
            table = render_table(rows or block.get("rows") or [])
            if table:
                items.append({"t": "body", "text": table})
            continue

        if kind == "source_image":
            page_no = labels.get(page_index, {}).get("page", (page_index or 0) + 1)
            alt = clean_text(block.get("alt") or "未命名")
            items.append({"t": "body", "text": f"> 【原書插圖】{alt}（PDF 第 {page_no} 頁）"
                                               "——圖片內容未轉為文字，需要判讀圖形時請看原始 PDF。"})
            continue

        text = block_body(block)
        if not text:
            continue
        if kind == "list_item":
            marker = (block.get("marker") or "").strip()
            indent = "  " * max(0, min((block.get("depth") or 3) - 3, 3))
            label = "" if marker in {"", "•", "‧", "·", "◆", "▪", "-", "◦", "○"} else f"{marker} "
            if text.startswith("$$"):
                items.append({"t": "body", "text": f"{indent}- {label}".rstrip() + "\n\n" + text})
            else:
                items.append({"t": "body", "text": f"{indent}- {label}{text}"})
        else:
            items.append({"t": "body", "text": text})
    return items


def prune_items(items: list[dict]) -> list[dict]:
    """丟掉後面沒有內容的頁碼標記，以及底下完全空白的標題。"""
    keep = [True] * len(items)
    for index, item in enumerate(items):
        if item["t"] == "page":
            keep[index] = any(
                later["t"] == "body" for later in items[index + 1:index + 2]
            ) or any(later["t"] == "body" for later in items[index + 1:] [:1])
        elif item["t"] == "heading":
            has_body = False
            for later in items[index + 1:]:
                if later["t"] == "heading" and later.get("depth", 9) <= item.get("depth", 0):
                    break
                if later["t"] == "body":
                    has_body = True
                    break
            keep[index] = has_body
    # page 標記要看它到下一個 page/heading 之間有沒有 body
    for index, item in enumerate(items):
        if item["t"] != "page":
            continue
        has_body = False
        for later in items[index + 1:]:
            if later["t"] == "page":
                break
            if later["t"] == "body":
                has_body = True
                break
        keep[index] = has_body
    return [item for index, item in enumerate(items) if keep[index]]


def items_to_markdown(items: list[dict]) -> str:
    out = []
    for item in items:
        if item["t"] == "heading":
            out.append(f"\n{'#' * item['level']} {item['text']}\n")
        elif item["t"] == "page":
            out.append(f"\n{item['text']}\n")
        else:
            out.append(item["text"] if item["text"].startswith(("-", " ")) else "\n" + item["text"] + "\n")
    return "\n".join(out)


def guide_files(level: str, outlines: dict, hierarchy: dict, manifest: dict,
                errata: list) -> tuple[list[tuple[str, str]], Counter]:
    files = []
    counter: Counter = Counter()
    for order, subject in enumerate(manifest.get("subjects") or [], start=1):
        subject_id = subject.get("id")
        guide = (outlines.get("guides") or {}).get(subject_id)
        if not guide:
            continue
        nodes = guide.get("nodesById") or {}
        hier_nodes = ((hierarchy.get("guides") or {}).get(subject_id) or {}).get("nodesById") or {}
        content_dir = GENERATED / "guideContent" / guide["key"]
        subject_title = guide.get("subject") or subject_id

        loaded = {}
        for node_id in guide.get("flat") or []:
            path = content_dir / f"{node_id}.json"
            if path.exists():
                loaded[node_id] = load_json(path)

        # 大章（第三章…）的正文導言只存在於父節點，leaf-only 會整段漏掉
        leaf_prints, leaf_corpus = leaf_index(loaded, nodes)

        body = [
            f"# {level}｜{subject_title}",
            "",
            f"資料類型：官方學習指引正文｜等級：{level}｜科目：{subject_title}",
            "",
            f"> {GUIDE_NOTE}",
            f"> 來源 PDF：`{guide.get('pdf', '')}`",
            "> 〔原書 X-Y 頁〕是講義的印刷頁碼，方便回頭對照原始 PDF。",
            "> 本檔只有正文；書上章末的練習題與解答另見「21-學習指引練習」。",
            "",
        ]

        body_start = min(
            (page.get("page") for node in loaded.values()
             for page in (node.get("sourcePages") or [])
             if isinstance(page, dict) and page.get("page")),
            default=5,
        )
        front_matter = render_front_matter(level, (guide.get("key") or "").split("-")[-1],
                                           body_start)
        if front_matter:
            body.append(front_matter)

        for node_id in guide.get("flat") or []:
            node = loaded.get(node_id)
            if node is None:
                continue
            meta = nodes.get(node_id) or {}
            hier = hier_nodes.get(node_id) or {}
            is_parent = bool(meta.get("children"))

            if hier.get("kind") == "chapter" or is_parent:
                title = clean_text(hier.get("title") or meta.get("title") or node_id)
                body.append(f"\n## {title}\n")

            if is_parent:
                # 只收父節點獨有的 block（章導言），子章正文由 leaf 自己輸出
                own = {
                    "sourcePages": node.get("sourcePages"),
                    "blocks": parent_only_blocks(node, leaf_prints, leaf_corpus),
                }
                items = [
                    item for item in prune_items(block_items(own))
                    # 章導言第一行常常就是章名本身，剛剛已經當標題印過了
                    if not (item["t"] == "body" and squash(title).endswith(squash(item["text"])))
                ]
                if items:
                    body.append(items_to_markdown(items))
                continue

            if hier.get("kind") != "chapter":
                number = meta.get("number")
                title = clean_text(meta.get("title") or node.get("title") or node_id)
                body.append(f"\n### {f'{number} {title}'.strip() if number else title}\n")
            body.append(items_to_markdown(prune_items(block_items(node, skip_chapter_heading=True))))

        text = apply_errata("\n".join(body), errata, counter)
        files.append((f"{order:02d}-學習指引-{subject_title.replace('：', '-').replace('/', '／')}.md", text))
    return files, counter


# --- 考題與詳解 ---------------------------------------------------------------

def reference_lookup(references: dict, question_id: str, legacy_prefix: str | None):
    hit = references.get(question_id)
    if hit:
        return hit
    match = re.search(r"_q(\d+)$", question_id or "")
    if not match:
        return None
    if legacy_prefix:
        hit = references.get(f"{legacy_prefix}_q{match.group(1)}")
        if hit:
            return hit
    candidates = [k for k in references if k.endswith(f"_q{match.group(1)}")]
    return references[candidates[0]] if len(candidates) == 1 else None


def exam_files(level: str, catalog: dict) -> list[tuple[str, str]]:
    """題目與詳解合成一檔：答案與解析和題幹在同一個區塊，檢索時才會一起被撈出來。"""
    level_id = LEVELS[level]
    exams = [e for e in catalog.get("exams") or [] if e.get("levelId") == level_id]
    sections: list[tuple[str, str]] = []
    no_reference: list[str] = []

    for exam in exams:
        question_path = REPO / "data" / level / "questions" / exam["questionFile"]
        if not question_path.exists():
            continue
        reference_path = GENERATED / "examReferenceAnswers" / f"{exam['routeKey']}.json"
        references = load_json(reference_path) if reference_path.exists() else {}
        if not references:
            no_reference.append(exam.get("label") or exam.get("title") or exam["routeKey"])
        questions = load_json(question_path).get("questions") or []
        tag = exam.get("label") or exam.get("title") or exam["routeKey"]
        chunk = [f"\n## {exam.get('title') or exam['routeKey']}（共 {len(questions)} 題）\n"]
        # 題組的附件只掛在來源標註的那一題上，同組其他題也需要，往後傳給 context 相同的題目
        carried: dict[str, list] = {}
        for question in questions:
            context_key = squash(question.get("context") or "")
            blocks = question.get("context_blocks") or []
            if context_key and blocks:
                carried.setdefault(context_key, blocks)

        for number, question in enumerate(questions, start=1):
            chunk.append(f"\n### {tag}　第 {number} 題\n")
            context = clean_text((question.get("context") or "").strip())
            if context:
                chunk.append(f"**題組共用說明：** {context}\n")
            chunk.append(clean_text(question.get("question", "").strip()) + "\n")
            blocks = question.get("context_blocks") or carried.get(squash(question.get("context") or ""), [])
            for block in blocks:
                title = clean_text(block.get("title") or "附件")
                language = block.get("language") or "text"
                chunk.append(f"**{title}：**\n\n```{language}\n{block.get('markdown', '').strip()}\n```\n")
            if question.get("images"):
                chunk.append("> ⚠️ 本題附圖，圖片未包含在文字檔中。只看文字無法判斷答案，"
                             "請對照原始考卷 PDF 的該題附圖。\n")
            options = question.get("options") or {}
            for key in sorted(options):
                chunk.append(f"- （{key}）{clean_text(str(options[key]))}")
            chunk.append(f"\n**官方答案：{question.get('answer', '')}**\n")

            issue = question.get("source_issue") or {}
            if issue.get("note"):
                chunk.append(f"> ⚠️ 本題官方答案有爭議：{clean_text(issue['note'])}\n")

            entry = reference_lookup(references, question.get("id", ""), exam.get("legacyReferencePrefix"))
            if not entry:
                chunk.append("> 本題沒有參考詳解。請勿引用其他考卷的解析來回答本題。\n")
                continue
            answer_text = strip_rag_phrases(clean_text((entry.get("reference_answer") or "").strip()))
            if answer_text:
                chunk.append(f"**參考詳解（本教材編寫，非官方）：** {answer_text}\n")
            analysis = entry.get("option_analysis") or {}
            if isinstance(analysis, dict) and analysis:
                chunk.append("**逐選項分析：**\n")
                for key in sorted(analysis):
                    chunk.append(f"- （{key}）{strip_rag_phrases(clean_text(str(analysis[key])))}")
                chunk.append("")
            concepts = entry.get("key_concepts") or []
            if concepts:
                chunk.append("**關鍵觀念：** " + "；".join(clean_text(str(c)) for c in concepts) + "\n")
            citations = entry.get("citations")
            citations = [citations] if isinstance(citations, dict) else (citations or [])
            titles = []
            for citation in citations:
                name = clean_text((citation.get("title") or "").strip())
                if name and name not in titles:
                    titles.append(name)
            if titles:
                # page_label 記的是被引章節的起始頁而非該段所在頁，印出來會把讀者導到錯頁，故不印頁碼
                chunk.append("**對應講義章節：** " + "、".join(titles) + "\n")
        sections.append((exam.get("title") or exam["routeKey"], "\n".join(chunk)))

    header = [
        f"# {level}｜官方試題與參考詳解",
        "",
        f"資料類型：官方公告試題與官方樣題＋本教材參考詳解｜等級：{level}",
        "",
        f"> {EXAM_NOTE}",
    ]
    if no_reference:
        header.append("> ⚠️ 下列考卷沒有參考詳解，題目下方會逐題標註；被問到時不要從其他考卷外推："
                      + "、".join(no_reference))
    header.append("")
    return split_sections("10-官方試題與參考詳解", "\n".join(header), sections)


def split_sections(stem: str, header: str, sections: list[tuple[str, str]]) -> list[tuple[str, str]]:
    if not sections:
        return []
    buckets: list[list[tuple[str, str]]] = [[]]
    size = len(header)
    for section in sections:
        if buckets[-1] and size + len(section[1]) > MAX_FILE_CHARS:
            buckets.append([])
            size = len(header)
        buckets[-1].append(section)
        size += len(section[1])
    files = []
    for order, bucket in enumerate(buckets, start=1):
        names = "、".join(name for name, _ in bucket)
        suffix = f"-{order:02d}" if len(buckets) > 1 else ""
        title_line = f"\n> 本檔涵蓋：{names}\n\n"
        body = header + title_line + "\n".join(text for _, text in bucket)
        if len(buckets) > 1:
            first = header.split("\n")[0]
            body = body.replace(first, f"{first}（第 {order} 部分，共 {len(buckets)} 部分）", 1)
        files.append((f"{stem}{suffix}.md", body))
    return files


# --- 練習題、名詞、熱度、讀我 --------------------------------------------------

def practice_files(level: str, manifest: dict) -> list[tuple[str, str]]:
    subjects = manifest.get("subjects") or []
    body = [f"# {level}｜章節練習題", "", f"資料類型：章節練習題（非官方考題）｜等級：{level}", "",
            f"> {PRACTICE_NOTE}", ""]
    total = 0
    for order, subject in enumerate(subjects, start=1):
        path = REPO / "data" / level / "questions" / f"subject{order}_questions.json"
        if not path.exists():
            continue
        data = load_json(path)
        body.append(f"\n## {data.get('subject') or subject.get('id')}\n")
        for chapter in data.get("chapters") or []:
            questions = chapter.get("questions") or []
            if not questions:
                continue
            total += len(questions)
            body.append(f"\n### {chapter.get('title')}（{len(questions)} 題）\n")
            for number, question in enumerate(questions, start=1):
                body.append(f"\n**章節練習　{chapter.get('title')}　第 {number} 題**\n")
                body.append(clean_text(question.get("question", "").strip()))
                for key in sorted(question.get("options") or {}):
                    body.append(f"- （{key}）{clean_text(str(question['options'][key]))}")
                body.append(f"\n答案：{question.get('answer', '')}")
                explanation = strip_explanation_prefix(question.get("explanation"))
                if explanation:
                    body.append(f"解析：{explanation}")
                card = question.get("card") or {}
                bits = [f"{label}：{card[key]}" for key, label in
                        (("concept", "核心觀念"), ("mnemonic", "記憶點"), ("confusion", "易混淆"))
                        if card.get(key)]
                if bits:
                    body.append("　".join(clean_text(b) for b in bits))
                tags = [t for t in question.get("tags") or []
                        if not INTERNAL_TAG.match(str(t)) and str(t) not in STRUCTURAL_TAG]
                if tags:
                    body.append(f"標籤：{'、'.join(tags)}")
                body.append("")
    body.insert(5, f"> 共 {total} 題。標籤是自由描述詞，與「40-考點分布」的詞彙表不相通。\n")
    return [("20-章節練習題.md", "\n".join(body))]


def guide_exercise_files(level: str, manifest: dict, errata, counter: Counter) -> list[tuple[str, str]]:
    body = [f"# {level}｜學習指引練習", "", f"資料類型：官方學習指引內附練習題｜等級：{level}", "",
            f"> {EXERCISE_NOTE}"]
    if level == "中級":
        body.append("> ⚠️ 中級的練習題印在大章章末、涵蓋整個大章，這裡掛在該大章的最後一節底下，"
                    "實際考察範圍是整個大章，不限那一節。")
    body.append("")
    total = 0
    for order, _subject in enumerate(manifest.get("subjects") or [], start=1):
        path = REPO / "data" / level / "questions" / f"subject{order}_guide_exercises.json"
        if not path.exists():
            continue
        data = load_json(path)
        body.append(f"\n## {data.get('subject') or f'科目{order}'}\n")
        for chapter in data.get("chapters") or []:
            questions = chapter.get("questions") or []
            if not questions:
                continue  # 沒有練習題的章不印空標題
            total += len(questions)
            body.append(f"\n### {chapter.get('title')}（{len(questions)} 題）\n")
            for number, question in enumerate(questions, start=1):
                reference = question.get("source_ref") or {}
                page = reference.get("question_page")
                # source_ref 的 page 是 0-based index，+1 才是 PDF 頁碼
                where = f"（原書 PDF 第 {page + 1} 頁）" if isinstance(page, int) else ""
                body.append(f"\n**學習指引練習　{chapter.get('title')}　第 {number} 題**{where}\n")
                body.append(clean_text(question.get("question", "").strip()))
                for key in sorted(question.get("options") or {}):
                    body.append(f"- （{key}）{clean_text(str(question['options'][key]))}")
                body.append(f"\n答案：{question.get('answer', '')}")
                explanation = strip_explanation_prefix(question.get("explanation"))
                if explanation:
                    body.append(f"解析：{explanation}")
                body.append("")
    body.insert(5, f"> 共 {total} 題。\n")
    return [("21-學習指引練習.md", apply_errata("\n".join(body), errata, counter))]


def glossary_files(level: str) -> list[tuple[str, str]]:
    path = GENERATED / GLOSSARY_FILE[level]
    if not path.exists():
        return []
    data = load_json(path)
    body = [f"# {level}｜名詞解釋", "", f"資料類型：名詞釋義｜等級：{level}", "", f"> {GLOSSARY_NOTE}", ""]
    total = 0
    subjects = data.get("subjects") or {}
    items = subjects.items() if isinstance(subjects, dict) else [(s.get("id"), s) for s in subjects]
    for subject_id, payload in items:
        terms = (payload.get("terms") if isinstance(payload, dict) else payload) or []
        total += len(terms)
        title = payload.get("subject") if isinstance(payload, dict) else None
        body.append(f"\n## {title or subject_id}（{len(terms)} 條）\n")
        for term in sorted(terms, key=lambda t: t.get("zh") or ""):
            english = f"（{term['en']}）" if term.get("en") else ""
            body.append(f"\n### {clean_text(term.get('zh', ''))}{english}")
            body.append(clean_text(term.get("definition", "")))
            if term.get("example"):
                body.append(f"例：{clean_text(term['example'])}")
    body.insert(5, f"> 共 {total} 條。\n")
    return [("30-名詞解釋.md", "\n".join(body))]


def annotated_exams(level: str, catalog: dict) -> list[str]:
    """考點分布的母體＝有章別標註的考卷。標註檔在 guideExamAnnotations，逐檔掃出 examKey。"""
    keys: set[str] = set()
    base = GENERATED / "guideExamAnnotations"
    for path in base.rglob("*.json"):
        if path.name == "index.json":
            continue
        try:
            payload = load_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        stack = [payload]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                for key, value in node.items():
                    if key in {"examKey", "exam", "source"} and isinstance(value, str):
                        keys.add(value)
                    stack.append(value)
            elif isinstance(node, list):
                stack.extend(node)
    titles = []
    for exam in catalog.get("exams") or []:
        if exam.get("levelId") == LEVELS[level] and exam.get("routeKey") in keys:
            titles.append(exam.get("label") or exam.get("title") or exam["routeKey"])
    return titles


def heat_files(level: str, manifest: dict, catalog: dict) -> list[tuple[str, str]]:
    path = GENERATED / "topicHeat.json"
    if not path.exists():
        return []
    data = load_json(path)
    chapter_titles = {
        chapter["id"]: chapter.get("title", "")
        for subject in manifest.get("subjects") or []
        for chapter in subject.get("chapters") or []
    }
    rows = []
    for topic in data.get("topics") or []:
        hits = [c for c in topic.get("chapters") or []
                if c.get("kind") == "guide" and c.get("nodeId") in chapter_titles]
        if not hits:
            continue
        where = "、".join(f"{chapter_titles[c['nodeId']]}（{c.get('count', 0)} 次）"
                         for c in sorted(hits, key=lambda c: -c.get("count", 0)))
        rows.append((len(hits), max(c.get("count", 0) for c in hits), topic.get("name", ""),
                     topic.get("parent") or "", where))
    rows.sort(key=lambda r: (-r[0], -r[1], r[2]))
    titles = annotated_exams(level, catalog)
    covered = "、".join(titles) if titles else "（查無標註來源）"
    body = [
        f"# {level}｜考點分布",
        "",
        f"資料類型：考點與章節的對應分布｜等級：{level}",
        "",
        "> 這張表說的是「哪個觀念被歷屆題目考過、分散在哪幾章」，不是排行榜。",
        "> ⚠️ 各章的次數**不可以相加**：同一題常同時對應多章，章別是分布不是份額。"
        "所以這裡不提供任何加總欄位，排序依據是「橫跨幾章」與「單章最高次數」。",
        f"> 母體：只有下列考卷做過章別標註，其餘考卷完全不在這張表裡——{covered}。"
        "所以這張表反映的是這幾份考卷的分布，不是全部考題。",
        "",
        "| 觀念 | 所屬主題 | 橫跨章數 | 單章最高次數 | 分布在哪些章 |",
        "|---|---|---|---|---|",
    ]
    for span, top, name, parent, where in rows:
        body.append(f"| {name} | {parent} | {span} | {top} | {where} |")
    return [("40-考點分布.md", "\n".join(body))]


CUSTOM_INSTRUCTIONS = """你是這個 notebook 的考試輔導助教，回答對象是準備 iPAS AI 應用規劃師考試的學生。

回答時請遵守：
1. 只根據來源檔案回答。找不到依據就直接說「這份資料裡沒有」，不要用一般常識補。
2. 講義文字是由原始 PDF 的頁面影像辨識還原的，小節標題用字可能與書上略有出入，
   公式與表格也可能有殘留錯誤。回答涉及公式、表格或精確用字時，請一併說
   「建議對照原始 PDF 第 X 頁確認」。
3. 引用時要講清楚素材種類：「官方試題」是歷次公告試題與官方樣題；「學習指引練習」是官方
   學習指引書上章末附的練習題，屬官方素材但不是考題；「章節練習題」是本教材整理的，
   不是官方素材。三者不要混為一談。
4. 「參考詳解」是本教材編寫的解析，不是官方公布的答案。官方只公布答案。
   引用詳解時請說明這一點。
5. 題目標了 ⚠️ 附圖的，一定要提醒學生去看原始考卷 PDF，不要只憑文字推測答案。
6. 「考點分布」檔的各章次數不可以相加——同一題常同時對應多章。
   不要自行加總來排名，也不要說某章「共考了 N 題」。
7. 用繁體中文回答。
"""


def readme_file(level: str, manifest: dict, catalog: dict, written: list[tuple[str, str]],
                errata_hits: Counter, errata_total: int, image_marks: int) -> tuple[str, str]:
    level_id = LEVELS[level]
    exams = [e for e in catalog.get("exams") or [] if e.get("levelId") == level_id]
    chapters = sum(len(s.get("chapters") or []) for s in manifest.get("subjects") or [])
    body = [
        f"# {level}｜讀我：這個 notebook 有什麼",
        "",
        f"資料類型：索引與章節地圖｜等級：{level}｜科目 {len(manifest.get('subjects') or [])} 科、章 {chapters} 章",
        "",
        "## 檔案清單",
        "",
        "- `00-讀我-章節地圖.md`（本檔）",
    ]
    for name, _text in written:
        body.append(f"- `{name}`")
    body.extend([
        "",
        "## 章節地圖",
        "",
        "講義的章節與各章涵蓋的主題如下。回答時請用這裡的章節名稱指出出處。",
        "",
    ])
    for subject in manifest.get("subjects") or []:
        body.append(f"\n### {subject.get('subject') or subject.get('id')}\n")
        for chapter in subject.get("chapters") or []:
            subtopics = "、".join(chapter.get("subtopics") or [])
            body.append(f"- **{chapter.get('title')}**（原書 {chapter.get('start_page', '')} 頁起）"
                        + (f"：{subtopics}" if subtopics else ""))
    body.extend(["", "## 考卷清單", ""])
    for exam in exams:
        reference = GENERATED / "examReferenceAnswers" / f"{exam['routeKey']}.json"
        mark = "" if reference.exists() else "（無參考詳解）"
        body.append(f"- {exam.get('title')}（{exam.get('expectedQuestions')} 題）{mark}")
    body.extend([
        "",
        "## 這批資料的邊界",
        "",
        "- 講義文字由頁面影像辨識還原，小節標題用字可能與書上略有出入。以官方 PDF 為準。",
        f"- 官方勘誤表共 {errata_total} 條可機械比對，匯出時實際替換了 {sum(errata_hits.values())} 處。"
        "沒有替換到的條目有幾種情況：上游資料早已是正確版本、目標頁不在匯出範圍、"
        "或原文用字與辨識結果對不上。要確認特定條目請查官方勘誤表。",
        f"- 原書的插圖與圖表**沒有**轉成文字，匯出檔裡也沒有圖。只有 {image_marks} 處留下了位置標記，"
        "其餘插圖在檔案中不留痕跡。凡是需要判讀圖形的內容，一定要看原始 PDF。",
        "- 官方只公布考題與答案，未公布解析；檔案中的「參考詳解」是本教材編寫的。",
        "- 「考點分布」的各章次數不可相加。",
        "",
        "## 建議把這份 notebook 的自訂指令設成",
        "",
        "見同目錄的 `99-自訂指令.txt`（這個檔不要上傳，是拿去貼到 NotebookLM 的 Configure chat → Custom）。",
        "把規則放在自訂指令、而不是放在來源檔裡，模型才會真的照做。",
        "",
    ])
    return ("00-讀我-章節地圖.md", "\n".join(body))


def export_level(level: str, out_root: Path) -> tuple[list[tuple[str, int]], Counter]:
    manifest = load_json(REPO / "data" / level / "toc_manifest.json")
    outlines = load_json(GENERATED / "guideOutlines.json")
    hierarchy = load_json(GENERATED / "guideHierarchy.json")
    catalog = load_json(REPO / "data" / "resource_catalog.json")
    errata = errata_rules(level)

    guides, errata_hits = guide_files(level, outlines, hierarchy, manifest, errata)
    files: list[tuple[str, str]] = []
    files.extend(guides)
    files.extend(exam_files(level, catalog))
    files.extend(practice_files(level, manifest))
    files.extend(guide_exercise_files(level, manifest, errata, errata_hits))
    files.extend(glossary_files(level))
    files.extend(heat_files(level, manifest, catalog))
    image_marks = sum(text.count("【原書插圖】") for _name, text in files)
    files.insert(0, readme_file(level, manifest, catalog, files, errata_hits, len(errata), image_marks))
    files.append(("99-自訂指令.txt", CUSTOM_INSTRUCTIONS))

    out_dir = out_root / level
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in list(out_dir.glob("*.md")) + list(out_dir.glob("*.txt")):
        stale.unlink()

    written = []
    for name, text in files:
        path = out_dir / name
        payload = text.rstrip() + "\n"
        path.write_text(payload, encoding="utf-8")
        written.append((name, len(payload)))
    return written, errata_hits


def main() -> None:
    parser = argparse.ArgumentParser(description="匯出 NotebookLM 匯入包")
    parser.add_argument("--level", choices=["初級", "中級", "all"], default="all")
    parser.add_argument("--out", default=str(REPO / "exports" / "notebooklm"))
    args = parser.parse_args()

    out_root = Path(args.out)
    for level in (list(LEVELS) if args.level == "all" else [args.level]):
        written, errata_hits = export_level(level, out_root)
        total = sum(size for _, size in written)
        print(f"\n{level} → {out_root / level}（{len(written)} 檔，共 {total:,} 字元）")
        for name, size in written:
            print(f"  {size:>9,}  {name}")
        if errata_hits:
            print(f"  官方勘誤套用 {sum(errata_hits.values())} 處：{dict(errata_hits)}")
        else:
            print("  官方勘誤套用 0 處")


if __name__ == "__main__":
    main()
