# LP-210A／B／C：Topic stable ID 的相容層、盤點、遷移與衍生產物

日期：2026-09-07 起；LP-210B 於 2026-09-09 完成；LP-210C 於 2026-09-14 完成。

**目前狀態：遷移已完成，衍生產物與前端也已改用 id。** 181 個不具語意的穩定代號已寫入 SSOT，
`TopicRef` 改成 `{id, name}`，整份詞彙表的 hash 退出契約，13 筆因此失效的 review 已以新 hash 重新開立。
候選驗證 `validated`／144 entities／issues 0，`unmetReviews` 只剩既有的真人 Colab L5。
LP-210C 把兩份標註、三個名稱型快取、`topicHeat.json`、`conceptGraph.json` 改成同時帶 id，
前端 `/concepts?c=` 以 id 為鍵並保留舊中文名連結的相容層。
**LP-210B 的設計見 [§9](#9-lp-210b實際落地的設計與經過2026-09-09)，LP-210C 見 [§10](#10-lp-210c衍生產物與前端相容層2026-09-14)。**
**§3 未決事項 C 已於 2026-09-14 裁決：舊名連結只保留一段過渡期**，到期日 2026-12-31（§10.4）。

§1–§8 是 LP-210A（相容層與盤點）當時的紀錄，保留作為決策過程的稽核軌跡。
其中 §3 的「未決事項」已由維護者裁決、§7 的下一包順序已被執行，
**閱讀那兩節時請以 §9 為準**。

---

以下 §1–§8 為 LP-210A 原文。這是 [`implementation-plan.md`](implementation-plan.md) P2 的
LP-210 第一小包。目標不是完成遷移，
而是讓遷移**可被決定**：詞彙表現況、名稱在哪些地方已經是主鍵、候選 id 規則各自會撞在哪、
以及哪些 consumer 必須跟著改。id 指派本身是一次性策展，依
[`data-contracts.md`](data-contracts.md) §3「不可依排序編號或每次由當前名稱重算」，
必須由維護者裁決並經非作者審查，因此本包不寫任何 id。

## 這一包做了什麼／沒做什麼

| 已交付 | 明確不做 |
|---|---|
| resolver 的 stable-id 相容層與 fail-closed 規則（`scripts/learning/references.py`） | 不改 `data/topics/topics.json`，不指派任何 canonical id |
| 正／負向 fixture 與測例（`tests/test_learning_references.py`、`tests/test_learning_contracts.py`） | 不批量回填 `topicRefs[].id`，不重算既有 contentHash／review |
| 唯讀盤點 CLI（`scripts/migrate_topic_ids.py --dry-run --report`） | 不建立第二份詞彙表，不改 `schemas/learning/common.schema.json` |
| 本文件：consumer inventory、規則提案、碰撞報告 | 不重跑 OCR／Vision／付費模型，不動 production `current.json` |

`TopicRef.id` 在 MVP 就已經是 optional 欄位（`common.schema.json` 的 `topicRef`、
`frontend/src/features/learning/types.ts`），所以本包沒有新增 schema 欄位，只補上**詞彙表側**
schema 表達不到的規則（id 全域唯一）與負向驗證。

## 1. 現況：display name 就是主鍵

以 `data/topics/topics.json`（`sha256:bbfedffc559834396aa3093b908409472ac26626e5976b196f4192ae3c093e3b`，
`status=signed-off`、`signedOff=2026-08-31`）為準：

| 項目 | 數值 |
|---|---|
| canonical topics | 181（8 個 parent 分類） |
| 重複 canonical name | 0 |
| 已有 stable id | **0** |
| aliases | 1,583（依 `build_topic_vocabulary.normalise` 去重後 1,582） |
| authored 內容中的 topic 引用 | 15（12 個 `TopicRef` ＋ 3 個 topic 配額 key），全部 canonical、vocabularyHash 皆為現行值 |
| 以 marker 掃到的 consumer 檔案 | 25 |

15 筆 authored 引用分布在 6 個檔案：3 個 unit、1 個 project、1 個 lab 的 `topicRefs`，
以及 `content/learning/mock-blueprints/diagnostic-imbalanced-classification-v1.json` 的
`quotas[].key`（`dimension="topic"`）。所有引用目前都靠中文名稱命中。

## 2. Consumer inventory

marker 由 `migrate_topic_ids.py` 掃描產生（比對檔名而非完整路徑，才抓得到用 `Path` 組路徑的讀取器）；
「遷移動作」欄是本文件的判斷，不在機器報告裡。

掃描範圍：`scripts/`、`tests/`、`schemas/`、`frontend/src/`、`notebooks/` **遞迴**取
`.py/.ts/.tsx/.json/.ipynb`，排除 `generated`、`fixtures`、`node_modules`、`__pycache__`。
authored 內容另由 `authoredReferences` 逐筆列出，不混進 consumer 計數。

marker 掃描仍有兩個殘餘限制，兩者本節都已用人工讀碼補正：

- **誤報**：marker 只是字面命中，可能落在註解。`QuestionModal.tsx` 就是這種情形——
  它唯一的 `conceptGraph` 字樣在註解裡，實際是用 `item.id`／`examKey` 去題庫查題（`:31–45`），
  不以 topic name 查概念，因此**不是**需要遷移的 topic consumer。
- **漏報**：抓不到「透過 import 間接吃到 topic 名稱」的檔案。`TopicHeatPanel.tsx`
  是人工補上的（從 `data/topicHeat.ts` 取資料，檔內沒有任何 marker 字面）。

掃描命中 25 個檔案，其中 4 個是測試檔
（`tests/test_learning_{references,publication,assessment}.py`、`tests/test_resource_catalog.py`），
跟著各自被測的 consumer 一起改，不另列；其餘 21 個列在下面三張表。

### 2.1 契約與 resolver（stable id 的唯一入口）

| 檔案 | 讀什麼 | 目前 key | 遷移動作 |
|---|---|---|---|
| `schemas/learning/common.schema.json` | `topicRef` 定義 | `name` 必填、`id` optional | 不改；`id` 轉必填是 LP-210C 以後的事 |
| `scripts/learning/references.py` | 詞彙表 | `name`，`id` 可選核對 | **已改**：`topic_vocabulary()` 建 name／id 雙索引並 fail closed |
| `scripts/learning/contracts.py` | `topic-ref` schema target | — | 不改；詞彙表 id 沿用同一 identifier 規則驗證 |
| `schemas/learning/{content,analysis,review}.schema.json` | 帶 `topicRef` 的實體 | 同上 | 不改 |
| `schemas/learning/mock.schema.json` | quota 定義 | `dimension="topic"` 時 `key` 是自由字串 | 遷移後 `key` 應收斂為 topic id；本包不改 |
| `scripts/learning/assessment.py` | blueprint quota 比對標註 | `quota["key"] in annotation["topics"]` | 跟隨 quota key 一起改，兩邊必須同時切換 |
| `frontend/src/features/learning/types.ts` | `TopicRef` 型別 | `name`，`id?` | 已相容，不改 |

### 2.2 標註與衍生產物（遷移時要重建，不是手改）

| 檔案 | 讀什麼 | 目前 key | 遷移動作 |
|---|---|---|---|
| `scripts/build_topic_vocabulary.py` | 產生／合併詞彙表本身 | `name` 排序與 merge 鍵 | **必須保留既有 id**：`apply_merge_pairs()` 目前每次由 draft 重建，合併時要讓存活 topic 保留 id、被併掉的 id 進 redirects |
| `scripts/assign_question_topics.py` | 詞彙表→官方／練習題標註 | `normalise(name)` 與 alias | 輸出改為同時寫 `topicId`，保留 `topic` 名稱欄位供舊讀取器 |
| `scripts/export_topic_heat.py` | 標註＋詞彙表→`topicHeat.json` | `vocab[name]` | 產物加 `id` 欄位；`name` 保留 |
| `scripts/export_concept_graph.py` | 標註＋heat＋詞彙表→`conceptGraph.json` | `topics[name]`、共現邊以 name 配對 | 同上；共現邊改以 id 配對後 name 只作顯示 |
| `scripts/build_glossary.py` | heat＋詞彙表 alias | `topic['name']` → aliases | 名詞解釋以 id 對齊，避免改名後對不上 |
| `scripts/build_learning_assessment.py` | 詞彙表 hash＋題目→topic mapping | 硬寫的中文名稱 | 產生 mapping 時帶 id |
| `scripts/learning/assessment.py` | blueprint quota 比對標註、`topic_measures` 統計 | `mapping["topic"]`、`quota["key"]` 都是字串 | quota key 與 mapping 必須**同時**改成 id，否則統計會靜默 0 命中（`assessment.py:262–267`） |
| `data/topics/_assign_cache*.json`、`_verify_cache*.json` | `assign_question_topics.py` 的模型指派／評分快取 | 題號 → topic **名稱** | 遷移時必須決定保留／轉換／失效；改名後 `align()`（`:263–270`）只靠 normalise 對齊，會靜默錯位 |
| `scripts/verify_generated_images.py` | 詞彙表名稱當中文字形檢查詞 | `name` | 不需遷移（本來就只要顯示名） |
| `scripts/export_notebooklm_pack.py` | `topicHeat.json` | `topic['name']` | 跟隨 heat 產物；不需自行查詞彙表 |

衍生產物本身（`frontend/src/generated/topicHeat.json`、`frontend/src/generated/conceptGraph.json`、
`data/topics/question_topics.json`、`data/topics/practice_question_topics.json`）是 build artifacts，
遷移後**重建**而不是手改；`migrate_topic_ids.py` 的 `generatedRebuildSurface` 會列出這四份是否存在。

### 2.3 前端（display name 目前是對外契約的一部分）

| 檔案 | 讀什麼 | 目前 key | 遷移動作 |
|---|---|---|---|
| `frontend/src/pages/ConceptsPage.tsx` | `conceptGraph.json` | `concept.name`，且**寫進網址 `?c=<中文名>`** | 需相容層：新網址用 id，舊 `?c=<name>` 仍要能解析到同一概念 |
| ~~`frontend/src/components/concepts/QuestionModal.tsx`~~（marker 誤報） | 只在註解提到 conceptGraph | 用 `item.id`／`examKey` 查題庫 | **不需遷移**；它渲染的是題目引用，不是 topic |
| `frontend/src/data/topicHeat.ts`、`frontend/src/types/index.ts` | `topicHeat.json` | `name` | 型別加 optional `id`；顯示仍用 name |
| `frontend/src/components/guide/TopicHeatPanel.tsx`（掃描漏、人工補） | 經 `data/topicHeat.ts` | `topic.name`、`topic.parent` 篩選 | 跟隨 heat 型別；篩選鍵改 id、顯示仍用 name |

`?c=<中文名>` 是這次盤點最容易被漏掉的一項：概念改名會**直接讓既有分享連結失效**，
而不是只影響內部資料。這條與 `implementation-plan.md`「關閉新入口不得停止既有 route」同一性質，
必須在 LP-210C 之前決定相容策略。

## 3. ID 規則提案（待維護者裁決）

以下是提案，不是已核准的規則。審查者應逐條裁決。

1. **格式**：`^[A-Za-z0-9][A-Za-z0-9._:-]*$`、長度 ≤160，即 `common.schema.json` 的 `identifier`。
   建議實際採 `topic-<英文小寫連字號 slug>`（例：`topic-data-leakage`）。
   不使用中文字元，理由是 id 會進 URL、檔名與 quota key。
2. **唯一性**：id 在整份詞彙表全域唯一，且 **casefold 後仍唯一**（`topic-ML` 與 `topic-ml`
   算同一個）——id 會進 URL 與檔名，大小寫孿生在不分大小寫的檔案系統上會撞在一起，
   §4 的 13 組別名衝突就是同一類問題。重複或格式不合時，**整份詞彙表拒絕解析**（不是只擋該筆），
   避免半套遷移期間 ref 靜默命中錯的 topic。
   格式比對一律 `fullmatch`：JSON Schema 的 `pattern` 在 Python 走 `re.search`，
   而 `$` 也吃得下尾端換行，`"topic-a\n"` 會通過 schema 卻是另一個字串。
3. **不可重算**：id 一次指派後即凍結。禁止依排序編號、禁止由當前名稱雜湊重算（見 §4 的量測）。
4. **改名**：只改 `name`，id 不動，舊 name 進 `aliases`。
5. **合併**：存活 topic 保留自己的 id；被併掉的 id 進同一份 SSOT 的 redirects，不得重用於別的概念。
6. **拆分**：新概念取新 id；舊 id 保留給語意最接近的那一個，**不得自動把舊標籤複製給所有新 id**，
   受影響的標註要重新審。
7. **retired**：id 不重用。
8. **ref 相容**：舊 ref 可只帶 `name`；帶 `id` 的 ref 必須同時對上同一筆的 canonical name。
   alias 永遠不能當 `TopicRef.name`。
9. **顯示**：UI 一律顯示 `name`；id 只做連結與統計鍵。

### 未決事項（需要審查者裁決，本包不預設答案）

- **A. id 用什麼字面**：先決是「是否採英文 slug」——也可以是不具語意的穩定代號（如 `topic-0a3f`）。
  若採英文 slug，181 個中文名稱沒有離線可決定的英譯，要 (a) 維護者逐筆策展、
  (b) 以模型產草案再逐筆人工核可、還是 (c) 先只給熱度前 N 名指派 id？本包不呼叫付費模型，故未產生任何 slug。
- **B. redirects 的欄位形狀**：放同一份 SSOT 已由 `data-contracts.md` §3 定案（「同一詞彙 SSOT 的
  redirects 指向存活 id」），不是可選項；待決的是欄位名稱與結構，以及 **retired／redirect 的舊 id
  是否也佔用全域唯一性**（本包的 resolver 目前只檢查 `topics[].id`）。
- **C. `?c=` 網址相容策略**：永久接受舊中文名、或只接受一段過渡期？
- **D. 分階段強制**：哪一個 consumer 先要求 `id` 必填？建議順序見 §7。

## 4. 碰撞報告（機器量測）

`migrate_topic_ids.py` 對每個候選規則量測覆蓋率與碰撞，每筆都帶 `"approved": false` 欄位——
本包沒有核准任何一個規則。四個規則的碰撞數都是**實算**（`curated-slug` 算目前已指派的 id，
所以現在是 0/0；不是寫死的常數）。

| 規則 | 覆蓋 | 碰撞 | 離線可決定 | 改名後仍有效 | 合乎 data-contracts §3 |
|---|---|---|---|---|---|
| `curated-slug`（策展英文 slug） | 0/181 | 0 | ✗（需策展） | ✓ | ✓ |
| `ascii-alias-slug`（取第一個純 ASCII 別名） | 143/181 | 2 | ✓ | ✗ | ✗ |
| `name-digest`（`sha256(name)[:12]`） | 181/181 | 0 | ✓ | ✗ | ✗ |
| `parent-ordinal`（依排序編號） | 181/181 | 0 | ✓ | ✗ | ✗ |

- `ascii-alias-slug` 的 2 組碰撞：`deep-learning` ←「機器學習概論」「深度學習」；
  `sentiment-analysis` ←「NLP應用」「情感分析」。別名是自由文字，會隨 merge 改變，不能當永久主鍵。
- `name-digest` 目前 0 碰撞，但只要有人重跑就會跟著改名飄移，正是 §3 第 3 條要禁止的。
- alias 歧義：以標註管線自己的 `normalise` 規則看是 **0** 組（與 `question_topics.json` 的
  `aliasQuality.canonicalNameUsedAsAlias=0` 一致）；但**再套 casefold 之後有 13 組**跨 topic 撞名，
  例如 `precision`、`recall` 同時是「模型評估」與「評估指標」的別名。任何會 lowercase 的 slug 規則
  都會踩到這 13 組，所以「用別名產 slug」不可行。

## 5. 已實作的 fail-closed 行為

`ReferenceResolver.topic_vocabulary()` 先驗詞彙表，再由 `topic()` 解析單筆 ref：

| 情境 | 錯誤碼 | 測例 |
|---|---|---|
| 舊 ref 只帶 `name`（不論該 topic 有無 id） | 通過 | `test_topic_stable_id_is_optional_but_never_ambiguous` |
| `id + name` 同時對上同一筆 | 通過 | 同上 |
| `id` 指向另一個 topic | `stale_topic_id` | 同上 |
| `id` 借給尚未指派 id 的 topic | `stale_topic_id` | 同上 |
| `id` 不在詞彙表 | `unknown_topic_id` | 同上 |
| 以 alias 當 `name`（即使 id 正確） | `unknown_topic` | 同上 |
| 詞彙表有重複 id | `ambiguous_reference`（整份拒絕，連無關的 name-only ref 也擋） | `test_duplicate_or_malformed_vocabulary_ids_block_every_topic` |
| 詞彙表 id 不是 contract identifier（含空字串） | `invalid_topic_id`（整份拒絕） | 同上 |
| 詞彙表 id 只差大小寫（`Topic-Data-Leakage`／`topic-data-leakage`） | `ambiguous_reference` | `test_case_only_twin_ids_are_not_two_ids` |
| 詞彙表 id 帶尾端換行（schema 的 `$` 會放過）或超過 `maxLength` | `invalid_topic_id`，且盤點列進 `invalidStableIds` | `test_trailing_newline_id_is_rejected_by_resolver_and_inventory_alike` |
| 同一個 resolver 先解析舊版、再更新 `input_hashes`，用新 hash 解析 | `stale_vocabulary`（索引與 hash 綁同一次讀取） | `test_one_resolver_cannot_check_one_version_and_resolve_another` |
| 詞彙表 bytes 改變後，用新 hash 來解析 | `stale_vocabulary` | `test_topic_name_hash_and_no_alias_guessing`、`test_one_resolver_cannot_check_one_version_and_resolve_another` |
| `TopicRef.id` 是中文／含空白／空字串；混入 `alias` 欄位；缺 `name` | schema issue | `test_topic_ref_accepts_an_optional_stable_id_but_no_free_text_key` |

詞彙表 id 的格式檢查刻意反過來呼叫 `validate_document("topic-ref", ...)`，再加上
`contracts.identifier_pattern().fullmatch()` 補上 anchoring。要講精確：**純 schema 驗證本身仍會
放過尾端換行**，是詞彙表這一層額外的 `fullmatch` 擋下來的；兩邊共用的是同一份 `$defs.identifier`
定義，不是同一段執行路徑。`migrate_topic_ids.py` 直接讀同一份 schema 的 `$defs.identifier`
取出 pattern **與 minLength／maxLength**（不 import `jsonschema`，所以裸 interpreter 也跑得動）。
兩邊在「格式、長度、`null`／非字串、尾端換行」四類上判定一致，並各有回歸測例；
`format` 之類 schema 其他關鍵字若日後加進 identifier，仍要再同步一次。

freshness 的比較對象是**實際被解析的那份 bytes 的 hash**（`_json_hashes`），
不是會被後續 `read_bytes()` 更新的 `input_hashes`——否則同一個 resolver 可能用新版 hash
配到舊版索引。兩種先後順序（先建索引後改檔、先讀檔改檔再建索引）都有測例。

要說清楚這條規則的邊界：resolver 是**快照式**的，一個 instance 讀過一次就固定用那份資料。
所以同一個 resolver 拿**舊 hash** 解析仍然會成功——它解析的本來就是那個版本，這是設計行為，
測例明確要求。build 期間來源被改動由 publication 的 `source_changed_during_build` 負責攔，
不是靠 resolver。

**本包沒有處理、應列為獨立後續項目**：`guide()`／`question()`／`catalog()` 走的是同一個
`input_hashes` 與快取分離的模式，第三輪審查者在記憶體中確認「先讀舊版、改檔、再 `read_bytes()`、
提供新 hash」對這些路徑仍可通過。審查者同時確認**移除本包新增的 hash bookkeeping 後這些重現依舊成立**，
因此屬既有行為而非本包退化。LP-210A 只宣稱修好 topic 這條路徑；其餘路徑要不要一併改成
`_json_hashes`，應該是一個獨立、且能重跑完整 gate 的變更包。

盤點 CLI 自己的 fail-closed：authored ref 帶了無法解析或與 name 不符的 id（`"id": null`
算「存在但不合法」，不是欄位缺席）、authored JSON 讀不動、
詞彙表 canonical name 正規化後重名、id 大小寫孿生，都會讓 `blocking=true`、exit 1；
`--report` 不接受寫進 repo 內的路徑（否則 `--report data/topics/topics.json` 就是一條覆寫 SSOT 的路），
對應 `test_inventory_blocks_authored_ids_that_do_not_resolve` 與
`test_migration_cli_refuses_apply_mode_and_repeats_byte_identically`。

**已知未修的既有限制**：`_unique()` 對形狀錯誤的來源（`topics` 是字串或含 `null`）會拋
`AttributeError`，而 `ReferenceResolver.validate()` 只捕捉 `KeyError/TypeError/ValueError`，
因此會是崩潰而不是結構化 issue。這是 LP-210A 之前就存在、且影響所有 ref 型別的行為，
本包沒有一併改動；它仍是 fail closed（build 中止），但錯誤訊息不友善。

## 6. 重跑與驗收

```bash
uv run python tests/test_learning_contracts.py
uv run python tests/test_learning_references.py
uv run python scripts/migrate_topic_ids.py --dry-run --report /tmp/ipas-topic-id-migration.json  # 路徑必須在 repo 之外
git diff --check
```

盤點 CLI 的性質：`--dry-run` 是唯一支援的模式（沒帶會以 exit 2 拒絕），只讀 SSOT，
報告無時間戳與絕對路徑，連跑兩次 byte-identical，`data/topics/topics.json` 不會被碰。
詞彙表本身或既有 authored 引用不一致時 exit 1。

因為動到共用 resolver 與 schema target，交付前另跑完整閘門：

```bash
UV_CACHE_DIR=/tmp/ipas-uv-cache uv run python tests/run_all.py
```

實際執行結果（2026-09-08，最終修正後的來源）：**20/20 通過、exit 0、356 秒**，
未使用 `--skip-browser`；含 production build、初／中級 alignment、`audit_resources`
與五支真 Chromium E2E。跑完以 `sha256sum -c` 確認受審來源在整段執行期間未變動。
本文件與 handoff 在該次 gate 之後只做過文字修正（§5／§6／§8 的措辭與審查紀錄），
markdown 不在 gate 的執行範圍內，程式與測試的 bytes 未再變動。

新測例掛在既有的 `test_learning_references` 與 `test_learning_contracts` 底下，
run_all 仍是 20 項；不新增 gate 項目，也就不會用「多一項」稀釋原本的 20/20 標準。

## 7. 下一包（LP-210B）與停點

本包到此停下。LP-210B 之前必須先有 §3 未決事項的裁決與非作者審查。之後的順序建議：

1. **LP-210B（必須是一個原子包）**：維護者指派 181 個 canonical id（含 A 的裁決），寫入 `topics.json`，
   `build_topic_vocabulary.apply_merge_pairs()` 改成保留 id，
   `tests/test_resource_catalog.py::test_signed_off_topic_vocabulary_rebuild_is_exact` 必須仍然通過。

   ⚠ **不能只寫詞彙表就收工**：`topics.json` 的 bytes 一變，`vocabularyHash` 就變，
   現有 12 筆 authored `topicRefs` 立刻全部 `stale_vocabulary`（`references.py` 的 `topic()`），
   build 直接擋下。所以「寫入 id」與「更新這 12 筆 ref 的 `vocabularyHash`」必須在同一包完成；
   而更新 ref 會改 `contentHash`，依 data-contracts §7 相關 review 同時失效，
   必須重新交獨立 reviewer 並重跑完整發布 gate。回填 `topicRefs[].id`（原本規劃在 D）
   建議一併在這一包做完，否則等於為了同一批檔案付兩次 review 成本。
2. **LP-210C**：標註與衍生產物重建（§2.2，含 `_assign_cache*`／`_verify_cache*` 的保留或失效決定），
   前端 `?c=` 相容層（§2.3）。
3. 只有以上都完成，才談讓某個 consumer 把 `id` 轉為必填。

停點規則（與 handoff 一致）：沒有完成獨立規則審查與完整 gate 之前，不修改 canonical
`data/topics/topics.json`、不批量回填 `topicRefs[].id`、不重算或覆蓋既有 review、
不建立第二份詞彙表、不開始第二主題內容。

## 8. 非作者審查紀錄（2026-09-08，三輪）

審查者：Codex CLI（`codex exec`，`sandbox_permissions=["disk-full-read-access"]` 唯讀），
在 repo 根目錄對本包的檔案與 SSOT 做獨立讀回，全程未修改任何檔案。
三輪的**報告本文**已歸檔到
[`content/learning/evidence/topic-id-migration-review.md`](../../content/learning/evidence/topic-id-migration-review.md)，
本節只是它的摘要；含工具呼叫 trace 的原始 log 留在本機 scratchpad，不進版控。
第一、二輪判 FAIL，第三輪判 **WARN**（三項必要修正全數驗證通過，剩下的是文件措辭與一項既有問題）。

### 第一輪：FAIL → 已修正

| 發現 | 性質 | 修正 |
|---|---|---|
| schema 的 `pattern` 用 `re.search` 且 `$` 吃尾端換行，`"topic-a\n"` 通過 resolver 但被盤點列為 invalid | 判定不一致 | 兩邊改用同一份 schema pattern 的 `fullmatch` |
| `_topic_index` 記憶化後，`input_hashes` 可被 `read_bytes()` 單獨更新，同一 resolver 用新 hash 配舊索引 | 版本錯配 | 見第二輪：首次修法不完整，最後改綁 `_json_hashes` |
| `canonicalNameUsedAsAnotherTopicAlias` 漏檢：`[{"name":"A","aliases":["A"]},{"name":"B","aliases":["A"]}]` 回傳空 | 碰撞漏報 | 條件改成 `set(owners) - {同名 topic}` |
| authored ref 帶不存在或錯配的 id 時，報告仍是 `blocking=false` | 盤點不可信 | 逐筆核對 id，新增 `stableIdState`／`unresolvedStableIds` 並列入 blocking |
| 文件宣稱「四個規則都是 `approved: false`」但報告沒有這個欄位；測例 `scheme.get("approved")` 恆真 | 文件不實＋假測試 | 欄位真的加上，測例改斷言 `[False] * 4`；`curated-slug` 碰撞改實算 |
| `--report` 可寫任意路徑，`--report data/topics/topics.json` 會覆寫 SSOT 之後還印「未寫入詞彙表」 | 破壞性缺口 | 報告路徑落在 repo 內即 exit 2 |
| `SOURCE_GLOBS` 非遞迴，子目錄不在掃描範圍 | 盤點盲點 | 改成遞迴掃描並明列排除項；重掃仍是同一批 25 個檔案 |
| `QuestionModal.tsx` 的 conceptGraph 字樣只在註解，實際用 `item.id` 查題 | consumer 誤報 | §2.3 改列為誤報並說明 |
| `assessment.py` 的 mapping、`assign_question_topics` 的名稱型快取未列入遷移面 | 漏項 | 補進 §2.2 |
| LP-210B 只寫詞彙表就會讓 12 筆 ref 立刻 stale，D 才處理 review 失效已太晚 | 順序錯誤 | §7 改成 B 必須是含 ref rehash 與 review 重審的原子包 |
| 未決事項 B 把「redirects 放獨立檔」當可選項，但 data-contracts §3 已定案在同一 SSOT | 重開已定契約 | §3 改成只留欄位形狀與 retired id 是否佔用唯一性 |
| id 大小寫孿生（`topic-ML`／`topic-ml`）未定義 | 規則缺口 | §3 規則 2 加 casefold 唯一，resolver 一併強制 |

### 第二輪（複審第一輪的修正）：FAIL → 已修正

第二輪確認第一輪多數修正成立（尾端換行、canonical-as-alias、`--report` 護欄、遞迴掃描、
consumer 更正、LP-210B 因果鏈、redirects 與大小寫規則），但抓到三個殘留缺陷與兩個測試覆蓋缺口：

| 發現 | 為什麼第一輪的修法不夠 | 修正 |
|---|---|---|
| 版本綁定只是延後包裝：**先 `read_json()`、改檔、再 `read_bytes()`、最後才建索引**，仍會用新 hash 配到舊資料 | 索引建立時才抓 `input_hashes`，而它在那之前就可能被更新 | `read_json()` 在解析當下把 hash 存進 `_json_hashes`，freshness 只跟這個比 |
| 161 字元的 id：resolver 拒絕、盤點放行 | 盤點只取 schema 的 `pattern`，沒取 `minLength`／`maxLength` | 新增 `valid_identifier()`，完整套用 `$defs.identifier` |
| authored ref 的 `"id": null` 被當成欄位缺席，`blocking=false` | 用 `node.get("id") is None` 判斷存在與否 | 改用 `"id" in node`，與 resolver 的判定對齊 |
| 「canonical-as-alias 修正」與「curated 碰撞實算」缺回歸測試 | 把它們改回錯的實作，19 個測例仍全過 | 各補一個測例；兩者現在改回錯的實作都會失敗 |

五項修正都做過**變異驗證**：逐一把修正還原成錯誤實作，對應測例都真的失敗
（版本綁定、identifier 長度、`"id": null`、canonical-as-alias、curated 碰撞實算），確認沒有恆真斷言。

### 第三輪（複審第二輪的修正）：WARN

三項必要修正逐一實測通過：版本綁定（另試八種讀取順序，hash 都對應實際快取版本）、
identifier 完整約束（161 字元／空字串／尾端換行／`null`／數字／布林／陣列／物件，
resolver 與盤點判定一致，160 字元通過）、authored `"id": null`。
審查者**獨立重跑了全部五項變異驗證**，確認測例真的會失敗，且不是靠執行例外冒充攔截。
也確認 `_json_hashes` 沒有造成共用 `read_json()` 的退化：無效 JSON／編碼／缺檔都不會留下單邊快取。

第三輪剩下的 WARN 已全部處理：

| 發現 | 處理 |
|---|---|
| §5「詞彙表 bytes 改變 → stale」省略快取條件；「永遠是同一條規則」過強（純 schema 仍放過尾端換行） | §5 已改寫，明說 resolver 是快照式、舊 hash 解析舊資料是設計行為，並說明兩邊共用的是同一份定義而非同一段執行路徑 |
| §6 只有命令、沒有 gate 執行結果 | §6 補上 2026-09-08 的 20/20、exit 0、356 秒與凍結來源核對 |
| `guide()`／`question()`／`catalog()` 有同類的快取／hash 版本問題 | 審查者確認移除本包新增的 bookkeeping 後重現依舊成立，屬**既有**行為；已在 §5 列為獨立後續項目，本包不宣稱修好 |

**未進行第四輪。** 上表的三項處理都只動文件，沒有再改程式或測試；
第三輪之後程式與測試的 bytes 未變動。

### 審查者明示無法驗證的部分

- 本包開始前的工作樹基準：多數受審檔案仍 untracked，無法證明既有 review／contentHash 未被改動，
  只能確認 SSOT 目前與 HEAD 逐 byte 相同。
- 完整 20 項 gate、production build 與瀏覽器流程：唯讀 sandbox 不跑，由作者在修正後重跑並記於 §6。
- marker 掃描不能證明所有**間接** consumer 已完整列出（§2 已列此限制）。
- 第二輪明確表示無法替第一輪的「確認過」做歷史歸因，第三輪同樣只背書自己實跑的結果；
  本節較早輪次的 OK 項目，以後續輪次重新驗證過的為準。
- 所有**間接** consumer 的完整性，以及並行／重入讀取的安全性，三輪都未完整驗證。

---

## 9. LP-210B：實際落地的設計與經過（2026-09-09）

### 9.1 維護者對 §3 未決事項的裁決

| | 裁決 |
|---|---|
| **A. id 用什麼字面** | **不具語意的穩定代號**，另以同一份 SSOT 的欄位承載語意對應。英文 slug 因此變成**可選的後續增補層**——帳本每筆都有 `slug: null`，之後補 slug 不動任何 ref、不改 contentHash、不讓任何 review 失效。 |
| **B. redirects 欄位** | 以 `data/topics/topic_id_assignments.json` 指派帳本承載，join 鍵是 `canonicalName ∪ previousNames`。它是 `topics.json` 的**策展輸入**（與既有的 `merge_pairs.json`、`alias_cleanup.json`、`manual_topic_additions.json` 同一類），不是第二份詞彙表。 |
| **C. `?c=<中文名>` 相容期** | 仍未決。前端目前不受影響（`conceptGraph.json` 尚未帶 id），屬 LP-210C。 |
| **D. 哪個 consumer 先強制 id** | 全部一起——因為這一包本來就是原子的（見 §7），分階段反而要付兩次 review 成本。 |

### 9.2 最後採用的設計比 §3 提案更小

實作過程中發現一件 §1–§8 沒看出來的事：**`vocabularyHash` 才是真正的痛點，穩定 id 不是**。

`TopicRef` 原本帶的是整份 `topics.json` 的 blob hash，而 `topic()` 在查 name 之前就無條件比對它。
所以詞彙表動一個 byte——新增一個概念、修一個別名錯字、**甚至只是寫入 id 本身**——
現有每一筆 ref 就全部 `stale_vocabulary`，連帶所有綁在它們身上的 review 全部失效。
穩定 id 對這件事**一點幫助也沒有**：改名時照樣要 rehash 全部。

同一份契約裡 `questionRef` 是 `{questionKey, revision, hash}`——**逐題** hash；
只有 topic 被當成整包資產。這才是異常。

因此最後採用的不是「id + 逐筆 entry hash」，而是更小的 **`TopicRef = {id, name}`，完全不帶 hash**：

| 事件 | 結果 |
|---|---|
| 新增概念 | 既有引用**完全不受影響**（LP-220 要的就是這個） |
| 改別的概念的別名／parent | 不受影響 |
| 改**這個**概念的別名／parent | 不受影響（別名不改變引用的意義） |
| **改名** | id/name 交叉檢查失敗 → 作者必須更新 → 走 review |
| 合併掉這個概念 | `unknown_topic_id` |
| 兩個概念互換名字 | 兩邊都失敗 |

有了不可變 id，`name` 欄位本身就是完整性檢查——hash 之所以需要，正是因為 name 曾是唯一的鍵。

**刻意接受的取捨**：`publication.py` 的 `dependency_hashes()` 不再收集 `vocabularyHash`，
詞彙表版本因此退出每一筆 review 的相依指紋。這正是「改一個別名就讓全部 review 失效」的 review 層版本。
整體 provenance 沒有消失——release manifest 的 `inputHashes` 與 analysis 的 `taxonomyHash` 仍記整份詞彙表。
代價是：個別 ref 的 review 不再固定完整 taxonomy 快照，這一點非作者審查者已標為 WARN 並確認本次未影響既有結論。

### 9.3 代號與帳本

- 格式 `topic-<8 hex>`，一次性隨機指派後凍結。8 hex 對 181 個概念的首次碰撞機率約 0，指派時仍逐一查重。
- 帳本 `data/topics/topic_id_assignments.json`：`{id, canonicalName, previousNames[], slug}`。
- `topics.json` 的改動是 **186 行純新增、0 行刪除**：181 個 `id` ＋ 5 行 `stableIds` metadata。
- `build_topic_vocabulary.apply_merge_pairs()` 每次都從 draft 整份重建，所以帳本必須被折回來。
  **隨機代號一旦掉了就救不回**，因此六道防線都會讓重建 exit 1，且各自有獨立測例（皆經變異驗證）：

  | 防線 | 訊息 |
  |---|---|
  | 帳本不見但詞彙表已有 id | `找不到 id 指派帳本…重建會把它們洗掉且無法重算` |
  | 概念沒有對應指派（含改名沒補 previousNames） | `沒有 id 指派` |
  | 帳本 id 不是合法 identifier | `不是合法 identifier` |
  | 帳本 id 只差大小寫 | `只差大小寫` |
  | 帳本要換掉詞彙表既有 id | `帳本卻指派` |
  | `--assign` 遇到帳本與詞彙表不一致 | `帳本卻是` |

  最後一條特別重要：重建失敗的訊息會引導使用者去跑 `--assign`，
  所以 `--assign` 必須**收編**詞彙表既有代號而不是重新指派——否則修復路徑本身會製造孤兒引用。

### 9.4 配額 key 的處理

topic 維度的 `quotas[].key` 維持**可讀的中文 canonical 名稱**（blueprint 是人在審的），
但新增了對詞彙表的驗證：改名或打錯會讓 build 擋下（`unknown_topic`），不再靜默對不到任何題。

### 9.5 13 筆 review 的重新開立

寫入 id 讓 5 個 authored 實體的 `contentHash` 改變，13 筆綁在舊 hash 上的 review 依
`data-contracts.md` §7 全部失效。維護者選擇**範圍受限的重新審查**，作法與界線：

- **證明只有 topicRefs 變動**：不靠任何備份。把 `topicRefs` 還原成舊形狀
  （`{name, vocabularyHash}`，hash 取自 `git show HEAD:data/topics/topics.json`）再重算 `contentHash`，
  精確還原成舊 review 記錄的 `subject.hash`。analysis 另有一套還原（`measures[].topic`、
  `taxonomyHash`、`labelReviewHash`，且 mapping 順序是證明的一部分）。
  完整可重跑指令與**證明的邊界**在 `content/learning/evidence/lp210b-topic-id-migration-20260909.md`。
- **誰背書什麼**：6 筆 `deterministic_contract` 由實跑的 `validate_learning_content.py` 背書；
  1 筆 `notebook_execution` 由 2026-09-09 實跑的 `verify_learning_labs.py --check` 背書；
  6 筆 `domain_content` 由非作者的 Codex CLI 以**機械式遷移**為範圍承接舊結論。
- **明確不涵蓋**：沒有重做教學語意審查、沒有重做 lab 的 L4、沒有真人 Colab L5。
  `review-lab-semantic-20260909-v2` 的 `L4: pass` 只能讀作「舊結論經遷移確認後承接」。
- 每筆都有 `supersedes` 指回前一版，舊紀錄保留在 repo 作為稽核軌跡。

### 9.6 非作者審查（Codex CLI，兩輪）

- **第一輪**：6 個實體的內容遷移全部 `approved`；但工具層兩個 FAIL——
  帳本不見時重建仍 exit 0 並產出零 id 詞彙表（最高優先）、`--assign` 會把詞彙表既有 id 重新指派、
  帳本 id 的大小寫／格式重建不擋、合法 guide mapping 讓盤點 `TypeError` 崩潰、漏判 `/measures/N/topic`。
- **第二輪**：確認上述修正成立，但指出三筆紀錄敘述不實或證據不足——
  兩筆 analysis 誤套了只適用於 5 個 authored 實體的證明、execution 紀錄缺本輪重跑證據、
  以及證據文件兩處措辭仍過強。**這三項全部已修**：補了 analysis 專屬還原證明、
  補了 2026-09-09 的 L0–L3 重跑證據、把「一個 byte 都沒動」限縮為「參與雜湊投影的欄位值」。
  第二輪另指出重建測例只斷言「有 SystemExit」而非各自的訊息，已改成逐條綁定訊息並重做變異驗證。
- 兩輪報告本文歸檔在 `content/learning/evidence/topic-id-migration-review.md` 的延續檔與本機 log；
  委派與範圍限定見 `content/learning/evidence/lp210b-review-delegation-20260909.md`。

### 9.7 下一步

1. ~~**LP-210C**：衍生產物重建與前端 `?c=` 相容層~~ **✅ 2026-09-14 完成，見 §10**。
   §3 未決事項 C（相容期）仍待裁決。
2. **英文 slug**（可選）：填帳本的 `slug` 欄位。純增補，不影響任何 ref 或 review。
3. **既有問題（非本包）**：`guide()`／`question()`／`catalog()` 仍有「快取資料與 `input_hashes`
   版本可能不同」的模式，非作者審查者確認屬既有行為。見 §5 的說明。

## 10. LP-210C：衍生產物與前端相容層（2026-09-14）

### 10.1 範圍

LP-210B 之後，SSOT 與 authored 引用都有 id，但**下游全部還是以中文名稱為鍵**：兩份標註
（`question_topics.json`／`practice_question_topics.json`）、三個 gitignored 的模型快取、
`topicHeat.json`、`conceptGraph.json`，以及前端 `/concepts?c=<中文名>`。概念一改名，
這一層會靜默錯位或直接斷鏈。本包讓它們**同時帶 id**，名稱一律保留給顯示與舊讀取器。

不動的東西：`data/topics/topics.json`、`topic_id_assignments.json`、任何已指派的 id、
`content/learning/**`、既有 review、glossary（重生要付費模型）、production `current.json`。
沒有呼叫任何模型或 API：標註與快取是由既有檔案**回填**，兩份 export 產物是重跑腳本。

### 10.2 產物形狀（全部是純新增，拆掉新欄位就是原檔）

| 檔案 | 新增 | 鍵 | 驗證 |
|---|---|---|---|
| `data/topics/question_topics.json`、`practice_question_topics.json` | 頂層 `stableIds`（複製詞彙表的出處區塊）；每題 `topicIds` 與 `topics` 逐位對應；`evidence[].topicId` 緊接在 `topic` 後；`droppedAsWrongIds` | 名稱仍是鍵，id 隨行 | 565／580 題、1,105／880 筆 evidence（濾掉「錯誤」後的有效標籤 1,072／877）100% 對到 id；`git diff --stat` 6,394 行插入、0 刪除 |
| `frontend/src/generated/topicHeat.json` | 每列 `id`（排第一）；頂層 `stableIds` | `name`（顯示） | 重跑 byte-identical；`id` 與詞彙表逐列一致 |
| `frontend/src/generated/conceptGraph.json` | 每個概念 `id`、`previousNames`（取自帳本）；`related[].id`；頂層 `stableIds`、`source.ledger`；**移除 `generatedAt`** | **id**：計數、共現邊、`related` 都以 id 配對，`name` 只作顯示 | 拆掉新欄位後與舊檔相等（除時間戳）；跨 `PYTHONHASHSEED` 位元相同 |
| `data/topics/_assign_cache*.json`、`_verify_cache*.json`（gitignored） | 改成 `topic-cache/v2` 封裝：`{format, kind, stableIds, entries}`；每筆 `{topic, topicId[, verdict]}` | 讀取時 id 優先 | v2 轉回 v1 與原檔逐字相等（無損）；原檔備份 SHA 記在 evidence |

`generatedAt` 移除的理由是 08 §7-3 的既有規則：committed 產物要能位元重現，時間戳讓每次重跑都有無意義的 diff，
也讓「重建是否精確」無法用 `cmp` 回答。前端不讀這個欄位。

### 10.3 標註腳本的變化（`scripts/assign_question_topics.py`）

- 兩個寫出點（指派、`--verify-all`）都先經 `attach_topic_ids()`：名稱對不到詞彙表就 `FAIL`，
  **不寫 null**——標註檔裡出現不在詞彙表的名稱是資料壞了。`rejectedTopics` 本來就是「不在詞彙表」，不帶 id。
- 新增 `--backfill-ids`（不呼叫模型）：讀既有標註檔與兩個快取，補 id 後寫回。寫入前在記憶體證明
  「拆掉 id 後與原檔相等」（快取則證明 v2→v1 逐字相等），不成立就不寫。冪等；原子寫入（同目錄暫存檔再 replace）；
  保留原檔的結尾換行慣例，所以 tracked 的 diff 是純新增。
- **id 優先、名稱其次**：`canonicalise_names()` 讓帶 id 的舊標註在概念改名後重跑 `--backfill-ids` 就自動換成新名稱；
  驗收快取的 `align_cached()` 先以 id 對到這題目前的標籤，沒有 id 的舊紀錄才退回 normalise。
  這正是 §2.2 指出的「改名後 `align()` 只靠 normalise 對齊，會靜默錯位」的修法。
- 順手修掉一個既有的破壞性行為：舊版每寫一批就把驗收快取整份重寫成「只含本輪題目、且對齊成本輪標籤」的版本——
  只要標註檔的題目集合比快取小（例如用 `--out` 做的小複本）又至少跑到一批，快取裡其他題的判定就全部消失
  （非作者審查者實測：HEAD 版 553 筆有效判定 → 0 筆；新版 553 → 553）。現在本輪沒跑到的題原樣寫回；
  本輪題目上已不屬於該題的舊紀錄仍會濾掉，與舊版意圖相同。批內也從快取已有的判定起算，模型少回一個標籤不會洗掉上次的。
  註：`--limit` 搭 `--verify-all` 在新舊版都走不到快取（先 KeyError），不是觸發條件；新版改成明確 FAIL，
  因為全量驗收只跑一部分會把其他題洗成「未評」。
- `verify_all` 一開始就先 `attach_topic_ids()`：名稱不在詞彙表時在花 API 錢之前 FAIL 並指引 `--backfill-ids`，
  而不是在 `align_cached()`／`persist()` 以裸 KeyError 收場（非作者審查 F7）。

`_assign_cache_practice.json` 裡 1 個模型自創名稱（「應用場景評估」，已在 `rejectedTopics`）保留原字串、`topicId: null`；
`_verify_cache_practice.json` 裡 18 種非正式寫法（空白、連字號等，如「AI 基礎設施評估」，共 151 筆）由 normalise 解析到 id，原字串不動。

### 10.4 前端相容層（`ConceptsPage.tsx`）

`?c=` 的解析在 `frontend/src/data/conceptLookup.ts`（純 TS、無 import），順序**嚴格分段**：
**id → 目前正式名稱 → 帳本 `previousNames`**。三段不能合成一次 `find`——兩個概念互換名字時，排前面那個的
`previousNames` 會蓋過排後面那個的正式名稱（非作者審查 F3 抓到的潛伏缺陷，第一版就是這樣寫的，已改）。
命中後兩種就以 `replace` 把網址改寫成 `?c=<id>`（不留歷史紀錄），之後再分享出去的連結不再綁名稱。
對不到任何概念時顯示明確的「找不到概念」狀態，不再靜默落回空白右欄。清單、立體圖節點、相關概念按鈕、
`TopicHeatPanel` 的 key 與選取狀態全部改用 id；顯示一律仍是 `name`。

目前 181 筆帳本的 `previousNames` 全部為空，真實資料走不到第三段；`tests/test_learning_frontend_static.py`
因此呼叫 `tests/frontend_checks/concept_lookup_check.cjs`——用 frontend 自己的 typescript 套件轉譯 `conceptLookup.ts`
後執行（CI 是 Node 20，不能靠 Node 22 的原生 TS），以人造 fixture 驗三段順序、互換名字與空值（非作者審查 F4）。

**§3 未決事項 C 已裁決（2026-09-14，維護者）：只保留一段過渡期。** 維護者沒有指定長度，作者取 **2026-12-31**
為到期日（約三個半月，跨過 12 月的考期），日期只寫在本節與 `frontend/src/data/conceptLookup.ts` 的註解，要改只改這兩處。

到期後的移除步驟（一次做完，跑完整 gate）：

1. `frontend/src/data/conceptLookup.ts`：刪 `resolveByLegacyName()`，讓 `resolveConcept()` 只剩 id 那一段。
2. `tests/test_routes.py`：刪 `ROUTES` 的「概念索引 舊名連結」與 `CONCEPT_LINK_CASES` 的「?c=<中文名> → 改寫成 id」；保留 id 直達與無效概念兩條。
3. `tests/frontend_checks/concept_lookup_check.cjs`：把名稱與 previousNames 的 case 改成預期 `null`。
4. `conceptGraph.json` 的 `previousNames` 可留作資料，不必移除；`tests/README.md` 第 18 項的路由數同步改。

到期前行為等同「永久接受」；到期日不寫進程式邏輯（不做時間炸彈測試），避免 gate 在某一天突然為了不相干的部署變紅。

### 10.5 fail-closed 行為（本包新增）

| 情境 | 結果 | 測例 |
|---|---|---|
| 詞彙表任一概念沒有 id／id 重複 | `assign`、`export_topic_heat`、`export_concept_graph` 都拒絕輸出（heat 的重複 id 閘門是非作者審查 F1 補上的） | `test_exports_refuse_a_vocabulary_with_duplicate_or_missing_ids` |
| `--verify-all` 搭 `--limit`；標註名稱不在詞彙表 | 在呼叫模型前 FAIL，訊息指引 `--out`／`--backfill-ids` | `test_verify_all_refuses_partial_runs_and_stale_names_before_spending` |
| 標註檔名稱不在詞彙表 | `attach_topic_ids` FAIL，不寫 null | `test_attach_topic_ids_fails_closed_on_unknown_names_and_renames_by_id` |
| 標註的 `topicId` 缺、或 id／名稱與詞彙表不一致 | `export_concept_graph` 拒絕建圖，提示先跑 `--backfill-ids` | `test_concept_graph_refuses_labels_whose_id_and_name_disagree` |
| 帳本的 `canonicalName` 與詞彙表對不上、帳本不存在 | `export_concept_graph` FAIL | `previous_names()` |
| 快取 `kind` 不符（拿 assign 快取當 verify） | FAIL | `test_cache_upgrade_is_lossless_and_alignment_prefers_ids` |
| 回填後拆掉 id 與原檔不相等（比序列化字串，鍵序也算） | 拒絕寫入 | `backfill_ids()`；兩個 rebuild 測例也改比 bytes（非作者審查 F6） |
| 網址 `?c=` 對不到任何概念 | 「找不到概念」狀態、無 console error | `test_routes.py` 無效概念 |

`migrate_topic_ids.py --dry-run` 的 `generatedRebuildSurface` 多了 `carriesStableIds`，四份衍生產物現在都是 `true`。

### 10.6 重跑與驗收

```bash
python3 scripts/assign_question_topics.py --backfill-ids                    # 官方卷標註＋_verify_cache（官方卷沒有指派快取，會印「不存在，略過」）
python3 scripts/assign_question_topics.py --source practice --backfill-ids  # 練習題標註＋兩個快取
python3 scripts/export_topic_heat.py
python3 scripts/export_concept_graph.py
uv run python tests/test_resource_catalog.py        # 22 tests（新增 9 個 stable-id 產物測例）
uv run python tests/test_learning_frontend_static.py  # 含 conceptLookup.ts 的三段解析檢查（node tests/frontend_checks/concept_lookup_check.cjs）
uv run python tests/test_routes.py                  # 30 條正常＋2 條概念連結相容＋4 條錯誤路由
(cd frontend && npm run build)
UV_CACHE_DIR=/tmp/ipas-uv-cache uv run python tests/run_all.py   # 完整 20 項
```

run_all 仍是 20 項：新測例掛在既有的 `test_resource_catalog`、`test_learning_frontend_static` 與 `test_routes` 底下。

實際執行結果（2026-09-14，修正非作者審查 F1–F8 之後的最終來源、無其他負載）：**20/20 通過、exit 0、797 秒**，
未使用 `--skip-browser`；開跑前以 `sha256sum` 凍結 602 個來源檔，跑完 `sha256sum -c` 全部相符。
同日稍早一次與審查 agent 併行的 gate 是 18/20（兩支學習平台 E2E 在 CPU 競爭下逾時），不當證據，經過記在
`content/learning/evidence/lp210c-derived-artifacts-20260914.md`。

### 10.7 非作者審查

Codex CLI 當日因登入 token 失效無法使用；改派沒有實作脈絡的 Claude Code 子代理（opus）唯讀審查，只給驗收條件不給實作過程。
10 項宣稱 9 項 PASS（第 5／7／8 項帶 WARN），3 項優先修正（F1 熱度腳本不擋重複 id、F2 `--limit` 敘述不實、
F3 舊名解析優先序）與 5 項補強（F4–F8）全部已修並加測例；沒有第二輪。報告全文、對照表與委派範圍在
`content/learning/evidence/topic-id-migration-review.md`（LP-210C 節）與 `lp210c-review-delegation-20260914.md`。

### 10.8 下一步

1. **§3 未決事項 C 已裁決為過渡期，到期日 2026-12-31**：到期後依 §10.4 的四步移除 name fallback。
2. **英文 slug**（可選）：填帳本的 `slug` 欄位，純增補。
3. **既有問題（非本包）**：`guide()`／`question()`／`catalog()` 的快取版本問題（§5）。
4. **可選**：維護者 `codex login` 後補一輪 Codex 審查，對 F1／F3／F7 的修正做變異驗證。
