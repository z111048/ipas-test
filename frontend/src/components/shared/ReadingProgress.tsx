import { useEffect, useState } from 'react'
import { preferredScrollBehavior } from '../../utils/motion'

type ScrollHost = HTMLElement | Window

function readMetrics(host: ScrollHost) {
  if (host instanceof Window) {
    return {
      top: window.scrollY || document.documentElement.scrollTop,
      height: document.documentElement.scrollHeight,
      client: window.innerHeight,
    }
  }
  return { top: host.scrollTop, height: host.scrollHeight, client: host.clientHeight }
}

/**
 * Tracks scroll progress (0–100) and back-to-top visibility for a scroll host
 * resolved lazily via a callback (so callers can point at a ref value, or at
 * an ancestor element discovered through `closest()`, without this hook
 * needing to know which).
 */
export function useScrollProgress(resolveHost: () => ScrollHost | null | undefined) {
  const [progress, setProgress] = useState(0)
  const [showBackToTop, setShowBackToTop] = useState(false)

  useEffect(() => {
    const host = resolveHost()
    if (!host) return

    const handleScroll = () => {
      const { top, height, client } = readMetrics(host)
      const max = height - client
      setProgress(max > 0 ? Math.min(100, Math.max(0, (top / max) * 100)) : 0)
      setShowBackToTop(top > client * 0.6)
    }

    handleScroll()
    host.addEventListener('scroll', handleScroll, { passive: true })
    window.addEventListener('resize', handleScroll)
    return () => {
      host.removeEventListener('scroll', handleScroll)
      window.removeEventListener('resize', handleScroll)
    }
    // resolveHost is expected to resolve to a stable scroll host for the
    // lifetime of the owning component (route params changing content don't
    // change which element scrolls).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const scrollToTop = () => {
    const host = resolveHost()
    host?.scrollTo({ top: 0, behavior: preferredScrollBehavior() })
  }

  return { progress, showBackToTop, scrollToTop }
}

export function ReadingProgressBar({ progress, className = '' }: { progress: number; className?: string }) {
  return (
    <div className={`h-[3px] w-full shrink-0 overflow-hidden rounded-full bg-[#e8eef5] ${className}`} aria-hidden="true">
      <div
        className="h-full bg-accent transition-[width] duration-150 ease-out"
        style={{ width: `${progress}%` }}
      />
    </div>
  )
}

export function BackToTopButton({
  show,
  onClick,
  className = '',
}: {
  show: boolean
  onClick: () => void
  className?: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label="回到頂部"
      tabIndex={show ? 0 : -1}
      className={`touch-target fixed z-30 flex h-11 w-11 items-center justify-center rounded-full border border-border bg-white text-lg text-primary shadow-md transition-all duration-200 hover:border-accent hover:text-accent ${
        show ? 'translate-y-0 opacity-100' : 'pointer-events-none translate-y-3 opacity-0'
      } ${className}`}
    >
      ↑
    </button>
  )
}
