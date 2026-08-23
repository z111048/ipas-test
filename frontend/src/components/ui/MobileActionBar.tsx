import type { ReactNode } from 'react'

interface MobileActionBarProps {
  children: ReactNode
  className?: string
}

export default function MobileActionBar({ children, className = '' }: MobileActionBarProps) {
  return (
    <div className={`mobile-action-bar flex items-center justify-between gap-2 ${className}`}>
      {children}
    </div>
  )
}
