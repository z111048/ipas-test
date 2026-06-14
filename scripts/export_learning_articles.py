"""Export topic-oriented learning articles from generated guide content."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_GENERATED = ROOT / "frontend" / "src" / "generated"
GUIDE_OUTLINES_PATH = FRONTEND_GENERATED / "guideOutlines.json"
OUTPUT_DIR = FRONTEND_GENERATED / "learningArticles"

LEVELS = {
    "junior": {
        "label": "初級",
        "data_dir": ROOT / "data" / "初級",
    },
    "middle": {
        "label": "中級",
        "data_dir": ROOT / "data" / "中級",
    },
}

LEARNING_PATH_DEFINITIONS = [
    {
        "id": "ai-foundations",
        "title": "AI 基礎與機器學習入門",
        "description": "從人工智慧、資料處理、機器學習概念一路銜接到中級的機率、線性代數與最佳化基礎。",
        "articleIds": ["s1c1", "s1c2", "s1c3", "s1c4", "mid-s3c1", "mid-s3c2", "mid-s3c3", "mid-s3c4"],
    },
    {
        "id": "genai-practice",
        "title": "生成式 AI 應用與導入",
        "description": "先建立生成式 AI 與 No Code / Low Code 概念，再進入工具應用、導入評估、多模態與資料支撐。",
        "articleIds": ["s1c4", "s2c1", "s2c2", "s2c3", "mid-s1c3", "mid-s1c4", "mid-s2c12"],
    },
    {
        "id": "data-analytics",
        "title": "資料處理、統計與大數據分析",
        "description": "依序學習資料摘要、機率分佈、統計推論、收集清理、儲存管理、處理工具、分析方法與視覺化。",
        "articleIds": [
            "s1c2",
            "mid-s2c1",
            "mid-s2c2",
            "mid-s2c3",
            "mid-s2c4",
            "mid-s2c5",
            "mid-s2c6",
            "mid-s2c7",
            "mid-s2c8",
            "mid-s2c9",
        ],
    },
    {
        "id": "ml-engineering",
        "title": "模型建置、訓練與優化",
        "description": "聚焦從資料準備、模型選擇、演算法、深度學習到訓練評估與調校的完整模型工程流程。",
        "articleIds": ["s1c3", "mid-s1c8", "mid-s2c10", "mid-s3c4", "mid-s3c5", "mid-s3c6", "mid-s3c7", "mid-s3c8", "mid-s3c9", "mid-s3c10"],
    },
    {
        "id": "ai-solutions",
        "title": "AI 技術應用與系統落地",
        "description": "整理 NLP、電腦視覺、生成式 AI、多模態，以及鑑別式 AI / 生成式 AI 在大數據與系統整合中的應用。",
        "articleIds": ["mid-s1c1", "mid-s1c2", "mid-s1c3", "mid-s1c4", "mid-s2c11", "mid-s2c12", "mid-s1c9"],
    },
    {
        "id": "governance-risk",
        "title": "AI 導入、治理、風險與合規",
        "description": "從導入評估與規劃開始，延伸到風險管理、隱私安全、合規、偏見與公平性。",
        "articleIds": ["s2c3", "mid-s1c5", "mid-s1c6", "mid-s1c7", "mid-s1c9", "mid-s2c13", "mid-s3c11", "mid-s3c12"],
    },
]

ARTICLE_BLOCK_FIELDS = {
    "id",
    "type",
    "depth",
    "title",
    "text",
    "marker",
    "rows",
    "html",
    "formulas",
    "latex",
    "formulaOnly",
    "indentFirstLine",
    "pageIndex",
    "bbox",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def text_of_block(block: dict[str, Any]) -> str:
    if isinstance(block.get("title"), str):
        return block["title"]
    if isinstance(block.get("text"), str):
        return block["text"]
    if isinstance(block.get("rows"), list):
        cells: list[str] = []
        for row in block["rows"]:
            if isinstance(row, list):
                cells.extend(str(cell) for cell in row if cell)
        return " ".join(cells)
    return ""


def normalized_title(value: str) -> str:
    return re.sub(r"[\s:：()（）./\-、]+", "", value).lower()


def leading_heading_is_duplicate(block: dict[str, Any], article_title: str) -> bool:
    title = text_of_block(block)
    if not title:
        return False
    normalized_heading = normalized_title(title)
    normalized_article = normalized_title(article_title)
    return normalized_article in normalized_heading or normalized_heading in normalized_article


def estimate_word_count(blocks: list[dict[str, Any]]) -> int:
    return sum(len(text_of_block(block)) for block in blocks)


def article_excerpt(blocks: list[dict[str, Any]]) -> str:
    for block in blocks:
        if block.get("type") != "paragraph":
            continue
        text = re.sub(r"\s+", " ", text_of_block(block)).strip()
        if len(text) >= 24:
            return text[:120] + ("…" if len(text) > 120 else "")
    return ""


def normalize_article_blocks(raw_blocks: list[dict[str, Any]], article_title: str) -> list[dict[str, Any]]:
    heading_depths = [
        block.get("depth")
        for block in raw_blocks
        if block.get("type") == "heading" and isinstance(block.get("depth"), int)
    ]
    base_depth = min(heading_depths) if heading_depths else 2
    output: list[dict[str, Any]] = []

    for index, raw_block in enumerate(raw_blocks):
        if index == 0 and raw_block.get("type") == "heading" and leading_heading_is_duplicate(raw_block, article_title):
            continue
        block = {
            key: value
            for key, value in raw_block.items()
            if key in ARTICLE_BLOCK_FIELDS and value not in (None, [], {})
        }
        depth = raw_block.get("depth")
        if isinstance(depth, int):
            block["depth"] = max(2, min(6, depth - base_depth + 2))
        else:
            block["depth"] = 3
        output.append(block)
    return output


def build_sections(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sections = []
    for block in blocks:
        if block.get("type") != "heading":
            continue
        depth = block.get("depth")
        title = text_of_block(block)
        if isinstance(depth, int) and depth <= 4 and title:
            sections.append({
                "id": block["id"],
                "title": title,
                "depth": depth,
            })
    return sections


def subject_short_title(subject_title: str) -> str:
    return subject_title.split("：", 1)[-1]


def build_article(
    *,
    level_id: str,
    level_label: str,
    subject: dict[str, Any],
    subject_index: int,
    chapter: dict[str, Any],
    chapter_index: int,
    guide: dict[str, Any],
    node: dict[str, Any],
    content: dict[str, Any],
) -> dict[str, Any]:
    raw_blocks = content.get("blocks") or []
    if not isinstance(raw_blocks, list):
        raw_blocks = []
    blocks = normalize_article_blocks(raw_blocks, chapter["title"])
    word_count = estimate_word_count(blocks)
    page_range = node.get("pageRange") or chapter.get("page_range")
    source_page_range = page_range if isinstance(page_range, list) and len(page_range) == 2 else None
    content_ref = f"{chapter['id']}.json"

    return {
        "id": chapter["id"],
        "levelId": level_id,
        "levelLabel": level_label,
        "subjectId": subject["id"],
        "subjectTitle": subject["subject"],
        "subjectShortTitle": subject_short_title(subject["subject"]),
        "title": chapter["title"],
        "order": chapter_index + 1,
        "globalOrder": subject_index * 100 + chapter_index + 1,
        "route": f"/articles/{chapter['id']}",
        "guideRoute": f"/guide/{subject['id']}/{chapter['id']}",
        "practiceRoute": f"/practice/{subject['id']}/{chapter['id']}",
        "pathIds": [],
        "subtopics": chapter.get("subtopics", []),
        "excerpt": article_excerpt(blocks),
        "wordCount": word_count,
        "readingMinutes": max(1, round(word_count / 650)),
        "sectionCount": len(build_sections(blocks)),
        "source": {
            "guideKey": guide["key"],
            "nodeId": node["id"],
            "contentRef": content_ref,
            "sourceContentRef": node.get("contentRef"),
            "sourcePageRange": source_page_range,
            "pdf": subject.get("pdf"),
        },
        "sections": build_sections(blocks),
        "blocks": blocks,
    }


def build_learning_paths(articles_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    paths: list[dict[str, Any]] = []
    for definition in LEARNING_PATH_DEFINITIONS:
        article_ids = [
            article_id
            for article_id in definition["articleIds"]
            if article_id in articles_by_id
        ]
        if not article_ids:
            continue
        missing = sorted(set(definition["articleIds"]) - set(article_ids))
        if missing:
            print(f"Warning: path {definition['id']} skipped missing article ids: {', '.join(missing)}")
        level_ids = sorted({articles_by_id[article_id]["levelId"] for article_id in article_ids})
        estimated_minutes = sum(articles_by_id[article_id]["readingMinutes"] for article_id in article_ids)
        path = {
            "id": definition["id"],
            "title": definition["title"],
            "description": definition["description"],
            "articleIds": article_ids,
            "articleCount": len(article_ids),
            "levelIds": level_ids,
            "estimatedMinutes": estimated_minutes,
            "route": f"/articles?path={definition['id']}",
            "startingArticleId": article_ids[0],
        }
        for article_id in article_ids:
            articles_by_id[article_id]["pathIds"].append(path["id"])
        paths.append(path)
    return paths


def build_articles(level_filter: set[str] | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    guide_outlines = read_json(GUIDE_OUTLINES_PATH)
    all_articles: list[dict[str, Any]] = []
    levels: dict[str, Any] = {}

    for level_id, config in LEVELS.items():
        if level_filter and level_id not in level_filter:
            continue
        level_label = config["label"]
        manifest = read_json(config["data_dir"] / "toc_manifest.json")
        level_article_ids: list[str] = []
        subject_entries: list[dict[str, Any]] = []

        for subject_index, subject in enumerate(manifest["subjects"]):
            guide = guide_outlines["guides"].get(subject["id"])
            if not guide:
                raise RuntimeError(f"Missing guide outline for subject {subject['id']}")

            subject_article_ids: list[str] = []
            for chapter_index, chapter in enumerate(subject["chapters"]):
                node = guide["nodesById"].get(chapter["id"])
                if not node:
                    raise RuntimeError(f"Missing guide node for chapter {chapter['id']}")
                source_content_ref = node.get("contentRef")
                if not source_content_ref:
                    raise RuntimeError(f"Missing contentRef for chapter {chapter['id']}")
                content_path = FRONTEND_GENERATED / "guideContent" / guide["key"] / source_content_ref
                content = read_json(content_path)
                article = build_article(
                    level_id=level_id,
                    level_label=level_label,
                    subject=subject,
                    subject_index=subject_index,
                    chapter=chapter,
                    chapter_index=chapter_index,
                    guide=guide,
                    node=node,
                    content=content,
                )
                all_articles.append(article)
                subject_article_ids.append(article["id"])
                level_article_ids.append(article["id"])

            subject_entries.append({
                "id": subject["id"],
                "title": subject["subject"],
                "shortTitle": subject_short_title(subject["subject"]),
                "articleIds": subject_article_ids,
            })

        levels[level_id] = {
            "id": level_id,
            "label": level_label,
            "articleIds": level_article_ids,
            "subjects": subject_entries,
        }

    all_articles.sort(key=lambda article: (article["levelId"], article["subjectId"], article["order"]))
    articles_by_id = {article["id"]: article for article in all_articles}
    learning_paths = build_learning_paths(articles_by_id)
    for article in all_articles:
        write_json(OUTPUT_DIR / article["levelLabel"] / article["source"]["contentRef"], article)
    index = {
        "generatedAt": utc_now(),
        "articleCount": len(all_articles),
        "pathCount": len(learning_paths),
        "levels": levels,
        "learningPaths": learning_paths,
        "pathsById": {
            path["id"]: path
            for path in learning_paths
        },
        "flatArticleIds": [article["id"] for article in all_articles],
        "articlesById": {
            article["id"]: {
                key: article[key]
                for key in [
                    "id",
                    "levelId",
                    "levelLabel",
                    "subjectId",
                    "subjectTitle",
                    "subjectShortTitle",
                    "title",
                    "order",
                    "globalOrder",
                    "route",
                    "guideRoute",
                    "practiceRoute",
                    "pathIds",
                    "subtopics",
                    "excerpt",
                    "wordCount",
                    "readingMinutes",
                    "sectionCount",
                    "source",
                ]
            }
            for article in all_articles
        },
    }
    return index, all_articles


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--level",
        choices=sorted(LEVELS.keys()) + [config["label"] for config in LEVELS.values()],
        help="Limit export to one level; defaults to all levels.",
    )
    return parser.parse_args()


def normalized_level_filter(level: str | None) -> set[str] | None:
    if not level:
        return None
    for level_id, config in LEVELS.items():
        if level in (level_id, config["label"]):
            return {level_id}
    raise ValueError(f"Unsupported level: {level}")


def main() -> None:
    args = parse_args()
    index, articles = build_articles(normalized_level_filter(args.level))
    write_json(OUTPUT_DIR / "index.json", index)
    print(f"Wrote {len(articles)} learning articles to {OUTPUT_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
