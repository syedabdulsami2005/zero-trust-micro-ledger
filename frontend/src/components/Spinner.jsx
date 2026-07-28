/* Spinner — premium light theme */

export function Spinner({ size = 'md' }) {
  const sz = { sm: 'w-4 h-4', md: 'w-6 h-6', lg: 'w-10 h-10' }[size]
  return (
    <div
      className={`${sz} rounded-full animate-spin`}
      style={{
        border: '2px solid var(--c-line)',
        borderTopColor: 'var(--c-accent)',
      }}
    />
  )
}

export function PageSpinner() {
  return (
    <div className="flex flex-col items-center justify-center h-64 gap-4">
      <div className="relative">
        <Spinner size="lg" />
        {/* Subtle glow ring */}
        <div
          className="absolute inset-0 rounded-full opacity-20"
          style={{ boxShadow: '0 0 16px 4px var(--c-accent)' }}
        />
      </div>
      <p className="text-xs text-ink-faint font-medium animate-pulse tracking-wide">
        Loading…
      </p>
    </div>
  )
}

export function EmptyState({ icon: Icon, title, message }) {
  return (
    <div className="empty-state">
      {Icon && (
        <div className="empty-icon-wrap animate-float">
          <Icon className="w-6 h-6 text-ink-faint" strokeWidth={1.5} />
        </div>
      )}
      <p className="text-ink-secondary font-semibold text-sm">{title}</p>
      {message && (
        <p className="text-ink-faint text-xs max-w-xs text-center leading-relaxed">{message}</p>
      )}
    </div>
  )
}

export function ErrorState({ message }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-2">
      <div
        className="w-12 h-12 rounded-2xl flex items-center justify-center mb-1"
        style={{ background: '#FFF1F2', border: '1px solid #FECACA' }}
      >
        <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="#DC2626" strokeWidth={2}>
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      </div>
      <p className="text-danger font-semibold text-sm">Failed to load data</p>
      <p className="text-ink-muted text-xs max-w-sm text-center leading-relaxed">{message}</p>
    </div>
  )
}
