import { useEffect, useState } from 'react'
import { Settings as SettingsIcon, Wifi, WifiOff, Play, FileText, CheckCircle, XCircle } from 'lucide-react'
import { getHealth, runVerification, BASE_URL } from '../api/client'

function fmtTime(ts) {
  if (!ts) return '—'
  try { return new Date(ts).toLocaleString() } catch { return ts }
}

function InfoRow({ label, children }) {
  return (
    <div
      className="flex items-center justify-between py-3 last:border-0"
      style={{ borderBottom: '1px solid var(--c-surface-subtle)' }}
    >
      <span className="text-sm text-ink-muted">{label}</span>
      <div className="text-sm text-ink font-medium">{children}</div>
    </div>
  )
}

function SectionCard({ icon: Icon, iconColor = 'text-accent', title, badge, children }) {
  return (
    <div className="card overflow-hidden">
      <div className="panel-header">
        <h2 className="card-title flex items-center gap-2">
          {Icon && <Icon className={`w-4 h-4 ${iconColor}`} strokeWidth={2} />}
          {title}
        </h2>
        {badge}
      </div>
      <div>{children}</div>
    </div>
  )
}

export default function Settings() {
  const [health,     setHealth]       = useState(null)
  const [lastPing,   setLastPing]     = useState(null)
  const [online,     setOnline]       = useState(false)
  const [running,    setRunning]      = useState(false)
  const [runResult,  setRunResult]    = useState(null)
  const [interval,   setIntervalPref] = useState(
    () => localStorage.getItem('refresh_interval') ?? '10'
  )

  const ping = () =>
    getHealth()
      .then(h => { setHealth(h); setOnline(true); setLastPing(new Date()) })
      .catch(() => setOnline(false))

  useEffect(() => { ping(); const t = setInterval(ping, 30000); return () => clearInterval(t) }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleIntervalChange = (v) => {
    setIntervalPref(v)
    localStorage.setItem('refresh_interval', v)
  }

  const handleRunVerification = async () => {
    setRunning(true)
    try {
      const res = await runVerification()
      setRunResult(res)
    } catch (e) {
      setRunResult({ error: e.message })
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="space-y-6 animate-fade-in max-w-2xl">

      {/* ── Header ──────────────────────────────────────── */}
      <div>
        <h1 className="page-title">Settings</h1>
        <p className="page-subtitle">Gateway configuration and system controls</p>
      </div>

      {/* ── Gateway connection ──────────────────────────── */}
      <SectionCard
        icon={online ? Wifi : WifiOff}
        iconColor={online ? 'text-ok' : 'text-danger'}
        title="Gateway Connection"
        badge={
          <span className={`tag text-[10px] ${online ? 'tag-healthy' : 'tag-broken'}`}>
            {online ? 'Connected' : 'Unreachable'}
          </span>
        }
      >
        <div className="px-5 py-1">
          <InfoRow label="API Base URL">
            <span className="mono text-accent">{BASE_URL}</span>
          </InfoRow>
          <InfoRow label="Last Ping">
            {lastPing ? fmtTime(lastPing.toISOString()) : '—'}
          </InfoRow>
          {health && (
            <InfoRow label="Daemon Running">
              <span className={`flex items-center gap-1.5 ${health.daemon_running ? 'text-ok' : 'text-ink-muted'}`}>
                <span className={`w-2 h-2 rounded-full ${health.daemon_running ? 'bg-ok animate-pulse-slow' : 'bg-line-strong'}`} />
                {health.daemon_running ? 'Active' : 'Stopped'}
              </span>
            </InfoRow>
          )}
        </div>
      </SectionCard>

      {/* ── UI Preferences ──────────────────────────────── */}
      <SectionCard title="UI Preferences">
        <div className="px-5 py-4">
          <div className="flex items-center justify-between gap-4">
            <div>
              <label className="text-sm font-semibold text-ink">Auto-refresh interval</label>
              <p className="text-xs text-ink-muted mt-0.5">How often the dashboard polls for updates</p>
            </div>
            <select
              className="select-field w-36"
              value={interval}
              onChange={e => handleIntervalChange(e.target.value)}
            >
              <option value="5">5 seconds</option>
              <option value="10">10 seconds</option>
              <option value="30">30 seconds</option>
              <option value="60">60 seconds</option>
            </select>
          </div>
        </div>
      </SectionCard>

      {/* ── System controls ─────────────────────────────── */}
      <SectionCard icon={Play} title="System Controls">
        <div className="px-5 py-4 space-y-3">
          <div className="flex items-start gap-4">
            <div className="flex-1">
              <p className="text-sm font-semibold text-ink">Run Verification</p>
              <p className="text-xs text-ink-muted mt-0.5">Trigger a full chain integrity verification run</p>
            </div>
            <button onClick={handleRunVerification} disabled={running} className="btn-primary flex-shrink-0">
              {running
                ? <><span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> Running…</>
                : <><Play className="w-4 h-4" /> Run Now</>
              }
            </button>
          </div>
          {runResult && (
            <div
              className={`rounded-xl p-3.5 text-xs font-mono flex items-center gap-2.5 animate-slide-up ${
                runResult.error
                  ? 'border border-danger-border bg-danger-bg text-danger'
                  : 'border border-ok-border bg-ok-bg text-ok'
              }`}
            >
              {runResult.error
                ? <XCircle    className="w-4 h-4 flex-shrink-0" />
                : <CheckCircle className="w-4 h-4 flex-shrink-0" />
              }
              {runResult.error
                ? runResult.error
                : `${runResult.healthy ? '✓ Passed' : '✗ Failed'} · ${runResult.blocks_checked} blocks · ${runResult.verification_id}`
              }
            </div>
          )}
        </div>
      </SectionCard>

      {/* ── Project docs ─────────────────────────────────── */}
      <SectionCard icon={FileText} title="Project Documentation">
        <div className="px-5 py-1">
          {[
            ['PRD.md',          'Product Requirements'],
            ['TRD.md',          'Technical Requirements'],
            ['architecture.md', 'System Architecture'],
            ['design.md',       'UI Design Spec'],
            ['phases.md',       'Build Phases'],
            ['rules.md',        'Development Rules'],
          ].map(([file, label]) => (
            <div
              key={file}
              className="flex items-center justify-between py-3 last:border-0"
              style={{ borderBottom: '1px solid var(--c-surface-subtle)' }}
            >
              <span className="text-sm text-ink font-medium">{label}</span>
              <span className="mono text-ink-faint">{file}</span>
            </div>
          ))}
        </div>
      </SectionCard>

    </div>
  )
}
