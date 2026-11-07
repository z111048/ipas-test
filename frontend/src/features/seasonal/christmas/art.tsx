/**
 * 聖誕節剪影（inline SVG，自己畫，不用外部圖檔或字型 icon）。
 * 一律 aria-hidden、focusable=false；紅綠只用在這些淡化的裝飾上，不碰主色與答題狀態色。
 */
import type { CSSProperties } from 'react'

export const XM_RED = '#b91c1c'
export const XM_RED_SOFT = '#fca5a5'
export const XM_PINE = '#15803d'
export const XM_PINE_DEEP = '#14532d'
export const XM_GOLD = '#ca8a04'
export const XM_GOLD_SOFT = '#fcd34d'
export const XM_ICE = '#93c5fd'
export const XM_ICE_DEEP = '#60a5fa'

interface ArtProps {
  className?: string
  style?: CSSProperties
}

const SNOWFLAKE_ARM = 'M16 16V3.5M16 8.5l-3.2-3.2M16 8.5l3.2-3.2M16 12.6l-2.2-2.2M16 12.6l2.2-2.2'

export function SnowflakeArt({ className, style, color = XM_ICE_DEEP }: ArtProps & { color?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} style={style} aria-hidden="true" focusable="false">
      <g fill="none" stroke={color} strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
        {[0, 60, 120, 180, 240, 300].map((deg) => (
          <path key={deg} d={SNOWFLAKE_ARM} transform={`rotate(${deg} 16 16)`} />
        ))}
      </g>
    </svg>
  )
}

/**
 * 松枝：沿枝條兩側密排針葉（兩層不同角度、交錯排列），越往枝尖越短。
 * 枝條是二次貝茲曲線；座標只在載入時算一次。
 */
type Point = [number, number]

function needles(a: Point, c: Point, b: Point, len: number) {
  const parts: string[] = []
  const at = (t: number): Point => [
    (1 - t) ** 2 * a[0] + 2 * (1 - t) * t * c[0] + t ** 2 * b[0],
    (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * c[1] + t ** 2 * b[1],
  ]
  const layers = [
    { angle: 38, scale: 1, offset: 0 },
    { angle: 64, scale: 0.72, offset: 0.5 },
  ]
  const step = 0.034
  for (const layer of layers) {
    for (let t = 0.06 + layer.offset * step; t <= 0.97; t += step) {
      const [px, py] = at(t)
      const [qx, qy] = at(t + 0.001)
      const norm = Math.hypot(qx - px, qy - py)
      const ux = (qx - px) / norm
      const uy = (qy - py) / norm
      const l = len * layer.scale * (1 - t * 0.5)
      for (const side of [-1, 1]) {
        const angle = (side * layer.angle * Math.PI) / 180
        const nx = ux * Math.cos(angle) - uy * Math.sin(angle)
        const ny = ux * Math.sin(angle) + uy * Math.cos(angle)
        parts.push(`M${px.toFixed(1)} ${py.toFixed(1)}l${(nx * l).toFixed(1)} ${(ny * l).toFixed(1)}`)
      }
    }
  }
  return parts.join('')
}

const STEM: [Point, Point, Point] = [[122, 4], [78, 18], [22, 46]]
const TWIG: [Point, Point, Point] = [[92, 14], [84, 32], [68, 52]]
const STEM_NEEDLES = needles(...STEM, 13)
const TWIG_NEEDLES = needles(...TWIG, 9)
const curve = ([a, c, b]: [Point, Point, Point]) => `M${a[0]} ${a[1]}Q${c[0]} ${c[1]} ${b[0]} ${b[1]}`

/** 松枝＋一串紅莓＋一顆垂掛的小鈴鐺（首頁主視覺角落用）。 */
export function PineSprigArt({ className, style }: ArtProps) {
  return (
    <svg viewBox="0 0 124 72" className={className} style={style} aria-hidden="true" focusable="false">
      <g fill="none" stroke={XM_PINE} strokeLinecap="round">
        <path d={STEM_NEEDLES} strokeWidth="1.3" />
        <path d={TWIG_NEEDLES} strokeWidth="1.15" />
        <path d={curve(STEM)} strokeWidth="2" stroke={XM_PINE_DEEP} />
        <path d={curve(TWIG)} strokeWidth="1.5" stroke={XM_PINE_DEEP} />
      </g>
      <circle cx="100" cy="17" r="3.8" fill={XM_RED} />
      <circle cx="106.5" cy="19.5" r="3.3" fill={XM_RED} />
      <circle cx="102" cy="23.5" r="3.1" fill={XM_RED} />
      <path d="M50 32v15.5" stroke={XM_GOLD} strokeWidth="1" />
      <g transform="translate(42 44.5) scale(0.5)">
        <path d="M16 6c-6 0-9 4.6-9 10.5V23l-3 4.5h24L25 23v-6.5C25 10.6 22 6 16 6z" fill={XM_GOLD} />
        <circle cx="16" cy="30.5" r="3" fill={XM_GOLD} />
      </g>
    </svg>
  )
}

export function SantaHatArt({ className, style }: ArtProps) {
  return (
    <svg viewBox="0 0 32 32" className={className} style={style} aria-hidden="true" focusable="false">
      <path d="M5.5 23.5C7 13 12.5 5.5 20.5 5.5c4 0 7 2.6 7.6 7.4-1.8-2.2-4.4-2.6-6-1-1.4 3.4-.8 7.6.9 11.6z" fill={XM_RED} />
      <circle cx="28" cy="14.5" r="3.4" fill="#ffffff" stroke="#d6d3d1" strokeWidth="1" />
      <rect x="3" y="21.5" width="23" height="7" rx="3.5" fill="#ffffff" stroke="#d6d3d1" strokeWidth="1" />
    </svg>
  )
}

export function SnowmanArt({ className, style }: ArtProps) {
  return (
    <svg viewBox="0 0 40 46" className={className} style={style} aria-hidden="true" focusable="false">
      <g fill="#ffffff" stroke="#475569" strokeOpacity="0.55" strokeWidth="1.8">
        <circle cx="20" cy="32.5" r="11" />
        <circle cx="20" cy="14.5" r="9" />
      </g>
      <circle cx="16.6" cy="13" r="1.5" fill="#1f2937" />
      <circle cx="23.4" cy="13" r="1.5" fill="#1f2937" />
      <path d="M20 15.2l6 1.6-6 1.4z" fill="#ea580c" />
      <ellipse cx="13.6" cy="17.6" rx="1.9" ry="1.1" fill={XM_RED_SOFT} opacity="0.85" />
      <ellipse cx="26.4" cy="17.6" rx="1.9" ry="1.1" fill={XM_RED_SOFT} opacity="0.85" />
      <path d="M11.5 22.6c5.4 2.2 11.6 2.2 17 0" fill="none" stroke={XM_RED} strokeWidth="3.4" strokeLinecap="round" />
      <path d="M24.6 24.2l1.4 6.4" stroke={XM_RED} strokeWidth="3" strokeLinecap="round" />
      <circle cx="20" cy="30" r="1.3" fill="#64748b" />
      <circle cx="20" cy="35.5" r="1.3" fill="#64748b" />
    </svg>
  )
}

export function GiftArt({ className, style }: ArtProps) {
  return (
    <svg viewBox="0 0 32 32" className={className} style={style} aria-hidden="true" focusable="false">
      <rect x="5" y="14" width="22" height="15" rx="2" fill={XM_RED} />
      <rect x="3.5" y="9.5" width="25" height="6" rx="1.6" fill={XM_RED} />
      <rect x="3.5" y="14.2" width="25" height="1.3" fill="#7f1d1d" opacity="0.35" />
      <rect x="14.4" y="9.5" width="3.2" height="19.5" fill={XM_GOLD_SOFT} />
      <path
        d="M16 9.5c-1.6-4.2-6.6-6-7.6-3.4-.8 2.2 3.4 3.6 7.6 3.4zM16 9.5c1.6-4.2 6.6-6 7.6-3.4.8 2.2-3.4 3.6-7.6 3.4z"
        fill="none"
        stroke={XM_GOLD}
        strokeWidth="2"
        strokeLinejoin="round"
      />
    </svg>
  )
}

/** 一小片微彎的彩帶紙片（及格時與雪花一起落下）。 */
export function RibbonArt({ color, className, style }: ArtProps & { color: string }) {
  return (
    <svg viewBox="0 0 12 20" className={className} style={style} aria-hidden="true" focusable="false">
      <path d="M3.5 2.5c3 2 3 6 0 9.5l5 6c3-3.6 3-7.6 0-11.4z" fill={color} />
    </svg>
  )
}

function Reindeer({ x }: { x: number }) {
  return (
    <g transform={`translate(${x} 0)`}>
      <path d="M11 18.5c2-3.4 6.4-4.6 11.6-4.2 3.6.3 5.8 2 5.8 4.4 0 2.4-2.6 3.6-6.4 3.6-4.6 0-8.4-.6-11-3.8z" />
      <path d="M12.6 17.2L8.4 10.6l2.6-1.2 4.6 6.6z" />
      <ellipse cx="7" cy="9.4" rx="3.6" ry="2.2" transform="rotate(-14 7 9.4)" />
      <path d="M8.6 7.6l1.6-4.6M9.8 4.6l3-1.6M7.2 7.4L5.4 3.4M5.9 4.6L3.4 3.6" fill="none" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M14 20.6l-6 3.6M15.6 21l-5.2 5M25.4 21.2l6 2.8M23.6 21.6l5.4 4.4" fill="none" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M28.2 17.2l2.6-1.6" fill="none" strokeWidth="1.6" strokeLinecap="round" />
    </g>
  )
}

/** 馴鹿雪橇剪影（往左飛：馴鹿在前、雪橇在後）。 */
export function SleighArt({ className, style }: ArtProps) {
  return (
    <svg viewBox="0 0 132 36" className={className} style={style} aria-hidden="true" focusable="false">
      <g fill={XM_PINE_DEEP} stroke={XM_PINE_DEEP}>
        <Reindeer x={0} />
        <Reindeer x={30} />
        <path d="M27 18.6L60 17.2M57 18.6L84 20.4" fill="none" strokeWidth="0.9" />
        <path d="M84 14.5h26c3.4 0 5.4-2.4 6-6.4l3.4.4c-.4 8.6-4.4 15-12 15H90c-3.4 0-6-3.4-6-9z" stroke="none" />
        <path d="M96 12.4c-.4-4.4 2.4-7.6 6-7.6 3 0 4.6 2.2 4.4 5.4l-2.6 2.2z" stroke="none" />
        <path d="M80 30h33c3.4 0 5.6-1.6 6.4-4.4" fill="none" strokeWidth="1.6" strokeLinecap="round" />
        <path d="M91 23.4V30M106 23.4V30" fill="none" strokeWidth="1.5" />
      </g>
    </svg>
  )
}
