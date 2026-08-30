#!/usr/bin/env python3
"""補寫公告試題的人工解析與題幹。

`parse_exams_v2.py` 由 PDF 重建題目時，explanation 一律填成「正確答案為(X)。」。
本腳本把人工撰寫的解析覆蓋回去，因此**每次重跑 parse_exams_v2 後都要再執行一次**，
否則解析會被制式字串蓋掉。與 `annotate_exam_code_images.py` 同屬「解析後的人工補強」層。

QUESTION_OVERRIDES 則收人工謄寫的題幹：有些題目的敘述清單（描述A~F）在 PDF 裡是
圖片內的文字，表格與頁面文字都取不到，任何重跑都無法還原，只能由這裡覆蓋回去。
SOURCE_ISSUES 保留官方題幹與答案不動，只加入機器可讀註記與成績頁可見解析，標明
原始題目的分類或選項歧義。
"""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]

QUESTION_OVERRIDES: dict[str, str] = {
    'mid_1151_s3_q46': '參考下圖資料處理，下列哪一項描述組合正確？\n描述A：x_train, x_test 將影像範圍壓縮到 0~31 範圍\n描述B：x_train, x_test 資料轉換可以增加模型的泛化能力\n描述C：x_train, x_test 資料轉換結果相當於 z-score 標準化\n描述D：資料轉換目的是避免梯度爆炸或梯度消失\n描述E：y_train 將 label 轉換為獨熱編碼（One-hot Encoding）\n描述F：y_train 適合輸出層使用 softmax 函數',
    'mid_1151_s3_q47': '參考下圖建立模型結果，下列哪一項描述組合正確？\n描述A：區塊1 layers.Input(shape=(32, 32, 3)) 主要目的是進行資料標準化\n描述B：區塊1 layers.Conv2D(32, kernel_size=(3,3), padding="same", activation="relu") 考慮輸入為(32,32,3)，則輸出 shape 為(32,32,3)\n描述C：區塊1 layers.BatchNormalization() 放在 Conv2D 之後可以減少梯度消失或爆炸\n描述D：區塊2 layers.Dropout(0.25) 可以隨機將 25% 神經元輸出設定為 1\n描述E：區塊3 layers.Dropout(0.25) 可以減少過度擬合（Overfitting）\n描述F：區塊4 Flatten 層的作用是將 3D 特徵圖展開為平面 1D 向量',
}

SOURCE_ISSUES: dict[tuple[str, str, str], dict[str, str]] = {
    ('初級', 'sample', 'sample_q22'): {
        'type': 'ambiguous_taxonomy',
        'official_answer': 'C',
        'note': (
            '官方答案為(C)，本平台照錄、不改寫題幹或答案。惟本題將「特徵選取技術或方法」'
            '合併表述；依常見機器學習術語，PCA 通常歸類為特徵擷取／降維而非特徵選取，'
            '因此選項(B)亦存在分類歧義。'
        ),
    },
    ('中級', 'mid_1151_s2', 'mid_1151_s2_q49'): {
        'type': 'multiple_syntactically_valid_choices',
        'official_answer': 'B',
        'note': (
            '官方答案為(B)，本平台照錄、不改寫題幹或答案。依題目列出的 split → 建立模型 → fit '
            '流程，選項(A)的 liblinear 與選項(B)的 lbfgs 都可用於 Iris 羅吉斯迴歸；'
            '原題未提供足以排除(A)的額外條件，因此答案具有歧義。'
        ),
    },
}

EXPLANATIONS = {
'mid_1141_s2_q3': '圖中密度曲線的高峰偏在右側（約 40），左側則拖出一條長尾一路延伸到 −20，屬於左偏（負偏態）分布。左偏時平均數被長尾拉低於中位數，偏態係數為負，故 Skewness < 0。(B) 右偏（正偏態）的圖形應是峰在左、長尾在右；(C) 唯有左右對稱的分布（如常態分布）偏態才會接近 0；(D) 只要有樣本資料就能計算偏態係數，不存在無法計算的情況。',

'mid_1141_s2_q40': '虛擬碼的迴圈跑 i = 1 到 N，每一輪只取「第 i 筆」資料當測試集、其餘 N−1 筆當訓練集，等於做 N 次訓練與驗證後取平均——這正是留一交叉驗證（LOOCV）的定義。(A) Hold-out 只切一次訓練／測試集，不會迴圈 N 次；(C) K-fold 是把資料切成 K 份（K 通常遠小於 N），每次留下一「份」而非一「筆」；(D) 拔靴法是以有放回的重複抽樣產生多組樣本，虛擬碼中沒有任何重抽動作。',

'mid_1141_s2_q41': '虛擬碼先隨機挑 X 個資料點當初始中心，接著反覆執行「把每個點指派給距離最近的中心 → 以群內所有點的平均值更新中心」，直到中心不再變動為止，這是 K-means 的標準流程。(B) 高斯混合模型以 EM 演算法估計各高斯成分的機率歸屬，屬於軟分群，不是取最近中心；(C) 階層式分群靠逐步合併或分裂建立樹狀圖，不需預先指定中心點；(D) DBSCAN 依密度參數（eps、minPts）擴散成群並可標記雜訊點，也不需指定群數。',

'mid_1141_s2_q42': '卜瓦松分佈的成立前提正是「事件彼此獨立發生，且單位時間內的平均發生率 λ 固定」，故 (C) 正確。(A) λ = 5 是平均值而非上限，瑕疵品個數理論上可以是任意非負整數；(B) `poisson.pmf(5, λ)` 是「恰好 5 個」的機率，「小於 5 個」應寫成 `poisson.cdf(4, λ)`；(D) `poisson.cdf(10, 5)` 是「小於或等於 10 個」的累積機率，「大於或等於 10 個」要用 `1 - poisson.cdf(9, 5)`。',

'mid_1141_s2_q45': '要統計「每個平台的全球銷售總額」，必須依 Platform 分組後對 Global_Sales 取 `sum()`，再以 `plot(kind="bar")` 繪製長條圖。(B) `count()` 算的是各平台的遊戲款數，不是銷售額；(C) `value_counts()` 同樣只在數各平台出現幾筆資料；(D) `mean()` 得到的是平均每款銷售額，而非總額。',

'mid_1141_s2_q46': '要比較四個地區的銷售總額比例，需先用 `pd.melt` 把 NA/EU/JP/Other 四個欄位轉成「variable（地區）／value（銷售額）」的長格式，再以 `sns.barplot` 搭配 `estimator=sum` 對各地區加總，故 (C) 正確。(A) `countplot` 只能計算出現次數，且 x 不接受欄位名稱清單；(B) `lineplot` 的 y 不接受多欄位清單，折線圖也不適合呈現總額比較；(D) `histplot` 畫的是數值的次數分布，不是各地區的加總。',

'mid_1141_s2_q47': '`data.nlargest(5, "NA_Sales")` 會依北美銷售額取出最高的前五筆，再交給 `sns.barplot` 以遊戲名稱對銷售額作圖，正好符合需求。(A) `data.head(5)` 只是取資料集的前五列（依全球排名 Rank 排序），不等於北美銷售前五名；(C) 前五名屬於類別間的比較，用 `lineplot` 折線並不恰當；(D) `countplot` 用於計算類別次數，不接受同時指定 x 與 y 的數值欄位。',

'mid_1141_s2_q49': 'pandas 中偵測遺漏值的正確寫法是 `df.isnull()` 與 `df.isna()`，兩者互為別名、功能完全相同，接 `.sum()` 後即可得到各欄位的 NaN 個數（本題結果顯示 facebook 有 1 筆遺漏值）。而 `df.isNaN()` 與 `df.isnan()` 都不是 DataFrame 的方法，執行會拋出 AttributeError，因此只有選項 A、C 正確。',

'mid_1141_s2_q50': 'B 正確：`LinearRegression().fit(X, y)` 的參數順序是先特徵矩陣、後反應變數。F 正確：OLS 摘要中 `const` 的係數為 3.5561，即為截距項。A 錯誤：`fit(y, X)` 把參數順序寫反了。C 錯誤：`reg.coef_` 只回傳 youtube、facebook、newspaper 三個自變數的斜率，截距另存於 `reg.intercept_`，不會是 4 個值。D 錯誤：`sm.OLS` 的參數順序是 `sm.OLS(y, X2)`，應變數在前。E 錯誤：newspaper 的 p 值為 0.914，遠大於 α = 0.05，不具顯著解釋力，因此不能說「所有」係數都顯著。',

'mid_1141_s3_q38': '程式碼將 `(y_true - y_pred) ** 2` 加總後除以樣本數，也就是「平方誤差的平均」，正是均方誤差 MSE。(A) MAE 取的是絕對值 `abs(y_true - y_pred)` 的平均；(C) RMSE 需要在 MSE 之後再開平方根；(D) R² 要比較殘差平方和與總平方和，公式與此完全不同。',

'mid_1141_s3_q39': '程式碼在訓練階段用 `np.random.binomial` 產生 0/1 遮罩隨機關閉一部分神經元的輸出，並除以保留機率 p 做尺度補償（inverted dropout），推論階段則直接原值回傳——這正是 Dropout 的標準實作方式。(A)(B) L1／L2 正則化是在損失函數上加入權重絕對值和或平方和的懲罰項，不會隨機遮蔽神經元；(D) Batch Normalization 是用批次的平均數與標準差做標準化，與隨機遮罩無關。',

'mid_1141_s3_q40': '`np.dot(v1, v2)` 計算兩向量的內積：1×4 + 2×5 + 3×6 = 32，NumPy 回傳純量 `np.int64(32)`，故 (C) 正確。(A) 程式碼只建立了矩陣 A，並未呼叫 `np.linalg.inv` 求反矩陣；(B) `v1 * v2` 是逐元素相乘，結果為 `array([4, 10, 18])` 而非 `array([5, 7, 9])`（後者是 `v1 + v2`）；(D) `np.linalg.eig` 僅是函式名稱，程式碼中並未呼叫。',

'mid_1141_s3_q41': '條件機率的定義為 P(A│B) = P(A∩B) / P(B)，以蒙地卡羅模擬估計時，就是把「同時滿足 A 與 B 的次數」除以「滿足 B 的次數」，即 `A_and_B.sum() / B.sum()`。(C) 除以 `A.sum()` 算出來的是 P(B│A)，條件顛倒了；(A)(B) 分母改用相乘或相加都沒有機率上的意義，也不是條件機率的定義。',

'mid_1141_s3_q45': '遷移學習要凍結的是負責特徵萃取的卷積層，在 torchvision 的 VGG16 中即 `model.features`。選項 B 只對 `model.features.parameters()` 設 `requires_grad = False`，再把 `classifier[6]` 換成新的 10 類輸出層，卷積層固定、分類器可訓練，完全符合題意。(A) 對 `model.parameters()` 全面凍結，連 classifier 前面的全連接層也一併凍住，凍結範圍超出題目所要求的「卷積層」；(C) 凍結的是 classifier，方向完全相反，卷積層反而會被更新；(D) `model.requires_grad = False` 只是在 Module 物件上新增一個同名屬性，並不會傳遞到底下各層的參數，實際上沒有凍結任何東西。',

'mid_1141_s3_q46': 'PCA 能降噪的關鍵，在於只保留承載主要特徵的前幾個主成分、捨棄承載雜訊的次要成分。程式碼 B 寫的是 `pca = PCA()`，沒有指定 `n_components`，等於保留全部主成分，後續 `inverse_transform` 便會把原始資料（連同雜訊）完整還原，自然看不出降噪效果。必須改成指定保留的成分數或變異比例（例如 `PCA(n_components=0.5)`）才會生效。(A) import 敘述本身沒有問題；(C)(D) 以 noisy 進行 fit 與 transform 是降噪流程的正常步驟；(E) `inverse_transform` 負責把壓縮後的成分投影回原始空間，寫法正確。',

'mid_1141_s3_q47': '程式碼 A 以 `StratifiedKFold` 搭配 `scoring="accuracy"`，程式碼 C 直接用 `cv=5`（分類任務下 `cross_val_score` 預設即採分層 K-fold）同樣搭配 accuracy，兩者都能順利執行並輸出平均準確率。程式碼 B、D 則把 `scoring` 設為 `"f1"`；digits 是 10 個類別的多類別資料集，`f1` 未指定 `average`（例如 `f1_macro`）時會直接拋出錯誤，無法輸出結果，因此正確組合為 A、C。',

'mid_1141_s3_q48': 'A 正確：`X_train -= X_train.mean(axis=0)` 逐特徵減去平均數，使每個特徵的平均值變成 0，即中心化。D 正確：標準化讓各特徵的尺度趨於一致，可避免輸入量級差異過大導致梯度爆炸或消失，有助於訓練收斂。B 錯誤：除以標準差是把標準差調整為 1，不是 0。C 錯誤：把資料壓縮到 0 與 1 之間的是 Min-Max 正規化；此處的 Z-score 標準化後值域並不受限，仍會出現負值。E 錯誤：標準化屬於特徵縮放（Feature Scaling），特徵選擇則是挑選要保留哪些變數，兩者不同。F 錯誤：改成 `X_train = X_train.std(axis=0)` 會把整個資料集直接換成一組標準差數值，資料就毀了。',

'mid_1141_s3_q49': 'Dense 層的參數量 =（輸入維度 × 神經元數）+ 偏差項數。輸入特徵有 9 個，第一層 Dense(10) 的參數量為 9 × 10 + 10 = 100，即空格1；第二層的輸入是前一層的 10 個輸出，參數量為 10 × 10 + 10 = 110，即空格2，故 (C) 正確、(B) 兩個數字顛倒。(A) 並未給出完整的數學式，ReLU 的定義是 max(0, x)；(D) sigmoid 輸出單一機率值，適用於二元分類（本題 loss 也正是 binary_crossentropy），多類別分類應改用 softmax。',

'mid_1141_s3_q50': 'matplotlib 的格式字串中，`b-` 代表藍色實線、`r--` 代表紅色虛線。對照執行結果的圖例，Training Loss 是藍色實線、Validation Loss 是紅色虛線，因此空格1應填 `"b-"`（敘述 A 正確）、空格2應填 `"r--"`（敘述 D 正確）。(B) 空格2並非 `b--`；(C) 空格1並非 `r-`；(E) 由圖可見訓練損失自 0.65 持續下降到約 0.40，驗證損失則在約 0.45 附近就趨於平坦，是訓練損失下降得更明顯（並出現輕微過擬合），敘述反了。',
}

_ALL_IDS = set(EXPLANATIONS) | set(QUESTION_OVERRIDES)
TARGETS = (
    ('初級', 'sample', 'sample_exam.json', 'sample_'),
    ('中級', 'mid_1141_s2', 'mock_mid_1141_s2.json', 'mid_1141_s2'),
    ('中級', 'mid_1141_s3', 'mock_mid_1141_s3.json', 'mid_1141_s3'),
    ('中級', 'mid_1151_s2', 'mock_mid_1151_s2.json', 'mid_1151_s2'),
    ('中級', 'mid_1151_s3', 'mock_mid_1151_s3.json', 'mid_1151_s3'),
)


def apply_to_file(path: Path, ids: list[str], level: str, exam_key: str) -> int:
    """Apply curated fields to one production JSON and return changed fields."""
    data = json.loads(path.read_text(encoding='utf-8'))
    changed = 0
    present_ids = {question['id'] for question in data['questions']}
    missing = sorted(set(ids) - present_ids)
    if missing:
        raise RuntimeError(f'{path.name} 找不到題號: {missing}')

    for question in data['questions']:
        qid = question['id']
        issue = SOURCE_ISSUES.get((level, exam_key, qid))
        new_explanation = issue['note'] if issue else EXPLANATIONS.get(qid)
        if new_explanation and question.get('explanation') != new_explanation:
            question['explanation'] = new_explanation
            changed += 1
        stem = QUESTION_OVERRIDES.get(qid)
        if stem and question.get('question') != stem:
            question['question'] = stem
            changed += 1
        if issue and question.get('source_issue') != issue:
            question['source_issue'] = issue
            changed += 1

    if changed:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return changed


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--level', choices=['初級', '中級'])
    parser.add_argument('--key', action='append', dest='keys', help='只更新指定考卷 key（可重複）')
    args = parser.parse_args()

    selected = [
        target for target in TARGETS
        if (not args.level or target[0] == args.level)
        and (not args.keys or target[1] in set(args.keys))
    ]
    if args.keys:
        matched = {target[1] for target in selected}
        unknown = sorted(set(args.keys) - matched)
        if unknown:
            parser.error(f'沒有人工補強資料的考卷 key: {", ".join(unknown)}')

    total = 0
    for level, key, filename, id_prefix in selected:
        ids = sorted(
            {qid for qid in _ALL_IDS if qid.startswith(id_prefix)}
            | {
                qid for issue_level, issue_key, qid in SOURCE_ISSUES
                if issue_level == level and issue_key == key
            }
        )
        path = BASE / 'data' / level / 'questions' / filename
        changed = apply_to_file(path, ids, level, key)
        print(f'{level}/{key}: 更新 {changed} 個欄位')
        total += changed
    print(f'合計更新 {total} 個欄位')


if __name__ == '__main__':
    main()
