<!-- 2026-11-02: 精簡（419→250 內）：歷次改版註解收成此行；§6 教訓改寫為規則清單；§7-0／§7-1 完成紀錄、§7-2 舊精度表、
     §7-6 長篇診斷過程移到 backups/08-topic-labeling.md.bak-2026-11-02（更早的見 .bak-2026-08-08～-10-31）。
     同步現況：詞彙表 182、815/815 有標註、guideExamAnnotations 與熱度數字、/mindmap 導覽名「章節熱度圖」。 -->

# 08 — 考古題熱度、概念標籤與心智圖

**狀態：`/mindmap`（導覽名「章節熱度圖」，頁內「按章節」／「按概念」兩軸）已上線；概念詞彙表 182 個
（`data/topics/topics.json`，`signed-off`；原定案 174 個加 8 個人工補簽），815 題官方考古題
全有概念標註（2026-10-31，`deepseek-v4-pro --model-all`、`qwen3.5:397b` 驗收，見 §7-2）；
出題配額已改為熱度加權（§7-4）。未完：§7-5 補教材、§7-7 正規化標註結構；概念圖卡另有 10 張
字形變形但可讀，若要處理需換產圖方案（§7-6）。**

出題那條線在 07；本檔是「反過來用考古題驅動出題與導覽」的那一半。

## §1 這條線在做什麼

出題原本是「每個小節平均出 2 題」，跟實際考試分布無關。這條線反過來：
**先量出考古題實際考哪裡，再用熱度驅動出題配額與站上導覽。**

三個資料軸，彼此正交，不要混在一起：

| 軸 | 回答什麼 | 現況 |
|---|---|---|
| **位置**（章節樹） | 這題考講義哪一段 | ✅ `guideExamAnnotations` |
| **概念**（受控詞彙） | 這題考什麼觀念 | ✅ 182 個概念已指派並驗收，前端概念軸已上線 |
| **熱度**（統計） | 哪裡考得多 | ✅ 章層級與概念層級都已上線，標題層不做（§4） |

位置軸是樹狀的，概念軸是跨章節的圖——**硬把概念塞進樹只會讓樹變成圖**。

## §2 已經有的資料（別重造）

- `frontend/src/generated/guideExamAnnotations/` — 14 份卷 700 題官方考古題 → 2,903 個講義區塊、
  5,862 條標註（`index.json` 的 `stats`，2026-11-02），帶 `confidence` 與 `why_relevant`。
  來源是 `examReferenceAnswers` 的引文。
- `frontend/src/generated/examReferenceAnswers/` — **815 題**的詳解（16 卷），每題帶
  `citations`（有序，含 `block_ids`）與 **`key_concepts`**（概念詞組）。
- `frontend/src/generated/guideNav.json`（64 節點）／`guideHierarchy.json`（約 1,200 節點）。

## §3 章節熱度圖（已上線）

```bash
python3 scripts/export_guide_mindmap.py [--check]   # → guideMindmap/{subjectId}.json
```

只讀既有 committed 產物，無 API 花費，可隨時重跑。三個設計決定，改動前先讀：

- **各章題數不可相加**。一題通常引用數章（2026-08-08 時逐章加總 905 但實際只有 450 題）。
  子樹彙總取 **max** 不是 sum，頁面也明講這件事——不然使用者會自己加起來。
- **同時給密度（每千字題數）**。章節篇幅差一個數量級，只看題數會把「長」讀成「熱」。
- **標註只到章層級，節點以空心表示「尚無統計」而不是 0**。假的深度比沒有深度糟。

熱度前段（2026-11-02 `guideMindmap`）：初級科目一第三章 110 題、初級科目二第三章 104 題、
中級科目三第四／五章各 37 題。**初級的集中度遠高於中級。**

## §4 標題層熱度：技術可行，但價值有限

量過（2026-08-08）：96.4% 的題目落得到標題節點，但**標題名稱空泛**（最熱的是「C. 挑戰與未來方向」
69 題；查證後那段確實是高產段落，只是標題取得很空）。

> 結論：位置軸再往下挖也回答不了「該準備哪個觀念」。要往下做應該做概念軸，
> 不是把樹挖深。標題層資料本身可用，若要上線，節點標籤得換成概念而非原標題。

## §5 概念詞彙表（已定案，`data/topics/topics.json`）

```bash
python3 scripts/build_topic_vocabulary.py                 # 分科目收斂 → 草稿
python3 scripts/build_topic_vocabulary.py --consolidate    # 合併大類與重複概念
python3 scripts/build_topic_vocabulary.py --show           # 依大類印出
python3 scripts/build_topic_vocabulary.py --dedupe-pairs   # 語意去重 → 合併配對清單（待人工勾選）
python3 scripts/build_topic_vocabulary.py --apply-pairs    # 合併＋重播 alias cleanup／人工補簽 → topics.json
```

三個檔各有角色，不要混：`topics_draft.json`（草稿，不動）→ `merge_pairs.json`
（合併決定，含 `stillOpen` 未決項）→ `topics.json`（定案版，標題目時用這個）。

`key_concepts` 不能直接當標籤：當初 3,034 個詞組有 2,685 種寫法、93% 只出現一次，純字串正規化
也只降到 2,613 種。收斂是語意工作，所以分科目請模型收斂，再合併成 **204 概念 / 8 大類**。

**2026-08-08 定案 204 → 174**。`known_duplicate_pairs.json` 是先寫好的人工基線，用途是
**驗收去重輸出**：漏太多代表太保守，基線外的新配對要逐條看；其中 5 組 `keepSeparate`
（`異常偵測` vs `異常值偵測`、四個多模態概念、`模型優化` vs `效能優化`）**看起來像重複但不是**，
被合併就是誤殺。去重時一次送 204 個概念只挖到 10 組，改成「每大類各問一次＋全域一次」才拿到
19 組——**清單太長模型只挑最明顯的**；是基線讓「模型太保守」變成一個數字而不是感覺。

`stillOpen` 有 5 組未決（`模型評估`/`評估指標`、`機率分佈`/`機率與統計`、
`特徵縮放`/`資料標準化`、`異常值偵測`/`離群值處理`、兩個 AI 幻覺概念），要動之前先看標註分布。

**人工補簽（174 → 182）**：2026-08-31 補 7 個（二分搜尋、人工智慧能力層級、圖論分析、感知器網路、
推理模型、數據密度、演算法複雜度）並移除兩個會造成歧義的舊別名；2026-10-31 補 `Python程式語意`
（`mid_1151_s2_q39`）。決定記在 `data/topics/manual_topic_additions.json`；`--apply-pairs` 會先重播
committed `alias_cleanup.json` 再套此 overlay，並有 exact-rebuild regression。補簽限於可由官方題幹與
已發布詳解直接判定的概念，不重跑模型，也不改寫 2026-08-08 的歷史基線。

## §6 這條線踩過的坑（全是「看起來成功、實際上錯」）

- **不要送整頁 PDF 給視覺驗證器**：公告試題的答案印在表格最左欄。只送 `image_*.png` 裁圖，
  排除 `page.png`/`table_*.png`，沒有裁圖就跳過；偵測手段是 `07` 的 `answer_echo_rate`。
- **批次彙總任一分組失敗就拒絕寫出**（曾 7 組壞 4 組，照樣合併剩下 3 組並印「成功」）。
- **完整性要逐批比對「送進去的每一筆都有回來」**，不是只看非空：曾有 1,108 個標籤裡 326 個「未評」
  卻標成 `verified`（一批 36 個判定被 `max_tokens` 截掉）。輸出量是輸入數倍的步驟批次要開更小。
- **模型回傳的識別碼要在該批範圍內寬鬆比對**（完全相同 → 尾綴相同且唯一）：key `sample:sample_q27`
  被模型縮成 `sample_q27`、對不上就被靜默丟掉——上面 326 個「未評」的真因。「批次一直失敗」先懷疑
  自己的比對，不要先怪模型。
- **合併鍵只用正式名稱，別名只做累積**；每一次合併印出 `合併「X」→「Y」`。拿模型 alias 當合併鍵等於
  取傳遞閉包，一條爛連結讓「欠擬合」吞掉 133 個別名。
- **名稱包含式合併要擋 `MEANING_CHANGING_PREFIX`**（非/半/自/反/無/未/不/逆）：曾把「非監督式學習」
  併進「監督式學習」。寧可少併。
- **彙總步驟一律從原始草稿重算**（`_drafts_by_subject.json`），在已統整輸出上重跑會累積合併。
- **錯誤訊息要區分「空回應」與「回應無法解析（N 字，可能被截斷）」**；`max_tokens` 太小時重試必然白費。
- **LLM 產生的結構要存下來沿用**：大類歸併每次重跑得到 7 或 8 類，存進 `parentMap`，重算才加 `--remap`。

**貫穿這些坑的一條**：有效的防護都不是更強的模型，而是**讓錯誤現形的機制**——
選項亂序把洩題變成錯誤率、`answer_echo_rate` 把偷看變成數字、逐條列印合併記錄把
誤殺變成清單。設計彙總步驟時先問：**這一步錯了，會不會有人看得出來？**

## §6a 審核機制

```bash
python3 scripts/audit_resources.py            # Layer 1 確定性；build_web.py 會先跑，FAIL 中止 build
python3 scripts/review_committed_notebooks.py --python <有 pandas/sklearn 的直譯器>
```

三層：**Layer 1** 確定性（不需模型金鑰，`audit_resources.py`）→ **Layer 2** 語意
（`verify_question_answers.py` 多模型共識、notebook 語意複查）→ **Layer 3** 人工佇列。
例外一律寫 `data/audit_allowlist.json` **並附理由**（目前 1 筆）。

- **語意審核器不是確定性的**：同一份 notebook 連跑三次照出的低嚴重度項目都不同。別把「這輪 0 筆」
  當「這本乾淨」；收工條件是「照出來的每一筆都逐條看過並處置」。自己補的說明要先讀那格程式碼再寫。
- **閘門若會誤報就會被繞過**（第一版誤判 483 筆中英夾雜、62 筆詞彙表、27 筆 notebook）。
  寫閘門的力氣要有一半花在驗證閘門本身：對已知正確資料回報乾淨、對已知錯誤資料抓得到。
- 2026-08-08 notebook 修正的經驗：照出的缺陷**大多數不是內容錯，而是同一個 markdown 底下連放
  好幾個 code cell，補小節標題就對了**；另有閘門把程式碼截在 1500 字造成的誤報（`pipeline-reference` §5）。

## §7 待接工作（依順序）

0. ~~notebook 說明與程式碼不符~~ ✅ 2026-08-08（經驗併入 §6a）。
1. ~~語意去重~~ ✅ 2026-08-08（204 → 174，經驗併入 §5）。
2. ~~指派標籤~~ ✅ `assign_question_topics.py`。**精度基線**：2026-08-08 別名比對為主時
   正確 62%／過廣 25%／錯誤 13%；清完別名只到 63%；**全部走模型讀詳解（`--model-all`）75%／22%／3%**。
   真因是 `key_concepts` 混了干擾項概念（該題 `key_concepts` 越多，別名比對越差：1–3 個 100%、
   7+ 個 54%），別名比對分不出考點與干擾項，模型讀詳解分得出來。現行 815 題（2026-10-31，
   `deepseek-v4-pro --model-all`、`qwen3.5:397b` 驗收）：正確 1,139／過廣 419／錯誤 64（已濾除）。
   流程與參數見 `pipeline-reference.md` §5b 與 `07` §7。
   > 規則：**先量再改**。「別名品質不好」是真的、「清了會變準」是假的，兩者看起來一樣合理。
   > 分來源、分分組各算一次正確率，比再讀一次程式碼有用。
3. ~~概念熱度~~ ✅ 資料層＋前端（`/mindmap`「按概念」軸：長條＝題數、右欄＝散落章數，兩種排序；
   大類篩選與搜尋；展開列出章節分布）。`topicHeat.json` 走動態 import，不進首頁 bundle。

   ```bash
   python3 scripts/export_topic_heat.py   # → frontend/src/generated/topicHeat.json
   ```

   只讀 committed 產物、無 API 花費、可隨時重跑。**採計規則：只算 `verdict=正確`**
   （2026-11-02：1,149 個標籤／180 個概念有命中）；`count`／`countLoose` 兩種都輸出，前端要改規則
   不必重跑。嚴格採計是量過才選的：寬鬆版會把空泛上位詞（「機率與統計」「機器學習概論」）推上來。
   **「散落章數」才是這個軸的新資訊**——評估指標散在 12 章，是跨章節概念；集中在少數章的是新主題。

   ⚠️ 兩份產物的題號不同名：標註用考卷題號（`jr_1141_s1_q8`），舊詳解鍵用 `referenceQuestionId`
   （`exam1_q8`）。只接一種會大量對不到章節，而且**看起來像「標註覆蓋不足」而不是 join 寫錯**。
   目前 `questionsWithoutChapter` 115 題，是因為章節標註只建在 14 份 700 題上，屬預期。

   ⚠️ **「散落章數」不能用 `chapterCount`**。同一份內容有兩套章節層級——官方大綱章（`*pdf-c{n}`）
   與學習指引章——標註兩邊各記一次（2026-08-08 量得虛胖約 32%）。腳本另出
   `guideChapterCount`／`outlineChapterCount` 與每章 `kind`，前端顯示用前者，展開時兩套分組標明。

   > 規則：**任何跨產物 join 或計數，先列出兩邊的 id 樣本各三筆再寫程式**——這條線已因
   > 兩套 id 體系（題號、章節層級）踩過兩次，兩次都偽裝成「覆蓋不足」或「數字看起來合理」。

   > 規則：**產生 committed JSON 的腳本，凡迭代 set／dict 決定輸出順序處一律 `sorted()`**，並用
   > 不同 `PYTHONHASHSEED` 跑兩次 `cmp` 驗證位元相同（`export_topic_heat.py` 曾因此每次重跑無故 diff）。
4. ~~熱度驅動出題配額~~ ✅ `build_codex_section_prompts.py --heat-total N`：按 guideMindmap 的章熱度
   分章配額，再按區塊長度分到各區塊，上限 1 題／400 字。⚠️ 配額**必須對整科算完再篩章節**
   （只拿選中的章去算，`--chapter s1c2 --heat-total 100` 會把整科 100 題全給那一章）。
5. **教材相對考試權重不足**（`data/baselines/2026-08-08_教材熱度落差.json`）。2026-08-08 做 §7-4 時
   量出：初級兩科各以 100 題為目標，只排得出 67 與 58 題，短少全部是「總容量不足」——

   | 章節 | 考古題 | 講義字數 | 密度（題/千字） | 需補 |
   |---|---|---|---|---|
   | s1c3 機器學習概念 | 114 | 8,194 | **11.7** | 12,400 字 |
   | s2c3 生成式AI導入評估規劃 | 127 | 15,087 | 7.1 | 13,600 字 |
   | s2c1、s2c2、s1c1 | 31／33／65 | — | 3.2–4.2 | 800–1,600 字 |

   **最熱的章節，講義篇幅最小**。決定：**維持 1 題／400 字不調低**——調低是拿同一段材料多出題，
   會退回「題目很多但重複」。短少改為明確回報，補教材另立為內容工作（不是 pipeline 問題）。
6. **card 欄位與概念圖卡** ✅ 2026-08-08 驗過並修完。

   ```bash
   python3 scripts/sample_card_review.py --size 40   # 確定性分層抽樣 → 工作表
   python3 scripts/sample_card_review.py --tally     # 判定填完後算錯誤率
   python3 scripts/fix_card_defects.py [--dry-run]   # 修值域外資料與附錄殘留（冪等）
   ```

   **card**（基線 `data/baselines/2026-08-08_card欄位抽樣驗收.json`，母體 689 題有 card）：抽 40 題
   只找到**一個系統性缺陷**：179 題 `guide_exercises` 的 `confusion` 全是 `explanation` 複製、`mnemonic`
   全是同一句佔位字串（前端 `CardPanel` 會顯示成「常見混淆」「記憶口訣」）。已全數用 codex CLI 重生；
   根因腳本 `export_guide_embedded_exercises.py` 不再編造 card 且保留既有 card。
   **`frequency` 欄沒有事實依據**（與該章實際考古題數秩相關 −0.17，方向相反），已整欄移除，
   圖卡第四格改查該章實際考古題數。`audit_resources.py` 已加閘門：`confusion` 是解析複製、
   `mnemonic` 是佔位字串。
   > 規則：**能機械偵測的缺陷不要用抽樣去估**。樣本裡一出現同型缺陷，立刻寫全量掃描，分清「系統性
   > 缺陷」與「散落錯誤」——修法完全不同。
   > 規則：**還沒決定修不修的缺陷不要先加進 allowlist**——那是它變成永久現狀的方式；要嘛修掉、
   > 要嘛明確決定不修再 allowlist 並寫理由。

   **概念圖卡**（基線 `data/baselines/2026-08-08_概念圖卡抽樣驗收.json`）：抽 30 張內容 30/30 正確，
   10 張字形變形但可讀，4 張真的文字缺陷（非中文詞、截斷、`判別式AI` 應為初級官方章名的
   **鑑別式AI**）已全數修好。

   ```bash
   python3 scripts/verify_generated_images.py --sample 30   # 或 --all / --ids a,b
   python3 scripts/regenerate_flagged_images.py --from-review --attempts 3
   ```

   `verify_generated_images.py` 用 `codex exec --image` 讀回圖上每一串中文並逐條判定
   （garbled／nonword／truncated／terminology／wrong）；上線前先拿 4 張已知缺陷＋3 張已知乾淨驗過閘門
   本身（§6a）。官方用詞清單從 `toc_manifest.json`（SSOT）＋`topics.json` 組出來，不另建第三份。
   `generate_images.py` 也接上同一個檢查，**每一次產圖都過閘門**（`--no-verify` 可跳過，不建議）。
   產圖一律走 `imggen_client.py`（CLAUDE.md 環境備忘），修圖卡用 **`/edit` 圖生圖、拿現有那張當參考
   只改錯字**——從頭重抽會連版面一起換掉。

   `regenerate_flagged_images.py` 的保護，少一條就會出事：
   - **回饋要累積**：每輪把**所有**已知問題寫進 prompt（不是取代成本輪的），判定器要列出全部問題，
     `/edit` 從上一輪最好的結果繼續，不要每輪從原始備份重來。
   - **所有嘗試都沒過就還原備份**（`build/image_backup/`），不然會靜靜把好圖換成壞圖。
   - **`error` 不算 pass**：codex 沒回應時當失敗重試。
   - **技術失敗與內容失敗分開計數**（`--infra-retries`，不佔 `--attempts`），不然服務 502 會偽裝成
     「模型修不好」。
   - **沒過的候選圖要留下來**（`build/image_candidates/`，檔名帶 attempt 與失敗類型），不然無法查證
     「閘門是不是太嚴」。

   > 規則：**斷言「這是模型能力極限」之前，先確認自己的迴圈沒有在丟資訊**（回饋有累積嗎？從最好的
   > 狀態繼續嗎？判定器列出全部問題嗎？）。`guide3-mid-s3c3-img-016` 曾被誤判為中文渲染極限，修好
   > 迴圈後 `/edit` 第 2 次就通過。若排除迴圈缺陷後仍反覆寫不出正確中文，才換方案
   > （HTML/SVG＋真字型渲染），不是換 prompt。
7. **正規化標註結構**：現有 `guideExamAnnotations` 是反正規化的（同一題的題幹被複製多次），
   加上生成題與概念標籤後會膨脹。拆成 `questionIndex` + 邊表 + `topics`。
