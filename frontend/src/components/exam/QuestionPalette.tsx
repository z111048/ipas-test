import type { ReactNode, Ref } from 'react'
import { Badge } from '../ui'

/**
 * 題號盤（考試頁與章節練習頁共用）。
 *
 * - answered：已作答（考試頁，藍色 answered token）
 * - correct / wrong：已批改（練習頁）
 * - unanswered：未作答（中性）
 * - 當前題：外框（ring-accent），不改底色，讓狀態色仍看得出來。
 *
 * 注意 tests/test_exam_flow.py 以 `div.grid` 內 >= 40 顆 button 找題號盤，
 * 並以 class token `bg-answered-soft`／子字串 `ring-accent` 判斷已答與當前題：
 * 非當前題的按鈕不可出現任何含 `ring-accent` 的 class。
 */
export type PaletteStatus = 'answered' | 'unanswered' | 'correct' | 'wrong'

export interface PaletteItem {
  id: string
  status: PaletteStatus
}

const STATUS_LABEL: Record<PaletteStatus, string> = {
  answered: '已作答',
  unanswered: '未作答',
  correct: '答對',
  wrong: '答錯',
}

const STATUS_CLASS: Record<PaletteStatus, string> = {
  answered: 'border-answered-line bg-answered-soft text-answered',
  unanswered: 'border-unanswered-line bg-unanswered-soft text-unanswered',
  correct: 'border-correct-line bg-correct-soft text-correct',
  wrong: 'border-wrong-line bg-wrong-soft text-wrong',
}

const LEGEND_TONE: Record<PaletteStatus, 'answered' | 'neutral' | 'correct' | 'wrong'> = {
  answered: 'answered',
  unanswered: 'neutral',
  correct: 'correct',
  wrong: 'wrong',
}

interface QuestionPaletteGridProps {
  items: PaletteItem[]
  activeIndex: number
  onSelect: (index: number) => void
  /** Tailwind grid-cols classes; default fits a bottom sheet / side panel. */
  columnsClassName?: string
  activeButtonRef?: Ref<HTMLButtonElement>
}

export function QuestionPaletteGrid({
  items,
  activeIndex,
  onSelect,
  columnsClassName = 'grid-cols-5 sm:grid-cols-8 lg:grid-cols-5',
  activeButtonRef,
}: QuestionPaletteGridProps) {
  return (
    <div className={`grid gap-2 ${columnsClassName}`}>
      {items.map((item, index) => {
        const isActive = index === activeIndex
        return (
          <button
            key={item.id}
            ref={isActive ? activeButtonRef : undefined}
            type="button"
            className={`min-h-[44px] rounded-lg border px-1 py-2 text-ui font-semibold tabular-nums transition-colors ${
              STATUS_CLASS[item.status]
            } ${isActive ? 'border-accent ring-2 ring-accent/40 ring-offset-1' : ''}`}
            onClick={() => onSelect(index)}
            aria-current={isActive ? 'true' : undefined}
          >
            <span className="block" aria-hidden="true">{index + 1}</span>
            <span className="sr-only">
              第 {index + 1} 題，{STATUS_LABEL[item.status]}{isActive ? '，目前題' : ''}
            </span>
          </button>
        )
      })}
    </div>
  )
}

interface QuestionPaletteProps extends QuestionPaletteGridProps {
  /** Statuses to show in the legend (in order). */
  legend: PaletteStatus[]
  /** Short progress line, e.g. 「目前第 3 題 · 未答 12 題」. */
  summary?: ReactNode
  /** Extra buttons (跳到未答題、關閉…). */
  actions?: ReactNode
  /** Heading element id for aria-labelledby. */
  headingId?: string
  title?: string
  /** Hide the visible heading (e.g. inside a Dialog that has its own). */
  headingHidden?: boolean
}

/** 題號盤內容：標題、摘要、圖例、操作、格子。外框由呼叫端決定（側欄或底部抽屜）。 */
export default function QuestionPalette({
  legend,
  summary,
  actions,
  headingId,
  title = '題號盤',
  headingHidden = false,
  ...gridProps
}: QuestionPaletteProps) {
  return (
    <div>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 id={headingId} className={headingHidden ? 'sr-only' : 'section-title'}>
            {title}
          </h2>
          {summary && <p className="mt-1 text-meta text-text-light">{summary}</p>}
        </div>
      </div>
      {actions && <div className="mt-3 flex flex-wrap gap-2">{actions}</div>}
      <div className="mt-3 flex flex-wrap gap-1.5" aria-hidden="true">
        {legend.map((status) => (
          <Badge key={status} tone={LEGEND_TONE[status]}>
            {STATUS_LABEL[status]}
          </Badge>
        ))}
      </div>
      <div className="mt-3">
        <QuestionPaletteGrid {...gridProps} />
      </div>
    </div>
  )
}
