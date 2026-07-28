export default function KpiCard({
  label,
  value,
  icon: Icon,
  iconColor  = 'text-accent',
  iconBg     = 'bg-accent-faint',
  sub,
  highlight,
  trend,
  accentColor, // optional custom accent for the icon bg/color
}) {
  return (
    <div
      className={`card card-hover p-5 flex flex-col gap-3.5 group ${
        highlight
          ? 'border-red-200 shadow-[0_4px_16px_rgba(220,38,38,.08)]'
          : ''
      }`}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <span className="section-header leading-none">{label}</span>
        {Icon && (
          <div
            className={`w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0
                        transition-all duration-200 group-hover:scale-105 ${
              highlight ? 'bg-red-50' : iconBg
            }`}
            style={accentColor ? { background: accentColor + '15' } : undefined}
          >
            <Icon
              className={`w-4 h-4 ${highlight ? 'text-red-500' : iconColor}`}
              style={accentColor ? { color: accentColor } : undefined}
              strokeWidth={2}
            />
          </div>
        )}
      </div>

      {/* Value */}
      <div>
        <p
          className={`stat-value ${highlight ? 'text-red-600' : ''}`}
          style={
            highlight
              ? {}
              : {
                  background: 'linear-gradient(135deg, var(--c-ink) 0%, var(--c-ink-secondary) 100%)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                  backgroundClip: 'text',
                }
          }
        >
          {value ?? '—'}
        </p>
        {sub && (
          <p className="text-xs text-ink-faint mt-1 truncate font-medium leading-none">
            {sub}
          </p>
        )}
      </div>

      {/* Trend bar */}
      {trend !== undefined && (
        <div className="h-0.5 rounded-full overflow-hidden" style={{ background: 'var(--c-surface-subtle)' }}>
          <div
            className={`h-full rounded-full transition-all duration-700 ${
              highlight ? 'bg-red-400' : 'bg-accent'
            }`}
            style={{ width: `${Math.min(100, Math.max(0, trend))}%` }}
          />
        </div>
      )}
    </div>
  )
}
