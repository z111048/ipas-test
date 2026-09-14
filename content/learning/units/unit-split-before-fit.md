# 先切分，再學習資料規則

## context

你要替設備維護團隊做異常告警模型。資料有 2,000 筆，每列是一台獨立設備的一次觀測；`row_id` 是追蹤列的識別，不是模型特徵。團隊要的成果不是一個漂亮分數，而是一份能回答「哪些資料參與了哪個決定」的切分紀錄。

學習指引說明資料品質會影響預測與決策，也介紹模型評估。本單元補上實務中最容易漏掉的一步：缺失值填補、標準化、特徵選擇與閾值都會從資料學到規則，因此必須先固定 train／validation／test，再決定每個 `fit` 可看哪些 row IDs。

交付物是一張資料流表：每個物件列出 `fit_rows`、`transform_rows`、用途及禁止用途。這張表比「我用了 Pipeline」更重要，因為 Pipeline 不知道某個欄位是否在事故發生後才產生。

## concept_bridge

把資料處理看成兩類操作：

- `fit` 會從資料估計規則，例如中位數、平均數、標準差、特徵排名或模型係數。
- `transform` 只套用已凍結的規則，例如用 train 的中位數補 validation 缺值。

切分契約固定為 60% train、20% validation、20% test。train 用來估計處理規則與模型參數；validation 用來選閾值與其他決策；test 只在方案凍結後讀一次。三組 `row_id` 必須兩兩不相交，聯集必須等於資料全集。

scikit-learn 官方常見陷阱文件建議先切分，再讓前處理只對 train 執行 `fit`，並以 Pipeline 降低錯用 API 的機率（查核日 2026-09-07）。但 Pipeline 只能管理被放進流程的轉換；如果你加入「維修後結果」這種預測當下不存在的欄位，流程仍會忠實地學到洩漏。

## worked_example

先預測：若先在全部 2,000 列計算缺失值中位數，再切分，test 是否參與了模型建立？答案是有。中位數雖不是分類器係數，仍是從 test 學到的資料處理參數。

正確流程如下：

1. 讀取已發布的 split manifest，依 `row_id` 分出 train、validation、test。
2. 建立 `Pipeline([SimpleImputer(strategy='median'), StandardScaler(), LogisticRegression(...)])`。
3. 只用 train 呼叫一次 `fit`。
4. 對 validation 呼叫 `predict_proba` 選擇閾值；不能再 fit。
5. 凍結模型、特徵與閾值後，才對 test 呼叫 `predict_proba`。

證據不靠口頭保證。lab 會保存 `split_hash`、各集合 row IDs 的摘要，以及 `fit_row_ids`。檢查式要求 `fit_row_ids ⊆ train_row_ids` 且 `test_row_ids` 不出現在 threshold search 的輸入。

## guided_practice

第一步，列出下列操作屬於 `fit` 還是 `transform`：計算中位數、以既有中位數補值、估計標準差、套用標準化、訓練 LogisticRegression。提示：只要操作會因輸入列改變而產生新的參數，就是 `fit`。

第二步，找出這段流程的三個問題：「全資料補值 → 全資料標準化 → 切分 → 用 test 選 threshold」。提示一：前兩個問題都發生在切分之前；提示二：最後一個問題不是模型 `fit`，卻仍用 test 做了選擇。

第三步，畫出修正後箭頭。train 可以流向 `fit`；validation 可以流向 threshold selection；test 只能流向 final evaluation。再把每支箭頭旁寫出允許的 API。

## independent_practice

現在資料改成同一設備每天一列。請不要直接沿用隨機 row split。提出一個 group 或 time split 方案，說明分組鍵、時間界線，以及如何防止同一設備的近鄰觀測跨集合。交付一張至少含 12 個示例 row IDs 的分組表，並寫出兩個機驗不變條件。

這項任務沒有唯一切點；評分看你是否能說明部署時會遇到的是「新時間」還是「新設備」，以及切分是否模擬該情境。

## misconceptions

錯法一：「只要最後沒有用 test 訓練 LogisticRegression，就沒有洩漏。」可觀察症狀是 imputer 或 scaler 的 `fit_rows` 含 test。修正理由：前處理參數也是從資料學得的模型狀態。

錯法二：「用了 Pipeline 就不可能洩漏。」可觀察症狀是特徵表含 `repair_completed_at`、`failure_confirmed` 等預測當下尚無法取得、事後才知道的欄位。修正理由：Pipeline 管理執行順序，不理解欄位的業務時間語意。

錯法三：「validation 表現不好，可以改用 test 選閾值一次。」可觀察症狀是 threshold search log 出現 test row IDs。修正理由：一旦 test 參與選擇，它就不再是未見資料的最終估計。

## assessment_reflection

自評時附上資料流表、切分不相交檢查與一段 150–250 字說明。通過條件：指出至少三個洩漏位置；所有學習型轉換只 fit train；validation 與 test 用途分開；能解釋 Pipeline 的能力邊界。

若任一 `fit_row_id` 不在 train，或用 test 選擇欄位、模型、閾值，本項必須重做。分數沒有變好也不能把洩漏判為無害。

來源：scikit-learn〈Common pitfalls and recommended practices〉，https://scikit-learn.org/stable/common_pitfalls.html（查核 2026-09-07）；iPAS 中級學習指引 `mid-s2c4` 與 `mid-s3c9` 的定位由本 release GuideRef 綁定。
