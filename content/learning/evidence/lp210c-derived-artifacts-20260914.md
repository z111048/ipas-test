# LP-210C：衍生產物改帶穩定 id 的差異證據

日期：2026-09-14。這份證據支撐兩件事：(1) 四份 tracked 衍生產物與三個 gitignored 快取的改動**只有新增 id 欄位**，
沒有改到任何一筆標籤、判定或計數；(2) 兩份 export 產物可由來源位元重現。它**不**證明標籤本身標得對——
那是 2026-08 標註驗收（`question_topics.json` 的 `verifiedBy`／`verdictTally`）的職責，本包沒有改變任何判定。

沒有呼叫任何模型或 API：標註與快取由既有檔案回填（`assign_question_topics.py --backfill-ids`），export 產物是重跑腳本。
沒有動 `data/topics/topics.json`、`topic_id_assignments.json`、任何 id、`content/learning/**`、review 紀錄、glossary、production `current.json`。

## 改了什麼（設計見 `specifications/learning-platform/topic-id-migration.md` §10）

| 檔案 | 新增欄位 | 純新增的證明 |
|---|---|---|
| `data/topics/question_topics.json`（565 題、1,105 標籤） | 頂層 `stableIds`；每題 `topicIds`；`evidence[].topicId`；`droppedAsWrongIds` | 拆掉新欄位 == `git show HEAD:` 版本；`git diff --stat` 3,409 插入、0 刪除 |
| `data/topics/practice_question_topics.json`（580 題、880 標籤） | 同上 | 拆掉新欄位 == HEAD；2,985 插入、0 刪除 |
| `frontend/src/generated/topicHeat.json`（179 列） | 每列 `id`（排第一）；頂層 `stableIds` | 拆掉新欄位 == HEAD；重跑 byte-identical |
| `frontend/src/generated/conceptGraph.json`（178 概念、406 邊） | 每個概念 `id`、`previousNames`；`related[].id`；頂層 `stableIds`、`source.ledger`；移除 `generatedAt` | 拆掉新欄位 == HEAD（除時間戳）；重跑 byte-identical |
| `data/topics/_verify_cache.json`（558 筆、1,089 判定） | `topic-cache/v2` 封裝，每筆 `{topic, topicId, verdict}` | v2 → v1 逐字 == 備份原檔；0 個 null id |
| `data/topics/_verify_cache_practice.json`（580 筆、884 判定） | 同上 | 同上；18 個空白變體名稱（如「AI 基礎設施評估」）原字串保留、id 由 normalise 解析 |
| `data/topics/_assign_cache_practice.json`（590 筆、881 標籤） | v2，每筆 `{topic, topicId}` | v2 → v1 逐字 == 備份原檔；1 個 null id（模型自創「應用場景評估」，已在 `rejectedTopics`） |

`_assign_cache.json`（官方卷指派快取）本來就不存在，`--backfill-ids` 印出「不存在，略過」。

## 可重跑的證明

回填腳本自己在寫入前就做了同樣的檢查（不成立就拒絕寫入）；下面是作者**另外**用獨立程式對備份重算的結果。
tracked 產物的基準是 `git show HEAD:<path>`；gitignored 快取沒有版控基準，基準是回填前複製到 scratchpad 的唯讀備份：

```
0c61e01a3d070e1cd39d7795c43840a733118babcea04292d222c345b2265df2  _assign_cache_practice.json（原檔）
0bd3d5eec81f2484a507496ca1bcbedafe5d516ffaa637009d5a463d8c9aee83  _verify_cache.json（原檔）
e5525f9f2445dc26fe26087831aba307881a4016ed367ddbc9ab410453d62da8  _verify_cache_practice.json（原檔）
9ece9faef5d8f77dbe446c80737816dc5c3bb75b08a0e30e7a71037ba05459a5  conceptGraph.json（HEAD）
480a429fe40db0742cb9d807cd0be88e3573e15568d06e66e0fbfc706faa9d1d  practice_question_topics.json（HEAD）
eeac69d28ecb799458ea63d191a542d9d9ba7fa88b03701b004f409b764933f9  question_topics.json（HEAD）
9d70541ac6fd1548adc37675f17f15958cbaf45310cfa1a36f60cf8f9a13e262  topicHeat.json（HEAD）
```

tracked 四份可由任何人重算（快取那三份要有回填前原檔才能重算，備份不進版控）：

```bash
python3 - <<'PY'
import json, subprocess
def head(path): return json.loads(subprocess.run(['git', 'show', f'HEAD:{path}'], capture_output=True, text=True).stdout)
def strip_annotation(p):
    out = {k: v for k, v in p.items() if k != 'stableIds'}
    out['assignments'] = {k: {f: ([{kk: vv for kk, vv in ev.items() if kk != 'topicId'} for ev in v] if f == 'evidence' else v)
                              for f, v in e.items() if f not in ('topicIds', 'droppedAsWrongIds')} for k, e in p['assignments'].items()}
    return out
vocab = json.load(open('data/topics/topics.json')); ids = {t['name']: t['id'] for t in vocab['topics']}
for path in ('data/topics/question_topics.json', 'data/topics/practice_question_topics.json'):
    new = json.load(open(path)); assert strip_annotation(new) == head(path), path
    for e in new['assignments'].values():
        assert e['topicIds'] == [ids[n] for n in e['topics']] and all(ev['topicId'] == ids[ev['topic']] for ev in e['evidence'])
heat = json.load(open('frontend/src/generated/topicHeat.json')); s = dict(heat); s.pop('stableIds')
s['topics'] = [{k: v for k, v in t.items() if k != 'id'} for t in heat['topics']]; assert s == head('frontend/src/generated/topicHeat.json')
g = json.load(open('frontend/src/generated/conceptGraph.json')); old = head('frontend/src/generated/conceptGraph.json'); old.pop('generatedAt')
s = dict(g); s.pop('stableIds'); s['source'] = {k: v for k, v in s['source'].items() if k != 'ledger'}
s['concepts'] = [{**{k: v for k, v in c.items() if k not in ('id', 'previousNames')}, 'related': [{k: v for k, v in r.items() if k != 'id'} for r in c['related']]} for c in g['concepts']]
assert s == old; print('pure addition ✓')
PY
python3 scripts/assign_question_topics.py --backfill-ids | tail -1                     # 已寫入：（無變動）＝冪等
python3 scripts/assign_question_topics.py --source practice --backfill-ids | tail -1
for seed in 1 2; do PYTHONHASHSEED=$seed python3 scripts/export_topic_heat.py >/dev/null && sha256sum frontend/src/generated/topicHeat.json; done
for seed in 1 2; do PYTHONHASHSEED=$seed python3 scripts/export_concept_graph.py >/dev/null && sha256sum frontend/src/generated/conceptGraph.json; done
```

2026-09-14 實際執行結果：兩份標註 2,210／1,779 個 id 全部與詞彙表一致、拆掉後與 HEAD 逐欄相等；三個快取 v1 視圖與備份逐字相等；
`topicHeat.json` 與 `conceptGraph.json` 在 `PYTHONHASHSEED=1`／`2` 下 SHA-256 各自相同
（`e6e62806…4654c`、`78e07463…6bcc`）；回填重跑兩次都是「（無變動）」。

## 局部測試

- `uv run python tests/test_resource_catalog.py`：22 tests OK（新增 `TopicStableIdArtifactTests` 9 個：id 一致、attach 冪等與 fail-closed、改名依 id 更新、
  快取無損與 id 優先對齊、topicHeat／conceptGraph **位元**精確重建、export 拒絕重複／缺 id 的詞彙表、graph 拒絕 id／名稱不一致的標註、
  `verify_all` 拒絕 `--limit` 與過期名稱、盤點回報 `carriesStableIds`）。
- `node tests/frontend_checks/concept_lookup_check.cjs`（由 `tests/test_learning_frontend_static.py` 呼叫；用 frontend 的 typescript 轉譯 `conceptLookup.ts`，Node 20 可跑）：`?c=` 三段解析順序 11 條全部正確，
  含「兩個概念互換名字」——真實資料的 `previousNames` 目前全空，只有這個 fixture 走得到第三段。
- `(cd frontend && npx tsc -p tsconfig.app.json --noEmit)`：零錯誤。
- `uv run python tests/test_routes.py`：30 條正常路由＋2 條概念連結相容＋4 條錯誤路由全部正常。
  舊 `?c=生成式AI` 進站後網址改寫成 `#/concepts?c=topic-10f38c70`、標題是「生成式AI」；`?c=topic-10f38c70` 直達；
  `?c=topic-not-a-real-topic` 顯示「找不到概念」、無 console error。
- `(cd frontend && npm run build)`：tsc 零錯誤、vite 產出（1m42s）。

## 完整 20 項 gate

兩次執行，只有第二次算數：

| 次 | 條件 | 結果 |
|---|---|---|
| 1（2026-09-14 22:35–22:57） | 與非作者審查 agent **併行**（它同時跑了 52 次工具呼叫、多支 Python），另一個專案的 vite build 也在搶 CPU | 18/20：15 項靜態全過，`npm run build` 220 秒（平常 102 秒），`test_learning_state`／`test_learning_frontend` 在 30 秒等待處逾時。這兩支跑的是 `/learn`，與本包沒有共用檔案；但**這一次不當證據**，只記下來說明為什麼要重跑 |
| 2（2026-09-14 23:01–23:13） | 修正 F1–F8 之後、**無其他負載**、`UV_CACHE_DIR=/tmp/ipas-uv-cache uv run python tests/run_all.py`，沒有 `--skip-browser` | **20/20 PASS、exit 0、797 秒**；含 production build（156 秒）、初／中級 alignment、`audit_resources`、五支真 Chromium E2E |

第二次 gate 開跑前以 `sha256sum` 凍結 602 個檔（`git ls-files` 的 `content/`、`data/topics/`、`schemas/`、`scripts/`、`tests/`、`frontend/src/`
＋ untracked 同目錄檔 ＋ 三個 gitignored 快取），跑完 `sha256sum -c --quiet` 全部相符：受審來源在整段執行期間未變動。
兩次 gate 的 stdout 留在本機 scratchpad（`gate_run1_contended.log`、`gate.log`），不進版控。
本檔與 `topic-id-migration-review.md`、`lp210c-review-delegation-20260914.md` 是在第二次 gate **之後**才寫進 `content/learning/evidence/`
的 markdown；程式、測試與產物的 bytes 在 gate 之後未再變動。

教訓：完整 gate 與會大量跑 Python 的審查 agent **不要併行**——E2E 的 30 秒等待在 CPU 競爭下會偽裝成程式缺陷。

## 非作者審查

原定的 Codex CLI 於 2026-09-14 因登入 token 失效（`401 Unauthorized`，refresh token already used）無法使用，沒有產生任何審查內容；
改派一個沒有實作脈絡的全新 Claude Code 子代理（opus）做唯讀審查，只給驗收條件與作者宣稱，不給實作過程，
且不得跑 build／E2E（gate 由作者實跑）。審查者以 52 次工具呼叫實跑重現：10 項宣稱 9 項 PASS、
其中第 5／7／8 項帶 WARN，列出 3 項優先修正（F1 熱度腳本不擋重複 id、F2 `--limit` 洗快取的敘述不實、
F3 舊名解析單次 `find` 讓 previousNames 可蓋過正式名稱）與 5 項補強（F4 previousNames 零覆蓋、F5 證據檔尚未存在、
F6 自證鍵序不敏感、F7 名稱過期是裸 KeyError、F8 措辭不完整）。**全部已修**，修法與新測例對照表在
[`topic-id-migration-review.md`](topic-id-migration-review.md) 的 LP-210C 節（含審查報告全文）。
沒有第二輪；修正由新測例覆蓋並重跑完整 gate。委派範圍見 [`lp210c-review-delegation-20260914.md`](lp210c-review-delegation-20260914.md)。

## 明確不涵蓋

- 沒有重做任何標籤語意判定；`verdictTally`、`coverage`、`byModel` 等統計一個 byte 都沒變。
- glossary（`primaryGlossary.json`／`middleGlossary.json`）仍以中文名稱對齊：重生需要付費模型，不在本包；`export_concept_graph.py` 以詞彙表名稱去對 glossary 的 `zh`，改名後會對不到而顯示「這個概念還沒有名詞解釋」，不會錯配。
- `scripts/learning/assessment.py` 的 topic mapping／quota key 沿用 LP-210B 的決定（中文 canonical 名稱＋詞彙表驗證），不在本包。
- §3 未決事項 C（舊名連結的相容期）仍待維護者裁決；本包在裁決前的行為等同「永久接受」。
