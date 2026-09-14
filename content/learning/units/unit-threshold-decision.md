# 用 validation 成本選閾值，再凍結決策

## context

模型輸出異常機率後，`0.5` 並不是自然法則。設備維護團隊估計一次漏報（FN）的相對成本是 20，一次誤報（FP）的相對成本是 1。你的任務是在 validation 選閾值，凍結規則後只讀一次 test，回答是否值得先做有限範圍告警試點。

這裡的成本是教學假設，不是貨幣、真實事故率或上線承諾。報告必須保留假設，讓決策者能改用 FN=5 做敏感度比較。

## concept_bridge

候選閾值固定為 `[0.05, 0.10, ..., 0.95]`。每個閾值把 probability 轉成 `score >= threshold` 的正類判斷，再用 validation 計算：

`average_cost = (20 × FN + 1 × FP) / N_validation`

先選成本最低者；若成本相同，選 recall 較高者；若仍相同，選較小閾值。明寫 tie-break 能讓結果可重現，也避免作者看到 test 後臨時挑一個看起來較好看的閾值。

模型參數、特徵、資料切分、成本與 threshold 都在 test 前凍結。test 只回答「這個已選方案在未參與選擇的資料上如何」，不能用來再挑一次。

## worked_example

假設 validation 有 400 筆，三個候選結果如下：

| threshold | FN | FP | recall | 每筆平均成本 |
|---:|---:|---:|---:|---:|
| 0.20 | 2 | 72 | 0.90 | `(20×2+72)/400=0.280` |
| 0.35 | 4 | 31 | 0.80 | `(20×4+31)/400=0.2775` |
| 0.50 | 8 | 12 | 0.60 | `(20×8+12)/400=0.430` |

先預測最低閾值是否一定最好。答案是否定的：降低閾值通常減少 FN，卻可能增加大量 FP。此例按假設選 0.35。接著寫入 frozen decision：資料與 split hash、模型設定、threshold=0.35、FN/FP 成本及 tie-break。只有完成這張紀錄後才執行 test。

scikit-learn 官方閾值文件把機率估計與採取行動分成兩個問題，並提醒不要用同一資料同時訓練分類器與調整決策閾值（查核日 2026-09-07）。

## guided_practice

第一步，用上表驗算三個成本。第二步，加入 threshold=0.30，假設 FN=3、FP=51，判斷是否改選。第三步，建立一個成本相同的例子，依 recall、再依較小 threshold 套用 tie-break。

最後完成「凍結前／凍結後」清單。凍結前允許閱讀 train 與 validation 的指標並修改選擇規則；凍結後只允許用 test 估計一次結果與寫限制，不允許回到 threshold 搜尋。

## independent_practice

把 FN 成本改為 5、FP 成本維持 1，以相同 validation probability 重算所有候選閾值。提交完整成本表、選定閾值、與 FN=20 方案的差異及 150–250 字建議。新閾值可能相同；評分看重算與理由，不要求數字一定改變。

再提出一個真實部署前必要但此 fixture 沒有的資訊，例如實際派工容量、不同設備群的錯誤率、概率校準或時間漂移。說明它可能如何改變成本模型。

## misconceptions

錯法一：「`predict()` 預設 0.5，所以 0.5 最客觀。」可觀察症狀是報告沒有成本或容量假設。修正理由：預設閾值是通用 API 決策，不代表特定業務效用最佳。

錯法二：「test 最接近真實，應直接用 test 選閾值。」可觀察症狀是 threshold search 的 row IDs 與 test 有交集。修正理由：test 一旦參與選擇，就不能再提供獨立估計。

錯法三：「最低 validation 成本就證明可以全面上線。」可觀察症狀是把合成資料成本寫成真實金額或 SLA。修正理由：fixture 只驗流程；上線還需要代表性資料、營運容量、漂移監控與有限試點。

## assessment_reflection

通過證據包括完整 threshold 表、確定性 tie-break、frozen decision、一次 test 報告與 FN=5 敏感度分析。所有 test row IDs 必須排除在 threshold search；precision、recall 與成本要從 confusion matrix 獨立重算。

自評最後回答：正類比例改變會如何影響 precision 與派工量？低 validation 成本還缺哪些證據才能支持試點？若真實設備是重複觀測，現有切分為何不足？

來源：scikit-learn〈Tuning the decision threshold for class prediction〉，https://scikit-learn.org/stable/modules/classification_threshold.html，以及〈Post-tuning the decision threshold for cost-sensitive learning〉，https://scikit-learn.org/stable/auto_examples/model_selection/plot_cost_sensitive_learning.html（查核 2026-09-07）。
