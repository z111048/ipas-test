/**
 * 各主題共用的裝飾骨架：隱藏角色＋打氣泡泡、答對小慶祝、及格橫幅＋散落特效、首頁捲動飛過。
 * 主題只提供剪影、文案與配色（index.css 的 `.theme-<id>` 底下設 --seasonal-* 變數）；
 * 結構樣式寫在 index.css 的 `.seasonal-*`，只有主題開啟時這些元素才會進 DOM。
 */
import { useEffect, useRef, useState, type ComponentType, type CSSProperties, type ReactNode } from 'react'
import { FxLayer, prefersReducedMotion } from './fx'
import type { SeasonalCompanionProps, SeasonalPassBannerProps } from './types'

interface ArtComponentProps {
  className?: string
  style?: CSSProperties
}

// ── 隱藏角色：點了冒出一句打氣話 ─────────────────────────────────────────

const CHEER_MS = 4500

export function CheerCompanion({
  className = '',
  label,
  cheers,
  Art,
}: SeasonalCompanionProps & {
  /** 按鈕的 aria-label，例如「小幽靈」「小雪人」。 */
  label: string
  cheers: readonly string[]
  Art: ComponentType<ArtComponentProps>
}) {
  const [message, setMessage] = useState<string | null>(null)
  const lastIndex = useRef(-1)
  const timer = useRef<number | undefined>(undefined)

  useEffect(() => () => window.clearTimeout(timer.current), [])

  const speak = () => {
    let index = Math.floor(Math.random() * cheers.length)
    if (index === lastIndex.current) index = (index + 1) % cheers.length
    lastIndex.current = index
    setMessage(cheers[index])
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => setMessage(null), CHEER_MS)
  }

  return (
    <div className={`seasonal-companion ${className}`}>
      <button type="button" className="seasonal-companion-button" aria-label={label} onClick={speak}>
        <Art className="seasonal-companion-art" />
      </button>
      {/* 一直存在的 live region：讀屏會念出新的打氣話；沒有訊息時不佔版面也看不到。 */}
      <p role="status" className={message ? 'seasonal-bubble' : 'sr-only'}>
        {message ?? ''}
      </p>
    </div>
  )
}

// ── 答對的小慶祝（約 0.8 秒） ───────────────────────────────────────────

let celebrationCount = 0

/** 每次答對輪流換一個剪影；外加三顆小火花（顏色由主題的 --seasonal-spark-* 決定）。 */
export function CelebrationBurst({ arts }: { arts: readonly ComponentType<ArtComponentProps>[] }) {
  const [Art] = useState(() => arts[celebrationCount++ % arts.length])
  return (
    <div className="seasonal-burst">
      <Art className="seasonal-burst-art" />
      <span className="seasonal-spark seasonal-spark-1" />
      <span className="seasonal-spark seasonal-spark-2" />
      <span className="seasonal-spark seasonal-spark-3" />
    </div>
  )
}

// ── 及格祝賀橫幅＋約 2 秒的散落特效 ─────────────────────────────────────

const FALL_MS = 2000

export interface FallingPiece {
  left: number
  delay: number
  duration: number
  spin: number
  drift: number
  size: number
  /** 第幾種樣式（交給主題的 renderPiece 決定畫什麼）。 */
  variant: number
}

export interface FallingOptions {
  count: number
  variants: number
  /** 落下時間（秒）：base + random * spread。 */
  duration?: [number, number]
  /** 旋轉角度（度）：base + random * spread，方向隨機。 */
  spin?: [number, number]
  /** 尺寸（px）：base + random * spread。 */
  size?: [number, number]
  /** 左右飄移最大幅度（px，總寬）。 */
  drift?: number
}

export function makeFallingPieces({
  count,
  variants,
  duration = [1.15, 0.4],
  spin = [240, 360],
  size = [20, 10],
  drift = 80,
}: FallingOptions): FallingPiece[] {
  return Array.from({ length: count }, (_, i) => ({
    left: 3 + Math.random() * 94,
    delay: Math.random() * 0.35,
    duration: duration[0] + Math.random() * duration[1],
    spin: (Math.random() < 0.5 ? -1 : 1) * (spin[0] + Math.random() * spin[1]),
    drift: (Math.random() - 0.5) * drift,
    size: size[0] + Math.random() * size[1],
    variant: i % variants,
  }))
}

export function PassCelebration({
  onDismiss,
  icon,
  title,
  text,
  falling,
  renderPiece,
}: SeasonalPassBannerProps & {
  icon: ReactNode
  title: string
  text: string
  falling: FallingOptions
  renderPiece: (variant: number) => ReactNode
}) {
  const [pieces] = useState(() => (prefersReducedMotion() ? [] : makeFallingPieces(falling)))
  const [raining, setRaining] = useState(pieces.length > 0)

  useEffect(() => {
    if (!raining) return
    const timer = window.setTimeout(() => setRaining(false), FALL_MS)
    return () => window.clearTimeout(timer)
  }, [raining])

  return (
    <>
      <div className="seasonal-pass-banner" role="status">
        {icon}
        <div className="min-w-0 flex-1">
          <p className="seasonal-pass-title">{title}</p>
          <p className="seasonal-pass-text">{text}</p>
        </div>
        <button type="button" className="seasonal-pass-close" aria-label="關閉祝賀訊息" onClick={onDismiss}>
          <span aria-hidden="true">×</span>
        </button>
      </div>
      {raining && (
        <FxLayer>
          {pieces.map((piece, i) => (
            <span
              key={i}
              className="seasonal-fall"
              style={{
                left: `${piece.left}%`,
                width: piece.size,
                animationDelay: `${piece.delay}s`,
                animationDuration: `${piece.duration}s`,
                ['--seasonal-spin' as string]: `${piece.spin}deg`,
                ['--seasonal-drift' as string]: `${piece.drift}px`,
              }}
            >
              {renderPiece(piece.variant)}
            </span>
          ))}
        </FxLayer>
      )}
    </>
  )
}

// ── 首頁第一次往下捲：剪影從角落飛過一次 ────────────────────────────────

/** 每個主題每次載入最多一次（離開首頁再回來也不重播）。 */
const flown = new Set<string>()
const FLY_MS = 2000

export function ScrollFlyby({ id, children }: { id: string; children: ReactNode }) {
  const [flying, setFlying] = useState(false)

  useEffect(() => {
    if (flown.has(id) || prefersReducedMotion()) return
    const scroller = document.getElementById('main-content')
    if (!scroller) return
    const onScroll = () => {
      if (flown.has(id) || scroller.scrollTop < 24) return
      flown.add(id)
      scroller.removeEventListener('scroll', onScroll)
      setFlying(true)
    }
    scroller.addEventListener('scroll', onScroll, { passive: true })
    return () => scroller.removeEventListener('scroll', onScroll)
  }, [id])

  useEffect(() => {
    if (!flying) return
    const timer = window.setTimeout(() => setFlying(false), FLY_MS)
    return () => window.clearTimeout(timer)
  }, [flying])

  if (!flying) return null
  return (
    <FxLayer>
      <div className="seasonal-flyby">{children}</div>
    </FxLayer>
  )
}
