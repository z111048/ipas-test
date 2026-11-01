import { useState, type ReactNode } from 'react'
import type { SavedExamAttempt } from '../../store/examStore'
import type { ExamData } from '../../types'
import { navLabel } from '../../constants/navLabels'
import { ConfirmDialog, PageHeader } from '../ui'

interface ExamIntroProps {
  examData: ExamData
  onStart: () => void
  savedAttempt?: SavedExamAttempt | null
  onResume?: () => void
  /** Extra notice under the header (e.g. deep-link target question). */
  notice?: ReactNode
}

function formatClock(seconds: number) {
  const minutes = Math.floor(seconds / 60)
  return `${minutes}:${String(seconds % 60).padStart(2, '0')}`
}

export default function ExamIntro({ examData, onStart, savedAttempt, onResume, notice }: ExamIntroProps) {
  const canResume = Boolean(savedAttempt && onResume)
  const answeredCount = savedAttempt ? Object.keys(savedAttempt.answers).length : 0
  const [confirmRestart, setConfirmRestart] = useState(false)

  return (
    <div className="page-shell">
      <PageHeader
        className="mb-5"
        eyebrow={navLabel('exam')}
        title={examData.exam}
        description={
          canResume && savedAttempt
            ? `你有一份尚未繳卷的作答，剩餘時間 ${formatClock(savedAttempt.secondsRemaining)}。離開期間不計時。`
            : '開始後即計時，可隨時用題號盤切換題目，時間到會自動繳卷。'
        }
        meta={
          <div className="flex flex-wrap gap-2">
            <span className="pill">共 {examData.total} 題</span>
            <span className="pill pill-muted">考試時間：{examData.time_limit}</span>
            <span className="pill pill-muted">及格分數：{examData.passing_score} 分</span>
          </div>
        }
        actions={
          canResume && savedAttempt ? (
            <>
              <button type="button" className="btn-primary" onClick={onResume}>
                繼續上次作答（已答 {answeredCount} 題）
              </button>
              {/* 重新開始會丟掉上次作答：放次要位置（ghost），並先確認。 */}
              <button
                type="button"
                className="btn-ghost self-start"
                onClick={() => setConfirmRestart(true)}
                aria-haspopup="dialog"
              >
                重新開始
              </button>
            </>
          ) : (
            <button type="button" className="btn-primary" onClick={onStart}>
              開始考試
            </button>
          )
        }
      />
      {notice}
      <ConfirmDialog
        open={confirmRestart}
        title="確認重新開始"
        heading="要放棄上次的作答嗎？"
        cancelLabel="保留上次作答"
        confirmLabel="清除並重新開始"
        onCancel={() => setConfirmRestart(false)}
        onConfirm={() => {
          setConfirmRestart(false)
          onStart()
        }}
      >
        <p>重新開始會清除上次已答的 {answeredCount} 題與剩餘時間，並從第 1 題重新計時。</p>
      </ConfirmDialog>
    </div>
  )
}
