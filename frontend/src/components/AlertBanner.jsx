import { Link } from 'react-router-dom'
import { AlertTriangle, X, Eye, ShieldAlert } from 'lucide-react'

export default function AlertBanner({ state, onDismiss }) {
  const chainState = state?.chain_state ?? state?.health_status
  if (!chainState || chainState === 'healthy') return null

  const isBroken   = chainState === 'broken'
  const isDegraded = chainState === 'degraded'
  const activeCount = state?.active_alert_count ?? 0
  const ackCount    = state?.acknowledged_alert_count ?? 0

  let statusLabel = chainState.toUpperCase()
  let message     = ''
  let Icon        = AlertTriangle

  if (isBroken) {
    Icon = ShieldAlert
    if (ackCount > 0 && activeCount === 0) {
      statusLabel = 'INVESTIGATING'
      message = 'Append frozen until clean verification.'
    } else {
      message = 'Append frozen. Acknowledge, repair, and verify.'
    }
  } else if (isDegraded) {
    message = 'Minor chain issues detected.'
  }

  const totalActive  = activeCount + ackCount
  const isInvestigating = isBroken && ackCount > 0 && activeCount === 0

  const s = isBroken && !isInvestigating
    ? { bg: '#FFF1F2', border: '#FECACA', text: '#991B1B', accent: '#DC2626', iconBg: '#FEE2E2' }
    : { bg: '#FFFBEB', border: '#FDE68A', text: '#92400E', accent: '#D97706', iconBg: '#FEF3C7' }

  return (
    <div
      className="fixed top-0 right-0 z-40 flex items-center gap-3 px-5 h-10 text-xs font-medium animate-slide-up"
      style={{
        left: 'var(--sidebar-w)',
        background: s.bg,
        borderBottom: `1px solid ${s.border}`,
        color: s.text,
      }}
    >
      {/* Icon */}
      <div
        className="w-5 h-5 rounded-md flex items-center justify-center flex-shrink-0"
        style={{ background: s.iconBg }}
      >
        <Icon className="w-3 h-3" style={{ color: s.accent }} />
      </div>

      {/* Message */}
      <span className="flex items-center gap-2 flex-1 min-w-0">
        <strong className="uppercase tracking-wide font-bold text-[11px]">{statusLabel}</strong>
        {totalActive > 0 && (
          <span
            className="inline-flex text-[10px] font-bold px-1.5 py-0.5 rounded-full"
            style={{ background: s.iconBg, color: s.accent }}
          >
            {totalActive} alert{totalActive !== 1 ? 's' : ''}
          </span>
        )}
        {message && (
          <span className="opacity-70 hidden sm:inline truncate">{message}</span>
        )}
      </span>

      {/* CTA */}
      <Link
        to="/alerts"
        className="flex-shrink-0 font-semibold px-2.5 py-1 rounded-lg border flex items-center gap-1 hover:opacity-90 transition-opacity"
        style={{
          background: 'white',
          borderColor: s.border,
          color: s.accent,
          boxShadow: '0 1px 3px rgba(0,0,0,.05)',
          fontSize: '11px',
        }}
      >
        {ackCount > 0 ? <Eye className="w-3 h-3" /> : null}
        View Alerts
      </Link>

      {/* Dismiss */}
      {onDismiss && (
        <button
          onClick={onDismiss}
          className="ml-0.5 w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0 hover:bg-white/50 transition-colors"
          aria-label="Dismiss banner"
        >
          <X className="w-3 h-3" />
        </button>
      )}
    </div>
  )
}
