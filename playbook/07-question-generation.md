<!-- 2026-08-07: 新增。小節粒度出題（codex CLI）的進行中任務紀錄。
     OCR 那條線已完工，見 06；本檔接手它的待接清單第 1 項。 -->

# 07 — 小節粒度出題（進行中）

**狀態：單章試跑完成並人工核對通過，全量前缺一道自動驗證。**
下一步是「接上答案交叉驗證」，理由見 §4。

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

專案裡已有現成機制可接：`multi_ai_pipeline.py` 的「三 AI 答題驗證」——
gemini／codex／claude 各自作答，2 個以上答錯就寫進 `flagged.json` 待人工處理。
需要三個 CLI 都已認證。

## §5 待接工作（依順序）

1. **接上答案交叉驗證**（全量前的必要條件，見 §4）。
   把 `multi_ai_pipeline.py` 的三 AI 答題驗證接進這條 codex 線，
   或另寫一支只做「獨立作答 + 比對標記答案」的驗證腳本。
   輸出要能標出不一致的題目供人工裁決。
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
