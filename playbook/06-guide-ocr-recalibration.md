<!-- 2026-11-02: 新增「2026-11-01 完整重建」節（stale guide_tree 重建、block-id 遷移、括號正規化、頁面影像審查結果）。備份：playbook/backups/06-guide-ocr-recalibration.md.bak-2026-11-02。 -->
<!-- 2026-08-30: 同步考題 current-state 14 卷／715 題與 sidecar 715 分母；已快取 150 維持。備份：backups/06-guide-ocr-recalibration.md.bak-2026-08-30-2。 -->
<!-- 2026-08-30（使用者授權）：同步三軌語意 gate、初級勘誤資源與嵌入練習邊界的最終收斂狀態；
     移除 2 筆未決勘誤、公式約六成與前端未使用階層樹等過時敘述。修改前備份：
     playbook/backups/06-guide-ocr-recalibration.md.bak-2026-08-30。 -->
<!-- 2026-08-07: 全檔收斂。任務主體（OCR 遷移／勘誤／引文對齊）已完成並合回 main，
     常駐規則已寫進 pipeline-reference.md（§1a 重跑順序、§3 練習題抽取陷阱、§9 教訓）。
     完整的 §1–§12 執行歷史留在 playbook/backups/06-guide-ocr-recalibration.md.bak-2026-08-07。 -->

# 06 — 學習指引 OCR 重新校正

**狀態：OCR 遷移完成；已審語意缺陷於 2026-08-30 收斂。** 本檔現在只留「現況 + 待接」；
執行過程、決策理由、踩過的坑寫在
`playbook/backups/06-guide-ocr-recalibration.md.bak-2026-08-07`（564 行），需要考古再開。

**要重跑 pipeline 的話不要看這裡** → `pipeline-reference.md` §1a（OCR 兩軌與完整順序）。

---

## 做完了什麼

716 頁學習指引（5 份指引 + 2 份勘誤表）改用 PaddleOCR-VL 重新解析，取代原本的
Gemini 2.5 Flash vision。成果 `data/{level}/guide_ocr/`（33 MB，committed，視為 SSOT）。

| 項目 | 結果 |
|---|---|
| OCR 成本 / 效能 | 716 頁、4.87 秒/頁、**$0.90**、零死鎖 |
| 公式 | KaTeX + MathJax 雙引擎全量渲染**零解析錯誤** |
| 簡體殘留 | 751 → 8 個（實際 4 處，經查證原稿本來就印簡體） |
| 階層樹 | `guideHierarchy.json`，1,207 節點、最深 6 層 |
| 出題粒度 | 章 → 小節／chunk；數量以當次 export log 為準，5 份輸出須能由 canonical exact rebuild |
| 官方勘誤 | 28 筆已處理，兩級 `errata_unresolved.json` 均為空陣列 |
| 引文對齊 | `guide_exercises` 179 題**全數**在引用頁逐字命中，0 退化 |
| Track A 語意 gate | 169/169 已審 inventory ＋ 3/3 publication overlays ＋ 3/3 structure contracts，remaining 0 |
| Track B 語意 gate | 78/78（71 OCR／抽取、2 來源數式、5 provenance），remaining 0 |
| 考題 production gate | catalog 14 份／715 題及逐頁 direct-view SHA/inventory 通過；2 題官方來源歧義以可見註記保留 |
| 勘誤資源 | 初級／中級勘誤皆由 resource catalog 發佈；初級 gallery 新增 8 個逐頁／表格資產 |
| Vision sidecar | fresh checkout 0/715；2026-08-30 本機 150/715，promotion 仍阻擋 |
| 發佈驗收 | `tests/run_all.py` 13 項；`audit_resources.py` 8 類（含三軌 `ocrSemantics`） |

驗證狀態：Track A/Track B 確定性 gate、兩級 `verify_data_alignment` 與 frontend build 均納入
`tests/run_all.py`；`apply_errata.py` 與完整 Track A export cycle 都有冪等驗證。

## 2026-08-30 收斂結果

- 初級 3-27 的 Type I 錯誤已用精確文字／route gate 修正，原始頁面影像仍保留。
- 中級 5-21 的 Recall 在 Track A 目標 block／reading snapshot 與 Track B canonical 都做精確校正，
  Precision 保持 `TP/(TP+FP)`。
- 後續盤點發現的中級 4-56 感知器加總項已套官方 `w_i x_i` 勘誤；另把來源 PDF 的
  `X_man`、Softmax 分母 `z_i` 以明示 publication overlay 校正。三筆都保留來源截圖。
- Track A 對 43 個已審公式頁做 exact same-page formula multiset／attachment 驗證；連同
  Type-I／Recall 共 45 筆 `formula_and_errata` inventory。這取代舊的「數 `$$`、約六成」估法。
- s1c2/s1c4/s2c3 的 deterministic publication hierarchy overlay 已整合進 staged exporter；標準
  exporter 單獨重跑位元冪等，3/3 structure contracts 會阻擋 content／headings／blocks／導覽搜尋漂移。
- 兩輪從 immutable `guide_ocr` 重建 Track B 的 canonical／sections SHA 完全一致；實跑時發現並
  修正插入型勘誤重複套用與 Recall／Precision 同頁誤命中的問題，現由內容遮罩及 heading-qualified
  context 精確 gate 鎖住。
- `guide_exercises` 會在結構化參考書目 appendix 前停止，寫檔前拒絕書目污染、題目 ID 漂移或
  既有 card 遺失；現行契約為初級 69＋中級 110＝179 題、179 cards。
- 169/169 是**已審 inventory closure**，不是對未審頁或未來新增 PDF 的全域正確性證明；
  新來源仍須逐頁看影像，並把新缺陷加入可回歸的 registry。

## 2026-11-01 完整重建（guide_tree 過期）

**為什麼**：發佈中的 guideContent 來自 5/25 建的 `guide_tree`，早於 OCR 合併進 page_extract；使用者選擇
完整、照 playbook 的重建（未呼叫付費 API；gitignored 輸入／輸出全數先備份並以 7,701 筆 SHA 驗證）。

**做了什麼**
- 整條鏈依 `pipeline-reference.md` §1a 重跑；s1c2 假說檢定表 overlay 改支援新來源結構，OCR 表不再被文字層表頭
  覆蓋，表格上下緣被吃掉的正文行救回 18 行。
- `merge_guide_ocr.py`：儲存格換行轉換跳過 `$…$`，修好 中級 guide2 4 格（8 個區塊）的 `\ne`／`\neq`。
- 發佈層新增四項（細節：`deterministic-publication-overlays.md`「2026-11-01 重建 finalize」）：簽章視窗鏡像到
  PDF 章節路由＋`CONTINUATION_MERGES`、s2c3 標題溢字歸還、`TABLE_CELL_REPAIRS`、**中文語境半形括號→全形**
  （使用者 11/01 決定；含 `$…$` 的括號依外側／內側中文判斷，回歸測試在 `test_pipeline_output_safety.py`）。
- **Block id 遷移**：`build_guide_block_id_migrations.py --old-ref 153f13d` 產生 `data/guide_block_id_migrations.json`；
  人工逐筆裁決 132 筆無法以同文字遷移的詳解引用（84 未決、47 自動候選、1 既有覆寫），全部寫進
  `data/guide_citation_overrides.json`（`method: manual`，附審查理由與審查時的區塊 ID），**0 筆移除**。

**數字**
| 項目 | 結果 |
|---|---|
| 詳解引用（6,512 個舊 block 參照） | 同 ID 同文字 5,659；ID 還在但文字已不同 852；ID 消失 1 → 全部經對照表／人工裁決遷移 |
| 遷移後 | 6,628 個參照（多塊對應），全部指向現存區塊；815 題無一題變成零引用 |
| 跨頁斷段（句中斷開、下一塊在次頁） | HEAD 56 → 重建初版 90 → finalize 54 |
| Track A | 169/169＋3/3＋3/3，remaining 0；TA-106/107/108 依影像重新簽章（`reviewedOn` 2026-11-01） |
| 練習題／引文對齊 | 179 題／179 卡逐位元不變；69＋110 題引用頁逐字命中，0 退化 |
| 圖片標題 | 62 筆 headingBlockId 經對照表改寫 |

**頁面影像審查**（150 dpi 逐頁）：初級 38 項（核准 18、退回 20）、中級 g1 40 項、g2＋g3 46 項。新的退化
（`\ne`、H_o、en dash／＋、BERT/GPT 全形括號、分佈、L23 空格、s2c3 少五字、PDF 章節路由跨頁斷段、含 `$` 的括號）
都已在本輪修正並重看影像。

**刻意留下、待決**
- TA-048 標題「1. 人工智慧技術的多樣化應用」與影像 3-1「1. 人工智慧的應用領域」不符（HEAD 即如此、簽章鎖定），待使用者決定。
- mid-s3c9 三個學習錨點（block-70/148/167 → 71/149/168，文字逐字相同）：學習平台規則要求人工核准定位＋非作者重審，
  `validate_learning_content` 與 3 項學習測試因此 blocked。
- 既有（HEAD 就有）未修：s1pdf-c3 章末習題題目邊界、「AI AI」標題、block-297 大答案區塊、s1c3 缺「3. 機器學習核心過程」、
  s2pdf-c3 block-174 超大答案區塊、s1c3／s1c4 同頁斷詞、mid-s1c2「雙重標註 」」空白、「其流程包括：」獨立成段、PDPA 條列結構。

## 待接工作（依價值排序）

1. **決定要不要用 `--by-section` 重出題庫**。基礎設施好了但一次都沒跑過——
   到目前為止提升的只有前處理，題庫仍是舊講義文字生出來的。
   建議先單章試跑（挑漂移最大的 `mid-s2c3`，相似度 0.739）驗證品質再決定全量。
   需要 `ANTHROPIC_API_KEY`，量不小（初級科目1 光 `--count 3` 就 111 題）。
2. **新來源的語意抽查制度**：現行 gate 鎖住已審 registry；新增或換版 PDF 時仍要抽查／核對
   公式、表格、跨頁順序與來源圖，再把確認缺陷轉成 exact signature。
3. **四個備份目錄可清**——但 `page_extract_before_ocr_merge/`（193 MB）**先別刪**，
   它是 `verify_question_guide_alignment.py` 的舊版基線，刪了就無法區分
   「本輪造成的退化」與「本來就這樣」。

## 這個任務留給制度的東西（已寫進 pipeline playbook）

- §1a — OCR 兩軌與**完整重跑順序**（勘誤是疊加層、轉接層重跑會沖掉）。
- §3 — `export_guide_embedded_exercises.py` 的邊界陷阱（頁眉黏進選項、解析吃到下一章／參考
  書目 appendix、無條件頁尾收束會掉題）及寫檔前 fail-closed 契約。
- §9 — 中文 PDF 文字比對的教訓（兩邊都要 NFKC、題幹與選項分開比、題目常跨頁）。
- `deterministic-publication-overlays.md` 修正 4 — 勘誤的全有或全無策略、兩軌格式不同要各寫一筆、安全閥。
