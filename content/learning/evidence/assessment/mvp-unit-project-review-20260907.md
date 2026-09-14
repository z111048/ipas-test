# MVP 單元與專題最新內容審查

審查者 `/root/content_labs`，作者 `/root/p0_baseline`；模型內容審查，並非真人教學實測或使用者批准。Root 明確委派本次 Unit/Project 內容與實際機械檢查補記。下面只對列出的 contentHash 有效；舊報告及十題答案審查保留。

本輪完整重讀三篇 Markdown、三份 Unit metadata、Project metadata、修正版 Lab source 與 L4 記錄；重新比對官方 scikit-learn 文件（2026-09-07）。

| 對象 | 本輪 hash | 結論 |
|---|---|---|
| unit-imbalanced-classification | `sha256:a8e8213fc629be53447ec321246d1cb2d04c07b1510c22671a0c7be8e76411a8` | D1 PASS |
| unit-split-before-fit | `sha256:947a4dffcddf2b0f964351d67004b00a6ebd08cff9d0c4c93787490fba33bdf1` | D1 PASS |
| unit-threshold-decision | `sha256:fb5b5b1985d5c46e6684140616bd7741d0ef3885473dc7caa5dc9e248d500e29` | D1 PASS |
| project-imbalanced-classification | `sha256:c9553d68d5ffe227115e4648f46a04b8cd33402aef2e1c65fbe5e53ec17d8152` | D1 PASS |

## 教學與計算

- split：先固定 train/validation/test，fit 型前處理只讀 train；閾值選擇與特徵可得時點分開。重複設備觀測要求 group/time 切分並解釋部署情境，沒有把單純 Pipeline 視為排除事後欄位的保證。資料流表、兩項不變條件與重做條件可觀察。
- metrics：固定矩陣 TN362/FP18/FN8/TP12 總數400、正類20；accuracy=.935、precision=.4、recall=.6、F1=.48，程式重算一致。全負類 accuracy=.95、recall=0。guided 的 TN345/FP35/FN3/TP17 同母體、precision=.326923、recall=.85。獨立任務要求兩模型矩陣及成本理由，不能只按 Run All。
- threshold：FN20/FP1 下三列成本 .280/.2775/.430，選.35；新增.30、FN3/FP51 也是.2775，recall=.85優於.35的.80，應按明示 tie-break 改選.30。成本假設、FN5敏感度及test凍結一致，不把合成成本宣稱真實績效。
- Project：四個里程碑依序要求 split→baseline/指標→validation閾值→凍結後test與試點建議；30/25/25/20權重合計100。2,000列、8特徵、100正類與1,200/400/400切分符合fixture。Lab的 `metrics.json` 提供 dataChecksum/splitHash/modelConfig/seed/costs，矩陣與四項指標實際位於 `test`，validation表另列；Project requiredFields 是交付內容標籤而非本站自動 JSON 驗證schema。`decision.md` 是待學習者補齊的草稿，並未宣稱自動通過反思評量。

## 來源與編輯層

資料洩漏定義與 train-only 前處理核對 [scikit-learn Common pitfalls](https://scikit-learn.org/stable/common_pitfalls.html)；指標公式核對 [Metrics and scoring](https://scikit-learn.org/stable/modules/model_evaluation.html)；閾值選擇隔離核對 [Tuning the decision threshold](https://scikit-learn.org/stable/modules/classification_threshold.html)，查核日均為2026-09-07。

GuideRef 的實際 sourceHash、blockIds、quote 與頁數由本輪 C1 再驗；它只把指引既有內容作概念橋接，不宣稱原指引已具完整 Lab 流程。PDF recall分母差異已直接檢視原PDF，本輪重讀新增短註，敘述中性並明言不代表官方勘誤。原PDF及Guide沒有更動；direct-view證據見 `recall-formula-direct-view.md`，新版正文hash見 `lab-semantic-review.md` 第二輪。

## 機械檢查與執行紀錄的範圍

`mvp-contract-check-20260907.json` 保存實際成功的全候選schema/ref/hash結果與8個公開實體fingerprints，包含namespace、source bindings、topic/章節、引用/先修及rubric總分。C1只是可重跑的deterministic檢查，不是其作者程式已通過獨立code review的宣稱。

Lab L0–L3：使用已封存作者execution report，核對source/fixture/split hash、L0–L3 pass、starter未完成停TODO以及真clean kernel；非作者另於空工作目錄實跑solution並做八項反例（`lab-l4-independent-result.json`）。作者允許提供機械執行證據，L4仍由非作者獨立執行審查；真人Colab L5完全沒有執行，仍須阻擋。

Blueprint/Pool/Analysis由本審查者編寫，本輪沒有自批其獨立D1或Pool A1；交另一位非作者代理核對。已完成的逐題答案review不因總體pool gate未補記而改寫，也不能把pool策展覆核冒成作者對自寫題目的獨立答題。
