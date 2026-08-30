<!-- 2026-08-31: 內容指紋升為來源與實際圖檔 bytes，補 targeted-rerun／完整發布防線。 -->
<!-- 2026-08-30: 從 pipeline-reference.md §7 忠實搬入逐支腳本目錄；補考題內容指紋、reference-answer provenance 與 direct-view gate 契約。 -->
# Pipeline 腳本目錄（原 §7 companion）

> 本檔是逐支腳本用途、輸入輸出與陷阱的唯一權威目錄。執行順序仍以
> `playbook/pipeline-reference.md` 對應小節為準；deterministic publication overlays 詳節見
> `playbook/deterministic-publication-overlays.md`。新增或改變腳本行為時更新本檔，不要把完整目錄複製回主檔。


**SSOT / 抽取**
- `build_manifest.py` — 章節定義 SSOT 生成器，唯一硬編 `GUIDES_BY_LEVEL` 之處；開 PDF 算 `page_range`（0-based）寫入 `toc_manifest.json`。
- `resource_catalog.py` — 驗證／查詢 committed `data/resource_catalog.json`；等級、考卷、route、題庫檔、預期題數、PDF、legacy asset key 的唯一共用入口。
- `extract_pdfs.py` — pdfplumber 為主、PyMuPDF fallback 的整檔抽取 → `extracted/`；guide PDF 來自 manifest，考題／參考資源 PDF 來自 resource catalog。
- `extract_pdf_pages_structured.py` — 頁面忠實抽取：每頁文字 + text/image/table bbox + 裁切 PNG → `page_extract/{key}/assets/`。
- `clean_pdf_page_text.py` — 清 header/footer/頁碼/表格標籤、標記跨頁接續、重建 per-PDF outline → `page_clean/{key}/`。
- `ocr_extract.py` — Track B 轉接層：PaddleOCR-VL 逐頁 md → `pages_cache/{key}/page_NNN.json`；
  page type 由規則＋5 筆 committed override 決定，舊 Gemini backup 僅診斷（見 §1a）。
- `merge_guide_ocr.py` — Track A 轉接層：OCR 內容合併進 `page_extract/`，首次執行會備份原檔（見 §1a）。
- `guide_publication_overlays.py` — s1c2/s1c4/s2c3 deterministic structure transform SSOT；exporter 在 staging 套用，legacy `apply_manual_guide_fixes.py` 共用同一映射。
- `build_errata.py` / `apply_errata.py` — 勘誤表 OCR → `errata_corrections.json`；套用到兩軌，冪等（見 `deterministic-publication-overlays.md`「修正 4」）。
- `apply_track_b_ocr_fixes.py` — Track B 的 78 筆 reviewed correction overlay；`--check` 以 committed canonical SHA 為必要層，完整本機 cache 存在時再做重建深比對。
- `build_codex_section_prompts.py` — 小節粒度出題 prompt。⚠️ `--heat-total` 的配額**必須對整科算完再篩章節**；`--batch-target`（預設 9）把連續區塊打包，因為每次 codex 呼叫固定開銷約 108 秒與題數無關（不打包時平均每次只出 1.6 題）；`--run-dir` 兩種寫法都吃。
- `export_guide_mindmap.py` — guideNav ＋ 考古題標註 → `guideMindmap/{subjectId}.json`（前端 `/mindmap` 章節熱度圖）。只讀 committed 產物、無 API 花費、可隨時重跑。⚠️ 各章題數**不可相加**（一題常引用多章：905 vs 實際 450 題）。
- `imggen_client.py` — **產圖一律走這裡**（`codex-imggen` HTTP 服務，`~/projects/codex-imggen`，`docker compose up -d`，`http://localhost:8090`）。`generate()` 文生圖、`edit()` 圖生圖、`require_service()` 開跑前健康檢查。⚠️ **不要再直接 `codex exec` 產圖**：那會把 session rollout 與原始 PNG 堆在 host `~/.codex/`、在 repo 根目錄亂丟 png，而且產物檔名慣例隨 codex-cli 版本變（2026-08-08 就因此讓 `generate_images.py` 靜默壞掉）。服務直接回傳圖片 bytes。
- `verify_generated_images.py` — 用 `codex exec --image` 讀回概念圖卡上的中文並逐條判定（garbled／nonword／truncated／terminology／wrong）→ `data/audit/image_text_review.json`。`--sample N`／`--all`／`--ids`／`--report`；已驗過的會跳過，`--force` 重驗。官方用詞清單從 `toc_manifest.json`（SSOT）＋ `topics.json` 組出來，不另建。
- `regenerate_flagged_images.py` — 重生 `verdict=fail` 的圖卡直到通過。⚠️ 三條保護：把上一輪的問題寫進下一輪 prompt（回饋比重試次數有用）、**所有嘗試都沒過就還原備份**（`build/image_backup/`，不用更差的圖換掉現有的）、`error` 不算 pass。
- `generate_images.py` — 產圖後**自動跑文字檢查**，不過就帶著問題回饋重試（`--no-verify` 可跳過，不建議）。原本的重試只處理 timeout 與抓不到 session id。⚠️ 產物路徑是 `~/.codex/generated_images/<session>/`，**檔名慣例會隨 codex-cli 版本變**（舊 `ig_*.png`、0.146 起 `exec-<uuid>.png`），腳本已改成取目錄裡最新的 PNG；若又出現「找不到產圖 PNG」先去看那個目錄。
- `export_generated_questions.py` — 把小節管線產出的題目併進 `data/{level}/questions/subject{N}_questions.json`（**2026-08-09 補上，原本完全沒有這一步**）。寫入前重驗每一批、檢查 id 與題幹唯一、**要求每批有通過的 `.verify.json`**，任一項不過整批拒寫。⚠️ 預設要求整科完整（只匯出一章會抹掉其他章），要只替換某幾章得加 `--replace-chapters`。
- `verify_batch_answers.py` — 單批答案交叉驗證，供 runner（`--verify-answers`）與 export 當閘門。結果存輸出檔旁 `<batch>.verify.json`，可續跑可稽核；**驗不到不算過**；圖片題跳過。判準看 `wrong_consensus`（不同意者都選同一個錯答才是真的錯）。金鑰 `LLMSHARE_API_KEY` 放 `.env`（gitignored）。
- `sample_card_review.py` — 確定性分層抽樣題目 `card` 欄位 → `data/audit/card_sample_review.json`；`--tally` 讀回判定算錯誤率。同 `--size`／`--seed` 重跑會拿到同一批題，才能改完驗同一批。
- `fix_card_defects.py` — 修 `card.frequency` 值域外（依所在章熱度分段給值）與解析尾端黏上的「參考書目」附件。冪等，`--dry-run` 先看。
- `export_topic_heat.py` — 概念標註 ＋ 詞彙表 ＋ 考古題標註 → `topicHeat.json`（前端 `/mindmap` 概念軸）。只讀 committed 產物、無 API 花費、可隨時重跑、輸出確定性（跨 `PYTHONHASHSEED` 位元相同）。⚠️ 採計只算 `verdict=正確`；「散落章數」用 `guideChapterCount`，**不是** `chapterCount`（後者把大綱章與指引章各記一次，虛胖 32%）。細節見 `08-topic-labeling.md` §7-3。
- `export_concept_graph.py` — 概念關聯圖：把詞彙表、兩份標註、熱度、名詞解釋、題幹併成 `conceptGraph.json`（前端 `/concepts`）。只讀 committed 產物、無 API 花費、可隨時重跑。⚠️ `questionCount` 的 official／practice 不可相加當熱度。見 §5b。
- `build_glossary.py` — 名詞解釋生成（詞表由 `topicHeat.json` 熱度決定，來源＝講義原文段落＋詳解片段）→ `frontend/src/generated/{primary,middle}Glossary.json`。`--dry-run` 只看選詞與來源覆蓋、不花錢；`--apply` 才寫前端；既有詞條預設保留不覆蓋（`--regenerate` 才重寫）。生成模型不可與 `verify_glossary_terms.py` 的審核名單重疊。見 §5a。
- `verify_glossary_terms.py` — 釋義閘門：三模型盲審每一條，`wrong` 票 ≥2 就 flagged。`--self-test` 拿 4 條故意寫錯的＋4 條乾淨孿生驗閘門本身（要 4/4 抓到、0 誤報）；`--term` 只重驗改過的那條。金鑰 `LLMSHARE_API_KEY`（`.env`，gitignored）。
- `export_guide_hierarchy.py` — 接成完整階層樹，並產導覽用的兩個衍生檔 → `guideHierarchy.json`、`guideNav.json`、`guideSearchIndex.json`（見 §1b）。
- `pdf_vision_extract.py` — 每頁 PNG（2x）送 Gemini Vision → `pages_cache/{key}/page_NNN.json`（{type, headings, markdown, usage}）；完成後自動生成 `page_index.json`。重跑只補 missing/failed。
- `gemini_exam_vision_extract.py` — 考題 Vision OCR 稽核 sidecar → `exam_pages_cache/`；`parse_exams_v2.py` 不消費，不能當 production 題庫來源。

**組裝 / 解析**
- `parse_guides.py` — pages_cache → canonical Track B `guide/subject{N}_guide.json`；cache 不合格即停止，legacy regex 必須明確加 `--allow-regex-fallback`，輸出帶來源標記。
- `export_guide_sections.py` — canonical Track B → committed `guide_sections/subject{N}.json`；記錄來源 SHA 與切片參數，可由現行 canonical exact rebuild。兩個 section 出題入口都會先拒絕 stale payload。
- `parse_exams_v2.py` — 依 catalog 從 extracted JSON 解析題目／答案 → 指定 `questions/*.json`；頁面圖片才套 `legacyAssetKey`。
- `build_guide_tree.py` — 從 page_clean 建驗證過的章節樹（heading 深度、sibling 連續性、頁範圍、內嵌習題檢查）→ `guide_tree/{key}/tree.json, blocks.json, warnings.json`（gitignored）。
- `build_pdf_outline.py` — 從 page_extract 建可審閱的 PDF 階層 outline（有 Vision headings 用之，否則 regex）→ `outline/{key}_outline.{json,md}`。

**審核**
- `audit_chapters.py` — Claude Haiku 逐章審 subtopics 覆蓋 → `subject{N}_audit_report.json`。
- `pdf_vision_audit.py` — 第二次 Vision pass（AUDIT_PROMPT，結構化 blocks）→ `audit_cache/`。用途是審核與增補，不是內容替換。
- `codex_audit_compare.py` — Codex CLI 比對 audit_cache 標題結構 vs guide JSON → `audit_compare/`。
- `supplement_guide_from_audit.py` — 用 audit_cache（或 pages_cache）重組 Markdown 補 fail 章節，原檔備 `*.bak`。
- `codex_review_pdf_pages.py` — Codex CLI（read-only sandbox）逐頁審 cleaned pages → `codex_page_review/{key}/`。
- `verify_data_alignment.py` — manifest vs build_manifest vs PDF 頁標 vs guide/questions 一致性檢查。
- `track_a_ocr_repairs.py` — Track A 169 筆 review/inventory registry、3 筆 publication overlay 與 3 筆 structure contract＋唯讀 publication gate；真正套用由 `export_guide_outline_data.py` 內建完成，並在 commit staged outputs 前再跑同一 gate。預期簽章在 `track_a_ocr_expected_signatures.json`。
- `verify_exam_ocr_repairs.py` — 依 catalog 鎖定 14 份／715 題 production 題庫、人工覆蓋與來源歧義註記，並串入逐頁 direct-view gate。
- `verify_exam_visual_reviews.py` — 驗 `data/exam_visual_review/*.json` 的 14 卷 PDF/question SHA、全頁與完整 qid inventory；缺卷、stale SHA、非 pass 或 unresolved issue 一律失敗。
- `reconcile_exam_vision_sidecar.py` — 唯讀建立 raw Vision sidecar 的 verified overlay；只有 715/715 且零 mismatch 才允許 promotion。
- `verify_question_guide_alignment.py` — 唯讀。量題庫與講義的引文對齊：章節引用完整性、
  `guide_exercises` 逐字引文（對 page_clean，含跨頁串接）、章節正文新舊漂移。
  與 `page_extract_before_ocr_merge/` 舊版比，能區分「本輪造成的退化」與「舊版就這樣」。
  `--level` / `--json out.json`。跑一次兩級約 20–40 分鐘。
- `verify_question_answers.py` — 多模型盲答交叉驗證答案（出題產物／官方考卷／已上線題庫）→ `verification/`；cache 綁題目／來源頁與實際有序圖片 path＋SHA-256＋byte length，legacy、stale、缺圖或執行中換圖一律失效（見 §3 與 `07-question-generation.md` §4a）。
- `audit_resources.py` — **發佈前確定性審核閘門**，`build_web.py` 會先跑它，FAIL 就中止 build；例外寫 `data/audit_allowlist.json`（要附理由）。
- `review_committed_notebooks.py` — 複查 committed notebook（累積執行 + 語意）→ `data/notebook_review/`（見 §5）。
- `llm_review_guide_headings.py`、`question_dedupe.py`、`annotate_exam_code_images.py` — 輔助（先讀 docstring）。

**前端匯出（`frontend/src/generated/` 是 committed 靜態輸入）**
- `export_guide_outline_data.py` — page_clean/guide_tree → `guideOutlines.json` + `guideContent/{key}/`；staging 驗證後一起替換，失敗 rollback，partial 保留其他等級。
- `export_guide_embedded_exercises.py` — 抽 guide PDF 內嵌官方習題 → `questions/subject{N}_guide_exercises.json`（與 AI 生成題分開）；在結構化 appendix 前停止，寫檔前拒絕 bibliography bleed、ID 漂移與 card 遺失，production 契約為 179 題／179 cards。
- `export_question_generation_data.py` — Track A seed → `subject{N}_reading_guide.json`，初始化／保留 `subject{N}_questions.json`；不寫 canonical Track B。
- `export_pdf_image_gallery.py` — page_extract 裁圖 → `frontend/public/pdf-assets/{level}/` +
  `frontend/src/generated/pdfGallery.json`（`#/images` 檢視器）；partial export 會合併未指定等級。
  2026-08-29 起不再寫 `public/.../gallery.json`——那份三個 level 合計 589 KB，從來沒有消費者。
- `export_resource_summary.py` — 章節/題數/覆蓋統計 + `visuals` 概念圖卡計數 → `resourceSummary.json`（首頁統計用；題目 JSON 得以 lazy load）。
- `export_exam_reference_answers.py` — 以 v2 generation-input SHA-256 provenance 對 canonical qid，驗 overlay 指紋並要求 published/production inventory 完全相等；不得改回無條件 legacy ID offset（細節見 `07-question-generation.md` §4a）。
- `export_colab_metadata.py`、`export_guide_images_data.py`、`export_guide_image_units.py`、`export_learning_articles.py`、`export_guide_exam_annotations.py` — 各自把後端產物轉前端 JSON；改了上游資料記得重跑對應那支。
- ~~`render_guide_page_images.py`~~ — **已退場（2026-08-29）**。產物 `frontend/public/guide-pages/`（89 檔 13 MB）
  經窮舉比對確認前端從未引用（`parse_guides.py:369-373` 註解已寫明），已從版控刪除。
  前端讀的是 `guideContent` 與 `pdfGallery`，都指向 `pdf-assets/`。不要重跑這支。

**生成（花錢/花時間）**
- `generate_questions.py` — Claude API 出題（`--subject N`）或補 card 欄位（`--enrich`）。`--dry-run` 先看 prompt。
- `multi_ai_pipeline.py` — 三 CLI（gemini/codex/claude）subprocess pipeline，含答題驗證與 flagged。
- `generate_colab_notebooks.py` — 三階段 Colab notebook pipeline（見 §5）。
- `generate_images.py` — Codex 圖像 API 逐 unit 生成資訊圖 → WebP → `frontend/public/images/`。
- `run_codex_exam_reference_answers.py` — reference-answer producer；輸出保存題目、情境、圖片與來源頁 v2 provenance，targeted rerun 先擋重編號 carrier 覆寫；canonical qid 契約見 §4／`07-question-generation.md` §4a。
- `build_codex_*_prompts.py` / `run_codex_*_generation.py` / `merge_codex_mock_exam_outputs.py` / `validate_codex_*_output.py` / `export_codex_mock_exam_questions.py` — Codex 批次出題家族：build prompts → run → validate → merge → export。

**Build / 發佈**：`build_web.py` 先 audit 再 Vite build → `docs/`；`publish_assets.py` 可選上傳 R2（預設 copy，`--prune` 才刪除）；`verify_r2_assets.py` 全量 HEAD，正式切換不可用 `--sample`。

---

## §1b 學習指引完整階層樹

```bash
python3 scripts/export_guide_hierarchy.py                    # → guideHierarchy.json + guideNav.json + guideSearchIndex.json
python3 scripts/export_guide_hierarchy.py --print-tree s1    # 印出來目視檢查（s1/s2/mid-s1/mid-s2/mid-s3）
```

階層原本斷成兩段：`guideOutlines.json` 只到「節」（64 節點），節以下的標題散在各章的
`blocks[]` 與 `headings[]`，沒有父子關係。本腳本接成一棵樹（**1,207 節點**：23 章 +
41 節 + 1,143 標題，最深 6 層），並用 `guide_ocr` 補回 Track A 漏抓的 `N.` 層（72 個）。
只讀既有產物、可隨時重跑；跑在 `export_guide_outline_data.py` 之後。

三個實作重點（改動前先讀，都是踩過的坑）：
- **章不能與其下的節重複收標題**。章的 `pageRange` 涵蓋所有節、content 也是節的聯集，
  有子節點的章只保留「子節點頁範圍沒涵蓋到」的標題。
- **`blocks` 與 `headings[]` 互補，缺一不可**。初級 s1c1 的 blocks 只到 A. 層（缺 a. 層），
  中級 mid-s2c8 的 `headings[]` 整個是空的。以項目多的那邊當主幹，另一邊補頁碼。
- **補回的標題不能只按頁碼插入**。同一頁常有多個標題，只看頁碼會把「3. 資料處理與分析」
  插到同頁但實際在它前面的「E. 專家系統」之前，讓 E. 變成它的子項。同頁內要用
  guide_ocr 該頁的標題順序決定先後。

節以下的節點是既有章節頁的錨點（`href = {route}#{anchor}`），**前端路由完全不用動**。

<!-- 2026-08-07: 新增兩個衍生檔與前端消費現況。 -->
同一支腳本另外產兩個**衍生檔**，目的是不讓全站為了兩層結構背上整棵樹：

| 檔案 | 內容 | 大小 | 誰在用 |
|---|---|---|---|
| `guideHierarchy.json` | 全部 1,207 節點 | 449 KB | GuidePage 的「本節階層」（靜態 import，進 GuidePage chunk） |
| `guideNav.json` | 只有章/節 64 節點 | 13 KB | 側欄章節樹、GuidePage 麵包屑（靜態 import，進首頁 chunk） |
| `guideSearchIndex.json` | 全部節點，欄位縮寫 | 195 KB | 搜尋對話框、`/outline`（**動態 import**，開啟時才載） |

⚠️ **`a`（anchor）只在該 anchor 真的存在於章節頁的 `blocks[]` 時才輸出**。
階層樹的標題有兩個來源，從 `headings[]` 來的那批只有標題文字、anchor 是 slug 推出來的，
頁面上沒有對應 DOM——帶著 `#anchor` 連過去只會停在頁頂（實測佔全部標題約兩成）。
這類節點標 `x:1`，消費端要退回連到章節頁本身或顯示為不可跳轉。
目前 1,143 個標題裡可跳轉 849、不可跳轉 294（含 OCR 補回的 72 個）。

前端吃 `#anchor` 的是 GuidePage 的 `location.hash` effect。**HashRouter 下網址形如
`#/guide/s1/s1c1#anchor`**（react-router 把第二個 `#` 之後當 `location.hash`）；內容非同步
載入，要等 `content` 到位才捲得到，所以 effect 依賴 `[location.hash, content]`。

⚠️ **捲一次不夠**。KaTeX 與圖片載入後才撐開高度，早算的位置會失準——實測目標被推到
畫面外一萬多 px，重試到 2.5 秒仍差 3,463 px。現行做法：每 250 ms 檢查 `scrollHeight`，
變動就重捲，連續 4 次不變或超過 12 秒才停，使用者一動就停手。不要退回單次捲動。

`a`（anchor）採三段式定位：自身可跳（849）→ 退到最近有區塊的上層標題並標 `x:1`
（202，前端顯示「概略位置」）→ 都沒有就連章節頁（92）。**最深的 `a.`/`b.` 層幾乎都是
第二類**，而那正是搜尋最常命中的一層——早期版本把這些做成不可點，搜「梯度下降」
兩筆結果全是死的。

---

## §5a 名詞解釋（glossary）pipeline

```bash
# 選詞＋抓來源，不打 API：看每個詞條有多少講義原文／詳解可用
python3 scripts/build_glossary.py --level 初級 --dry-run
# 生成（預設 --min-count 3：只收在官方考卷出現 ≥3 題的概念）
python3 scripts/build_glossary.py --level 初級 [--min-count 3] [--limit N] [--model glm-5.2]
# → data/{level}/pipeline/glossary/generated.json（gitignored）
python3 scripts/build_glossary.py --level 初級 --apply
# → frontend/src/generated/{primary,middle}Glossary.json（committed）

# 閘門：三模型盲審每一條釋義（必跑）
python3 scripts/verify_glossary_terms.py --glossary frontend/src/generated/primaryGlossary.json \
    --out-dir data/audit/glossary_review/初級 \
    --verifiers llm:deepseek-v4-pro,llm:kimi-k2.7-code,llm:qwen3.5:397b
python3 scripts/verify_glossary_terms.py --term 資料標準化 ...   # 修完只重驗那一條
python3 scripts/verify_glossary_terms.py --self-test              # 閘門自身的自測，見下
```

規則：

- **選詞不靠人腦**：詞表由 `topicHeat.json` 的 `count` 決定，等於「這個概念實際被考幾題」。
  科目歸屬取該概念在此等級各科的題數最大者；科目 id／名稱一律讀 `toc_manifest.json`（不變量 1）。
- **取材以講義原文為主、詳解為輔**：只把「有提到這個概念的段落」餵進 prompt，不是整章。
  比對詞用 `topics.json` 的 aliases——只比對正式名稱時，初級有 45／108 個詞完全抓不到講義段落，
  加上別名後降到 30。抓不到的詞退回用詳解，`sources` 欄位記得住是哪一種。
- **prompt 不可寫成「只根據片段」**：這樣會把某一題的情境當成定義（實測：代理式AI 被定義成
  「在解決方案圖譜的候選路徑中探索」）。正確寫法是「片段決定用詞與著重點，釋義必須是通行定義」。
- **生成模型不可出現在審核名單**：生成用 `glm-5.2`，審核名單就換成 deepseek／kimi／qwen。
- **改完詞條要重驗**：`--term` 只重跑那一條，不必重掃整份。

閘門自測（上線前必做，`--self-test`）：腳本內建 4 條故意寫錯的釋義（精確率↔召回率、
中位數寫成平均數、過擬合寫成欠擬合、監督式寫成非監督）＋4 條原樣孿生對照，
要求 4/4 抓到且 0 誤報才算閘門可用。

> 2026-08-09 教訓：第一次自測是 0/4，我差點寫成「模型判不出概念互換」。真因是
> `results` dict 用 `(subject, index)` 當 key，汙染版與乾淨孿生同 key，後寫的把前面蓋掉。
> **模型答錯之前，先確認自己的迴圈沒把答案丟掉。**

`audit_resources.py` 的 glossary 檢查涵蓋兩份檔案：空釋義／釋義長度 20–200 字外 → FAIL，
沒有案例說明／同科目內重複 → WARN。**內容對不對不在 audit 判**，那是 verify 腳本的事。
