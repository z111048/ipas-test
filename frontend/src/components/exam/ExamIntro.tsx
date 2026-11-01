import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import type { SavedExamAttempt } from '../../store/examStore'
import type { ExamData } from '../../types'
import { navLabel } from '../../constants/navLabels'
import { resourceLevels } from '../../data/resourceRegistry'
import { ConfirmDialog, PageHeader } from '../ui'

interface ExamIntroProps {
  examData: ExamData
  onStart: () => void
  savedAttempt?: SavedExamAttempt | null
  onResume?: () => void
  /** Extra notice under the header (e.g. deep-link target question). */
  notice?: ReactNode
  /** 這份考卷所屬科目（由考卷目錄推得），用來連到同科目的章節練習與學習指引。 */
  subjectId?: string | null
}

function formatClock(seconds: number) {
  const minutes = Math.floor(seconds / 60)
  return `${minutes}:${String(seconds % 60).padStart(2, '0')}`
}

export default function ExamIntro({ examData, onStart, savedAttempt, onResume, notice, subjectId }: ExamIntroProps) {
  const canResume = Boolean(savedAttempt && onResume)
  const answeredCount = savedAttempt ? Object.keys(savedAttempt.answers).length : 0
  const [confirmRestart, setConfirmRestart] = useState(false)
  // 同科目的複習入口：科目與章節一律從 resourceLevels（toc_manifest 衍生）查，不硬編。
  const subject = subjectId
    ? resourceLevels.flatMap((level) => level.subjects).find((item) => item.id === subjectId)
    : undefined
  const studyLinks = subject
    ? [
        subject.practiceStatus === 'available' && subject.practiceTo
          ? { to: subject.practiceTo, label: navLabel('practice'), detail: `${subject.shortLabel}・${subject.practiceDetail}` }
          : undefined,
        subject.guideTo
          ? { to: subject.guideTo, label: navLabel('guide'), detail: `${subject.shortLabel}・依章節閱讀重點與原文` }
          : undefined,
        subject.overviewTo
          ? { to: subject.overviewTo, label: navLabel('subject'), detail: `${subject.shortLabel}・所有章節與練習入口` }
          : undefined,
      ].filter((item): item is { to: string; label: string; detail: string } => Boolean(item))
    : []
  const pointsPerQuestion = examData.total > 0 ? Math.round((100 / examData.total) * 100) / 100 : undefined

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
      <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,20rem)] md:items-start">
        <section className="surface p-4 sm:p-5" aria-labelledby="exam-intro-rules-heading">
          <h2 id="exam-intro-rules-heading" className="section-title mb-3">作答須知</h2>
          <ul className="list-disc space-y-2 pl-5 text-body text-app-text marker:text-text-light">
            <li>
              共 {examData.total} 題單選題，作答時間 {examData.time_limit}
              {pointsPerQuestion ? `，滿分 100 分（每題 ${pointsPerQuestion} 分）` : ''}，{examData.passing_score} 分及格。
            </li>
            <li>按「開始考試」後開始倒數計時，時間到會自動繳卷。</li>
            <li>可隨時用題號盤切換題目；桌機可用鍵盤 1–4 選答、←→ 切換上下題。</li>
            <li>中途可以按「離開」保存作答，離開期間不計時，回到這一頁即可續答。</li>
            <li>繳卷前會提醒未作答題數；繳卷後可逐題查看答案與解析，並連到學習指引對應段落。</li>
          </ul>
        </section>
        {studyLinks.length > 0 && (
          <section className="surface p-4 sm:p-5" aria-labelledby="exam-intro-study-heading">
            <h2 id="exam-intro-study-heading" className="section-title mb-1">考前複習</h2>
            <p className="mb-3 text-meta text-text-light">還沒準備好？先從同一科目的教材與練習開始。</p>
            <ul className="space-y-2">
              {studyLinks.map((item) => (
                <li key={item.to}>
                  <Link
                    to={item.to}
                    className="flex min-h-11 flex-col justify-center rounded-lg border border-border px-3 py-2 transition-colors hover:border-accent hover:bg-accent-soft"
                  >
                    <span className="text-ui font-semibold text-accent">{item.label}</span>
                    <span className="text-meta text-text-light">{item.detail}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
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
