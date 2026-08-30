#!/usr/bin/env python3
"""Apply the reviewed semantic correction layer to Track B OCR pages.

``data/{level}/guide_ocr`` remains an immutable record of the OCR result.  This
script edits only the generated ``pages_cache`` bridge, immediately before
``parse_guides.py`` rebuilds the canonical question-generation guides.

Required order::

    python3 scripts/ocr_extract.py
    python3 scripts/apply_errata.py                 # official errata first
    python3 scripts/apply_track_b_ocr_fixes.py --level all
    uv run python3 scripts/parse_guides.py --level 初級
    uv run python3 scripts/parse_guides.py --level 中級

The correction set is strict, transactional per invocation, and idempotent.
Unexpected source text aborts before any page is written.  Two formula fixes
(``TB-002`` and ``TB-007``) are explicitly classified as source-PDF math
corrections rather than OCR defects.  The two official errata fixes are owned
by ``errata_manual.json``; this layer only verifies and records them.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


BASE = Path(__file__).resolve().parents[1]


def replace(find: str, replacement: str, count: int = 1) -> dict[str, Any]:
    return {
        "type": "replace",
        "find": find,
        "replacement": replacement,
        "count": count,
    }


def assert_official(forbid: str, required: str) -> dict[str, Any]:
    return {"type": "assert_official", "forbid": forbid, "required": required}


def append_once(marker: str, text: str) -> dict[str, Any]:
    return {"type": "append_once", "marker": marker, "text": text}


def remove_table_row(*contains: str) -> dict[str, Any]:
    return {"type": "remove_table_row", "contains": list(contains)}


def patch(
    correction_id: str,
    classification: str,
    level: str,
    key: str,
    page_index: int,
    page_label: str,
    *operations: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": correction_id,
        "classification": classification,
        "level": level,
        "key": key,
        "page_index": page_index,
        "page_label": page_label,
        "operations": list(operations),
    }


def image_patch(
    correction_id: str,
    level: str,
    key: str,
    page_index: int,
    page_label: str,
    description: str,
) -> dict[str, Any]:
    marker = f"<!-- track-b-image-semantic:{correction_id} -->"
    supplement = (
        f"{marker}\n"
        f"> **圖像語意補充（原始教材圖示）**：{description}"
    )
    return patch(
        correction_id,
        "image_semantic",
        level,
        key,
        page_index,
        page_label,
        append_once(marker, supplement),
    )


# Every logical correction ID maps back to /tmp/ocr_defects_track_b.json.  TB-008
# has two page targets because one table row crosses the page boundary.
PATCHES: list[dict[str, Any]] = [
    patch(
        "TB-001", "official_errata", "初級", "guide1", 32, "3-27",
        assert_official(
            "Type II 錯誤 ( $ \\alpha $)",
            "Type I 錯誤 ( $ \\alpha $)",
        ),
    ),
    patch(
        "TB-002", "source_math_correction", "初級", "guide1", 45, "3-40",
        replace(
            r"$$ X_{scaled}=\frac{X-X_{min}}{X_{man}-X_{min}} $$",
            r"$$ X_{scaled}=\frac{X-X_{min}}{X_{max}-X_{min}} $$",
        ),
        append_once(
            "<!-- track-b-source-math-correction:TB-002 -->",
            "<!-- track-b-source-math-correction:TB-002 -->\n"
            "> **來源公式校正**：原始 PDF 將 Min-Max 公式的分母下標誤植為 "
            "`man`；本出題來源依 Min-Max 定義更正為 `max`。",
        ),
    ),
    patch(
        "TB-003", "ocr_formula", "中級", "guide1", 23, "3-17",
        replace(
            "IDF(t, D) = log(∏(D | ( |{d ∈ D : t ∈ d} |))",
            r"IDF(t, D) = $ \log\left(\frac{|D|}{|\{d \in D:t \in d\}|}\right) $",
        ),
    ),
    patch(
        "TB-004", "ocr_formula", "中級", "guide2", 23, "3-17",
        replace(r"\left(\frac{n}{k}\right)", r"\binom{n}{k}", count=3),
    ),
    patch(
        "TB-005", "ocr_formula", "中級", "guide2", 43, "3-37",
        replace(
            r"$ n \times p_0 \geq 5 \cdot n \times (1 - p_0) \geq 5 $",
            r"$ n \times p_0 \geq 5 \quad\text{且}\quad n \times (1 - p_0) \geq 5 $",
        ),
    ),
    patch(
        "TB-006", "official_errata", "中級", "guide3", 154, "5-21",
        assert_official(
            "- 公式：Precision =  $ \\frac{TP}{TP+FN} $\n\n"
            "定義：被預測為正類的樣本中，實際為正類的比例。\n\n"
            "適用場景：當「誤報正類」的代價高時（例如垃圾郵件分類、醫療誤診）。\n\n"
            "目的：衡量「預測為正的可信度」。\n\n"
            "### 召回率（Recall）\n\n"
            "- 公式：Recall =  $ \\frac{TP}{TP+FP} $",
            "- 公式：Precision =  $ \\frac{TP}{TP+FP} $\n\n"
            "定義：被預測為正類的樣本中，實際為正類的比例。\n\n"
            "適用場景：當「誤報正類」的代價高時（例如垃圾郵件分類、醫療誤診）。\n\n"
            "目的：衡量「預測為正的可信度」。\n\n"
            "### 召回率（Recall）\n\n"
            "- 公式：Recall =  $ \\frac{TP}{TP+FN} $",
        ),
    ),
    patch(
        "TB-007", "source_math_correction", "中級", "guide3", 168, "5-35",
        replace(
            r"$$  Softmax(z_{i})=\frac{e^{z_{i}}}{\sum_{j=1}^{K}e^{z_{i}}} $$",
            r"$$  Softmax(z_{i})=\frac{e^{z_{i}}}{\sum_{j=1}^{K}e^{z_{j}}} $$",
        ),
        append_once(
            "<!-- track-b-source-math-correction:TB-007 -->",
            "<!-- track-b-source-math-correction:TB-007 -->\n"
            "> **來源公式校正**：原始 PDF 的 Softmax 分母將求和項誤植為 "
            "`e^{z_i}`；本出題來源依定義更正為 `e^{z_j}`。",
        ),
    ),
    patch(
        "TB-008", "ocr_table", "中級", "guide1", 18, "3-12",
        replace("能反詞彙重要性、實作簡單、效果", "能反詞彙重要性、實作簡單、效果穩定"),
        replace("無法處理同詞</td>", "無法處理同詞異義或多義詞</td>"),
    ),
    patch(
        "TB-008", "ocr_table", "中級", "guide1", 19, "3-13",
        remove_table_row("穩定", "異義或多義詞"),
    ),
    patch(
        "TB-009", "ocr_structure", "初級", "guide2", 44, "3-39",
        replace(
            "##### a. 模型架構與演算法\n\n##### A. 模型開發至部署",
            "##### A. 模型開發至部署\n\n##### a. 模型架構與演算法",
        ),
    ),
    patch(
        "TB-010", "ocr_text", "中級", "guide1", 75, "3-69",
        replace("特徵：音質細膩、訓練效度高，適應多語考情境。\n\n", ""),
    ),
    patch(
        "TB-011", "ocr_text", "中級", "guide1", 113, "4-20",
        replace(
            "1-4週、常見2週），期間內團隊針對特定目標",
            "其中，Sprint 是 Scrum 的節奏核心。每次 Sprint 為一個固定週期（一般為1-4週、常見2週），期間內團隊針對特定目標",
        ),
    ),
    patch(
        "TB-012", "ocr_structure", "中級", "guide2", 102, "5-15",
        replace(
            "這些方法通過數學模型捕捉時序數據的線性和季節性模式",
            "### 統計建模方法\n\n這些方法通過數學模型捕捉時序數據的線性和季節性模式",
        ),
    ),
    patch(
        "TB-013", "ocr_structure", "中級", "guide2", 160, "6-23",
        replace(
            "挑戰：\n\n實務案例：\n\n跨系統資料的時間欄位可能有延遲、格式差異或時區不一致。\n\n- 網站日誌",
            "挑戰：\n\n跨系統資料的時間欄位可能有延遲、格式差異或時區不一致。\n\n實務案例：\n\n- 網站日誌",
        ),
    ),
    patch(
        "TB-014", "ocr_structure", "中級", "guide3", 53, "4-16",
        replace(
            "無多重共線性（No Multicollinearity）\n\n### 適用情境\n\n"
            "自變數之間不應高度相關，以免影響係數估計的穩定性。\n\n"
            "- 資料存在多重共線性時。\n\n"
            "Ridge 與 Lasso 特別適用於以下情況：",
            "無多重共線性（No Multicollinearity）\n\n"
            "自變數之間不應高度相關，以免影響係數估計的穩定性。\n\n"
            "### 適用情境\n\n"
            "Ridge 與 Lasso 特別適用於以下情況：\n\n"
            "- 資料存在多重共線性時。",
        ),
    ),
    patch(
        "TB-015", "ocr_text", "中級", "guide3", 56, "4-19",
        replace(
            "決策樹迴歸本身沒有像線性模型那樣的明確數學公式，其預測流程為：\n\n"
            "決策樹迴歸本身沒有像線性模型那樣的明確數學公式，其預測流程為：a.",
            "決策樹迴歸本身沒有像線性模型那樣的明確數學公式，其預測流程為：\n\n"
            "a.",
        ),
    ),
    patch(
        "TB-016", "ocr_structure", "中級", "guide3", 59, "4-22",
        replace(
            "擅長捕捉複雜的非線性關係與變數交互作用。\n\n"
            "可透過各決策樹的重要性分數來解讀變數影響。\n\n"
            "可自訂損失函數，具高度彈性。",
            "擅長捕捉複雜的非線性關係與變數交互作用。\n\n"
            "可自訂損失函數，具高度彈性。\n\n"
            "可透過各決策樹的重要性分數來解讀變數影響。",
        ),
    ),
    patch(
        "TB-017", "ocr_structure", "中級", "guide3", 100, "4-63",
        replace(
            "模型在訓練集上的損失很低，準確率很高。\n\n"
            "### 正則化技術\n\n"
            "模型在驗證集（或測試集）上的損失高，準確率顯著低於訓練集。",
            "模型在訓練集上的損失很低，準確率很高。\n\n"
            "模型在驗證集（或測試集）上的損失高，準確率顯著低於訓練集。\n\n"
            "### 正則化技術",
        ),
    ),
    patch(
        "TB-018", "ocr_structure", "中級", "guide3", 121, "4-84",
        replace(
            "生成式模型的核心目標是學習訓練數據的底層分佈",
            "#### （5）生成式模型\n\n生成式模型的核心目標是學習訓練數據的底層分佈",
        ),
    ),
    patch("TB-019", "ocr_text", "初級", "guide1", 39, "3-34", replace("情況上不斷", "情況下不斷")),
    patch("TB-020", "ocr_text", "初級", "guide1", 47, "3-42", replace("進步優化", "進一步優化")),
    patch("TB-021", "ocr_text", "初級", "guide2", 16, "3-11", replace("推勤跨領域創新", "推動跨領域創新")),
    patch("TB-022", "ocr_text", "初級", "guide2", 28, "3-23", replace("個人內容生成", "個人化內容生成")),
    patch("TB-023", "ocr_text", "初級", "guide2", 36, "3-31", replace("一數據清洗與整合", "- 數據清洗與整合")),
    patch(
        "TB-024", "ocr_text", "初級", "guide2", 38, "3-33",
        replace("試點與驟證", "試點與驗證"),
        replace("仕初始階段", "在初始階段"),
        replace("貧源", "資源"),
    ),
    patch("TB-025", "ocr_text", "中級", "guide1", 39, "3-33", replace("社群興情監控", "社群輿情監控")),
    patch("TB-026", "ocr_text", "中級", "guide1", 40, "3-34", replace("一 聚合處理", "- 聚合處理")),
    patch("TB-027", "ocr_text", "中級", "guide1", 136, "4-43", replace("預警閥值", "預警閾值")),
    patch("TB-028", "ocr_text", "中級", "guide1", 148, "5-8", replace("預測未來一段時間", "預測未來某一段時間")),
    patch("TB-029", "ocr_text", "中級", "guide1", 156, "5-16", replace("每個服務實作單功能", "每個服務實作單一功能")),
    patch("TB-030", "ocr_text", "中級", "guide2", 48, "3-42", replace("样本資料", "樣本資料")),
    patch("TB-031", "ocr_text", "中級", "guide2", 78, "4-24", replace("模型對資針的理解", "模型對資料的理解")),
    patch("TB-032", "ocr_text", "中級", "guide2", 82, "4-28", replace("豐富的操作者（Operators）", "豐富的操作器（Operators）")),
    patch("TB-033", "ocr_text", "中級", "guide2", 101, "5-14", replace("### 3. 在序數據分析", "### 3. 時序數據分析")),
    patch("TB-034", "ocr_text", "中級", "guide2", 108, "5-21", replace("結合詞類和文獻稀有性", "結合詞頻和文獻稀有性")),
    patch("TB-035", "ocr_text", "中級", "guide3", 11, "3-5", replace("侏件機率", "條件機率")),
    patch("TB-036", "ocr_text", "中級", "guide3", 21, "3-15", replace("可視潛在特徵", "可視為潛在特徵")),
    patch("TB-037", "ocr_text", "中級", "guide3", 43, "4-6", replace("個典型的監督式學習流程", "一個典型的監督式學習流程")),
    patch("TB-038", "ocr_text", "中級", "guide3", 65, "4-28", replace("決策世界", "決策邊界")),
    patch("TB-039", "ocr_text", "中級", "guide3", 68, "4-31", replace("集中於單類別", "集中於單一類別")),
    patch("TB-040", "ocr_text", "中級", "guide3", 92, "4-55", replace("澂活函數", "激活函數")),
    patch("TB-041", "ocr_text", "中級", "guide3", 115, "4-78", replace("轉化為個連貫、有意義的輸出序列", "轉化為一個連貫、有意義的輸出序列")),
    patch("TB-042", "ocr_text", "中級", "guide3", 116, "4-79", replace("得到個綜合了相關資訊的「上下文向量」", "得到一個綜合了相關資訊的「上下文向量」")),
    patch("TB-043", "ocr_text", "中級", "guide3", 157, "5-24", replace("解釋資料差異", "解釋資料變異")),
    patch("TB-044", "ocr_text", "中級", "guide3", 179, "5-46", replace("保持輸出期望值致", "保持輸出期望值一致")),
    patch("TB-045", "ocr_text", "中級", "guide3", 181, "5-48", replace("合成新檨本", "合成新樣本")),
    patch("TB-046", "ocr_text", "中級", "guide2", 10, "3-4", replace("侗限", "侷限")),
    patch("TB-047", "ocr_text", "中級", "guide2", 11, "3-5", replace("侗限", "侷限", count=2)),
    patch("TB-048", "ocr_text", "中級", "guide2", 13, "3-7", replace("侗限", "侷限")),
    patch("TB-049", "ocr_text", "中級", "guide2", 14, "3-8", replace("侗限", "侷限")),
    patch("TB-050", "ocr_text", "中級", "guide2", 16, "3-10", replace("侗限", "侷限")),
    patch("TB-051", "ocr_text", "中級", "guide2", 22, "3-16", replace("侗限", "侷限")),
    patch("TB-052", "ocr_text", "中級", "guide2", 23, "3-17", replace("侗限", "侷限")),
    patch("TB-053", "ocr_text", "中級", "guide2", 24, "3-18", replace("侗限", "侷限")),
    patch("TB-054", "ocr_text", "中級", "guide2", 25, "3-19", replace("侗限", "侷限")),
    patch("TB-055", "ocr_text", "中級", "guide2", 26, "3-20", replace("侗限", "侷限")),
    patch("TB-056", "ocr_text", "中級", "guide2", 27, "3-21", replace("侗限", "侷限")),
    image_patch(
        "TB-057", "初級", "guide1", 54, "3-49",
        "流程圖比較鑑別式 AI 與生成式 AI：鑑別式 AI 由資料經邊界判定產生決策；"
        "生成式 AI 由提示經輸入與調整、創建及生成產生內容，並以箭頭呈現兩者的整合。",
    ),
    image_patch(
        "TB-058", "中級", "guide2", 14, "3-8",
        "箱形圖標示離群值、上下鬚、第一四分位數 Q1、中位數與第三四分位數 Q3。",
    ),
    image_patch(
        "TB-059", "中級", "guide2", 17, "3-11",
        "負偏態與正偏態分布對照；負偏態長尾在左、主體在右，正偏態長尾在右、主體在左。",
    ),
    image_patch(
        "TB-060", "中級", "guide2", 18, "3-12",
        "峰度比較曲線包含高峰的 Leptokurtic、基準 Mesokurtic 與平峰 Platykurtic。",
    ),
    image_patch(
        "TB-061", "中級", "guide2", 117, "5-30",
        "兩張並列直方圖分別以 0 與 5 附近為中心，皆呈近似對稱鐘形分布。",
    ),
    image_patch(
        "TB-062", "中級", "guide2", 118, "5-31",
        "三個類別的箱形圖，呈現中位數、四分位距、上下鬚及離群值。",
    ),
    image_patch(
        "TB-063", "中級", "guide2", 119, "5-32",
        "flipper_length_mm 的 KDE 密度曲線呈雙峰分布，主峰約在 195、次峰約在 215。",
    ),
    image_patch(
        "TB-064", "中級", "guide2", 120, "5-33",
        "total_bill 與 tip 散佈圖依 Lunch、Dinner 分組，顯示帳單金額增加時小費亦有上升趨勢。",
    ),
    image_patch(
        "TB-065", "中級", "guide2", 121, "5-34",
        "A 到 Z 變數的下三角皮爾森相關係數熱力圖，以藍至橘色呈現負、零與正相關。",
    ),
    image_patch(
        "TB-066", "中級", "guide2", 122, "5-35",
        "NLP 模型（如 BERT、BiLSTM、ERNIE、RoBERTa、T5）在多項任務上的表現熱力圖。",
    ),
    image_patch(
        "TB-067", "中級", "guide2", 123, "5-36",
        "Torgersen、Biscoe 與 Dream 三座島嶼的 body_mass_g 長條圖，含誤差線；Biscoe 最高。",
    ),
    image_patch(
        "TB-068", "中級", "guide2", 124, "5-37",
        "男性與女性年齡分布的堆疊長條圖，依 alive 的 yes／no 狀態分色。",
    ),
    image_patch(
        "TB-069", "中級", "guide2", 125, "5-38",
        "Dogs、Hogs、Frogs、Logs 四類比例圓餅圖，其中 Dogs 最大、Logs 最小。",
    ),
    image_patch(
        "TB-070", "中級", "guide2", 126, "5-39",
        "1970 至 2020 年多國 Spending_USD 的累積區域折線圖；支出整體隨時間增長，USA 占比最大。",
    ),
    image_patch(
        "TB-071", "中級", "guide3", 60, "4-23",
        "XGBoost 與 LightGBM 樹生長策略對比：前者採 level-wise 同層分裂，後者採 leaf-wise 優先分裂最大增益葉節點。",
    ),
    image_patch(
        "TB-072", "中級", "guide3", 149, "5-16",
        "偏差－變異權衡圖：模型複雜度提高時 Bias² 下降、Variance 上升、Total Error 呈 U 形，最低點為最佳複雜度。",
    ),
    image_patch(
        "TB-073", "中級", "guide3", 155, "5-22",
        "ROC 圖以假陽性率為橫軸、真陽性率為縱軸，並標示完美分類器與隨機分類器對角線；曲線愈靠左上愈佳。",
    ),
]


PROVENANCE_CORRECTIONS = [
    {"id": "TB-074", "level": "中級", "key": "guide1"},
    {"id": "TB-075", "level": "中級", "key": "guide2"},
    {"id": "TB-076", "level": "中級", "key": "guide3"},
    {"id": "TB-077", "level": "初級", "key": "guide1"},
    {"id": "TB-078", "level": "初級", "key": "guide2"},
]


# Reviewed canonical content fingerprints are committed truth for fresh clones
# and CI, where gitignored pages_cache is intentionally unavailable.  The hash
# covers ``[(chapter id, chapter content), ...]`` using the same stable encoding
# as parse_guides.chapter_content_sha256().
REVIEWED_CANONICAL = {
    ("初級", "guide1"): {
        "path": "guide/subject1_guide.json",
        "content_sha256": "ab5872cd4ae5bd90d074a5ba0d8c019def622127dddf19dff8112947d166f7b0",
        "source_pages_sha256": "44d5fd312c9fa09df83e0493bb535a6653ad8940a76bbf05d37ec4e676d7473e",
    },
    ("初級", "guide2"): {
        "path": "guide/subject2_guide.json",
        "content_sha256": "237e299d9c80755a34e2072cfacc701c96e845bcefbfd7680b1b7e1cc5c97668",
        "source_pages_sha256": "c2e399a14654f49d8f7614360f4803ecdda2c41820f06bbe4d649db5ce3c88a4",
    },
    ("中級", "guide1"): {
        "path": "guide/subject1_guide.json",
        "content_sha256": "f94dfd2cb5d78a07cc44be8ab4daaf57801ffa636ffd428d6d6c5c49c86def42",
        "source_pages_sha256": "7ea50638a9329664666dd4a6fb1fb00ea56bb73557f3c6739b76eacbdb829d90",
    },
    ("中級", "guide2"): {
        "path": "guide/subject2_guide.json",
        "content_sha256": "a572b00800ef75e3e3c9079d44510995cabd5c4ed7343c98f4ccac853ffc2462",
        "source_pages_sha256": "72fe9e4380c5b69f8e1e80e5be532a5e230d13a9f790d9d55aafd9c671ee134a",
    },
    ("中級", "guide3"): {
        "path": "guide/subject3_guide.json",
        "content_sha256": "4dd4f4660a9265b173802d24835fceba90ccc1c7fa4b54aa4aed9b33fe9a8f55",
        "source_pages_sha256": "110644a7e447f044cff6d384283c3413c5867ae24098ec413c0db8bd37e5066d",
    },
}


def _table_rows(markdown: str) -> list[tuple[int, int, str]]:
    """Return HTML table row spans without requiring an HTML dependency."""
    rows: list[tuple[int, int, str]] = []
    cursor = 0
    while True:
        start = markdown.find("<tr>", cursor)
        if start < 0:
            break
        end = markdown.find("</tr>", start)
        if end < 0:
            break
        end += len("</tr>")
        rows.append((start, end, markdown[start:end]))
        cursor = end
    return rows


def _mask_corrected_spans(markdown: str, replacement: str) -> tuple[str, str]:
    """Mask full corrected spans so shorter damaged substrings stay detectable."""
    marker = "\x00TRACK_B_CORRECTED_SPAN\x00"
    while marker in markdown or marker in replacement:
        marker += "_"
    return markdown.replace(replacement, marker), marker


def _apply_operation(markdown: str, operation: dict[str, Any], correction_id: str) -> tuple[str, bool]:
    kind = operation["type"]
    if kind == "replace":
        find = operation["find"]
        replacement = operation["replacement"]
        expected_count = operation["count"]
        corrected_count = markdown.count(replacement) if replacement else 0
        protected = markdown
        marker = ""
        if replacement and find in replacement:
            protected, marker = _mask_corrected_spans(markdown, replacement)
        damaged_count = protected.count(find)
        if damaged_count == expected_count:
            protected = protected.replace(find, replacement, expected_count)
            if marker:
                protected = protected.replace(marker, replacement)
            return protected, True
        if damaged_count == 0:
            if replacement and corrected_count >= expected_count:
                return markdown, False
            if not replacement:
                return markdown, False
        raise ValueError(
            f"{correction_id}: expected {expected_count} uncorrected occurrence(s), "
            f"found {damaged_count}: {find[:80]!r}"
        )

    if kind == "assert_official":
        if operation["forbid"] in markdown:
            raise ValueError(
                f"{correction_id}: official errata is not applied; run scripts/apply_errata.py first"
            )
        if operation["required"] not in markdown:
            raise ValueError(f"{correction_id}: corrected official-errata text is missing")
        return markdown, False

    if kind == "append_once":
        marker = operation["marker"]
        if marker in markdown:
            if operation["text"] not in markdown:
                raise ValueError(f"{correction_id}: marker exists but supplement text is incomplete")
            return markdown, False
        return f"{markdown.rstrip()}\n\n{operation['text']}\n", True

    if kind == "remove_table_row":
        matches = [
            (start, end, row)
            for start, end, row in _table_rows(markdown)
            if all(value in row for value in operation["contains"])
        ]
        if len(matches) == 1:
            start, end, _row = matches[0]
            return markdown[:start] + markdown[end:], True
        if not matches:
            return markdown, False
        raise ValueError(f"{correction_id}: ambiguous HTML table row ({len(matches)} matches)")

    raise ValueError(f"{correction_id}: unsupported operation type {kind!r}")


def _verify_operation(markdown: str, operation: dict[str, Any], correction_id: str) -> None:
    """Validate an already-tagged correction without mutating its text."""
    kind = operation["type"]
    if kind == "replace":
        find = operation["find"]
        replacement = operation["replacement"]
        if replacement:
            if markdown.count(replacement) < operation["count"]:
                raise ValueError(f"{correction_id}: tagged replacement is no longer present")
            protected = markdown
            if find in replacement:
                protected, _marker = _mask_corrected_spans(markdown, replacement)
            if find in protected:
                raise ValueError(f"{correction_id}: corrected and damaged text coexist")
        elif find in markdown:
            raise ValueError(f"{correction_id}: tagged deletion has regressed")
        return
    if kind == "assert_official":
        if operation["forbid"] in markdown or operation["required"] not in markdown:
            raise ValueError(f"{correction_id}: official errata state has regressed")
        return
    if kind == "append_once":
        if operation["marker"] not in markdown or operation["text"] not in markdown:
            raise ValueError(f"{correction_id}: tagged semantic supplement is incomplete")
        return
    if kind == "remove_table_row":
        matches = [
            row for _start, _end, row in _table_rows(markdown)
            if all(value in row for value in operation["contains"])
        ]
        if matches:
            raise ValueError(f"{correction_id}: removed continuation row has returned")
        return
    raise ValueError(f"{correction_id}: unsupported operation type {kind!r}")


def _page_path(base: Path, patch_data: dict[str, Any]) -> Path:
    return (
        base / "data" / patch_data["level"] / "pages_cache" / patch_data["key"]
        / f"page_{patch_data['page_index']:03d}.json"
    )


def selected_patches(level: str) -> list[dict[str, Any]]:
    levels = {"初級", "中級"} if level == "all" else {level}
    return [entry for entry in PATCHES if entry["level"] in levels]


def validate_registry() -> None:
    ids = {entry["id"] for entry in PATCHES}
    expected = {f"TB-{number:03d}" for number in range(1, 74)}
    if ids != expected:
        missing = sorted(expected - ids)
        extra = sorted(ids - expected)
        raise ValueError(f"Track B registry mismatch: missing={missing}, extra={extra}")
    if len(PATCHES) != 74:
        raise ValueError(f"Expected 74 page targets (TB-008 spans two pages), got {len(PATCHES)}")
    provenance_ids = {entry["id"] for entry in PROVENANCE_CORRECTIONS}
    expected_provenance = {f"TB-{number:03d}" for number in range(74, 79)}
    if provenance_ids != expected_provenance:
        raise ValueError(
            f"Track B provenance registry mismatch: expected={sorted(expected_provenance)}, "
            f"actual={sorted(provenance_ids)}"
        )
    expected_guides = {
        (entry["level"], entry["key"])
        for entry in PROVENANCE_CORRECTIONS
    }
    if set(REVIEWED_CANONICAL) != expected_guides:
        raise ValueError(
            "Reviewed canonical fingerprint registry must cover exactly the five provenance guides"
        )
    for guide, review in REVIEWED_CANONICAL.items():
        for field in ("content_sha256", "source_pages_sha256"):
            digest = review.get(field, "")
            if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
                raise ValueError(f"Invalid reviewed canonical {field} for {guide}: {digest!r}")


def apply(base: Path, level: str, *, dry_run: bool = False, check: bool = False) -> dict[str, int]:
    """Apply selected patches transactionally and return summary counts."""
    validate_registry()
    pending: dict[Path, dict[str, Any]] = {}
    changed_ids: set[str] = set()
    already_ids: set[str] = set()

    for patch_data in selected_patches(level):
        path = _page_path(base, patch_data)
        if not path.is_file():
            raise FileNotFoundError(f"{patch_data['id']}: missing {path}")
        if path not in pending:
            pending[path] = json.loads(path.read_text(encoding="utf-8"))
        page = pending[path]
        if page.get("idx") != patch_data["page_index"]:
            raise ValueError(
                f"{patch_data['id']}: {path} idx={page.get('idx')} does not match filename"
            )
        markdown = page.get("markdown")
        if not isinstance(markdown, str) or not markdown.strip():
            raise ValueError(f"{patch_data['id']}: missing non-empty markdown in {path}")

        metadata = page.setdefault("track_b_corrections", [])
        expected_meta = {
            "id": patch_data["id"],
            "classification": patch_data["classification"],
            "page_label": patch_data["page_label"],
        }
        existing = next((item for item in metadata if item.get("id") == patch_data["id"]), None)
        changed = False
        if existing is not None:
            if existing != expected_meta:
                raise ValueError(f"{patch_data['id']}: inconsistent correction metadata in {path}")
            for operation in patch_data["operations"]:
                _verify_operation(markdown, operation, patch_data["id"])
        else:
            for operation in patch_data["operations"]:
                markdown, operation_changed = _apply_operation(markdown, operation, patch_data["id"])
                changed = changed or operation_changed
            page["markdown"] = markdown
            metadata.append(expected_meta)
            changed = True
        metadata.sort(key=lambda item: item["id"])

        (changed_ids if changed else already_ids).add(patch_data["id"])

    if check and changed_ids:
        raise ValueError(
            f"Track B corrections not fully applied; pending IDs: {', '.join(sorted(changed_ids))}"
        )
    if not dry_run and not check:
        for path, payload in pending.items():
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "logical_corrections": len({entry["id"] for entry in selected_patches(level)}),
        "page_targets": len(selected_patches(level)),
        "changed": len(changed_ids),
        "already_applied": len(already_ids - changed_ids),
    }


def _chapter_content_sha256(chapters: list[dict[str, Any]]) -> str:
    payload = [[chapter.get("id"), chapter.get("content")] for chapter in chapters]
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _source_pages_sha256(chapters: list[dict[str, Any]]) -> str:
    payload = [
        [chapter.get("id"), chapter.get("source_pages")]
        for chapter in chapters
    ]
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _validate_complete_cache(cache_dir: Path, total_pages: int) -> None:
    """Mirror parse_guides' all-page cache completeness contract."""
    cached_indices: set[int] = set()
    invalid_files: list[str] = []
    for path in sorted(cache_dir.glob("page_*.json")):
        if path.name == "page_index.json":
            continue
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            invalid_files.append(path.name)
            continue
        index = entry.get("idx")
        filename_index = path.stem.removeprefix("page_")
        valid_type = entry.get("type") in {"content", "practice", "skip"}
        valid_content = entry.get("type") != "content" or bool(
            isinstance(entry.get("markdown"), str) and entry["markdown"].strip()
        )
        if (
            not isinstance(index, int)
            or not filename_index.isdigit()
            or int(filename_index) != index
            or index in cached_indices
            or not valid_type
            or not valid_content
        ):
            invalid_files.append(path.name)
            continue
        cached_indices.add(index)

    expected_indices = set(range(total_pages))
    missing = sorted(expected_indices - cached_indices)
    unexpected = sorted(cached_indices - expected_indices)
    if missing or unexpected or invalid_files:
        raise ValueError(
            f"Incomplete local Track B cache {cache_dir}: missing page indices={missing}; "
            f"unexpected={unexpected}; invalid={invalid_files}"
        )


def _audit_local_cache(
    base: Path,
    level: str,
    selected_levels: list[str],
    canonical: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    """Extended local-only check against gitignored corrected pages_cache."""
    manifests: dict[str, dict[str, Any]] = {}
    for selected_level in selected_levels:
        data_dir = base / "data" / selected_level
        manifest_path = data_dir / "toc_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifests[selected_level] = manifest
        for cfg in manifest.get("subjects", []):
            guide_key = (selected_level, cfg.get("key"))
            if guide_key not in canonical:
                continue
            chapters = cfg.get("chapters") or []
            if not chapters or not isinstance(chapters[-1].get("page_range"), list):
                raise ValueError(f"Invalid manifest terminal page range for {guide_key}")
            total_pages = chapters[-1]["page_range"][1] + 1
            _validate_complete_cache(
                data_dir / "pages_cache" / cfg["key"], total_pages,
            )

    cache_summary: dict[str, Any] = apply(base, level, check=True)
    cache_summary.update({
        "status": "verified",
        "available": True,
        "extended_rebuild_check": True,
    })

    for selected_level in selected_levels:
        data_dir = base / "data" / selected_level
        manifest = manifests[selected_level]
        for cfg in manifest.get("subjects", []):
            key = cfg.get("key")
            guide_key = (selected_level, key)
            if guide_key not in canonical:
                continue
            actual = canonical[guide_key]
            path = data_dir / REVIEWED_CANONICAL[guide_key]["path"]
            expected_chapters: list[dict[str, str]] = []
            expected_ids_from_pages: set[str] = set()
            actual_chapters = {
                chapter.get("id"): chapter for chapter in actual.get("chapters") or []
            }
            for chapter_cfg in cfg.get("chapters", []):
                page_range = chapter_cfg.get("page_range")
                if not (
                    isinstance(page_range, list) and len(page_range) == 2
                    and all(isinstance(value, int) for value in page_range)
                ):
                    raise ValueError(f"{path}: invalid manifest page range for {chapter_cfg.get('id')}")
                parts: list[str] = []
                expected_indices: list[int] = []
                expected_page_ids: dict[int, list[str]] = {}
                in_practice_block = False
                for page_index in range(page_range[0], page_range[1] + 1):
                    cache_path = data_dir / "pages_cache" / key / f"page_{page_index:03d}.json"
                    if not cache_path.is_file():
                        raise ValueError(f"Local Track B cache is incomplete: missing {cache_path}")
                    entry = json.loads(cache_path.read_text(encoding="utf-8"))
                    if entry.get("type") == "practice":
                        in_practice_block = True
                        continue
                    if in_practice_block or entry.get("type") != "content":
                        continue
                    markdown = entry.get("markdown", "").strip()
                    if not markdown:
                        raise ValueError(f"{cache_path}: selected content page has no markdown")
                    parts.append(markdown)
                    expected_indices.append(page_index)
                    correction_ids = sorted({
                        item.get("id")
                        for item in entry.get("track_b_corrections", [])
                        if isinstance(item, dict) and isinstance(item.get("id"), str)
                    })
                    expected_page_ids[page_index] = correction_ids
                    expected_ids_from_pages.update(correction_ids)

                joined_parts = "\n\n".join(parts)
                full_content = f"# {chapter_cfg['title']}\n\n{joined_parts}".strip()
                expected_chapters.append({"id": chapter_cfg["id"], "content": full_content})

                actual_chapter = actual_chapters.get(chapter_cfg["id"])
                if actual_chapter is None:
                    raise ValueError(f"{path}: missing canonical chapter {chapter_cfg['id']}")
                actual_pages = actual_chapter.get("source_pages") or []
                if [page.get("index") for page in actual_pages] != expected_indices:
                    raise ValueError(f"{path}: stale source-page membership for {chapter_cfg['id']}")
                for source_page in actual_pages:
                    page_index = source_page["index"]
                    if source_page.get("semantic_correction_ids", []) != expected_page_ids[page_index]:
                        raise ValueError(
                            f"{path}: stale page correction provenance at index {page_index}"
                        )

            if _chapter_content_sha256(expected_chapters) != actual["source_content_sha256"]:
                raise ValueError(f"{path}: canonical Track B is stale relative to corrected pages_cache")
            if set(actual["semantic_correction_ids"]) != expected_ids_from_pages:
                raise ValueError(f"{path}: canonical correction provenance differs from pages_cache")
    return cache_summary


def audit_track_b_state(base: Path = BASE, level: str = "all") -> dict[str, Any]:
    """Two-layer, read-only Track B release gate.

    The committed layer always validates five reviewed canonical JSON files
    against fixed content SHA-256 values and registry correction IDs.  When all
    local gitignored pages_cache directories exist, an additional reconstruction
    comparison is mandatory.  A fresh clone with no pages_cache is valid.
    """
    validate_registry()
    selected_levels = ["初級", "中級"] if level == "all" else [level]
    selected_guide_keys = {
        guide_key for guide_key in REVIEWED_CANONICAL
        if guide_key[0] in selected_levels
    }
    expected_semantic_ids = {
        entry["id"] for entry in selected_patches(level)
    }
    expected_provenance = {
        (entry["level"], entry["key"]): entry["id"]
        for entry in PROVENANCE_CORRECTIONS
        if entry["level"] in selected_levels
    }
    canonical: dict[tuple[str, str], dict[str, Any]] = {}
    seen_semantic_ids: set[str] = set()
    seen_provenance_ids: set[str] = set()

    for guide_key in sorted(selected_guide_keys):
        selected_level, key = guide_key
        review = REVIEWED_CANONICAL[guide_key]
        path = base / "data" / selected_level / review["path"]
        if not path.is_file():
            raise ValueError(f"Missing reviewed canonical Track B guide: {path}")
        actual = json.loads(path.read_text(encoding="utf-8"))
        if actual.get("source_track") != "track_b_ocr_vision":
            raise ValueError(f"{path}: source_track provenance is missing or stale")
        if actual.get("source_mode") != "vision":
            raise ValueError(f"{path}: source_mode provenance is missing or stale")
        if actual.get("semantic_correction_layer") != "track_b_reviewed_v1":
            raise ValueError(f"{path}: semantic correction layer provenance is missing")

        guide_expected_ids = sorted({
            entry["id"]
            for entry in PATCHES
            if entry["level"] == selected_level and entry["key"] == key
        })
        actual_ids = actual.get("semantic_correction_ids")
        if actual_ids != guide_expected_ids:
            raise ValueError(
                f"{path}: semantic correction IDs are stale; "
                f"expected={guide_expected_ids}, actual={actual_ids}"
            )
        actual_page_ids: dict[int, list[str]] = {}
        for chapter in actual.get("chapters") or []:
            for source_page in chapter.get("source_pages") or []:
                page_index = source_page.get("index")
                if not isinstance(page_index, int) or page_index in actual_page_ids:
                    raise ValueError(f"{path}: invalid or duplicate source page index {page_index!r}")
                actual_page_ids[page_index] = source_page.get("semantic_correction_ids", [])
        expected_page_ids: dict[int, list[str]] = {}
        for entry in PATCHES:
            if entry["level"] == selected_level and entry["key"] == key:
                expected_page_ids.setdefault(entry["page_index"], []).append(entry["id"])
        expected_page_ids = {
            page_index: sorted(set(correction_ids))
            for page_index, correction_ids in expected_page_ids.items()
        }
        for page_index, actual_source_ids in actual_page_ids.items():
            if actual_source_ids != expected_page_ids.get(page_index, []):
                raise ValueError(
                    f"{path}: correction provenance is wrong at source page {page_index}"
                )
        missing_correction_pages = sorted(set(expected_page_ids) - set(actual_page_ids))
        if missing_correction_pages:
            raise ValueError(
                f"{path}: correction source pages are missing: {missing_correction_pages}"
            )
        page_ids = sorted({
            correction_id
            for correction_ids in actual_page_ids.values()
            for correction_id in correction_ids
        })
        if page_ids != guide_expected_ids:
            raise ValueError(f"{path}: page-level correction provenance is incomplete")

        actual_digest = _chapter_content_sha256(actual.get("chapters") or [])
        if actual.get("source_content_sha256") != actual_digest:
            raise ValueError(f"{path}: canonical content does not match its embedded fingerprint")
        if actual_digest != review["content_sha256"]:
            raise ValueError(
                f"{path}: canonical content differs from reviewed committed SHA-256"
            )
        if _source_pages_sha256(actual.get("chapters") or []) != review["source_pages_sha256"]:
            raise ValueError(
                f"{path}: source-page provenance differs from reviewed committed SHA-256"
            )

        canonical[guide_key] = actual
        seen_semantic_ids.update(actual_ids)
        seen_provenance_ids.add(expected_provenance[guide_key])

    if seen_semantic_ids != expected_semantic_ids:
        raise ValueError(
            f"Canonical semantic correction coverage mismatch: "
            f"missing={sorted(expected_semantic_ids - seen_semantic_ids)}, "
            f"extra={sorted(seen_semantic_ids - expected_semantic_ids)}"
        )
    expected_provenance_ids = set(expected_provenance.values())
    if seen_provenance_ids != expected_provenance_ids:
        raise ValueError(
            f"Canonical provenance coverage mismatch: "
            f"missing={sorted(expected_provenance_ids - seen_provenance_ids)}"
        )

    cache_dirs = [
        base / "data" / selected_level / "pages_cache" / key
        for selected_level, key in sorted(selected_guide_keys)
    ]
    cache_presence = [path.is_dir() for path in cache_dirs]
    if any(cache_presence) and not all(cache_presence):
        missing = [str(path) for path, present in zip(cache_dirs, cache_presence) if not present]
        raise ValueError(f"Partial local Track B cache; missing directories: {missing}")
    if all(cache_presence):
        cache_summary = _audit_local_cache(base, level, selected_levels, canonical)
    else:
        cache_summary = {
            "status": "not_available",
            "available": False,
            "extended_rebuild_check": False,
            "reason": "gitignored pages_cache is absent; committed reviewed canonical gate passed",
        }

    source_math_ids = {
        entry["id"] for entry in selected_patches(level)
        if entry["classification"] == "source_math_correction"
    }
    return {
        "status": "pass",
        "canonical_files": len(canonical),
        "ocr_or_extraction_corrections": len(expected_semantic_ids - source_math_ids),
        "source_math_corrections": len(source_math_ids),
        "provenance_corrections": len(expected_provenance_ids),
        "verified_inventory_ids": len(expected_semantic_ids | expected_provenance_ids),
        "remaining": 0,
        "committed_canonical": {
            "status": "verified",
            "fixed_content_sha256": len(canonical),
        },
        "cache": cache_summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--level", choices=["初級", "中級", "all"], default="all")
    parser.add_argument("--dry-run", action="store_true", help="驗證並顯示將套用的數量，不寫檔")
    parser.add_argument("--check", action="store_true", help="要求所有 correction 已在位，不寫檔")
    args = parser.parse_args()
    if args.dry_run and args.check:
        parser.error("--dry-run and --check are mutually exclusive")
    if args.check:
        report = audit_track_b_state(BASE, args.level)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    summary = apply(BASE, args.level, dry_run=args.dry_run)
    mode = "dry-run" if args.dry_run else "applied"
    print(
        f"Track B corrections ({mode}): {summary['logical_corrections']} logical IDs / "
        f"{summary['page_targets']} page targets; changed {summary['changed']}, "
        f"already applied {summary['already_applied']}"
    )
    if not args.dry_run and not args.check:
        print("Next: rebuild canonical guides with parse_guides.py for each selected level.")


if __name__ == "__main__":
    main()
