# 學習平台資料契約與相容性規格

版本：1.0；狀態：目標資料契約；日期：2026-09-07。本文的 MUST 表示發佈阻擋條件。實際 MVP 完成與驗收範圍見 [progress.md](progress.md)，操作方式見 [mvp-runbook.md](mvp-runbook.md)。
配合 [架構](architecture.md)、[實作順序](implementation-plan.md) 與 [內容及 Colab](content-and-labs.md) 使用。
本文的 interface 定義必備欄位；實際可用的 JSON Schema、TypeScript 型別與 API 範圍以進度文件及 repository 實作為準。

## 1. 所有權與資料流

「committed」是版本控制政策，「generated」是產生方式，兩者並不互斥。所有新策展 source 必須 committed。

| 實體／關係 | 唯一 owner 與 source | 產物方向與提交政策 |
|---|---|---|
| 等級、科目、章節 | `build_manifest.py` → `data/{level}/toc_manifest.json` | 既有 committed manifest → 所有 chapter refs；不可複製章節表 |
| 考卷、來源、外部資料集 metadata | `data/resource_catalog.json` | 既有 catalog 擴充帶 namespace 的 resource ref、日期／權利欄位 → source index；不可另建來源清單 |
| Topic 名稱／別名／上位類 | `data/topics/topics.json` 與既有 merge/manual 決策流程 | 保留唯一詞彙權威；舊 name consumer 與新 ref adapter 共用 |
| Guide 原文 | PDF → `guide_ocr` → 既有 A／B pipeline | Track A `guideContent` 供讀者引用；Track B `guide/subjectN_guide.json` 供出題；兩者不可互換 |
| Guide 穩定定位 | `content/learning/identity/guide-anchors.json` | 只存定位及歷次映射 → generated resolved refs；不可複製 block 原文作另一權威 |
| 題目本體 | catalog 指向的 production 題庫／既有策展練習題庫 | 既有 committed 題庫 → generated question index/revision payload；新模型不得直接覆蓋 source |
| 題目 alias／family | `content/learning/identity/question-aliases.json`、`question-families.json` | 策展決策 → canonical index；重複檢測只產候選，人工核准才能合併 |
| Topic／Guide 題目關係 | 既有 `data/topics/*question_topics.json` + 新 `content/learning/mappings/*.json` | legacy adapter 讀舊標註；新 correction 明確 supersedes；同一 active edge 不得雙寫 |
| 實務補充 LearningUnit | `content/learning/units/<id>.json` + 同目錄 `<id>.md` | 編輯 source → 當次 release 的 `units/<id>.json`；不回寫 Guide |
| LearningPath／Project | `content/learning/paths/*.json`、`projects/*.json` | 路徑順序／交付任務 → generated indexes；既有 6 條 paths 遷入後移除 exporter 常數 |
| Lab 教學 metadata／程式 | `content/learning/labs/*.json`／`notebooks/labs/<id>.ipynb` | 單一 notebook → starter/solution；既有 `notebooks/{level}/*.ipynb` 保留 legacy source |
| Evidence／Review | `content/learning/evidence/*.json`、`reviews/*.json` | 策展事實與不可變審核 → release validation；模型草稿在 gitignored pipeline |
| ExamAnalysis／MockBlueprint | `content/learning/analysis-policies/*.json`、`mock-blueprints/*.json` | policy/blueprint committed；analysis snapshots 與發佈 pool 為 committed generated |
| Attempt／Progress | 瀏覽器 IndexedDB；未來同步服務擁有使用者資料 | 使用者本機資料與匯出檔，不提交 Git、不混入內容 release |

新增 generated indexes/分片一律在 `frontend/src/generated/learning/releases/<releaseId>/`，同層 `current.json` 是唯一啟用指標；本文的 units／pools 等產物相對路徑均相對此 release root。
Notebook 公開輸出在 `frontend/public/labs/<labId>/<revision>/`，全部不可變版本資產寫妥及驗證後才切指標；孤立未引用資產不影響舊release，清理另設GC工作包。
大型執行紀錄、草稿、staging、完整 stdout 為 gitignored `data/learning/pipeline/`，需實作 `.gitignore` 規則。
發佈 release manifest、分析快照、有效審核摘要、starter/solution 與必要來源指紋必須 committed，fresh checkout 能驗證。
舊 `learningArticles/`、`guideContent/`、`colabNotebooks/` 與路由保留相容輸出；一次只能有一個 writer。
不引進 graph database：目前 JSON 主表與有向邊已足夠；需要查詢時建立可重建索引，不建立第二份知識權威。

## 2. 共用版本、來源與發佈封套

```ts
type LevelId = 'junior' | 'middle'; // dataLevel 與 subjectId 一律查 catalog/manifest
type Hash = string; // sha256:<64 lowercase hex>，禁止 placeholder 進 release
type State = 'draft' | 'in_review' | 'published' | 'retired';
type ResourceRef = { namespace: 'exam' | 'resource'; levelId?: LevelId; key: string };
type SourceSnapshot = {
  resource: ResourceRef; revision: string; hash: Hash;
  selector?: string; // 外部 URL／授權只記在 catalog
} & (
  | { kind: 'repository'; hashScope: 'full_artifact'; artifactPath: string }
  | { kind: 'external'; hashScope: 'reviewed_capture'; retrievedAt: string; reviewDueAt: string;
      capture: { mode: 'permitted_excerpt' | 'authored_summary'; text: string };
      artifactPath?: string } // 只有允許重分發才存完整檔；repo relative
);
interface Envelope {
  schemaVersion: 1; id: string; revision: number; contentHash: Hash;
  status: State; reviewIds: string[]; dependencies: SourceSnapshot[];
}
type ChapterRef = { levelId: LevelId; subjectId: string; chapterId: string };
type TopicRef = { name: string; vocabularyHash: Hash; id?: string };
type EntityRef = { kind: 'unit' | 'project' | 'path' | 'lab'; id: string; revision: number };
type QuestionRef = { questionKey: string; revision: number; hash: Hash };
type EvidenceRef = { id: string; revision: number; hash: Hash };
interface LifecycleEvent {
  id: string; subject: { kind: string; id: string; revision: number; hash: Hash };
  from: State; to: State; reason: string; reviewIds: string[]; createdAt: string;
}
type PublicationResult = { status: 'published'; releaseId: string }
  | { status: 'blocked'; failedStage: 'schema' | 'references' | 'review' | 'execution' | 'integrity' | 'commit';
      affectedIds: string[]; errors: Array<{ code: string; evidenceIds: string[] }> };
```

1. `schemaVersion` 管結構；`revision` 管同一 entity 內容，不可拿 timestamp 取代。已發佈 revision 不可就地覆寫。
2. 結構化內容採排序 object keys、保留 array 順序、UTF-8 的 canonical JSON 計 SHA-256；排除 `contentHash`、執行時間、審核連結等非內容欄位。
3. 每種 schema 明列 hash projection：單元含 metadata+body bytes、題目含題幹/共用情境/選項/答案/解析/圖像內容 hash、notebook 含 cell ids/source/有作用的 metadata，排除 outputs/execution_count。
4. dependency fingerprint 包含來源 artifact hash；只記 Git commit 不足以辨認某一段改動。外部來源採 pinned snapshot hash + retrievedAt。
5. 產物 release manifest 記 `releaseId, schemaVersion, exporterVersion, inputHashes, files[{path,hash,size}]`；先寫不可變版本資產，再驗證完整候選，最後原子替換 `frontend/src/generated/learning/current.json` 指標；失敗不動現有 release。
6. catalog 新增來源時擴充既有 discriminated union／Python reader，驗唯一 `(namespace,levelId,key)`；禁止把 URL 清單藏進多份 Lab JSON。
7. 相依被修改／撤回時產 impacted IDs；審核以 subjectHash 和 dependency hashes 全等才有效，不能沿用舊 PASS。
8. 外部來源的 retrievedAt ≤ reviewDueAt（UTC ISO-8601）；過期以 build report 的 assessmentAt 判定，進待複核並阻擋依賴該主張的新發布。日期只是驗收輸入，不計入確定性產物時間戳；URL／授權 metadata 仍只存在 catalog。
9. external.hash 計算 canonical `{resource,revision,selector,capture}`；它僅證明審查過的合法節錄／自撰摘要沒有變動，不冒稱完整網頁 hash。不可重分發完整來源時 artifactPath 可省略；審查者仍需查原始 URL，Evidence 綁定查核內容與日期。

合法狀態轉換：`draft → in_review` 須 schema／references 通過；`in_review → draft` 表示退回修改；
`in_review → published` 須所有必要 review／execution／integrity gate 通過；`published → retired` 須有原因與有效撤回審查。
禁止 `draft → published`、`retired → published`。任何影響 contentHash 的修改均建立同 ID 的 revision+1/draft，
即使前版仍在審核也不覆寫其內容或 review；published 版仍可供讀取，直到新 release 切換或撤回。
status／reviewIds 是生命週期 metadata，排除於 contentHash；狀態變更保留 Git diff 與審查紀錄。
LifecycleEvent 保存於 `content/learning/reviews/lifecycle/*.json`，不可改寫；from 必須等於上一個有效狀態，subject hash／revision 必須完全相同，retired 事件的 reason／reviewIds 不得為空。
任一 stage 失敗只產生 blocked PublicationResult，保持 candidate 的 draft/in_review 與現行 release；不得先把 status 設 published 再檢查。
retired 的 ID 不重用；若修復內容再發佈，仍用原 ID 的新 revision 走完整 gate，舊 revision 保持 retired。

## 3. Topic 與章節相容性

現行 181 個 Topic 以 `name` 當 key，`aliases`、人工 additions/merge 決策已存在；MVP 必須接受 `TopicRef.name`。
第一階段 `name` 必須匹配該 vocabularyHash 下的 canonical name；別名只在 import adapter 正規化，不能模糊命中後直接發佈。
後續才在既有 `topics.json` 每筆追加不可變 `id`，例如 `topic-data-leakage`；保留 name/aliases，修改 build/apply-pairs 保留 id。
重新命名只更新 name 並保留 old name alias；合併的舊 id 以同一詞彙 SSOT 的 redirects 指向存活 id；拆分不得自動把舊標籤複製給所有新 id。
id 分配是一次策展，不可依排序編號或每次由當前名稱重算；migration 一對一驗證後才允許新 consumer 強制 id。
`chapterId=s1c3` 與 `mid-s3c9` 均原樣保留；`*pdf-cN` 為 outline 層，不可誤當 manifest chapter。
ChapterRef 由 manifest 查標題，LearningPath 可跨章／跨級，Topic 多對多連章，但不能把章節樹改成 Topic 樹。

## 4. 題目身分、修訂、alias 與題組

```ts
interface QuestionIdentity {
  questionKey: string; // q:<levelId>:<sourceKey>:<legacyId>
  levelId: LevelId; sourceKey: string; legacyId: string;
  kind: 'official' | 'sample' | 'chapter_practice' | 'guide_exercise';
  sourcePath: string; sourceNumber?: number; chapterRef?: ChapterRef;
  familyId: string; identityReview: 'legacy_unverified' | 'verified';
}
interface QuestionRevision {
  questionKey: string; revision: number; contentHash: Hash;
  format: 'single_choice'; // MVP 唯一可評分題型，其餘 quarantine
  stem: string; options: Array<{ optionId: string; text: string }>;
  correctOptionId: string; explanation: string;
  answerStatus: 'legacy_unverified' | 'verified' | 'disputed' | 'withdrawn';
  contextGroupId?: string; contextGroupRevision?: number; contextHash?: Hash; sourceOrder?: number;
  difficulty?: QuestionDifficulty; // generated 關聯投影，非題目本體 source
  assets: Array<{ resource: ResourceRef; hash: Hash; placement: string; answerLeakReviewId: string }>;
  reviewIds: string[]; sourceHashes: Hash[];
}
interface QuestionAlias {
  legacyNamespace: string; legacyId: string; questionKey: string;
  decision: 'verified' | 'ambiguous' | 'unresolved'; evidenceIds: string[];
}
interface ContextGroup {
  id: string; revision: number; contentHash: Hash; text: string;
  assets: Array<{ resource: ResourceRef; hash: Hash; answerLeakReviewId: string }>;
  members: Array<{ questionKey: string; revision: number; sourceOrder: number }>;
  contiguous: true; preserveSourceOrder: true; sourceHashes: Hash[]; reviewIds: string[];
}
interface QuestionDifficulty {
  id: string; question: QuestionRef; value: 'easy' | 'medium' | 'hard' | null;
  basis: 'editorial' | 'empirical' | 'unknown'; rubricVersion: string;
  rationale: string; evidenceIds: string[]; reviewIds: string[];
  sampleSize?: number; observationPeriod?: { from: string; to: string };
}
```

- 官方 sourceKey 使用 catalog `key`，routeKey 只管導覽；中級樣題 key=`sample`、routeKey=`midSample`，兩者不可混。
- 練習 sourceKey 使用既有 filename stem（`subject1_questions`／`subject1_guide_exercises`），levelId 不可省略；章節從容器取得，不靠 regex 成為新 SSOT。
- 例：`q:junior:sample:sample_q1` 與 `q:middle:sample:sample_q1` 必須是兩題；以 tuple 建索引，字串分隔符限定/escape，不能靠 `split` 猜 namespace。
- 舊 `jr_1141_s1:exam1_q7` → production `jr_1141_s1_q7`，初次遷移以卷別+題號提出候選，再比對題幹/選項/來源證據；不能只靠尾數核准。
- canonical key 不隨改字而改；題幹、答案、選項、圖片、解析任何語意修改都增加 revision，保留歷史 payload 供作答快照重播。
- optionId 初次取 `opt-A`…`opt-D`；顯示 A/B/C/D 是 presentation mapping。重新排序保留 id；替換不同語意選項應分配新 id，不可偷換老 option。
- 一份 source 內同 sourceNumber 重複／alias 一對多／題號空缺屬 inventory 錯誤；不能 last-write-wins。
- familyId 表同一道概念題的重刊或近似重製；初次每題獨立 family，合併需 review。analysis 同時支援 occurrence/family，模擬預設同 family 至多 1。
- shared context 以 `contextGroupId` 連 context source、成員 questionKeys、必須連續與原順序規則；候選 pool 中某成員不合格時整組不合格，禁止孤立出題。

QuestionRef.hash 必須等於該 QuestionRevision.contentHash；選題、mapping、path 與回饋全部使用這個 tuple，不另造 hash 欄位語意。
ContextGroup 從既有題庫的共用情境抽取；原始題庫無法無歧義表示時，唯一策展補充放 `content/learning/mappings/context-groups/*.json`。
同一來源情境只允許一個有效 owner。contentHash 只計 text／assets／sourceHashes，members 的版本與順序由 release manifest 一併鎖定，避免題目與 group hash 循環引用。
members 不可重複，sourceOrder 唯一且遞增；每個成員的 contextGroupId／revision／hash 必須反向一致，一題最多屬於一組；組內任何內容／順序／成員改變增加 group revision。
ContextGroup 必須包含完整文字與資產引用，不能只存 ID；題文快照與圖片版本亦須進 Attempt，避免原來源改動破壞續答。
Difficulty 的唯一策展 owner 為 `content/learning/mappings/question-difficulty/*.json`；generated QuestionRevision.difficulty 是 resolver 的投影，排除於題文本體 contentHash。
MVP 只允許 editorial 或 unknown：editorial 必有評量 rubric、理由與當前有效 assessment 審查；unknown 的 value 必為 null。
設置 difficulty quota 時，null／失效 review 不算該配額 eligible；沒有難度 quota 的卷可採未分級但其他資格完整的題。
empirical 是保留型別，本期發布 gate 拒絕啟用；後續必須先核准估計方法及最小樣本 policy，填 sampleSize／observationPeriod／證據後才能使用，不推算官方難度。

## 5. Guide 引用與來源更新

```ts
interface GuideRef {
  anchorId: string; levelId: LevelId; guideKey: string; nodeId: string;
  blockIds: string[]; sourceHash: Hash; pageIndexes: number[]; // 0-based PDF index
  quote: string; anchor: string | null; // 最短可核對節錄，非全文複本
  precision: 'exact' | 'parent' | 'chapter'; fallbackRoute: string;
}
interface GuideAnchorRecord {
  anchorId: string; current: GuideRef;
  history: Array<{ sourceHash: Hash; blockIds: string[]; nodeId: string }>;
  status: 'resolved' | 'needs_review' | 'orphaned'; evidenceIds: string[];
}
```

`guideKey` 是 generated key（如 `中級-guide3`），不是 subjectId `mid-s3`，也不是 sourceKey `guide3`；adapter 由 outlines 驗證三者關係。
現行 `block-N` 會重編，`heading.anchor` 可能隨文字修改；永久關係指向 registry `anchorId`，解析時再讀當前 blockIds。
初建由編輯選定章節/頁/節錄並核對 PDF；stable id 不由 block 順序產生。quote 僅輔助重定位，不代表引用正確性自動通過。
更新依序：相同 sourceHash→直接採用；不同 hash→同頁/相鄰頁/heading path/節錄找候選；只有人工核准才更新 current。
找不到、多個候選、章節拆合、原文撤回均標 needs_review/orphaned；保留 history，不猜最近 block 直接修補。
UI 可以明示「章節定位」回退 fallbackRoute，但不得把 parent/chapter 冒稱 exact；新發佈需要 exact 的證據則 fail-closed。
只依實際 `GuideContent.blocks[].anchor` 產生 hash link；recovered hierarchy heading 無 DOM anchor 不可製造假連結。
實務補充可指出教材未涵蓋的現實限制，但內文與 Guide 原文必須分來源；不能把編輯推論寫回 guide_ocr。

## 6. Evidence、Review 與題目映射

```ts
interface Evidence {
  id: string; revision: number; contentHash: Hash;
  kind: 'source_quote' | 'guide_location' | 'execution' | 'editorial_reasoning';
  source?: SourceSnapshot; guideRef?: GuideRef;
  claim: string; locator?: string; excerpt?: string; observedAt?: string;
  artifactRef?: string; artifactHash?: Hash;
}
interface Review {
  id: string; subject: { kind: string; id: string; revision: number; hash: Hash };
  dependencyHashes: Hash[]; rubricVersion: string; reviewerId: string;
  reviewerRole: 'human' | 'independent_model' | 'automated_check'; authorId: string;
  responsibility: 'domain_content' | 'assessment_answer' | 'notebook_execution' | 'deterministic_contract';
  qualification: { scope: string[]; evidenceIds: string[]; grantedBy: string; grantedAt: string };
  evidenceRefs: EvidenceRef[];
  verdict: 'approved' | 'changes_requested' | 'rejected' | 'incomplete';
  checks: Array<{ code: string; verdict: 'pass' | 'fail' | 'not_run'; evidenceIds: string[] }>;
  createdAt: string; supersedes?: string; rationale: string;
}
interface QuestionMapping {
  id: string; question: QuestionRef;
  target: { kind: 'topic'; ref: TopicRef } | { kind: 'guide'; ref: GuideRef };
  relation: 'assesses' | 'distractor_only' | 'prerequisite' | 'explained_by';
  verdict: 'correct' | 'too_broad' | 'incorrect' | 'unreviewed';
  evidenceIds: string[]; reviewIds: string[]; supersedes?: string;
  origin: 'legacy_import' | 'editorial';
}
interface ReviewPolicy {
  schemaVersion: 1; id: string; version: number;
  requirements: Array<{ subjectKind: string; responsibility: Review['responsibility'];
    allowedReviewerRoles: Review['reviewerRole'][]; qualificationScope: string;
    rubricVersion: string; requiredCheckCodes: string[]; independentFromAuthor: boolean }>;
}
```

舊 `verdict=正確` 可保留為 imported historical verdict，但沒有 source hash 的新 publication eligibility 為 `legacy_unverified`。
new mapping 應 keyed by `(questionKey,target,relation)`；correction 透過 supersedes 取代前一筆，檢查唯一 active edge、禁止循環 supersedes。
嚴格統計只採 `assesses + correct + 當前有效review`；distractor_only 不計考點，`explained_by` 引文不等於該題考察此 Topic。
適配既有歷史熱度時使用獨立 `legacy_strict_v1` policy：保留舊正確判定並顯示 source-bound review coverage，不可標示與新 strict 等價。
資料完整性／模型共識／內容正確性為不同 checks；not_run、模型空回、缺一個 label 的評價都不是 pass。
來源、答案或 taxonomy 改變使相依 review 失效；失效是計算狀態，不改寫過去的 approved 紀錄。
發佈至少需 domain reviewer 的內容審核與 deterministic checks 通過；authorId 不可同時作唯一 reviewer，遇 disputed 答案阻止進 mock pool。
Evidence 以 `(id,revision)` 不可變保存；任何 source／excerpt／claim／artifact 變更增加 revision，hash 計全部實質欄位，排除自身 contentHash。
Review.evidenceRefs 必須涵蓋其 checks／qualification 及受審物件引用的全部 evidenceIds，並綁定精確 revision/hash；缺件、重複版本或內容被改寫使 review 失效。
`content/learning/review-policy.json` 是唯一角色／rubric 閘門配置；MVP 每個新發布實體要求 domain_content + deterministic_contract，
題目另要求 assessment_answer，Lab 另要求 notebook_execution。前兩種語意責任允許 human 或 independent_model；notebook_execution允許human／automated_check，deterministic_contract要求automated_check。
資格 scope 使用受審實體的 topic／domain 範圍 key；需由維護者 grantedBy 核准且有 evidence，reviewer 不得自行授予資格，模型名稱也不是資格。
gate 必須找到對應 responsibility、允許 reviewerRole、qualificationScope、rubricVersion 及全部 requiredCheckCodes=pass 的當前有效 approved Review；缺一項即阻擋。
MVP role 必要check codes：domain_content=`source_fidelity,objective_alignment,practical_accuracy`；assessment_answer=`answer_correct,distractors_valid`；notebook_execution=`L0,L1,L2,L3`（依內容規格）；deterministic_contract=`schema,references,hash_integrity`。
Lab另加兩條policy requirement：domain_content要求L4；notebook_execution且reviewerRole=human要求L5的Colab smoke／發布走查，不能以自動check代替。LP-010將這組基線寫進policy，role未具名或空requiredCheckCodes不得發布。
domain_content／assessment_answer 必須 independentFromAuthor=true；相同 authorId 改用另一 role 不算獨立審查。資格與規則是版控審查資料，不需要先建立帳號服務。

## 7. 實務補充、學習路徑與專題

```ts
interface LearningUnit extends Envelope {
  title: string; summary: string; bodyRef: string; levelIds: LevelId[];
  chapterRefs: ChapterRef[]; topicRefs: TopicRef[]; guideRefs: GuideRef[];
  gapStatement: string; objectives: Array<{ id: string; action: string; condition: string;
    criterion: string; assessmentIds: string[] }>;
  prerequisites: Array<{ kind: 'unit' | 'skill'; ref: string; diagnosticPrompt: string; remediationRef: string }>;
  estimatedMinutes: number;
  sections: Array<{ id: string; kind: 'context' | 'concept_bridge' | 'worked_example' |
    'guided_practice' | 'independent_practice' | 'misconceptions' | 'assessment_reflection';
    bodyAnchor: string; objectiveIds: string[]; claimIds: string[] }>;
  claims: Array<{ id: string; kind: 'source' | 'editorial' | 'example'; text: string; sourceRefs: SourceSnapshot[] }>;
  assessments: Array<{ id: string; kind: string; prompt: string; objectiveIds: string[]; expectedEvidence: string; rubricId: string }>;
  rubrics: Array<{ id: string; criteria: Array<{ criterion: string; passEvidence: string }> }>;
  evidenceIds: string[]; labRefs: EntityRef[]; projectRefs: EntityRef[];
}
type PathStepTarget =
  | { kind: 'unit' | 'project' | 'lab'; id: string; revision: number; hash: Hash }
  | { kind: 'article'; id: string; contentHash: Hash }
  | { kind: 'guide'; ref: GuideRef }
  | { kind: 'practice'; chapter: ChapterRef; practiceSet: 'chapter' | 'guide'; questions: QuestionRef[] }
  | { kind: 'simulation'; blueprintId: string; revision: number; hash: Hash };
interface LearningPath extends Envelope {
  title: string; audience: string; outcomes: string[];
  steps: Array<{ stepId: string; target: PathStepTarget;
    required: boolean; prerequisiteStepIds: string[] }>;
}
interface Project extends Envelope {
  title: string; brief: { scenario: string; problemStatement: string; constraints: string[] };
  topicRefs: TopicRef[]; chapterRefs: ChapterRef[]; unitRefs: EntityRef[]; labRefs: EntityRef[];
  milestones: Array<{ id: string; title: string; requiredUnitIds: string[]; task: string;
    deliverableIds: string[]; prerequisiteIds: string[]; acceptanceCriteria: string[] }>;
  rubric: Array<{ id: string; criterion: string; weight: number; passEvidence: string }>;
  deliverables: Array<{ id: string; format: string; requiredFields: string[]; maxBytes: number; rubricCriterionIds: string[] }>;
}
```

每個 LearningUnit MUST 有至少一個可驗收 objective、實務情境、與指引概念的連接、操作/決策、失敗案例和 checkpoint；不得只把原文重排當實務補充。
objective ID 全域唯一，格式固定 `<unitId>::<localId>`；單元、Lab steps/checks、cell metadata 的 objectiveIds 全部使用此 qualified ID。resolver 驗 unit 存在且 objective 屬於 Lab.unitRefs，不接受裸 `obj-1`。
bodyRef 只能指向自身 source subtree，Markdown HTML sanitize；rendered section id 來自策展 section id，不能靠標題 slug 當永久連結。
Project 必須產出可評量成果，例如比較基準模型/混淆矩陣/成本假設的決策報告；LearningPath 只負責順序，不和 Project 合併。
前置依賴須檢查 cycle、dangling ref、未發佈 revision；rubric weights 合計 100，outcome 必須對上 assessment 或 deliverable。
PathStepTarget 不允許 kind=path，避免路徑引用自身／遞迴嵌套；steps 的 prerequisiteStepIds 只能引用同一路徑，且整圖須無環。
practice 只連既有章節練習，questions 必須完整列出該章／set 本次可用的題目（至少一題），與既有 route 顯示集合一致；任意子集或跨章組卷一律用 simulation blueprint。
來源 route 由 adapter 依現有 manifests／catalog 產生，禁止在 target 中另存可漂移的硬編 URL；article contentHash 與 guide sourceHash 綁定本次來源版。
既有 `LearningArticle` 仍是閱讀載體，id=s1c3 等不變；在其旁邊查關聯 units/projects/labs。搬遷 6 條 path 後由同一 writer 產生舊 articleIds 格式。

## 8. Lab 及執行證據

```ts
type LabPhase = 'setup' | 'worked' | 'guided' | 'independent' | 'check' | 'reflection';
interface LearningCellMetadata {
  labId: string; revision: number; cellId: string; phase: LabPhase;
  objectiveIds: string[]; audience: 'both' | 'solution'; starterSource?: string;
}
interface Lab extends Envelope {
  title: string; unitRefs: EntityRef[]; chapterRefs: ChapterRef[]; topicRefs: TopicRef[];
  objectiveIds: string[]; sourceNotebookRef: string; notebookHash: Hash;
  environment: { pythonVersion: string; lockRef: string; lockHash: Hash; kernelName: string;
    runtimeProfile: string; seed: number };
  executionPolicy: { cpuOnly: boolean; maxMemoryMb: number; cellTimeoutSeconds: number;
    totalTimeoutSeconds: number; networkPolicy: 'offline' | 'approved_resources' };
  datasets: Array<{ resource: ResourceRef; hash: Hash; version: string; fallbackResource?: ResourceRef }>;
  steps: Array<{ id: string; phase: LabPhase;
    cellIds: string[]; objectiveIds: string[]; estimatedMinutes: number; expectedArtifacts: string[] }>;
  checks: Array<{ id: string; objectiveIds: string[]; artifactRef: string; predicate: string;
    tolerance?: number; bounds?: [number, number]; severity: 'block' | 'warn' }>;
  rubric: Array<{ criterion: string; passEvidence: string }>; reflectionPrompts: string[];
  artifacts: Array<{ variant: 'starter' | 'solution'; path: string; hash: Hash; revision: number; size: number }>;
  executionReviewId?: string; semanticReviewId?: string;
}
```

`LearningCellMetadata` 存每個 cell 的 `metadata.learning`；notebook 根 `metadata.learning` 另存一致的 labId／revision。
程式碼練習 cell 的 `starterSource` 替換 solution source；僅 solution 可見的 Markdown／完整答案由 audience 控制，派生 starter 移除解答 metadata。
draft 可用空 artifacts、缺少 executionReviewId／semanticReviewId；published 必須有兩種 variant 資產及當前有效審核，不能以空字串代替。
artifacts 由 exporter 生成，review IDs／建置 URL 不計入 notebook sourceHash；來源或環境內容變動使相關執行及語意審核失效。
notebook 與 JSON steps 引用的 cellId 集合必須一致且唯一；解答 cell 的 starterSource 明確替換內容，兩 variant 由單一 source 派生，禁止各自維護。
runtime/資料集用 pinned 版本+hash；權利、下載位置、授權與歸屬查 catalog；金鑰不得出現在 notebook、輸出或公開測試資料。
檢查必須 Run all 乾淨 kernel、累積 cells、無跳過必要 cell、含 assertions；starter 的 TODO 以預期未完成處理，不能宣稱全解通過。
完整 solution 需重新執行；starter 另驗可打開、setup可執行、TODO位置一致且無解答洩漏。runtime/依賴/資料集改變重跑。
公開 Colab URL 應指向包含 notebook 的實際 commit SHA；若輸入 tag，須先解析為 SHA，不能把可移動 tag 當固定版本。sourceHash 不等時不得沿用舊 execution evidence。固定 seed 只提供可重現設定，不保證跨環境位元一致。
41 本 legacy notebook 先登錄清單與舊結果，不自動升級：原來的 pass/warn 或 skippedCells>0 不能代替新檢查。

## 9. 歷屆分析快照與分母

LP-310 擴充既有 catalog 的 exam metadata：`session:CatalogSession|null`、`questionSegments:[{subjectId,questionIds,evidenceIds}]`，
以及帶官方來源證據的 `publicationInventory`；由既有 Python reader／前端 catalog schema 同步讀取，沒有證據的 session 保持 unknown。
兩份 sample 現行 subjectId=null 且跨科，逐題科目只能由上述經來源核對的 segments／單科卷 subjectId 決定，不從 topic 或 optional chapterRef 猜測。
segments 不可重複或重疊題 ID，subjectId 必須在 manifest；尚未分科題歸 unknownSubject，保留在全卷分母。科目 filter 額外顯示 unknownSubject 題數，不假定它們不屬於該科。
missingSessions 只讀 catalog 中有證據的 publicationInventory，現有 key/title 不足以建立完整歷年發佈史。

```ts
type SessionKey = string; // canonical "roc-115-r01"，只由catalog session推導
type CatalogSession = { year: number; round: number }; // 民國年正整數；round為1..99
interface AnalysisPolicy {
  id: string; revision: number; levelIds: LevelId[]; subjectIds: string[];
  kinds: Array<'official' | 'sample'>; examKeys: Array<{ levelId: LevelId; key: string }>;
  fromSession?: SessionKey; toSession?: SessionKey; mappingPolicy: 'source_bound_strict_v1' | 'legacy_strict_v1';
  unit: 'occurrence' | 'family'; answerPolicy: 'include_with_status' | 'verified_only';
}
interface ExamAnalysis {
  schemaVersion: 1; id: string; policy: AnalysisPolicy; policyHash: Hash;
  catalogHash: Hash; contentHash: Hash; taxonomyHash: Hash; labelReviewHash: Hash;
  releaseId: string; inventory: Array<{ levelId: LevelId; examKey: string; kind: 'official' | 'sample';
    expected: number | null; present: number; labelReviewed: number; answerDisputed: number }>;
  publicationCoverage: { sessionsKnown: SessionKey[]; sessionsIncluded: SessionKey[];
    missingSessions: Array<{ session: SessionKey; reason: 'not_available' | 'not_ingested' | 'unknown' }>;
    exhaustive: boolean; evidenceIds: string[] };
  measures: Array<{ scopeKey: string; topic: TopicRef; population: number; reviewed: number;
    matched: number; unknown: number; prevalence: number | null; reviewedPrevalence: number | null;
    lowerBound: number | null; upperBound: number | null }>;
  exclusions: Array<{ reason: string; count: number }>;
}
```

SessionKey 固定為 `roc-` + 民國年十進位至少補滿3位 + `-r` + round補滿2位，例如 `{year:115,round:1}` → `roc-115-r01`。
排序與起訖篩選使用解析後的 `(year,round)` 數值比較（含兩端），不可用字串排序或從examKey猜期別；`fromSession <= toSession`。
coverage各陣列去重後依此排序；所有非unknown session都必須能在本次catalog／publicationInventory找到，沒有第二份session registry。
無日期證據的樣題 session=null，不產造 SessionKey；啟用日期範圍時不計入已知期別分布，但獨立顯示unknownSession題數及排除原因。

1. `catalogHash` 含來源/kind/session/inventory；`contentHash` 是所選 questionKey+revision+hash 的排序 digest；`taxonomyHash` 含詞彙/redirects；`labelReviewHash` 含 active mapping/review/有效性。任一改變須重算快照。
2. catalog 才是卷別母體：先依 level/subject/session/kind 選卷，再按 policy answerPolicy 決定題目集合 P；MVP default official + occurrence + include_with_status，不因沒標籤而先刪題。
3. 樣題獨立 scope，不算歷屆趨勢；若使用者選 all_sources，至少分列 official/sample，不能把混合比例命名為歷屆考頻。
4. `population=N=|P|`，`reviewed=R` 為題目已完成該 policy 全量 Topic 標註審核的集合，含「確認沒有適用Topic」；未貼某標籤不等於已確認不考此概念。
5. `matched=M` 為 R 中對當前 Topic 有有效 assesses/correct edge 的 distinct 題；`unknown=U=N-R`。一題多個同名證據、跨兩章引用或多標籤都只算一次該 Topic。
6. `prevalence=M/N` 僅 R=N 且 N>0 時輸出，否則 null；`reviewedPrevalence=M/R` 在 R>0 輸出且明示為已審樣本比例；lowerBound=M/N、upperBound=(M+U)/N，N=0皆null。
7. Topic filter 只選要顯示的 Topic rows，**不改卷別分母 P**；題型／答案狀態 filter 若啟用需先套到 P 並顯示 exclusions；chapter filter 需獨立 chapter mapping coverage，未分類題不得隱形刪除。
8. chapter 條件下：以確認 belongs 的題為章內 P，另列 chapter-unclassified count；不能自稱全卷代表性。guide/outline 分開展示，不把同內容兩層的章數相加。
9. `unit=occurrence` 表不同卷出現各算一次；同卷同題僅一次。family 模式以已核准 familyId 合併，輸出 family identity coverage；未核准不得宣稱已做跨卷語意去重。
10. disputed 答案仍可作「曾考此概念」的 occurrence，需有效 Topic review 並另列 disputed count；正確率/成績排除 disputed，政策與分母必須可見。
11. 已收錄年份不等於官方完整發佈史；missingSessions 只能由帶證據的 catalog publication inventory 推導，未知是否存在的年份標unknown，禁止補0畫連續趨勢。
12. 不從少量作答資料推定官方難度或預測考題；difficulty 依 §4 的 owner／basis／review，MVP 僅 editorial 或 unknown，不發布 empirical 估計。

本機基線：正式題 600、樣題 115；現有概念標註為正式 450 + 樣題 115，缺 3 份中級 1151 卷的 150 題。
`565` 是既有標註筆數，不能當正式歷屆總題數；練習 590 題其中 assigned 580，也不能把缺的 10 題當無考點。

## 10. 模擬組題、答案隔離與失敗語意

```ts
type MockPoolRef = { id: string; releaseId: string; hash: Hash };
interface MockPool {
  schemaVersion: 1; id: string; releaseId: string; contentHash: Hash;
  policyHash: Hash; annotationSnapshotHash: Hash;
  questions: Array<{ question: QuestionRef; payloadPath: string; fileHash: Hash;
    identityReview: 'verified'; mappingReviewIds: string[]; difficultyReviewIds: string[] }>;
  groups: Array<{ id: string; revision: number; hash: Hash; members: QuestionRef[] }>;
}
interface MockBlueprint extends Envelope {
  title: string; levelId: LevelId; subjectIds: string[]; questionCount: number; timeLimitSeconds: number;
  poolRef: MockPoolRef; kinds: QuestionIdentity['kind'][]; format: 'single_choice';
  quotas: Array<{ id: string; dimension: 'topic' | 'chapter' | 'difficulty'; key: string;
    min: number; max: number; mode: 'hard' | 'soft'; priority: number }>;
  seedPolicy: 'user_or_generated'; algorithmVersion: 'mock-selector-v1';
  uniqueFamily: true; contextPolicy: 'atomic_keep_order'; optionOrder: 'fixed' | 'seeded';
  scoring: { correct: number; incorrect: 0; unanswered: 0; passingPercent: number };
}
type AssemblyResult = { status: 'ready'; formId: string; seed: string; blueprintHash: Hash;
  poolRef: MockPoolRef; poolHash: Hash; selectedQuestionRevisions: QuestionRef[];
  slotAssignments: Array<{ question: QuestionRef; dimension: 'topic' | 'chapter' | 'difficulty'; quotaId: string }>;
  displayedOptionIds: Array<{ question: QuestionRef; optionIds: string[] }>; softMisses: string[] }
  | { status: 'insufficient_pool' | 'unsupported_format' | 'stale_pool';
      reason: 'unsatisfied_constraints' | 'search_limit' | 'unsupported_format' | 'stale_pool';
      unmet: Array<{ rule: string; required: number; eligible: number }>; suggestions: string[] };
```

MockPool 保存於該 release 的 `pools/<poolId>.json`，payloadPath 指向同 release 的問題版本分片；questions、groups 按 canonical key 排序。
Blueprint、AssemblyResult與Attempt均保存同一MockPoolRef；以`releases/<poolRef.releaseId>/pools/<poolRef.id>.json`唯一解析，並驗id/releaseId及contentHash=poolRef.hash；不按目前release或第一個pool猜測。
poolHash是poolRef.hash的演算法用別名，保存兩者時必須相等；同release可有多個pool，每個id唯一。舊pool不可用時回stale_pool，不默默改用最新版。
poolHash=MockPool.contentHash，計除自身 hash／releaseId 以外的全部欄位；releaseId 由輸入 hashes＋exporterVersion計算，不用含自身的檔案bytes反算，避免雜湊循環。
候選必須 identityReview=verified、無 ambiguous/unresolved alias、answerStatus=verified、hash-bound內容/答案/圖片審核有效、assets可解析、未撤回；MVP用已審既有題或已審新題，不在使用者點開始時呼叫生成模型。
涉及 quota 的 topic/chapter mapping 或 difficulty 必須有當前有效 review 並凍結在 annotationSnapshotHash；僅歷史 legacy 判定不構成新pool資格。
先把 shared context 轉為原子候選 bundle，檢查 quota/family/重刊原題、單選格式；多選、缺答案、disputed、來源失效均拒絕。
每個 quota 維度以一題最多一個 quota slot 計量（多Topic先決定主要slot），可跨不同維度各計一次；禁止一題同時填三個Topic配額而仍算3題。
slotAssignments 以 `(questionKey,revision,dimension)` 唯一；quotaId 必須存在且 dimension 一致、題目符合該 quota key。同一題最多三筆（各維度一筆），不可由重複記錄充數；序列固定按題目顯示位置、dimension字典序、quotaId字典序排列。
固定演算法輸入序列用 canonical JSON array 的 UTF-8 bytes；題目／bundle 排序分數為 SHA-256(`["question",seed,poolHash,blueprintHash,algorithmVersion,candidateKey]`)。
candidateKey 是獨立題 canonical key 或 `context:<groupId>:<revision>`；按 digest 升冪，同分按 candidateKey 升冪，組內維持 sourceOrder。
求解採此排序的 depth-first backtracking；quota 槽按 priority 降冪、quotaId 升冪選擇。soft quota損失=`max(min-count,0)+max(count-max,0)`；按priority降冪各加總，損失向量取字典序最小，最後以selected canonical keys序列打破平手，不讀時鐘／Math.random。
`optionOrder=fixed` 使用 source option 順序；seeded 對每題以 SHA-256(`["option",seed,poolHash,blueprintHash,algorithmVersion,questionKey,revision,optionId]`) 升冪排列，同分用 optionId 升冪。
`question`／`option` domain separation 避免共用隨機序列互相影響；displayedOptionIds 存入 AssemblyResult 與 Attempt，只改顯示位置，不改 correctOptionId 或 optionId。
求解器固定最多 100000 個搜尋節點，超限回 insufficient_pool 並 reason=search_limit（不宣稱數學上無解）；正式發佈 blueprint 必須在固定驗收seed集合可求解。
seed 統一為32位小寫hex（128 bits）；未指定用 Web Crypto產生後立即存入attempt，重播不得重生。非法使用者seed直接報格式錯誤。
formId=`form-`加SHA-256(canonical `[blueprintHash,poolHash,seed,algorithmVersion,selectedQuestionRevisions,displayedOptionIds,slotAssignments]`)；各陣列依上述確定性順序，實作 fixture 要比完整結果。
先滿足題數/level/subject/format/family/context/已審資格及所有 hard quotas，再依 priority 優化 soft quotas；明列 softMisses，不偷改 hard limits。
組題不足回各規則 required/eligible 與可選調整方案，使用者主動更改 blueprint 後重組；不可偷偷放入未審題、重複題或跨級湊數。
圖片需檢查整頁/表格是否含答案表、解說或其他題答案；只有 crop/reference本身經 answerLeakReview 才可進 pool。關閉解析文字不代表圖片無洩漏。
MVP公開靜態站是自我練習；作答視圖不載/顯示answer/explanation/card/solution等欄位，但使用者仍可下載公開資產，不宣稱防作弊或認證考試。
需考試級保密時另建授權伺服器的組卷/交卷/評分服務，答案不可送到提交前的 client；這不屬本期可驗收範圍。

## 11. Attempt 快照、評分與本機遷移

```ts
interface AttemptSnapshot {
  schemaVersion: 1; attemptId: string; mode: 'practice' | 'simulation'; status: 'active' | 'submitted' | 'abandoned';
  formId: string; releaseId: string; blueprintHash: Hash; poolRef: MockPoolRef; poolHash: Hash; seed: string; algorithmVersion: string;
  startedAt: string; deadlineAt: string | null; submittedAt: string | null;
  items: Array<{ questionKey: string; revision: number; contentHash: Hash; position: number;
    promptSnapshot: { stem: string; options: Array<{ optionId: string; text: string }> };
    assets: Array<{ path: string; hash: Hash }>; contextSnapshot?: string;
    displayedOptionIds: string[]; selectedOptionId: string | null; answeredAt: string | null }>;
  scoringSnapshot: { correct: number; incorrect: 0; unanswered: 0; passingPercent: number };
  result?: { score: number; eligibleCount: number; correctCount: number; invalidatedQuestionKeys: string[];
    answerKeySnapshot: Array<{ questionKey: string; revision: number; correctOptionId: string }> };
}
interface LearnerProgress {
  schemaVersion: 1; target: EntityRef; targetHash: Hash; writeVersion: number;
  state: 'not_started' | 'in_progress' | 'self_reported_complete';
  openedAt?: string; selfReportedAt?: string; updatedAt: string;
}
interface AttemptStorageEnvelope {
  schemaVersion: 1; writeVersion: number; snapshotHash: Hash;
  snapshot: AttemptSnapshot; importedFrom?: string;
}
interface ScoreAmendment {
  id: string; attemptId: string; originalSnapshotHash: Hash; createdAt: string;
  reason: 'answer_corrected' | 'question_disputed' | 'question_withdrawn';
  affectedQuestions: QuestionRef[]; evidenceRefs: EvidenceRef[];
  revisedResult: { score: number | null; eligibleCount: number; correctCount: number };
}
```

Progress 以 `(kind,id,revision)` 為 key；點擊 Colab 僅更新 openedAt／in_progress，只有使用者明確操作可設 self_reported_complete。
AttemptStorageEnvelope.snapshotHash 是完整 snapshot 的 canonical JSON hash，排除 storage writeVersion／importedFrom；儲存及匯入前都重算。ScoreAmendment 是獨立不可變紀錄，對同一原始snapshot可有多筆有日期的修正，UI並列原分數與最新適用修正。
MVP 不接收 Colab 自動回傳或 lab-report 匯入；P2 可選 `lab-result.json` 匯入依內容規格標示 unverified_import，不能改為可信 passed。
一般 Attempt／Progress JSON 備份匯出／匯入仍屬 MVP；新版 targetHash 不沿用舊版完成，保留舊紀錄供查看。
答案以 questionKey+revision+optionId 儲存，position 只作顯示；重新排序不能移動使用者原答案。快照含固定題文/圖hash/選項順序，不能只存seed後載最新題庫。
score = correctCount / eligibleCount ×100；passingPercent 是平台練習設定，不能推稱官方門檻；eligibleCount=0顯示不可評分，不給0分。
正式提交結果不可就地重算：題目後續爭議/更正另產 score amendment，保留原 result 和原因；active遇撤回標明影響並阻止用新答案靜默改判。
IndexedDB 使用一筆原子 attempt transaction 儲存；deadlineAt 為絕對時間，重整續答不可重設時限；逾時採自動提交，重複提交需 idempotent。
storage envelope 另帶 `writeVersion`；同 attempt 透過 IndexedDB transaction 比對版本後遞增，跨分頁只允許一個 active writer，以 BroadcastChannel 通知其餘分頁唯讀；搶寫衝突必須 reload，不合併互斥答案。
MVP預設最多保留100筆已交卷/50MB快照索引與內容；達限先提示匯出及由使用者選擇清理，不自動刪 active/未同步資料；圖片用版本化cache，獨立配額且可重新取得。
既有 localStorage `ipas:practice:{subjectId}:{chapterId}:{practiceSet}` 經 manifest+source namespace轉換；保留原檔，寫入成功並標 migrationVersion 後才停止讀舊key。
舊記錄沒有 revision/時間/題文，匯入標 `legacy_unversioned`，只顯示曾選答案，不納入跨版本成績或能力推估；不存在qid進orphan report，不丟棄也不配最近題。
目前 ExamStore 在記憶體中的既有 attempt 不可假裝能復原；換架構時新建測驗才套新快照。儲存滿/停用時顯示未保存，提供匯出並繼續當次操作。
匯入JSON檢查schema/大小/引用版本，禁止直接信任分數；同步服務是後續 adapter，不把匿名本機ID冒認跨裝置帳號。
單次匯入上限10MB；同attemptId且hash相同跳過，不同則以新attemptId另存importedFrom，保留兩份不覆寫；檔案含active attempt時降為歷史匯入，不能倒轉deadline恢復計時。

## 12. 一組具體關聯示範與驗收

以下 existing IDs 已在 repo 查到；新增 unit/lab/project/anchor 名稱與關係僅為設計示範，**不是已完成內容或審核結果**。

```json
{
  "unitId": "unit-split-before-fit",
  "chapterRef": { "levelId": "middle", "subjectId": "mid-s3", "chapterId": "mid-s3c9" },
  "topicRef": { "name": "資料洩漏", "vocabularyHash": "<build computes sha256>" },
  "guide": { "guideKey": "中級-guide3", "nodeId": "mid-s3c9", "blockIds": ["block-1"],
    "pageIndexes": [150], "anchor": "53模型訓練評估與驗證",
    "precision": "chapter", "fallbackRoute": "/guide/mid-s3/mid-s3c9" },
  "questionKey": "q:junior:jr_1151_s1:jr_1151_s1_q6",
  "labId": "lab-imbalanced-classification",
  "projectId": "project-imbalanced-classification",
  "reviewState": "draft"
}
```

上例不是 schema fixture；實作須計算所有 hash、補 exact guide evidence、完整 Topic/Guide mapping review，再產 validated fixture。
題目真的詢問正規化/標準化時避免資料洩漏；chapter heading只能證明章節存在，不能單獨支持「此段回答題目」的 claim。
驗收 fixture 最少覆蓋：兩級 sample_q1不碰撞、舊exam1_q7 alias、題序/選項改序答案不漂移、來源改hash審核失效、Guide block插入不誤連、Topic rename保留舊連結。
分析 fixture：正式3題，已審2題，同Topic2個edge只命中1題→M=1/R=2/N=3/U=1，prevalence=null、reviewed=1/2、bounds=[1/3,2/3]；另1樣題不改N。
模擬 fixture：同seed同pool同blueprint結果完全相同；少1題/題組缺員/hard quota不足/圖含答案/disputed都拒絕；改poolHash返回不同form identity。
發佈 gate 必須驗schema、外鍵、唯一性、cycle、review hashes、source ownership、determinism與原子rollback；前端執行完整build與既有必要測試，不為文件本身重跑OCR。
