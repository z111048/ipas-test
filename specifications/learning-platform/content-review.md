# MVP 獨立內容與考題審查紀錄

查核時間：2026-09-07T12:01:50Z。作者為 `/root/p0_baseline`；審查者為另一個代理 `/root/content_labs`（系統識別 `agent-content-labs`），角色是 `independent_model`。本紀錄是本次專案限域的模型審查，不代表使用者、教師或其他人類已閱讀與批准。

## 範圍與委派

Root coordinator 明確委派獨立核對三個 Unit、十題診斷、五題既有官方題的來源與答案；並同意記錄 machine-role qualification，範圍限於實際核對的內容、答案及機械來源檢查。`grantedBy=root-coordinator` 不表示人類簽核。原委派與限域文字保存在 `content/learning/qualifications/assessment-delegation.json`。

已閱讀三篇完整 Markdown、兩版核心例子摘要、十題完整四選項及解析，並直接讀取五題既有 canonical 題文、選項、答案及來源頁碼。以獨立算式核對矩陣、F1、成本與 threshold 的單調性，並以現有官方 scikit-learn 文件核對前處理與閾值用法。Notebook L4 語意審查與人類 L5 Colab smoke 尚未完成；本紀錄不替它們提供通過證據。

## 審查時的不可變輸入

凍結的題目與來源選讀快照另保存於 `content/learning/evidence/assessment/`，與 staging 輸入相同 bytes，供 fresh checkout 重建；staging 不是唯一來源。以下皆為原始檔案 SHA-256，不是重新排序 JSON 的值雜湊。

| 檔案 | SHA-256 |
|---|---|
| `data/learning/pipeline/mvp-authoring/questions.json` | `f99e3bf237b5ec6e978795ee0d99e434bc23daee7fac30973c3e6123a0d96f2a` |
| `content/learning/units/unit-split-before-fit.md` | `9bd1aa3d3b96f24a3eb25a827deea95c1554d11e92ad21aba09c6b8dbab795c9` |
| `content/learning/units/unit-imbalanced-classification.md` | `1ea47c16300aefa8583eea0a68cf4a9f4b9822bc5dce781206e2ad9457b9053f` |
| `content/learning/units/unit-threshold-decision.md` | `6da06ffbec6f44b7d5d02f67806b6830272414f7557c11dd17c4ed57dc071c39` |

## 發現與修正

| 編號 | 原問題 | 作者修正後的判斷 |
|---|---|---|
| R1 | Q10 同一模型降低 threshold 卻降低 recall，與固定分數與正類定義下的單調性矛盾。 | 改成 A=0.25、B=0.20 且兩者 recall 均 0.80、成本相同；第三層 tie-break 選 B。正解已由 A 改 B。 |
| R2 | Q04 將多數類 baseline 稱為 accuracy 的「下限」，忽略模型可能更差。 | 改為比較基準，明示模型可能高於或低於它。 |
| R3 | split Unit 對事後維修欄位的說明誤寫為預測當下才知道。 | 改為預測當下尚無法取得、事後才知道，符合時間語意洩漏。 |
| R4 | 指標 guided 練習只改 FN/FP，若其他數值不變，總數與正類總數也會變。 | 固定 N=400、正類20；改為 TP=17、FN=3、FP=35、TN=345。precision=17/52、recall=17/20。 |

四項已在凍結版本核對；沒有將修改前的審查 hash 沿用到修改後內容。核心例子採 `matrix-first`：先做可手算的 worked example，再移到設備告警與成本決策。`cost-first` 的營運動機適合用作開頭，不取代前置矩陣教學。

## 十題逐題判斷

全部題目屬本站作者的主題診斷，不宣稱為官方試題。題號尾碼與 canonical ID 一致；A/B/C/D 為來源顯示字母，release 的 `optionId` 保存身分，洗牌不改正解。

| 題號 | Unit／類型 | 唯一正解 | 實際核對與誘答判斷 |
|---|---|---|---|
| q01 | split／情境 | B | 全體中位數讓 test 參與 fit；保存與否、分類器是否只讀 train 都不能補救。各集合自行 fit 亦不是凍結的同一前處理。 |
| q02 | split／觀念 | C | fitRowIds ⊆ trainRowIds 是比工具名、accuracy 或集合大小更直接的範圍證據；前提是實際觀測的 row IDs，不能只自行填一個宣稱值。 |
| q03 | split／情境 | D | 「最終故障原因」在維修後才產生；Pipeline 不能推知業務欄位的可得時間。尺度與類別比例不回答此問題。 |
| q04 | metrics／情境 | B | 異常率5%、全負類 accuracy=.95、異常 recall=0。未預測正類時 precision 的零分母處理須明定，不能推為 .95。 |
| q05 | metrics／計算 | A | TP12/FN8/FP18/TN362：precision=12/30=.4，recall=12/20=.6，accuracy=374/400=.935。B 顛倒分母；C 混入 accuracy；D 無對應定義。 |
| q06 | metrics／計算 | B | F1=2×.4×.6/(.4+.6)=.48；.50 是算術平均；.935 是別的 accuracy。 |
| q07 | metrics／情境 | A | FN 成本高時先看異常 recall；題目問初步優先關注，不宣稱只憑 recall 就上線，解析仍要求 precision 與告警量。 |
| q08 | threshold／情境 | C | 在本課固定 train/validation/test 設定，validation 選 threshold、test 評估凍結方案。題意不是說其他正確交叉驗證設計不存在。 |
| q09 | threshold／計算 | C | (20×4+31)/400=111/400=.2775。A/B 各漏一種成本，D 把每筆成本誤作百分比數值。 |
| q10 | threshold／決策 | B | 成本相同且 recall 相同，依本課預先宣告規則選較小 threshold=.20；這是教學政策，不是普遍最佳化定理。不可再讀 test 來選。 |

分布為 3/4/3，共五題情境、三題計算、一題觀念、一題決策。難度欄只保留作者 editorial 意見，不宣稱有考生作答實證，MVP 不用難度配額。配額使用凍結的主分類：資料洩漏3、評估指標4、模型評估3；threshold 屬模型評估下的決策活動。其餘跨概念連結保留在 Unit/objective mapping，不讓同一道題占兩個同維度配額。

## 五題官方來源對照

這是選讀五題的教材對照，沒有重跑 OCR、修改官方答案或宣稱新增 PDF 人類審查。來源鍵沿 `resource_catalog.json`；每題的來源檔 raw hash 與頁碼由 adapter 再核對。既有題文及答案逐字保留，官方來源身分與答案合理性是兩個不同判斷。

| QuestionKey | 原答案／零起算頁 | 對照與界線 |
|---|---|---|
| `q:junior:jr_1151_s1:jr_1151_s1_q6` | C／1 | 先切分，標準化統計量只從 train 計算，直接對照資料洩漏。 |
| `q:junior:jr_1151_s1:jr_1151_s1_q40` | A／8 | 稀有瑕疵情境選 F1，對照類別不平衡與分類指標；不把官方干擾選項的原字詞自行修正。 |
| `q:middle:mid_1141_s3:mid_1141_s3_q19` | C／3 | 3% 正類時 accuracy 最不適當，對照少數類指標。 |
| `q:middle:mid_1141_s3:mid_1141_s3_q16` | A／3 | P=.8、R=.6，F1=.96/1.4=.685714，選 .686。 |
| `q:middle:mid_1151_s3:mid_1151_s3_q32` | D／7 | F1 是調和平均而非算術平均；對 threshold Unit 是先備關係，不作「直接考成本閾值」的證據。 |

分析的母體採這些題目所屬的完整三份已匯入試卷，依實際 canonical 題數計算；只有上述五題完成此輪 mapping 審查。其餘題目維持 unknown，嚴格 prevalence 為 null，另列 reviewed prevalence 與上下界。跨初中級彙總僅為教學選讀的明確範圍；不推論全部歷屆、下一次命題機率或熱度趨勢。

## 教材與外部依據

Worked → guided → independent → reflection 的任務與 Unit 目標對應；獨立練習要求提交矩陣重算、成本表、凍結決策與限制，不以 Run All 當成學會。固定例子的成本驗算為 .280、.2775、.430；新增 threshold=.30、FN3、FP51 也得 .2775，但 recall=.85 較高，應改選 .30。

前處理只在 training fit、閾值調整不能用同一筆資料同時訓練分類器與調閾值，依據 [scikit-learn Common pitfalls](https://scikit-learn.org/stable/common_pitfalls.html) 與 [Tuning decision thresholds](https://scikit-learn.org/stable/modules/classification_threshold.html)（查核 2026-09-07）。矩陣排列與 precision/recall 定義依據 [confusion_matrix](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.confusion_matrix.html) 和 [precision_recall_curve](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.precision_recall_curve.html)（查核 2026-09-07）。

## 尚未通過的發布條件

本次 content/answer review 合格可以進明確標示 preview 的本機診斷；正式完整 bundle 仍需規格要求的各角色審查。Lab L4、實際人類 L5 Colab smoke、固定 Git commit 下可開啟的 Colab URL 不能由此紀錄推定通過。未出現的日期、簽名或執行不得補造。來源、題文、正文、notebook 或 lock 變更後，舊審查因 hash 不符失效；必須重審或重跑對應檢查。
