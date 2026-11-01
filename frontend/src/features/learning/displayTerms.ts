import type { Heading, Parent, Root, RootContent } from 'mdast'

/**
 * 學習內容的顯示用詞。
 *
 * 單元、專題與實作的原文（content/learning/*）以英文工作術語撰寫（validation、fit、row ID…），
 * 對考生不友善。這裡只在「顯示」時換成中文，第一次出現時保留英文於括號內（考試或工具實際使用的名稱），
 * 之後只顯示中文。原文、content hash 與審核紀錄都不受影響。
 *
 * 只處理一般文字：Markdown 的行內程式碼與程式碼區塊不會被改寫；駝峰式識別字（fitRowIds）也不會被比對到。
 */

interface TermRule {
  /** 比對的英文片語（不含前後空白）。 */
  pattern: string
  /** 第一次出現時的寫法。 */
  first: string
  /** 之後出現時的寫法；省略時與 first 相同。 */
  later?: string
  /** 共用「是否已出現過」狀態的鍵；省略時用 pattern。 */
  keys?: string[]
}

const RULES: TermRule[] = [
  { pattern: 'train／validation／test', first: '訓練集／驗證集／測試集（train／validation／test）', later: '訓練集／驗證集／測試集', keys: ['train', 'validation', 'test'] },
  { pattern: 'fit 與 transform', first: '擬合（fit）與轉換（transform）', later: '擬合與轉換', keys: ['fit', 'transform'] },
  { pattern: 'threshold search', first: '閾值搜尋' },
  { pattern: 'threshold selection', first: '閾值選擇' },
  { pattern: 'final evaluation', first: '最終評估' },
  { pattern: 'validation scores', first: '驗證集（validation）分數', later: '驗證集分數', keys: ['validation'] },
  { pattern: 'split manifest', first: '切分清單（split manifest）', later: '切分清單' },
  { pattern: 'row split', first: '逐列隨機切分' },
  { pattern: 'row IDs', first: '資料列編號' },
  { pattern: 'row ID', first: '資料列編號' },
  { pattern: 'fit rows', first: '擬合（fit）所用資料列', later: '擬合所用資料列', keys: ['fit'] },
  { pattern: 'baseline', first: '基準模型（baseline）', later: '基準模型' },
  { pattern: 'validation', first: '驗證集（validation）', later: '驗證集' },
  { pattern: 'train', first: '訓練集（train）', later: '訓練集' },
  { pattern: 'test', first: '測試集（test）', later: '測試集' },
  { pattern: 'transform', first: '轉換（transform）', later: '轉換' },
  { pattern: 'fit', first: '擬合（fit）', later: '擬合' },
  { pattern: 'thresholds', first: '閾值（threshold）', later: '閾值', keys: ['threshold'] },
  { pattern: 'threshold', first: '閾值（threshold）', later: '閾值' },
  { pattern: 'tie-break', first: '同分處理規則（tie-break）', later: '同分處理規則' },
  { pattern: 'lab', first: '實作練習' },
]

const BY_PATTERN = new Map(RULES.map((rule) => [rule.pattern, rule]))
const escape = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
// 長片語優先；英文前後不能緊鄰英數字或底線，避免改到 fitRowIds、DummyClassifier 等識別字。
const TERM_RE = new RegExp(
  `( ?)(?<![A-Za-z0-9_])(${[...RULES].sort((a, b) => b.pattern.length - a.pattern.length).map((rule) => escape(rule.pattern)).join('|')})(?![A-Za-z0-9_])( ?)`,
  'g',
)
const ASCII_WORD = /[A-Za-z0-9%]/

/** 一份文件內共用的「已出現過」紀錄，讓括號英文只出現一次。 */
export type TermMemory = Set<string>

export function localizeTerms(text: string, memory: TermMemory = new Set()): string {
  if (!text) return text
  let changed = false
  const result = text.replace(TERM_RE, (_match, before: string, term: string, after: string, offset: number) => {
    const rule = BY_PATTERN.get(term)
    if (!rule) return _match
    const keys = rule.keys ?? [rule.pattern]
    const seen = keys.every((key) => memory.has(key))
    keys.forEach((key) => memory.add(key))
    const replacement = seen ? rule.later ?? rule.first : rule.first
    // 中文之間的英文原本以空白分隔；換成中文後，只在旁邊仍是英數字時保留空白。
    const prev = text[offset - 1] ?? ''
    const next = text[offset + _match.length] ?? ''
    const lead = before && ASCII_WORD.test(prev) ? ' ' : ''
    const trail = after && ASCII_WORD.test(next) ? ' ' : ''
    changed = true
    return `${lead}${replacement}${trail}`
  })
  // 相鄰兩個術語都換成中文後，中間殘留的空白一併收掉。
  return changed ? result.replace(/([㐀-鿿）])[ ]+(?=[㐀-鿿（])/g, '$1') : result
}

/** 單元正文的段落鍵（Markdown 二級標題）對應的中文標題。 */
const SECTION_HEADINGS: Record<string, string> = {
  context: '情境',
  concept_bridge: '概念銜接',
  worked_example: '範例解析',
  guided_practice: '引導練習',
  independent_practice: '獨立練習',
  misconceptions: '常見錯誤',
  assessment_reflection: '自我評量與反思',
}

function headingText(node: Heading) {
  return node.children.length === 1 && node.children[0].type === 'text' ? node.children[0].value.trim() : undefined
}

function walk(node: Parent, memory: TermMemory) {
  node.children = node.children.filter((child: RootContent) => {
    // 正文開頭的一級標題與頁面標題重複；頁面只保留 PageHeader 的 <h1>。
    if (child.type === 'heading' && child.depth === 1) return false
    return true
  }) as typeof node.children
  for (const child of node.children as RootContent[]) {
    if (child.type === 'heading') {
      const key = headingText(child)
      if (key && SECTION_HEADINGS[key] && child.children[0].type === 'text') {
        child.children[0].value = SECTION_HEADINGS[key]
        continue
      }
    }
    if (child.type === 'text') child.value = localizeTerms(child.value, memory)
    else if (child.type === 'code' || child.type === 'inlineCode' || child.type === 'html') continue
    else if ('children' in child) walk(child as Parent, memory)
  }
}

/** remark 外掛：中文化段落標題與工作術語，並移除與頁面標題重複的一級標題。 */
export function remarkLearningTerms() {
  return (tree: Root) => walk(tree, new Set())
}
