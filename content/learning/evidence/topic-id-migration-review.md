# LP-210A 非作者審查原始報告（Codex CLI，三輪）

日期：2026-09-08。審查者：Codex CLI (`codex exec -c 'sandbox_permissions=["disk-full-read-access"]'`，唯讀)。
審查對象：`scripts/learning/references.py`、`scripts/learning/contracts.py`、`scripts/migrate_topic_ids.py`、
`tests/test_learning_{references,contracts}.py`、`tests/fixtures/learning/references/source-tree.json`、
`specifications/learning-platform/topic-id-migration.md`，以及 SSOT `data/topics/topics.json`。

本檔保存三輪審查者輸出的**報告本文**（已去除 codex 的工具呼叫 trace），
讓 `specifications/learning-platform/topic-id-migration.md` §8 的摘要可被追溯。
審查者三輪都未修改 repo 內任何檔案。判定依序為 FAIL → FAIL → WARN。

作者對每輪發現的處理與對照表在 `topic-id-migration.md` §8；
本檔不重述處理結果，只保存審查者原話。

---

## 第一輪（初審）

審查提示詞（節錄任務界定）：

```text
你是**非作者**的獨立審查者。任務：審查 iPAS repo 工作樹中「LP-210A：Topic stable ID 相容層與遷移盤點」這個變更包。
你不是作者，不要替作者辯護，也不要因為文件寫得完整就假設它正確。所有結論都要有 file:line 或可重算的數字當證據。

**唯讀**：不要修改、建立或刪除 repo 內任何檔案，不要 git commit/checkout/restore/clean。
你可以執行不寫入 repo 的唯讀指令（cat / sed -n / grep / jq / python3 讀檔）。
如果 sandbox 擋住某個你想做的驗證，就明說「無法驗證」，不要當成通過。

## 這個變更包宣稱做了什麼

作者宣稱：在不指派任何 canonical topic id 的前提下，先建立 stable-ID 的**相容層**與**遷移盤點**，並停在
「不寫 data/topics/topics.json、不回填 topicRefs[].id、不重算既有 review、不建立第二詞彙表」之前。

需求規格在 `specifications/learning-platform/claude-code-handoff.md` 的「LP-210A」小節（步驟 1–6 與停點）；
上位契約在 `specifications/learning-platform/data-contracts.md` §3「Topic 與章節相容性」。

## 審查對象（工作樹目前狀態，全部尚未 commit）

1. `scripts/learning/references.py` — 看 `ReferenceResolver.topic_vocabulary()` 與 `topic()`
2. `scripts/migrate_topic_ids.py` — 新增的唯讀盤點 CLI
3. `specifications/learning-platform/topic-id-migration.md` — 新增的 inventory／規則提案／碰撞報告
```

審查者報告：

**總體：FAIL，建議退回修正後再交付。** 核心盤點數字正確，現有 12 筆 name-only 引用也能解析；但 fail-closed 有可重現漏洞，盤點報告亦有漏檢與誤報。

本次全程未修改 repo。局部測試 **11＋15＝26 例通過**，`git diff --check` 通過；以下反例仍能成立，因此不能以測試全綠認定契約完整。

## 1. ID 規則自洽性：WARN

- **基本方向符合契約**：一次指派後凍結、rename 保留 ID、merge 保留存活 ID、split 不複製全部標籤，都符合 `data-contracts.md:90–94`。文件 §3 並未正式批准英文 slug；`topic-id-migration.md:97–104` 明寫是提案。
- **未決事項 B 重開了已定契約**：文件 `:106` 已要求 redirects 在同一 SSOT，`:118–119` 卻又讓人選獨立檔。上位契約 `data-contracts.md:93` 已指定「同一詞彙 SSOT 的 redirects」，這不是目前可自由裁決的選項。
- **slug 選項有預設傾向**：`:116–117` 只問英文 slug 由誰產生、是否部分指派，沒有真正列出「是否採英文 slug」的裁決。這不等於已批准，但未決清單不完整。
- **rename 與歷史 ref 相容需要明說**：`:105` 把舊名移入 aliases，`:110–111` 又禁止 alias 作 `TopicRef.name`。兩者可以共存，但代表舊 ref 不會自動因穩定 ID 而繼續有效，必須另有遷移／歷史版本策略。
- **大小寫與 redirects 唯一性未定義**：現行格式接受大小寫，resolver 精確區分 `Topic-A` 與 `topic-a`。提案應明確規定比較方式，以及 retired／redirect ID 是否同樣參與全域唯一性檢查。

## 2. 碰撞報告可重算性：WARN

我直接讀取 SSOT、重寫正規化與分組計算，並獨立遞迴走訪 `content/learning/**/*.json`，結果如下：

| 項目 | 重算結果 | 判定 |
|---|---:|---|
| 概念／parent | 181／8 | OK |
| aliases／normalise 去重 | 1583／1582 | OK |
| alias 跨 topic 歧義 | 0 組 | OK |
| normalise＋casefold 歧義 | 13 組 | OK |
| ASCII alias slug 覆蓋／碰撞 | 143／2 組 | OK |
| NFC name digest 覆蓋／碰撞 | 181／0 組 | OK |
| authored 引用 | 12 topicRef＋3 quotaKey，6 檔 | OK |
| 現有 ref ID／過期 vocabularyHash | 0／0 | OK |
| marker 命中檔案 | 25 | OK，僅代表掃描命中數 |

ASCII 的兩組確實是：

- `deep-learning`：「機器學習概論」「深度學習」
- `sentiment-analysis`：「NLP應用」「情感分析」

計算定義見 `migrate_topic_ids.py:84–183`。其中「第一個 ASCII alias」實際是**先按字串排序後的第一個**（`:154`），不是 aliases 陣列第一個。

但報告有以下缺陷：

1. **canonical-name-as-alias 有漏檢。**  
   `migrate_topic_ids.py:143` 使用 `canonical[alias] not in names`。反例：

   ```json
   [{"name":"A","aliases":["A"]},{"name":"B","aliases":["A"]}]
   ```

   實跑 `canonicalNameUsedAsAnotherTopicAlias` 回傳 `[]`，漏掉 B 借用 A 名稱；另一個 alias 歧義欄位雖會命中，不能補成這一欄正確。

2. **未量測正規化後的 canonical name 碰撞。**  
   `:101` 只算原字串重複，`:120` 又以 dict 覆蓋 normalise 後重名。這是既有 `assign_question_topics.py:106–110` 確實使用的查找方式。此次另外重算 NFC、normalise、NFKC＋casefold、normalise＋casefold，現況全部 **0 組**；但 CLI 沒有防止未來退化。

3. **未知／錯配的 authored ID 不列入 blocking。**  
   `:204–208` 只記錄有無 ID，`:254–257` 不檢查 ID 是否存在或與 name 一致。我在記憶體把 12 筆 ref 全加上 `topic-nonexistent`，報告仍是 **`blocking=false`**。

4. **「四個規則都是 approved:false」不屬實。**  
   文件 `topic-id-migration.md:125` 如此宣稱，但 `candidate_schemes()` 四筆全部**沒有 `approved` 欄位**。另外 curated-slug 的碰撞 `0` 是常數（`:173`），不是對策展 ID 實際分組的結果。

## 3. 歷史 ref 相容與 fail-closed：FAIL

**正常路徑通過：**

- 現有 12 筆 name-only ref 全部解析成功。
- 未知 ID、重複 ID、ID/name 錯配、alias 冒充 canonical name 的測例確實使用錯誤碼斷言，並非恆真：`test_learning_references.py:65–68、106–134`。
- 詞彙表 ID 為 `null`、數字、boolean、list、dict，實跑均回 `invalid_topic_id`。
- Unicode 全形 ID 被拒絕；大小寫採精確比較，沒有自動 casefold 命中。
- 正常冷啟動不會因 `input_hashes` 未填入而 KeyError：`read_json()` 先經 `read_bytes()` 寫入 hash，見 `references.py:116–131`。
- `name=None` 的 schema issue 實際落在 `/name`，沒有誤歸 `/id`；`:185` 也只篩 `/id`。

**已重現的缺陷：**

1. **尾端換行 ID 被接受，且 resolver 與 inventory 判斷不同。**  
   詞彙表與 ref 同用 `"topic-a\n"`，schema issues 為 `[]`，resolver 成功解析；inventory 卻列為 invalid。原因是 schema 的 `$` 可匹配最末換行之前，而 CLI 使用 `re.fullmatch()`。

   證據：[common.schema.json:7](/home/james/projects/ipas-test/schemas/learning/common.schema.json:7)、[references.py:184](/home/james/projects/ipas-test/scripts/learning/references.py:184)、[migrate_topic_ids.py:127](/home/james/projects/ipas-test/scripts/migrate_topic_ids.py:127)。

2. **索引與 hash 可以指向不同版本。**  
   用 mock 模擬同一路徑先讀 A、後讀 B，未寫檔：

   - 第一次解析 `A / topic-a / hash(A)`。
   - 詞彙表換成 `A / topic-b`，同一 resolver 仍接受舊 ref。
   - 再呼叫公開的 `read_bytes()` 更新 hash，竟接受 **`topic-a / hash(B)`**，回傳舊索引。

   `_topic_index` 提前返回，`_json_cache` 亦不失效，但 `input_hashes` 可獨立更新。這超出單純「固定讀取快照」的行為。證據：[references.py:112](/home/james/projects/ipas-test/scripts/learning/references.py:112)、`:122–131、172–173、198–208`。既有 stale 測試每次建立新 resolver（`test_learning_references.py:98–104`），驗不到此問題。

3. **來源形狀錯誤不是完整的結構化拒絕。**  
   實跑 `topics=null` 得 TypeError；`topics="abc"`、`topics=[null]` 得 AttributeError。`_unique()` 直接呼叫 `item.get()`（`:74–80`），外層 `validate()` 沒捕捉 AttributeError（`:430–436`）。這些沒有錯誤放行，但會崩潰。直接傳 list／dict 型 ref ID 也會 TypeError；正常 schema-first 入口則會先擋住。

**測試品質：** `test_learning_references.py:168` 的 `scheme.get("approved")` 在欄位全缺時仍通過。因此它不能證明文件所稱的「每筆明確 approved:false」。目前也缺換行、同實例快取失效、來源形狀及 inventory ID 錯配反例。

## 4. Consumer completeness：WARN

**25 個是 marker hits，不能當作 25 個真正需要遷移的讀取器。**

- **確認誤報：`QuestionModal.tsx`。**  
  唯一 conceptGraph marker 在註解 `:24`；實際用 `item.id` 查題目（`:31–45`），沒有以 topic name 查概念。文件 `topic-id-migration.md:87` 把目前 key 寫成 `name`，是錯誤判斷。

- **確認掃描漏報：`TopicHeatPanel.tsx`。**  
  文件已人工補上。它從 loader 間接讀資料（`:5、32`），並以 topic name 作開啟狀態及 React key（`:137–142`）。

- **「篩選鍵改 ID」過於籠統。**  
  `TopicHeatPanel.tsx:65–68` 的 parent 分類與文字搜尋本來就應接受顯示文字；需要遷移的是概念身分狀態／key，不能把搜尋 name 一概換成 ID。

- **SOURCE_GLOBS 非遞迴，排除了很多目錄。**  
  `migrate_topic_ids.py:53–58、226` 只掃指定目錄的直接子檔。未涵蓋其他 `scripts/**` 子目錄、`frontend/src/features/learning` 子目錄及其中 `.tsx`、其他 components 子目錄、hooks、notebooks、`.github` 等。  
  我另外用含 hidden／ignored 檔案的 `rg` 搜尋指定關鍵字；**除已人工補列的 TopicHeatPanel，沒有找到可證實因上述 glob 排除而漏掉的另一個直接讀取器**。不能把潛在盲點寫成已發現漏洞，也不能據此證明所有間接依賴完整。

- **遷移動作仍有漏項。**  
  `scripts/learning/assessment.py:262–267` 的 mapping 比對與 analysis 輸出也使用 topic 字串，文件只詳述 quota。`assign_question_topics.py:268–270、525–555` 還讀取名稱型 assignment／verification caches，四份 `generatedRebuildSurface` 沒列出這些快取的保留、轉換或失效策略。

**`?c=<name>` 宣稱屬實。**  
`ConceptsPage.tsx:81–83` 按 `c.name` 找概念，`:101–104` 寫入 query parameter，`:246` 傳入 `concept.name`。中文會經 URL 編碼，但值確實是概念名稱。

## 5. 停點與副作用：WARN

**目前狀態符合主要停點：**

- SSOT 與 `git show HEAD:data/topics/topics.json` **逐 byte 相同**。
- SHA-256 為 `bbfedffc559834396aa3093b908409472ac26626e5976b196f4192ae3c093e3b`。
- production vocabulary ID 數 **0**；authored topicRef ID 數 **0**。
- 三概念 fixture 位於 `tests/fixtures/learning/references/source-tree.json:13`，不是第二份 production 詞彙 SSOT。

**CLI 實測：**

- 不帶 `--dry-run`：exit **2**。
- 不帶 `--report`：只輸出 stdout／stderr。
- 相同來源連跑兩次：exit **0／0**，stdout byte-identical，SHA-256：
  `ff5cb422df5091d5c2691976531957ffea9cd5a4d415ef22126c6ca76cfa4fea`。
- 報告沒有執行時間戳或機器絕對路徑；`signedOff` 是來源既有 metadata。

但 **`--report` 沒有保護來源路徑**：`:304–306` 對任意指定路徑直接 `write_text()`。指定 canonical `topics.json`、content 或 review 路徑就能覆寫它，之後還印「未寫入詞彙表」（`:318`）。**本次未執行此破壞性反例**；這是程式碼可直接確認的缺口，不代表作者已覆寫 SSOT。

## 6. 總體評估：FAIL；優先修正最多三項

1. **修正 resolver 的格式與版本一致性。**  
   阻擋尾端換行；確保索引與 hash 綁定同一版本；補來源形狀與同實例反例測試。

2. **修正 inventory 的可信度。**  
   核對 authored ID/name；修 canonical-name-as-alias 漏檢；明確輸出 approval 狀態；更正 consumer 誤報，並禁止 report 覆寫來源。

3. **重寫 LP-210B 的 hash／review 遷移順序。**  
   文件 `topic-id-migration.md:188–193` 把 vocabulary 加 ID 放 B、ref 回填與 review 失效放 D。但 **B 一寫詞彙表就改變 vocabularyHash，12 筆現有 ref 立即 stale**（`references.py:198–199`）。更新 ref hash 又會涉及 authored content／review 驗證，不能等到 D 才處理。開始下一包前，必須先決定一致的遷移或版本相容方案。

## 我無法驗證的部分

- **LP-210A 前的完整工作樹差異**：多個受審檔案及整個 `content/` 尚未追蹤，沒有包開始前的基準。因此無法證明既有 review／contentHash 從未被作者改動；只能確認目前狀態及 SSOT 與 HEAD 相同。
- **完整 20/20 gate、production build、瀏覽器互動**未重跑：這些流程可能寫入 repo，與此次唯讀限制衝突。26 例局部通過不能替代完整 gate。
- 系統 `python3` 缺 `referencing`；改用既有 `.venv/bin/python` 完成 resolver 反例及測試，沒有安裝依賴。
- 未執行 `--report` 覆寫來源的破壞性驗證，也未宣稱 consumer 搜尋能證明所有動態／間接依賴完整。

---

## 第二輪（複審第一輪修正）

審查提示詞（節錄任務界定）：

```text
你是**非作者**的獨立審查者，這是**第二輪複審**。第一輪你判定 FAIL，作者宣稱已修正。
你的任務是驗證修正是否真的成立、有沒有修出新問題，以及有沒有把修正誇大成超出實際的宣稱。
不要因為作者列了對照表就相信它；逐條自己重現。

**唯讀**：不要修改／建立／刪除 repo 內任何檔案，不要 git commit/checkout/restore/clean。
可以執行不寫入 repo 的唯讀指令。系統 python3 沒有 jsonschema／referencing，需要時用 repo 的 .venv/bin/python。
如果 sandbox 擋住某個驗證，明說「無法驗證」，不要當成通過。

## 第一輪的發現與作者宣稱的修正

作者在 `specifications/learning-platform/topic-id-migration.md` §8 列了對照表。逐項驗證：

1. 尾端換行 id（`"topic-a\n"`）：宣稱 resolver 與盤點都改用同一份 schema pattern 的 `fullmatch`。
2. `_topic_index` 與 `input_hashes` 版本錯配：宣稱索引與 vocabularyHash 現在綁在同一次讀取一起回傳。
3. `canonicalNameUsedAsAnotherTopicAlias` 漏檢：宣稱條件改成 `set(owners) - {同名 topic}`。
   請用第一輪你自己的反例 `[{"name":"A","aliases":["A"]},{"name":"B","aliases":["A"]}]` 重跑。
4. authored ref 帶不存在／錯配 id 時 `blocking=false`：宣稱新增 `stableIdState`、`unresolvedStableIds` 並列入 blocking。
   請自己造一份帶假 id 的 authored ref 驗證（在 repo 之外的 temp 目錄複製最小來源樹，不要動 repo）。
5. `approved` 欄位不存在、測例恆真：宣稱欄位已加、測例改成斷言 `[False] * 4`、curated-slug 碰撞改實算。
6. `--report` 可覆寫 SSOT：宣稱報告路徑落在 repo 內就 exit 2。請實際嘗試
```

審查者報告：

**總體：FAIL。** 修正大多成立，但版本錯配仍可重現，盤點與 resolver 仍有判定差異；「首輪 findings 已全數修正」尚不成立。

本輪未修改 repo 檔案。原有測試實跑為 contracts **11/11**、references **19/19** 通過；以下反例與變異驗證均在 repo 外暫存目錄或程序記憶體中執行。

| 項目 | 判定 | 獨立驗證結果與證據 |
|---|---|---|
| 1. 尾端換行 id | **OK** | `"topic-a\n"` 被 resolver 判為 `invalid_topic_id`，盤點列入 `invalidStableIds` 且 `blocking=true`。兩邊確實使用 schema pattern 的 `fullmatch`。[references.py:91](/home/james/projects/ipas-test/scripts/learning/references.py:91)、[migrate_topic_ids.py:138](/home/james/projects/ipas-test/scripts/migrate_topic_ids.py:138)。但「所有 id 判定一致」的延伸宣稱不成立，見下文。 |
| 2. 索引與 hash 版本錯配 | **FAIL** | 原測例的「先建索引，再更新 bytes」已修好；**先 `read_json()`、再更新 bytes、最後才建索引仍錯配**。實跑接受新版 hash 搭配已不存在的舊 id。原因是 cached JSON 與可更新的 `input_hashes` 仍分開取得。[references.py:138](/home/james/projects/ipas-test/scripts/learning/references.py:138)、[references.py:190](/home/james/projects/ipas-test/scripts/learning/references.py:190)。 |
| 3. canonical name 同時為自己及別人的 alias | **OK** | 指定反例實跑得到 `[{"name":"A","aliasOf":["B"]}]`，不再漏報。[migrate_topic_ids.py:152](/home/james/projects/ipas-test/scripts/migrate_topic_ids.py:152)。但沒有有效回歸測試覆蓋，見下文。 |
| 4. authored 假 id／錯配 id | **FAIL（部分修正）** | 複製真實詞彙表至 `/tmp` 後，自造假 id 得到 `unknown`，借用另一 topic 的 id 得到 `name_mismatch`；兩者均 blocking。**但 `"id": null` 被當成欄位缺席**，回報 `stableIdState=absent`、`unresolvedStableIds=0`、`blocking=false`。這是存在但不合法的 id。[migrate_topic_ids.py:237](/home/james/projects/ipas-test/scripts/migrate_topic_ids.py:237)。 |
| 5. approved 與 curated 碰撞 | **WARN** | 四筆 `approved` 確實都是 `false`；大小寫碰撞 fixture 實算得到 `covered=2, collisions=1`。移除 `approved` 的記憶體變異會使測試出錯，證明斷言有效；但把 curated 碰撞改回常數 `0`，19 個 references 測試仍全過。[tests:168](/home/james/projects/ipas-test/tests/test_learning_references.py:168)、[migrate_topic_ids.py:200](/home/james/projects/ipas-test/scripts/migrate_topic_ids.py:200)。 |
| 6. `--report` 覆寫 repo | **OK** | 實際執行 `--dry-run --report data/topics/topics.json`，以及 `--report /home/james/projects/ipas-test/specifications/learning-platform/topic-id-migration.md`；均 **exit 2**，目標檔案 bytes 與 mtime 均未改變。[migrate_topic_ids.py:350](/home/james/projects/ipas-test/scripts/migrate_topic_ids.py:350)。 |
| 7. 遞迴掃描 | **OK** | 現況實掃 **25 檔**。另在外部最小樹建立 `scripts/nested/deeper/reader.py`，內容含 `topics.json`，確實被掃到；在 generated、fixtures、node_modules、`__pycache__` 放相同內容則均排除。這證明遞迴行為有效；不是只相信檔案總數。[migrate_topic_ids.py:264](/home/james/projects/ipas-test/scripts/migrate_topic_ids.py:264)。 |
| 8. consumer 文件補正 | **OK** | `QuestionModal` 確實只在註解提 conceptGraph，實際以題目 id 查找；文件已補 assessment mapping 與兩類名稱型快取。[QuestionModal.tsx:24](/home/james/projects/ipas-test/frontend/src/components/concepts/QuestionModal.tsx:24)、[assessment.py:262](/home/james/projects/ipas-test/scripts/learning/assessment.py:262)、[文件:87](/home/james/projects/ipas-test/specifications/learning-platform/topic-id-migration.md:87)。 |
| 9. LP-210B 原子包 | **OK** | 外部複製樹中，現有 **12/12 refs 可解析**；寫入一個 id 後全部變成 `stale_vocabulary`。保持正文不變、只更新 ref hash，也實測改變 unit `contentHash`；review 會比對 subject hash 與 dependency hashes。因此 §7 的因果鏈正確。[文件:230](/home/james/projects/ipas-test/specifications/learning-platform/topic-id-migration.md:230)、[publication.py:154](/home/james/projects/ipas-test/scripts/learning/publication.py:154)。 |
| 10. redirects 契約與大小寫孿生 | **OK** | §3 已明列 redirects 必須放同一 SSOT；casefold 重複會使 resolver 整份拒絕，相關負向測試實跑通過。[文件:137](/home/james/projects/ipas-test/specifications/learning-platform/topic-id-migration.md:137)、[references.py:201](/home/james/projects/ipas-test/scripts/learning/references.py:201)。 |

**額外發現與測試有效性**

- **FAIL：161 字 id 造成判定分歧。** 暫存詞彙表設 `id = "x" * 161`，resolver 回 `invalid_topic_id`，盤點卻回 `invalidStableIds=[]`、`blocking=false`。schema 除了 pattern，還有 `maxLength: 160`；盤點只取 pattern。因此[文件:184](/home/james/projects/ipas-test/specifications/learning-platform/topic-id-migration.md:184)所稱「兩邊判定一致」過度宣稱。[schema:7](/home/james/projects/ipas-test/schemas/learning/common.schema.json:7)

- **FAIL：版本綁定只是延後包裝，沒有保證來源一致。** 實跑順序如下，最後一步成功回傳 `topic-old`：

  ```text
  暫存詞彙表 = A / topic-old
  resolver.read_json("data/topics/topics.json")
  暫存詞彙表改成 A / topic-new
  new_hash = blob_hash(resolver.read_bytes("data/topics/topics.json"))
  resolver.topic({"name": "A", "id": "topic-old", "vocabularyHash": new_hash})
  ```

  三元組呼叫端搜尋只找到 `topic()`，已正確拆三項，**沒有發現二元組呼叫端退化**。`identifier_pattern()` 的 cache 實測正常命中；它快取的是程序內首次載入的 schema pattern，不能單靠此 helper 保證完整 schema 約束一致。

- **WARN：測試不是恆真，但有實質覆蓋缺口。** 記憶體變異結果：移除 resolver `fullmatch` 會造成 **1 failure**；移除 `approved` 會造成 **1 error**。然而令 canonical-alias 結果永遠空陣列，或令 curated 碰撞永遠為零，兩種變異均 **19/19 通過**。因此不能宣稱這兩個修正已有有效回歸保障。

**文件宣稱**

[§8:255](/home/james/projects/ipas-test/specifications/learning-platform/topic-id-migration.md:255)的版本綁定修正不完整；[開頭:4](/home/james/projects/ipas-test/specifications/learning-platform/topic-id-migration.md:4)「已全數修正」應撤回。[handoff:105](/home/james/projects/ipas-test/specifications/learning-platform/claude-code-handoff.md:105)「已全數修正並補上回歸測例」也超出實測結果。

§8 所稱「審查者確認過」屬歷史歸因，本輪只能重新確認部分事實：數字、12 筆 refs、stdout 決定性及 SSOT 與 HEAD bytes 相同均成立；不能據此證明首輪審查者曾作出那些確認。

**必須修正，最多三項**

1. 把 cached JSON 與其來源 hash 一起保存，補上「索引建立前」的錯配反例。
2. 盤點完整遵守 identifier 約束，包括長度；區分 id 欄位缺席與 `id: null`。
3. 補上能抓住 alias／curated 碰撞退化的測試，並同步收斂 migration 文件及 handoff 的完成宣稱。

**我無法驗證的部分**

- 未取得首輪完整輸出及修正前工作樹，無法確認歷史歸因，也無法把每個殘留問題確定分類為新引入或既有。
- 未執行會寫入 repo 的完整 20 項 gate、production build 與瀏覽器流程；不能確認作者的完整發布驗收宣稱。§6 列的是命令，沒有可核對的完整執行結果。
- marker 掃描不能證明所有間接 consumer 已完整列出。
- 本輪實際執行的驗證未遭 sandbox 阻擋；未執行項目均未計為通過。

---

## 第三輪（複審第二輪修正）

審查提示詞（節錄任務界定）：

```text
你是**非作者**的獨立審查者，這是**第三輪複審**。第二輪你判定 FAIL 並列出三項必須修正，
作者宣稱已修正並補上回歸測例。請驗證，並特別注意這一輪的修正動到了**共用程式碼**。

**唯讀**：不要修改／建立／刪除 repo 內任何檔案，不要 git commit/checkout/restore/clean。
系統 python3 沒有 jsonschema／referencing，需要時用 repo 的 .venv/bin/python。
sandbox 擋住的驗證請明說「無法驗證」，不要當成通過。

## 作者宣稱的修正（逐項驗證）

1. **版本綁定**：`ReferenceResolver.read_json()` 現在在解析當下把該次 bytes 的 hash 存進
   `self._json_hashes`，`topic_vocabulary()` 改用它判 freshness。請重跑你第二輪的反例序列
   （先 `read_json` → 改檔 → `read_bytes` → 才建索引），確認現在會 `stale_vocabulary`；
   也試其他你想得到的順序。
2. **identifier 完整約束**：`migrate_topic_ids.valid_identifier()` 現在同時套用 schema
   `$defs.identifier` 的 pattern 與 minLength／maxLength。請用 161 字元 id、空字串、
   尾端換行、非字串型別，確認 resolver 與盤點**判定一致**。
3. **`"id": null`**：盤點改用 `"id" in node` 判斷欄位是否存在。請確認 `{"id": null}`
   會得到 `stableIdState="unknown"`、`unresolvedStableIds=1`、`blocking=true`，與 resolver 一致。
4. **測試有效性**：作者宣稱對五項修正做過變異驗證（把修正還原成錯的實作，對應測例都會失敗）。
   請自己抽驗至少三項，不要只看作者的宣稱。特別檢查是否又出現恆真斷言。
```

審查者報告：

**總體：WARN。** 本輪三項必要修正均驗證通過，五項變異測試也確實抓到錯誤實作。未發現 `_json_hashes` 新增造成的一般讀取退化；但其他 reference 路徑仍有版本錯配風險，文件也尚未完全準確。

全程未修改、建立或刪除 repo 內檔案；測試 fixture 與獨立驗證腳本均在 `/tmp`，Python 已停用 bytecode 寫入。

| 項目 | 判定 | 實測與證據 |
|---|---|---|
| 1. 版本綁定 | **OK** | `read_json → 改檔 → read_bytes → 建索引 → 用新 hash 解析` 現在回報 `stale_vocabulary`。另驗先建索引、未刷新 bytes、只先讀 bytes 等八種組合，hash 均對應實際快取版本。[references.py:139](/home/james/projects/ipas-test/scripts/learning/references.py:139)、[references.py:195](/home/james/projects/ipas-test/scripts/learning/references.py:195) |
| 2. identifier 完整約束 | **OK** | 詞彙表 id 為 161 字元、空字串、尾端換行、`null`、數字、布林、陣列、物件時，resolver 均拒絕，盤點均列 `invalidStableIds` 且 blocking；160 字元通過。[migrate_topic_ids.py:49](/home/james/projects/ipas-test/scripts/migrate_topic_ids.py:49)、[references.py:84](/home/james/projects/ipas-test/scripts/learning/references.py:84) |
| 3. authored `"id": null` | **OK** | 實得 `stableIdState="unknown"`、`unresolvedStableIds=1`、`blocking=true`；直接呼叫 resolver 得 `unknown_topic_id`。[migrate_topic_ids.py:247](/home/james/projects/ipas-test/scripts/migrate_topic_ids.py:247) |
| 4. 測試有效性 | **OK** | 我獨立抽驗全部五項變異，均因預期斷言失敗被抓到，沒有以執行例外冒充成功攔截；相關斷言未見恆真問題。[test_learning_references.py:184](/home/james/projects/ipas-test/tests/test_learning_references.py:184) |

五項變異分別是：改回使用 `input_hashes`、移除長度限制、把 null 當缺席、還原 canonical-as-alias 漏檢條件、把 curated 碰撞數寫死為 0。

可重跑獨立驗證：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B /tmp/ipas_round3_review.py
```

**共用程式碼：OK，但保留既有風險 WARN**

- **OK：例外與快取同步。** 無效 JSON、無效編碼、缺檔均未留下單邊 `_json_cache`／`_json_hashes`；修復後重試正常。已快取有效 JSON 再讀到無效 bytes，也仍保留配對的舊資料與舊 hash。新增成本為每個 JSON 快取鍵的一筆 hash 記錄，沒有額外保存整份 bytes。[references.py:125](/home/james/projects/ipas-test/scripts/learning/references.py:125)
- **WARN：guide／question 仍可能混用版本。** 預讀舊 JSON、修改來源、呼叫 `read_bytes()`，再提供新 hash，舊快取仍可通過；新 resolver 則分別拒絕為 `guide_quote_mismatch`、`question_answer_mismatch`。guide 重現使用公開參數 `require_registry=False`。[references.py:311](/home/james/projects/ipas-test/scripts/learning/references.py:311)、[references.py:384](/home/james/projects/ipas-test/scripts/learning/references.py:384)
- **WARN：catalog／snapshot 仍使用舊 metadata。** 快取 catalog 後撤銷資源並刷新 catalog bytes，既有 resolver 的 snapshot 仍通過，新 resolver 回報 `revoked_resource`。snapshot 自身的 artifact hash 是直接由當次 bytes 計算，問題在 catalog 快取。[references.py:150](/home/james/projects/ipas-test/scripts/learning/references.py:150)、[references.py:257](/home/james/projects/ipas-test/scripts/learning/references.py:257)

上述三個重現，在記憶體中移除本輪新增的 hash bookkeeping 後仍成立，因此**不是新增 `_json_hashes` 所造成**。但受審檔案仍 untracked，無法用歷史 diff 證明首次引入時間。

其他 consumer 確有一致性假設：題目產生器拿 `input_hashes` 填 `sourceHashes`，publication 最終也只重新核對 `input_hashes`；若它已被新讀取覆蓋，該檢查無法證明先前使用的快取資料版本。[assessment.py:54](/home/james/projects/ipas-test/scripts/learning/assessment.py:54)、[publication.py:599](/home/james/projects/ipas-test/scripts/learning/publication.py:599)

**文件：WARN，並非完全相符**

1. §5「詞彙表 bytes 改變 → stale」省略了快取條件：同一 resolver 仍接受舊 hash 配舊索引，測例也明確要求此行為。另外，「詞彙表 id 與 `TopicRef.id` 永遠同一規則」過強：純 schema 驗證仍接受尾端換行，詞彙表額外的 `fullmatch` 才拒絕。[文件:181](/home/james/projects/ipas-test/specifications/learning-platform/topic-id-migration.md:181)、[文件:184](/home/james/projects/ipas-test/specifications/learning-platform/topic-id-migration.md:184)
2. §8 說完整 gate 由作者重跑並「記於 §6」，但 §6 只有指令，沒有執行結果或 evidence。[文件:293](/home/james/projects/ipas-test/specifications/learning-platform/topic-id-migration.md:293)
3. 「兩輪 findings 均已修正」就本次列出的修正而言成立；「第三輪未進行」可描述本輪開始前的狀態，**本報告完成後即不再成立**。handoff 亦須同步。[handoff:105](/home/james/projects/ipas-test/specifications/learning-platform/claude-code-handoff.md:105)

實跑 references 20、contracts 11、publication 12、assessment 9，**共 52 tests 通過**。正式盤點連跑兩次 byte-identical，數量符合文件；`topics.json` 與 HEAD bytes 相同。

待修正／追蹤，最多三項：

1. 收斂 §5 的 freshness 與 schema 等價宣稱。
2. 補正 §6／§8 的 gate evidence 描述，更新第三輪審查狀態。
3. 將 guide／question／catalog 與 `input_hashes` 的一致性問題列為獨立後續修正，不視為本輪 topic 修正退化。

**我無法驗證的部分**

- 完整 20 項 gate、production build 與瀏覽器流程：本次依唯讀要求未執行會寫入 repo 的流程，**無法驗證**，不計通過。
- 前兩輪原始審查紀錄、作者歷史變異操作及修改前工作樹：**無法驗證**；本報告僅背書本次獨立實跑結果。
- 所有間接 consumer 的完整性，以及並行／重入讀取的安全性：未完整驗證。


---

# LP-210B 的非作者審查（2026-09-09，兩輪）

同樣是 Codex CLI 唯讀 sandbox，全程未修改 repo。審查範圍由維護者限定為「機械式遷移的正確性」，
不含重做教學語意審查、不含真人 Colab L5；委派與界線見 `lp210b-review-delegation-20260909.md`。

## 第一輪（遷移正確性＋逐實體判定）

審查提示詞（節錄）：

```text
你是**非作者**的獨立審查者。作者剛完成 LP-210B：把 topic 引用從
`{name, vocabularyHash}` 改成 `{id, name}`，並替 181 個概念指派不具語意的穩定代號。
這次改動讓 13 筆既有 review 因 subject hash 改變而失效，作者要據你的判定重新開立。

**你這一輪的 scope 是「機械式遷移的正確性」，不是重做教學語意審查。**
請不要假裝重審了教學內容；也不要因為「作者說只動了 topicRefs」就相信它——自己驗。

**唯讀**：不要修改／建立／刪除 repo 內任何檔案，不要 git commit/checkout/restore/clean。
系統 python3 沒有 jsonschema／referencing，需要時用 repo 的 .venv/bin/python。
sandbox 擋住的驗證請明說「無法驗證」，不要當成通過。

## 請逐項驗證

1. **只有 topicRefs 變動（最重要）**
```

審查者報告：

**總體：FAIL。** 現有內容的機械式轉換可承接原審查結論，但 id 耐久性與 migration inventory 有可重現缺陷，LP-210B 整包尚不能通過。

全程未修改、建立或刪除 repo 內檔案；破壞性測試只在 `/tmp`，Python 均停用 bytecode 寫入。

**1. OK／WARN：五個實體指紋全部還原，但證明範圍被文件誇大**

我重新執行還原計算，結果如下：

| 實體 | 還原後符合舊 review hash |
|---|---|
| unit-imbalanced-classification | OK：`a8e8213fc629…` |
| unit-split-before-fit | OK：`947a4dffcddf…` |
| unit-threshold-decision | OK：`fb5b5b1985d5…` |
| project-imbalanced-classification | OK：`c9553d68d5ff…` |
| lab-imbalanced-classification | OK：`5bb3dc8b27d1…` |

五個目前的 `contentHash` 也都正確；還原舊 entity hashes、補回舊 vocabulary hash 後，五者的相依指紋皆與原 review 相符。

Lab 的 `sourceNotebookRef`、`notebookHash` 都包含在上述還原成功的投影內；實際 notebook 的 `notebook_content_hash()` 也符合 `ec7cfde721e6…`。證據：[lab JSON:75](/home/james/projects/ipas-test/content/learning/labs/lab-imbalanced-classification.json:75)。

但有兩項 **WARN**：

- `git ls-files content/learning/reviews` 沒有輸出，工作樹顯示 `?? content/`。因此只能確認與**現存舊 review 紀錄**相符，無法證明它們是文件宣稱的「版控中遷移前指紋」。
- `contentHash` 是 canonical JSON 投影，排除 `status`、`reviewIds`，Lab 另排除 execution／semantic review IDs。因此不能宣稱「其他每個欄位一個 byte 都没動」。正文 bytes 有涵蓋，JSON 排版及排除欄位沒有。[contracts.py:210](/home/james/projects/ipas-test/scripts/learning/contracts.py:210)

**2. OK：詞彙表純新增且帳本一對一**

實測：

- `git diff --numstat -- data/topics/topics.json`：**186 新增、0 刪除**。
- 181 個 topic 均有 id；原字串與 casefold 後各為 **181 個唯一值**。
- 181 筆帳本的 `canonicalName → id` 與詞彙表的 `name → id` 完全一致。
- 暫存樹 baseline 執行 `--apply-pairs`，輸出與目前 `topics.json` **bytes 完全相同**。

**3. FAIL：耐久性防線不完整**

在複製的最小來源樹執行 `build_topic_vocabulary.py --apply-pairs`：

| 變異 | 實際結果 |
|---|---|
| 帳本少一筆 | exit 1，符合預期 |
| 只改帳本 canonicalName，未補 previousNames | exit 1 |
| 兩筆使用完全相同 id | exit 1，符合預期 |
| **來源概念與帳本同時改名，未補 previousNames** | **exit 0，不符合要求** |
| **整份帳本缺失** | **exit 0，輸出 181 個概念、零個 id** |
| 帳本 id 僅大小寫不同／非法 `bad/id` | exit 0；後續 resolver 才拒絕 |

改名反例使用 manual addition 的「二分搜尋」：同步改為「二分搜尋改名」，`previousNames=[]`，重建仍成功。實作只做當前名稱 join，沒有驗證改名歷史。[build_topic_vocabulary.py:448](/home/james/projects/ipas-test/scripts/build_topic_vocabulary.py:448)

**最高優先修正**是缺帳本直接 `return {}` 的分支，會讓正式重建成功覆寫成無 id 詞彙表。[build_topic_vocabulary.py:454](/home/james/projects/ipas-test/scripts/build_topic_vocabulary.py:454)

**4. OK／WARN：新引用契約解決全域失效；既有來源保障仍在**

- 新增一個概念後，既有 **12/12** authored refs 仍可解析。
- 改掉被引用概念的名稱，舊 ref 得到 `unknown_topic`；錯配 id/name 亦被拒絕。[references.py:207](/home/james/projects/ipas-test/scripts/learning/references.py:207)
- schema 實測拒絕缺 `id`、缺 `name`、帶 `vocabularyHash` 三種資料。[common.schema.json:26](/home/james/projects/ipas-test/schemas/learning/common.schema.json:26)
- `dependency_hashes()` 仍收集 `hash`、`sourceHash`、`notebookHash`、`lockHash`、`artifactHash`，並納入 unit／lab／project 的實際 `contentHash`。逐項注入與來源 hash 變異測試均有效，舊 review 被拒絕。[publication.py:85](/home/james/projects/ipas-test/scripts/learning/publication.py:85)
- analysis 仍保留整份 `taxonomyHash`、mapping 的 `labelReviewHash`，兩者由 analysis subject hash 綁定。[build_learning_assessment.py:175](/home/james/projects/ipas-test/scripts/build_learning_assessment.py:175)

**WARN：** topic ref 現在只保護 id/name，不再綁定 aliases、parent 等詞彙 metadata。這符合解除整份詞彙表耦合的目的；不能再宣稱個別 ref review 固定了完整 taxonomy 快照。本次 metadata 原值未變，未見因此影響既有內容審查結論。

**5. OK：不存在的 quota 名稱被 build 擋下**

將 fixture blueprint 的 quota key 改成「不存在的名稱」，重算 blueprint hash 後執行實際 publication build check：

```text
status: blocked
code: unknown_topic
path: adapter:mock-blueprint/blueprint-fixture@1/quotas/0/key
```

證據：[references.py:519](/home/james/projects/ipas-test/scripts/learning/references.py:519)。

**6. FAIL：另有新缺陷；現有測例只涵蓋部分防線**

- **`--assign` 會重新指派已有 id 的概念。** 刪去一筆帳本、保留 `topics.json` 的既有 id，再跑 `--assign --seed 42`：`topic-a4208908` 被換成 `topic-a3b1799d`，exit 0，後續重建也 exit 0。它只查帳本名稱，未核對詞彙表既有 id；而重建錯誤訊息正會引導使用者跑這個命令。[migrate_topic_ids.py:355](/home/james/projects/ipas-test/scripts/migrate_topic_ids.py:355)
- **合法 Guide mapping 使 inventory crash。** `is_topic_ref()` 把所有 `/target/ref` 當成 TopicRef；加入 `target.kind="guide"` 的 mapping 後，`build_report()` 在 `normalise(None)` 拋出 `TypeError`。它也漏判 `/measures/0/topic`。[migrate_topic_ids.py:231](/home/james/projects/ipas-test/scripts/migrate_topic_ids.py:231)
- 帳本重建缺乏完整 identifier／casefold 驗證，與 resolver 的規則不一致，見第 3 項。

測試結果：contracts **11/11**、references **19/19**、publication **12/12** 通過。另在記憶體中移除「id/name 配對」「casefold 重複」「改名拒絕」三道檢查，既有對應測例**全部會失敗**；這些測例有效，但沒有攔住上述帳本與 Guide mapping 缺陷。

可重跑的獨立腳本，均只寫 `/tmp`：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python /tmp/lp210b-independent-check.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python /tmp/lp210b-followup-check.py
```

**逐實體判定**

以下 `approved` **僅表示本次內容遷移可承接現存原審查結論**，不表示 LP-210B 工具實作通過，也不補發未完成的審查資格。

| 實體 | 判定 | 限定依據 |
|---|---|---|
| unit-imbalanced-classification | **approved** | 舊內容及相依指紋還原一致 |
| unit-split-before-fit | **approved** | 舊內容及相依指紋還原一致 |
| unit-threshold-decision | **approved** | 舊內容及相依指紋還原一致 |
| project-imbalanced-classification | **approved** | 舊內容及相依指紋還原一致 |
| lab-imbalanced-classification | **approved** | 同上；notebook 路徑與執行內容 hash 一致 |
| analysis-imbalanced-source-examples-v1 | **approved** | 還原 7 個 mapping refs、measure refs、taxonomy／labelReview hash 後，得到原 `7fe21ecf929b…` |

實際 `build_learning_assessment.py --preview --check` 為 `checked`、`issues=[]`、`wrotePointer=false`，但仍列出失效 reviews 與未滿足的真人 L5。**不是正式發布通過。**

**我這一輪沒有驗證的部分**

- 沒有重做教學語意、題目答案、誘答品質或分析標記的人工審查。
- 沒有執行 notebook、重跑 L0–L3 或真人 Colab L5。
- 沒有驗證 notebook outputs／執行計數／所有 metadata 的歷史 bytes 不變。
- 沒有跑完整 20 項 release gate、前端 build 或瀏覽器 E2E。
- 無法從目前 Git 狀態驗證舊 review 的版控歷史，以及 hash 排除欄位的遷移前值；這些沒有當成通過。
- 本輪沒有 sandbox 擋住的驗證，也沒有建立或重新開立任何 review。

## 第二輪（複審修正＋審查 13 筆新紀錄）

審查提示詞（節錄）：

```text
你是**非作者**的獨立審查者，這是 LP-210B 的**第二輪**。第一輪你的判定是：
6 個實體的內容遷移 approved，但工具層有兩個 FAIL（§3 耐久性防線不完整、§6 新缺陷）。
作者宣稱已修正，並依你的逐實體 approved 開立了 13 筆範圍受限的重審紀錄。

**唯讀**：不要修改／建立／刪除 repo 內任何檔案，不要 git commit/checkout/restore/clean。
系統 python3 沒有 jsonschema／referencing，需要時用 repo 的 .venv/bin/python。
sandbox 擋住的驗證請明說「無法驗證」，不要當成通過。

## 一、驗證你上輪指出的缺陷是否真的修好

1. **帳本不見時重建仍 exit 0、產出零 id 詞彙表**（你標為最高優先）。
   作者宣稱：若帳本不存在但現有 topics.json 已有 id，重建改為 exit 1。請自己重現。
2. **帳本 id 大小寫孿生／非法 `bad/id` 重建不擋**。作者宣稱已在
   `apply_topic_id_assignments()` 加上與 resolver 同一條 identifier 規則與 casefold 唯一。
```

審查者報告：

**總體：FAIL。** 重建防線已修好，但 `--assign` 仍未拒絕帳本與詞彙表 id 不一致；13 筆紀錄的雜湊均正確，其中 3 筆需要修正說明或證據。

本輪未修改、建立或刪除 repo 檔案。重現使用 `/tmp`，程式變異僅在記憶體中注入。

**一、缺陷與回歸測試**

| 項目 | 判定 | 實測結果與定位 |
|---|---|---|
| 帳本遺失 | **OK** | 現有詞彙表保留 181 個 id、移除暫存帳本後，重建 exit 1，詞彙表未覆寫。[build_topic_vocabulary.py:462](/home/james/projects/ipas-test/scripts/build_topic_vocabulary.py:462) |
| 大小寫孿生／`bad/id` | **OK** | 兩種輸入均 exit 1，原詞彙表未覆寫；使用共用 `valid_identifier()` 與 casefold 檢查。[build_topic_vocabulary.py:475](/home/james/projects/ipas-test/scripts/build_topic_vocabulary.py:475) |
| 帳本漏一筆、詞彙表仍有 id | **OK** | 重建先拒絕；接著 `--assign` exit 0，顯示「指派 0、收編 1」，181 個既有 id 全部保留。[migrate_topic_ids.py:384](/home/james/projects/ipas-test/scripts/migrate_topic_ids.py:384) |
| 帳本與詞彙表 id 不一致 | **FAIL** | 將暫存帳本第一筆改為 `topic-00000000`：重建 exit 1，但 `--assign` **exit 0 並寫回不一致帳本**。原因是已知名稱直接 `continue`。[migrate_topic_ids.py:382](/home/james/projects/ipas-test/scripts/migrate_topic_ids.py:382) |
| guide mapping／analysis measures | **OK** | guide ref 不再被盤點為 TopicRef；`/measures/0/topic` 正確納入，測例通過。[migrate_topic_ids.py:216](/home/james/projects/ipas-test/scripts/migrate_topic_ids.py:216) |
| 回歸測試有效性 | **OK／WARN** | 下述四種變異確實造成 assertion failure；但 identifier 與 casefold 的個別防線仍有測試缺口。 |

實際注入並被測試抓到的四種退化：

- 移除帳本遺失防線 → `SystemExit not raised`。
- 將既有 id 改回重新鑄造 → id 相等斷言失敗。
- 將 guide mapping 納入 TopicRef → `/target/ref` 排除斷言失敗。
- 漏掉 measures → `/measures/0/topic` 存在斷言失敗。

**WARN：** 單獨移除 identifier 或 casefold 檢查，重建回歸測試仍通過。原因是測例同時觸發「既有 id 不一致」，而測試只要求任一 `SystemExit`，未證明這兩道防線各自有效。[test_resource_catalog.py:93](/home/james/projects/ipas-test/tests/test_resource_catalog.py:93)

此外，21 項 references 測試、正常精確重建測試均通過；尚未看到針對 **`--assign` 不一致帳本**的回歸測例。

**二、13 筆重審紀錄**

以下每筆的 `subject.hash` 都與實體重新計算的 `contentHash` 相符，`dependencyHashes` 也全部符合現行契約：

| 紀錄，均省略日期尾碼 `-20260909-v2` | 判定 |
|---|---|
| `review-contract-analysis-imbalanced-source-examples-v1` | **FAIL：遷移說明不實，需修正** |
| `review-contract-lab-imbalanced-classification` | **OK** |
| `review-contract-project-imbalanced-classification` | **OK** |
| `review-contract-unit-imbalanced-classification` | **OK** |
| `review-contract-unit-split-before-fit` | **OK** |
| `review-contract-unit-threshold-decision` | **OK** |
| `review-domain-project-imbalanced-classification` | **OK** |
| `review-domain-unit-imbalanced-classification` | **OK** |
| `review-domain-unit-split-before-fit` | **OK** |
| `review-domain-unit-threshold-decision` | **OK** |
| `review-execution-lab-imbalanced-classification` | **WARN：本次重跑證據不足，需修正** |
| `review-lab-semantic` | **OK，僅限承接舊 L4 結論** |
| `review-peer-d1-analysis-imbalanced-source-examples-v1` | **FAIL：遷移說明不實，需修正** |

共同檢查結果：

- **OK：** 13 筆均寫明機械式遷移範圍，且 `supersedes` 指向存在、同實體的前版。
- **OK：** 作者均為 `agent-claude-code`；六筆獨立承接使用 `agent-codex-cli / independent_model`，七筆自動檢查使用相應腳本身分。
- **OK：** `qualification.grantedBy` 均不同於 reviewer；資格文件的 `humanApproval` 是 `false`。
- **OK：** 無任何一筆宣稱人類 L5 完成。實跑 validator 也只剩 L5 未滿足，`publicationApproved: false`。

需要修正的內容：

1. **兩筆 analysis 紀錄誤套五實體證明。**  
   [contract rationale:61](/home/james/projects/ipas-test/content/learning/reviews/review-contract-analysis-imbalanced-source-examples-v1-20260909-v2.json:61) 與 [peer rationale:62](/home/james/projects/ipas-test/content/learning/reviews/review-peer-d1-analysis-imbalanced-source-examples-v1-20260909-v2.json:62) 都聲稱已確認「只有 topicRefs 改變、教學正文 bytes 不變」。但 analysis 實際變動包括 `measures[].topic`、`taxonomyHash`、`labelReviewHash`；證據文件的 TARGETS 也只有五個 authored 實體。

   我額外還原上述三類變動後，確實重現 analysis 舊 hash `7fe21ecf…`。所以**內容遷移仍可接受，但不可把未適用的證明記成我做過的確認**。應補上 analysis 專屬證明並修正兩筆 rationale。

2. **execution 紀錄沒有冒稱 Codex 跑 notebook，但「實際重跑」缺乏本次證據。**  
   reviewer 正確是腳本；然而主要執行證據仍是 [9 月 7 日紀錄](/home/james/projects/ipas-test/content/learning/evidence/evidence-lab-author-execution.json:7)，委派文件卻寫由「實際重跑的腳本」背書。[委派文件:37](/home/james/projects/ipas-test/content/learning/evidence/lp210b-review-delegation-20260909.md:37)

   本輪執行 `verify_learning_labs.py --check` 在建立 Jupyter socket 時收到 `PermissionError: Operation not permitted`，**無法驗證**。應明寫承接 9 月 7 日 L0–L3，或補入可核對的本次重跑證據；不能把本輪受阻算成成功。

3. **L4 沒有被我重新審過。**  
   [semantic rationale:93](/home/james/projects/ipas-test/content/learning/reviews/review-lab-semantic-20260909-v2.json:93) 明確否認重做語意審查，並指回原 L4 紀錄。依使用者允許的範圍受限承接，這筆可以留下；其中 `L4: pass` 只能讀作**舊結論經遷移確認後承接**，不能引用為 Codex 新做 L4。

**三、證據文件措辭**

- **OK：** 已明確承認 contentHash 是投影、`content/` 是 untracked；Git 現況符合。[證據文件:7](/home/james/projects/ipas-test/content/learning/evidence/lp210b-topic-id-migration-20260909.md:7)、[證據文件:37](/home/james/projects/ipas-test/content/learning/evidence/lp210b-topic-id-migration-20260909.md:37)
- **OK：** 五實體反推舊 hash 全相符；詞彙表確為 186 行新增、零刪除；盤點為 181 個 id、15 筆 authored refs、零 unresolved、非 blocking。
- **WARN：** 第 40 行仍寫「其餘欄位一個 byte 都沒動」，應限定為其餘**投影欄位值**；notebook「沒有被碰過」也比投影 hash 能證明的範圍更強。[證據文件:40](/home/james/projects/ipas-test/content/learning/evidence/lp210b-topic-id-migration-20260909.md:40)、[證據文件:89](/home/james/projects/ipas-test/content/learning/evidence/lp210b-topic-id-migration-20260909.md:89)

**13 筆重審紀錄是否可以留下：需修正。** 必改兩筆 analysis 與一筆 execution；其餘十筆可作範圍受限的承接紀錄保留。這不代表工具層已通過。

**我這一輪沒有驗證的部分**

- 未重做教學語意、題目答案或 L4 審查。
- Notebook 執行遭 sandbox 阻擋，**無法驗證 L0–L3 本輪執行成功**；未做真人 Colab L5。
- 未跑完整 20 項 gate、前端 build 或部署驗收。
- 無獨立歷史快照可證明 untracked 舊 review 從未改動；反推證明仍以目前保存的舊 hash 為前提。

---

# LP-210C（2026-09-14）：衍生產物與前端相容層

## 委派與工具

原定沿用 LP-210A／B 的 Codex CLI（`codex exec --sandbox read-only`）。2026-09-14 實跑時 Codex 以
`401 Unauthorized`／「refresh token was already used, please log out and sign in again」失敗（exit 1），
沒有產生任何審查內容。作者改派一個**沒有實作脈絡**的全新 Claude Code 子代理（模型 opus，角色 `independent_model`）
做唯讀審查：只給驗收條件與作者宣稱清單，不給實作過程；限制不得修改 repo、不得跑 build／E2E／`run_all.py`
（完整 gate 由作者另行實跑）。審查者回報「report 檔寫入被 harness 擋住」，因此報告本文以回覆形式交回，下面全文歸檔。
委派範圍與角色見 `lp210c-review-delegation-20260914.md`。維護者若要補一輪 Codex 審查，先 `codex login` 再以
同一份提示詞（`scratchpad/codex_review_prompt.md` 的內容已收錄於本節末）重跑。

審查者自述獨立性邊界：三個 gitignored 快取的「修改前原檔」只有作者自備的 scratchpad 備份（HEAD 無基準），
它只背書「新檔 v2→v1 與這三份備份逐字相等」；前端執行時行為（TS 是否零錯誤、瀏覽器內 `?c=` 是否真的改寫）
依指示未跑，由作者的 gate 與 `test_routes.py` 背書。

## 第一輪：判定 PASS 9／10（第 5、7、8 項帶 WARN），三項優先修正 → 已全部修正

審查者的摘要（原文）：

1. **純新增 PASS** — 自寫鍵序敏感的 strip-compare，四份產物拆掉新欄位後與 HEAD 完全相等；2985/3409/184 行 0 刪除，conceptGraph 的 2 行刪除是 `generatedAt` ＋逗號格式。
2. **id 一致 PASS** — 181 概念無缺 id/重複；1072+877 標籤、1105+880 evidence 全部對到詞彙表，無 null，逐位對應。
3. **快取無損 PASS** — 三份 v2→v1 與備份**逐字相等**；唯一 null 就是「應用場景評估」，確在 rejectedTopics。
4. **可重建 PASS（比宣稱強）** — 把 OUT_PATH patch 到 scratchpad 實跑，3 個 PYTHONHASHSEED 下兩份都**位元相同**；`test_resource_catalog.py` 20 tests OK。
5. **fail-closed PASS，但 1 格文件不符** — 18 個變異案例 17 個正確 SystemExit；`export_topic_heat.py` **不擋重複 id**（§10.5 說它會擋）。
6. **改名 PASS** — 自建改名 fixture 實跑 `backfill_ids`：帶 id 的自動改名、無 id 的走 normalise、`align_cached` id 優先，全部成立。
7. **破壞性行為 PASS（修法）／WARN（敘述）** — 實測 HEAD 553 筆→0 筆、新版 553 筆保住；但「`--limit` 一跑就洗掉」不實，`--limit --verify-all` 在新舊版都是 KeyError。
8. **前端 PASS／WARN** — 解析順序、replace 改寫、無限迴圈、key 全改 id、無殘留名稱鍵、無 AI 字眼皆確認；但 `resolveByLegacyName` 是單次 find，previousNames 可蓋過正式名稱（與文件宣稱的優先序不符），且 previousNames 全為空、零測試覆蓋。
9. **§3 C 未被代決 PASS** ｜ **10. 範圍紀律 PASS** — 09-14 異動檔清單與宣稱完全吻合；topics.json/帳本 mtime 09-09、content/ 最新 09-09。

審查者的逐項證據（原文摘錄）：

- **純新增**：`strip_compare.py` 用 `object_pairs_hook=OrderedDict` ＋ `json.dumps(sort_keys=False)` 比對，同時驗值與鍵序（比作者 `backfill_ids()` 內的 dict `!=` 更嚴）：四份 `PASS(identical after strip)`。`git diff --numstat` 2985/0、3409/0、184/0、1158/2；conceptGraph 的 2 行刪除逐行檢視為 `generatedAt` 與補逗號。
- **id 一致**：vocab 181 concepts, no-id 0, dup-ids 0；official 565 題／1072 標籤／1105 evidence、practice 580／877／880 全部帶 id、無 null；topicHeat 179 列 id mismatch 0；conceptGraph 178 概念 id mismatch 0、related id mismatch 0、id 唯一。另驗 `topicIds`／`droppedAsWrongIds` 逐位對應、`evidence.topicId` 緊接 `topic`。
- **快取無損**：`_assign_cache_practice.json` v2→v1 byte-identical=True、nullIds=1（應用場景評估）；`_verify_cache.json` True、0；`_verify_cache_practice.json` True、0。§10.3 的「18 個空白變體」實測是 18 個不同的非正式寫法共 151 次（「AI 基礎設施評估」只佔 3 次；含連字號變體），數字對、措辭讓人誤解——已改。
- **可重建**：`rebuild.py` patch `OUT_PATH` 到 scratchpad 實跑兩支 export，`PYTHONHASHSEED=0/1/12345` 三次皆 `bytes_identical=True`（156523 與 1023503 bytes）。作者的兩個 rebuild 測例用 `assertEqual(load_json(...), committed)` 是鍵序不敏感的 dict 比對，不證明位元相同——已改為比 bytes。
- **fail-closed**：18 個變異案例：attach 未知名稱（topics／evidence／droppedAsWrong）、`correct_labels` 缺 topicId／名稱不符／id 不存在（皆含 `--backfill-ids` 提示）、`topic_ids()` 無 id／重複 id、`export_topic_heat` 無 id、`export_concept_graph` 無 id／重複 id／topicHeat 缺 id、帳本不存在／canonicalName 不符、快取 kind 不符——17 個正確 SystemExit。回填自證兩條以變異實測（讓 `attach_topic_ids` 靜默少一個標籤、讓 `load_cache` 少一筆）：都 SystemExit「拒絕寫入」且檔案 bytes 未變。唯一失敗：`export_topic_heat.py` 把前兩概念 id 設相同仍寫出 179 列（F1）。
- **改名**：自建「生成式AI → 生成式人工智慧」fixture 實跑 `backfill_ids`：topics／evidence／droppedAsWrong 全部換新名、id 不變、stdout 印「依 id 更新改名」；無 id 的舊標註在改名下 SystemExit（要求人工對回）、未改名時走 normalise；`align_cached` id 優先、無 id 退回 normalise、「無 id ＋ 已改名」正確丟掉；v1 快取原字串保留、v2 快取舊名＋id → id 保住。
- **破壞性行為**：HEAD 版舊行為確實存在（`cache = {qid: align(...)}` ＋ 迴圈內整份 write_text）。同輸入同假 gateway 對比：HEAD 553 筆有效 → 0 筆（全洗成空字典，且在 SystemExit 之後仍已落盤）；NEW 553 → 553。但 `--limit 5 --verify-all` 在 HEAD 與新版都是 KeyError（`verify_all` 對 `data['assignments']` 全鍵做 `questions[k]`，而 `--limit` 已裁掉 `questions`），「`--limit` 一跑就洗掉」的敘述不實（F2）。
- **前端**：`ConceptsPage.tsx` id → name → previousNames；useEffect 在 `requested === selected.id` 時 return，無迴圈，用 `replace`；「找不到概念」；key／選取值全改 id；`ConceptGraph3D.tsx` 節點／邊／focus／hover 全用 id，`SpriteText(item.name)` 只畫標籤。grep 全 `frontend/src`：無其他 `?c=` 產生點、無殘留名稱鍵（搜尋／過濾用 name 是正確用途）。三個檔的使用者可見字串無 AI／模型字眼。
- **範圍紀律**：`find -newermt 2026-09-13`（排除 docs/）列出的 09-14 異動檔與宣稱清單完全吻合；`topics.json` mtime 09-09 且 `git diff --numstat` = `186 0`（與 §9.3 一字不差）、帳本 mtime 09-09、`content/` 最新 09-09 04:31、glossary 最新 08-10。

### 優先修正（審查者列）與作者的處置

| 編號 | 發現 | 處置（2026-09-14，均已重跑局部測試） |
|---|---|---|
| F1 | `export_topic_heat.py` 不擋重複 id，§10.5 卻說會擋；後果是 React key 重複＋`?c=` 撞號 | 補上唯一性檢查（訊息「同時屬於」），新測例 `test_exports_refuse_a_vocabulary_with_duplicate_or_missing_ids` |
| F2 | 「`--limit` 試跑一次就洗掉快取」敘述不實；`--limit --verify-all` 新舊版都是裸 KeyError | 註解與 §10.3 改寫成真正的觸發條件（標註檔題目集合比快取小＋至少跑到一批）；`verify_all` 對 `--limit` 明確 FAIL（全量驗收只跑一部分會把其他題洗成「未評」），新測例 `test_verify_all_refuses_partial_runs_and_stale_names_before_spending` |
| F3 | `resolveByLegacyName` 單次 `find(name === v \|\| previousNames.includes(v))`，兩條件同權，排前面概念的 previousNames 會蓋過排後面概念的正式名稱（§9.2 的「互換名字」情境） | 解析抽到 `frontend/src/data/conceptLookup.ts`，三段嚴格分開：id → 目前正式名稱 → previousNames |
| F4 | `previousNames` 零覆蓋：真實資料 181 筆全空，兩個 E2E case 測的是 name fallback | 新增 `tests/frontend_checks/concept_lookup_check.cjs`（用 frontend 的 typescript 轉譯 `conceptLookup.ts` 後執行，CI 的 Node 20 也能跑），以互換名字等 11 條 fixture 驗三段順序；掛在 `test_learning_frontend_static.py`（gate 第 12 項） |
| F5 | 文件引用的 `lp210c-derived-artifacts-20260914.md` 當時不存在 | 於 gate 之後補寫（本檔同目錄） |
| F6 | 回填自證與兩個 rebuild 測例是鍵序不敏感的 dict 比對 | 自證改比序列化字串（`_canonical_text`），測例改比 bytes |
| F7 | 標註名稱過期時 `align_cached()`／`persist()` 裸 KeyError，缺 `--backfill-ids` 指引 | `verify_all` 開頭先 `attach_topic_ids()`：在花 API 錢之前 FAIL 並指引 |
| F8 | 文件只說「本輪沒跑到的題原樣寫回」，沒說本輪題目上已不在該題的舊紀錄會被濾掉 | §10.3 補上 |
| — | §10.2「1,105／880 個標籤」是 evidence 數，最終有效標籤 1072／877；§10.6 沒提官方卷 `_assign_cache.json` 本來不存在 | 兩處文件已改 |

### 審查者明示無法驗證的部分

1. 快取的「原檔」基準只有作者自備的備份（gitignored，HEAD 無基準）；只背書「新檔 v2→v1 與備份逐字相等」。
2. 前端執行時行為（TS 零錯誤、瀏覽器內 `?c=` 改寫、console error）依指示未跑。
3. `previousNames` 分支在真實資料上從未被執行，只能用人造 fixture 推理（F4 的 Node 檢查就是為此加的）。
4. 證據檔 `lp210c-derived-artifacts-20260914.md` 審查時不存在，無法核對 gate 結果與備份 SHA。

**未進行第二輪。** 上表 F1–F8 的修正由作者實作並以新測例覆蓋（`test_resource_catalog` 22 tests、`test_learning_frontend_static` 的 Node 檢查、
`tsc --noEmit` 零錯誤），再重跑完整 20 項 gate；沒有再請審查者複審修正本身。若維護者要第二輪，
建議以 Codex（重新登入後）對 F1／F3／F7 的修正做變異驗證。

### 審查提示詞（全文，Codex 與替代 agent 共用；agent 版只多了「不得跑 build／E2E、報告寫到 scratchpad」的限制）

```text
你是**非作者**的獨立審查者，審查 LP-210C（topic stable id 的衍生產物與前端相容層）。
作者是另一個 agent（Claude Code）；你的判定會被歸檔，請只背書你自己實跑過的結果。

**唯讀**：不要修改／建立／刪除 repo 內任何檔案，不要 git commit/checkout/restore/clean/stash。
系統 python3 沒有 jsonschema／referencing；需要時用 repo 的 `.venv/bin/python`，或
`UV_CACHE_DIR=/tmp/ipas-uv-cache uv run python …`。sandbox 擋住的驗證請明說「無法驗證」，不要當成通過。
工作樹是未 commit 的 MVP；只有下列檔案屬於本包，其餘未追蹤／已修改檔案不在審查範圍：

程式：scripts/assign_question_topics.py、scripts/export_topic_heat.py、scripts/export_concept_graph.py、
scripts/migrate_topic_ids.py（只加 carriesStableIds）、frontend/src/pages/ConceptsPage.tsx、
frontend/src/components/concepts/ConceptGraph3D.tsx、frontend/src/components/guide/TopicHeatPanel.tsx、
frontend/src/types/index.ts（TopicHeatTopic.id）、tests/test_resource_catalog.py（新 class TopicStableIdArtifactTests）、
tests/test_routes.py（概念連結相容 case）。
產物（tracked，HEAD 有修改前版本可比）：data/topics/question_topics.json、data/topics/practice_question_topics.json、
frontend/src/generated/topicHeat.json、frontend/src/generated/conceptGraph.json。
產物（gitignored 快取）：data/topics/_assign_cache_practice.json、_verify_cache.json、_verify_cache_practice.json；
修改前原檔的唯讀備份與 SHA256SUMS 在
/tmp/claude-1000/-home-james-projects-ipas-test/e7c1a207-576b-45e0-abef-39341c75945c/scratchpad/backup/ 。
文件：specifications/learning-platform/topic-id-migration.md §10、claude-code-handoff.md 的 LP-210C 節。

## 作者宣稱（逐項驗證，能重現就自己重現）

1. **純新增**：兩份標註檔拆掉 `stableIds`／`topicIds`／`evidence[].topicId`／`droppedAsWrongIds` 後，
   與 `git show HEAD:<path>` 逐欄相等；`git diff --stat` 是 0 刪除。topicHeat.json 拆掉 `stableIds`、每列 `id` 後與 HEAD 相等；
   conceptGraph.json 拆掉 `stableIds`、`source.ledger`、每個概念的 `id`／`previousNames`、`related[].id` 後，與 HEAD 版本
   除 `generatedAt` 外相等。
2. **id 一致**：每個 id 都等於 data/topics/topics.json 同名概念的 `id`；沒有 null；`topics` 與 `topicIds` 逐位對應。
3. **快取無損**：三個 v2 快取轉回 v1 形狀（assign：鍵→[topic]；verify：鍵→{topic: verdict}）與備份原檔逐字相等；
   只有 `_assign_cache_practice.json` 的「應用場景評估」是 `topicId: null`（模型自創、已在 rejectedTopics）。
4. **可重建**：`python3 scripts/export_topic_heat.py` 與 `export_concept_graph.py` 重跑後與 committed 位元相同
   （若 sandbox 不允許寫入產物路徑，改跑 `uv run python tests/test_resource_catalog.py`，它把輸出導到 tempdir 再比對；再不行就明說無法驗證）。
5. **fail-closed**：(a) 標註名稱不在詞彙表 → `attach_topic_ids` SystemExit，不寫 null；(b) 標註 `topicId` 缺或 id／名稱與詞彙表不一致 →
   `export_concept_graph.correct_labels` SystemExit 並提示 `--backfill-ids`；(c) 詞彙表任一概念沒 id → 三支腳本拒絕；
   (d) 快取 kind 不符 → SystemExit；(e) 回填後拆掉 id 與原檔不等 → 拒絕寫入。請用變異或臨時輸入實測，不要只讀碼。
6. **改名走得通**：`canonicalise_names()`＋`attach_topic_ids()` 對帶 id 的舊標註會依 id 換成新名稱；`align_cached()` 以 id 優先對到
   這題目前的標籤。請構造一個「詞彙表改名」的小 fixture 驗證，並確認**沒有** id 的舊紀錄仍走 normalise。
7. **既有破壞性行為已修**：HEAD 版 `verify_all` 會把整份驗收快取對齊到本輪題目後整份重寫（`--limit` 會洗掉其他題）；
   新版本輪沒跑到的題原樣寫回，批內從快取已有判定起算。請比對 `git show HEAD:scripts/assign_question_topics.py` 確認舊行為
   真的存在、新行為真的如宣稱。
8. **前端相容層**（讀碼＋邏輯審查，不必開瀏覽器）：ConceptsPage 的 `?c=` 解析順序 id → 目前名稱 → previousNames；命中舊名以
   `replace` 改寫成 id；對不到顯示「找不到概念」；`useEffect` 不會無限迴圈（requested === selected.id 時停）；
   ConceptGraph3D 節點 id 改為概念 id 但標籤畫 name；TopicHeatPanel key 改 id。請 grep frontend/src 確認沒有殘留以 `concept.name`／
   `related.name`／`topic.name` 當鍵或選取值的地方（顯示用 name 是正確的）。使用者可見文案不得出現 AI／模型字眼。
9. **§3 未決事項 C 沒有被代決**：程式與文件都把相容期留給維護者，並寫明兩種裁決下各要做什麼。
10. **範圍紀律**：沒有改 data/topics/topics.json、topic_id_assignments.json、任何 id、content/learning/**、review 紀錄、glossary、
    production current.json；`git status`／`git diff --stat` 應能證明前兩者與 content/ 未被本包碰到（注意：topics.json 與 content/ 本來就
    是 LP-210B 留下的未 commit 改動，你要判斷的是本包有沒有再動它們——可比對 topic-id-migration.md §9 記載的狀態）。

## 回報格式

每一項：PASS／WARN／FAIL ＋ 你實跑的命令與關鍵輸出（精簡）。最後：
- 「我無法驗證的部分」清單（sandbox、缺基準等）。
- 「優先修正」最多三項，說明為什麼與怎麼重現。
- 「有沒有引入新缺陷」：本包改動處的任何 bug、邏輯漏洞、不一致的文件宣稱，即使不在上面十項裡也要列。
不要重寫或美化作者的說法；不確定就寫不確定。
```
