<!-- 2026-08-30: 從 pipeline-reference.md §10 忠實搬入 deterministic publication overlay 詳節；主檔保留 fail-closed 摘要與路由。 -->
# Deterministic Publication Overlays（原 §10 companion）

> 本檔是 s1c2／s1c4／s2c3 publication transforms、官方勘誤與公式 inventory 的詳細權威。
> 完整 pipeline 順序見 `playbook/pipeline-reference.md` §1a；逐支腳本用途見
> `playbook/pipeline-script-catalog.md`。


### Export transaction 已修復；常規仍用 `--all-levels`

2026-08-29 起，腳本在 staging 建立／驗證完整候選，才一起替換 `guideContent/` 與 `guideOutlines.json`；每個 contentRef 會讀回 JSON，驗證 node id、非空 content、非空 blocks、contentFormat 與 sourcePages 型別。失敗 rollback，單等級只替換該級並保留另一級；舊 rmtree 與空／錯 schema 資料損失路徑都由 `test_pipeline_output_safety.py` 鎖住。

2026-08-30 起，s1c2/s1c4/s2c3 的三項人工判斷已整理成 `guide_publication_overlays.py` 的
deterministic transform，由 exporter 在 staged candidate 內套用，再以 exact structure gate
驗證後才 commit。標準 exporter 單獨重跑已可位元冪等，不再依賴事後修改 live output。

### 修正 1、2、5、6 已整合進 exporter（2026-08-30）

```bash
uv run python3 scripts/export_guide_outline_data.py --all-levels --use-guide-tree
python3 scripts/apply_manual_guide_fixes.py     # optional legacy compatibility check；應為 0 change
python3 scripts/track_a_ocr_repairs.py          # 3/3 publication structure，否則 exit 1
```

舊流程是在 live output 上事後補 patch；字串對不上時可能靜默不改。現在同一份對照表由
exporter 與 legacy compatibility script 共用，staged precommit gate 會精確驗證三個 structure
名稱與內容。以下保留修正內容的來源說明，不必再手動執行。

### 修正 5：s1c2 標題升階（2026-08-08 新增，已腳本化）

publication overlay 把「假說檢定名詞介紹：」升為 h3。
這章在 PDF 裡只有這一個次級標題，而且它**緊貼表格上緣**（y 421.6–434.9 vs 表格起點
426.3），一度被 `positioned_page_items` 的表格重疊過濾**整行刪掉**。

> 教訓 2026-08-08：表格重疊判定用「block 中心點 + pad 8」，緊貼表格邊緣的整行文字
> 會被無聲刪除——不是排版跑掉，是內容消失。根因：把「與表格 bbox 有交集」直接當成
> 「屬於表格內文」。規則：這類過濾要能被量測（本次量到兩級合計只有 1 個 block 受害，
> 才敢改）；`pages_cache` 的 OCR 標題現在用來救回這種被誤刪的行。

> 教訓 2026-08-08：想用 OCR 的 heading 標記取代編號式 regex 來判定標題——**全語料試算
> 後放棄**：OCR 把 `• 分布式詞嵌入`、`○ 應用示例：`、斷句的 `響包括：` 都標成標題，
> 約半數是雜訊，會讓 25 章的導覽變差來換 1 章變好。規則：**換掉一個啟發式之前，先在
> 全語料上算「改善幾章 vs 惡化幾章」**，不要只看目標案例。

### 修正 6：s2c3 導入策略標題同步（2026-08-30 新增，已腳本化）

publication overlay 將破碎的「（3）企業導入階段性實施策略企業需採取」精確改為
「（3） 導入策略與階段規劃」，並同步 Markdown、`headings[]`、`blocks[]`、hierarchy 與 search anchor；
Track A live gate 會拒絕任一表面殘留舊標題或缺少新節點。

### 修正 1、2 的內容（說明用，不必手動執行）

- **修正 1：s1c4 本節階層 heading 層級**（6 個 h4 → h3）。腳本對所有 `（\d+）` 開頭行
  一律輸出 `####`，但 PDF 中同符號用於兩個嵌套層次（x 座標同為 70.2，無法自動判斷），
  導致「本節階層」出現 `（1）→（1）` 同層。
- **修正 2：s1c4 H4 標題截短**（在修正 1 之後執行）。H3 節下的 H4 模型條目仍帶
  `（1）（2）…` 前綴（如「（1） 邏輯迴歸（Logistic Regression）是鑑別式AI 中最簡單…」
  → 「邏輯迴歸（Logistic Regression）」），造成側欄同層視覺混淆。

兩者的完整對照表在 `guide_publication_overlays.py`；
原本的手動 code block 見 `playbook/backups/pipeline-reference.md.bak-2026-08-07`。

驗收時機：每次執行 exporter 後跑 `track_a_ocr_repairs.py` 與 `npm run build`；legacy
`apply_manual_guide_fixes.py` 可用來確認相容性，但標準輸出必須讓它回報 0 change。

### 修正 4：官方勘誤表（2026-08-06 新增，已腳本化）

官方另發佈學習指引勘誤表（初級 3 頁、中級 7 頁，PDF 在 `data/{level}/pdfs/`，
OCR 成果在 `data/{level}/guide_ocr/errata/`）。內容是「頁碼 / 行數段落 / 原內容 / 更正後內容」
四欄表，多數是用字更正（反饋→回饋、攝像頭→鏡頭、合同→合約、ChatGTP→ChatGPT），
少數是整段改寫（初級 3-31 答案由 B 改為 A、中級 4-34 PDPA 整段重寫）。

```bash
python3 scripts/build_errata.py --level 初級                 # 勘誤表 OCR → data/{level}/errata_corrections.json
python3 scripts/build_errata.py --level 中級
python3 scripts/apply_errata.py --level 初級 [--dry-run]     # 套進 pages_cache 與 page_extract
python3 scripts/apply_errata.py --level 中級 [--dry-run]
```

**執行順序有硬性要求**——勘誤是疊加層，套在兩條軌的轉接產物上，重跑轉接層會沖掉：

```
ocr_extract.py     → apply_errata.py → apply_track_b_ocr_fixes.py → parse_guides.py
                  → Track B --check → export_guide_sections.py             （Track B）
merge_guide_ocr.py → apply_errata.py → clean_pdf_page_text.py → build_guide_tree.py
                  → export_guide_outline_data.py（staged precommit gate）
                  → export_guide_hierarchy.py → reading snapshot
                  → track_a_ocr_repairs.py                                  （Track A）
```

不改 `data/{level}/guide_ocr/`：那是 OCR 的忠實紀錄，要能對回原稿印的內容。

採**全有或全無**策略：一筆勘誤的片段沒有全部定位到就整筆不動，因為只改一半會產生
新舊混雜的段落。腳本是**冪等**的；插入型更正若「原文」是「更正後文字」的子字串，
必須先等長遮罩所有已完成 span，再找真正未更正的原文，否則每次重跑都會再追加一次。

自動比對解不了的（勘誤表對「原內容」的轉錄與講義原文有標點、條列符號、斷行的差異，
或一筆勘誤同時要改題目頁與解析頁）寫進 `data/{level}/errata_manual.json`
由人工指定精確的 find/replace，沿用同一套定位與冪等機制：

```json
{"key": "guide1", "page_label": "3-53", "resolves": ["3-53"],
 "track": "A",              // 選填。標明這筆只負責哪一軌；省略＝預期兩軌都要改到
 "note": "為什麼要人工指定",
 "find": "…", "replace": "…"}
```

**兩軌的原文格式常常不同**（Track B 是 OCR markdown、Track A 是 PDF 文字層），
同一處更正往往要各寫一筆並標 `track`。只改到一軌時腳本會示警——這類漏網以前是靜默的。
中級 5-21 的官方 diff 在同頁 Precision／Recall 間不唯一；TB-006 必須用含 Recall 標題的
人工上下文修正 Recall，並另把被誤改的 Precision 復原，不能接受第一個文字命中。

2026-08-30 現況：28 筆官方勘誤已處理，兩級 `errata_unresolved.json` 都是空陣列；
Type-I、Recall 與感知器 `w_i x_i` 等容易誤套的項目另由 Track A/B 精確 gate 鎖住。
完整收斂邊界見 `06-guide-ocr-recalibration.md`。

安全閥：純刪除（更正後文字是原文開頭）且刪掉超過 30 字的片段一律不套——
那幾乎都是勘誤表表格 OCR 壞掉造成的，照套會刪掉整段講義。

### 修正 3（已改為精確 inventory gate）：guideContent 的 LaTeX 公式

2026-06-10 手工補在 13 個章節檔的 98 處 `$$...$$`（把 PDF 文字層攤平的公式亂碼換成
可渲染 LaTeX）**沒有留在任何腳本裡**，重跑 export 就全數消失。2026-08-06 起
`export_guide_outline_data.py` 的 `inject_formulas_into_markdown()` 自動做這件事。2026-08-30 起
**不再用 `$$` 數量或「約六成」推估正確率**：Track A 對 43 個已審公式頁驗 exact same-page
formula multiset、目標 attachment 與 `formulaOnly`；加上 Type-I／Recall，共 45 筆
`formula_and_errata` inventory。169 筆總 inventory remaining=0，另有 X_max、Softmax z_j、
感知器官方勘誤 3 筆 publication overlays。

`content` 雖不是 GuidePage 的主要渲染來源（64 章都優先走 `blocks`），仍由概念圖卡與 export
流程讀取，所以 overlay 會同步兩者；本機 reading snapshot 存在時也會驗它。這套數字只代表已審 inventory closure；
新增／換版 PDF 仍須看原始影像，確認後把新缺陷加入 registry，不能把 gate 外推成全頁正確。
