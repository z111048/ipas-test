interface OverlayProps {
  isOpen: boolean
  onClick: () => void
}

export default function Overlay({ isOpen, onClick }: OverlayProps) {
  return (
    <div
      className={`fixed inset-0 bg-black/50 z-40 transition-opacity md:hidden ${isOpen ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'}`}
      onClick={onClick}
    />
  )
}
