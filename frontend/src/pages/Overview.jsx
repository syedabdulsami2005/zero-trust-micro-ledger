import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Layers, Bell, ShieldCheck, Clock, Activity, ChevronRight,
  CheckCircle2, AlertTriangle, Lock, Unlock, TrendingUp,
  ShieldAlert, Zap, ArrowRight,
} from 'lucide-react'
import { getState, getEvents, getAlerts, getLedger } from '../api/client'
import KpiCard from '../components/KpiCard'
import StatusBadge, { ChangeTypeBadge } from '../components/StatusBadge'
import { PageSpinner, ErrorState } from '../components/Spinner'

function fmtTime(ts) {
  if (!ts) return '—'
  try { return new Date(ts).toLocaleString() } catch { return ts }
}

function fmtShort(ts) {
  if (!ts) return '—'
  try { return new Date(ts).toLocaleTimeString() } catch { return ts }
}

const SEVERITY_CLS = {
  critical: 'tag-broken',
  warning:  'tag-warning',
  info:     'tag-info',
}

const STATUS_CFG = {
  active:       { dot: 'bg-danger',    label: 'Active',       cls: 'text-danger' },
  acknowledged: { dot: 'bg-warn',      label: 'Acknowledged', cls: 'text-warn' },
  resolved:     { dot: 'bg-ok',        label: 'Resolved',     cls: 'text-ok' },
}

/* ─────────────────────────────────────────────────────────── */
/* Chain Status Banner — redesigned                            */
/* ─────────────────────────────────────────────────────────── */
function ChainStatusBanner({ state }) {
  const chainState    = state?.chain_state ?? state?.health_status ?? 'unknown'
  const appendEnabled = state?.append_enabled ?? !state?.frozen
  const ackCount      = state?.acknowledged_alert_count ?? 0

  let config = {
    bg:        'linear-gradient(135deg, #ECFDF5 0%, #F0FDFA 60%, #F7FFFE 100%)',
    border:    '#A7F3D0',
    accentBar: 'linear-gradient(90deg, #059669, #34D399)',
    iconGrad:  'linear-gradient(135deg, #059669, #10B981)',
    iconShadow:'rgba(5,150,105,.25)',
    iconColor: '#FFFFFF',
    textColor: '#065F46',
    subColor:  '#6EE7B7',
    labelColor:'#059669',
    Icon:      ShieldCheck,
    label:     'Chain Healthy',
    sub:       'All blocks verified. Integrity intact.',
  }

  if (chainState === 'broken') {
    config = ackCount > 0
      ? {
          bg:        'linear-gradient(135deg, #FFFBEB 0%, #FEF9EC 60%, #FFFDF5 100%)',
          border:    '#FDE68A',
          accentBar: 'linear-gradient(90deg, #D97706, #FBBF24)',
          iconGrad:  'linear-gradient(135deg, #D97706, #F59E0B)',
          iconShadow:'rgba(217,119,6,.25)',
          iconColor: '#FFFFFF',
          textColor: '#92400E',
          subColor:  '#F59E0B',
          labelColor:'#D97706',
          Icon:      AlertTriangle,
          label:     'Investigating',
          sub:       'Alert acknowledged — append frozen until verification passes.',
        }
      : {
          bg:        'linear-gradient(135deg, #FFF1F2 0%, #FFF5F5 60%, #FFFAFA 100%)',
          border:    '#FECACA',
          accentBar: 'linear-gradient(90deg, #DC2626, #F87171)',
          iconGrad:  'linear-gradient(135deg, #DC2626, #EF4444)',
          iconShadow:'rgba(220,38,38,.25)',
          iconColor: '#FFFFFF',
          textColor: '#991B1B',
          subColor:  '#FCA5A5',
          labelColor:'#DC2626',
          Icon:      ShieldAlert,
          label:     'Chain Broken',
          sub:       'Integrity failure detected. Repair and re-verify.',
        }
  } else if (chainState === 'degraded') {
    config = {
      bg:        'linear-gradient(135deg, #FFFBEB 0%, #FEFCE8 60%, #FFFFF5 100%)',
      border:    '#FDE68A',
      accentBar: 'linear-gradient(90deg, #D97706, #FCD34D)',
      iconGrad:  'linear-gradient(135deg, #D97706, #F59E0B)',
      iconShadow:'rgba(217,119,6,.25)',
      iconColor: '#FFFFFF',
      textColor: '#78350F',
      subColor:  '#F59E0B',
      labelColor:'#D97706',
      Icon:      AlertTriangle,
      label:     'Chain Degraded',
      sub:       'Non-critical issues detected. Review alerts.',
    }
  }

  const { bg, border, accentBar, iconGrad, iconShadow, iconColor, textColor, labelColor, Icon, label, sub } = config

  return (
    <div
      className="rounded-2xl border overflow-hidden transition-all duration-300"
      style={{ background: bg, borderColor: border }}
    >
      {/* Top accent bar */}
      <div className="h-0.5" style={{ background: accentBar }} />

      <div className="p-5 flex items-center gap-5">
        {/* Icon */}
        <div
          className="w-14 h-14 rounded-2xl flex items-center justify-center flex-shrink-0"
          style={{
            background: iconGrad,
            boxShadow: `0 6px 18px ${iconShadow}`,
          }}
        >
          <Icon className="w-7 h-7" style={{ color: iconColor }} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <p className="section-header mb-1.5" style={{ color: labelColor }}>Chain Status</p>
          <div className="flex items-center gap-3">
            <StatusBadge status={chainState} size="lg" />
            <span className="text-base font-bold" style={{ color: textColor }}>{label}</span>
          </div>
          <p className="text-xs mt-1.5 font-medium" style={{ color: textColor, opacity: 0.7 }}>{sub}</p>
        </div>

        {/* Append lock indicator */}
        <div
          className="flex-shrink-0 flex flex-col items-center gap-1.5 px-4 py-3 rounded-xl"
          style={{
            background: 'rgba(255,255,255,0.55)',
            border: `1px solid ${border}`,
          }}
        >
          {appendEnabled
            ? <Unlock className="w-5 h-5" style={{ color: labelColor }} />
            : <Lock   className="w-5 h-5" style={{ color: labelColor }} />
          }
          <p className="text-[10px] font-semibold" style={{ color: textColor }}>
            {appendEnabled ? 'Unlocked' : 'Locked'}
          </p>
        </div>

        {/* Updated time */}
        <div className="text-right flex-shrink-0 hidden sm:block">
          <p className="section-header mb-1">Updated</p>
          <p className="text-xs font-semibold" style={{ color: textColor }}>
            {fmtShort(state?.updated_utc) || '—'}
          </p>
        </div>
      </div>
    </div>
  )
}

/* ─────────────────────────────────────────────────────────── */
/* Section Panel                                               */
/* ─────────────────────────────────────────────────────────── */
function SectionPanel({ icon: Icon, iconColor = 'text-accent', title, linkTo, linkLabel = 'View all', children }) {
  return (
    <div className="card overflow-hidden flex flex-col">
      {/* Panel header */}
      <div className="panel-header">
        <h2 className="card-title flex items-center gap-2">
          <Icon className={`w-4 h-4 ${iconColor}`} strokeWidth={2} />
          {title}
        </h2>
        {linkTo && (
          <Link
            to={linkTo}
            className="text-xs font-semibold flex items-center gap-0.5 transition-all duration-150 group"
            style={{ color: 'var(--c-accent)' }}
          >
            {linkLabel}
            <ChevronRight className="w-3.5 h-3.5 transition-transform duration-150 group-hover:translate-x-0.5" />
          </Link>
        )}
      </div>
      {children}
    </div>
  )
}

/* ─────────────────────────────────────────────────────────── */
/* Main Overview Page                                          */
/* ─────────────────────────────────────────────────────────── */
export default function Overview() {
  const [state,    setState]    = useState(null)
  const [events,   setEvents]   = useState([])
  const [alerts,   setAlerts]   = useState([])
  const [chainLen, setChainLen] = useState(null)
  const [error,    setError]    = useState(null)
  const [loading,  setLoading]  = useState(true)

  const load = async () => {
    try {
      const [s, ev, al, ledger] = await Promise.all([
        getState(),
        getEvents(5),
        getAlerts(5, 'unresolved'),
        getLedger(1, 0),
      ])
      setState(s)
      setEvents(Array.isArray(ev) ? ev : [])
      setAlerts(Array.isArray(al) ? al : [])
      setChainLen(ledger?.total ?? null)
      setError(null)
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  useEffect(() => {
    load()
    const t = setInterval(load, 10000)
    return () => clearInterval(t)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) return <PageSpinner />
  if (error)   return <ErrorState message={error} />

  const lastResolved  = state?.last_resolved_incident
  const hasAlerts     = alerts.length > 0
  const activeAlerts  = state?.active_alert_count ?? 0

  return (
    <div className="space-y-6 animate-fade-in">

      {/* ── Page header ──────────────────────────────────── */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="page-title">Overview</h1>
          <p className="page-subtitle">Real-time chain health and activity summary</p>
        </div>
        {/* Live pill */}
        <div
          className="flex items-center gap-2 px-3 py-1.5 rounded-full border"
          style={{
            background: '#ECFDF5',
            borderColor: '#A7F3D0',
          }}
        >
          <span className="live-dot" />
          <span className="text-xs font-bold" style={{ color: '#059669' }}>Live</span>
        </div>
      </div>

      {/* ── KPI row ──────────────────────────────────────── */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4 stagger">
        <KpiCard
          label="Chain Length"
          value={chainLen ?? '—'}
          icon={Layers}
          iconColor="text-accent"
          iconBg="bg-accent-faint"
          sub="total blocks"
        />
        <KpiCard
          label="Active Alerts"
          value={(state?.active_alert_count ?? 0) + (state?.acknowledged_alert_count ?? 0)}
          icon={Bell}
          iconColor={activeAlerts > 0 ? 'text-danger' : 'text-ink-faint'}
          iconBg={activeAlerts > 0 ? 'bg-danger-bg' : 'bg-surface-subtle'}
          highlight={activeAlerts > 0}
          sub={`${state?.acknowledged_alert_count ?? 0} acknowledged`}
        />
        <KpiCard
          label="Verifications"
          value={state?.total_verifications ?? 0}
          icon={ShieldCheck}
          iconColor="text-ok"
          iconBg="bg-ok-bg"
          sub={state?.last_verification_result === 'pass' ? '✓ Last: pass' : '✗ Last: fail'}
        />
        <KpiCard
          label="Last Verified"
          value={state?.last_verification_utc ? fmtShort(state.last_verification_utc) : 'Never'}
          icon={Clock}
          iconColor="text-warn"
          iconBg="bg-warn-bg"
          sub={state?.last_verification_utc ? fmtTime(state.last_verification_utc) : 'Not yet verified'}
        />
      </div>

      {/* ── Chain health hero ────────────────────────────── */}
      <ChainStatusBanner state={state} />

      {/* ── Last resolved incident ───────────────────────── */}
      {lastResolved && (
        <div
          className="card p-4 flex items-center gap-4 card-accent-ok"
          style={{ background: 'linear-gradient(135deg, #ECFDF5, #F7FFFE)' }}
        >
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
            style={{ background: 'linear-gradient(135deg,#059669,#10B981)', boxShadow: '0 4px 12px rgba(5,150,105,.25)' }}
          >
            <CheckCircle2 className="w-5 h-5 text-white" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-[10px] font-bold text-ok uppercase tracking-wider mb-0.5">
              Last Resolved Incident
            </p>
            <p className="text-sm font-semibold text-ink truncate">
              {lastResolved.incident_key ?? lastResolved.alert_id ?? '—'}
            </p>
            <p className="text-xs text-ink-muted mt-0.5">
              Resolved {fmtTime(lastResolved.resolved_at)} · {lastResolved.severity} {lastResolved.failure_type}
            </p>
          </div>
          <Link
            to="/alerts"
            className="text-xs font-semibold flex items-center gap-1 flex-shrink-0 transition-all duration-150 group"
            style={{ color: '#059669' }}
          >
            History
            <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </div>
      )}

      {/* ── Two-column panels ────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Active alerts panel */}
        <SectionPanel
          icon={Bell}
          iconColor={hasAlerts ? 'text-danger' : 'text-ink-faint'}
          title="Active Alerts"
          linkTo="/alerts"
        >
          <div className="divide-y" style={{ borderColor: 'var(--c-surface-subtle)' }}>
            {alerts.length === 0 ? (
              <div className="px-5 py-10 flex flex-col items-center gap-2">
                <div
                  className="w-11 h-11 rounded-2xl flex items-center justify-center"
                  style={{ background: '#ECFDF5', border: '1px solid #A7F3D0' }}
                >
                  <ShieldCheck className="w-5 h-5 text-ok" />
                </div>
                <p className="text-sm font-semibold text-ink-secondary">No active alerts</p>
                <p className="text-xs text-ink-faint">Chain integrity is healthy</p>
              </div>
            ) : alerts.slice(0, 5).map(a => {
              const sc = STATUS_CFG[a.status] ?? STATUS_CFG.active
              return (
                <div
                  key={a.alert_id}
                  className="px-5 py-3.5 flex items-start gap-3 transition-colors duration-100"
                  style={{ '--hover': 'var(--c-surface-warm)' }}
                  onMouseEnter={e => e.currentTarget.style.background = 'var(--c-surface-warm)'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                >
                  <span className={`w-2 h-2 rounded-full mt-2 flex-shrink-0 ${sc.dot}`} />
                  <span className={`${SEVERITY_CLS[a.severity] ?? 'tag-info'} mt-0.5 flex-shrink-0`}>
                    {a.severity}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-ink font-medium truncate">{a.message}</p>
                    <p className="text-xs text-ink-faint mt-0.5">
                      <span className={`font-semibold ${sc.cls}`}>{sc.label}</span>
                      {' · '}{fmtTime(a.created_at ?? a.timestamp_utc)}
                    </p>
                  </div>
                </div>
              )
            })}
          </div>
        </SectionPanel>

        {/* Latest events panel */}
        <SectionPanel
          icon={Activity}
          iconColor="text-accent"
          title="Latest Events"
          linkTo="/events"
        >
          <div className="divide-y" style={{ borderColor: 'var(--c-surface-subtle)' }}>
            {events.length === 0 ? (
              <div className="px-5 py-10 flex flex-col items-center gap-2">
                <div
                  className="w-11 h-11 rounded-2xl flex items-center justify-center"
                  style={{ background: 'var(--c-accent-faint)', border: '1px solid rgba(15,118,110,.18)' }}
                >
                  <Zap className="w-5 h-5 text-accent" />
                </div>
                <p className="text-sm font-semibold text-ink-secondary">No events recorded yet</p>
                <p className="text-xs text-ink-faint text-center">Events will appear as the ledger captures activity</p>
              </div>
            ) : events.slice(0, 5).map(ev => (
              <div
                key={ev.event_id ?? ev.block_index}
                className="px-5 py-3.5 transition-colors duration-100"
                onMouseEnter={e => e.currentTarget.style.background = 'var(--c-surface-warm)'}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="tag-accent text-[10px]">{ev.event_type}</span>
                    <ChangeTypeBadge changeType={ev.change_type} changeLabel={ev.change_label} />
                  </div>
                  <span className="mono text-ink-faint">#{ev.block_index}</span>
                </div>
                <p className="text-sm text-ink font-medium truncate mt-1.5">{ev.source_path}</p>
                <p className="text-xs text-ink-faint mt-0.5">{fmtTime(ev.timestamp_utc)}</p>
              </div>
            ))}
          </div>
        </SectionPanel>

      </div>
    </div>
  )
}
