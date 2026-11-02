# 2026-11 round 3 講義修正：mid-s2c4／mid-s3c9 guide 雜湊重綁（block ID 不變）證據

日期：2026-11-02。作者：`agent-claude-code`。這份證據支撐 `content/learning/identity/guide-anchors.json`
四個 anchor 的 `current.sourceHash` 更新，以及其後重新開立的 unit／lab／project／analysis review。
它只證明「anchor 與 evidence 所指的 block，id 與內容都沒變，只是所在檔案的整檔 hash 變了」；**不**證明教學內容本身正確。
前例：[`guide-anchor-migration-20261102.md`](guide-anchor-migration-20261102.md)（block 序號 +1 的遷移）、
`assessment/analysis-hash-rebind-20261102.json`（只換 provenance hash）。

## 起因

round 3 第 3–5 批講義修正（CJK 括號空白、印刷編號標題、斷字合併、彙整頁補圖、出處逐筆覆核）重新產生兩個 guide 檔：

| 檔案 | HEAD（舊，受審版） | 工作樹（新） | blocks |
|---|---|---|---|
| `中級-guide2/mid-s2c4.json` | `sha256:0a879eb0b67bbdd33cf0e92e0df98f7668ddd94ec522deb5ba01c2b06079e63a` | `sha256:1d1eb632f9388f88388a5b735e93ce5b7d6bf1e09f5e75b1a2db7cf4f50e7f04` | 111 → 112 |
| `中級-guide3/mid-s3c9.json` | `sha256:fae30b12ab4e03d3b21072304c7150859350f7d73d5205660e51f2c306e30083` | `sha256:8b4b3996c690ac586e065f13fda6e265168a41b739fab4e3acb934dc6e5eeaf1` | 221 → 221 |

兩檔頂層只有 `blocks` 改變。以排除 `id`、`bbox` 後的 block 內容做序列比對（`difflib.SequenceMatcher`）：

- **mid-s2c4**：`block-1`～`block-6`（pageIndex 56，含被錨定的 `block-3`）完全不動；
  1. 在 `block-6` 之後新增印刷頁的 heading `block-7`「2. 資料來源類型與蒐集方式」；
  2. 原 `block-36` heading「2. 資料品質問題與清理策略」（位置錯在段落之後）改為新 `block-36` heading「3. 資料品質問題類型與評估指標」，置於該段落之前；
  3. 兩處 list_item 刪除中文與「（」之間多餘空白（舊 `block-26`、`block-41`）。
  因第 1 點，舊 `block-7` 之後的 block 序號 +1。**學習平台沒有任何紀錄引用 mid-s2c4 的 `block-7` 以後**（見下方引用盤點）。
- **mid-s3c9**：block 數與 id 序列完全相同；只有三個 block 的 `text` 刪除中文與「（」之間的多餘空白：
  `block-18`（pageIndex 151，「子集 （folds）」）、`block-59`（pageIndex 153，「正類 （Positive）」）、`block-174`（pageIndex 160，「1 折 （fold）」）。
  三者都不是被引用的 block。

依 `data-contracts.md` §5，不同 sourceHash 時不得猜最近 block。本次不需要猜：被引用 block 的 id 不變，
且新版同 id 的 block 與舊版**逐欄位全等**（含 `bbox`），quote 在新版全文恰好一個命中，就是同一個 id；維護者已於 2026-11-02 核准只換雜湊。

## 被引用 block 盤點與逐欄位比對

盤點方式：`grep -rhoE 'block-[0-9]+'` 掃 `content/learning/{units,identity,labs,projects}`、頂層 `evidence/*.json`、`evidence/assessment/`（排除 `superseded/` 與 review）。
現行引用只有下列四個；另 `block-70`／`148`／`167` 只出現在前例紀錄與 anchor history（舊版 mid-s3c9 `263987fb…`），
`block-77` 只出現在 `assessment/recall-formula-direct-view.md`，是對 `263987fb…` 版的歷史敘述，不是 GuideRef，本次不改。

| anchorId | block | pageIndex | quote | 新版命中 | 新舊 block 逐欄位全等 | 引用者 |
|---|---|---|---|---|---|---|
| mid-s2c4-data-quality | block-3 | 56 | 若資料本身存在缺漏、錯誤、格式不一致等問題，將直接導致模型預測失真 | `block-3` 唯一 | ✓ | unit-split-before-fit、evidence-mid-s2c4-data-quality |
| mid-s3c9-accuracy-imbalance | block-71 | 154 | 95%樣本為負類時，即使模型全預測為負，準確率仍高達95% | `block-71` 唯一 | ✓ | unit-imbalanced-classification、evidence-mid-s3c9-accuracy-imbalance |
| mid-s3c9-imbalance-strategies | block-149 | 158 | 類別不平衡處理與評估策略 | `block-149` 唯一 | ✓ | unit-imbalanced-classification、evidence-mid-s3c9-imbalance-strategies |
| mid-s3c9-cross-validation | block-168 | 159 | 4. 交叉驗證（DOM anchor `4交叉驗證`） | `block-168` 唯一 | ✓ | unit-threshold-decision、evidence-mid-s3c9-cross-validation |

「逐欄位全等」指 `git show HEAD:<檔>` 與工作樹檔中同 id 的 block dict 以 Python `==` 比較為真（`id`、`type`、`text`／`title`、
`depth`、`marker`、`pageIndex`、`bbox`、`anchor`、`kind` 等全部欄位）。四張頁面 PNG（page_056、154、158、159）未改動，
實測 sha256 與 evidence 的 `artifactHash` 相同。

`data/guide_block_id_migrations.json`（基準 153f13d）旁證：`中級-guide2/mid-s2c4` 未列 `block-3`（＝對應到自己），
`中級-guide3/mid-s3c9` 的 `block-70→71`、`148→149`、`167→168` 均為 `exact`，與現行 anchor 一致。

## 改了什麼

- `data/resource_catalog.json`：`learning-guide-middle-2`、`learning-guide-middle-3` 的 `version`／`sha256` 換成新 blob hash。
- `content/learning/identity/guide-anchors.json`：四筆 `current.sourceHash` 換成新值；`blockIds`、`pageIndexes`、`quote`、`anchor` 不變。
  舊的 `{sourceHash, blockIds, nodeId}` 追加到 `history`（mid-s3c9 三筆保留前例的 `263987fb…` 紀錄，再追加 `fae30b12…`），
  各 anchor 的 `evidenceIds` 追加本證據 id `evidence-guide-hash-rebind-20261102-diff`。
- 四筆 guide_location evidence：`revision` +1（mid-s2c4 1→2；mid-s3c9 三筆 2→3），`guideRef.sourceHash`、`observedAt` 更新，
  `blockIds`、`locator`、`claim`、`excerpt`、`artifactRef`、`artifactHash` 不變；`contentHash` 以 `learning.contracts.content_hash` 重算。
- 三個 unit：`dependencies[0]` 與 claim `sourceRefs` 的 guide snapshot `revision`／`hash`、`guideRefs[*].sourceHash`；`contentHash` 以 repo API 重算；`reviewIds` 指向新 review。
  **revision 維持 1**，理由同前例（in_review、從未發佈；改 revision 會牽動 lab／project 的 `unitRefs` 與 contentHash）。
- lab／project：只更新 `reviewIds`（被 contentHash 排除的生命週期欄位；lab 的 `semanticReviewId` 比照前例不動）；兩者 contentHash 不變。
- exam-analysis `analysis-imbalanced-source-examples-v1`：其 `catalogHash` 是 `data/resource_catalog.json` 整檔 blob hash，
  上述 catalog 兩列的 hash 更新使它由 `sha256:aeed547b5f54…` 變為 `sha256:1912806b845d…`，analysis contentHash 隨之由
  `sha256:1060192bbbff…` 變為 `sha256:a0fec784b20b…`；analysis 其他欄位（policy、inventory、measures、exclusions、labelReviewHash、taxonomyHash）不變。
  這是同一次雜湊重綁的連帶結果，比照 `analysis-hash-rebind-20261102` 重新開立 review。

| 實體 | 舊 | 新 |
|---|---|---|
| unit-imbalanced-classification (r1) | `sha256:b7f2aaf93faa…` | `sha256:9cad43d95be4…` |
| unit-threshold-decision (r1) | `sha256:9950dac23fac…` | `sha256:73b75b70c1ac…` |
| unit-split-before-fit (r1) | `sha256:df97d09c8ae8…` | `sha256:f314aa80b30f…` |
| evidence-mid-s2c4-data-quality | r1 `sha256:2f021d9d13c4…` | r2 `sha256:dc1c9b076e45…` |
| evidence-mid-s3c9-accuracy-imbalance | r2 `sha256:f0cff8cf2728…` | r3 `sha256:00e25fdd49e9…` |
| evidence-mid-s3c9-imbalance-strategies | r2 `sha256:077c688cef82…` | r3 `sha256:daa7269d006d…` |
| evidence-mid-s3c9-cross-validation | r2 `sha256:5298976f0b99…` | r3 `sha256:235ff00644fb…` |
| analysis-imbalanced-source-examples-v1 | `sha256:1060192bbbff…` | `sha256:a0fec784b20b…` |
| data/resource_catalog.json（整檔） | `sha256:aeed547b5f54…` | `sha256:1912806b845d…` |
| lab-imbalanced-classification | `sha256:6aeb2aeb2702…` | 不變 |
| project-imbalanced-classification | `sha256:c333d0600d3c…` | 不變 |

## 可重跑的反推證明

把新 hash 換回舊 hash（兩種寫法 `sha256:`／`sha256-`；evidence 另還原 `revision`／`observedAt`；analysis 把 `catalogHash` 換回 HEAD 版 catalog 的 blob hash）後重算，
必須精確得到 HEAD 記錄的指紋；相符即證明其餘參與雜湊投影的欄位（含 unit 正文 `.md` bytes）全都沒變。

```bash
source .venv/bin/activate && python3 - <<'PY'
import json, pathlib, subprocess, sys
sys.path.insert(0, "scripts")
from learning.contracts import content_hash, blob_hash
from learning.references import ReferenceResolver
from build_learning_assessment import assessment_inputs
ROOT = pathlib.Path(".").resolve()
git = lambda p: subprocess.run(["git", "show", f"HEAD:{p}"], capture_output=True, check=True).stdout
PAIRS = []
for g in ("中級-guide2/mid-s2c4", "中級-guide3/mid-s3c9"):
    p = f"frontend/src/generated/guideContent/{g}.json"
    PAIRS.append((blob_hash((ROOT / p).read_bytes()), blob_hash(git(p))))
def restore(text):
    for new, old in PAIRS:
        text = text.replace(new, old).replace("sha256-" + new[7:], "sha256-" + old[7:])
    return json.loads(text)
head = lambda p: json.loads(git(p))
resolver = ReferenceResolver(ROOT)
for u in ("unit-imbalanced-classification", "unit-threshold-decision", "unit-split-before-fit"):
    p = f"content/learning/units/{u}.json"; r = restore((ROOT / p).read_text(encoding="utf-8")); o = head(p)
    same = sorted(k for k in set(r) | set(o) if r.get(k) != o.get(k))
    print(u, content_hash("learning-unit", r, body_bytes=resolver.body_bytes(r)) == o["contentHash"], "diff fields:", same)
for e in ("mid-s2c4-data-quality", "mid-s3c9-accuracy-imbalance", "mid-s3c9-imbalance-strategies", "mid-s3c9-cross-validation"):
    p = f"content/learning/evidence/evidence-{e}.json"; r = restore((ROOT / p).read_text(encoding="utf-8")); o = head(p)
    r["revision"], r["observedAt"] = o["revision"], o["observedAt"]
    print(e, content_hash("evidence", r) == o["contentHash"], "diff fields:", sorted(k for k in set(r) | set(o) if r.get(k) != o.get(k)))
a = assessment_inputs(ROOT)["analysis"]; old = dict(a); old["catalogHash"] = blob_hash(git("data/resource_catalog.json"))
print("analysis", a["contentHash"], content_hash("exam-analysis", old) == head("content/learning/reviews/review-peer-d1-analysis-imbalanced-source-examples-v1-20261102-v3.json")["subject"]["hash"])
cat = restore((ROOT / "data/resource_catalog.json").read_text(encoding="utf-8")); print("catalog restored == HEAD", cat == head("data/resource_catalog.json"))
anc = json.loads((ROOT / "content/learning/identity/guide-anchors.json").read_text(encoding="utf-8")); oa = head("content/learning/identity/guide-anchors.json")
for a1, a0 in zip(anc["anchors"], oa["anchors"]):
    c = dict(a1["current"]); c["sourceHash"] = dict(PAIRS)[c["sourceHash"]]
    print(a1["anchorId"], "current restored == HEAD", c == a0["current"], "history prefix kept", a1["history"][:-1] == a0["history"], "new history = HEAD current", a1["history"][-1] == {"sourceHash": a0["current"]["sourceHash"], "blockIds": a0["current"]["blockIds"], "nodeId": a0["current"]["nodeId"]})
PY
```

2026-11-02 實際執行結果（未 commit 的工作樹對 HEAD `e5ecfd5`）：

```text
unit-imbalanced-classification True diff fields: ['contentHash', 'reviewIds']
unit-threshold-decision True diff fields: ['contentHash', 'reviewIds']
unit-split-before-fit True diff fields: ['contentHash', 'reviewIds']
mid-s2c4-data-quality True diff fields: ['contentHash']
mid-s3c9-accuracy-imbalance True diff fields: ['contentHash']
mid-s3c9-imbalance-strategies True diff fields: ['contentHash']
mid-s3c9-cross-validation True diff fields: ['contentHash']
analysis sha256:a0fec784b20b1e5c74fbd388bc53ee7f9c266c00800c68a5812e3bd59ba0b03c True
catalog restored == HEAD True
mid-s3c9-accuracy-imbalance current restored == HEAD True history prefix kept True new history = HEAD current True
mid-s3c9-imbalance-strategies current restored == HEAD True history prefix kept True new history = HEAD current True
mid-s3c9-cross-validation current restored == HEAD True history prefix kept True new history = HEAD current True
mid-s2c4-data-quality current restored == HEAD True history prefix kept True new history = HEAD current True
```

unit 還原後與 HEAD 只差 `contentHash`（還原時未改回）與 `reviewIds`（被 contentHash 排除的生命週期欄位）；
evidence 還原後只差 `contentHash`。lab／project 只改 review 指標欄位，以 `content_hash` 重算的 contentHash 與 HEAD 相同。

## 舊紀錄的保存位置

比照前例：被新 revision 取代的 evidence 與以 `evidenceRefs` 精確綁定它們的 unit review，**原封不動（逐 byte）**移到 `superseded/`：

- `content/learning/evidence/superseded/`：`evidence-mid-s2c4-data-quality.r1.json`、`evidence-mid-s3c9-{accuracy-imbalance,imbalance-strategies,cross-validation}.r2.json`
- `content/learning/reviews/superseded/`：unit-split-before-fit 的 20260907-v1、20260909-v2（domain＋contract，綁 mid-s2c4 r1）；
  unit-imbalanced-classification、unit-threshold-decision 的 20261102-v3（domain＋contract，綁 mid-s3c9 r2）——共 8 檔

lab／project／analysis 的舊 review 沒有綁這些 evidence revision，比照前例留在 `content/learning/reviews/`，新 review 以 `supersedes` 指向前一版。
