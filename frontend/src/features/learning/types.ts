export type LevelId = 'junior' | 'middle'
export type Hash = `sha256:${string}`
export type ContentState = 'draft' | 'in_review' | 'published' | 'retired'
export type ResourceRef = {
  namespace: 'exam' | 'resource'
  levelId?: LevelId
  key: string
}

export type SourceSnapshot = {
  resource: ResourceRef
  revision: string
  hash: Hash
  selector?: string
} & (
  | { kind: 'repository'; hashScope: 'full_artifact'; artifactPath: string }
  | {
      kind: 'external'
      hashScope: 'reviewed_capture'
      retrievedAt: string
      reviewDueAt: string
      capture: { mode: 'permitted_excerpt' | 'authored_summary'; text: string }
      artifactPath?: string
    }
)

export interface Envelope {
  schemaVersion: 1
  id: string
  revision: number
  contentHash: Hash
  status: ContentState
  reviewIds: string[]
  dependencies: SourceSnapshot[]
}

export interface ChapterRef { levelId: LevelId; subjectId: string; chapterId: string }
export interface TopicRef { id: string; name: string }
export interface EntityRef { kind: 'unit' | 'project' | 'path' | 'lab'; id: string; revision: number }
export interface QuestionRef { questionKey: string; revision: number; hash: Hash }
export interface EvidenceRef { id: string; revision: number; hash: Hash }

export interface GuideRef {
  anchorId: string
  levelId: LevelId
  guideKey: string
  nodeId: string
  blockIds: string[]
  sourceHash: Hash
  pageIndexes: number[]
  quote: string
  anchor: string | null
  precision: 'exact' | 'parent' | 'chapter'
  fallbackRoute: string
}

export interface LearningObjective {
  id: string
  action: string
  condition: string
  criterion: string
  assessmentIds: string[]
}

export interface LearningUnit extends Envelope {
  title: string
  summary: string
  bodyRef: string
  levelIds: LevelId[]
  chapterRefs: ChapterRef[]
  topicRefs: TopicRef[]
  guideRefs: GuideRef[]
  gapStatement: string
  objectives: LearningObjective[]
  prerequisites: Array<{ kind: 'unit' | 'skill'; ref: string; diagnosticPrompt: string; remediationRef: string }>
  estimatedMinutes: number
  sections: Array<{
    id: string
    kind: 'context' | 'concept_bridge' | 'worked_example' | 'guided_practice' | 'independent_practice' | 'misconceptions' | 'assessment_reflection'
    bodyAnchor: string
    objectiveIds: string[]
    claimIds: string[]
  }>
  claims: Array<{ id: string; kind: 'source' | 'editorial' | 'example'; text: string; sourceRefs: SourceSnapshot[] }>
  assessments: Array<{ id: string; kind: string; prompt: string; objectiveIds: string[]; expectedEvidence: string; rubricId: string }>
  rubrics: Array<{ id: string; criteria: Array<{ criterion: string; passEvidence: string }> }>
  evidenceIds: string[]
  labRefs: EntityRef[]
  projectRefs: EntityRef[]
}

export type PathStepTarget =
  | { kind: 'unit' | 'project' | 'lab'; id: string; revision: number; hash: Hash }
  | { kind: 'article'; id: string; contentHash: Hash }
  | { kind: 'guide'; ref: GuideRef }
  | { kind: 'practice'; chapter: ChapterRef; practiceSet: 'chapter' | 'guide'; questions: QuestionRef[] }
  | { kind: 'simulation'; blueprintId: string; revision: number; hash: Hash }

export interface LearningPath extends Envelope {
  title: string
  audience: string
  outcomes: string[]
  steps: Array<{ stepId: string; target: PathStepTarget; required: boolean; prerequisiteStepIds: string[] }>
}

export interface Project extends Envelope {
  title: string
  brief: { scenario: string; problemStatement: string; constraints: string[] }
  topicRefs: TopicRef[]
  chapterRefs: ChapterRef[]
  unitRefs: EntityRef[]
  labRefs: EntityRef[]
  milestones: Array<{ id: string; title: string; requiredUnitIds: string[]; task: string; deliverableIds: string[]; prerequisiteIds: string[]; acceptanceCriteria: string[] }>
  rubric: Array<{ id: string; criterion: string; weight: number; passEvidence: string }>
  deliverables: Array<{ id: string; format: string; requiredFields: string[]; maxBytes: number; rubricCriterionIds: string[] }>
}

export type LabPhase = 'setup' | 'worked' | 'guided' | 'independent' | 'check' | 'reflection'
export interface LearningCellMetadata {
  labId: string
  revision: number
  cellId: string
  phase: LabPhase
  objectiveIds: string[]
  audience: 'both' | 'solution'
  starterSource?: string
}

export interface Lab extends Envelope {
  title: string
  unitRefs: EntityRef[]
  chapterRefs: ChapterRef[]
  topicRefs: TopicRef[]
  objectiveIds: string[]
  sourceNotebookRef: string
  notebookHash: Hash
  environment: { pythonVersion: string; lockRef: string; lockHash: Hash; kernelName: string; runtimeProfile: string; seed: number }
  executionPolicy: { cpuOnly: true; maxMemoryMb: number; cellTimeoutSeconds: number; totalTimeoutSeconds: number; networkPolicy: 'offline' | 'approved_resources' }
  datasets: Array<{ resource: ResourceRef; hash: Hash; version: string; fallbackResource?: ResourceRef }>
  steps: Array<{ id: string; phase: LabPhase; cellIds: string[]; objectiveIds: string[]; estimatedMinutes: number; expectedArtifacts: string[] }>
  checks: Array<{ id: string; objectiveIds: string[]; artifactRef: string; predicate: string; tolerance?: number; bounds?: [number, number]; severity: 'block' | 'warn' }>
  rubric: Array<{ criterion: string; passEvidence: string }>
  reflectionPrompts: string[]
  artifacts: Array<{ variant: 'starter' | 'solution'; path: string; hash: Hash; revision: number; size: number }>
  executionReviewId?: string
  semanticReviewId?: string
}

export interface ReviewPolicy {
  schemaVersion: 1
  id: string
  version: number
  requirements: Array<{
    subjectKind: string
    responsibility: 'domain_content' | 'assessment_answer' | 'notebook_execution' | 'deterministic_contract'
    allowedReviewerRoles: Array<'human' | 'independent_model' | 'automated_check'>
    qualificationScope: string
    rubricVersion: string
    requiredCheckCodes: string[]
    independentFromAuthor: boolean
  }>
}

export interface MockPoolRef { id: string; releaseId: string; hash: Hash }
export interface LearnerProgress {
  schemaVersion: 1
  target: EntityRef
  targetHash: Hash
  writeVersion: number
  state: 'not_started' | 'in_progress' | 'self_reported_complete'
  openedAt?: string
  selfReportedAt?: string
  updatedAt: string
}

export interface AttemptSnapshot {
  schemaVersion: 1
  attemptId: string
  mode: 'practice' | 'simulation'
  status: 'active' | 'submitted' | 'abandoned'
  formId: string
  releaseId: string
  blueprintHash: Hash
  poolRef: MockPoolRef
  poolHash: Hash
  seed: string
  algorithmVersion: string
  startedAt: string
  deadlineAt: string | null
  submittedAt: string | null
  items: Array<{
    questionKey: string
    revision: number
    contentHash: Hash
    position: number
    promptSnapshot: { stem: string; options: Array<{ optionId: string; text: string }> }
    assets: Array<{ path: string; hash: Hash }>
    contextSnapshot?: string
    displayedOptionIds: string[]
    selectedOptionId: string | null
    answeredAt: string | null
  }>
  scoringSnapshot: { correct: number; incorrect: 0; unanswered: 0; passingPercent: number }
  result?: { score: number; eligibleCount: number; correctCount: number; invalidatedQuestionKeys: string[]; answerKeySnapshot: Array<{ questionKey: string; revision: number; correctOptionId: string }> }
}

export interface ReleaseManifest {
  schemaVersion: 1
  releaseId: string
  availability: 'preview' | 'published'
  exporterVersion: string
  inputHashes: Record<string, Hash>
  entities: Array<{ kind: string; id: string; revision: number; contentHash: Hash; path: string }>
  files: Array<{ path: string; hash: Hash; size: number }>
  gates: Array<{ stage: 'schema' | 'references' | 'review' | 'execution' | 'integrity' | 'commit'; status: 'passed' | 'failed' | 'not_run'; evidenceIds: string[] }>
}
