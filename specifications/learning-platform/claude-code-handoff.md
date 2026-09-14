# Claude Code 交接：實務學習平台

交接日期：2026-09-07。這份文件給新的 Claude Code session 使用；先確認事實與工作樹，再選擇下一個工作包。本文件記錄本機 MVP 的交接狀態；正式發布與真人驗收仍未完成。

## 先讀與先做

依序讀取，避免從大量 generated JSON 反推架構：

1. repo 根目錄的 [`CLAUDE.md`](../../CLAUDE.md)：權威不變量與文件路由。
2. [`progress.md`](progress.md)：已完成範圍、最後候選與唯一正式審查缺口。
3. [`acceptance.md`](acceptance.md)：非作者 runtime/read-back 驗收與實際命令結果。
4. [`mvp-runbook.md`](mvp-runbook.md)：本機 preview 的最小重建及操作方式。
5. [`implementation-plan.md`](implementation-plan.md) 的「P2 跨主題擴展與內容運作」及 LP-210；只有準備實作該包時才讀相關契約。
6. [`data-contracts.md`](data-contracts.md)、[`tests/README.md`](../../tests/README.md)，以及需要的 [`playbook/pipeline-reference.md`](../../playbook/pipeline-reference.md) 小節。

進入 session 後先執行唯讀盤點：

```bash
git rev-parse --short HEAD
git status --short
git diff --stat
```

2026-09-14 之前 HEAD 是 `e35a312`、工作樹未 commit；同日已以單一 commit push `main` 上線（見「已驗證事實」最後一條），
之後的 session 應以 `git log` 為準。仍然不要使用 `git reset --hard`、`git checkout -- <path>`、`git restore` 或 `git clean`；
不要把未追蹤檔案當成可丟棄的生成垃圾。先用 `git diff -- <path>` 分辨來源，再只改獲授權的檔案。

大型 JSON（特別是 86 KB 的 `data/topics/topics.json` 與 `frontend/src/generated/`）不要整檔讀取。先用 `rg`、`jq` 或短 Python 程式計數／選取需要的欄位。

## 已驗證事實

- 本機第一條 P0→P1 MVP 已完成，涵蓋三個 Unit、一個 Project、一個 CPU Lab、10 題診斷、5 題官方來源選讀、IndexedDB 狀態與 frontend 流程。
- 最終 preview candidate 是 `learning-e6732041208784d31304146c`。`frontend/src/generated/learning/preview.json` 指向該 preview；production `frontend/src/generated/learning/current.json` 不存在。
- 最終 candidate 驗證 128 個文件，`issues=[]`、`invalidReviews={}`。17 項 machine review 已有真實 hash-bound 紀錄；唯一 `unmetReviews` 是 Lab 真人 L5。
- Lab L0–L3 本機乾淨 kernel 通過，獨立模型 L4 對 content hash `sha256:5bb3dc8b27d18e8d5407398445a7ea52791c2ae5d97de5d5131a63c3c319cb2b` 通過；這不是真人 Colab L5。
- 2026-09-07 在 frozen source 上執行 `UV_CACHE_DIR=/tmp/ipas-uv-cache uv run python tests/run_all.py`，20/20 PASS、exit 0、679 秒，沒有使用 `--skip-browser`。它包含 production build、初／中級 alignment、舊三支及新兩支真 Chromium E2E。
- Blueprint／Pool／Analysis 另有非作者 21/21 machine check；三卷母體 150、reviewed 5、unknown 145，沒有宣稱完整歷屆分布。
- 本輪沒有 commit、push、deploy，也沒有真人 Colab 完整走查。
- 2026-09-08 追加 LP-210A（topic stable ID 相容層與盤點）。同日在最終修正後的來源上重跑
  `tests/run_all.py`，**20/20 PASS、exit 0、356 秒**，沒有使用 `--skip-browser`；
  跑完以 `sha256sum -c` 確認受審來源在整段執行期間未變動。之後只再修改過 markdown。
- 2026-09-09 完成 LP-210B（topic stable ID 遷移落地）。在最終來源上跑
  `tests/run_all.py`，**20/20 PASS、exit 0、418 秒**，沒有使用 `--skip-browser`；
  跑完以 `sha256sum -c` 確認 63 個 `content/` 檔在整段執行期間未變動。
  候選驗證 `validated`／144 entities／`issues=[]`／`invalidReviews={}`，
  `unmetReviews` 只剩既有的真人 Colab L5，`publicationApproved: false`。
  LP-210B 另經 Codex 兩輪唯讀非作者審查，報告本文歸檔在同一份
  [`topic-id-migration-review.md`](../../content/learning/evidence/topic-id-migration-review.md)。
- 2026-09-14 完成 LP-210C（衍生產物與前端相容層）。在修正非作者審查 F1–F8 之後的最終來源上、無其他負載下跑
  `tests/run_all.py`，**20/20 PASS、exit 0、797 秒**，沒有使用 `--skip-browser`；開跑前以 `sha256sum` 凍結 602 個
  `content/`、`data/topics/`、`schemas/`、`scripts/`、`tests/`、`frontend/src/` 檔（含三個 gitignored 快取），跑完 `sha256sum -c`
  全部相符。同日稍早與審查 agent 併行的一次是 18/20（兩支學習 E2E 在 CPU 競爭下逾時），不當證據。
  四份 tracked 衍生產物的改動對 HEAD 是純新增（6,394＋184＋1,158 行插入、只刪 `generatedAt`），三個快取轉回 v1 與原檔逐字相等。
  非作者審查改由 opus 子代理進行（Codex 登入失效），10 項 9 PASS、全部修正已加測例；報告與委派紀錄在
  [`topic-id-migration-review.md`](../../content/learning/evidence/topic-id-migration-review.md) LP-210C 節與
  [`lp210c-review-delegation-20260914.md`](../../content/learning/evidence/lp210c-review-delegation-20260914.md)，
  差異證據在 [`lp210c-derived-artifacts-20260914.md`](../../content/learning/evidence/lp210c-derived-artifacts-20260914.md)。
  沒有呼叫任何模型或 API。
- **2026-09-14 上線**：維護者裁決以**單一 commit** 把整個工作樹（MVP、LP-210A／B／C、先前未 commit 的規格與 README 變更）
  連同 6 個本機未 push 的 EPUB／匯出 commit 一起 push 到 `main`，由 `deploy.yml` 跑完整 20 項 gate 後部署 GitHub Pages。
  push 前先在 fresh-checkout 複本（只含 tracked＋untracked 非 ignored 檔，無 preview.json、無快取）跑過
  `npm ci → uv sync --frozen → run_all.py → build_web.py`，確認 CI 環境不依賴任何本機 gitignored 檔；
  為此 `tests/test_learning_frontend_static.py` 改成 preview 指標不存在時自行 `build_learning_content.py --preview`。
  **站台上線 ≠ 學習平台正式發布**：production `current.json` 仍不存在，「實務補充」等導覽項在正式站不會出現，
  直接開 `/learn` 只會看到「尚未發布」；學習內容的正式發布仍依下方「正式發布前仍待完成」的 L5 與版本門檻。
- LP-210A 經三輪 Codex 唯讀非作者審查（FAIL → FAIL → WARN），報告本文已歸檔到
  [`content/learning/evidence/topic-id-migration-review.md`](../../content/learning/evidence/topic-id-migration-review.md)。
  審查者三輪都明示：因為受審檔案多數仍 untracked，**無法取得修改前的工作樹基準**，
  因此不能證明既有 review／contentHash 未被改動，只能確認 SSOT 目前與 HEAD 逐 byte 相同。
  這是「不 commit」直接換來的驗證缺口，不是審查疏漏。

可版控、可供目前工作樹與後續 commit 引用的證據在 repo；它們目前仍可能是 untracked，不可稱為已提交：

- [`baseline.md`](baseline.md)：開工前 13 項基線。
- [`acceptance.md`](acceptance.md)：最終 20 項、state 黑盒與 fresh-source 證據。
- [`content/learning/evidence/`](../../content/learning/evidence/) 與 [`content/learning/reviews/`](../../content/learning/reviews/)：版本化的內容、Lab 與 assessment 審查紀錄。
- [`progress.md`](progress.md)：最後候選與發布邊界。

以下只存在本機 `/tmp`，不能當 fresh checkout 的唯一證據，也不應加入 source contract：

- `/tmp/ipas-learning-final-gate.log`：20/20 stdout/stderr 與 `RUN_ALL_EXIT=0`；SHA-256 `26a230ff003a93585f8b22f2100e7a8ca087ac2523c24ae143a60c2482459794`。
- `/tmp/ipas-learning-baseline.log`：開工前完整基線。
- `/tmp/ipas-learning-preview-determinism.json` 與相鄰 stdout logs：早期 fresh-root 連跑兩次結果。
- `/tmp/ipas-learning-assessment-independent-review.json`：已封存到 repo evidence 的原始非作者 assessment 報告。

最終 `test_learning_assessment` 已從 repo 內可版控來源建立來源檔複本，在沒有 `data/learning/pipeline/` 的 temporary root 重建 preview；正式 review 補記沒有製造 staging 依賴。這證明目前來源樹可重建，不代表檔案已進 Git commit。

## 本機 preview 與發布界線

從 repo 根目錄建立 preview：

```bash
uv sync
uv run python scripts/build_learning_content.py --preview
cd frontend
npm ci
npm run dev -- --host
```

開啟 `http://localhost:5173/#/learn`。一般 preview 不需要 `learning-lab` dependency group，也不需要 `data/learning/pipeline/` staging。只有維護或重驗 notebook 才使用：

```bash
uv run --group learning-lab python scripts/generate_learning_lab.py --check
uv run --group learning-lab python scripts/verify_learning_labs.py --lab lab-imbalanced-classification --profile cpu --check
```

在 L5 與 immutable Git URL 未完成前，只使用 `--preview`、`--check` 或 `--dry-run`。不要手寫或切換 production `current.json`，不要把 preview 目錄複製成 production release，也不要將「可下載／已開啟／使用者自報完成」改寫成「已驗證通過」。

`docs/` 是 gitignored build output，GitHub Pages 由 workflow 建置；push main 可能部署。本輪未提交或部署；接手時先分辨既有使用者變更，發布仍依下列 L5 與版本門檻處理。

## 契約與 SSOT

- 章節 SSOT：`scripts/build_manifest.py` 的 `GUIDES_BY_LEVEL` → `data/{level}/toc_manifest.json`。前端或新腳本不得複製章節陣列。
- 資源 SSOT：`data/resource_catalog.json`；dataset、guide、external resource 仍由同一 catalog 管理。
- topic vocabulary SSOT：`data/topics/topics.json`。LP-210 必須擴充同一份詞彙表，不能建立第二份 stable-ID 詞彙表。
- Learning JSON Schema：`schemas/learning/*.schema.json`；Python API 在 `scripts/learning/contracts.py`，引用解析在 `scripts/learning/references.py`，候選發布在 `scripts/learning/publication.py`。
- Frontend learning 型別與 loader 在 `frontend/src/features/learning/types.ts`、`data.ts`、`useLearningIndex.ts`、`useLearningItem.ts`。
- `contentHash`、blob hash、reference hash 應呼叫既有 contract API；不要另寫近似 canonical JSON/hash 實作。
- Unit 的 GuideRef 必須解析到 `content/learning/identity/guide-anchors.json` 的 exact current mapping；QuestionRef 必須帶完整 namespace、revision 與 hash。

審查紀錄只能描述真的執行者、角色、scope、subject hash 與 evidence。作者不能替自己的內容補獨立 D1/A1；model review 不能標為 human，沒有實跑不能標 PASS。修改 subject 或 dependency hash 後，舊 review 必須失效並重新交給獨立 reviewer。

不要為下一階段重跑 PDF Vision、全量 OCR、`--force` extraction、Claude/Gemini API 或其他付費模型。LP-210 使用 repo 內既有 vocabulary、fixtures 與 consumers 即可完成第一小包。

## LP-210C（2026-09-14 已實作）：衍生產物與前端相容層

**狀態：完成；§3 未決事項 C 已於 2026-09-14 裁決為過渡期（到期日 2026-12-31，見 §10.4）。** 詳見
[`topic-id-migration.md`](topic-id-migration.md) §10，證據與 gate 結果在
`content/learning/evidence/lp210c-derived-artifacts-20260914.md`。摘要：

- 兩份標註（565／580 題）每個名稱旁同時帶 `topicIds`／`evidence[].topicId`／`droppedAsWrongIds`，
  三個 gitignored 快取改成 `topic-cache/v2`（每筆 `{topic, topicId}`）。全部由既有檔案**回填**
  （`assign_question_topics.py --backfill-ids`，不呼叫模型），寫入前先證明拆掉 id 就是原檔；
  tracked 的 diff 是純新增（6,394 行插入、0 刪除），快取轉回 v1 與原檔逐字相等。
- `topicHeat.json` 每列帶 `id`；`conceptGraph.json` 以 id 為鍵（計數、共現邊、`related`），
  每個概念帶帳本的 `previousNames`，並移除非確定性的 `generatedAt`。兩份都能位元重現。
- 前端 `/concepts?c=` 解析在 `frontend/src/data/conceptLookup.ts`，三段嚴格分開：id → 目前正式名稱 → `previousNames`；
  舊中文名連結命中後以 `replace` 改寫成 id 形式；對不到顯示「找不到概念」。清單、立體圖、相關概念、`TopicHeatPanel` 的 key 全改 id。
  `previousNames` 目前全空，第三段只靠 `tests/frontend_checks/concept_lookup_check.cjs`（轉譯後執行，掛在 gate 第 12 項）的 fixture 驗。
- 非作者審查：Codex CLI 當日登入 token 失效（401）無法用，改派沒有實作脈絡的 opus 子代理唯讀審查，10 項宣稱 9 PASS，
  3 項優先修正＋5 項補強**全部已修並加測例**（對照表與報告全文在
  [`topic-id-migration-review.md`](../../content/learning/evidence/topic-id-migration-review.md) LP-210C 節）。沒有第二輪。
- 概念改名後的重跑順序固定為：重建詞彙表 → `--backfill-ids`（兩份）→ `export_topic_heat` → `export_concept_graph`；
  少跑回填 graph 會拒絕建圖，不會靜默用舊名。
- 沒有動 `topics.json`、帳本、任何 id、`content/learning/**`、review、glossary、production `current.json`；沒有呼叫 API。

**C 已裁決為過渡期**（維護者：「保留一段時間即可」；到期日由作者定為 2026-12-31，只寫在 §10.4 與
`conceptLookup.ts` 註解兩處）。到期後依 §10.4 的四步移除 name fallback，到期前行為等同永久接受。

## LP-210B（2026-09-09 已實作）：遷移完成

**狀態：topic stable ID 遷移已落地。** 詳見
[`topic-id-migration.md`](topic-id-migration.md) §9。摘要：

- `TopicRef` 從 `{name, vocabularyHash}` 改成 **`{id, name}`，完全不帶 hash**。
  根因是整份詞彙表的 blob hash 被綁在每一筆引用上——動一個 byte 就讓所有引用與 review 全滅。
  有了不可變 id，`name` 本身就是完整性檢查。**新增概念不再讓既有引用失效**，改名仍會被擋。
- 181 個代號 `topic-<8 hex>` 一次性隨機指派，帳本
  `data/topics/topic_id_assignments.json` 是 `topics.json` 的策展輸入（不是第二詞彙表）。
  `topics.json` 的 diff 是 186 行純新增、0 刪除。
- 重建流程有六道防線防止代號遺失（隨機代號掉了救不回），每道各有測例並經變異驗證。
- 13 筆因 contentHash 改變而失效的 review 已以新 hash 重新開立，
  scope 明寫為機械式遷移、`supersedes` 指回前一版；舊紀錄保留作稽核。
- 非作者審查（Codex CLI）兩輪：第一輪 6 實體內容遷移 approved＋工具層 2 個 FAIL，
  第二輪確認修正並抓到 3 筆紀錄敘述不實／證據不足——全部已修。
- 候選驗證 `validated`／144 entities／issues 0；`unmetReviews` 只剩既有的真人 Colab L5。
- 完整 20 項 gate 於 2026-09-09 通過。

~~**下一步是 LP-210C**~~ **✅ 2026-09-14 完成（見上一節）**。
英文 slug 是可選的後續增補（填帳本的 `slug` 欄位），純增補、不影響任何 ref 或 review。

## LP-210A（2026-09-07 已實作）

**狀態：完成並停在原訂停點。** 交付內容與規則提案見
[`topic-id-migration.md`](topic-id-migration.md)：

- `scripts/learning/references.py` 新增 `topic_vocabulary()`，name／id 雙索引；
  重複 id、不合格式 id 會讓**整份詞彙表**拒絕解析，`unknown_topic_id`／`stale_topic_id`／
  `unknown_topic` 分別擋未知 id、id-name 錯配與 alias 冒充 canonical name。舊 name-only ref 不受影響。
- `scripts/migrate_topic_ids.py --dry-run --report <path>`：唯讀盤點，連跑兩次 byte-identical，
  不寫 `data/topics/topics.json`；沒帶 `--dry-run` 以 exit 2 拒絕。
- 測例掛在既有 `tests/test_learning_references.py`（20 tests）與 `tests/test_learning_contracts.py`（11 tests），
  run_all 仍是 20 項。
- 盤點結果：181 topics／0 個已有 id、1,583 aliases、15 筆 authored 引用（全 canonical）、25 個 consumer 檔案；
  候選 id 規則四種都帶 `approved: false`。
- **已做三輪非作者審查**（Codex CLI 唯讀）：判定依序 FAIL → FAIL → WARN，發現皆已處理；
  五項關鍵修正的變異驗證由第三輪審查者獨立重跑成立。最後一輪剩下的三項只需改文件，已改完。
  對照表在 `topic-id-migration.md` §8；guide／question／catalog 的同類快取問題屬既有，
  已列為獨立後續項目（`topic-id-migration.md` §5），不在本包。

**下一個 session 不要直接接 LP-210B**：先取得 `topic-id-migration.md` §3「未決事項」A–D 的裁決。
特別注意 §7 的警告——**只寫詞彙表就會讓現有 12 筆 ref 立刻 `stale_vocabulary`**，
B 必須是「寫 id ＋ 更新 ref hash ＋ 重審 review」的原子包。以下原始任務描述保留為當初的範圍界定。

這是建議，尚未實作或授權為 production migration。目標是先建立「stable topic ID 相容層與遷移盤點」，讓後續第二主題可增加 source 而不把中文 display name 當永久主鍵。不要在同一包啟動 LP-220、LP-230 或批量改寫 181 個 topic。

可觀察結果：給 resolver 一個帶 stable `id` 的 topic fixture 時，`id + name + vocabularyHash` 可精確解析；舊的 `name + vocabularyHash` reference 仍相容；未知 ID、重複 ID、ID/name 指向不同 topic、把 alias 當 canonical name 都 fail closed。另有 deterministic dry-run inventory，列出 canonical topics、aliases、現有 refs 與需遷移 consumers，但不寫 production vocabulary。

建議步驟：

1. ✅ 建立 consumer inventory，至少覆蓋 `scripts/learning/references.py`、`scripts/build_learning_assessment.py`、`scripts/assign_question_topics.py`、`scripts/export_topic_heat.py`、`scripts/export_concept_graph.py`、`scripts/build_glossary.py`、`frontend/src/features/learning/types.ts`、`content/learning/**/topicRefs` 與 topic mapping/analysis payload。把結果寫入建議的新文件 `specifications/learning-platform/topic-id-migration.md`。
2. 在 fixture 先提出 ID 格式、唯一性、alias 與 display-name 相容規則；不要從中文名稱直接假設永不變的 slug。用碰撞報告、理由與非作者審查收斂方案，不預設某個 slug 規則已獲批准。
3. 現有 `schemas/learning/common.schema.json` 已允許 optional `TopicRef.id`，`scripts/learning/references.py` 也會核對傳入的 ID/name pair；在此基礎補齊 vocabulary ID 唯一性與負向 fixture。舊 ref 可省略 `id`，新 ref 帶 `id` 時必須同時核對 canonical name，alias 仍不可冒充 canonical name。只有規則確定且現有 schema 表達不足時才修改 schema。
4. 更新 `tests/fixtures/learning/references/source-tree.json`、`tests/test_learning_contracts.py` 與 `tests/test_learning_references.py`，用真失敗 fixture 驗證重複、錯配、未知與 alias 案例。若 TypeScript 型別需要調整，再改 `frontend/src/features/learning/types.ts`；目前 `TopicRef.id` 已是 optional，不要無理由重寫 frontend。
5. 建議新增一支 migration CLI（候選路徑 `scripts/migrate_topic_ids.py`，目前不存在），提供 `--dry-run --report <path>`，只讀現有 SSOT 並產生 deterministic proposal/inventory；連跑兩次 byte-identical，預設不得覆寫 `data/topics/topics.json`。所有 subprocess 都要明確 `cwd`。
6. 交給非作者讀回 ID 規則、碰撞、歷史 ref 相容與 consumer completeness。到此停下；canonical vocabulary 寫入、全量 reference rehash、review invalidation 與 migration activation 應成為下一個獨立變更包。

LP-210A 局部驗收建議；第三條只在上述候選 CLI 已建立後執行：

```bash
uv run python tests/test_learning_contracts.py
uv run python tests/test_learning_references.py
uv run python scripts/migrate_topic_ids.py --dry-run --report /tmp/ipas-topic-id-migration.json
git diff --check
```

如果改了 `frontend/src/`，另跑 `(cd frontend && npm run build)`。因這個 task 會觸及共用 schema／resolver／topic data path，交付前仍須跑完整：

```bash
UV_CACHE_DIR=/tmp/ipas-uv-cache uv run python tests/run_all.py
```

完整 gate 必須是 20/20，不能以 `--skip-browser` 冒充 release pass。若環境不能建立瀏覽器 socket，明確回報 blocked；不要把 skip 結果記成通過。Jupyter socket 只在另行重驗 Notebook L0–L3 時需要，不是 LP-210 或 `run_all.py` 的前提。

LP-210A 停點：沒有完成獨立規則審查與完整 gate前，不修改 canonical `data/topics/topics.json`，不批量回填 `topicRefs[].id`，不重算／覆蓋既有 review，不建立第二詞彙表，也不開始第二主題內容。

## 正式發布前仍待完成

這些工作不是 LP-210A 的一部分：

1. 為 notebook source 選擇不會誤觸 production deploy 的版本固定流程（例如獲授權的專用來源分支 checkpoint），取得真實 commit SHA；push main 會觸發部署，不能拿它當一般版本固定步驟。現在工作樹未 commit，不能預造 blob URL。
2. 依 [`content-and-labs.md`](content-and-labs.md) 的規則，由站台 build metadata 注入 `https://colab.research.google.com/github/<owner>/<repo>/blob/<commit>/<path>`；不要把 URL 嵌回 notebook 造成自我雜湊。
3. 由真人以該 commit 的實際 starter／solution、CSV 與 split manifest 在空白 Google Colab 依序完整執行並記錄 L5 evidence。現有 model、nbclient 或本機 Chromium 結果不能代替。
4. URL、Lab metadata 或 subject/dependency/content hash 一旦改變，舊 review 不可沿用；以 exact 新 hash 建立真實 human review record，再執行正式 `build_learning_content.py --check` 與完整 20 項 gate。
5. publication gate 無 unmet/invalid review且 production isolation 仍通過後，才進行 production promotion；merge／部署沿用 repo 的授權與 workflow，不把 L5 gate 誤套成所有一般 commit 的前置條件。

## 維護者已裁決的事項（保留紀錄）

LP-210A 當時停在這裡：`topic-id-migration.md` §3 的未決事項 A–D 要由維護者決定，
模型不得代為決定 id 字面規則。維護者已於 2026-09-09 裁決 A、B、D（C 仍未決），
LP-210B 據此完成。下表保留作為決策紀錄。

| 代號 | 要決定的事 | 為什麼不能由模型決定 |
|---|---|---|
| A | id 用什麼字面 | **已裁決**：不具語意的穩定代號＋同一 SSOT 的語意對應欄位；英文 slug 降為可選後續增補 |
| B | redirects 的欄位名稱與結構 | **已裁決**：由 `topic_id_assignments.json` 指派帳本承載，join 鍵 `canonicalName ∪ previousNames` |
| C | `?c=<中文名>` 舊分享連結的相容期 | **已裁決（2026-09-14）**：過渡期，到期日 2026-12-31；相容層（id → 正式名稱 → `previousNames`，命中舊名改寫成 id）到期後依 `topic-id-migration.md` §10.4 移除 |
| D | 哪一個 consumer 先把 `id` 轉為必填 | **已裁決**：全部一起，因為這一包本來就是原子的 |

## 可直接貼給 Claude Code 的開場 prompt（LP-210C 之後）

LP-210 三包都已完成，C 也已裁決。之後可選的獨立工作：英文 slug（純增補）、
`topic-id-migration.md` §5 列的 `guide()`／`question()`／`catalog()` 快取版本問題，或 2026-12-31 之後依 §10.4 移除舊名相容層。

```text
先讀 CLAUDE.md、specifications/learning-platform/claude-code-handoff.md 與 topic-id-migration.md（§9、§10），唯讀檢查 git status/diff；不要 reset、clean、push 或 deploy。LP-210A／B／C 已完成：181 個穩定代號在 data/topics/topics.json，TopicRef 是 {id, name}，兩份標註、三個快取、topicHeat.json、conceptGraph.json 都同時帶 id，前端 /concepts?c= 以 id 為鍵並保留舊中文名相容層（過渡期到 2026-12-31）。接著做＜英文 slug 增補／§5 的 guide()/question()/catalog() 快取版本修正／到期移除舊名相容層＞。不得建立第二詞彙表、不得改動已指派的 id、不得重跑 OCR/API、不得假造 review 或把 preview 當 production。先回報寫入範圍，再依局部測試與完整 20 項 gate 驗收，並交非作者審查。
```

原 LP-210C 的開場 prompt 保留在 git 歷史（本檔 2026-09-09 版）。

不依賴任何裁決、可隨時進行的獨立工作：`topic-id-migration.md` §5 列出的既有項目——
把 `guide()`／`question()`／`catalog()` 的「快取資料與 `input_hashes` 版本可能不同」一併修掉。
