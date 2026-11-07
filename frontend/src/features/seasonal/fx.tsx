import type { ReactNode } from 'react'
import { createPortal } from 'react-dom'

/** 一次性特效的共用工具（答對慶祝、及格散落、捲動飛過）。 */

export function prefersReducedMotion(): boolean {
  try {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches
  } catch {
    return false
  }
}

/**
 * 蓋在畫面上的特效圖層：fixed + inset 0 + overflow hidden，所以飛出畫面的元素不會造成水平溢出；
 * aria-hidden、pointer-events: none，不擋任何操作，也不佔版面高度。
 */
export function FxLayer({ children, className = '' }: { children: ReactNode; className?: string }) {
  return createPortal(
    <div className={`seasonal-fx-layer ${className}`} aria-hidden="true">
      {children}
    </div>,
    document.body,
  )
}
