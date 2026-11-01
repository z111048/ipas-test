import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { Dialog, MobileActionBar, PageHeader, StatePanel } from '../components/ui'
import { navLabel } from '../constants/navLabels'
import { loadExamData } from '../data/examLoaders'
import { useExamTimer } from '../hooks/useExamTimer'
import { useExamStore } from '../store/examStore'
import type { ExamData } from '../types'
import ExamIntro from '../components/exam/ExamIntro'
import ExamQuestion from '../components/exam/ExamQuestion'
import ExamResults from '../components/exam/ExamResults'
import ExamTimer from '../components/exam/ExamTimer'
import QuestionPalette from '../components/exam/QuestionPalette'
import { examSubjectId } from '../components/exam/examResultLinks'
import { useMediaQuery, WIDE_LAYOUT_QUERY } from '../hooks/useMediaQuery'
import { useFocusMode } from '../hooks/useFocusMode'
import { scrollMainToTop } from '../utils/scrollMain'

const SIDE_PALETTE_ID = 'exam-side-palette'

function isTypingTarget(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) return false
  const tag = target.tagName
  if (tag === 'TEXTAREA') return true
  if (tag === 'INPUT') {
    const type = (target as HTMLInputElement).type
    return type !== 'radio' && type !== 'checkbox'
  }
  return target.isContentEditable
}

function formatRemaining(seconds: number) {
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  return `${minutes} 分 ${String(remainingSeconds).padStart(2, '0')} 秒`
}

export default function ExamPage() {
  const { examKey } = useParams<{ examKey: string }>()
  const [examData, setExamData] = useState<ExamData | undefined>()
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [activeIndex, setActiveIndex] = useState(0)
  const [showPalette, setShowPalette] = useState(false)
  const [showSubmitDialog, setShowSubmitDialog] = useState(false)
  const questionRefs = useRef<Array<HTMLElement | null>>([])
  const confirmSubmitRef = useRef<HTMLButtonElement>(null)
  const paletteButtonRef = useRef<HTMLButtonElement>(null)
  const sheetActiveRef = useRef<HTMLButtonElement>(null)
  /** >= 1024px：題號盤是常駐右側欄；以下是底部抽屜。 */
  const isWide = useMediaQuery(WIDE_LAYOUT_QUERY)
  const [searchParams] = useSearchParams()
  const targetQuestionId = searchParams.get('q')

  const phase = useExamStore((s) => s.phase)
  const storeExamKey = useExamStore((s) => s.examKey)
  const setExam = useExamStore((s) => s.setExam)
  const startExam = useExamStore((s) => s.startExam)
  const resumeExam = useExamStore((s) => s.resumeExam)
  const savedAttempt = useExamStore((s) => s.savedAttempt)
  const setCurrentIndex = useExamStore((s) => s.setCurrentIndex)
  const submitExam = useExamStore((s) => s.submitExam)
  const suspendExam = useExamStore((s) => s.suspendExam)
  const resetExam = useExamStore((s) => s.resetExam)
  const selectAnswer = useExamStore((s) => s.selectAnswer)
  const userAnswers = useExamStore((s) => s.userAnswers)
  const currentExamData = useExamStore((s) => s.examData)
  const secondsRemaining = useExamStore((s) => s.secondsRemaining)
  /** 續答時要回到的題號；等作答頁渲染、scroll-spy 歸零之後才捲過去。 */
  const pendingResumeIndexRef = useRef<number | null>(null)

  useExamTimer(phase === 'active')
  // 作答中進入專注模式：手機隱藏站台 Header、桌機收合側欄；交卷、離開、結果頁即還原。
  useFocusMode(phase === 'active' && Boolean(examKey) && storeExamKey === examKey)

  // 離開考試頁（站內導覽、換路由）時把作答存檔並退回 intro，回來可選擇續答。
  useEffect(() => () => useExamStore.getState().suspendExam(), [])

  useEffect(() => {
    if (phase === 'active') setCurrentIndex(activeIndex)
  }, [phase, activeIndex, setCurrentIndex])

  const hasAnswers = Object.keys(userAnswers).length > 0
  useEffect(() => {
    if (phase !== 'active' || !hasAnswers) return
    const handler = (event: BeforeUnloadEvent) => {
      event.preventDefault()
      // 舊版瀏覽器要設 returnValue 才會跳出確認
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [phase, hasAnswers])

  /**
   * 移動到指定題目。**程式觸發的捲動一律用 instant，這是正確性需求不是偏好。**
   *
   * 這一頁把所有題目一次渲染，用下面那個 IntersectionObserver 維護 activeIndex
   * （哪一題是「當前題」），而鍵盤 1-4 是對 activeIndex 那一題作答。
   * 一旦用平滑捲動，動畫途中 observer 會把 activeIndex 改成畫面上當下最顯眼的題，
   * 於是「切題後立刻按數字鍵」會答到動畫經過的那一題——在考試裡就是靜默答錯題。
   *
   * 試過用「捲動期間鎖住 scroll-spy」來保留平滑動畫，是錯的，實測有三個破口：
   * (a) 這一頁捲動的是 App.tsx 的 &lt;main overflow-y-scroll&gt; 而不是 document，
   *     而 scrollend 從元素發出時**不冒泡**，掛在 document 上的解鎖永遠不會執行；
   * (b) Chrome 的平滑捲動時長隨距離增加（實測上限約 1534ms），任何固定 timeout
   *     都會在長距離跳題（題號盤、jumpToFirstUnanswered、深連結）時提早過期，
   *     原本的錯答照樣復現，只是時間窗口換了位置；
   * (c) 鎖期間使用者自己捲走，activeIndex 不跟隨，會答到畫面外看不見的題——
   *     這比原本的 bug 更糟，因為螢幕與作答不再一致。
   *
   * instant 沒有中間狀態，observer 拿到的第一批 entry 就是最終位置，
   * 正確性是 by construction 而不是跟時序賽跑。代價是失去平滑觀感——
   * prefers-reduced-motion 的使用者本來走的就是這條路徑。
   */
  const focusQuestion = useCallback((index: number) => {
    setActiveIndex(index)
    questionRefs.current[index]?.scrollIntoView({ behavior: 'instant', block: 'center' })
  }, [])

  const goTo = (idx: number) => {
    const total = currentExamData?.questions.length ?? 0
    if (total === 0) return
    focusQuestion(Math.max(0, Math.min(idx, total - 1)))
  }

  useEffect(() => {
    // 繳卷對話框或手機題號盤抽屜開著時不接受作答快捷鍵（避免在看不到題目時改到答案）
    if (phase !== 'active' || !currentExamData || showSubmitDialog || (showPalette && !isWide)) return
    const handler = (event: KeyboardEvent) => {
      if (isTypingTarget(event.target)) return
      if (['1', '2', '3', '4'].includes(event.key)) {
        event.preventDefault()
        const optKey = (['A', 'B', 'C', 'D'] as const)[Number(event.key) - 1]
        const activeQuestionId = currentExamData.questions[activeIndex]?.id
        if (activeQuestionId) selectAnswer(activeQuestionId, optKey)
      } else if (event.key === 'ArrowRight') {
        event.preventDefault()
        goTo(activeIndex + 1)
      } else if (event.key === 'ArrowLeft') {
        event.preventDefault()
        goTo(activeIndex - 1)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [phase, currentExamData, activeIndex, selectAnswer, showSubmitDialog, showPalette, isWide])

  useEffect(() => {
    if (phase !== 'active' || !currentExamData) return
    questionRefs.current = []
    setActiveIndex(0)
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((entry) => entry.isIntersecting)
        if (visible.length === 0) return
        const closest = visible.reduce((a, b) => (a.intersectionRatio > b.intersectionRatio ? a : b))
        const idx = Number((closest.target as HTMLElement).dataset.qIndex)
        if (!Number.isNaN(idx)) setActiveIndex(idx)
      },
      { threshold: [0.3, 0.6, 0.9], rootMargin: '-120px 0px -35% 0px' },
    )
    const id = window.setTimeout(() => {
      questionRefs.current.forEach((el) => el && observer.observe(el))
    }, 0)
    return () => {
      window.clearTimeout(id)
      observer.disconnect()
    }
  }, [phase, currentExamData])

  useEffect(() => {
    let active = true
    setExamData(undefined)
    setLoadError(null)
    if (!examKey) return

    setLoading(true)
    loadExamData(examKey)
      .then((loadedData) => {
        if (active) setExamData(loadedData)
      })
      .catch((error) => {
        if (active) setLoadError(error instanceof Error ? error.message : String(error))
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [examKey])

  useEffect(() => {
    if (examData && examKey && (examKey !== storeExamKey || currentExamData !== examData)) {
      setExam(examData, examKey)
    }
  }, [examKey, examData, storeExamKey, currentExamData, setExam])

  useEffect(() => {
    if (phase === 'active' && (targetQuestionId || pendingResumeIndexRef.current !== null)) return
    scrollMainToTop()
  }, [examKey, phase, targetQuestionId])

  useEffect(() => {
    if (phase !== 'active' || !currentExamData) return
    const index = pendingResumeIndexRef.current
    if (index === null) return
    pendingResumeIndexRef.current = null
    // 與深連結相同：等 scroll-spy 的 observer 掛好、把 activeIndex 歸零之後再定位
    const timer = window.setTimeout(() => focusQuestion(index), 120)
    return () => window.clearTimeout(timer)
  }, [phase, currentExamData, focusQuestion])

  useEffect(() => {
    if (!targetQuestionId || phase !== 'active' || !currentExamData) return
    const index = currentExamData.questions.findIndex((q) => q.id === targetQuestionId)
    if (index < 0) return
    const timer = window.setTimeout(() => focusQuestion(index), 120)
    return () => window.clearTimeout(timer)
  }, [targetQuestionId, phase, currentExamData, focusQuestion])

  useEffect(() => {
    if (phase !== 'active') {
      setShowPalette(false)
      setShowSubmitDialog(false)
    }
  }, [phase])

  if (loading) {
    return (
      <div className="page-shell">
        <StatePanel tone="loading">考卷載入中...</StatePanel>
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="page-shell">
        <PageHeader variant="plain" className="mb-5" eyebrow={navLabel('exam')} title="考卷載入失敗" />
        <StatePanel tone="error">{loadError}</StatePanel>
      </div>
    )
  }

  if (!examData) {
    return (
      <div className="page-shell">
        <PageHeader
          variant="plain"
          eyebrow={navLabel('exam')}
          title="找不到考試"
          description="這份考卷不存在，或內容已經移動。"
          actions={<Link to="/" className="btn-primary">回到首頁</Link>}
        />
      </div>
    )
  }

  if (examKey !== storeExamKey || currentExamData !== examData) {
    return (
      <div className="page-shell">
        <StatePanel tone="loading">考卷準備中...</StatePanel>
      </div>
    )
  }

  const targetIndex = targetQuestionId
    ? examData.questions.findIndex((q) => q.id === targetQuestionId)
    : -1

  if (phase === 'intro') {
    return (
      <ExamIntro
          examData={examData}
          subjectId={examKey ? examSubjectId(examKey) : null}
          notice={
            targetIndex >= 0 ? (
              <StatePanel className="mb-4">
                開始作答後會自動跳到<strong>第 {targetIndex + 1} 題</strong>
                （你從概念索引點進來的那一題）。
              </StatePanel>
            ) : undefined
          }
          onStart={() => {
            pendingResumeIndexRef.current = null
            startExam()
          }}
          savedAttempt={savedAttempt}
          onResume={() => {
            if (!savedAttempt) return
            pendingResumeIndexRef.current = targetIndex >= 0 ? null : savedAttempt.currentIndex
            resumeExam()
          }}
        />
    )
  }

  if (phase === 'results') {
    return <ExamResults onRetry={resetExam} />
  }

  const answeredCount = Object.keys(userAnswers).length
  const unansweredIndices = currentExamData.questions
    .map((_, index) => index)
    .filter((index) => !userAnswers[currentExamData.questions[index].id])
  const unansweredCount = unansweredIndices.length
  const activeQuestionId = currentExamData.questions[activeIndex]?.id
  const activeAnswered = Boolean(activeQuestionId && userAnswers[activeQuestionId])
  const currentAnswer = activeQuestionId ? userAnswers[activeQuestionId] : undefined
  const paletteItems = currentExamData.questions.map((question) => ({
    id: question.id,
    status: userAnswers[question.id] ? ('answered' as const) : ('unanswered' as const),
  }))
  const unansweredText = unansweredCount === 0 ? '全部已答' : `未答 ${unansweredCount} 題`

  const jumpToFirstUnanswered = () => {
    const nextIndex = unansweredIndices[0]
    if (typeof nextIndex !== 'number') return
    setShowPalette(false)
    setShowSubmitDialog(false)
    // 等題號盤抽屜與對話框卸載、版面重排完再捲。
    // 在同一個 handler 裡直接捲，scrollIntoView 算的是舊版面，
    // 捲完位置可能偏掉——使用者看到的與 activeIndex 就對不起來了。
    requestAnimationFrame(() => goTo(nextIndex))
  }

  /** 題號盤點題號：手機抽屜先關閉再捲（理由同上）；寬版側欄常駐，直接捲。 */
  const selectFromPalette = (index: number) => {
    if (showPalette && !isWide) {
      setShowPalette(false)
      requestAnimationFrame(() => goTo(index))
      return
    }
    goTo(index)
  }

  /** 只在窄版出現：寬版題號盤是常駐側欄，計時列不放重複的按鈕。 */
  const handlePaletteButton = () => setShowPalette((open) => !open)

  const handleSubmitIntent = () => {
    setShowPalette(false)
    setShowSubmitDialog(true)
  }

  const handleConfirmSubmit = () => {
    setShowSubmitDialog(false)
    submitExam()
  }

  /** 離開：保存目前作答與剩餘時間並回到考卷說明頁，可隨時繼續（離開期間不計時）。 */
  const handleLeave = () => {
    setShowPalette(false)
    setShowSubmitDialog(false)
    suspendExam()
  }

  const paletteSummary = (
    <>
      目前在第 {activeIndex + 1} 題 · {unansweredText}
    </>
  )

  return (
    <div className="page-shell pb-28 sm:pb-6">
      <div className="mx-auto w-full max-w-[46rem] lg:max-w-[63rem]">
        <PageHeader
          variant="plain"
          className="mb-1 pb-2"
          eyebrow={navLabel('exam')}
          title={currentExamData.exam}
        />
        {/*
          作答計時列：手機專注模式下站台 Header 隱藏、main 從畫面頂端開始，
          這一列以 sticky 貼在 main 最上緣（-top-4／md:-top-6 抵銷 main 的 py-4／md:py-6，否則上方會留一條露出題目的縫），固定單行（離開 · 時間 · 已答 · 題號盤 · 繳卷；寬版題號盤是常駐側欄，這裡不放按鈕）。
        */}
        <div className="sticky -top-4 md:-top-6 z-20 mb-3">
          <div className="rounded-xl border border-primary-light bg-primary px-2 py-1.5 text-on-dark shadow-lg sm:p-3">
            <div className="flex items-center gap-2 sm:gap-3">
              <button
                type="button"
                className="btn-hero-ghost shrink-0 border-transparent bg-transparent px-2 text-ui font-medium text-on-dark-muted underline-offset-4 hover:border-transparent hover:bg-transparent hover:text-on-dark hover:underline sm:px-2.5"
                onClick={handleLeave}
                aria-label="離開（保存作答進度）"
                title="保存作答進度並離開，之後可以繼續作答"
              >
                <span aria-hidden="true" className="mr-0.5">‹</span>離開
              </button>
              <ExamTimer compact />
              <div className="min-w-0 flex-1 text-center">
                <div className="whitespace-nowrap text-meta font-semibold tabular-nums sm:text-ui">
                  已答 {answeredCount}/{currentExamData.total}
                </div>
                <div className="hidden text-caption text-on-dark-muted sm:block">{unansweredText}</div>
              </div>
              <div className="flex shrink-0 items-center gap-1.5">
                {!isWide && (
                  <button
                    ref={paletteButtonRef}
                    type="button"
                    className="btn-hero-ghost px-2.5 text-ui sm:px-3"
                    onClick={handlePaletteButton}
                    aria-haspopup="dialog"
                    aria-expanded={showPalette}
                  >
                    題號盤
                  </button>
                )}
                <button
                  type="button"
                  className="btn-hero px-2.5 text-ui shadow-none sm:px-3"
                  onClick={handleSubmitIntent}
                >
                  繳卷
                </button>
              </div>
            </div>
          </div>
        </div>

        <div className="lg:grid lg:grid-cols-[minmax(0,46rem)_16rem] lg:items-start lg:justify-between lg:gap-6">
          <div className="min-w-0">
            <div className="hidden sm:block">
              <StatePanel className="mb-4">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <span>鍵盤：1–4 選答，←→ 切換上下題。</span>
                  {unansweredCount > 0 && (
                    <button type="button" className="btn-outline btn-sm" onClick={jumpToFirstUnanswered}>
                      跳到未答題
                    </button>
                  )}
                </div>
              </StatePanel>
            </div>

            {currentExamData.questions.map((q, i) => (
              <ExamQuestion
                key={q.id}
                question={q}
                index={i}
                isActive={i === activeIndex}
                registerRef={(el) => {
                  questionRefs.current[i] = el
                }}
              />
            ))}

            <div className="hidden py-4 text-center sm:block">
              <button
                type="button"
                className="btn-primary px-8 py-3 text-reading"
                onClick={handleSubmitIntent}
              >
                繳卷交答案
              </button>
            </div>
          </div>

          {isWide && (
            <aside
              id={SIDE_PALETTE_ID}
              aria-labelledby="exam-side-palette-heading"
              className="surface sticky top-[5.5rem] max-h-[calc(100dvh-3.5rem-7.5rem)] overflow-y-auto p-4"
            >
              <QuestionPalette
                headingId="exam-side-palette-heading"
                items={paletteItems}
                activeIndex={activeIndex}
                onSelect={selectFromPalette}
                columnsClassName="grid-cols-5"
                legend={['answered', 'unanswered']}
                summary={paletteSummary}
                actions={
                  unansweredCount > 0 ? (
                    <button type="button" className="btn-outline btn-sm" onClick={jumpToFirstUnanswered}>
                      跳到未答題
                    </button>
                  ) : undefined
                }
              />
            </aside>
          )}
        </div>
      </div>

      <MobileActionBar className="sm:hidden">
        <button
          type="button"
          className="btn-outline flex-1"
          onClick={() => goTo(activeIndex - 1)}
          disabled={activeIndex === 0}
        >
          ← 上一題
        </button>
        <div className="min-w-[92px] shrink-0 text-center text-caption text-text-light">
          <div className="font-semibold text-primary">第 {activeIndex + 1} 題</div>
          <div>
            {currentAnswer ? `已選 ${currentAnswer}` : '未作答'} · {answeredCount}/{currentExamData.questions.length}
          </div>
        </div>
        <button
          type="button"
          className="btn-outline flex-1"
          onClick={() => goTo(activeIndex + 1)}
          disabled={activeIndex === currentExamData.questions.length - 1}
        >
          下一題 →
        </button>
      </MobileActionBar>

      {/* 窄版題號盤：底部抽屜。點題號會關閉抽屜並跳到該題。 */}
      <Dialog
        open={showPalette && !isWide}
        title="題號盤"
        onClose={() => setShowPalette(false)}
        initialFocusRef={sheetActiveRef}
        restoreFocusRef={paletteButtonRef}
      >
        <div className="p-4 sm:p-5">
          <QuestionPalette
            items={paletteItems}
            activeIndex={activeIndex}
            onSelect={selectFromPalette}
            activeButtonRef={sheetActiveRef}
            columnsClassName="grid-cols-6 sm:grid-cols-10"
            legend={['answered', 'unanswered']}
            summary={paletteSummary}
            actions={
              <>
                {unansweredCount > 0 && (
                  <button type="button" className="btn-outline btn-sm" onClick={jumpToFirstUnanswered}>
                    跳到未答題
                  </button>
                )}
                <button type="button" className="btn-ghost btn-sm" onClick={() => setShowPalette(false)}>
                  收起題號盤
                </button>
              </>
            }
          />
        </div>
      </Dialog>

      <Dialog
        open={showSubmitDialog}
        title="確認繳卷"
        onClose={() => setShowSubmitDialog(false)}
        initialFocusRef={confirmSubmitRef}
      >
        <div className="p-5 sm:p-6">
          <div className="mb-1 text-ui font-semibold text-primary">確認繳卷</div>
          <h2 className="text-xl font-bold text-app-text">要現在結束作答嗎？</h2>
          <div className="mt-4 space-y-3 text-body text-app-text">
            <p>剩餘時間：{formatRemaining(secondsRemaining)}</p>
            <p>{unansweredCount === 0 ? '所有題目都已作答。' : `還有 ${unansweredCount} 題未作答。`}</p>
            {activeAnswered ? (
              <p>目前停留在第 {activeIndex + 1} 題，已完成作答。</p>
            ) : (
              <p>目前停留在第 {activeIndex + 1} 題，尚未作答。</p>
            )}
          </div>

          <div className="mt-5 flex flex-wrap gap-2">
            {unansweredCount > 0 && (
              <button type="button" className="btn-outline" onClick={jumpToFirstUnanswered}>
                先看未答題
              </button>
            )}
            <button type="button" className="btn-outline" onClick={() => setShowSubmitDialog(false)}>
              返回作答
            </button>
            <button
              ref={confirmSubmitRef}
              type="button"
              className="btn-primary"
              onClick={handleConfirmSubmit}
            >
              確認繳卷
            </button>
          </div>
        </div>
      </Dialog>
    </div>
  )
}
