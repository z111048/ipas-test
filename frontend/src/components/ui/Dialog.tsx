import { type ReactNode, type RefObject, useRef } from 'react'
import { useFocusTrap } from '../../hooks/useFocusTrap'

interface DialogProps {
  open: boolean
  title: string
  children: ReactNode
  onClose: () => void
  initialFocusRef?: RefObject<HTMLElement | null>
  restoreFocusRef?: RefObject<HTMLElement | null>
  descriptionId?: string
  closeOnBackdrop?: boolean
  lockBodyScroll?: boolean
  mobilePosition?: 'bottom' | 'top' | 'center'
  className?: string
}

export default function Dialog({
  open,
  title,
  children,
  onClose,
  initialFocusRef,
  restoreFocusRef,
  descriptionId,
  closeOnBackdrop = true,
  lockBodyScroll = true,
  mobilePosition = 'bottom',
  className = '',
}: DialogProps) {
  const panelRef = useRef<HTMLDivElement>(null)
  useFocusTrap({
    active: open,
    containerRef: panelRef,
    onDismiss: onClose,
    initialFocusRef,
    restoreFocusRef,
    lockBodyScroll,
  })

  if (!open) return null

  const mobilePositionClass =
    mobilePosition === 'top'
      ? 'items-start p-4 pt-4 sm:items-center sm:p-6'
      : mobilePosition === 'center'
        ? 'items-center p-4 sm:p-6'
        : 'items-end p-0 sm:items-center sm:p-6'

  return (
    <div
      className={`fixed inset-0 z-200 flex justify-center bg-slate-950/45 ${mobilePositionClass}`}
      onClick={closeOnBackdrop ? onClose : undefined}
      role="presentation"
    >
      <section
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        aria-describedby={descriptionId}
        tabIndex={-1}
        onClick={(event) => event.stopPropagation()}
        className={`max-h-[90dvh] w-full overflow-y-auto rounded-t-2xl bg-card shadow-2xl sm:max-w-2xl sm:rounded-xl ${className}`}
      >
        {children}
      </section>
    </div>
  )
}
