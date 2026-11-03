# 2026-11 round 4 講義修正：mid-s2c4／mid-s3c9 guide 雜湊重綁（blocks 不變）證據

日期：2026-11-03。作者：`agent-claude-code`。這份證據支撐 `content/learning/identity/guide-anchors.json`
四個 anchor 的 `current.sourceHash` 更新，以及其後重新開立的 unit／lab／project／analysis review。
它只證明「anchor 與 evidence 所指的 block，id 與內容都沒變，只是所在檔案的整檔 hash 變了」；**不**證明教學內容本身正確，
也**不**證明 round 4 講義修正本身（`content`／`headings` 備援欄位）的正確性。
前例：[`guide-hash-rebind-20261102.md`](guide-hash-rebind-20261102.md)（round 3 的同類重綁）。

## 起因

round 4 講義修正把 guideContent 的 `content`（markdown 備援全文）與 `headings`（目錄備援）改由已發佈的 `blocks` 推導並對齊；
`blocks` 陣列本身完全不變。這使兩個被學習平台引用的 guide 檔整檔 sha256 改變：

| 檔案 | 基準 `8717147`（舊，受審版） | 工作樹（新） | 改變的頂層欄位 | blocks |
|---|---|---|---|---|
| `中級-guide2/mid-s2c4.json` | `sha256:1d1eb632f9388f88388a5b735e93ce5b7d6bf1e09f5e75b1a2db7cf4f50e7f04` | `sha256:b4559ebcceba4b0ffc0465a83ef2282bfccdc9da138507f6c8a41ad76e918e89` | `content`、`headings` | 112 → 112，陣列 `==` |
| `中級-guide3/mid-s3c9.json` | `sha256:8b4b3996c690ac586e065f13fda6e265168a41b739fab4e3acb934dc6e5eeaf1` | `sha256:c33286d7d5e01dd48cdd59067276f8094745e0e89498e77d55303bbfddb077a8` | `content`、`headings` | 221 → 221，陣列 `==` |

`headings` 的變動：mid-s2c4 由 2 筆增為 6 筆（新增 `41數據收集與清理`、`1前言與章節導覽`、`2資料來源類型與蒐集方式`、
`3資料品質問題類型與評估指標`，原有 2 筆不變）；mid-s3c9 仍為 17 筆，只有 level 2 標題 `模型訓練評估與驗證` 改為
`53模型訓練評估與驗證`（標題補上印刷編號 5.3）。學習平台唯一引用的 DOM anchor 是 `4交叉驗證`，新舊 `headings` 都有同一筆
`{"id": "4交叉驗證", "level": 3, "title": "4. 交叉驗證"}`，且 `block-168.anchor` 未變；`content/learning` 中沒有任何紀錄引用其他 heading id。

依 `data-contracts.md` §5，不同 sourceHash 時不得猜最近 block。本次不需要猜：`blocks` 陣列整體與舊版 `==`，被引用 block 的 id、
所有欄位（含 `bbox`）、quote 唯一命中與 DOM anchor 均相同；維護者已於 2026-11-03 核准只換雜湊。

## 被引用 block 盤點與逐欄位比對

盤點沿用前例方式（2026-11-03 實跑 `grep -rHoE 'block-[0-9]+'` 掃 `content/learning/{units,identity,labs,projects}`、頂層 `evidence/*.json`、`evidence/assessment/`，
排除 `superseded/` 與 review），現行 GuideRef 只有下列四個。另 `block-70`／`148`／`167` 只出現在 anchor history（`263987fb…` 版），
`block-77` 只出現在 `assessment/recall-formula-direct-view.md`（歷史敘述），`evidence-guide-hash-rebind-20261102-diff.json` 的 claim 文字提到 block-3／71，皆非 GuideRef，本次不改。

| anchorId | block | pageIndex | quote | 新版命中 | 新舊 block 逐欄位全等 | 引用者 |
|---|---|---|---|---|---|---|
| mid-s2c4-data-quality | block-3 | 56 | 若資料本身存在缺漏、錯誤、格式不一致等問題，將直接導致模型預測失真 | `block-3` 唯一 | ✓ | unit-split-before-fit、evidence-mid-s2c4-data-quality |
| mid-s3c9-accuracy-imbalance | block-71 | 154 | 95%樣本為負類時，即使模型全預測為負，準確率仍高達95% | `block-71` 唯一 | ✓ | unit-imbalanced-classification、evidence-mid-s3c9-accuracy-imbalance |
| mid-s3c9-imbalance-strategies | block-149 | 158 | 類別不平衡處理與評估策略 | `block-149` 唯一 | ✓ | unit-imbalanced-classification、evidence-mid-s3c9-imbalance-strategies |
| mid-s3c9-cross-validation | block-168 | 159 | 4. 交叉驗證（DOM anchor `4交叉驗證`） | `block-168` 唯一 | ✓ | unit-threshold-decision、evidence-mid-s3c9-cross-validation |

「逐欄位全等」指 `git show 8717147:<檔>` 與工作樹檔中同 id 的 block dict 以 Python `==` 比較為真；本次更強：兩檔的整個 `blocks` 陣列 `==`。
四張頁面 PNG（page_056、154、158、159）未改動，實測 sha256 與 evidence 的 `artifactHash` 相同
（`297a74ad…`、`f81f7863…`、`77d7d1a5…`、`b9aba37f…`）。

## 改了什麼

- `data/resource_catalog.json`：`learning-guide-middle-2`、`learning-guide-middle-3` 的 `version`／`sha256` 換成新 blob hash（numstat `4 4`）。
- `content/learning/identity/guide-anchors.json`：四筆 `current.sourceHash` 換成新值；`blockIds`、`pageIndexes`、`quote`、`anchor` 不變。
  舊的 `{sourceHash, blockIds, nodeId}` 追加到 `history`（既有 history 保留），各 anchor 的 `evidenceIds` 追加本證據 id `evidence-guide-hash-rebind-20261103-diff`。
- 四筆 guide_location evidence：`revision` +1（mid-s2c4 2→3；mid-s3c9 三筆 3→4），`guideRef.sourceHash` 換新值，
  `observedAt` 四筆都由 `2026-11-02T00:00:00Z` 改為 `2026-11-03T00:00:00Z`；`blockIds`、`locator`、`claim`、`excerpt`、`artifactRef`、`artifactHash` 不變；
  `contentHash` 以 `learning.contracts.content_hash` 重算。
- 三個 unit：`dependencies[0]` 與 claim `sourceRefs` 的 guide snapshot `revision`／`hash`、`guideRefs[*].sourceHash`；`contentHash` 以 repo API 重算；`reviewIds` 指向新 review。
  **revision 維持 1**，理由同前例（in_review、從未發佈；改 revision 會牽動 lab／project 的 `unitRefs` 與 contentHash）。正文 `.md` 未改。
- lab／project：只更新 `reviewIds`（被 contentHash 排除的生命週期欄位；lab 的 `semanticReviewId` 比照前例不動）；兩者 contentHash 不變。
- exam-analysis `analysis-imbalanced-source-examples-v1`：其 `catalogHash` 是 `data/resource_catalog.json` 整檔 blob hash，
  catalog 兩列 hash 更新使它由 `sha256:1912806b845d…` 變為 `sha256:55fbefd9e363…`，analysis contentHash 隨之由
  `sha256:a0fec784b20b…` 變為 `sha256:6506c6f3242e…`；analysis 其他欄位不變（反推見下）。這是同一次雜湊重綁的連帶結果，比照前例重新開立 review。

| 實體 | 舊 | 新 |
|---|---|---|
| unit-imbalanced-classification (r1) | `sha256:9cad43d95be4…` | `sha256:7d21f4237f8c…` |
| unit-threshold-decision (r1) | `sha256:73b75b70c1ac…` | `sha256:40b2b0d2ffd5…` |
| unit-split-before-fit (r1) | `sha256:f314aa80b30f…` | `sha256:b90d3d3a552f…` |
| evidence-mid-s2c4-data-quality | r2 `sha256:dc1c9b076e45…` | r3 `sha256:870119fc1f58…` |
| evidence-mid-s3c9-accuracy-imbalance | r3 `sha256:00e25fdd49e9…` | r4 `sha256:6f26585ec3a1…` |
| evidence-mid-s3c9-imbalance-strategies | r3 `sha256:daa7269d006d…` | r4 `sha256:52de1e72dbc3…` |
| evidence-mid-s3c9-cross-validation | r3 `sha256:235ff00644fb…` | r4 `sha256:09f6347cc45e…` |
| analysis-imbalanced-source-examples-v1 | `sha256:a0fec784b20b…` | `sha256:6506c6f3242e…` |
| data/resource_catalog.json（整檔） | `sha256:1912806b845d…` | `sha256:55fbefd9e363…` |
| lab-imbalanced-classification | `sha256:6aeb2aeb2702…` | 不變 |
| project-imbalanced-classification | `sha256:c333d0600d3c…` | 不變 |

## 可重跑的反推證明

基準固定為 `8717147`（round 4 講義修正與本次重綁之前的 HEAD），因此 commit 之後仍可重跑。
腳本先做 block 逐欄位與 quote／DOM anchor 核對；再把新 hash 換回舊 hash（兩種寫法 `sha256:`／`sha256-`；evidence 另還原 `revision`／`observedAt`；
analysis 把 `catalogHash` 換回基準版 catalog 的 blob hash）後重算，必須精確得到基準記錄的指紋；最後核對 superseded 檔逐 byte 等於基準原檔。

```bash
source .venv/bin/activate && python3 - <<'PY'
import json, pathlib, subprocess, sys
sys.path.insert(0, "scripts")
from learning.contracts import content_hash, blob_hash
from learning.references import ReferenceResolver
from build_learning_assessment import assessment_inputs
ROOT = pathlib.Path(".").resolve()
BASE = "8717147"  # round 4 前、本次重綁前的 HEAD
git = lambda p: subprocess.run(["git", "show", f"{BASE}:{p}"], capture_output=True, check=True).stdout
head = lambda p: json.loads(git(p))
# 1) 被引用 block 逐欄位比對與 quote 唯一命中
REFS = {"中級-guide2/mid-s2c4": ["block-3"], "中級-guide3/mid-s3c9": ["block-71", "block-149", "block-168"]}
anchors_now = {a["anchorId"]: a["current"] for a in json.loads((ROOT / "content/learning/identity/guide-anchors.json").read_text(encoding="utf-8"))["anchors"]}
PAIRS = []
for g, ids in REFS.items():
    p = f"frontend/src/generated/guideContent/{g}.json"
    ob, nb = git(p), (ROOT / p).read_bytes()
    PAIRS.append((blob_hash(nb), blob_hash(ob)))
    o, n = json.loads(ob), json.loads(nb)
    print(g, blob_hash(ob)[:15], "->", blob_hash(nb)[:15], "changed top-level keys:", sorted(k for k in set(o) | set(n) if o.get(k) != n.get(k)),
          "blocks list ==", o["blocks"] == n["blocks"], len(o["blocks"]), "->", len(n["blocks"]))
    obi = {b["id"]: b for b in o["blocks"]}; nbi = {b["id"]: b for b in n["blocks"]}
    for i in ids:
        a = next(c for c in anchors_now.values() if c["blockIds"] == [i] and c["nodeId"] == g.split("/")[1])
        hits = [b["id"] for b in n["blocks"] if a["quote"] in ((b.get("text") or "") + " " + (b.get("title") or ""))]
        print(" ", i, "fields ==", obi[i] == nbi[i], "pageIndex", nbi[i]["pageIndex"], "in", a["pageIndexes"], "anchor", nbi[i].get("anchor"), "==", a["anchor"], "quote hits", hits)
    for anc in [c["anchor"] for c in anchors_now.values() if c["anchor"] and c["nodeId"] == g.split("/")[1]]:
        print("  DOM anchor", anc, "in old headings", any(h["id"] == anc for h in o["headings"]), "in new headings", [h for h in n["headings"] if h["id"] == anc])
# 2) 反推：新 hash 換回舊 hash 後重算，必須等於 BASE 記錄的指紋
def restore(text):
    for new, old in PAIRS:
        text = text.replace(new, old).replace("sha256-" + new[7:], "sha256-" + old[7:])
    return json.loads(text)
resolver = ReferenceResolver(ROOT)
for u in ("unit-imbalanced-classification", "unit-threshold-decision", "unit-split-before-fit"):
    p = f"content/learning/units/{u}.json"; r = restore((ROOT / p).read_text(encoding="utf-8")); o = head(p)
    print(u, content_hash("learning-unit", r, body_bytes=resolver.body_bytes(r)) == o["contentHash"], "diff fields:", sorted(k for k in set(r) | set(o) if r.get(k) != o.get(k)))
for e in ("mid-s2c4-data-quality", "mid-s3c9-accuracy-imbalance", "mid-s3c9-imbalance-strategies", "mid-s3c9-cross-validation"):
    p = f"content/learning/evidence/evidence-{e}.json"; r = restore((ROOT / p).read_text(encoding="utf-8")); o = head(p)
    print(e, "observedAt", o["observedAt"], "->", r["observedAt"], "revision", o["revision"], "->", r["revision"], end=" ")
    r["revision"], r["observedAt"] = o["revision"], o["observedAt"]
    print(content_hash("evidence", r) == o["contentHash"], "diff fields:", sorted(k for k in set(r) | set(o) if r.get(k) != o.get(k)))
for p in ("content/learning/labs/lab-imbalanced-classification.json", "content/learning/projects/project-imbalanced-classification.json"):
    d = json.loads((ROOT / p).read_text(encoding="utf-8")); o = head(p)
    kind = "lab" if "/labs/" in p else "project"
    print(d["id"], "contentHash unchanged", d["contentHash"] == o["contentHash"], "diff fields:", sorted(k for k in set(d) | set(o) if d.get(k) != o.get(k)))
a = assessment_inputs(ROOT)["analysis"]; old = dict(a); old["catalogHash"] = blob_hash(git("data/resource_catalog.json"))
print("analysis", a["contentHash"], "catalogHash", a["catalogHash"], "restored ==", content_hash("exam-analysis", old) == head("content/learning/reviews/review-peer-d1-analysis-imbalanced-source-examples-v1-20261102-v4.json")["subject"]["hash"])
cat = restore((ROOT / "data/resource_catalog.json").read_text(encoding="utf-8")); print("catalog restored ==", BASE, cat == head("data/resource_catalog.json"))
anc = json.loads((ROOT / "content/learning/identity/guide-anchors.json").read_text(encoding="utf-8")); oa = head("content/learning/identity/guide-anchors.json")
for a1, a0 in zip(anc["anchors"], oa["anchors"]):
    c = dict(a1["current"]); c["sourceHash"] = dict(PAIRS)[c["sourceHash"]]
    print(a1["anchorId"], "current restored ==", c == a0["current"], "history prefix kept", a1["history"][:-1] == a0["history"],
          "new history = old current", a1["history"][-1] == {"sourceHash": a0["current"]["sourceHash"], "blockIds": a0["current"]["blockIds"], "nodeId": a0["current"]["nodeId"]},
          "evidenceIds +", a1["evidenceIds"][len(a0["evidenceIds"]):] if a1["evidenceIds"][:len(a0["evidenceIds"])] == a0["evidenceIds"] else "MISMATCH")
# 3) superseded 逐 byte
SUP = [("evidence/evidence-mid-s2c4-data-quality.json", "evidence/superseded/evidence-mid-s2c4-data-quality.r2.json")] + \
      [(f"evidence/evidence-mid-s3c9-{e}.json", f"evidence/superseded/evidence-mid-s3c9-{e}.r3.json") for e in ("accuracy-imbalance", "imbalance-strategies", "cross-validation")] + \
      [(f"reviews/review-{k}-{u}.json", f"reviews/superseded/review-{k}-{u}.json") for k in ("contract", "domain")
       for u in ("unit-imbalanced-classification-20261102-v4", "unit-threshold-decision-20261102-v4", "unit-split-before-fit-20261102-v3")]
for src, dst in SUP:
    print("superseded", dst.split("/")[-1], (ROOT / "content/learning" / dst).read_bytes() == git("content/learning/" + src))
PY
```

2026-11-03 實際執行結果（未 commit 的工作樹對 `8717147`）：

```text
中級-guide2/mid-s2c4 sha256:1d1eb632 -> sha256:b4559ebc changed top-level keys: ['content', 'headings'] blocks list == True 112 -> 112
  block-3 fields == True pageIndex 56 in [56] anchor None == None quote hits ['block-3']
中級-guide3/mid-s3c9 sha256:8b4b3996 -> sha256:c33286d7 changed top-level keys: ['content', 'headings'] blocks list == True 221 -> 221
  block-71 fields == True pageIndex 154 in [154] anchor None == None quote hits ['block-71']
  block-149 fields == True pageIndex 158 in [158] anchor None == None quote hits ['block-149']
  block-168 fields == True pageIndex 159 in [159] anchor 4交叉驗證 == 4交叉驗證 quote hits ['block-168']
  DOM anchor 4交叉驗證 in old headings True in new headings [{'id': '4交叉驗證', 'level': 3, 'title': '4. 交叉驗證'}]
unit-imbalanced-classification True diff fields: ['contentHash', 'reviewIds']
unit-threshold-decision True diff fields: ['contentHash', 'reviewIds']
unit-split-before-fit True diff fields: ['contentHash', 'reviewIds']
mid-s2c4-data-quality observedAt 2026-11-02T00:00:00Z -> 2026-11-03T00:00:00Z revision 2 -> 3 True diff fields: ['contentHash']
mid-s3c9-accuracy-imbalance observedAt 2026-11-02T00:00:00Z -> 2026-11-03T00:00:00Z revision 3 -> 4 True diff fields: ['contentHash']
mid-s3c9-imbalance-strategies observedAt 2026-11-02T00:00:00Z -> 2026-11-03T00:00:00Z revision 3 -> 4 True diff fields: ['contentHash']
mid-s3c9-cross-validation observedAt 2026-11-02T00:00:00Z -> 2026-11-03T00:00:00Z revision 3 -> 4 True diff fields: ['contentHash']
lab-imbalanced-classification contentHash unchanged True diff fields: ['reviewIds']
project-imbalanced-classification contentHash unchanged True diff fields: ['reviewIds']
analysis sha256:6506c6f3242eb45cc3e5a7558d351e883ef79fdb4365978f8d91b4f512251dd1 catalogHash sha256:55fbefd9e363eff7356322c0498a675e31f8ef67d159ae20add7c62d9510555d restored == True
catalog restored == 8717147 True
mid-s3c9-accuracy-imbalance current restored == True history prefix kept True new history = old current True evidenceIds + ['evidence-guide-hash-rebind-20261103-diff']
mid-s3c9-imbalance-strategies current restored == True history prefix kept True new history = old current True evidenceIds + ['evidence-guide-hash-rebind-20261103-diff']
mid-s3c9-cross-validation current restored == True history prefix kept True new history = old current True evidenceIds + ['evidence-guide-hash-rebind-20261103-diff']
mid-s2c4-data-quality current restored == True history prefix kept True new history = old current True evidenceIds + ['evidence-guide-hash-rebind-20261103-diff']
superseded evidence-mid-s2c4-data-quality.r2.json True
superseded evidence-mid-s3c9-accuracy-imbalance.r3.json True
superseded evidence-mid-s3c9-imbalance-strategies.r3.json True
superseded evidence-mid-s3c9-cross-validation.r3.json True
superseded review-contract-unit-imbalanced-classification-20261102-v4.json True
superseded review-contract-unit-threshold-decision-20261102-v4.json True
superseded review-contract-unit-split-before-fit-20261102-v3.json True
superseded review-domain-unit-imbalanced-classification-20261102-v4.json True
superseded review-domain-unit-threshold-decision-20261102-v4.json True
superseded review-domain-unit-split-before-fit-20261102-v3.json True
```

unit 還原後與基準只差 `contentHash`（還原時未改回）與 `reviewIds`（被 contentHash 排除的生命週期欄位）；
evidence 還原後只差 `contentHash`；lab／project 只差 `reviewIds`，contentHash 與基準相同。

## 舊紀錄的保存位置

比照前例：被新 revision 取代的 evidence 與以 `evidenceRefs` 精確綁定它們的 unit review，**原封不動（逐 byte）**移到 `superseded/`（上方輸出最後 10 行）：

- `content/learning/evidence/superseded/`：`evidence-mid-s2c4-data-quality.r2.json`、`evidence-mid-s3c9-{accuracy-imbalance,imbalance-strategies,cross-validation}.r3.json`
- `content/learning/reviews/superseded/`：unit-imbalanced-classification、unit-threshold-decision 的 `20261102-v4`，unit-split-before-fit 的 `20261102-v3`（domain＋contract）——共 6 檔

lab／project／analysis 的舊 review（`20261102-v4`）沒有綁這些 evidence revision，比照前例留在 `content/learning/reviews/`，新 review 以 `supersedes` 指向前一版。

## L0–L3 重跑

lab 本身 bytes 未變，只因相依 unit contentHash 改變而需重開 execution review。2026-11-03 作者在本機實跑
`uv run --isolated --group learning-lab python scripts/verify_learning_labs.py --lab lab-imbalanced-classification --profile cpu --check`，exit 0、L0–L3 pass，
紀錄 `evidence/assessment/lab-l0-l3-reverify-20261103-hash-rebind.json`。這不是 L4，也不是真人 Colab L5。
