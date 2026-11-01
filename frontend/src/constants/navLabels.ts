/**
 * 導覽命名表：route → 使用者可見名稱。
 *
 * 規則（使用者決定）：以「頁面標題」為正式名稱，Header／Sidebar／Footer／按鈕／麵包屑一律引用這裡。
 * 公告試題統一稱「公告試題」。
 *
 * 不得在此列章節或科目清單（CLAUDE.md 不變量 1）：科目名稱一律由 toc_manifest 經
 * data/resourceRegistry.ts 取得，再用下方 formatSubjectLabel() 統一前綴格式。
 */

export interface NavLabelEntry {
  /** Route pattern as declared in App.tsx (`:param` segments). */
  route: string
  /** Canonical user-visible label (= page title). */
  label: string
  /** Variants used before unification; kept for audits/tests, never render these. */
  previousVariants?: readonly string[]
}

export const NAV_LABELS = {
  home: { route: '/', label: '首頁' },
  subject: { route: '/subject/:subjectId', label: '科目總覽' },
  practice: { route: '/practice/:subjectId/:chapterId', label: '章節練習' },
  guidePractice: {
    route: '/practice/:subjectId/:chapterId/guide',
    label: '學習指引練習',
    previousVariants: ['指引練習'],
  },
  exam: {
    route: '/exam/:examKey',
    label: '公告試題',
    previousVariants: ['測驗', '試題庫', '歷屆公告試題', '公告題', '考'],
  },
  guide: { route: '/guide/:subjectId/:chapterId', label: '學習指引' },
  articles: {
    route: '/articles',
    label: '主題式文章',
    previousVariants: ['主題文章'],
  },
  learn: { route: '/learn', label: '實務補充' },
  projects: { route: '/projects', label: '實務專題', previousVariants: ['成果專題', '做中學'] },
  labs: { route: '/labs/:labId', label: '實作練習' },
  simulations: {
    route: '/simulations/:blueprintId',
    label: '主題診斷',
    previousVariants: ['10 題主題診斷'],
  },
  analysis: { route: '/analysis/exams', label: '精選例題對照' },
  visuals: { route: '/visuals', label: '概念圖卡' },
  images: {
    route: '/images',
    label: '教材圖片與表格',
    previousVariants: ['圖片總覽', '圖表總覽', '初級圖片與表格', '中級圖片與表格'],
  },
  glossary: {
    route: '/glossary',
    label: '關鍵字整理',
    previousVariants: ['名詞解釋'],
  },
  concepts: {
    route: '/concepts',
    // 頁面標題原為「概念、定義與考過的題目」（描述句，不適合當導覽名）；
    // 正式名稱取「概念索引」，頁面請改為 title=概念索引、該句移到 description。
    label: '概念索引',
    previousVariants: ['概念、定義與考過的題目'],
  },
  outline: {
    route: '/outline',
    label: '學習指引目錄',
    previousVariants: ['完整目錄'],
  },
  mindmap: {
    route: '/mindmap',
    label: '章節熱度圖',
    previousVariants: ['考點熱度圖', '概念熱度'],
  },
  notFound: { route: '*', label: '找不到頁面' },
} as const satisfies Record<string, NavLabelEntry>

export type NavLabelKey = keyof typeof NAV_LABELS

/** Section headings inside the sidebar / home level cards. */
export const SECTION_LABELS = {
  /** Sidebar per-level group listing official exams + official samples. */
  exams: '公告試題',
  /** Sidebar per-level group listing official PDFs / references. */
  references: '官方資料',
} as const

export const SITE_NAME = 'iPAS AI 應用規劃師備考平台'
export const SITE_TAGLINE = '官方資料、學習指引、公告試題與章節練習'

export function navLabel(key: NavLabelKey): string {
  return NAV_LABELS[key].label
}

/**
 * Canonical label for the section a pathname belongs to (Header context line,
 * breadcrumbs, document titles). Returns null for unknown routes.
 */
export function navLabelForPath(pathname: string): string | null {
  if (pathname === '/') return NAV_LABELS.home.label
  if (pathname.startsWith('/subject/')) return NAV_LABELS.subject.label
  if (pathname.startsWith('/practice/')) {
    return /\/guide\/?$/.test(pathname) ? NAV_LABELS.guidePractice.label : NAV_LABELS.practice.label
  }
  if (pathname.startsWith('/exam/')) return NAV_LABELS.exam.label
  if (pathname.startsWith('/guide/')) return NAV_LABELS.guide.label
  if (pathname.startsWith('/articles')) return NAV_LABELS.articles.label
  if (pathname.startsWith('/learn')) return NAV_LABELS.learn.label
  if (pathname.startsWith('/projects')) return NAV_LABELS.projects.label
  if (pathname.startsWith('/labs/')) return NAV_LABELS.labs.label
  if (pathname.startsWith('/simulations/')) return NAV_LABELS.simulations.label
  if (pathname.startsWith('/analysis/')) return NAV_LABELS.analysis.label
  if (pathname.startsWith('/visuals')) return NAV_LABELS.visuals.label
  if (pathname.startsWith('/images')) return NAV_LABELS.images.label
  if (pathname.startsWith('/glossary')) return NAV_LABELS.glossary.label
  if (pathname.startsWith('/concepts')) return NAV_LABELS.concepts.label
  if (pathname.startsWith('/outline')) return NAV_LABELS.outline.label
  if (pathname.startsWith('/mindmap')) return NAV_LABELS.mindmap.label
  return null
}

/** Separator between level and subject number: 「初級・科目一」. */
export const SUBJECT_PREFIX_SEPARATOR = '・'

export interface SubjectLabelParts {
  /** 「科目一」 (level prefix stripped from 「中級科目一」). */
  number: string
  /** 「人工智慧基礎概論」; empty if the manifest label has no 「：」. */
  name: string
  /** 「初級・科目一」 */
  short: string
  /** 「初級・科目一：人工智慧基礎概論」 */
  full: string
}

/**
 * Normalize a toc_manifest subject label (e.g. 「中級科目一：人工智慧技術應用與規劃」)
 * into the site-wide format. `levelLabel` comes from resourceLevels[n].label.
 */
export function formatSubjectLabel(levelLabel: string, manifestSubjectLabel: string): SubjectLabelParts {
  const colon = manifestSubjectLabel.indexOf('：')
  const rawNumber = (colon > -1 ? manifestSubjectLabel.slice(0, colon) : manifestSubjectLabel).trim()
  const name = colon > -1 ? manifestSubjectLabel.slice(colon + 1).trim() : ''
  const number = levelLabel && rawNumber.startsWith(levelLabel)
    ? rawNumber.slice(levelLabel.length).trim()
    : rawNumber
  const short = levelLabel ? `${levelLabel}${SUBJECT_PREFIX_SEPARATOR}${number}` : number
  return { number, name, short, full: name ? `${short}：${name}` : short }
}
