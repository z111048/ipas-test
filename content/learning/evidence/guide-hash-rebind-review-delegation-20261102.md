# 2026-11 round 3 guide 雜湊重綁：非作者審查的委派紀錄與 ds1017 原始輸出

日期：2026-11-02。這份紀錄說明誰授權了誰、審查範圍，並逐字保存審查者輸出；差異證據本身在
[`guide-hash-rebind-20261102.md`](guide-hash-rebind-20261102.md)。前例：
[`guide-anchor-migration-review-delegation-20261102.md`](guide-anchor-migration-review-delegation-20261102.md)、
`assessment/analysis-hash-rebind-review-delegation-20261102.json`。

## 為什麼需要重新審查

round 3 第 3–5 批講義修正改寫 `中級-guide2/mid-s2c4.json`（補回印刷頁 2.、3. 編號標題、CJK 括號空白）與
`中級-guide3/mid-s3c9.json`（pageIndex 151／153／160 刪除中文與「（」之間多餘空白），兩檔整檔 sha256 改變，
`validate_learning_content.py --all --check` 因 `stale_guide_hash`（8）／`stale_source_hash`（5）blocked。
更新 guide hash 後三個 unit 的 contentHash 改變；依 `data-contracts.md` §2 第 7 條，三個 unit 的 domain／contract review、
dependencyHashes 含 unit contentHash 的 lab（semantic／contract／execution）與 project（domain／contract）review 全部失效；
`data/resource_catalog.json` 整檔 hash 改變也使 analysis-imbalanced-source-examples-v1 的 catalogHash 與 peer／contract review 失效。

## 維護者的授權與範圍限定

維護者（repo 使用者本人）於 2026-11-02 核准 mid-s2c4、mid-s3c9 只換雜湊（block id 不變），並指定 ds1017 擔任範圍受限的非作者審查者。
資格紀錄：`content/learning/qualifications/guide-hash-rebind-20261102-review-delegation.json`。

**涵蓋**：機械式雜湊重綁——被引用 block 新舊 id 與逐欄位內容同一、quote 唯一命中、diff 侷限於 hash／revision／observedAt／contentHash／reviewIds／history、
舊紀錄原封保存，以及 analysis 的 catalogHash 連帶重綁。
**不涵蓋**：教學語意重審、Lab L4 重做、真人 Colab L5、題目答案重判、講義修正本身的 OCR 正確性。

## 角色

- 作者：`agent-claude-code`
- 審查者：`agent-ds1017` = 團購網關模型 `deepseek-v4.1-flash:1017`，以
  `cshare -m deepseek-v4.1-flash:1017 -p <prompt> --allowedTools "Read,Grep,Glob,Bash(git diff:*),Bash(git show:*),Bash(shasum:*),Bash(jq:*)" --output-format json < /dev/null`
  在 repo 根目錄啟動（唯讀工具、未加 `--force`），角色 `independent_model`
- 資格授予者：`maintainer`；`humanApproval: false`——維護者授權 model reviewer，不等於維護者本人完成審查

自動化檢查不由 ds1017 背書：C1 由 `scripts/validate_learning_content.py --all --check` 實跑；
L0–L3 由作者 2026-11-02 本機實跑 `uv run --isolated --group learning-lab python scripts/verify_learning_labs.py --lab lab-imbalanced-classification --profile cpu --check`（exit 0），
紀錄 `evidence/assessment/lab-l0-l3-reverify-20261102-hash-rebind.json`。

## 執行資訊

- prompt sha256：`0731d58e681eb259dd07b88d6f20c4fce2278f003718a67f5a0dc6f6314306af`（44,823 bytes；內容為差異證據 md 全文＋`git diff --diff-filter=M HEAD -- content/learning data/resource_catalog.json`＋git status＋新 review 計畫＋H1–H9 檢查清單）
- 原始 JSON 輸出 sha256：`49d5b5ee5814bc4a93f93d95d8e06fb8a7bb1bb702f2d30fd7d14c9276313ba5`
- 執行統計：`{"session_id":"a1b985c1-2715-49e4-a898-95c5dfe50a1d","num_turns":96,"duration_ms":280195,"total_cost_usd":4.450529999999999,"is_error":false,"denials":8}`
- 有 8 次權限拒絕（審查者嘗試允許清單外的複合指令），改用允許的唯讀指令完成，未影響結論。

## 作者對審查結果的複核

- H1–H4：作者以 Python 獨立重做（HEAD 與工作樹同 id block dict `==` 比較、以排除 id／bbox 的 SequenceMatcher 定位全部差異、quote 命中唯一、新舊 blob hash），結果一致。
- H5、H8 中 ds1017 列為 UNVERIFIABLE 的 contentHash：作者以 `learning.contracts.content_hash` 與 `build_learning_assessment.assessment_inputs` 反推重算，
  三個 unit、四筆 evidence 與 analysis 全部 `True`（指令與輸出見差異證據）；lab／project 的 contentHash 重算與 HEAD 相同。
- H7：作者重算 4 個 evidence 與 8 個 review superseded 檔與 `git show HEAD:<原路徑>` 的 sha256，12 組全部相同。
- H9-3：審查當下 `evidence-guide-hash-rebind-20261102-{diff,delegation,lab-reverify}` 與新 review 尚未建立；審查後已建立，新 review 的 `evidenceRefs` 以實際 contentHash 綁定，不再懸空。
- H9-4 屬實：差異證據寫「四筆 evidence … `observedAt` 更新」，實際只有 mid-s2c4 由 `2026-09-07T11:38:00Z` 改為 `2026-11-02T00:00:00Z`；
  mid-s3c9 三筆原本即 `2026-11-02T00:00:00Z`，值未變（revision 仍 +1）。差異 artifact 已送審，維持原文，更正記於此。
- H9-5：前例 md 的 `block-59／61` 為 263987fb 版歷史敘述，非現行 GuideRef，與作者盤點結論一致。

## ds1017 原始輸出（逐字）

~~~~text
# 審查報告：round 3 講義雜湊重綁（mid-s2c4／mid-s3c9）

審查者：agent-ds1017（唯讀、非作者）。基準：工作樹 vs `HEAD e5ecfd5`。以下每項都是我實際執行工具後的觀察，不採信作者敘述。

## H1：兩檔 sha256 — PASS

```
shasum -a 256 frontend/src/generated/guideContent/中級-guide2/mid-s2c4.json
git show HEAD:...mid-s2c4.json | shasum -a 256
```
- mid-s2c4：工作樹 `1d1eb632f9388f88…`、HEAD `0a879eb0b67bbdd3…` ✅
- mid-s3c9：工作樹 `8b4b3996c690ac58…`、HEAD `fae30b12ab4e03d3…` ✅
- 前後兩檔都只差 `blocks`：s3c9 的 `git diff -U0` 只有 3 個 hunk；s2c4 的 hunk 從第 120 行（`blocks` 陣列內）才開始。

## H2：四個被引用 block 新舊逐欄位相同 — PASS

以 `jq -S -c '.blocks[]|select(.id=="block-3")'` 對 HEAD 與工作樹各取 shasum（含 id、及 `del(.id)` 後）：

| block | 全物件 hash | 去 id 後 hash |
|---|---|---|
| s2c4 block-3 | 兩版皆 `aeb0418b…` | 兩版皆 `62e6a9f9…` |
| s3c9 block-71 | 兩版皆 `f1e4a3bf…` | 兩版皆 `0842f65b…` |
| s3c9 block-149 | 兩版皆 `8ae8c6b7…` | （全等即含去 id 全等） |
| s3c9 block-168 | 兩版皆 `8f2291c1…` | （同上） |

id 相同、`bbox`／`pageIndex`／`type`／`text`／`title` 等所有欄位相同。block 數：s2c4 HEAD 111 → 工作樹 112；s3c9 221 → 221，與作者主張一致。

## H3：quote 唯一命中、pageIndex、anchor — PASS

以 `jq '[.blocks[]|select(((.text//"")+" "+(.title//""))|contains("<quote>"))]|map({id,pageIndex,anchor,type})'`：

- `若資料本身存在缺漏…失真` → 唯一 `block-3`，pageIndex 56
- `95%樣本為負類時…仍高達95%` → 唯一 `block-71`，pageIndex 154
- `類別不平衡處理與評估策略` → 唯一 `block-149`，pageIndex 158
- `4. 交叉驗證` → 唯一 `block-168`（title），pageIndex 159，`anchor=="4交叉驗證"`

`[.blocks[].id]|group_by(.)|map(select(length>1))` 兩檔皆為 0（id 唯一）。

## H4：現行引用盤點 — PASS

掃 `content/learning`（排除 `superseded/`、`reviews/`）含 `block-[0-9]+` 的檔案，只有：

```
evidence-mid-s2c4-data-quality.json          block-3
evidence-mid-s3c9-{accuracy-imbalance,...}.json  block-71 / 149 / 168
identity/guide-anchors.json                  block-3,70,71,148,149,167,168（history 為舊版）
units/unit-split-before-fit.json             block-3
units/unit-threshold-decision.json           block-168
units/unit-imbalanced-classification.json    block-71,149
```

labs／projects 無 block id；`reviewed-diagnostic-source.json` 只用 anchor id。沒有任何現行 GuideRef 引用 s2c4 舊 `block-7` 以後的 id（即新 `block-8` 以後），也沒有引用 s3c9 的 `block-18/59/174`。`block-59/61` 只出現在前例 `guide-anchor-migration-20261102.md` 的歷史敘述（指 263987fb 版），`block-77` 只在 `recall-formula-direct-view.md`，皆非 GuideRef。另查 `data/guide_block_id_migrations.json`：s2c4 無 `block-3` 條目、s3c9 `block-70→71`、`148→149`、`167→168` 均 `exact`，與 anchor 一致。

## H5：變更範圍 — PASS（contentHash 重算 UNVERIFIABLE）

- `git diff --numstat data/resource_catalog.json` = `4 4`，只有 `learning-guide-middle-2/3` 兩列的 `version`／`sha256`。
- guide-anchors `-U0`：只有 4 個 `current.sourceHash`、4 段 history 追加、4 個 `evidenceIds` 追加。
- 四筆 evidence：只有 `revision`／`contentHash`／`guideRef.sourceHash`／`observedAt`（s2c4 的 observedAt 由 09-07 改 11-02；三筆 s3c9 原本已是 11-02，故無 diff）；`claim`、`locator`、`excerpt`、`quote`、`artifactRef`、`artifactHash` 皆未動。
- 三個 unit：只有 `contentHash`、dependencies／claim snapshot 的 `revision`／`hash`、`guideRefs[*].sourceHash`、`reviewIds`。
- lab／project：只有 `reviewIds`，`contentHash` 未動。
- 正文 `.md` 無任何修改（`git status` 無 unit `.md`）。
- 頁面 PNG 實測 hash 與 artifactHash 全符：page_056 `297a74ad…`、154 `f81f7863…`、158 `77d7d1a5…`、159 `b9aba37f…`。

**UNVERIFIABLE**：`contentHash` 的實際重算（我的工具限制為 Read/Grep/Glob/git/shasum/jq，不能跑 Python）。舊值與 HEAD 一致、新值與作者表格一致，但未獨立重算。

## H6：anchor history — PASS

`jq -c '.anchors[]|{anchorId,history}'`：三筆 s3c9 的 history 皆保留 `263987fb…`（block-70／148／167），並追加 `fae30b12…`（block-71／149／168）；s2c4 由空陣列追加 `0a879eb0…`（block-3）。每筆恰為 `sourceHash`／`blockIds`／`nodeId` 三欄，符合 `schemas/learning/identity.schema.json` 的 `guideHistory`（`additionalProperties:false`、required 這三欄）。

## H7：superseded 逐 byte 與 evidenceRefs — PASS

- 4 個 evidence：`superseded/…r1/r2.json` 的 sha256 與 `git show HEAD:content/learning/evidence/<id>.json` 完全相同（`d52ff5c2…`、`f95333c8…`、`c70b2d32…`、`5001d8c2…`）。
- 8 個 review：`superseded/…` 與 `git show HEAD:content/learning/reviews/<同檔名>` 四組 hash 全部相同。
- 綁定關係：split-before-fit v1/v2 的 `evidenceRefs` 為 `evidence-mid-s2c4-data-quality` revision 1／`2f021d9d…`；imbalanced-classification v3 綁 accuracy r2 `f0cff8cf…` 與 strategies r2 `077c688c…`；threshold-decision v3 綁 cross-validation r2 `5298976f…`；全部等於被移走的 r1/r2 檔自身 contentHash。
- 8 個舊 review id 在 `superseded/` 以外已無任何引用；split v2 的 `supersedes` 指 v1，鏈完整。

## H8：analysis catalogHash — PASS（新 analysis hash UNVERIFIABLE）

- `shasum -a 256 data/resource_catalog.json` = `1912806b845df306…`；HEAD = `aeed547b5f54ba4f…` ✅
- `scripts/build_learning_assessment.py:221` 明確使用 `resolver.input_hashes["data/resource_catalog.json"]`，而 `scripts/learning/references.py:129-135` 的 `read_bytes` 以 `blob_hash(整檔 bytes)` 填入 → 確為整檔 blob hash。
- catalog diff 只有兩列 resource；analysis 讀取的三卷 exams（jr_1151_s1、mid_1141_s3、mid_1151_s3）整列物件 hash 新舊相同（`416968b5…`）。
- analysis 其他輸入（`data/topics/topics.json`、analysis policy、question 檔、mock-blueprints）工作樹皆無修改。
- 舊 analysis contentHash `1060192b…` 與 v3 peer review 的 `subject.hash` 相符。
- **UNVERIFIABLE**：新 analysis contentHash `a0fec784…` 需跑 `assessment_inputs` 才能獨立重算；目前只能確認機制與輸入範圍正確。

## H9：其他發現 — PASS（非阻擋）

1. **授權範圍**：`qualifications/guide-hash-rebind-20261102-review-delegation.json` 的 `scopeLimit` 明確涵蓋本次機械重綁與 analysis catalogHash 連帶重綁；`scope` 與前例 `guide-anchor-migration-20261102` 相同，`humanApproval:false` 也與前例一致。新 review 計畫的 reviewer 指派（domain／semantic／peer = agent-ds1017、contract/execution = script）與 v3 前例一致，屬授權範圍內。
2. **lab L0–L3 誠實性**：`lab-l0-l3-reverify-20261102-hash-rebind.json` 明寫 `automatedScope: "L0-L3 implementation evidence; not an independent publication review"`、`publicationGate.L4/L5: "not_run"`、`reverifyScope` 末句「不是 L4、也不是真人 Colab L5」，標示誠實。其執行環境（Python 3.11.17、uv isolated）無法用我的工具重現，屬 UNVERIFIABLE，非阻擋。
3. **暫時性懸空引用（完成條件，非本次 FAIL）**：anchors 的 `evidenceIds` 已指向尚不存在的 `evidence-guide-hash-rebind-20261102-diff`；三個 unit 的 `reviewIds` 指向尚不存在的 v4/v3 review。依計畫這些會在審查後建立，**但 commit／發佈前必須先補齊**。
4. **文字精確度**：作者證據稱「四筆 evidence … `observedAt` 更新」，實際三筆 s3c9 的 observedAt 原本即 `2026-11-02T00:00:00Z`、未變動；僅 s2c4 由 09-07 改成 11-02。屬敘述不夠精確，不影響重綁正確性。
5. **庫存敘述**：證據清單未提到 `block-59/61` 也出現在前例 migration md，但該處是歷史敘述、非現行 GuideRef，無影響。

## 結論

H1–H8 的機械事實全部獨立驗證相符；H5／H8 的 contentHash 重算與 H9 的執行環境屬 UNVERIFIABLE，均在可接受範圍，且沒有發現阻擋性缺陷。唯一必須在提交前完成的是 H9-3 的懸空 evidence／review 參照。

VERDICT: PASS
~~~~
