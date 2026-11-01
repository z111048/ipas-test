import { type ReactNode, useRef } from 'react'
import Dialog from './Dialog'

export interface ConfirmDialogProps {
  open: boolean
  /** 對話框的無障礙名稱，例如「確認重新開始」。 */
  title: string
  heading: ReactNode
  children: ReactNode
  /** 安全選項（預設焦點、主按鈕），例如「保留作答」。 */
  cancelLabel: string
  /** 破壞性選項，例如「清除並重新開始」。 */
  confirmLabel: string
  onCancel: () => void
  onConfirm: () => void
}

/** 破壞性操作前的確認；預設焦點落在「取消」，避免誤按 Enter 清掉資料。 */
export default function ConfirmDialog({
  open,
  title,
  heading,
  children,
  cancelLabel,
  confirmLabel,
  onCancel,
  onConfirm,
}: ConfirmDialogProps) {
  const cancelRef = useRef<HTMLButtonElement>(null)
  return (
    <Dialog open={open} title={title} onClose={onCancel} initialFocusRef={cancelRef} mobilePosition="center">
      <div className="p-5 sm:p-6">
        <h2 className="text-xl font-bold text-app-text">{heading}</h2>
        <div className="mt-3 text-body text-app-text">{children}</div>
        <div className="mt-5 flex flex-wrap gap-2">
          <button ref={cancelRef} type="button" className="btn-primary" onClick={onCancel}>
            {cancelLabel}
          </button>
          <button type="button" className="btn-danger" onClick={onConfirm}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </Dialog>
  )
}
