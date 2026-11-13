# 章節脈絡圖草稿格式（drafts/<nodeId>.json）

目的：把一章學習指引「整理、歸納、拆解、重組」，讓學生先看懂脈絡再讀原文。只能改寫與歸納原文，**不得加入原文沒有的知識**。

```json
{
  "chapter": {"guideKey": "初級-guide1", "nodeId": "s1c3", "label": "初級 科目一・3.3 機器學習概念"},
  "headline": "一張圖看懂機器學習這一章",
  "lede": "2–3 句：這章在講什麼、學生最該先抓住什麼。",
  "story": [{"step": "是什麼", "title": "≤10 字", "text": "≤40 字"}],
  "lanes": [{"id": "types", "name": "學習方式"}],
  "nodes": [{"id": "sup", "label": "監督式學習", "lane": "types", "parent": "ml", "concept": "監督式學習",
             "gist": "一句話重點，≤60 字", "src": [{"block": 21, "quote": "以「有標記的數據」為基礎"}]}],
  "edges": [{"a": "scale", "b": "gd", "kind": "cross", "label": "≤14 字，說明關係", "block": 65, "quote": "原文短句"}],
  "confusions": [{"a": "Min-Max", "b": "Z-score", "text": "≤70 字，一句講清差別", "blocks": [62, 64]}],
  "gaps": [{"name": "決策樹", "block": 113}]
}
```

規則（驗證器 `validate_render.py` 會機械檢查，不過就失敗）：
- `story` 3–5 站，依學生理解順序排（不一定照原文順序）。
- `lanes` 2–4 條，是這章知識的幾條「軸線」（例：學習方式／流程／挑戰）。
- `nodes` 12–30 個。恰好一個核心節點：`"lane": null, "parent": null`。其他節點必須有 `lane`；`parent` 指向同一 lane 的上層節點，或核心節點，或 null（該 lane 的頂層）。
- `src[].quote` 必須是該 `block` 原文的**逐字子字串**（忽略空白），6–40 字。每個節點至少 1 個。
- `gist` 裡出現的數字，必須出現在它引用的區塊原文中。
- `concept` 填受控詞彙表的正式名稱（清單在 `concepts_<nodeId>.txt`），沒有對應就填 null；考古題數由程式自動填，不要自己寫。
- `edges` 只放**樹狀結構以外**的關係：`flow`（流程的下一步）或 `cross`（跨段落、跨軸線的關聯，這是這張圖最有價值的部分）。每條都要有逐字 `quote`。至少 5 條 `cross`。
- `confusions` 3–8 組學生容易搞混的概念；`text` 必須能由 `blocks` 原文支持。
- `gaps`：章末練習或題目考了、但本章正文沒說明的概念（沒有就空陣列）。`block` 指向出現它的題目區塊。
- 文案用繁體中文，不得提到 AI 生成、模型產生等字眼。
