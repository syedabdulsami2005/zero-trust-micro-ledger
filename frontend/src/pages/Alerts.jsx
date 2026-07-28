import { useEffect, useState, useMemo, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Bell, AlertTriangle, XCircle, Info, CheckCircle2,
  Clock, ShieldCheck, ExternalLink, RefreshCw, Eye
} from 'lucide-react'
import { getAlerts, acknowledgeAlert, runVerification } from '../api/client'
import DataTable from '../components/DataTable'
import Drawer from '../components/Drawer'
import { PageSpinner, ErrorState, EmptyState } from '../components/Spinner'

function fmtTime(ts) {
  if (!ts) return '—'
  try { return new Date(ts).toLocaleString() } catch { return ts }
}

// ── Severity config ────────────────────────────────────────────────
const SEV_CONFIG = {
  critical: { cls: 'tag-broken',  Icon: XCircle,       color: 'text-red-600',    bg: 'border-red-200 bg-red-50' },
  warning:  { cls: 'tag-warning', Icon: AlertTriangle, color: 'text-amber-600',  bg: 'border-amber-200 bg-amber-50' },
  info:     { cls: 'tag-info',    Icon: Info,          color: 'text-blue-600',   bg: 'border-blue-200 bg-blue-50' },
}

// ── Status config ──────────────────────────────────────────────────
const STATUS_CONFIG = {
  active:       { label: 'Active',       color: 'text-red-600',     bg: 'bg-red-50 text-red-700 border border-red-200',       dot: 'bg-red-500' },
  acknowledged: { label: 'Acknowledged', color: 'text-amber-600',   bg: 'bg-amber-50 text-amber-700 border border-amber-200',   dot: 'bg-amber-500' },
  resolved:     { label: 'Resolved',     color: 'text-ok',       bg: 'bg-ok-bg text-ok border border-ok-border',             dot: 'bg-ok' },
}

const TABS = [
  { id: 'all',          label: 'All' },
  { id: 'active',       label: 'Active' },
  { id: 'acknowledged', label: 'Acknowledged' },
  { id: 'resolved',     label: 'Resolved' },
]

function StatusBadge({ status }) {
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.active
  return (
    <span className={`inline-flex items-center gap-1.5 text-[10px] font-semibold px-2 py-0.5 rounded-full ${cfg.bg}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
      {cfg.label}
    </span>
  )
}

export default function Alerts() {
  const [allAlerts,  setAllAlerts]  = useState([])
  const [activeTab,  setActiveTab]  = useState('all')
  const [sel,        setSel]        = useState(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [loading,    setLoading]    = useState(true)
  const [error,      setError]      = useState(null)
  const [ackLoading, setAckLoading] = useState(false)
  const [verLoading, setVerLoading] = useState(false)
  const [actionMsg,  setActionMsg]  = useState(null)
  const navigate = useNavigate()

  const fetchAlerts = useCallback(() => {
    return getAlerts(500, 'all')
      .then(data => setAllAlerts(Array.isArray(data) ? data : []))
      .catch(e => setError(e.message))
  }, [])

  useEffect(() => {
    fetchAlerts().finally(() => setLoading(false))
    const t = setInterval(fetchAlerts, 15000)
    return () => clearInterval(t)
  }, [fetchAlerts])

  // Keep drawer in sync when alerts refresh
  useEffect(() => {
    if (sel) {
      const updated = allAlerts.find(a => a.alert_id === sel.alert_id)
      if (updated) setSel(updated)
    }
  }, [allAlerts]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Tab filtering ────────────────────────────────────────────────
  const displayed = useMemo(() => {
    if (activeTab === 'all') return allAlerts
    if (activeTab === 'active') return allAlerts.filter(a => a.status === 'active')
    if (activeTab === 'acknowledged') return allAlerts.filter(a => a.status === 'acknowledged')
    if (activeTab === 'resolved') return allAlerts.filter(a => a.status === 'resolved')
    return allAlerts
  }, [allAlerts, activeTab])

  // ── Counts ───────────────────────────────────────────────────────
  const counts = useMemo(() => ({
    active:       allAlerts.filter(a => a.status === 'active').length,
    acknowledged: allAlerts.filter(a => a.status === 'acknowledged').length,
    resolved:     allAlerts.filter(a => a.status === 'resolved').length,
    critical:     allAlerts.filter(a => a.severity === 'critical' && a.status !== 'resolved').length,
    warning:      allAlerts.filter(a => a.severity === 'warning'  && a.status !== 'resolved').length,
    info:         allAlerts.filter(a => a.severity === 'info'     && a.status !== 'resolved').length,
  }), [allAlerts])

  // ── Actions ──────────────────────────────────────────────────────
  const handleAcknowledge = async () => {
    if (!sel) return
    setAckLoading(true)
    setActionMsg(null)
    try {
      await acknowledgeAlert(sel.alert_id)
      setActionMsg({ type: 'success', text: 'Alert acknowledged' })
      await fetchAlerts()
    } catch (e) {
      setActionMsg({ type: 'error', text: e.message })
    } finally {
      setAckLoading(false)
    }
  }

  const handleRunVerification = async () => {
    setVerLoading(true)
    setActionMsg(null)
    try {
      const result = await runVerification()
      const restored = result.chain_state === 'healthy'
      setActionMsg({
        type: restored ? 'success' : 'error',
        text: restored
          ? `✅ Verification passed — chain restored. ${(result.alert_counts?.resolved ?? 0)} alert(s) resolved.`
          : `⚠️ Verification failed — ${result.failures?.length ?? 0} failure(s) detected.`,
      })
      await fetchAlerts()
    } catch (e) {
      setActionMsg({ type: 'error', text: e.message })
    } finally {
      setVerLoading(false)
    }
  }

  // ── Table columns ─────────────────────────────────────────────────
  const columns = [
    {
      key: 'status', label: 'Status',
      render: v => <StatusBadge status={v} />,
    },
    {
      key: 'severity', label: 'Severity',
      render: v => {
        const c = SEV_CONFIG[v]
        return c ? <span className={c.cls}><c.Icon className="w-3 h-3" />{v}</span> : <span>{v}</span>
      },
    },
    { key: 'alert_type',  label: 'Type',    render: v => <span className="text-ink-muted">{v}</span> },
    { key: 'message',     label: 'Message', render: v => <span className="text-ink font-medium truncate block max-w-xs">{v}</span> },
    { key: 'block_index', label: 'Block',   render: v => v != null ? <span className="mono text-accent">#{v}</span> : '—' },
    {
      key: 'occurrence_count', label: 'Seen',
      render: v => v > 1 ? <span className="text-amber-600 font-mono text-xs font-bold">{v}×</span> : <span className="text-ink-faint text-xs">{v ?? 1}</span>,
    },
    { key: 'created_at',  label: 'Created', render: fmtTime },
  ]

  if (loading) return <PageSpinner />
  if (error)   return <ErrorState message={error} />

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="page-title">Alerts</h1>
        <p className="page-subtitle">
          {counts.active} active · {counts.acknowledged} acknowledged · {counts.resolved} resolved
        </p>
        <div className="mt-3 bg-blue-50 border border-blue-200 rounded-xl px-3.5 py-2.5 flex items-center gap-2 text-xs text-blue-700">
          <Info className="w-4 h-4 text-blue-500 flex-shrink-0" />
          <span><strong className="font-semibold text-blue-800">Note:</strong> Active alerts are current unresolved issues; resolved alerts are historical evidence.</span>
        </div>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { key: 'critical', sev: 'critical' },
          { key: 'warning',  sev: 'warning' },
          { key: 'info',     sev: 'info' },
        ].map(({ key, sev }) => {
          const { cls, Icon, color, bg } = SEV_CONFIG[sev]
          const count = counts[key]
          return (
            <div key={sev} className={`card card-hover p-4 border ${count > 0 && sev === 'critical' ? bg : ''}`}>
              <div className="flex items-center gap-2 mb-3">
                <Icon className={`w-4 h-4 ${color}`} />
                <span className="section-header capitalize">{sev} (unresolved)</span>
              </div>
              <p className={`stat-value ${count > 0 ? color : 'text-ink-faint'}`}>{count}</p>
            </div>
          )
        })}
      </div>

      {/* Lifecycle tabs */}
      <div className="flex gap-1 p-1 rounded-xl" style={{ background: 'var(--c-surface-subtle)', border: '1px solid var(--c-line)' }}>
        {TABS.map(tab => {
          const badge = tab.id === 'all' ? allAlerts.length
            : tab.id === 'active' ? counts.active
            : tab.id === 'acknowledged' ? counts.acknowledged
            : counts.resolved
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-sm font-medium transition-all duration-150 ${
                activeTab === tab.id
                  ? 'bg-white text-accent border border-line shadow-xs'
                  : 'text-ink-muted hover:text-ink'
              }`}
            >
              {tab.label}
              <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${
                activeTab === tab.id
                  ? 'bg-accent-faint text-accent'
                  : 'bg-surface-subtle text-ink-faint'
              }`}>
                {badge}
              </span>
            </button>
          )
        })}
      </div>

      {/* Alert table */}
      <div className="card overflow-hidden">
        {displayed.length === 0
          ? <EmptyState icon={Bell} title="No alerts" message="No alerts match the current filter." />
          : (
            <DataTable
              columns={columns}
              rows={displayed}
              keyField="alert_id"
              selectedKey={sel?.alert_id}
              onRowClick={row => { setSel(row); setDrawerOpen(true) }}
            />
          )
        }
      </div>

      {/* Alert triage drawer */}
      <Drawer open={drawerOpen} onClose={() => { setDrawerOpen(false); setActionMsg(null) }} title="Alert Detail">
        {sel && (() => {
          const { cls, Icon } = SEV_CONFIG[sel.severity] ?? {}
          const isResolved = sel.status === 'resolved'
          const isActive = sel.status === 'active'
          return (
            <div className="p-5 space-y-5">
              {/* Header */}
              <div className="flex items-center gap-3 flex-wrap">
                {cls && <span className={cls}><Icon className="w-3 h-3" />{sel.severity}</span>}
                <StatusBadge status={sel.status} />
                <span className="text-sm font-bold text-ink">{sel.alert_type}</span>
                {sel.occurrence_count > 1 && (
                  <span className="text-xs text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-full">
                    Seen {sel.occurrence_count}× times
                  </span>
                )}
              </div>

              {/* Resolved banner */}
              {isResolved && (
                <div className="flex items-center gap-3 rounded-xl p-4" style={{ background: '#ECFDF5', border: '1px solid #A7F3D0' }}>
                  <CheckCircle2 className="w-5 h-5 text-ok flex-shrink-0" />
                  <div>
                    <p className="text-sm font-bold text-ok">Incident Resolved</p>
                    <p className="text-xs text-ink-muted mt-0.5">
                      Resolved {fmtTime(sel.resolved_at)} · by {sel.resolved_by_verification ?? '—'}
                    </p>
                  </div>
                </div>
              )}

              {/* Fields */}
              <div className="space-y-0 divide-y divide-[#F0EFED]">
                {[
                  ['Alert ID',         sel.alert_id],
                  ['Incident Key',     sel.incident_key],
                  ['Message',          sel.message],
                  ['Failure Type',     sel.failure_type],
                  ['Block Index',      sel.block_index != null ? `#${sel.block_index}` : '—'],
                  ['Verification ID',  sel.verification_id],
                  ['Stored Hash',      sel.stored_hash],
                  ['Recomputed Hash',  sel.recomputed_hash],
                  ['Status',           sel.status],
                  ['Occurrence Count', sel.occurrence_count ?? 1],
                  ['Last Seen',        fmtTime(sel.last_seen_at)],
                  ['Created',          fmtTime(sel.created_at ?? sel.timestamp_utc)],
                  ['Acknowledged At',  fmtTime(sel.acknowledged_at)],
                  ['Resolved At',      fmtTime(sel.resolved_at)],
                ].map(([k, v]) => (
                  <div key={k} className="flex items-start justify-between gap-4 py-2.5">
                    <span className="text-xs text-ink-muted flex-shrink-0 pt-0.5 w-32 font-medium">{k}</span>
                    <span className="text-xs text-ink text-right break-all font-mono">{v ?? '—'}</span>
                  </div>
                ))}
              </div>

              {/* Action message */}
              {actionMsg && (
                <div className={`rounded-xl p-3 text-sm ${
                  actionMsg.type === 'success'
                    ? 'bg-ok-bg border border-ok-border text-ok'
                    : 'bg-danger-bg border border-danger-border text-danger'
                }`}>
                  {actionMsg.text}
                </div>
              )}

              {/* Actions */}
              {!isResolved && (
                <div className="border-t border-[#E7E5E4] pt-4 space-y-2">
                  <p className="section-header mb-3">Actions</p>

                  {isActive && (
                    <button
                      className="btn-secondary w-full justify-center"
                      onClick={handleAcknowledge}
                      disabled={ackLoading}
                    >
                      {ackLoading
                        ? <><span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> Acknowledging…</>
                        : <><Eye className="w-4 h-4" /> Acknowledge Alert</>
                      }
                    </button>
                  )}

                  <button
                    className="btn-primary w-full justify-center"
                    onClick={handleRunVerification}
                    disabled={verLoading}
                  >
                    {verLoading
                      ? <><span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> Running verification…</>
                      : <><ShieldCheck className="w-4 h-4" /> Run Verification Now</>
                    }
                  </button>

                  {sel.block_index != null && (
                    <button
                      className="btn-secondary w-full justify-center"
                      onClick={() => { setDrawerOpen(false); navigate(`/ledger?block=${sel.block_index}`) }}
                    >
                      <ExternalLink className="w-4 h-4" /> View Failing Block #{sel.block_index}
                    </button>
                  )}
                </div>
              )}

              {/* Details JSON */}
              {sel.details && (
                <div className="border-t border-[#E7E5E4] pt-4">
                  <p className="section-header mb-2">Raw Details</p>
                  <pre className="bg-[#F5F4F2] border border-[#E7E5E4] rounded-xl p-3 text-xs text-ink-secondary font-mono overflow-x-auto">
                    {JSON.stringify(sel.details, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )
        })()}
      </Drawer>
    </div>
  )
}
