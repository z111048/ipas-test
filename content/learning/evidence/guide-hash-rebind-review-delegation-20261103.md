# 2026-11 round 4 guide 雜湊重綁：非作者審查的委派紀錄與 ds1017 原始輸出

日期：2026-11-03。這份紀錄說明誰授權了誰、審查範圍，並逐字保存審查者輸出；差異證據本身在
[`guide-hash-rebind-20261103.md`](guide-hash-rebind-20261103.md)。前例：
[`guide-hash-rebind-review-delegation-20261102.md`](guide-hash-rebind-review-delegation-20261102.md)。

## 為什麼需要重新審查

round 4 講義修正把 guideContent 的 `content`／`headings` 備援欄位改由 blocks 推導並對齊（blocks 不變），使
`中級-guide2/mid-s2c4.json` 與 `中級-guide3/mid-s3c9.json` 整檔 sha256 改變，`validate_learning_content.py --all --check`
因 `stale_guide_hash`（8）／`stale_source_hash`（5）blocked。更新 guide hash 後三個 unit 的 contentHash 改變；依 `data-contracts.md` §2 第 7 條，
三個 unit 的 domain／contract review、dependencyHashes 含 unit contentHash 的 lab（semantic／contract／execution）與 project（domain／contract）review 全部失效；
`data/resource_catalog.json` 整檔 hash 改變也使 analysis-imbalanced-source-examples-v1 的 catalogHash 與 peer／contract review 失效。

## 維護者的授權與範圍限定

維護者（repo 使用者本人）於 2026-11-03 核准 mid-s2c4、mid-s3c9 只換雜湊（block id 不變），並指定 ds1017 擔任範圍受限的非作者審查者。
資格紀錄：`content/learning/qualifications/guide-hash-rebind-20261103-review-delegation.json`。

**涵蓋**：機械式雜湊重綁——被引用 block 新舊 id 與逐欄位內容同一、quote 唯一命中、DOM anchor 未變、diff 侷限於 hash／revision／observedAt／contentHash／reviewIds／history、
舊紀錄原封保存，以及 analysis 的 catalogHash 連帶重綁。
**不涵蓋**：教學語意重審、Lab L4 重做、真人 Colab L5、題目答案重判、round 4 講義修正本身（`content`／`headings`）的 OCR 或教學正確性。

## 角色

- 作者：`agent-claude-code`
- 審查者：`agent-ds1017` = 團購網關模型 `deepseek-v4.1-flash:1017`，以
  `cshare -m deepseek-v4.1-flash:1017 -p <prompt> --allowedTools "Read,Grep,Glob,Bash(git diff:*),Bash(git show:*),Bash(shasum:*),Bash(jq:*)" --output-format json < /dev/null`
  在 repo 根目錄啟動（唯讀工具、未加 `--force`），角色 `independent_model`
- 資格授予者：`maintainer`；`humanApproval: false`——維護者授權 model reviewer，不等於維護者本人完成審查

自動化檢查不由 ds1017 背書：C1 由 `scripts/validate_learning_content.py --all --check` 實跑；
L0–L3 由作者 2026-11-03 本機實跑 `uv run --isolated --group learning-lab python scripts/verify_learning_labs.py --lab lab-imbalanced-classification --profile cpu --check`（exit 0），
紀錄 `evidence/assessment/lab-l0-l3-reverify-20261103-hash-rebind.json`（`--check` 的 stdout JSON，作者補上 `reverifiedAt`／`reverifyScope` 兩個行政欄位）。

## 執行資訊

- prompt sha256：`0e20a93f09278d27e3f1e5e0003055215d6d79026b15d33d845ac00851b71291`（51727 bytes；內容為委派說明＋H1–H9 檢查清單＋新 review 計畫＋差異證據 md 全文＋`git status --short -- content/learning data/resource_catalog.json`＋`git diff --diff-filter=M HEAD -- content/learning data/resource_catalog.json`；審查時 HEAD = `8717147`）
- 原始 JSON 輸出 sha256：`650a04f783eb91a7613f04b30829c9aea10c374a81e2cfcd244647c103088b52`
- 執行統計：`{"session_id":"a18fc5d3-ec67-47fb-b577-a5679741a44b","num_turns":102,"duration_ms":189456,"total_cost_usd":3.0271519999999996,"is_error":false,"denials":6}`
- 花費：網關 `/key/info` 的 `spend` 審查前 1.583438、審查後 1.677584，差額 **約 0.0941 美元**（以此為準）；cshare 回報的 `total_cost_usd` 3.027 是 Claude Code 依未知模型套用的估價，不是網關實際計費。
- 有 6 次權限拒絕（審查者嘗試寫暫存檔或允許清單外的指令），改用允許的唯讀指令完成，未影響結論。

## 作者對審查結果的複核

- H1–H4：作者以 Python 獨立重做（基準 `8717147` 與工作樹兩檔 `blocks` 陣列 `==`、同 id block dict `==`、quote 命中唯一、DOM anchor `4交叉驗證` 在新舊 headings 皆存在、新舊 blob hash），結果一致（差異證據「可重跑的反推證明」輸出前 7 行）。
- H5、H8 中 ds1017 列為 UNVERIFIABLE 的 contentHash：作者以 `learning.contracts.content_hash` 與 `build_learning_assessment.assessment_inputs` 反推重算，
  三個 unit、四筆 evidence 與 analysis 全部 `True`；lab／project contentHash 與基準相同；新 analysis contentHash `sha256:6506c6f3242e…` 由 `assessment_inputs` 直接算出（指令與輸出見差異證據）。
- H7：作者以 Python 比對 4 個 evidence 與 6 個 review superseded 檔與 `git show 8717147:<原路徑>` 的 bytes，10 組全部相同。
- H9 的 L0–L3 UNVERIFIABLE：作者於 2026-11-03 實跑上列指令，exit 0、L0–L3 pass。
- H9-1 屬實（審查當下的暫時懸空）：`evidence-guide-hash-rebind-20261103-{diff,delegation,lab-reverify}` 與新 review 在審查後才建立，新 review 的 `evidenceRefs` 以實際 contentHash 綁定，不再懸空。
- H9-2 屬實但不影響結論：差異證據的盤點只掃 `units`／`identity`／`labs`／`projects`、頂層 `evidence/*.json` 與 `evidence/assessment/`（已寫明範圍）；
  `block-70／148／167`、`block-77` 另外也出現在 `reviews/` 舊紀錄與 `guide-anchor-migration-20261102.md`、`guide-hash-rebind-review-delegation-20261102.md` 等歷史 md，皆非 GuideRef。
- H9-3 屬實：`lab-l0-l3-reverify-20261103-hash-rebind.json` 的 `reverifyScope` 寫「lab 封套 bytes 皆未變」不精確——lab 封套 `lab-imbalanced-classification.json` 本次改了 `reviewIds`，
  只是 contentHash 不變；notebook 與 fixture bytes 才是未變。該紀錄已送審，維持原文，更正記於此；新開立的 lab semantic／execution review 的 rationale 已改用精確敘述。

## ds1017 原始輸出（逐字）

~~~~text
# 非作者審查報告：mid-s2c4／mid-s3c9 guide 雜湊重綁（2026-11-03）

- 審查者：agent-ds1017（範圍受限、唯讀、非作者）
- 作者：agent-claude-code
- 基準：HEAD `871714764e9596ea9ca4779fdcd7573b80fed44a`（`git rev-parse HEAD`）
- 委派：`content/learning/qualifications/guide-hash-rebind-20261103-review-delegation.json`，`scopeLimit` 已讀，確認只涵蓋本次機械重綁與 analysis catalogHash 連帶重綁；不含教學語意、L4/L5、round 4 修正本身正確性。
- 方法：所有值均由我自己執行 `git show`／`git diff`／`shasum`／`jq`／Grep／Read 取得。工作區禁止寫入（`/tmp` 與 `.git/` 的暫存檔都被 sandbox 拒絕），因此 HEAD 版內容以 `git show <path> | shasum -a 256`、`git show <path> | jq … | shasum -a 256` 取得（僅串接上面列出的允許工具）。**未執行任何 Python**，故所有 `contentHash` 重算一律標 UNVERIFIABLE。

---

## H1 兩個 guide 檔的 sha256 與變動欄位 — PASS

```bash
shasum -a 256 "frontend/src/generated/guideContent/中級-guide2/mid-s2c4.json"
shasum -a 256 "frontend/src/generated/guideContent/中級-guide3/mid-s3c9.json"
git show HEAD:frontend/src/generated/guideContent/中級-guide2/mid-s2c4.json | shasum -a 256
git show HEAD:frontend/src/generated/guideContent/中級-guide3/mid-s3c9.json | shasum -a 256
```

| 檔 | HEAD（舊） | 工作樹（新） |
|---|---|---|
| mid-s2c4 | `1d1eb632f9388f88388a5b735e93ce5b7d6bf1e09f5e75b1a2db7cf4f50e7f04` | `b4559ebcceba4b0ffc0465a83ef2282bfccdc9da138507f6c8a41ad76e918e89` |
| mid-s3c9 | `8b4b3996c690ac586e065f13fda6e265168a41b739fab4e3acb934dc6e5eeaf1` | `c33286d7d5e01dd48cdd59067276f8094745e0e89498e77d55303bbfddb077a8` |

四值與證據表完全相符。

變動欄位（用 `jq -S -c` 正規化後取 sha256，避免管線外掛程式）：

```bash
git show HEAD:<p> | jq -S -c '.blocks' | shasum -a 256
jq -S -c '.blocks' <p> | shasum -a 256
git show HEAD:<p> | jq -S -c 'del(.content,.headings)' | shasum -a 256
jq -S -c 'del(.content,.headings)' <p> | shasum -a 256
```

- `blocks`：mid-s2c4 新舊皆 `edf69c39a2fd13c7…`；mid-s3c9 新舊皆 `6ff6cd0191e71770…` → **完全相同**。
- 移除 `content`、`headings` 後的其餘頂層欄位：mid-s2c4 新舊皆 `bc1e798e5c35739c…`；mid-s3c9 新舊皆 `d545cb14711680c3…` → **完全相同**。

合併兩項，兩檔確實只有 `content` 與 `headings` 變動。`content`／`headings` 本身的正確性不在本次範圍。

## H2 被引用 block 的 id 與逐欄位 — PASS

`blocks` 陣列整體已證明相等，等於逐 block 逐欄位相等。另以 `git show HEAD:<p> | jq -c '.blocks[] | select(.id=="…")'` 直接檢視舊版：

- `block-3`（mid-s2c4）：`pageIndex:56`、`bbox:[76.6,230.3,517.93,317.54]`、`text` 與工作樹一字不差。
- `block-71`：`pageIndex:154`、`bbox:[120.52,333.25,521.31,371.78]`。
- `block-149`：`pageIndex:158`、`bbox:[102.16,225.7,518.23,264.14]`。
- `block-168`：`pageIndex:159`、`bbox:[76.6,474.72,161.17,489.73]`、`anchor:"4交叉驗證"`。

新舊 `id`、`bbox`、`pageIndex`、`anchor`（以及 `depth`／`marker`／`kind`／`source`／`nodeId`）全部相同。**PASS**。

## H3 quote 唯一命中、pageIndex、DOM anchor — PASS

```bash
jq -c '[.blocks[] | select((((.text // "") + " " + (.title // "")) | contains("<quote>"))) | .id]' <file>
```

| quote | 新檔命中 | block pageIndex | evidence pageIndexes |
|---|---|---|---|
| 若資料本身存在缺漏、錯誤、格式不一致等問題，將直接導致模型預測失真 | `["block-3"]` | 56 | 56 |
| 95%樣本為負類時，即使模型全預測為負，準確率仍高達95% | `["block-71"]` | 154 | 154 |
| 類別不平衡處理與評估策略 | `["block-149"]` | 158 | 158 |
| 4. 交叉驗證 | `["block-168"]` | 159 | 159 |

- 四個 quote 都恰好唯一命中同一個 id。
- `block-168.anchor == "4交叉驗證"`；`jq -c '.headings'` 新版仍有 `{"id":"4交叉驗證","level":3,"title":"4. 交叉驗證"}`；HEAD 版 `headings` 同樣有它。
- `grep -n '"anchor"\s*:' content/learning` 只出現 `null` 與 `4交叉驗證`，沒有其他 DOM anchor。**PASS**。

## H4 現行引用盤點 — PASS

```bash
grep -rHoE 'block-[0-9]+' content/learning   # Grep 工具，output_mode=content, -o
grep -n '模型訓練評估與驗證|53模型訓練評估與驗證' content/learning
grep -n '4交叉驗證' content/learning
```

排除 `reviews/` 與 `superseded/` 後，現行 GuideRef 只有四個（`block-3`、`71`、`149`、`168`），分布於：

- `units/unit-split-before-fit.json`（block-3）、`unit-imbalanced-classification.json`（71、149）、`unit-threshold-decision.json`（168）
- `identity/guide-anchors.json`（current 4 筆）
- `evidence/evidence-mid-s2c4-data-quality.json`（3）、`…accuracy-imbalance.json`（71）、`…imbalance-strategies.json`（149）、`…cross-validation.json`（168）

- `block-70/148/167` 只出現在 `guide-anchors.json` 的 `history`（`263987fb…` 版）。
- `block-77` 只出現在 `evidence/assessment/recall-formula-direct-view.md`（敘述）。
- `模型訓練評估與驗證` 與 `53模型訓練評估與驗證` 在 `content/learning` 只出現於本次證據 md，**沒有任何現行紀錄引用被改名的 heading id**。
- 以 17 個 heading id 的聯集 grep，也只命中證據 md，未命中任何 unit／lab／project／evidence JSON。**PASS**。

## H5 變更範圍 — PASS（contentHash 重算 UNVERIFIABLE）

```bash
git diff --numstat HEAD -- content/learning data/resource_catalog.json
git diff HEAD -- content/learning/{units,labs,projects,evidence,identity}/…
git status --short -- content/learning/units
```

- 4 筆 evidence：`3 3`；guide-anchors：`28 8`；lab：`3 3`；project：`2 2`；3 個 unit 共 `9 9`／`8 8`／`6 6`；catalog：`4 4`；6 個 review rename：`0 0`。
- evidence diff 只改：`revision`（2→3、3→4×3）、`contentHash`、`guideRef.sourceHash`、`observedAt`（→`2026-11-03T00:00:00Z`）；`blockIds`、`pageIndexes`、`quote`、`anchor`、`locator`、`claim`、`excerpt`、`artifactRef`、`artifactHash` 皆未動。
- unit diff 只改：`contentHash`、`reviewIds`、`dependencies[0].revision/hash`、`guideRefs[*].sourceHash`、claim `sourceRefs` 的 `revision/hash`；`revision` 仍為 1。
- lab／project diff 只有 `reviewIds`；`contentHash` 是 context 行，未變（`sha256:6aeb2aeb2702…`、`sha256:c333d0600d3c…`）。
- `git status --short -- content/learning/units` 只列 3 個 `.json`，3 份 unit 正文 `.md` 未修改。
- PNG 實檔 hash：

```bash
shasum -a 256 frontend/public/pdf-assets/中級/guide2/page_056/page.png … page_159/page.png
```

`297a74ad8c96…`、`f81f786305e8…`、`77d7d1a53e39…`、`b9aba37fc487…`，與四筆 evidence 的 `artifactHash` 完全相同。

- 所有 `contentHash` 是否以 `learning.contracts.content_hash` 正確重算：**UNVERIFIABLE**（需 Python）。就 diff 而言，新值與證據表所列一致。

## H6 guide-anchors.json history 追加 — PASS

```bash
git diff HEAD -- content/learning/identity/guide-anchors.json
git show HEAD:content/learning/identity/guide-anchors.json | jq -S -c '.anchors[] | {anchorId, history}'
```

- 四筆 anchor 的 `current.sourceHash` 換新；`blockIds`、`pageIndexes`、`quote`、`anchor`、`fallbackRoute` 等未動。
- `history` 既有條目原樣保留：mid-s3c9 三筆各保留 2 筆、mid-s2c4 保留 1 筆；並各追加一筆 HEAD 的 current：

```
{s3c9 三筆} sourceHash sha256:8b4b3996…, blockIds [71]/[149]/[168], nodeId mid-s3c9
{s2c4}      sourceHash sha256:1d1eb632…, blockIds [3], nodeId mid-s2c4
```

- 與 `schemas/learning/identity.schema.json` 的 `guideHistory`（required：`sourceHash`、`blockIds`、`nodeId`；`additionalProperties:false`）完全相符。
- `evidenceIds` 皆在前一版陣列尾端追加 `evidence-guide-hash-rebind-20261103-diff`。**PASS**（該 id 尚無檔案，見 H9）。

## H7 superseded 逐 byte 與 evidenceRefs — PASS

四筆 evidence（`git show HEAD:<舊路徑> | shasum -a 256` vs `shasum -a 256 <superseded 路徑>`）：

| 檔 | 兩邊 sha256 |
|---|---|
| evidence-mid-s2c4-data-quality（HEAD → `.r2.json`） | `ebada1b993a7c5d6…` |
| evidence-mid-s3c9-accuracy-imbalance（→ `.r3.json`） | `56d2f1a01ea61e71…` |
| evidence-mid-s3c9-imbalance-strategies（→ `.r3.json`） | `e214da99dd43db39…` |
| evidence-mid-s3c9-cross-validation（→ `.r3.json`） | `1a005e5d04879476…` |

四對完全相同（逐 byte）。

```bash
git diff HEAD -M --summary -- content/learning/reviews
```

六筆 review 全部顯示 `rename … (100%)`，numstat 均為 `0 0`。

被移走的 unit review，其 `evidenceRefs`／`subject` 正是被取代的版本：

- `review-domain/contract-unit-split-before-fit-20261102-v3`：subject `sha256:f314aa80b30f…`；`evidence-mid-s2c4-data-quality` **revision 2**、hash `sha256:dc1c9b076e45…`。
- `review-…-unit-imbalanced-classification-20261102-v4`：subject `sha256:9cad43d95be4…`；accuracy **r3** `00e25fdd49e9…`、imbalance-strategies **r3** `daa7269d006d…`。
- `review-…-unit-threshold-decision-20261102-v4`：subject `sha256:73b75b70c1ac…`；cross-validation **r3** `235ff00644fb…`。

全部與上方 superseded evidence 的舊 `contentHash` 一致。**PASS**。

## H8 resource_catalog 與 analysis catalogHash — PASS（新 analysis contentHash UNVERIFIABLE）

```bash
shasum -a 256 data/resource_catalog.json
git show HEAD:data/resource_catalog.json | shasum -a 256
git diff HEAD -- data/resource_catalog.json
```

- HEAD：`1912806b845df306067fcf39ec1717889cab8fc862888f7cf10a490e8b812aa9`
- 工作樹：`55fbefd9e363eff7356322c0498a675e31f8ef67d159ae20add7c62d9510555d`

與證據表新舊值相符。diff 只有兩個 entry（`learning-guide-middle-2`、`learning-guide-middle-3`）各改 `version`／`sha256`，共 `4 4` 行。

catalogHash 定義（實讀程式）：

- `scripts/learning/references.py:129-135`：`read_bytes()` 對每個讀入檔案設 `self.input_hashes[relative] = blob_hash(result)`。
- `scripts/learning/contracts.py:197-200`：`blob_hash` = `"sha256:" + sha256(bytes).hexdigest()`。
- `scripts/build_learning_assessment.py:220-221`：`"catalogHash": resolver.input_hashes["data/resource_catalog.json"]`。

→ `catalogHash` 確為 `data/resource_catalog.json` 整檔 blob hash。

- 舊 analysis `subject.hash`：v4 review 為 `sha256:a0fec784b20b1e5c…`，與證據表一致。
- 新分析 `contentHash`（證據表 `6506c6f3242e…`）需實際跑 `build_learning_assessment` 才能重算：**UNVERIFIABLE**。

## H9 其他發現 — PASS（無阻擋性錯誤；3 項精確度／待辦觀察）

1. **懸空引用（已知、待辦）**：`guide-anchors.json` 的 `evidenceIds` 已指向 `evidence-guide-hash-rebind-20261103-diff`，但 `content/learning/evidence/` 下只有 `guide-hash-rebind-20261103.md` 與 `assessment/lab-l0-l3-reverify-20261103-hash-rebind.json`；三個新 evidence JSON（diff／delegation／lab-reverify）尚未建立。units／lab／project 的 `reviewIds` 指向的 `*-20261103-v4/v5` review 也都不存在（`Glob content/learning/reviews/*20261103*` → 無檔）。這與任務說明的「審查後由作者建立」一致，**不是本次重綁的錯誤，但 commit 前必須補齊**，否則現行樹不自洽。
2. **證據文件措辭不精確（非阻擋）**：md 說 `block-70／148／167 只出現在 anchor history`，實際上也出現在 `reviews/`（舊 v3）與 `guide-anchor-migration-20261102.md` 敘述；`block-77 只出現在 assessment/recall-formula-direct-view.md`，實際上也出現在 `guide-hash-rebind-review-delegation-20261102.md:110`。這些都不是 GuideRef，結論不受影響。
3. **「lab 封套 bytes 皆未變」不精確（非阻擋）**：依 repo 既有用法「封套」指 `content/learning/labs/lab-imbalanced-classification.json`，該檔本次確實改了 `reviewIds`（3 行）；只是 `contentHash` 不變。證據 md 另一段「lab／project 只更新 reviewIds、contentHash 不變」才是精確描述。

**誠實性正面證據**：

- `lab-l0-l3-reverify-20261103-hash-rebind.json` 的 `inputs` 三值，我以 `shasum -a 256` 實測筆記本／fixture／split manifest，分別為 `e2715354…`、`c6db9b75…`、`92a43c16…`，與紀錄完全相同。
- 該紀錄的 `environment` 是 `scripts/verify_learning_labs.py:283-287` 由 `platform.python_version()`／`importlib.metadata` 產生的；`.python-version` 為 `3.11`，記錄的 `3.11.17` 與之一致；與 2026-09-09 舊紀錄的 `3.11.13` 不同，且 11-02→11-03 的 diff 只有秒數、`reverifiedAt`、`reverifyScope` 改變，符合「真的重跑過」而非只改日期。
- 紀錄明確寫 `automatedScope: "L0-L3 implementation evidence; not an independent publication review"`、`publicationGate.status: "blocked"`、L4／L5 `not_run`，沒有宣稱做過 L4 或真人 Colab L5。
- `--check` 依 `verify_learning_labs.py:304-306` 只驗證、不寫檔，`reverifiedAt`／`reverifyScope` 也不在腳本輸出中；因此該 JSON 是由作者把 `--check` 的 stdout 轉存並補上兩個行政欄位。這點無法由工具驗證，但與檔案內容一致，**不構成不實**。
- L0–L3 是否真的 exit 0／pass、反推腳本是否能跑出相同指紋：**UNVERIFIABLE**（需執行 Python）。

---

## 總結

H1–H8 的機械式重綁在可驗證範圍內完全正確：四個被引用 block 的 id、quote、pageIndex、bbox、DOM anchor 與整份 `blocks` 陣列皆未變；只有 `content`／`headings` 兩個頂層欄位變動；guide hash、evidence revision/observedAt、contentHash、reviewIds、anchor history 與 catalog 兩列的改動都落在授權範圍；superseded 檔逐 byte 未變；catalogHash 確為整檔 blob hash。無法由唯讀工具驗證的僅有各 `contentHash` 的重算值與 L0–L3 實際執行，已逐項標為 UNVERIFIABLE。H9 的三項觀察（pending 的 evidence/review 檔、兩處措辭不精確）不影響本次重綁的正確性，但 commit 前應補齊懸空引用。

VERDICT: PASS
~~~~
