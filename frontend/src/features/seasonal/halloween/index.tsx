import { useEffect, useRef, useState } from 'react'
import type { SeasonalCompanionProps, SeasonalDecor, SeasonalPassBannerProps } from '../types'
import { FxLayer, prefersReducedMotion } from '../fx'
import { BatArt, CandyArt, GhostArt, HW_ORANGE, HW_ORANGE_SOFT, HW_PURPLE_SOFT, PumpkinArt } from './art'

/** 首頁主視覺角落：一顆南瓜＋兩隻蝙蝠，低透明度、排在內容後面。 */
function HeroDecor() {
  return (
    <div className="hw-hero-decor" aria-hidden="true">
      <PumpkinArt className="hw-hero-pumpkin" />
      <PumpkinArt className="hw-hero-pumpkin-small" />
      <BatArt className="hw-hero-bat hw-hero-bat-1" />
      <BatArt className="hw-hero-bat hw-hero-bat-2" />
    </div>
  )
}

function HeaderMark() {
  return <PumpkinArt className="hw-header-mark" />
}

// ── 隱藏小幽靈 ───────────────────────────────────────────────────────────

const CHEERS = [
  '今天多讀一節，考場上就少一分緊張。',
  '錯題是最好的老師，回頭看一眼就賺到了。',
  '慢慢來，比較快。',
  '讀累了就休息一下，休息也是備考的一部分。',
  '每做一題，實力就多一點。',
  '不懂的地方先標起來，明天再戰。',
  '你已經比昨天的自己更接近及格線了。',
  '先求理解，再求速度。',
  '喝口水，再做一題就好。',
  '穩穩地讀，考試那天會感謝現在的你。',
  '別怕，我也是一路飄過來的。',
]

const CHEER_MS = 4500

function Companion({ className = '' }: SeasonalCompanionProps) {
  const [message, setMessage] = useState<string | null>(null)
  const lastIndex = useRef(-1)
  const timer = useRef<number | undefined>(undefined)

  useEffect(() => () => window.clearTimeout(timer.current), [])

  const speak = () => {
    let index = Math.floor(Math.random() * CHEERS.length)
    if (index === lastIndex.current) index = (index + 1) % CHEERS.length
    lastIndex.current = index
    setMessage(CHEERS[index])
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => setMessage(null), CHEER_MS)
  }

  return (
    <div className={`hw-ghost ${className}`}>
      <button type="button" className="hw-ghost-button" aria-label="小幽靈" onClick={speak}>
        <GhostArt className="hw-ghost-art" />
      </button>
      {/* 一直存在的 live region：讀屏會念出新的打氣話；沒有訊息時不佔版面也看不到。 */}
      <p role="status" className={message ? 'hw-ghost-bubble' : 'sr-only'}>
        {message ?? ''}
      </p>
    </div>
  )
}

// ── 答對的小慶祝 ─────────────────────────────────────────────────────────

let celebrationCount = 0

function Celebration() {
  const [ghost] = useState(() => celebrationCount++ % 2 === 1)
  return (
    <div className="hw-pop">
      {ghost ? <GhostArt className="hw-pop-art" /> : <PumpkinArt face className="hw-pop-art" />}
      <span className="hw-pop-spark hw-pop-spark-1" />
      <span className="hw-pop-spark hw-pop-spark-2" />
      <span className="hw-pop-spark hw-pop-spark-3" />
    </div>
  )
}

// ── 及格彩蛋：祝賀橫幅＋糖果 ─────────────────────────────────────────────

const CANDY_COLORS = [HW_ORANGE, HW_PURPLE_SOFT, '#f59e0b', HW_ORANGE_SOFT, '#a855f7']
const CANDY_MS = 2000

interface Candy {
  left: number
  delay: number
  duration: number
  spin: number
  drift: number
  size: number
  color: string
}

function makeCandies(count: number): Candy[] {
  return Array.from({ length: count }, (_, i) => ({
    left: 3 + Math.random() * 94,
    delay: Math.random() * 0.35,
    duration: 1.15 + Math.random() * 0.4,
    spin: (Math.random() < 0.5 ? -1 : 1) * (240 + Math.random() * 360),
    drift: (Math.random() - 0.5) * 80,
    size: 20 + Math.random() * 10,
    color: CANDY_COLORS[i % CANDY_COLORS.length],
  }))
}

function PassBanner({ onDismiss }: SeasonalPassBannerProps) {
  const [candies] = useState(() => (prefersReducedMotion() ? [] : makeCandies(18)))
  const [raining, setRaining] = useState(candies.length > 0)

  useEffect(() => {
    if (!raining) return
    const timer = window.setTimeout(() => setRaining(false), CANDY_MS)
    return () => window.clearTimeout(timer)
  }, [raining])

  return (
    <>
      <div className="hw-pass-banner" role="status">
        <PumpkinArt face className="hw-pass-pumpkin" />
        <div className="min-w-0 flex-1">
          <p className="hw-pass-title">不給糖就搗蛋！你及格了</p>
          <p className="hw-pass-text">這把糖果送給一路認真準備的你，下一份試題也一起拿下吧。</p>
        </div>
        <button type="button" className="hw-pass-close" aria-label="關閉祝賀訊息" onClick={onDismiss}>
          <span aria-hidden="true">×</span>
        </button>
      </div>
      {raining && (
        <FxLayer>
          {candies.map((candy, i) => (
            <span
              key={i}
              className="hw-candy"
              style={{
                left: `${candy.left}%`,
                width: candy.size,
                animationDelay: `${candy.delay}s`,
                animationDuration: `${candy.duration}s`,
                ['--hw-spin' as string]: `${candy.spin}deg`,
                ['--hw-drift' as string]: `${candy.drift}px`,
              }}
            >
              <CandyArt color={candy.color} />
            </span>
          ))}
        </FxLayer>
      )}
    </>
  )
}

// ── 首頁第一次往下捲：蝙蝠飛過一次 ──────────────────────────────────────

/** 每次載入最多一次（離開首頁再回來也不重播）。 */
let batFlown = false
const BAT_MS = 2000

function ScrollFlyer() {
  const [flying, setFlying] = useState(false)

  useEffect(() => {
    if (batFlown || prefersReducedMotion()) return
    const scroller = document.getElementById('main-content')
    if (!scroller) return
    const onScroll = () => {
      if (batFlown || scroller.scrollTop < 24) return
      batFlown = true
      scroller.removeEventListener('scroll', onScroll)
      setFlying(true)
    }
    scroller.addEventListener('scroll', onScroll, { passive: true })
    return () => scroller.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => {
    if (!flying) return
    const timer = window.setTimeout(() => setFlying(false), BAT_MS)
    return () => window.clearTimeout(timer)
  }, [flying])

  if (!flying) return null
  return (
    <FxLayer>
      <div className="hw-flyby">
        <BatArt className="hw-flyby-bat" />
      </div>
    </FxLayer>
  )
}

export const halloweenDecor: SeasonalDecor = {
  HeroDecor,
  HeaderMark,
  Companion,
  PassBanner,
  ScrollFlyer,
  Celebration,
}
