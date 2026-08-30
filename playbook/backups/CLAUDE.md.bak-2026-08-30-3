<!-- 2026-08-30（使用者授權）：加入 OCR 語意驗收界線與三軌 release gate，完整驗收
     更新為 13 項。修改前備份：playbook/backups/CLAUDE.md.bak-2026-08-30-2。 -->
<!-- 2026-08-29（使用者授權）：同步架構硬化後現況——10 項驗收、Guide staged partial
     export 安全性與 production 腳本 repo-relative。修改前備份：
     playbook/backups/CLAUDE.md.bak-2026-08-29-2。 -->
# CLAUDE.md

iPAS AI 應用規劃師（初級＋中級）考試教材內容生成工作區。來源 PDF 在 `data/{level}/pdfs/`，
pipeline 抽取為結構化 JSON，前端（Vite + React 19 + TS + Tailwind v4）build 後由 GitHub Pages 部署。

**核心目標**：根據解析完成的教材與官方樣張/歷屆題目，針對特定章節綜合出高品質模擬試題。
PDF→MD 解析品質直接決定出題品質，前處理正確性優先於一切。

**OCR 驗收界線**：資料對齊、頁數與 cache 完整率只證明結構／引用齊全；
`audit_resources.py` 的 `ocrSemantics` 會阻擋已審 inventory／correction registry 的退化，但**不能替新來源或
未審頁面證明 OCR 語意正確**。發佈新 PDF 或把 sidecar 升為 production 前，仍須對頁面影像
核對公式、表格、跨頁順序與圖像語意，並分驗 Track A、Track B 及考題 production JSON。

## 路由表（先讀這裡，需要什麼載什麼，不要整包讀）

| 要做的事 | 讀這份 |
|---|---|
| 跑任何 pipeline、查腳本用途、輸出檔案、驗證清單、**s1c2/s1c4/s2c3 publication overlay** | `playbook/pipeline-reference.md`（有目錄，用 Grep 跳小節） |
| **動講義文字前**（OCR／勘誤／清洗）：重跑順序不可調換 | `playbook/pipeline-reference.md` §1a |
| 派 subagent、選 model/effort、回報格式、驗收方式 | `playbook/01-dispatch.md` |
| 拿不準：要不要升級模型／算不算完成／該不該問使用者／方向對不對 | `playbook/02-judgment.md` |
| 委派任務的 prompt 模板（搜尋/實作/重構/研究/審查） | `playbook/03-templates.md` |
| 想修改 CLAUDE.md 或 playbook 本身 | `playbook/04-maintenance.md`（先讀再改） |
| **跑測試／驗收**：13 項驗收、端對端測試怎麼寫 | `tests/README.md` |
| 本 harness 的已知弱點與環境備忘 | `playbook/00-diagnosis.md`、`playbook/05-letter.md` |
| 學習指引 OCR 校正的現況與待接工作 | `playbook/06-guide-ocr-recalibration.md`（2026-08-30：A 169＋3＋3／B 78／考題 14 份 709 題已收斂） |
| **小節粒度出題（進行中）**：codex CLI 出題、答案交叉驗證 | `playbook/07-question-generation.md` |
| **考古題熱度／概念標籤／心智圖**：`/mindmap`、受控詞彙表草稿 | `playbook/08-topic-labeling.md` |

`AGENTS.md` 是給 Codex CLI 的，內容較舊；與 playbook 衝突時以 playbook 為準。

## 不變量（違反任一條 = 事故）

1. **SSOT**：章節定義只存在於 `build_manifest.py` 的 `GUIDES_BY_LEVEL` →
   `data/{level}/toc_manifest.json`。任何腳本或前端都不得複製章節定義、不得硬編章節陣列。
2. **商品化文案**：前端使用者可見文案不得透露教材/題目由 AI 生成。內部變數/路由 key
   （`summary.ai` 等）可保留。既定對外命名：「章節練習/章節模擬練習題」（≠AI 模擬）、
   「學習指引練習」（學習指引 PDF 內嵌題抽取）、「概念圖卡」（=AI 資訊圖，頁面 `/visuals`）。
   「AI 應用規劃師」（考試名）與「生成式 AI」（考綱主題）屬正當用語。
   <!-- 2026-08-09（使用者指示）：移除「精選 100 題」。兩份生成題庫合併為每科一份
        熱度配額題庫，`codex100` 練習集與該命名已從前端、resourceSummary 全數移除。 -->
3. **破壞性腳本**：`export_guide_outline_data.py` 會 staging content／outlines／exact source assets，
   內建 s1c2/s1c4/s2c3 deterministic publication overlay，驗 schema 與 Track A 169＋3＋3 後才原子替換；
   失敗 rollback，單等級保留其他等級。常規完整重跑必帶 `--all-levels --use-guide-tree`（見 §10）。
   任何含 rmtree/`--force` 的腳本，先確認目標目錄是否 gitignored（gitignored = 刪了救不回，
   vision 快取重建要花 API 錢）。
4. **Build artifacts**：`data/{level}/questions/*.json`、`data/{level}/guide/*.json`、`docs/`
   視為產物；只有刻意策展時才手動編輯並在 commit 說明。`docs/` gitignored，Pages 由
   GitHub Actions 建，push main 即部署。
5. **改動後驗證**：動了 `frontend/src/` 或資料 JSON → `cd frontend && npm run build`
   必須零 TS 錯誤；動了資料 pipeline → `python3 scripts/verify_data_alignment.py --level {level}`。
   這兩條局部驗證任何情況都不可省。**正式發佈前一律跑** `uv run python tests/run_all.py`；
   動到執行時行為或 OCR 三軌也要跑——13 項約 4–5 分鐘，需要 Playwright Chromium。
   <!-- 2026-08-29（使用者指示 update）：原文是「沒有其他自動測試，這兩條不可省」。
        tests/ 已從無到有。促成原因：把考試作答從陣列索引改成 question id 時，
        build 與資料對齊**都會過**，但驗不到「勾選有沒有對到正確的題」——
        使用者可能答 A 卻記到別題。細節見 tests/README.md。 -->

## 常用指令

```bash
uv sync && (cd frontend && npm install)                  # 初始化（clone 後）
cd frontend && npm run dev -- --host                     # dev server（WSL 需 --host）
uv run python3 scripts/build_web.py                      # production build → docs/
python3 scripts/verify_data_alignment.py --level 初級    # 資料一致性檢查
uv run python tests/run_all.py                          # 13 項驗收（含端對端，需 Playwright）
```

支援 `--level` 的資料 pipeline **預設值不一致**：多數預設 `初級`，中級專屬 pipeline
（`supplement_guide_from_audit`、`generate_colab_notebooks`、`run_codex_exam_reference_answers`、
`export_exam_reference_answers`、`export_colab_metadata`、`export_question_generation_data`、
`llm_review_guide_headings`）預設 `中級`——有此參數時一律顯式帶值；跨級 gate 依 playbook
固定使用 `--all-levels`、`--level all` 或全域模式。
完整步驟見 `playbook/pipeline-reference.md`。
API 金鑰：`GEMINI_API_KEY`（vision）、`ANTHROPIC_API_KEY`（出題/審核）；
`multi_ai_pipeline.py` 和 `codex_*` 需已認證的 `gemini`/`codex`/`claude` CLI。

## 環境備忘

- production Python 腳本以 `Path(__file__).resolve()` 推導 repo root；不得新增機器專屬絕對路徑，
  `tests/test_repo_portability.py` 會掃描此退化與 subprocess cwd。
- WSL2；大型資料 JSON（`data/`、`frontend/src/generated/` 下常見 100KB–1MB）
  **>50KB 禁止整檔 Read**，用 `jq`/`grep` 切片或派 subagent（門檻與規則見 `playbook/01-dispatch.md` §0）。
- 前端 alias：`@data` → `data/初級/`、`@data-mid` → `data/中級/`。前端 GuidePage 讀的是
  `frontend/src/generated/guideContent/`，**不是** `data/*/guide/*.json`（雙軌，改一邊不影響另一邊）。
- **產圖依賴另一個 repo 的容器**：`~/projects/codex-imggen`（`docker compose up -d`，
  `localhost:8090`）。一律經 `scripts/imggen_client.py`，不要直接 `codex exec` 產圖
  （產物檔名慣例隨 codex-cli 版本變，會靜默壞掉）。詳見 `playbook/pipeline-reference.md`。

## Coding style / Commit

Python：4-space、snake_case、`Path` 不用 `os.path`、腳本自足。
Commit：祈使句 + scope（`exam: fix mid_1151_s2 Q40 option D text bleed`）。
測試放 `tests/test_*.py`，一次跑完用 `uv run python tests/run_all.py`。
