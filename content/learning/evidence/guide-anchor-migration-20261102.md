# 2026-11 guide_tree 重建：mid-s3c9 guide anchor 的機械式 block ID 遷移證據

日期：2026-11-02。作者：`agent-claude-code`。這份證據支撐 `content/learning/identity/guide-anchors.json`
三個 anchor 的 `current` 更新，以及其後重新開立的 unit／lab／project review。
它只證明「anchor 所指的原文沒變，只是 block 序號位移」；**不**證明教學內容本身正確。

## 起因

2026-11 的 guide_tree 重建（工作樹未 commit）重新產生
`frontend/src/generated/guideContent/中級-guide3/mid-s3c9.json`：

| | blob hash | blocks |
|---|---|---|
| HEAD（舊，受審版） | `sha256:263987fb931e9736a15bf16c4c1b3e94fec3d91d68d33ab601c7c16d77d06f37` | 220 |
| 工作樹（新） | `sha256:fae30b12ab4e03d3b21072304c7150859350f7d73d5205660e51f2c306e30083` | 221 |

以排除 `id` 後的 block 內容做序列比對，兩版**只有兩處**差異，都在 pageIndex 153（混淆矩陣段落）：

1. `block-59`（paragraph）把原本被截斷的句子補完（「…以「正類」→「…以「正類 （Positive）」和「負類（Negative）」作為預測與實際的對照。」），bbox 同步調整；
2. 在其後**新增**一個 list_item `block-61`「P：實際為正類的樣本數」。

第 2 點使原 `block-61` 之後的每個 block 序號 +1。頂層欄位只有 `content`（markdown 投影）跟著變，`sourcePages`、`headings` 等不變。

依 `data-contracts.md` §5，不同 sourceHash 時不得猜最近 block，需「同頁/節錄找候選→人工核准才更新 current」。
本次候選以 quote 在新版全文搜尋，三個 quote 各**恰好一個**命中，且命中 block 除 `id` 外逐欄位相同；
維護者已於 2026-11-02 核准新位置。

## 三個 anchor

| anchorId | 舊 block | 新 block | pageIndex | quote | 新版命中數 | 除 id 外全等 |
|---|---|---|---|---|---|---|
| mid-s3c9-accuracy-imbalance | block-70 | block-71 | 154 | 95%樣本為負類時，即使模型全預測為負，準確率仍高達95% | 1 | ✓ |
| mid-s3c9-imbalance-strategies | block-148 | block-149 | 158 | 類別不平衡處理與評估策略 | 1 | ✓ |
| mid-s3c9-cross-validation | block-167 | block-168 | 159 | 4. 交叉驗證（DOM anchor `4交叉驗證`） | 1 | ✓ |

新位置的完整 block（舊版只差 `id`）：

- block-71：list_item depth 6「限制：在嚴重類別不平衡的資料中容易誤導，例如95%樣本為負類時，即使模型全預測為負，準確率仍高達95%。」
- block-149：list_item depth 5「類別不平衡處理與評估策略：面對高度不平衡資料（如欺詐偵測、醫療診斷），傳統準確率常導致誤判。可搭配資料處理技術如：」
- block-168：heading depth 3「4. 交叉驗證」，anchor `4交叉驗證`

舊 ID 在新版指向的是別的文字（block-70＝「適用：類別分佈相對均衡時效果良好。」、block-148＝迴歸任務 MAE/RMSE/R²、block-167＝Boxplot 段落），
所以不更新 current 的話引用會靜默錯位——這正是 resolver 以 `stale_guide_hash` 擋下的原因。

旁證：同一次重建產生的 `data/guide_block_id_migrations.json`（`blocks/中級-guide3/mid-s3c9`）
獨立記載 `block-70→block-71`、`block-148→block-149`、`block-167→block-168`，method 均為 `exact`；
`block-59` 為 `unmapped`（ratio 0.694，即上面被補完的段落）。

## 改了什麼

- `data/resource_catalog.json`：`learning-guide-middle-3` 的 `version`／`sha256` 改成新 blob hash（unit 的 repository snapshot 以 catalog revision 驗證）。
- `content/learning/identity/guide-anchors.json`：三筆 `current.blockIds`／`current.sourceHash` 改成新值；
  舊的 `{sourceHash, blockIds, nodeId}` 追加到 `history`（schema 的 history 不允許 reason 欄位，因此原因以本證據的 id
  `evidence-guide-anchor-migration-20261102-diff` 追加到各 anchor 的 `evidenceIds`）。
- 三筆 guide_location evidence：`revision 1→2`，`guideRef.blockIds`／`sourceHash`、`locator` 的 block 號、`observedAt` 更新，
  `claim`／`excerpt`／`artifactRef`／`artifactHash` 不變（三張頁面 PNG 的 hash 已重算，與紀錄相符）。`contentHash` 以 `learning.contracts.content_hash` 重算。
- 兩個 unit：`guideRefs[*].blockIds`／`sourceHash`、`dependencies[0]` 與 `claims[0].sourceRefs[0]` 的 guide snapshot `revision`／`hash`，`contentHash` 以 repo API 重算。
  **revision 維持 1**：比照 LP-210B 對 in_review、從未發佈實體的處理（當時 topicRefs 改變也維持 revision 1、以 v2 review supersede）。
  若改成 revision 2，lab／project 的 `unitRefs` 也得改，會連帶改變它們的 contentHash 與 L4 綁定，超出本次機械遷移的範圍。
- lab／project：只更新 `reviewIds`（及 lab 的 `semanticReviewId`／`executionReviewId`）這些被 contentHash 排除的生命週期欄位；
  兩者的 contentHash 不變，但因 `dependencyHashes` 含 unit contentHash，舊 review 依 §2 第 7 條失效，故重新開立。

| 實體 | 舊 contentHash | 新 contentHash |
|---|---|---|
| unit-imbalanced-classification (r1) | `a5ac34ded71a…` | `b7f2aaf93faa…` |
| unit-threshold-decision (r1) | `27070a98f3b1…` | `9950dac23fac…` |
| evidence-mid-s3c9-accuracy-imbalance | r1 `81c6bb607828…` | r2 `f0cff8cf2728…` |
| evidence-mid-s3c9-imbalance-strategies | r1 `0ae999467db3…` | r2 `077c688cef82…` |
| evidence-mid-s3c9-cross-validation | r1 `02fb2c284b90…` | r2 `5298976f0b99…` |
| lab-imbalanced-classification | `6aeb2aeb2702…` | 不變 |
| project-imbalanced-classification | `c333d0600d3c…` | 不變 |

## 可重跑的反推證明

把上述欄位還原成舊值（新 hash→舊 hash、新 block→舊 block；evidence 另還原 `revision`／`observedAt`）後重算，
必須精確得到 HEAD 與舊 review `subject.hash` 記錄的指紋；相符即證明其餘參與雜湊投影的欄位（含 unit 正文 `.md` bytes）全都沒變。

```bash
source .venv/bin/activate && python3 - <<'PY'
import json, pathlib, subprocess, sys
sys.path.insert(0, "scripts")
from learning.contracts import content_hash, blob_hash
from learning.references import ReferenceResolver
ROOT = pathlib.Path(".").resolve()
GUIDE = "frontend/src/generated/guideContent/中級-guide3/mid-s3c9.json"
OLD = blob_hash(subprocess.run(["git", "show", f"HEAD:{GUIDE}"], capture_output=True, check=True).stdout)
NEW = blob_hash((ROOT / GUIDE).read_bytes())
BACK = {"block-71": "block-70", "block-149": "block-148", "block-168": "block-167"}
resolver = ReferenceResolver(ROOT)
def restore(text):
    text = text.replace(NEW, OLD).replace("sha256-" + NEW[7:], "sha256-" + OLD[7:])
    for new, old in BACK.items():
        text = text.replace(f'"{new}"', f'"{old}"').replace(f"，{new}\"", f"，{old}\"")
    return json.loads(text)
head = lambda p: json.loads(subprocess.run(["git", "show", f"HEAD:{p}"], capture_output=True, check=True).stdout)
for u in ("unit-imbalanced-classification", "unit-threshold-decision"):
    p = f"content/learning/units/{u}.json"; r = restore((ROOT / p).read_text(encoding="utf-8"))
    print(u, content_hash("learning-unit", r, body_bytes=resolver.body_bytes(r)) == head(p)["contentHash"])
for a in ("accuracy-imbalance", "imbalance-strategies", "cross-validation"):
    p = f"content/learning/evidence/evidence-mid-s3c9-{a}.json"; r = restore((ROOT / p).read_text(encoding="utf-8")); o = head(p)
    r["revision"], r["observedAt"] = o["revision"], o["observedAt"]
    print(a, content_hash("evidence", r) == o["contentHash"])
PY
```

2026-11-02 實際執行結果：五筆全部 `True`（unit 還原後 JSON 與 HEAD 逐欄位相等；evidence 還原後除 contentHash 外無其他差異欄位）；
lab／project 的 contentHash 重算與 HEAD 相同。

## 舊紀錄的保存位置

Evidence 以 `(id, revision)` 不可變保存。revision 1 的三筆 evidence 綁著舊 guide hash，若留在
`content/learning/evidence/*.json`，候選驗證會對它們回報 `stale_guide_hash`；而 8 筆舊 unit review
（20260907-v1、20260909-v2 的 domain＋contract）以 `evidenceRefs` 精確綁定 revision 1。
因此這 3＋8 個檔案**原封不動（逐 byte）**移到 `content/learning/evidence/superseded/`
（evidence 檔名加 `.r1`）與 `content/learning/reviews/superseded/`。候選載入只讀各目錄第一層的 `*.json`，
子目錄不參與 gate；舊紀錄仍可讀、可由 Git 追溯，新 review 的 `supersedes` 指向其中的 20260909-v2。

## 已知、與本次無關的既有缺口

`exam-analysis/analysis-imbalanced-source-examples-v1` 的 review 在本次之前就已失效：
目前由 `build_learning_assessment.assessment_inputs` 產生的 analysis，即使把 `catalogHash` 換回 HEAD、
32d5a7d、790b234 任一版 catalog 的 hash，都還原不出 review 記錄的 `sha256:5636989303de…`，
代表 10 月的試題更新已改變了它的其他輸入。本次 catalog 變更再改一次 `catalogHash`，但不是失效的原因；本次不處理。
