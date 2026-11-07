import type { SeasonalCompanionProps, SeasonalDecor, SeasonalPassBannerProps } from '../types'
import { CelebrationBurst, CheerCompanion, PassCelebration, ScrollFlyby } from '../common'
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

function Companion(props: SeasonalCompanionProps) {
  return <CheerCompanion {...props} label="小幽靈" cheers={CHEERS} Art={GhostArt} />
}

// ── 答對的小慶祝：南瓜臉與小幽靈輪流 ─────────────────────────────────────

function PumpkinFace(props: { className?: string }) {
  return <PumpkinArt face {...props} />
}

const CELEBRATION_ARTS = [PumpkinFace, GhostArt]

function Celebration() {
  return <CelebrationBurst arts={CELEBRATION_ARTS} />
}

// ── 及格彩蛋：祝賀橫幅＋糖果 ─────────────────────────────────────────────

const CANDY_COLORS = [HW_ORANGE, HW_PURPLE_SOFT, '#f59e0b', HW_ORANGE_SOFT, '#a855f7']

function PassBanner({ onDismiss }: SeasonalPassBannerProps) {
  return (
    <PassCelebration
      onDismiss={onDismiss}
      icon={<PumpkinArt face className="seasonal-pass-icon" />}
      title="不給糖就搗蛋！你及格了"
      text="這把糖果送給一路認真準備的你，下一份試題也一起拿下吧。"
      falling={{ count: 18, variants: CANDY_COLORS.length }}
      renderPiece={(variant) => <CandyArt color={CANDY_COLORS[variant]} />}
    />
  )
}

// ── 首頁第一次往下捲：蝙蝠飛過一次 ──────────────────────────────────────

function ScrollFlyer() {
  return (
    <ScrollFlyby id="halloween">
      <BatArt className="hw-flyby-bat" />
    </ScrollFlyby>
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
