# 2026-11 guide anchor 遷移：非作者審查的委派紀錄與 ds1017 原始輸出

日期：2026-11-02。這份紀錄說明誰授權了誰、審查範圍，並逐字保存審查者輸出；差異證據本身在
[`guide-anchor-migration-20261102.md`](guide-anchor-migration-20261102.md)。

## 為什麼需要重新審查

2026-11 guide_tree 重建改寫 `中級-guide3/mid-s3c9.json`，三個 guide anchor 的 block 序號 +1。
更新 anchor 後兩個 unit 的 contentHash 改變；依 `data-contracts.md` §2 第 7 條「審核以 subjectHash 和 dependency hashes 全等才有效」，
兩個 unit 的 domain／contract review，以及 dependencyHashes 含 unit contentHash 的 lab（semantic／contract／execution）與 project（domain／contract）review 全部失效。

## 維護者的授權與範圍限定

維護者（repo 使用者本人）於 2026-11-02 核准新的 anchor 位置，並表示「可以使用 ds1017」，
指定 ds1017 為本輪非作者審查者。資格紀錄：`content/learning/qualifications/guide-anchor-migration-20261102-review-delegation.json`。

**涵蓋**：機械式 anchor-ID 遷移——新舊 block 文字同一、新 ID 唯一可解析、diff 侷限於 anchor／hash／revision 欄位、history 保留、舊紀錄原封保存。
**不涵蓋**：教學語意重審、Lab L4 重做、真人 Colab L5、題目答案重判。

## 角色

- 作者：`agent-claude-code`
- 審查者：`agent-ds1017` = 團購網關模型 `deepseek-v4.1-flash:1017`，以
  `cshare -m deepseek-v4.1-flash:1017 -p <prompt> --allowedTools "Read,Grep,Glob,Bash(git show:*),Bash(cat:*),Bash(jq:*),Bash(shasum:*)" --output-format json`
  在 repo 根目錄啟動（唯讀工具；相較委派指示多加 `shasum` 以便比對 hash），角色 `independent_model`
- 資格授予者：`maintainer`；`humanApproval: false`——維護者授權 model reviewer，不等於維護者本人完成審查

自動化檢查不由 ds1017 背書：C1 由 `scripts/validate_learning_content.py --all --check` 實跑；
L0–L3 由作者 2026-11-02 本機實跑 `verify_learning_labs.py --check`（exit 0），紀錄 `evidence/assessment/lab-l0-l3-reverify-20261102.json`。

## 執行資訊

- prompt（含完整 diff）sha256：`2948f538f15073a1bc7144356512a27480e497a311ad593639f5d996e861f726`（約 18.6 KB；內容為本目錄 diff 證據＋M1–M9 檢查清單）
- 原始 JSON 輸出 sha256：`547c74ea97be04bf5737b0277c5d4608eee63b5d180adc0fa47255176432e348`
- 執行統計：`{"session_id":"ebf4c29f-98cc-48e3-b896-9781499cbd6a","num_turns":204,"duration_ms":356002,"total_cost_usd":4.555674999999998,"is_error":false,"denials":15}`
- 有數次寫入 /tmp 的複合指令被權限擋下，審查者改用允許的唯讀指令完成，未影響結論。

## 作者對審查結果的複核

- M1–M4、M6：作者以 Python 獨立重做（排除 id 後逐欄位比對、quote 命中唯一、新舊 blob hash），結果一致。
- M7：作者重算 11 個 superseded 檔與 `git show HEAD:<原路徑>` 的 sha256，全部相同。
- M8：`git diff --quiet HEAD` 對 lab、project 與兩份 unit `.md` 無差異。
- M9 (a)：審查當下 `evidence-guide-anchor-migration-20261102-diff` 的 JSON 尚未建立；審查後已建立（artifactRef 指向差異證據 md），不再懸空。
- M9 (b)：即本輪隨後開立的 20261102-v3 review。
- M9 (c)：差異證據描述的是審查完成後的終態（lab／project 只改 reviewIds 等被 contentHash 排除的欄位）；審查當下兩檔尚未改動，兩者不衝突。
- `image_units_all_levels.json` 的 headingBlockId 觀察屬既有、與本次無關，未處理。

## ds1017 原始輸出（逐字）

```text
M1: PASS — 以 `jq -S -c '.blocks[]|select(.id=="block-N")|del(.id)' | shasum -a 256` 對三組做正規化後 hash：70→71 皆 `0842f65b64c4e54d69589f2450390566ff77b720c858d3c0d54f2a8d0115049f`、148→149 皆 `f5f54f6093eb3b9e160a5104e6b69e6a69319f7925bf3b2ed4166ee775d23b10`、167→168 皆 `4fb2d92b393d9003cba44e336d44524056397e47b198afc8091f4e1063c16f04`；即除 `id` 外 text/title、type、depth、marker、pageIndex、bbox、anchor、nodeId、kind、source 全等。

M2: PASS — 新版 `block-71/149/168` 存在且 `pageIndex` 分別為 154/158/159，與三個 evidence 的 `pageIndexes` 一致；`jq 'select(((.text//.title)//"")|contains($q))|.id'` 對三個 quote 各只回傳 `block-71`、`block-149`、`block-168` 一個結果；`block-168.anchor == "4交叉驗證"`；block 陣列 221 筆、`id` unique 221。

M3: PASS — 新版 `block-70`＝「適用：類別分佈相對均衡時效果良好。」、`block-148`＝迴歸 MAE/RMSE/R²、`block-167`＝Boxplot 段落，確實已不是原文字；`git diff --stat` 顯示 220→221 blocks，`git diff` 中 id 行恰為 160 刪／161 增（新增 block-61），非 id/content 的實質差異只有 block-59 text 與 bbox 兩值及新 block-61 全欄位；另以 `content` 長度 7848→7901（+53）＝block-59 文字 (81−43)＋插入 bullet `• P：實際為正類的樣本數\n\n` (15) 精確吻合，證明 content 投影只含這兩處變更。

M4: PASS — `git show HEAD:…mid-s3c9.json | shasum -a 256` = `263987fb…6f37`，工作樹 `shasum` = `fae30b12…0083`，與作者主張一致；`data/resource_catalog.json` 的 `learning-guide-middle-3` 之 `version`／`sha256` 均已改為 `sha256:fae30b12…0083`。

M5: PASS — 實際 `git diff HEAD` 與作者 diff 逐字相同：evidence 只改 revision／contentHash／blockIds／sourceHash／locator 的 block 號／observedAt，claim、excerpt、quote、artifactRef、artifactHash 不變（頁面 PNG 實測 hash `f81f…`、`77d7…`、`b9ab…` 與 artifactHash 相符）；兩個 unit 只改 contentHash、snapshot revision/hash、guideRef blockIds/sourceHash；guide-anchors 只改 current 的三個欄位、history、evidenceIds；catalog 只改 version/sha256。contentHash 本身無法以 Python 重算，屬 UNVERIFIABLE（依指示可接受）。

M6: PASS — `jq '.anchors[]|select(.current.nodeId=="mid-s3c9")'` 顯示每個 anchor 的 `history` 皆保留一筆舊 `{sourceHash: sha256:263987fb…, blockIds: ["block-70"/"block-148"/"block-167"], nodeId: "mid-s3c9"}`，符合 guideHistory schema 的必填欄位。

M7: PASS — `reviews/superseded/` 8 檔與 `evidence/superseded/*.r1.json` 3 檔逐一 `shasum -a 256` 與 `git show HEAD:<原路徑> | shasum -a 256` 比對，11 組全部相同（例：contract-imbalanced-v1 `26598e7d…`、domain-threshold-v2 `278ded74…`、accuracy r1 `b520f0f6…`），且原路徑在 `git status` 顯示 D。

M8: PASS — lab `ecdb78f8…`、project `43a4e1fe…`、unit-imbalanced `.md` `f97f1314…`、unit-threshold `.md` `6da06ffb…`，四者工作樹 `shasum` 與 HEAD 完全相同，且 `git status --porcelain` 對這四條路徑無輸出。

M9: PASS（無阻擋問題，另有 3 個非阻擋觀察）— (a) 三個 anchor 的 `evidenceIds` 新增 `evidence-guide-anchor-migration-20261102-diff`，但 repo 內只有 `content/learning/evidence/guide-anchor-migration-20261102.md`，沒有同 id 的 evidence JSON；schema 只檢查 identifier 格式、`resolver.validate` 也不解析 anchor evidenceIds，故不阻擋，但屬 dangling reference，建議補 JSON 或改用實際存在的 id。(b) 現存 lab/project review 的 `dependencyHashes` 仍綁舊 unit contentHash，且兩 unit 的 `reviewIds` 仍指向已移入 `reviews/superseded/` 的檔案；這與作者所述「其後重新開立 review」一致，preview gate 只列為 unmetReviews 而非 blocking issue，屬待辦而非本次遷移錯誤。(c) 作者新 md 的「lab／project：只更新 reviewIds」與實際工作樹（兩檔與 HEAD 逐 byte 相同）不符，屬文件表述不一致；另 `data/共用/image_units_all_levels.json` 的 `headingBlockId` 與新舊 guide 都不一致，但該檔未改動且問題早於本次遷移，不列為本次新缺陷。未發現其他受位移影響卻未更新的 mid-s3c9 anchor（`guide-anchors.json` 中該 node 僅這三筆），也未發現其他 active 檔案殘留舊 hash／舊 block ID（舊值只出現在 history、superseded 與歷史 assessment 記錄）。

VERDICT: PASS
```
