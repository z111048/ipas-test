# LP-210B：topic 引用機械式遷移的差異證據

日期：2026-09-09。這份證據支撐 13 筆因 `contentHash` 改變而失效的 review 的重新開立。
它證明的**只有一件事**：這次遷移對 authored 內容的改動，在 `contentHash` 所涵蓋的投影範圍內，
完全侷限在 `topicRefs`；教學正文（`bodyRef` 指向的 `.md`）與其餘所有參與雜湊的欄位都沒有變。

**證明的邊界（非作者審查者指出，這裡如實記錄）**：

- `contentHash` 是 canonical JSON **投影**，依契約排除 `contentHash`／`status`／`reviewIds`
  （lab 另排除 execution／semantic review id）。因此本證明不涵蓋這些被排除的欄位，
  也不涵蓋 JSON 排版差異。被排除的欄位本來就是生命週期 metadata，不影響教學內容。
- 它**不**證明教學內容本身正確——那是原本 domain review 的職責，本文件不取代它。

## 遷移做了什麼

`TopicRef` 從 `{name, vocabularyHash}` 改成 `{id, name}`：

```
- {"name": "資料洩漏", "vocabularyHash": "sha256:bbfedffc…"}
+ {"id": "topic-899e6a65", "name": "資料洩漏"}
```

動機：`vocabularyHash` 是**整份 `data/topics/topics.json` 的 blob hash**，而 resolver 在查
name 之前就無條件比對它。因此只要詞彙表動一個 byte——新增一個概念、修一個別名錯字——
現有每一筆 TopicRef 就全部失效，連帶所有綁在它們身上的 review 全部失效。
改用不可變 id 之後，新增概念不再影響既有引用，改名則由 id/name 交叉檢查擋下。

`data/topics/topics.json` 這次的改動是 **186 行純新增、0 行刪除**：181 個 `id` 欄位
加上 5 行 `stableIds` metadata。代號來自一次性隨機指派，帳本在
`data/topics/topic_id_assignments.json`，重建流程 `build_topic_vocabulary.apply_merge_pairs()`
會把帳本折回來，對不上就 exit 1。

## 可重跑的證明：只有 topicRefs 變動

不依賴任何人的備份。舊 review 紀錄裡的 `subject.hash` 是遷移前的內容指紋，
且這些紀錄**先於本次遷移就已存在、本次未被改動**；
（誠實補充：`content/` 目前整棵仍是 untracked，所以它們不是 Git 版控中的檔案，
只有 `data/topics/topics.json` 在版控裡——這個證明依賴的另一半 `git show HEAD:` 是版控的。）
把 `topicRefs` 還原成舊形狀（`{name, vocabularyHash}`，hash 取自 `git show HEAD:data/topics/topics.json`）
再重算 `contentHash`，若能精確還原成舊指紋，就證明其餘**參與雜湊投影的欄位值**都沒有改變。

```bash
UV_CACHE_DIR=/tmp/ipas-uv-cache uv run python - <<'PY'
import json, pathlib, subprocess, sys
sys.path.insert(0, "scripts")
from learning.contracts import content_hash, blob_hash
from learning.references import ReferenceResolver

ROOT = pathlib.Path(".").resolve()
old_vocab_hash = blob_hash(subprocess.run(["git", "show", "HEAD:data/topics/topics.json"],
                                          capture_output=True, cwd=ROOT).stdout)
resolver = ReferenceResolver(ROOT)
TARGETS = [("learning-unit", "units", ["unit-imbalanced-classification", "unit-split-before-fit",
                                       "unit-threshold-decision"]),
           ("project", "projects", ["project-imbalanced-classification"]),
           ("lab", "labs", ["lab-imbalanced-classification"])]
reviews = {p.stem: json.loads(p.read_text(encoding="utf-8"))
           for p in pathlib.Path("content/learning/reviews").glob("*.json")}
for kind, folder, ids in TARGETS:
    for entity_id in ids:
        doc = json.loads(pathlib.Path("content/learning", folder, entity_id + ".json").read_text(encoding="utf-8"))
        restored = dict(doc)
        restored["topicRefs"] = [{"name": r["name"], "vocabularyHash": old_vocab_hash} for r in doc["topicRefs"]]
        kwargs = {"body_bytes": resolver.body_bytes(restored)} if kind == "learning-unit" else {}
        recomputed = content_hash(kind, restored, **kwargs)
        recorded = {r["subject"]["hash"] for r in reviews.values()
                    if r["subject"]["id"] == entity_id and r["subject"]["kind"] in {kind, "unit"}}
        print(entity_id, recomputed in recorded, recomputed)
PY
```

2026-09-09 實際執行結果（全部相符）：

| 實體 | 還原後重算 | 舊 review 記錄的 subject.hash |
|---|---|---|
| unit-imbalanced-classification | `a8e8213fc629…` | `a8e8213fc629…` ✓ |
| unit-split-before-fit | `947a4dffcddf…` | `947a4dffcddf…` ✓ |
| unit-threshold-decision | `fb5b5b1985d5…` | `fb5b5b1985d5…` ✓ |
| project-imbalanced-classification | `c9553d68d5ff…` | `c9553d68d5ff…` ✓ |
| lab-imbalanced-classification | `5bb3dc8b27d1…` | `5bb3dc8b27d1…` ✓ |

`git show HEAD:data/topics/topics.json` 的 blob hash 是
`sha256:bbfedffc559834396aa3093b908409472ac26626e5976b196f4192ae3c093e3b`，
與遷移前每一筆 TopicRef 所記的 `vocabularyHash` 相同。

三份教學正文 `content/learning/units/*.md` 的 bytes 與遷移前相同——`bodyRef` 指向它們，
且它們以 `body_bytes` 參與 unit 的 `contentHash` 計算，所以上表相符本身就涵蓋了這一點。

Lab 的 `sourceNotebookRef` 與 `notebookHash` 兩個欄位值未改動；`notebookHash` 依契約排除
outputs 與 execution_count，所以這證明的是 notebook 的 cell ids／source／有作用的 metadata 未變，
不是整個 `.ipynb` 檔逐 byte 相同。

## analysis 的還原證明（與上表不同的欄位）

`analysis-imbalanced-source-examples-v1` 是 build 時產生的，它變動的**不只**是 topicRefs：
`measures[].topic`、`taxonomyHash`、以及由 mapping 集合算出的 `labelReviewHash` 三者都變了
（mapping 的 `target.ref` 也從 name+hash 改成 id+name）。上表那段程式不適用於它，
因此另外做一次還原：把這三者還原成遷移前的形式再重算 `contentHash`。

```bash
UV_CACHE_DIR=/tmp/ipas-uv-cache uv run python - <<'PY'
import json, pathlib, subprocess, sys
sys.path.insert(0, "scripts")
from learning.contracts import content_hash, blob_hash, value_hash
from build_learning_assessment import assessment_inputs

ROOT = pathlib.Path(".").resolve()
old_vocab = blob_hash(subprocess.run(["git", "show", "HEAD:data/topics/topics.json"],
                                     capture_output=True, cwd=ROOT).stdout)
docs = assessment_inputs(ROOT)["additional_documents"]
analysis = next(d for (k, _i, _r), d in docs.items() if k == "exam-analysis")
# 順序很重要：labelReviewHash 用的是 builder 的產生順序，不是排序後的順序。
mappings = [d for (k, _i, _r), d in docs.items() if k == "question-mapping"]
restored = json.loads(json.dumps(analysis))
for row in restored["measures"]:
    row["topic"] = {"name": row["topic"]["name"], "vocabularyHash": old_vocab}
restored["taxonomyHash"] = old_vocab
old_maps = json.loads(json.dumps(mappings))
for m in old_maps:
    m["target"]["ref"] = {"name": m["target"]["ref"]["name"], "vocabularyHash": old_vocab}
restored["labelReviewHash"] = value_hash(old_maps)
print(content_hash("exam-analysis", restored))
PY
```

2026-09-09 實際執行結果：還原後重算得到
`sha256:7fe21ecf929bd42c11c857cd3fd70ed209301eb47454a683a1cf839fa4cccbea`，
與兩筆舊 analysis review 記錄的 `subject.hash` 相同。
因此 analysis 的改動同樣**只**來自 topic 引用形式的變更，母體、分母、verdict、
inventory、exclusions 等統計內容都沒有變。

（附註：把 mapping 集合先排序再算 `labelReviewHash` 會得到
`sha256:042a18e5ec91…`，對不上——順序是這個證明的一部分。）

## 這次遷移後的新引用

12 筆 authored `topicRefs` 全部帶 id 並解析成功；3 個 topic 配額 key 仍是可讀的
canonical 名稱，但新增了對詞彙表的驗證（改名會讓 build 失敗）。
`migrate_topic_ids.py --dry-run` 報告：181/181 概念有 id、authored refs 15 筆、
`unresolvedStableIds=0`、`blocking=false`。

## Lab L0–L3 的本次重跑

notebook 與 fixture 的 bytes 沒有變，但 lab 封套的 `contentHash` 變了，
因此 `notebook_execution` 的 review 也要以新 hash 重新開立。
2026-09-09 實際執行
`uv run --group learning-lab python scripts/verify_learning_labs.py --lab lab-imbalanced-classification --profile cpu --check`
（exit 0），乾淨 kernel 跑完 solution 4.203 秒、starter 設定 4.048 秒、手動上傳模擬 4.059 秒，
報告存在 `content/learning/evidence/assessment/lab-l0-l3-reverify-20260909.json`。
這是 L0–L3，**不是** L4，也**不是**真人 Colab L5；後者仍未完成。
