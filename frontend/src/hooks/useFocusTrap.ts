import { type RefObject, useEffect, useRef } from 'react'

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'textarea:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

// Active traps, innermost last. Only the topmost trap handles Escape/Tab, so a
// dialog opened on top of another dialog does not dismiss both on one Esc.
const trapStack: object[] = []

function focusableElements(container: HTMLElement) {
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR))
    .filter((el) => !el.hasAttribute('disabled') && !el.getAttribute('aria-hidden'))
}

interface FocusTrapOptions {
  active: boolean
  containerRef: RefObject<HTMLElement | null>
  onDismiss: () => void
  initialFocusRef?: RefObject<HTMLElement | null>
  restoreFocusRef?: RefObject<HTMLElement | null>
  lockBodyScroll?: boolean
  /**
   * Checked when the trap deactivates; return false to skip focus restore
   * (e.g. the drawer closed because the user navigated — focus goes to <main>).
   */
  shouldRestoreFocus?: () => boolean
}

export function useFocusTrap({
  active,
  containerRef,
  onDismiss,
  initialFocusRef,
  restoreFocusRef,
  lockBodyScroll = true,
  shouldRestoreFocus,
}: FocusTrapOptions) {
  // Dialog consumers often pass an inline close callback. Keep the latest
  // callback without tearing down the trap (and restoring/re-focusing) on
  // every parent render, such as the exam timer's one-second updates.
  const onDismissRef = useRef(onDismiss)
  onDismissRef.current = onDismiss
  const shouldRestoreRef = useRef(shouldRestoreFocus)
  shouldRestoreRef.current = shouldRestoreFocus

  useEffect(() => {
    if (!active) return

    const container = containerRef.current
    if (!container) return

    const restoreTarget = restoreFocusRef?.current ?? document.activeElement
    const previousOverflow = document.body.style.overflow
    const previousPaddingRight = document.body.style.paddingRight
    const scrollbarWidth = window.innerWidth - document.documentElement.clientWidth

    if (lockBodyScroll) {
      document.body.style.overflow = 'hidden'
      if (scrollbarWidth > 0) document.body.style.paddingRight = `${scrollbarWidth}px`
    }

    const focusTarget = initialFocusRef?.current ?? focusableElements(container)[0] ?? container
    requestAnimationFrame(() => focusTarget.focus({ preventScroll: true }))

    const trapToken = {}
    trapStack.push(trapToken)

    const onKeyDown = (event: KeyboardEvent) => {
      if (trapStack[trapStack.length - 1] !== trapToken) return
      if (event.key === 'Escape') {
        event.preventDefault()
        onDismissRef.current()
        return
      }

      if (event.key !== 'Tab') return
      const items = focusableElements(container)
      if (items.length === 0) {
        event.preventDefault()
        container.focus({ preventScroll: true })
        return
      }

      const first = items[0]
      const last = items[items.length - 1]
      const current = document.activeElement
      if (event.shiftKey && current === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && current === last) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      const stackIndex = trapStack.indexOf(trapToken)
      if (stackIndex >= 0) trapStack.splice(stackIndex, 1)
      if (lockBodyScroll) {
        document.body.style.overflow = previousOverflow
        document.body.style.paddingRight = previousPaddingRight
      }
      const restore = shouldRestoreRef.current?.() ?? true
      if (restore && restoreTarget instanceof HTMLElement && document.contains(restoreTarget)) {
        requestAnimationFrame(() => restoreTarget.focus({ preventScroll: true }))
      }
    }
  }, [active, containerRef, initialFocusRef, lockBodyScroll, restoreFocusRef])
}
