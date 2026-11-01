<!-- 2026-11-02: 精簡（350→250 內）：歷次改版註解收成此行；§5 已完成項、§7 原交接步驟（565 題時期現況）移到
     backups/07-question-generation.md.bak-2026-11-02（更早的見 .bak-2026-08-30／-10-31）；§4a 與 §6 的金鑰狀態合併；
     §7 改寫為「擴充新考卷題解」的通用步驟；失效的 memory 引用改為內文規則。 -->

# 07 — 小節粒度出題與官方考卷題解

**狀態：小節出題已全量完成（2026-08-09，411 題通過答案交叉驗證，§5）；官方考卷題解 16 卷 815 題
（2026-10-31，§7）。仍開放：runner 沒有 `--model`（§5）。**

## §1 這條線在做什麼

`generate_questions.py` 把章節內容截到 4000 字，實測 41 章有 39 章被截、整份講義
只有 40% 進得了出題流程。改成以**小節區塊**為單位出題，覆蓋率 100%，而且
**區塊原文直接寫進 prompt**，模型不必自己去大檔案裡翻。

出題引擎改用 **codex CLI**（不是 `generate_questions.py` 的 Claude API 線）。

```bash
# 1. 切塊（已含過短區塊合併，見 §3）
python3 scripts/export_guide_sections.py
# 2. 產 prompt（單章或整科）
python3 scripts/build_codex_section_prompts.py --level 中級 --subject 2 \
    --chapter mid-s2c3 --count 2
# 3. 跑（沿用既有 runner 的驗證與續跑，不必另寫）
python3 scripts/run_codex_question_batch_generation.py \
    --run-dir data/中級/pipeline/codex_section_prompts [--limit N] [--force]
```

`build_codex_section_prompts.py` 產的 `summary.json` 刻意與
`build_codex_question_batch_prompts.py` 同格式，所以 runner 的 schema 驗證、
近似題偵測、續跑全部可以直接複用。

**產物在 `data/{level}/pipeline/`，是 gitignored 的**——換機器就沒有了。

## §2 單章試跑結果（mid-s2c3 假設檢定與統計推論，2026-08-07）

挑這章是因為它是 OCR 那輪漂移最大的（公式轉 LaTeX 後 16,689 → 24,304 字）。
14 批 28 題全數 PASS，**逐題人工核對答案 28/28 正確**；術語全部出自講義原文，
與既有題庫 0 重複。這 28 題就是 §4a 的自產校準集。

出題模型取自 `~/.codex/config.toml` 的全域預設——**runner 沒有 `--model` 參數**，
出題模型綁在個人設定上，換機器結果會不一樣（§5 待接）。

## §3 兩個已修的坑（不要退回去）

**切塊只往下拆、不回頭合併。** 372 個區塊裡有 94 個不到 300 字，最短 17 字——
出不了題卻照樣要花一次呼叫。`export_guide_sections.py` 已加
`merge_small_chunks`（`--min-chars`，預設 300）：372 → 291 個區塊。

**軟性配額在單批 2 題時完全無效。** 讓模型自由決定題型／難度／答案時，題型出現 7 種寫法
（前端題型篩選會炸），答案 A×10、B×11、C×4、D×3。現在**逐題硬性指派**——題型輪替五種 enum、
答案輪替 A→B→C→D、難度按 20/50/30 輪替，全域計數跨批次連續，指派表寫在 `summary.json`
的 `specs` 欄位可稽核。指定答案字母不傷品質：干擾項照樣要模型自己設計。

## §4 為什麼答案驗證是出題閘門

runner 只驗欄位結構與近似題（28 題出現 1 次欄位幻覺 `mid-s2c3c3`，被擋下），**不驗答案對錯**。
全量 500+ 題無法人工核；不知道對錯的題庫**比沒有題庫更危險**，因為使用者會相信它。
所以答案交叉驗證（§4a）是生成閘門，不是選配。

## §4a 答案交叉驗證

`scripts/verify_question_answers.py`，指令與輸出格式見 `pipeline-reference.md` §3。

**驗證器陣容**：網關 `--verifiers llm:<model>` 走 `llm-share.duotify.com`（OpenAI 相容，
純 stdlib `urllib`，金鑰只讀 `LLMSHARE_API_KEY`，放 gitignored 的 `BASE/.env`），每題約 2 秒；
CLI 三票 `codex`、`claude`、`claude:sonnet` 每題 30–40 秒。`codex` 同時是出題者，**它答對的
證據力最弱**，report 另記 `wrong_count_excl_codex`。沒有直接接 `multi_ai_pipeline.py`：它的
`run_validation_stage` 綁在 chapter pipeline 裡拆不出來，且當時 `gemini` CLI 已停止支援個人版
（`IneligibleTierError`）。`.env` 的 `ANTHROPIC_API_KEY`／`GEMINI_API_KEY` 曾實測 400
`API_KEY_INVALID`，之後沒有重驗——要用之前先自己測一次。

兩個防作弊設計，改腳本時不要拿掉：
- **盲答**：prompt 只有題幹＋選項，不給 explanation／tags／difficulty；
  每題在 `tempfile` 空目錄裡跑（codex `--sandbox read-only --cd <tmpdir>`、
  claude `--tools ''`），碰不到 gitignored 的答案檔。
- **選項亂序**：依 question id 決定的固定排列重排選項，答完映射回原字母。
  出題端答案是 A→B→C→D 硬性輪替，不亂序等於把規律送給驗證器，順便消掉位置偏誤。

快取不能只看 question id 或答案字母：parser 補回漏題會讓後續 ID 位移，而答案字母可能恰好
相同。每筆 answer cache 必須帶題號、題幹、A–D、答案、共用情境、`source/source_ref`，以及
**實際送入模型的有序圖片路徑、檔案 SHA-256 與 byte length**；缺少 v2 指紋、圖片不存在／
讀不到、或指紋不符一律重問。表格去答案欄裁圖也以來源 table SHA 與裁切比例內容定址，
同路徑圖片換檔不會沿用舊 verdict；模型執行期間圖片若改變，該結果直接丟棄。

考卷詳解 producer 的 v2 指紋另涵蓋題幹、A–D、官方答案／既有解析、共用情境與 blocks、
圖片 metadata、`source/source_ref`。舊 stem/options prompt 與 v1 provenance 只走明示 migration；
targeted rerun 若同名檔仍承載重編號後另一題的唯一詳解會拒絕執行。publication overlay 每筆綁
同一 v2 指紋；exporter 在寫前端檔前要求 published qid inventory 與 production **完全相等**，
缺題、額外題、key collision 或 stale overlay 都 fail closed。

**分流規則（`wrong_consensus` 欄位）**：**答錯的票彼此答案一致才是「標記答案可能真的錯」**，
票數分散只代表題目難。自產校準集 28 題三票 threshold 2 偽陽性 1 題（q012，四情境複合題，
codex 答 B、claude:sonnet 答 A）。人工裁決先看 consensus 那批。

**網關模型校準（同 28 題）**：`glm-5.2`、`deepseek-v4-pro`、`kimi-k2.7-code`、`qwen3.5:397b`、
`gpt-oss:120b`、`nemotron-3-ultra`、`mistral-large-3:675b` 都 28/28；`minimax-m3` 27/28（錯 q012），
**不進預設陣容**。驗證器強弱跟是不是大廠 CLI 無關，用校準集決定，不要憑印象挑。

### 官方考卷校準（真正的基準）

自產 28 題只能證明「驗證器不會亂噴」；官方答案是權威的，才證明「抓得出錯」。
用 `--questions-file data/{level}/questions/mock_*.json`（輸出 `pipeline/answer_verification/`）。
2026-08-07 的 771 題純文字可答官方題：`glm-5.2` 99.1%、`kimi-k2.7-code` 99.2%、
`deepseek-v4-pro` 98.7%；flagged 6 題、consensus 5 題，**逐題看過沒有一題是驗證器壞掉**，
都是答案有得吵的題——**`sample_q22` 甚至是官方答案本身可疑**（「何者*不是*特徵選取技術」，
官方答 C 迴歸分析，三模型一致答 B 主成分分析；PCA 是特徵萃取），列為勘誤候選，未動資料。

⚠️ **`images` 欄位不足以判斷圖片題**。「附圖為某資料之分佈圖」「選項＝見下方程式碼」這種
看圖才能答的題，OCR 沒掛圖時 `images` 是空的，純文字驗證器答錯毫無意義。腳本用文字啟發式
（`FIGURE_HINT`）＋空白選項偵測過濾（中級 341 題攔下 38 題）。**不要拿掉這個過濾**，
不然偽陽性率會憑空多出十倍。初級 `FIGURE_HINT` 命中 0，這條只對中級有意義。

### 圖片題：`--vision`

```bash
python3 scripts/verify_question_answers.py --level 中級 --vision --only-figure \
    --questions-file data/中級/questions/mock_mid_1141_s3.json ...
# → report_vision.json / flagged_vision.json（不蓋掉純文字那份）
```

`glm-5.2`、`deepseek-v4-*` 送圖會回 400，所以 `--vision` 自動換成 `kimi-k2.7-code` +
`qwen3.5:397b` + `minimax-m3`；指定看不到圖的模型會被擋下。同一模型文字／視覺模式答案不互通，
快取偵測到「這題現在有圖」會強制重問；快取記錄的圖檔不存在也會重跑。
中級 36 題可送圖題單票錯誤率 4.6%，與純文字同一量級。

#### ⚠️ 絕對不要送整頁 PDF（會洩題）

**公告試題 PDF 的答案印在題目表格最左欄**。第一版用整頁渲染當 fallback，整頁組有
**66% 的票直接吐出「原始答案字母」**（隨機期望 25%），裁圖組只有 19%。
**是選項亂序讓污染現形的**——抄到的是原始排序的字母，映射回去多半變錯，污染以
「錯誤率 22.9%」暴露；沒有亂序就會呈現為漂亮的高一致率被當成「驗證通過」。

現在只送 `image_*.png` 圖形裁圖，排除 `page.png` 與 `table_*.png`；沒有裁圖的題直接跳過。
報告的 **`answer_echo_rate`** 是常駐守門員，超過 40% 主控台警告。
⚠️ 試過而且更差，不要再加回來：整頁 prompt 加「請只看第 N 題」，單票錯誤率 31.8% → 37.2%。

**裁圖在哪裡**：部分舊卷的頁面資產仍在 legacy key 目錄（如初級 114 年的 `exam1/2`），題目也可能
沒有 `images` 欄位——第一眼會以為沒有裁圖。對照只在 `data/resource_catalog.json` 的 `legacyAssetKey`，
腳本的 `ASSET_KEY_ALIASES` 由它導出（見 `pipeline-reference.md` §3「考題 key／資產相容名」）。

**程式碼題 `--allow-table-crops`（預設關閉，未證實）**：程式碼只存在於含答案欄的 `table_01.png`，
此旗標裁掉左側 13%（`TABLE_ANSWER_COLUMN_FRACTION`）再送；實測 `answer_echo_rate` 14% 沒洩題，
但只有 1 題（`mid_1151_s2_q49`）走過且答錯——**它的 flag 不要當證據**。

### 兩階段設計（現在的預設）

Stage 1 用三個網關模型全掃（`glm-5.2` + `deepseek-v4-pro` + `kimi-k2.7-code`，threshold 2），
Stage 2 才把 flagged 的題 `--only-flagged` 升級到 codex + claude + claude:sonnet + 兩個網關模型、
threshold 3，輸出 `report_stage2.json`／`flagged_stage2.json` 不蓋掉全掃報告。五票 threshold 3
在校準集上偽陽性 0（q012 只有 2 票錯）——**門檻要跟著票數走，不是固定值**。
全量 stage 1 約 20 分鐘，`answers/` 快取可續跑。

## §5 全量重生（2026-08-09 完成）與剩餘待接

411 題（初級 125／中級 286）全部重生並通過答案交叉驗證；`verify_batch_answers.py` 是生成閘門：
驗不過的批次算失敗、`export_generated_questions.py` 拒絕寫進題庫、驗不到不算過。

```bash
python3 scripts/build_codex_section_prompts.py --level 中級 --subject 2 \
    --heat-total 100 --batch-target 9 --run-dir data/中級/pipeline/regen_s2
python3 scripts/run_codex_question_batch_generation.py \
    --run-dir data/中級/pipeline/regen_s2 --verify-answers
python3 scripts/export_generated_questions.py --run-dir data/中級/pipeline/regen_s2
```

> 教訓 2026-08-09：**呼叫次數才是瓶頸，不是題數**。每次 codex 呼叫固定開銷約 108 秒、
> 與要 1 題還是 9 題幾乎無關，原本一區塊一 prompt 平均每次只出 1.6 題。`--batch-target`
> （預設 9）打包連續區塊：168 批 → 53 批，區塊原文不截斷；再加**跨科目**平行（不做科目內平行，
> 近似題偵測要看同章前面批次）。4 小時 → 約 50 分鐘。規則：優化前先算「每次呼叫實際產出多少」。

> 教訓 2026-08-09：**「只支援一個等級」的假設會偽裝成模型的錯**。schema 的 `level` 曾是
> `const: 中級`，初級 6/6 全判 `subject_id mismatch`，看起來像模型不聽話。
> 規則：跨等級跑之前先 grep 硬編字串。

> 教訓 2026-08-09：**題型與素材不搭會產出無效單選題**。mid-s2c6 的框架比較表被指定「計算判讀型」，
> 四個選項各自成立、單選題有兩個正解，連兩次重生同形狀——是素材問題不是隨機。prompt 加約束
> （錯的選項必須**算錯**）後通過。規則：懷疑判定器之前先把**實際送出的 prompt 印出來**看。

剩餘：
- **中英夾雜**：已由 `audit_resources.py` 事後掃描（「小寫英文單字被中文夾住」）處理，prompt 未加規則。
- **給 runner 加 `--model`**：出題模型仍綁 `~/.codex/config.toml`（2026-11-02 `--help` 確認無此參數），
  題庫沒有可重現性。網關模型可寫死在腳本裡解掉（§6）。

## §6 模型選擇的參考資料

`~/projects/llm-test` 有網關的模型評測，`API_USAGE.md` 推薦 `kimi-k2.7-code`。
⚠️ **那份排名是「視覺辨識」的排名**——該輪把「不支援視覺」的 `glm-5.2`、`deepseek-v4-pro`、
`nemotron-3-*` 全排除了，但它們在純文字驗證任務上都是滿分（§4a）。要換出題模型應針對「出題」
另做一輪對比，不要直接套用那份結論。可複用的是 `llm_client.py`（零耦合，內建空字串重試）。

## §7 擴充新考卷題解（2026-10-31 已完成到 16 卷 815 題）

已完成中級 115 年第一次三科與初級 115 年第三次（`jr_1153_s1/s2`）。新考卷照下列順序，
全部走既有腳本，不要另寫：

1. **產題解**：`python3 scripts/run_codex_exam_reference_answers.py --level <級> --exam <key> --run`。
   先不帶 `--run` 看 prompts 是否對到 v2 canonical qid（§4a、`pipeline-reference.md` §4）。
   每題一次 `codex exec`，各卷可平行；**單題逾時帶 `--timeout 600`**（預設 240 秒會漏題）。
   跑完看 `summary.json` 與 `outputs/*.err`，補跑失敗題（`--question-id`）。附圖或圖片清單救不回的題
   （例如 `mid_1151_s3_q46/q47`，見 `pipeline-reference.md` §3）題解要人工看一眼。
   ⚠️ prompt 已加規則禁止「R2 的 block-71」「看不到附圖」「此片段」等內部字樣，範圍含
   `citations.why_relevant`（出處提示對考生可見）；改 prompt 時不要拿掉。樣題卷題號會位移，須整卷重跑；
   舊題號卷重跑後題解鍵名會換新題號，`question_topics.json` 要依題號一對一遷移。
2. **發佈**：`python3 scripts/export_exam_reference_answers.py --level <級>` → 新 JSON ＋ `stats.json`。
   exporter 要求發布 inventory 與 production 完全相等，不得手動塞檔。
3. **概念標註（gate 會擋，不可省）**：`test_every_reference_answer_has_a_signed_off_topic` 要求
   `question_topics.json` 覆蓋**每一題**題解；`tests/test_resource_catalog.py` 的 `questionCount`
   寫死（現為 815），要同步改。官方卷路徑：`assign_question_topics.py --source exam`（2026-10-31 依使用者
   決定用 `deepseek-v4-pro --model-all`，帶 `--batch-size 5 --max-tokens 16000`，預設 4000 會被推理
   用光、整批空回應——不是限流）→ `--verify-all --verify-model qwen3.5:397b` → `--backfill-ids` →
   `export_guide_exam_annotations.py` → `export_topic_heat.py` → `export_concept_graph.py`
   （順序見 `pipeline-reference.md` §5b 教訓：annotations 要先於 heat）。
   新題只能標到 `topics.json` 現有概念；模型自創的名稱進 `rejectedTopics`，不得由模型擴詞彙表。
   確實無對應概念時走 `08-topic-labeling.md` §5 的人工補簽（2026-10-31 `mid_1151_s2_q39` 即以
   `Python程式語意` 補簽，詞彙表 182、覆蓋 815/815）；模型未標的題人工補標記 `source: manual`。
4. **驗收**：`cd frontend && npm run build`、`verify_data_alignment.py --level <級>`、
   `uv run python tests/run_all.py`（21 項）；`audit_resources.py` 的 `referenceAnswers` 會核對題號。
5. 一個 commit，說明題數與 topic 覆蓋數。

**不要做的**：產題解時不順手重跑 OCR／`parse_exams_v2`（考題資產鍵改名會讓圖片掛載靜默失效；
鍵名只在 catalog 定義，見 `pipeline-reference.md` §3）；不改 `mock_*.json` 題幹；不動 `topics.json` 的 id。
