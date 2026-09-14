# Lab L4 非作者語意審查

審查者：`/root/content_labs`，`independent_model`；作者：`/root/p0_baseline`。Root 明確委派本次非作者 Lab 語意檢查；這不是人類 Colab smoke，也不是使用者簽核。

最新結論（2026-09-07T12:42:26Z）：修正版的 L4 非作者語意審查與八項獨立反例檢查 **PASS**。只對下方第二輪列出的 source/Lab hash 有效；人類 L5 仍為 `not_run`。第一輪 `changes_requested` 及反例保留如下，不能當作新版的失敗或舊版的批准。

2026-09-07 第一輪結論：`changes_requested`。L5 保持 `not_run`。已完整閱讀 single notebook source、generator、verifier 與作者真實 clean-kernel execution report；沒有將作者的 L0–L3 執行成功直接當成 L4 教學語意合格。

## 第一輪輸入

| 檔案 | 原始 bytes SHA-256 |
|---|---|
| `notebooks/labs/lab-imbalanced-classification.ipynb` | `dbb6060fdd7e1fa669e04dc09e73a86d65143e25bdfb40c233b35ac59b4616a1` |
| `scripts/generate_learning_lab.py` | `fb3169c524765e05fb29e35fdc48753edc6b4845954e6ab4dd6c8147ec692c00` |
| `scripts/verify_learning_labs.py` | `d69133b82b69918f089152338cf06e638ba805b01a1d91c8614d3178e440710c` |

作者 report 所綁 source hash 與本輪 source 相同；三次 solution/starter setup+worked/空工作目錄手動上傳模擬都有真實執行時間。這證明該版本能在作者環境執行，尚未證明以下語意不變條件。

## 必須修正與重驗的項目

| 項目 | 第一輪觀察 | 重驗條件 |
|---|---|---|
| L4-01 test 凍結 | `fit-train-only` 在選 threshold 前先執行 `model.predict_proba(test[...])`。 | validation 與 FN=5 比較完成並凍結後，才讀 test features/labels 與評估；結果保留可追蹤的凍結規則。 |
| L4-02 baseline 比較 | DummyClassifier 只有 fit，沒有 predict/metrics 的實際對照。 | 在相同凍結 test 列上重算 baseline 與 logistic 指標，明示 baseline recall=0；不可用 worked example 的95%取代實測結果。 |
| L4-03 starter 可操作性 | starter 只留函式 TODO 與 print，沒有 result 格式/輸出框架，check cell 亦只有「待完成」。 | 保留完整輸出框架與可執行檢查；核心評估/選閾值仍由學習者完成。未完成時清楚阻擋，完成後能走同一套檢查，不必複製解答的核心演算法。 |
| L4-04 真資料路徑 fault | 所謂 allDataFit/testAsValidation 只修改 result 裡宣稱的 rows，沒有改實際輸入。 | wrapper 由實際傳入資料框記錄 rows；故障情境真的把全資料送進 fit 或 test 送進閾值選擇，再由範圍不變條件拒絕。僅修改報告的測例應另稱 report-tampering。 |
| L4-05 外部驗算 | verifier 信任報告的 yTrue 與 validationTable，未核對 fixture 列、完整長度或成本公式。 | 以 fixture 的 test rows/yTrue 為獨立真值；驗算所有 validation 列的矩陣、四指標、成本、最小值/tie-break、FN=5 表與 baseline，拒絕偽造表。 |
| L4-06 環境證據 | Lab pythonVersion 寫3.11，report沒有實際 Python/套件版本。 | 記錄實際執行的 Python/NumPy/pandas/scikit-learn 版本、lock hash；metadata 的版本含義與執行環境一致。 |

第一輪另直接執行 `independently_check_metrics()` 的偽造輸入：只給2個 test labels、虛構 row ID、負數 validation cost=-100、validation recall=99，原 verifier 仍接受。此為實際可重現的語意驗證漏洞，不只是對可能風險的猜測；修正後同類輸入必須拒絕。

矩陣公式、zero-division=0、固定 seed、資料與 split checksum、CPU/離線輸入、source/starter/solution 派生隔離、public答案可見而不宣稱防作弊，第一輪讀檢皆符合方向。仍須以作者修正後的 source/metadata/variants/report 重新綁定 hash 並重驗，不能沿用本輪完成標記。

## 後續狀態

作者已收到六項修正；Root 同意其為 L4 blocker，授權作者修正後由本審查者再做非作者讀檢。新版本尚未獨立確認前，維持 `changes_requested`。本檔不提供人類 L5 合格證據。

## 第二輪：修正版獨立重驗

| 對象 | 第二輪 fingerprint |
|---|---|
| source notebook 原始 bytes | `sha256:e271535428e2c50a5422ab80496eaf1f5bcd37502f605c0d927f31e34b4a5f31` |
| normalized notebookHash | `sha256:ec7cfde721e6728e913a0b0f8bd52aea2f10bbf0eb6fe69a9eae0a5b73959f8f` |
| Lab contentHash | `sha256:5bb3dc8b27d18e8d5407398445a7ea52791c2ae5d97de5d5131a63c3c319cb2b` |
| generator 原始 bytes | `sha256:a9a37e618f03026eb61fc53bc148123b18b808b5abc24b3d3c4179fa8fe96968` |
| verifier 原始 bytes | `sha256:1c7400e8a29795d73ad7a65af0afeaba05bcd435d66ed94f6db6d4934f3b84b1` |
| 獨立執行結果 | `sha256:043395c043ade0ec916b7dd015d654af790f381b66fb11b9a3c8306517f6b0df` |

獨立執行結果保存在 `content/learning/evidence/assessment/lab-l4-independent-result.json`。可重跑的檢查碼是同目錄 `lab-l4-probes.py`；它使用 repo-relative root、已版控的作者 L0–L3 report 快照及 single notebook source，不依賴 staging。Notebook 執行需安裝 `learning-lab` group，且本機 Jupyter 必須能建立 localhost socket。首次受限 sandbox 回報 PermissionError；經本次既有 Lab 驗收授權的自動核准，改在可開本機 socket 的環境執行，沒有呼叫外部 API 或模型。

本審查者在新的空工作目錄只放 CSV 與 split manifest **根層**，沒有 `fixtures/` 子目錄，啟動 clean kernel 並執行 solution 加上只讀取實際執行狀態的 audit cell。15.852 秒完成；實際 kernel Python=3.11.13、NumPy=2.4.3、pandas=3.0.5、scikit-learn=1.9.0，與作者 report 及 Lab 的 Python 3.11 系列設定一致。

| 項目 | 第二輪觀察與結果 |
|---|---|
| L4-01 | `fit-train-only` 不再讀 test_scores；先完成 FN=20/FN=5 validation 選擇，保存 frozen_threshold，才執行正常流程的 test 預測。後面的故障示範是分離的錯誤分支，不改寫主要 model/result。PASS。 |
| L4-02 | 同400列 test 實算 Dummy：TN380/FP0/FN20/TP0，accuracy=.95、recall=0、平均成本1.0；Logistic：TN266/FP114/FN7/TP13，accuracy=.6975、recall=.65、平均成本.635。此對照有意展示 accuracy 與成本排序可能不同，不能推論真實上線績效。PASS。 |
| L4-03 | starter 只把 evaluate/select 核心函式留下 TODO，保留 metrics.json/decision.md 輸出框架與完整檢查 cell；`solution-note` 被排除，outputs/counters清空。未完成的函式會清楚中止，作者重跑 report 亦證明停在 TODO，不是假完成。PASS。 |
| L4-04 | Audit 確認正常 fit 實際輸入1200列；故障 fit 真正把2000列送入另一個模型，其記錄包含test，後續檢查拒絕。錯誤 threshold 選擇真傳test的400列，實際記錄等於test，後續檢查拒絕。沒有僅靠手填虛假row IDs冒稱真操作。PASS。 |
| L4-05 | verifier 重新從 immutable fixture/split 建立獨立模型，比對19列 validation 的矩陣/指標/成本/threshold、FN=5敏感度與400列test的IDs/labels/predictions，以及Dummy結果。八種下述篡改皆被拒絕。PASS。 |
| L4-06 | 實際 kernel版本、套件版本與作者 report 比對通過；Lab的lock hash仍需source resolver驗證。network欄只說notebook沒有使用外部網路，不冒稱已建立OS網路防火牆。PASS。 |

八項獨立變異：空 fit rows、虛構 test row ID、只保留兩筆 test labels、負 validation cost、validation recall=99、竄改 FN=5 成本、偽造 Dummy recall、錯誤 threshold。每一項都從本次真實執行的完整 metrics 深拷貝，只改該項，再送入外部驗算；八項皆拒絕。正常 metrics 本身先通過，避免把「所有輸入都失敗」誤當防錯成功。

指標 Unit 新增的原 PDF 公式短註也已獨立核對：新版正文 raw hash `sha256:f97f13141a308ee2a90df4bc6f0245341cba09b6893813b853819aa400ba24c5`，Unit contentHash `sha256:a8e8213fc629be53447ec321246d1cb2d04c07b1510c22671a0c7be8e76411a8`。語句只描述原頁與正確召回率定義的差異，不宣稱官方已發布勘誤；兩筆 direct-view/PDF evidence 都有hash。十題題稿與其獨立審查證據未更動。舊 Unit 正文 hash 的歷史審查不能充作新版正式批准；目前 Unit 仍是 in_review、沒有借用舊正式review IDs。

本輪可記錄 machine L4 semantic review；不能由此設定 human L5、已上線、完整 production gate 或 learner verified completion。`decision.md` 是要求學習者補齊的草稿，評量仍須看理由與限制，Run All/下載本身不能證明學會。
