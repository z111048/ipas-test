# 不平衡分類：從矩陣回答業務問題

## context

設備異常只占觀測的 5%。維護團隊問：「模型抓到多少需要檢查的設備？派出去的檢查有多少是真的異常？」這兩句分別對應 recall 與 precision。只報 accuracy 會把最重要的少數類錯誤藏起來。

本單元使用人工指定的 400 筆混淆矩陣練習，不把數字冒充模型實跑結果：TP=12、FN=8、FP=18、TN=362，正類是「需要檢查的異常」。

## concept_bridge

先固定矩陣方向：列是真實類別，欄是預測類別；排列為 `[[TN, FP], [FN, TP]]`。每個指標回答不同問題：

- accuracy = `(TP + TN) / N`：所有判斷中答對的比例。
- precision = `TP / (TP + FP)`：發出正類告警後，有多少是真的。
- recall = `TP / (TP + FN)`：所有真實正類中，抓到多少。
- F1 = `2 × precision × recall / (precision + recall)`：precision 與 recall 的調和平均。

分母是辨識指標的最快方法。precision 的分母是「預測為正」；recall 的分母是「實際為正」。若交換兩者，成本解釋也會跟著顛倒。

原 PDF 的 pageIndex 154 所印 recall 分母與上述定義不一致；本站不宣稱官方已發布勘誤。本單元依 scikit-learn 的分類指標定義採 `TP / (TP + FN)`，並以真實正類總數檢查分母。

## worked_example

先預測：模型 accuracy 會比全負類 baseline 的 0.95 高還是低？

逐步計算：總數 `N=12+8+18+362=400`；accuracy=`374/400=0.935`；precision=`12/30=0.4`；recall=`12/20=0.6`；F1=`2×0.4×0.6/(0.4+0.6)=0.48`。

全負類模型答對 380 筆，accuracy=0.95，卻有 TP=0、FN=20，因此對異常的 recall=0。這不是說 0.935 的模型一定可上線，而是證明 accuracy 排名與異常偵測目標可能衝突。

請把同一組數字翻成工作語言：20 台真正異常設備中抓到 12 台、漏掉 8 台；共派出 30 次檢查，其中 18 次是誤報。團隊現在可以討論漏報與誤報的成本，而不是只比較一個總分。

## guided_practice

第一步，不看公式，從「30 次告警中 12 次正確」寫出 precision。第二步，從「20 台異常中抓到 12 台」寫出 recall。第三步，用原始整數重算 F1，將每一步保留至少四位小數，最終誤差不得超過 0.001。

接著在同一組 400 筆、20 筆實際正類的條件下，改成 TP=17、FN=3、FP=35、TN=345。先預測 precision 與 recall 的方向，再計算驗證：precision 約 0.3269，recall=0.85。提示逐步減少：先標分母、再代數字，最後自行解釋「抓漏改善、誤報增加」的取捨。

## independent_practice

設計兩個模型 A、B 的混淆矩陣，讓 A accuracy 較高但 recall 較低。每個矩陣總數固定 400、實際正類固定 20，所有格必須是非負整數。交付矩陣、四個指標與 100–180 字的選擇理由；理由必須明示哪種錯誤成本較高。

## misconceptions

錯法一：「95% accuracy 表示模型抓到 95% 異常。」可觀察症狀是把 accuracy 當 recall。修正理由：accuracy 分母是全部樣本，recall 分母只是真實正類。

錯法二：「precision=TP/(TP+FN)。」可觀察症狀是報出的 precision 等於正類召回率。修正理由：precision 問的是告警可信度，分母必須是所有預測正類 `TP+FP`。

錯法三：「F1 比 baseline 高，所以可以上線。」可觀察症狀是報告沒有告警量、成本、閾值或資料漂移。修正理由：F1 不含業務成本，也不證明資料代表部署環境。

## assessment_reflection

通過證據包括：矩陣方向標示、accuracy／precision／recall／F1 的手算與程式重算一致（誤差 ≤0.001）、全負類 baseline 比較，以及一段把 FP/FN 對應到設備維護後果的說明。

若交換 precision/recall、漏寫正類定義，或只用 accuracy 下結論，本項必須重做。

來源：scikit-learn〈Metrics and scoring: quantifying the quality of predictions〉與 `confusion_matrix` 文件，https://scikit-learn.org/stable/modules/model_evaluation.html（查核 2026-09-07）；iPAS 指引關於嚴重類別不平衡時 accuracy 可能誤導的原文定位由 GuideRef 綁定。注意：本單元公式依外部官方技術文件與定義核對，不以可能有排版錯誤的教材公式取代。
