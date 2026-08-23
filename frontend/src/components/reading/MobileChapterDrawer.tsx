import { type ReactNode, type RefObject, useRef } from 'react'
import { useFocusTrap } from '../../hooks/useFocusTrap'

interface MobileChapterDrawerProps {
  id?: string
  open: boolean
  title: string
  children: ReactNode
  onClose: () => void
  restoreFocusRef?: RefObject<HTMLElement | null>
}

export default function MobileChapterDrawer({
  id,
  open,
  title,
  children,
  onClose,
  restoreFocusRef,
}: MobileChapterDrawerProps) {
  const panelRef = useRef<HTMLDivElement>(null)
  const closeButtonRef = useRef<HTMLButtonElement>(null)

  useFocusTrap({
    active: open,
    containerRef: panelRef,
    initialFocusRef: closeButtonRef,
    restoreFocusRef,
    onDismiss: onClose,
    lockBodyScroll: true,
  })

  return (
    <>
      <div
        className={`xl:hidden fixed inset-0 z-40 bg-black/50 transition-opacity duration-300 ${
          open ? 'opacity-100' : 'opacity-0 pointer-events-none'
        }`}
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        id={id}
        ref={panelRef}
        className={`xl:hidden fixed bottom-0 left-0 right-0 z-50 flex max-h-[min(78dvh,40rem)] flex-col rounded-t-2xl bg-white shadow-2xl transition-transform duration-300 ease-out ${
          open ? 'translate-y-0' : 'translate-y-full'
        }`}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        aria-hidden={open ? undefined : 'true'}
        inert={open ? undefined : true}
        tabIndex={-1}
      >
        <div className="flex justify-center pt-2.5 pb-1 shrink-0">
          <div className="h-1 w-10 rounded-full bg-gray-200" />
        </div>
        <div className="flex min-h-11 shrink-0 items-center justify-between border-b border-border px-4 py-2">
          <span className="font-semibold text-primary text-sm">{title}</span>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            className="touch-target -mr-2 inline-flex items-center justify-center rounded text-text-light hover:text-primary"
            aria-label="關閉"
          >
            ✕
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-3 pb-[max(2rem,env(safe-area-inset-bottom))]">
          {children}
        </div>
      </div>
    </>
  )
}
