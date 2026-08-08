# 05 — 給未來 session 的信

寫於 2026-07-13，Fable 5。這是使用者唯一一次用這個等級的模型，此後由 Sonnet/Opus/Haiku
接手。playbook 的其他檔案是制度；這封信是制度沒涵蓋、但我認為對這個環境最重要的三件事，
加上這套制度會怎麼壞。

## 一、這個專案的真正瓶頸是「資料信任」，不是功能

使用者要把這個平台商品化。商品化的教材/題庫產品，使用者流失的原因不會是少一個功能，
而是**一題答案錯、一段教材與官方 PDF 不符、一處文案洩漏 AI 生成**。所以：

- 任何動到 `questions/`、`guideContent/`、考題詳解的任務，內容正確性檢查
  （`02-judgment.md` §5）的優先級高於速度。寧可回報「修了 3 題、驗了 3 題」，
  不要「修了 30 題、驗了 0 題」。
- git log 顯示近期工作大量是逐題修資料（Q40 溢出、Q46-48 完整性…）。這類任務
  的高 ROI 改進是**寫成可重複的檢查腳本**（例如：掃全部題目 JSON 驗 schema、
  選項數、答案域、文案違禁詞），放 `tests/` 或 `scripts/`，一次投資每次受益。
  這是我建議的第一個主動提案（先問使用者再做）。
- 同理，s1c4 手動補回目前是「文件裡的 code block」，最脆弱的形態。建議提案把它
  變成 committed 腳本 `scripts/fix_s1c4_headings.py`，甚至由
  `export_guide_outline_data.py` 收尾自動呼叫。

## 二、gitignored 目錄裡躺著花錢才能重建的資產

`pages_cache/`、`audit_cache/`、`exam_pages_cache/` 是 Gemini API 花錢跑出來的，
git 救不回。兩個具體行動：
- 任何 `--force` 或會覆蓋快取的操作前，先
  `tar czf ~/backups/ipas-cache-$(date +%F).tar.gz data/*/pages_cache data/*/exam_pages_cache`
  （目錄不存在就先建）。花 10 秒，省一次 API 全量重跑。
- `data/中級/exam_pages_cache/` 在 git status 是 untracked（.gitignore 沒列它）。
  這是懸而未決的政策問題：提交（資產入庫）或補進 .gitignore（與其他快取一致）。
  **問使用者**，不要自行決定。

## 三、使用者的介面語言與工作節奏

- 所有回覆繁體中文（記憶檔有，但值得重複：不是簡中、不是日文）。程式碼與指令原樣。
- 使用者的訊息風格短、目標導向，常一次丟一個具體症狀（「Q40 選項跑版」）。
  這種訊息背後通常有一批同型問題——修完指名的那個後，主動 grep 同型症狀並回報
  「另外發現 N 個同樣問題，要一起修嗎」，這是最受歡迎的加值動作
  （`02-judgment.md` §3 反例已把「鄰近同症狀」劃入原任務範圍）。
- WSL2 環境：dev server 要 `--host`；路徑全是 Linux 側，不要碰 /mnt/c。

## 這套制度最可能的退化方式（摘要，全文在 04-maintenance.md §5）

最危險的一種：**「這次情況特殊」**。忙的 session 會想跳過派工、跳過 fresh-context
驗收、跳過 s1c4 補回。制度的價值恰恰在你不想遵守的那次——那次通常就是出事的那次。
判準已經留了快路徑（小任務自己做、可逆細節不用問），不在快路徑內就照走。

第二危險：**文件與現實漂移**。我今天已修掉一批（舊 CLAUDE.md 不知道 `@data-mid` 和
`--use-guide-tree` 的存在）。你發現文件錯就當場修 pipeline-reference.md，
這是 04-maintenance §1 明文允許的，不需要等誰批准。

## Harness 的極限（誠實條款，繼承自 02-judgment.md §6）

制度能把執行品質補到接近我的水準；補不了的是：模糊需求的解讀、文案語感、
題目好壞的最後一成、專業內容的對錯直覺。遇到這些：多版本讓使用者挑、回到 PDF
原文為準、或明說做不到。假裝有把握比承認不確定貴得多。

## 交接（未完成項目）

- 本次 session 交付 A–G 全部完成，無未完成項目。
- 兩個待使用者決定的提案（上文）：①題庫自動檢查腳本 ②s1c4 修正腳本化
  ③exam_pages_cache 的 git 政策。下次 session 開場可以提。
- `playbook/` 尚未 commit（使用者沒要求就不 commit 是本 harness 的規矩）。
  建議 commit message：`docs: add playbook — session protocols and slimmed CLAUDE.md`。
