<!-- 2026-08-07: 新增。小節粒度出題（codex CLI）的進行中任務紀錄。
     OCR 那條線已完工，見 06；本檔接手它的待接清單第 1 項。 -->

# 07 — 小節粒度出題（進行中）

**狀態：單章試跑完成、答案交叉驗證已接上並在單章校準過（見 §4a）。**
全量跑之前還缺的是 §5 剩下的項目。

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

**產物在 `data/{level}/pipeline/`，是 gitignored 的**——換機器就沒有了，
但同一台機器上會留著。

## §2 單章試跑結果（mid-s2c3 假設檢定與統計推論，2026-08-07）

挑這章是因為它是 OCR 那輪漂移最大的（新舊相似度 0.739，公式轉 LaTeX 後
16,689 → 24,304 字）——要驗證「OCR 變好 → 題目變好」的假設。

14 批 28 題，全數 PASS。**逐題人工核對答案，28/28 正確**；術語（Dunn's test、
Fisher's exact test、Mann-Whitney、變異數齊一性、效果量、中央極限定理）
全部出自講義原文，模型沒有補外部知識；與既有題庫 0 重複、內部 0 重複。

出題模型：`gpt-5.6-luna`（reasoning effort `high`），來自 `~/.codex/config.toml`
的全域預設——**runner 沒有 `--model` 參數**，所以出題模型目前綁在個人設定上，
換機器結果會不一樣。要固定得自己加參數，見 §5。

## §3 兩個已修的坑（不要退回去）

**切塊只往下拆、不回頭合併。** 372 個區塊裡有 94 個不到 300 字，最短 17 字——
只有標題沒有內文，出不了題卻照樣要花一次呼叫。`export_guide_sections.py` 已加
`merge_small_chunks`（`--min-chars`，預設 300）：372 → 291 個區塊，過短的降到 3 個。

**軟性配額在單批 2 題時完全無效。** 第一輪讓模型自由決定題型／難度／答案，結果：
題型出現 7 種寫法（「情境應用型」與「應用情境型」並存，還多出「判讀型」
「概念應用型」，前端做題型篩選會炸）；答案 A×10、B×11、C×4、D×3，猜 A/B 有優勢。
現在改成**逐題硬性指派**——題型輪替五種 enum、答案輪替 A→B→C→D、難度按
20/50/30 輪替，全域計數跨批次連續，指派表寫在 `summary.json` 的 `specs` 欄位可稽核。
修正後：題型 5 種固定、答案 7/7/7/7、難度 易6/中14/難8。

指定答案字母不會傷害品質——模型只是把正確內容放到指定位置，干擾項照樣要自己設計。

## §4 為什麼全量前要先接驗證

**28 題出現 1 次欄位幻覺**（`chapter_id` 被寫成 `mid-s2c3c3`，其他欄位全對），
約 3.6%。runner 的驗證擋下了，重跑那批就過——這部分機制是夠的。

問題在**答案正確性目前沒有任何自動把關**。runner 只驗欄位結構與近似題，
不驗答案對不對。單章 28 題我人工核得完，全量 500+ 題不可能。
沒有驗證就全量跑，會拿到一份不知道對錯的題庫——**那比沒有題庫更危險**，
因為使用者會相信它。

## §4a 答案交叉驗證（2026-08-07 完成）

`scripts/verify_question_answers.py`，指令與輸出格式見 `pipeline-reference.md` §3。

**為什麼沒有直接接 `multi_ai_pipeline.py`**：它的 `run_validation_stage` 綁在
chapter pipeline 裡（自己出題→審核→完稿→驗證），拆不出來單獨用；而且
**`gemini` CLI 在本機已經不能用**——`IneligibleTierError: Gemini Code Assist for
individuals`，這個 client 被停止支援。`.env` 裡的 `GEMINI_API_KEY` /
`ANTHROPIC_API_KEY` 是遮罩過的佔位字串（實測 400 `API_KEY_INVALID`），
所以走 API 補第三家模型這條路現在也不通。

**2026-08-07 下午補上網關驗證器**：`--verifiers llm:<model>` 走
`llm-share.duotify.com`（OpenAI 相容，純 stdlib `urllib`，金鑰只讀
`LLMSHARE_API_KEY`，已放進 gitignored 的 `BASE/.env`）。這條線把模型家族補回三個以上，
而且**每題約 2 秒 vs CLI 的 30–40 秒**。§6 那句「視覺榜單不等於命題榜單」成立但方向相反——
被那輪以「不支援視覺」排除的 `glm-5.2`、`deepseek-v4-pro` 在這個純文字任務上都是滿分。

CLI 三票：`codex`、`claude`、`claude:sonnet`（`--verifiers` 可調）。
`codex` 同時是出題者，**它答對的證據力最弱**，report 另記
`wrong_count_excl_codex`。codex 帳號目前只准 `gpt-5.6-luna`（試過 `gpt-5.6`、
`gpt-5.6-codex` 都被擋），換不掉。

兩個防作弊設計，改腳本時不要拿掉：
- **盲答**：prompt 只有題幹＋選項，不給 explanation／tags／difficulty；
  每題在 `tempfile` 空目錄裡跑（codex `--sandbox read-only --cd <tmpdir>`、
  claude `--tools ''`），碰不到 gitignored 的答案檔。
- **選項亂序**：依 question id 決定的固定排列重排選項，答完映射回原字母。
  出題端的答案是 A→B→C→D 硬性輪替的，不亂序等於把規律送給驗證器，
  順便消掉位置偏誤。

**校準結果（mid-s2c3 28 題，答案已人工確認全對）**：flagged 1 題，
偽陽性率 3.6%，其餘 27 題三票全中。偽陽性是 q012——四個情境（甲乙丙丁）
各自判型一／型二錯誤的複合題，codex 答 B、claude:sonnet 答 A、claude 答對 D。

從這裡得到分流規則，已寫進報告的 `wrong_consensus` 欄位：
**答錯的票彼此答案一致才是「標記答案可能真的錯」**，票數分散（像 q012 的 A/B）
只代表題目難。人工裁決先看 consensus 那批。

### 網關模型校準（同一組 28 題，2026-08-07）

8 個候選跑完，**7 個 28/28 全對**：`glm-5.2`、`deepseek-v4-pro`、`kimi-k2.7-code`、
`qwen3.5:397b`、`gpt-oss:120b`、`nemotron-3-ultra`、`mistral-large-3:675b`。
唯一失手的是 `minimax-m3`（27/28，錯在 q012 那題，答 C），所以它**不進預設陣容**。

有趣的是 q012 這題把 codex 和 claude:sonnet 都騙了，開源模型幾乎全對——
驗證器的強弱跟它是不是大廠 CLI 沒什麼關係，該用校準集決定，不要憑印象挑。

### 官方考卷校準（2026-08-07，這才是真正的基準）

前面兩輪都是拿**自己生成的 28 題**當基準，只能證明「驗證器不會亂噴」，
不能證明「抓得出錯的答案」。真正的基準是官方考卷——答案是權威的。
`--questions-file` 就是為此加的：

```bash
python3 scripts/verify_question_answers.py --level 中級 --workers 8 \
    --questions-file data/中級/questions/mock_mid_1141_s1.json ...
# → data/{level}/pipeline/answer_verification/{report,flagged}.json
```

**771 題純文字可答的官方題**（中級 303、初級 468）跑完：

| 驗證器 | 中級 303 | 初級 468 | 合計正確率 |
|---|---|---|---|
| `llm:glm-5.2` | 錯 1 | 錯 6 | 99.1% |
| `llm:kimi-k2.7-code` | 錯 2 | 錯 4 | 99.2% |
| `llm:deepseek-v4-pro` | 錯 5 | 錯 5 | 98.7% |

flagged 共 6 題（0.78%），consensus 5 題。**逐題看過，沒有一題是驗證器壞掉**：
`mid_1151_s3_q30`（高變異 vs 過擬合）、`exam2_q36`（prompt injection 防禦策略）、
`sample_q48`（步驟排序）都是兩個答案都說得通的爭議題；
**`sample_q21` 甚至是官方答案本身可疑**——問「何者*不是*特徵選取技術」，
官方答 C 迴歸分析，三個模型一致答 B 主成分分析（PCA 是特徵*萃取*不是*選取*，
逐步迴歸則確實是選取法）。這題值得列入勘誤候選，本輪沒有動任何資料。

結論：consensus 這個分流欄位是有效的——它挑出來的都是「答案真的有得吵」的題。

⚠️ **`images` 欄位不足以判斷圖片題**。第一輪 5 個 consensus 裡有 4 個是
「附圖為某資料之分佈圖」「選項＝見下方選項 B 程式碼」這種**看圖才能答**的題，
OCR 沒把圖掛上去所以 `images` 是空的。純文字驗證器答錯它們毫無意義。
現在改用文字啟發式（`FIGURE_HINT`）＋空白選項偵測，中級 341 題攔下 38 題。
**改這支腳本時不要拿掉這個過濾**，不然偽陽性率會憑空多出十倍。

### 圖片題：`--vision`（2026-08-07）

```bash
uv run python3 scripts/verify_question_answers.py --level 中級 --vision --only-figure \
    --questions-file data/中級/questions/mock_mid_1151_s2.json ...
# → report_vision.json / flagged_vision.json（不蓋掉純文字那份）
```

`glm-5.2`、`deepseek-v4-*` 送圖會回 400 `does not support image input`，所以 `--vision`
自動換成 `kimi-k2.7-code` + `qwen3.5:397b` + `minimax-m3`；指定看不到圖的模型會被擋下。
需要 PyMuPDF，**用 `uv run`**。同一個模型在文字／視覺模式的答案不互通，
快取偵測到「這題現在有圖」會強制重問。

**圖片來源決定可信度，差距 7 倍**（中級 37 題）：

| 來源 | 題數 | 單票錯誤率 | flagged |
|---|---|---|---|
| `crop` 已裁好的題目附圖 | 21 | **3.2%** | 1 |
| `page` 整頁 PDF 渲染 | 16 | **22.9%** | 3 |

整頁渲染差是因為一頁上有多題多圖，模型得自己猜哪張圖是這題的。
1141 三份卷從來沒跑過裁圖流程（`frontend/public/pdf-assets/中級/mid_1141_s*/` 不存在），
只能退回整頁。報告的 `by_image_source` 會把兩者分開統計，
**`page` 來源的 flag 是弱證據，不要當成答案可疑的依據**；要提升就得先幫那三份卷補裁圖。

裁圖組唯一的 flag `sample_q7` 也是偽陽性：四格圖配對題，官方答 B（我看圖確認正確），
兩個模型把 (b) 語義分割與 (c) 物件偵測對調——多格圖的方位判讀是已知弱點。

⚠️ **試過而且更差，不要再加回來**：在整頁渲染的 prompt 裡加「本頁有多題，請只看第 N 題」，
同一批 15 題的單票錯誤率從 31.8% 升到 37.2%（6 題投票變動，方向隨機）。
問題不在提示寫法，在整頁掃描本身雜訊太多。

初級 468 題全部沒有圖片題（`FIGURE_HINT` 命中 0），所以這條只對中級有意義。

### 兩階段設計（現在的預設）

Stage 1 用三個網關模型全掃（`glm-5.2` + `deepseek-v4-pro` + `kimi-k2.7-code`，
threshold 2），Stage 2 才把 flagged 的題 `--only-flagged` 升級到
codex + claude + claude:sonnet + 兩個網關模型、threshold 3。
Stage 2 的輸出寫 `report_stage2.json` / `flagged_stage2.json`，不蓋掉全掃報告。

五票 threshold 3 在校準集上**偽陽性 0**（q012 只有 2 票錯，壓在門檻下），
比原本三票 threshold 2 的 3.6% 好。門檻要跟著票數走，不是固定值。

全量成本從「500 題 3–4 小時」降到 **stage 1 約 20 分鐘**，
只有真的可疑的少數題會付 CLI 的 40 秒。`answers/` 快取可續跑。

## §5 待接工作（依順序）

1. ~~接上答案交叉驗證~~ **已完成，見 §4a。**
2. **修中英夾雜**。28 題裡有 1 處：第 28 題選項 D「就能直接 conclude 所有組別…」。
   在 prompt 的輸出規範加一條「不得中英夾雜，術語英文只能以括號附註」，
   或事後用正規表示式掃。
3. **全量跑**。中級科目2 共 71 區塊（142 題）約 2 小時；三科 237 區塊約 7 小時。
   每批約 100 秒，時間是瓶頸不是錢（codex CLI 走訂閱）。
   跑完務必看 `failed` 數字並補跑失敗批次。
4. **決定產物怎麼進題庫**。目前結果停在 gitignored 的 `pipeline/` 下，
   還沒有 export 步驟把它併進 `data/{level}/questions/`。
   既有的 `export_codex_mock_exam_questions.py` 是給另一條線用的，需確認能不能複用。
5. **給 runner 加 `--model`**（見 §2）。出題模型現在綁在 `~/.codex/config.toml`，
   題庫沒有可重現性。

## §6 模型選擇的參考資料

`~/projects/llm-test` 有一份 LiteLLM 網關（`llm-share.duotify.com`，OpenAI 相容）
的模型評測，`API_USAGE.md` 推薦 `kimi-k2.7-code`。

⚠️ **那份排名是「視覺辨識」的排名**——測的是從降質圖片辨識公式、讀圖表刻度、
解析合併儲存格。我們的出題是純文字，需要的是中文命題品質，**視覺榜首不會自動是
命題榜首**，而且該輪把「不支援視覺」的模型（`glm-5.2`、`deepseek-v4-pro`、
`nemotron-3-*`）全排除了，那些在純文字任務上完全可用。

要換模型應該針對「出題」另做一輪對比，不要直接套用那份結論。
可複用的是 `llm_client.py`（零耦合，內建空字串重試）與網關本身
（模型可寫死在腳本裡，解掉 §5.5 的可重現性問題）。金鑰只放環境變數
`LLMSHARE_API_KEY`，目前未設定。
