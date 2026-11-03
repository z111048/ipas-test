/**
 * 萬聖節剪影（inline SVG，自己畫，不用外部圖檔或字型 icon）。
 * 一律 aria-hidden、focusable=false；顏色只用在這些裝飾上，不碰主色與答題狀態色。
 */
import type { CSSProperties } from 'react'

export const HW_ORANGE = '#ea580c'
export const HW_ORANGE_DEEP = '#c2410c'
export const HW_ORANGE_SOFT = '#fdba74'
export const HW_PURPLE = '#3b0764'
export const HW_PURPLE_SOFT = '#7e22ce'

interface ArtProps {
  className?: string
  style?: CSSProperties
}

export function PumpkinArt({ className, style, face = false }: ArtProps & { face?: boolean }) {
  return (
    <svg viewBox="0 0 64 64" className={className} style={style} aria-hidden="true" focusable="false">
      <path d="M31 19c0-5 1-9 5-12l3.5 2.2c-3 2.6-4.3 5.6-4.5 9.8z" fill={HW_PURPLE} />
      <path d="M35.5 12.5c4-3.5 9-3.6 12-1.6-3.6.2-6.6 1.8-9 4.6z" fill={HW_PURPLE_SOFT} />
      <ellipse cx="20" cy="39" rx="15" ry="18" fill={HW_ORANGE_DEEP} />
      <ellipse cx="44" cy="39" rx="15" ry="18" fill={HW_ORANGE_DEEP} />
      <ellipse cx="32" cy="39" rx="15" ry="19.5" fill={HW_ORANGE} />
      <path
        d="M24 24c-4 6-4 24 0 31M40 24c4 6 4 24 0 31"
        fill="none"
        stroke={HW_ORANGE_DEEP}
        strokeWidth="1.6"
        strokeLinecap="round"
        opacity="0.7"
      />
      {face && (
        <g fill={HW_PURPLE}>
          <path d="M22 34l6-4 1 6z" />
          <path d="M42 34l-6-4-1 6z" />
          <path d="M21 44c4 5 18 5 22 0-2 1-4 1.4-5 1.2l-1.5 2.4-2-2.2c-1.6.3-3.4.3-5 0l-2 2.2-1.5-2.4c-1.2.2-3-.2-5-1.2z" />
        </g>
      )}
    </svg>
  )
}

export function BatArt({ className, style }: ArtProps) {
  return (
    <svg viewBox="0 0 64 30" className={className} style={style} aria-hidden="true" focusable="false">
      <path
        fill={HW_PURPLE}
        d="M32 9.5c-1.3 0-2.2-1.7-2.6-3.2l-1 3.6C24 9.4 19.3 6.6 17 2.5c-.1 5.6-6.4 8.6-15 7.9 5 2.6 7.2 7.6 6.6 12.4 2.8-3 7.4-4 10.6-2.4 1.6-3 5.4-4.2 8-2.6 1.4-1.6 3-2.6 4.8-2.6s3.4 1 4.8 2.6c2.6-1.6 6.4-.4 8 2.6 3.2-1.6 7.8-.6 10.6 2.4-.6-4.8 1.6-9.8 6.6-12.4-8.6.7-14.9-2.3-15-7.9-2.3 4.1-7 6.9-11.4 7.4l-1-3.6c-.4 1.5-1.3 3.2-2.6 3.2z"
      />
    </svg>
  )
}

export function GhostArt({ className, style }: ArtProps) {
  return (
    <svg viewBox="0 0 40 44" className={className} style={style} aria-hidden="true" focusable="false">
      <path
        d="M20 2.5C10.6 2.5 4.5 9.8 4.5 19.5V41l5-3.6 5.2 3.6 5.3-3.6 5.3 3.6 5.2-3.6 5 3.6V19.5C35.5 9.8 29.4 2.5 20 2.5z"
        fill="#ffffff"
        stroke="#6b21a8"
        strokeOpacity="0.55"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
      <ellipse cx="14.5" cy="19" rx="2.6" ry="3.4" fill={HW_PURPLE} />
      <ellipse cx="25.5" cy="19" rx="2.6" ry="3.4" fill={HW_PURPLE} />
      <ellipse cx="11" cy="25" rx="2.6" ry="1.5" fill={HW_ORANGE_SOFT} opacity="0.85" />
      <ellipse cx="29" cy="25" rx="2.6" ry="1.5" fill={HW_ORANGE_SOFT} opacity="0.85" />
      <path d="M17.5 26.5c1.4 1.4 3.6 1.4 5 0" fill="none" stroke={HW_PURPLE} strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}

export function CandyArt({ color, className, style }: ArtProps & { color: string }) {
  return (
    <svg viewBox="0 0 32 16" className={className} style={style} aria-hidden="true" focusable="false">
      <path d="M9 8L1.5 2.5v11z" fill={color} opacity="0.8" />
      <path d="M23 8l7.5-5.5v11z" fill={color} opacity="0.8" />
      <circle cx="16" cy="8" r="7" fill={color} />
      <path d="M11.5 4.5l9 7M14 2.5l7 5.5" stroke="#ffffff" strokeOpacity="0.55" strokeWidth="1.4" />
    </svg>
  )
}
