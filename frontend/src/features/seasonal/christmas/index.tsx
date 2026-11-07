import type { SeasonalCompanionProps, SeasonalDecor, SeasonalPassBannerProps } from '../types'
import { CelebrationBurst, CheerCompanion, PassCelebration, ScrollFlyby } from '../common'
import {
  GiftArt,
  PineSprigArt,
  RibbonArt,
  SantaHatArt,
  SleighArt,
  SnowflakeArt,
  SnowmanArt,
  XM_GOLD_SOFT,
  XM_ICE,
  XM_ICE_DEEP,
  XM_RED_SOFT,
} from './art'

/** 首頁主視覺角落：一枝掛著小鈴鐺的松枝＋幾片雪花，靜態、低透明度、排在內容後面。 */
function HeroDecor() {
  return (
    <div className="xm-hero-decor" aria-hidden="true">
      <PineSprigArt className="xm-hero-sprig" />
      <SnowflakeArt className="xm-hero-flake xm-hero-flake-1" />
      <SnowflakeArt className="xm-hero-flake xm-hero-flake-2" />
      <SnowflakeArt className="xm-hero-flake xm-hero-flake-3" />
    </div>
  )
}

function HeaderMark() {
  return <SantaHatArt className="xm-header-mark" />
}

// ── 隱藏小雪人 ───────────────────────────────────────────────────────────

const CHEERS = [
  '每讀完一節，就像替聖誕樹掛上一顆新裝飾。',
  '雪是一片一片下的，實力也是一題一題累積的。',
  '錯題就像還沒拆的禮物，打開來就有收穫。',
  '天冷了，喝杯熱可可，再做一題就好。',
  '今年送自己的禮物，就是考場上的那份從容。',
  '雪人也是一球一球滾出來的，慢慢來沒關係。',
  '休息一下也沒關係，暖暖身再出發。',
  '你的努力，聖誕老人都看在眼裡。',
  '不懂的地方先標起來，明天再拆開來看。',
  '今天多讀一點，明年考場上就多一分把握。',
  '我會在這裡陪你讀到雪停。',
]

function Companion(props: SeasonalCompanionProps) {
  return <CheerCompanion {...props} label="小雪人" cheers={CHEERS} Art={SnowmanArt} />
}

// ── 答對的小慶祝：小雪花與小禮物輪流 ─────────────────────────────────────

const CELEBRATION_ARTS = [SnowflakeArt, GiftArt]

function Celebration() {
  return <CelebrationBurst arts={CELEBRATION_ARTS} />
}

// ── 及格彩蛋：祝賀橫幅＋飄雪與彩帶 ───────────────────────────────────────

// 以冰藍雪花為主，夾幾片金色與淡紅彩帶；不用飽和的紅綠，免得和答對／答錯的狀態色混在一起。
const PIECES = [
  { kind: 'flake', color: XM_ICE_DEEP },
  { kind: 'ribbon', color: XM_GOLD_SOFT },
  { kind: 'flake', color: XM_ICE },
  { kind: 'flake', color: XM_ICE_DEEP },
  { kind: 'ribbon', color: XM_RED_SOFT },
  { kind: 'flake', color: XM_ICE },
] as const

function renderPiece(variant: number) {
  const piece = PIECES[variant]
  return piece.kind === 'flake' ? <SnowflakeArt color={piece.color} /> : <RibbonArt color={piece.color} />
}

function PassBanner({ onDismiss }: SeasonalPassBannerProps) {
  return (
    <PassCelebration
      onDismiss={onDismiss}
      icon={<GiftArt className="seasonal-pass-icon" />}
      title="聖誕快樂！你及格了"
      text="這份好成績，就是今年送給自己最棒的禮物。下一份試題也一起拿下吧。"
      // 雪花轉得慢一點、尺寸小一點；總長仍在 2 秒內落完。
      falling={{ count: 22, variants: PIECES.length, duration: [1.2, 0.4], spin: [90, 180], size: [11, 9], drift: 110 }}
      renderPiece={renderPiece}
    />
  )
}

// ── 首頁第一次往下捲：馴鹿雪橇飛過一次 ──────────────────────────────────

function ScrollFlyer() {
  return (
    <ScrollFlyby id="christmas">
      <SleighArt className="xm-flyby-sleigh" />
    </ScrollFlyby>
  )
}

export const christmasDecor: SeasonalDecor = {
  HeroDecor,
  HeaderMark,
  Companion,
  PassBanner,
  ScrollFlyer,
  Celebration,
}
