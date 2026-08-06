# Pipeline Reference（腳本目錄與操作手冊）

> 本檔是 pipeline 細節的**唯一權威來源**。CLAUDE.md 只放路由；AGENTS.md（Codex CLI 用）內容較舊，
> 與本檔衝突時以本檔為準。更新腳本行為時**只改本檔**，不要回頭加肥 CLAUDE.md。
> 內容繼承自 2026-07-13 之前的 CLAUDE.md（備份在 `playbook/backups/`），並修正了已驗證的過時處。

## 使用方式（給接手的模型）

不要整檔讀。先看下方目錄，用 Grep 跳到需要的小節。

- 跑 guide 內容 pipeline → §1
- 跑品質審核 → §2、§4
- 跑考題 pipeline → §3
- 跑 Colab notebook → §5
- 前端 build / 資料匯出 → §6
- 某支腳本是幹嘛的 → §7 腳本目錄
- 輸出檔案的意義與 gitignore 狀態 → §8
- 跑完 pipeline 怎麼驗證 → §9
- **必補的手動修正（s1c4）→ §10（最容易漏，重跑 export 後必看）**

通用規則：
- 資料 pipeline 腳本都支援 `--level`，路徑解析為 `data/{level}/`。⚠️ **預設值不一致**：
  多數預設 `初級`，但 `supplement_guide_from_audit.py`、`generate_colab_notebooks.py`、
  `run_codex_exam_reference_answers.py`、`export_exam_reference_answers.py`、
  `export_colab_metadata.py`、`export_question_generation_data.py`、`llm_review_guide_headings.py`
  預設 `中級`（2026-07-13 grep argparse 驗證）。**一律顯式帶 `--level`，不要依賴預設**——
  尤其 `supplement_guide_from_audit.py` 會覆寫 guide JSON，跑錯等級就是資料事故。
- `data/{level}/toc_manifest.json` 是章節定義 SSOT，由 `build_manifest.py` 生成、需提交。
  任何地方都不得複製章節定義。
- 多數腳本硬編 `BASE = Path('/home/james/projects/ipas-test')`（少數 export 腳本用
  `Path(__file__).resolve().parents[1]` 相對解析），搬 repo 要逐支檢查。
- 新增等級：① `build_manifest.py` 的 `GUIDES_BY_LEVEL` 填章節定義 ② `build_manifest.py --level 中級`。
- 依賴：`uv sync`（Python：pdfplumber、PyMuPDF、anthropic、google-genai）；
  `cd frontend && npm install`（Node）。
- API 金鑰：`GEMINI_API_KEY`（vision 腳本，模型 gemini-2.5-flash，可用 `GOOGLE_MODEL` 覆蓋）、
  `ANTHROPIC_API_KEY`（generate_questions、audit_chapters，用 claude-haiku-4-5）。
  `multi_ai_pipeline.py` 與各 `codex_*` 腳本需要已認證的 `gemini`/`codex`/`claude` CLI。

---

## §0 章節目錄索引（僅章節定義或 PDF 異動時執行）

```bash
uv run python3 scripts/build_manifest.py --level 初級        # → data/初級/toc_manifest.json
python3 scripts/extract_pdf_pages_structured.py --level 初級 --all --force
python3 scripts/clean_pdf_page_text.py --level 初級 --all
python3 scripts/build_guide_tree.py --level 初級 --all       # 驗證過的章節樹（AGENTS.md 路線）
python3 scripts/export_guide_outline_data.py --all-levels --use-guide-tree   # ⚠️ 見 §10 陷阱
python3 scripts/codex_review_pdf_pages.py --level 初級 --key guide1 --page 7 --force
python3 scripts/build_pdf_outline.py --level 初級 --all
python3 scripts/export_pdf_image_gallery.py --level 初級 --force
```

⚠️ `export_guide_outline_data.py` 兩個陷阱（詳見 §10）：
1. 會先 rmtree 清空 `frontend/src/generated/guideContent/` 再重建——**沒帶 `--all-levels` 中級檔案就永久消失**。
2. 跑完必須補回 s1c4 的兩個手動 heading 修正。

## §1 Guide 內容 pipeline（Gemini Vision 提取，主路線）

```bash
# Step 1: 每頁轉圖送 Gemini Vision，快取於 data/{level}/pages_cache/（gitignored、重建花錢）
uv run python3 scripts/pdf_vision_extract.py --level 初級 --all        # 兩科全跑（約 133 頁）
uv run python3 scripts/pdf_vision_extract.py --level 初級 --subject 1  # 單科
uv run python3 scripts/pdf_vision_extract.py --level 初級 --subject 1 --dry-run  # 估費用
uv run python3 scripts/pdf_vision_extract.py --level 初級 --subject 1 --force    # 強制重跑（會覆蓋快取）
uv run python3 scripts/pdf_vision_extract.py --level 中級 --chapter mid-s1c1     # 單章
uv run python3 scripts/pdf_vision_extract.py --level 中級 --page-range 10 25     # 1-based 頁碼範圍

# Step 2: 組裝章節 JSON（偵測到 pages_cache → vision mode；否則 fallback regex mode）
uv run python3 scripts/parse_guides.py --level 初級 [--subject 1]
# → data/初級/guide/subject{1,2}_guide.json

# Step 2b: PDF 原頁截圖（前端摺疊區顯示原始版面）
python3 scripts/render_guide_page_images.py --level 初級 --all
# → frontend/public/guide-pages/{level}/{key}/
```

## §1b 學習指引完整階層樹

```bash
python3 scripts/export_guide_hierarchy.py                    # → frontend/src/generated/guideHierarchy.json
python3 scripts/export_guide_hierarchy.py --print-tree s1    # 印出來目視檢查（s1/s2/mid-s1/mid-s2/mid-s3）
```

現有資料裡階層是斷成兩段的：`guideOutlines.json` 只到「節」（64 節點），節以下的標題
散在各章的 `blocks[]` 與 `headings[]`，彼此沒有父子關係。本腳本把兩段接成一棵樹
（**1,207 節點**：23 章 + 41 節 + 1,143 標題，最深 6 層），並用 `guide_ocr` 補回
Track A 漏抓的 `N.` 層（74 個）。

只讀既有產物、不改任何來源，可隨時重跑；跑在 `export_guide_outline_data.py` 之後。

三個實作重點（改動前先讀，都是踩過的坑）：
- **章不能與其下的節重複收標題**。章的 `pageRange` 涵蓋所有節、content 也是節的聯集，
  有子節點的章只保留「子節點頁範圍沒涵蓋到」的標題。
- **`blocks` 與 `headings[]` 互補，缺一不可**。初級 s1c1 的 blocks 只到 A. 層（缺 a. 層），
  中級 mid-s2c8 的 `headings[]` 整個是空的。以項目多的那邊當主幹，另一邊補頁碼。
- **補回的標題不能只按頁碼插入**。同一頁常有多個標題，只看頁碼會把「3. 資料處理與分析」
  插到同頁但實際在它前面的「E. 專家系統」之前，讓 E. 變成它的子項。同頁內要用
  guide_ocr 該頁的標題順序決定先後。

節以下的節點是既有章節頁的錨點（`href = {route}#{anchor}`），**前端路由完全不用動**。
目前前端尚未消費這份檔案。

## §2 Guide 品質審核（PDF 更新後執行）

```bash
# Step A: Gemini Vision 逐頁結構審核（AUDIT_PROMPT，獨立於 pages_cache，不可互換）
uv run python3 scripts/pdf_vision_audit.py --level 中級 --subject 1 [--page 6]
# → data/{level}/audit_cache/{key}/page_NNN.json（gitignored）

# Step B: Codex CLI 比對 audit_cache vs subject{N}_guide.json 標題結構
python3 scripts/codex_audit_compare.py --level 中級 --subject 1 [--chapter mid-s1c1] [--dry-run]
# → data/{level}/audit_compare/{key}/{chapter_id}.json + summary.json（gitignored）
# status: ok / warn / fail

# Step C: 補充 fail 章節（從 audit_cache 重組 Markdown 寫回 guide JSON，原檔備份為 *.bak）
uv run python3 scripts/supplement_guide_from_audit.py --level 中級 --subject 1 [--chapter ...]
uv run python3 scripts/supplement_guide_from_audit.py --level 中級 --all --strategy all  # 強制覆蓋 ok 章節
uv run python3 scripts/supplement_guide_from_audit.py --level 中級 --subject 1 --source pages_cache

# Step D: LLM 章節內容審核（確認 subtopics 覆蓋、無錯置）
uv run python3 scripts/audit_chapters.py --level 初級 --all [--subject 1] [--chapter s1c1] [--dry-run]
# → data/初級/guide/subject{N}_audit_report.json（overall_status: PASS/WARN/FAIL）
# WARN/FAIL 章節要先處理，才能拿去出題
```

## §3 考題 pipeline

```bash
uv run python3 scripts/extract_pdfs.py --level 初級      # PDFs → data/初級/extracted/*.{txt,json}
uv run python3 scripts/gemini_exam_vision_extract.py --level 中級 --key exam2 [--dry-run]
# 官方考題 PDF 的 Vision OCR（題目/答案/共用題幹/圖片參照 schema），快取 data/{level}/exam_pages_cache/
uv run python3 scripts/parse_exams_v2.py --level 初級
# → mock_exam1.json, mock_exam2.json, sample_exam.json（subject{N}_questions.json 是人工策展，不會被覆蓋）
python3 scripts/verify_data_alignment.py --level 初級    # 一致性檢查，必跑

# 選用：Claude API 出題 / 補 card 欄位
uv run python3 scripts/generate_questions.py --level 初級 --subject 1
uv run python3 scripts/generate_questions.py --level 初級 --enrich

# 選用：多 AI pipeline（Gemini 出題 → Codex 審核 → Claude 完稿 → 三 AI 答題驗證，2+ 答錯 → flagged.json）
python3 scripts/multi_ai_pipeline.py --level 初級 --subject 1 [--chapter s1c1] [--count 3] [--dry-run]
# 中間產物 data/{level}/pipeline/<run_id>/（gitignored）；最終合併進 subject{N}_questions.json
```

## §4 官方考題詳解（Codex reference answers）

```bash
# BM25 式檢索 top-k guide 片段 → 寫 prompt → codex exec 產出每題 JSON（validate schema）
python3 scripts/run_codex_exam_reference_answers.py --level 初級 --exam all [--run] [--question-id ...] [--limit N] [--force]
# 不帶 --run 只寫 prompts。輸出 data/{level}/pipeline/exam_reference_answers/{exam_key}/outputs/

# 發佈到前端
python3 scripts/export_exam_reference_answers.py --level 初級
# → frontend/src/generated/examReferenceAnswers/{route_key}.json（exam key → route key 映射在 ROUTES_BY_LEVEL）
```

## §5 Colab notebook pipeline（中級章節實作練習）

```bash
# Stage 1 Codex 生成草稿 → Stage 2 靜態+執行檢查（ast.parse + subprocess）→ Stage 3 Codex 審核
python3 scripts/generate_colab_notebooks.py --level 中級 --all | --subject 2 | --chapter mid-s2c1 [--force] [--dry-run]
# pass/warn → notebooks/中級/{chapter_id}.ipynb（committed）
#           + frontend/src/generated/colabNotebooks/中級/{chapter_id}.json（committed）
# fail → data/{level}/pipeline/colab_notebooks/{chapter_id}/flagged.json 需人工審查

# 手動編輯 .ipynb 後重新匯出前端 metadata
python3 scripts/export_colab_metadata.py --level 中級 [--chapter mid-s2c1]

# 執行驗證（使用者手動）：colab execute notebooks/中級/mid-s2c1.ipynb
```

前端：GuidePage 在中級章節底部自動顯示「⚗️ 實作練習」摺疊區塊。

## §6 前端

```bash
cd frontend && npm run dev -- --host    # dev server；WSL 下 --host 才能從 Windows 存取
uv run python3 scripts/build_web.py     # production build → docs/（gitignored；Pages 由 GitHub Actions 建）
```

- Vite + React 19 + TypeScript + Tailwind CSS v4 + React Router v6（HashRouter，避免 Pages 404）+ Zustand。
- alias：`@data` → `data/初級/`、`@data-mid` → `data/中級/`（vite.config.ts:24-25，已驗證存在）。
- 所有 JSON build time 靜態匯入，無 runtime fetch。章節導覽一律從 `toc_manifest.json` 讀，
  不得加回硬編章節陣列。
- Guide 頁優先渲染 `GuideContent.blocks[]`（heading/paragraph/list_item/table/question/answer，
  depth 不限），無 blocks 才 fallback Markdown。「本節階層」側欄只顯示 depth 3–4。
- 練習題頁路由 `/practice/:subjectId/:chapterId`，行動版藏在 `☰` 抽屜——改導覽要檢查行動版。
<!-- 2026-07-13: 形象網站改版後補充版型事實 -->
- App shell（App.tsx）：`main` 是唯一捲動容器（body 不捲），sidebar 桌面版常駐、行動版抽屜。
  外層 row 是 `h-[calc(100vh-3.5rem)] overflow-hidden` **且不可加回 `flex-1`**——flex-basis 會蓋掉
  height，造成 body 捲動、sidebar 捲走（2026-07-13 修過的 bug）。路由切換時 main 自動捲回頂部。
- 全站 Footer（`components/layout/Footer.tsx`）：guide 路由不顯示；短頁面靠 main 的
  `flex flex-col` + footer 外層 `mt-auto` 貼底。
- 首頁 hero 用 `index.css` 的 `.hero-panel/.hero-grid/.hero-chip/.btn-hero/.btn-hero-ghost`；
  字體 Noto Sans TC 由 `index.html` 從 Google Fonts 載入（meta description/og 也在該檔）。
- 概念圖卡頁 `/visuals`（`VisualCardsPage.tsx`）：browse `guideImages.json`（944KB，route-lazy），
  開卡片時 lazy-load `guideContent/{level}-{guideKey}/{sourceNodeId}.json` 並用 `extractSection`
  切出對應標題的 markdown（~97% 命中，fallback 章節簡介）。行動版卡片置中 + `break-words`。
- **商品化文案規則**：見 CLAUDE.md 不變量（使用者可見文案不得透露 AI 生成）。

## §7 腳本目錄（依用途分組）

**SSOT / 抽取**
- `build_manifest.py` — 章節定義 SSOT 生成器，唯一硬編 `GUIDES_BY_LEVEL` 之處；開 PDF 算 `page_range`（0-based）寫入 `toc_manifest.json`。
- `extract_pdfs.py` — pdfplumber 為主、PyMuPDF fallback 的整檔文字/表格抽取 → `extracted/`。guide PDF 清單來自 manifest，考題 PDF 在 `EXAM_PDFS_BY_LEVEL`。
- `extract_pdf_pages_structured.py` — 頁面忠實抽取：每頁文字 + text/image/table bbox + 裁切 PNG → `page_extract/{key}/assets/`。
- `clean_pdf_page_text.py` — 清 header/footer/頁碼/表格標籤、標記跨頁接續、重建 per-PDF outline → `page_clean/{key}/`。
- `pdf_vision_extract.py` — 每頁 PNG（2x）送 Gemini Vision → `pages_cache/{key}/page_NNN.json`（{type, headings, markdown, usage}）；完成後自動生成 `page_index.json`。重跑只補 missing/failed。
- `gemini_exam_vision_extract.py` — 考題 PDF 的 Vision OCR（獨立 schema）→ `exam_pages_cache/`。

**組裝 / 解析**
- `parse_guides.py` — 從 pages_cache（vision mode，優先）或 extracted（regex mode，快取 <80% 時的緊急 fallback）組章節 JSON → `guide/subject{N}_guide.json`（`content_format: 'markdown'`）。跑完確認印出 `[vision mode]`。
- `parse_exams_v2.py` — 從 extracted JSON 解析題目/答案表（處理全形 A-D 與括號）→ `questions/mock_exam{1,2}.json, sample_exam.json`。
- `build_guide_tree.py` — 從 page_clean 建驗證過的章節樹（heading 深度、sibling 連續性、頁範圍、內嵌習題檢查）→ `guide_tree/{key}/tree.json, blocks.json, warnings.json`（gitignored）。
- `build_pdf_outline.py` — 從 page_extract 建可審閱的 PDF 階層 outline（有 Vision headings 用之，否則 regex）→ `outline/{key}_outline.{json,md}`。

**審核**
- `audit_chapters.py` — Claude Haiku 逐章審 subtopics 覆蓋 → `subject{N}_audit_report.json`。
- `pdf_vision_audit.py` — 第二次 Vision pass（AUDIT_PROMPT，結構化 blocks）→ `audit_cache/`。用途是審核與增補，不是內容替換。
- `codex_audit_compare.py` — Codex CLI 比對 audit_cache 標題結構 vs guide JSON → `audit_compare/`。
- `supplement_guide_from_audit.py` — 用 audit_cache（或 pages_cache）重組 Markdown 補 fail 章節，原檔備 `*.bak`。
- `codex_review_pdf_pages.py` — Codex CLI（read-only sandbox）逐頁審 cleaned pages → `codex_page_review/{key}/`。
- `verify_data_alignment.py` — manifest vs build_manifest vs PDF 頁標 vs guide/questions 一致性檢查。
- `llm_review_guide_headings.py`、`question_dedupe.py`、`annotate_exam_code_images.py` — 輔助工具（用前先讀 docstring）。

**前端匯出（`frontend/src/generated/` 是 committed 靜態輸入）**
- `export_guide_outline_data.py` — ⚠️ 見 §10。page_clean/guide_tree → `guideOutlines.json` + 分拆 per-node `guideContent/{key}/`（前端 GuidePage 讀的是這個，**不是** `data/*/guide/*.json`）。
- `export_guide_embedded_exercises.py` — 抽 guide PDF 內嵌官方習題 → `questions/subject{N}_guide_exercises.json`（與 AI 生成題分開）。
- `export_question_generation_data.py` — 匯出出題 pipeline 的 seed（guide 內容 + 既有題目），並初始化/保留 `subject{N}_questions.json`。
- `export_pdf_image_gallery.py` — page_extract 裁圖 → `frontend/public/pdf-assets/{level}/` + `gallery.json`（`#/images` 檢視器）。
- `export_resource_summary.py` — 章節/題數/覆蓋統計 + `visuals` 概念圖卡計數 → `resourceSummary.json`（首頁統計用；題目 JSON 得以 lazy load）。
- `export_exam_reference_answers.py`、`export_colab_metadata.py`、`export_guide_images_data.py`、`export_guide_image_units.py`、`export_learning_articles.py`、`export_guide_exam_annotations.py` — 各自把後端產物轉前端 JSON；改了上游資料記得重跑對應那支。
- `render_guide_page_images.py` — guide JSON `source_pages` 的 PDF 截圖 → `frontend/public/guide-pages/`。

**生成（花錢/花時間）**
- `generate_questions.py` — Claude API 出題（`--subject N`）或補 card 欄位（`--enrich`）。`--dry-run` 先看 prompt。
- `multi_ai_pipeline.py` — 三 CLI（gemini/codex/claude）subprocess pipeline，含答題驗證與 flagged。
- `generate_colab_notebooks.py` — 三階段 Colab notebook pipeline（見 §5）。
- `generate_images.py` — Codex 圖像 API 逐 unit 生成資訊圖 → WebP → `frontend/public/images/`。
- `run_codex_exam_reference_answers.py` — 見 §4。
- `build_codex_*_prompts.py` / `run_codex_*_generation.py` / `merge_codex_mock_exam_outputs.py` / `validate_codex_*_output.py` / `export_codex_mock_exam_questions.py` — Codex 批次出題家族：build prompts → run → validate → merge → export。

**Build**
- `build_web.py` — 薄包裝，跑 `frontend/ && npm run build` → `docs/`。

## §8 輸出檔案與 gitignore 狀態

**Committed（改了要提交）**：`data/{level}/toc_manifest.json`（SSOT）、`data/{level}/questions/*.json`、
`data/{level}/guide/subject{N}_guide.json`（tracked，`git ls-files` 已驗證；guide/ 下被忽略的只有
`*.md`、`*.bak`、`*_nested.json`、`*_audit_report.json`、`*_flagged.json`、`*_validation_report.json`）、
`notebooks/{level}/*.ipynb`、`frontend/src/generated/**`、`frontend/public/**`。

**Gitignored（刪了救不回；vision 快取重建要花 API 錢）**：`data/*/extracted/`、`page_extract/`、
`page_clean/`、`guide_tree/`、`codex_page_review/`、`outline/`、`pages_cache/`、`audit_cache/`、
`audit_compare/`、`exam_pages_cache/`（未列於 .gitignore 但同性質，見 git status）、`pipeline/`、
`analysis/`、`logs/`、`docs/`、`.claude/`、`.env`、`ref/`（`data/*/guide/` 只忽略上面
Committed 段列出的六類後綴，`subject{N}_guide.json` 本體是 tracked）。

**視為 build artifacts**：`data/{level}/questions/*.json`、`data/{level}/guide/*.json`、`docs/`。
只有刻意策展內容時才手動編輯 JSON，且要在 commit message 說明。
注意 `subject{1,2}_questions.json` 是人工策展，`parse_exams_v2.py` 不會覆蓋它。

**guide/ 的雙軌真相**（易混淆）：
- `data/{level}/guide/subject{N}_guide.json` — 後端章節 JSON，給 audit/compare/supplement 腳本用。
- 前端 GuidePage 讀的是 `frontend/src/generated/guideContent/`（由 `export_guide_outline_data.py`
  從 `page_clean/`/`guide_tree/` 生成）。**兩者來源不同，改一邊不會影響另一邊。**

**題目 schema（擴充版）**：
```json
{
  "id": "s1c1q1", "question": "...", "options": {"A":"...","B":"...","C":"...","D":"..."},
  "answer": "C", "explanation": "...",
  "card": {"concept":"...","mnemonic":"...","confusion":"...","frequency":"高/中/低"},
  "difficulty": "易/中/難", "type": "概念定義型", "tags": ["..."],
  "generated_by": "multi_ai_pipeline | generate_questions | manual"
}
```

## §9 驗證清單（無自動測試，靠這份）

Pipeline 跑完後：
1. `toc_manifest.json` 存在且所有章節 `page_range` 非 null。
2. `python3 scripts/verify_data_alignment.py --level {level}` 通過。
3. `pdf_vision_extract.py` 後：`pages_cache/{key}/summary.json` 的 missing/error 為 0，`page_index.json` 存在。
4. `parse_guides.py` 印出 `[vision mode]`（不是 regex mode），每章 >1000 字。
5. `audit_chapters.py` 報告 PASS；WARN/FAIL 章節先處理再出題。
6. `parse_exams_v2.py`：exam1/exam2 解析數 <50 是已知現象（部分 PDF 列無法機器解析），看 WARN 行與實際 JSON 總數。
7. 前端改動後：`cd frontend && npm run build` 零 TypeScript 錯誤（這是唯一的型別防線）。
8. 手動 spot-check：dev server 看題目渲染、答題後 card 面板出現（card 面板沒出現先確認
   題目 JSON 是否真的有 `card` 欄位，再懷疑前端）、行動版 `☰` 抽屜有 `✏️` 練習題入口。
9. 看 `logs/` 有無抽取/解析錯誤。
10. 未來自動測試放 `tests/test_*.py`。

## §10 已知手動修正（重跑 export 後必補回）⚠️

### 前置陷阱：`export_guide_outline_data.py` 必帶 `--all-levels`

腳本會先 `shutil.rmtree` 清空 `frontend/src/generated/guideContent/` 再重建。
預設 `--level 初級` 只重建初級 → **中級檔案永久消失**（2026-06-06 實際發生過）。
跑完立刻 `git status frontend/src/generated/guideContent/` 確認 mid-* 目錄還在。

### 修正 1、2 已經腳本化（2026-08-06）

```bash
uv run python3 scripts/export_guide_outline_data.py --all-levels
python3 scripts/apply_manual_guide_fixes.py     # ← 緊接著跑，冪等，可重複執行
```

原本是下面兩段「複製貼上執行」的程式碼，且**字串對不上時靜默不改**，
造成「以為補好了其實沒補」。腳本版對不上會**直接報錯中斷**（要放行加 `--no-strict`），
對照表在 `apply_manual_guide_fixes.py` 的 `DEMOTE_HEADINGS` / `SHORTEN_HEADINGS`。
以下兩段保留為修正內容的說明，不必再手動執行。

### 修正 1：s1c4 本節階層 heading 層級（6 個 h4 → h3）

問題：腳本對所有 `（\d+）` 開頭行一律輸出 `####`，但 PDF 中同符號用於兩個嵌套層次
（x 座標同為 70.2，無法自動判斷），導致「本節階層」出現 `（1）→（1）` 同層。

```python
import json
from pathlib import Path

s1c4 = Path('frontend/src/generated/guideContent/初級-guide1/s1c4.json')
data = json.loads(s1c4.read_text(encoding='utf-8'))
content = data['content']
fixes = [
    ('#### （1）鑑別式AI 的原理與應用\n',        '### （1）鑑別式AI 的原理與應用\n'),
    ('#### （2）生成式AI 的原理與應用\n',         '### （2）生成式AI 的原理與應用\n'),
    ('#### （3）鑑別式AI 與生成式AI 的技術差異\n','### （3）鑑別式AI 與生成式AI 的技術差異\n'),
    ('#### （1）整合應用的價值\n',               '### （1）整合應用的價值\n'),
    ('#### （2）整合應用的技術優勢\n',            '### （2）整合應用的技術優勢\n'),
    ('#### （3）整合應用的挑戰與解決策略\n',      '### （3）整合應用的挑戰與解決策略\n'),
]
targets = {f.split('\n')[0].lstrip('#').strip() for f, _ in fixes}
for old, new in fixes:
    content = content.replace(old, new)
data['content'] = content
for h in data.get('headings', []):
    if h.get('title') in targets and h.get('level') == 4:
        h['level'] = 3
s1c4.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
```

### 修正 2：s1c4 H4 標題截短（**在修正 1 之後執行**）

問題：H3 節下的 H4 模型條目仍帶 `（1）（2）...` 前綴，造成側欄同層視覺混淆。

```python
import json
from pathlib import Path

s1c4 = Path('frontend/src/generated/guideContent/初級-guide1/s1c4.json')
data = json.loads(s1c4.read_text(encoding='utf-8'))
fixes = {
    '（1） 邏輯迴歸（Logistic Regression）是鑑別式AI 中最簡單且最基礎的分類模型': '邏輯迴歸（Logistic Regression）',
    '（2） 支援向量機（Support Vector Machine, SVM）是一種強大的分類模型，其核心': '支援向量機（SVM）',
    '（3） 決策樹（Decision Tree）是一種基於樹形結構進行數據分類的模型。其透過': '決策樹（Decision Tree）',
    '（4） 隨機森林（Random Forest）是決策樹的集成學習方法，其透過構建多棵決策': '隨機森林（Random Forest）',
    '（5） 神經網路（Neural Networks）是一種模擬生物神經系統的非線性模型，透過': '神經網路（Neural Networks）',
    '（1） 生成對抗網路（Generative Adversarial Networks, GAN）是生成式AI 中最具': '生成對抗網路（GAN）',
    '（2） 變分自編碼器（Variational Autoencoders, VAE）是一種基於概率生成模型的': '變分自編碼器（VAE）',
    '（3） 擴散模型（Diffusion Models）是一種基於逐步添加與去除雜訊的數據生成方': '擴散模型（Diffusion Models）',
}
for h in data.get('headings', []):
    if h['title'] in fixes:
        h['title'] = fixes[h['title']]
s1c4.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
```

觸發時機：每次執行 `export_guide_outline_data.py`（含 `--all-levels`）後跑
`scripts/apply_manual_guide_fixes.py`，然後 `npm run build` 驗證。

### 修正 4：官方勘誤表（2026-08-06 新增，已腳本化）

官方另發佈學習指引勘誤表（初級 3 頁、中級 7 頁，PDF 在 `data/{level}/pdfs/`，
OCR 成果在 `data/{level}/guide_ocr/errata/`）。內容是「頁碼 / 行數段落 / 原內容 / 更正後內容」
四欄表，多數是用字更正（反饋→回饋、攝像頭→鏡頭、合同→合約、ChatGTP→ChatGPT），
少數是整段改寫（初級 3-31 答案由 B 改為 A、中級 4-34 PDPA 整段重寫）。

```bash
python3 scripts/build_errata.py                 # 勘誤表 OCR → data/{level}/errata_corrections.json
python3 scripts/apply_errata.py [--dry-run]     # 套進 pages_cache 與 page_extract
```

**執行順序有硬性要求**——勘誤是疊加層，套在兩條軌的轉接產物上，重跑轉接層會沖掉：

```
ocr_extract.py       → apply_errata.py → parse_guides.py                （Track B）
merge_guide_ocr.py   → apply_errata.py → clean_pdf_page_text.py
                                       → export_guide_outline_data.py   （Track A）
```

不改 `data/{level}/guide_ocr/`：那是 OCR 的忠實紀錄，要能對回原稿印的內容。

**自動化覆蓋率有限，這是預期的**：勘誤表對「原內容」的轉錄與講義實際文字有標點、
條列符號、斷行的差異，比對不一定成功。目前 28 筆中 7 筆兩軌都完整套用、
5 筆只套用了其中一軌，其餘需人工處理——清單在 `data/{level}/errata_unresolved.json`。
採**全有或全無**策略：一筆勘誤的片段沒有全部定位到就整筆不動，
因為只改一半會產生新舊混雜的段落，比不改更糟。

### 修正 3（已改為自動，留紀錄）：guideContent `content` 的 LaTeX 公式

2026-06-10 的 commit `3710342`「patch LaTeX formulas」手工在 13 個章節檔的 `content`
補了 **98 處 `$$...$$`**，把 PDF 文字層攤平的公式亂碼（「算術平均= 𝑥1 + 𝑥2 + ⋯+ 𝑥𝑛 𝑛」，
數學斜體碼點 U+1D400–U+1D7FF）換成可渲染的 LaTeX。**那批修補沒有留在任何腳本裡**，
重跑 export 就會全數消失——2026-08-06 重跑時才發現。

2026-08-06 起 `export_guide_outline_data.py` 新增 `inject_formulas_into_markdown()`
自動做這件事（來源是 `enrich_guide_blocks` 掛在 block 上的 LaTeX），不必再手工補。
但**自動版只覆蓋約六成**：公式標記從人工版的 149 處增加到 259 處，殘留亂碼卻也從
455 字元變成 860 字元——因為人工修補會把整段亂碼刪掉，自動版只換掉能對應到公式的片段。

影響範圍有限：`content` **不是前端閱讀頁的渲染來源**（GuidePage 走 `blocks`，64 章全都有
blocks，`content` 那條 markdown 分支永遠走不到）。實際讀 `content` 的是概念圖卡頁
（`VisualCardsPage.tsx`）與 `export_learning_articles.py` / `export_question_generation_data.py`。
要進一步收斂，方向是提高 `enrich_guide_blocks` 的公式附著率，而不是再手工 patch。

---

## 附錄：Coding style 與 commit convention

- Python：4-space、`snake_case`、短 module docstring、`Path` 不用 `os.path`、
  腳本自足、小 helper 優於深巢狀。
- 生成 JSON 以內容命名（`mock_exam1.json`、`subject2_questions.json`）。
- Commit：祈使句 + scope，如 `build: refresh mock exam JSON`、`parser: improve table extraction`。
