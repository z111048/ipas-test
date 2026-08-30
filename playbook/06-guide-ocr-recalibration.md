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
| 考題 production gate | catalog 14 份／709 題通過；2 題官方來源歧義以可見註記保留 |
| 勘誤資源 | 初級／中級勘誤皆由 resource catalog 發佈；初級 gallery 新增 8 個逐頁／表格資產 |
| Vision sidecar | fresh checkout 0/709；2026-08-30 本機 150/709，promotion 仍阻擋 |
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

## 這個任務留給制度的東西（已寫進 pipeline-reference）

- §1a — OCR 兩軌與**完整重跑順序**（勘誤是疊加層、轉接層重跑會沖掉）。
- §3 — `export_guide_embedded_exercises.py` 的邊界陷阱（頁眉黏進選項、解析吃到下一章／參考
  書目 appendix、無條件頁尾收束會掉題）及寫檔前 fail-closed 契約。
- §9 — 中文 PDF 文字比對的教訓（兩邊都要 NFKC、題幹與選項分開比、題目常跨頁）。
- §10 修正 4 — 勘誤的全有或全無策略、兩軌格式不同要各寫一筆、安全閥。
