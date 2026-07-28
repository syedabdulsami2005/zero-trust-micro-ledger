import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'

export default function Drawer({ open, onClose, title, children, width = 'w-[480px]' }) {
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  useEffect(() => {
    if (!open) return
    const handler = (e) => { if (e.key === 'Escape') onClose?.() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, onClose])

  if (!mounted || typeof document === 'undefined') return null

  return createPortal(
    <>
      {/* Backdrop */}
      <div
        className={`fixed inset-0 z-40 transition-opacity duration-300 ${
          open ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'
        }`}
        style={{
          background: 'rgba(24,24,27,0.20)',
          backdropFilter: open ? 'blur(3px)' : 'none',
        }}
        onClick={onClose}
      />

      {/* Panel */}
      <div
        className={`fixed top-0 right-0 h-full ${width} z-50 flex flex-col`}
        style={{
          background: '#FFFFFF',
          borderLeft: '1px solid var(--c-line)',
          boxShadow: open
            ? '-16px 0 40px -8px rgba(0,0,0,0.10), -4px 0 10px -4px rgba(0,0,0,0.06)'
            : 'none',
          transform: open ? 'translateX(0)' : 'translateX(100%)',
          visibility: open ? 'visible' : 'hidden',
          pointerEvents: open ? 'auto' : 'none',
          transition: open
            ? 'transform var(--dur-slow) var(--ease-spring), box-shadow var(--dur-slow) var(--ease-smooth), visibility 0s 0s'
            : 'transform var(--dur-slow) var(--ease-spring), box-shadow var(--dur-slow) var(--ease-smooth), visibility 0s var(--dur-slow)',
        }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-5 py-4 flex-shrink-0"
          style={{
            borderBottom: '1px solid var(--c-line)',
            background: 'var(--c-surface-warm)',
          }}
        >
          <h3 className="text-sm font-bold text-ink truncate pr-4" style={{ letterSpacing: '-0.01em' }}>
            {title}
          </h3>
          <button
            onClick={onClose}
            aria-label="Close drawer"
            className="btn-icon"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          {children}
        </div>
      </div>
    </>,
    document.body
  )
}
