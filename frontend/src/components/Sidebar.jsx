import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, FolderOpen, Activity, Database,
  ShieldCheck, Bell, Download, Settings, Shield, Users,
} from 'lucide-react'
import StatusBadge from './StatusBadge'

const NAV_GROUPS = [
  {
    label: 'Monitor',
    items: [
      { to: '/',             icon: LayoutDashboard, label: 'Overview' },
      { to: '/files',        icon: FolderOpen,      label: 'Monitored Files' },
      { to: '/events',       icon: Activity,        label: 'Event Stream' },
      { to: '/ledger',       icon: Database,        label: 'Micro-Ledger' },
    ],
  },
  {
    label: 'Security',
    items: [
      { to: '/verification', icon: ShieldCheck,     label: 'Verification' },
      { to: '/alerts',       icon: Bell,            label: 'Alerts' },
      { to: '/audit',        icon: Users,           label: 'User Audit Log' },
    ],
  },
  {
    label: 'Tools',
    items: [
      { to: '/export',       icon: Download,        label: 'Evidence Export' },
      { to: '/settings',     icon: Settings,        label: 'Settings' },
    ],
  },
]

export default function Sidebar({ state, daemonRunning }) {
  const chainState       = state?.chain_state ?? state?.health_status ?? 'unknown'
  const activeAlertCount = (state?.active_alert_count ?? 0) + (state?.acknowledged_alert_count ?? 0)
  const appendEnabled    = state?.append_enabled ?? !state?.frozen

  return (
    <aside
      className="fixed top-0 left-0 h-full flex flex-col z-30"
      style={{
        width: 'var(--sidebar-w)',
        background: '#FFFFFF',
        borderRight: '1px solid var(--c-line)',
      }}
    >
      {/* ── Logo / Brand ─────────────────────────────────────── */}
      <div className="px-5 py-5" style={{ borderBottom: '1px solid var(--c-line)' }}>
        <div className="flex items-center gap-3">
          <div
            className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0"
            style={{
              background: 'linear-gradient(140deg, #0D9488 0%, #2DD4BF 100%)',
              boxShadow: '0 3px 10px rgba(13,148,136,.30)',
            }}
          >
            <Shield className="w-4 h-4 text-white" strokeWidth={2.5} />
          </div>
          <div>
            <p className="text-sm font-bold text-ink leading-tight" style={{ letterSpacing: '-0.02em' }}>
              MicroLedger
            </p>
            <p className="text-[9.5px] font-semibold tracking-[0.10em] uppercase mt-0.5" style={{ color: 'var(--c-ink-faint)' }}>
              SOC Console
            </p>
          </div>
        </div>
      </div>

      {/* ── Chain Status Widget ───────────────────────────────── */}
      <div className="px-4 pt-3 pb-1">
        <div
          className="rounded-xl px-3.5 py-3"
          style={{
            background: 'linear-gradient(135deg, #F0FDFA 0%, #FEFEFE 100%)',
            border: '1px solid rgba(13,148,136,.14)',
          }}
        >
          <p className="section-header mb-2">Chain Status</p>
          <div className="flex items-center justify-between">
            <StatusBadge status={chainState} />
            <span
              className="text-[9.5px] font-semibold px-2 py-0.5 rounded-full"
              style={{
                background: appendEnabled ? '#ECFDF5' : '#FFFBEB',
                color: appendEnabled ? '#059669' : '#D97706',
              }}
            >
              {appendEnabled ? 'Append ✓' : 'Frozen'}
            </span>
          </div>
        </div>
      </div>

      {/* ── Navigation ───────────────────────────────────────── */}
      <nav className="flex-1 overflow-y-auto py-3 px-3 space-y-4">
        {NAV_GROUPS.map(({ label, items }) => (
          <div key={label}>
            <p className="section-header px-2 mb-1.5">{label}</p>
            {items.map(({ to, icon: Icon, label: itemLabel }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                className={({ isActive }) =>
                  `sidebar-nav-item ${isActive ? 'active' : ''}`
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon
                      className="w-[15px] h-[15px] flex-shrink-0"
                      style={{
                        color: isActive ? 'var(--c-accent)' : 'var(--c-ink-faint)',
                        transition: 'color var(--dur-fast)',
                      }}
                      strokeWidth={isActive ? 2.5 : 2}
                    />
                    <span className="flex-1 leading-none">{itemLabel}</span>
                    {itemLabel === 'Alerts' && activeAlertCount > 0 && (
                      <span
                        className="text-[10px] font-bold px-1.5 py-0.5 rounded-full ml-auto tabular-nums"
                        style={{
                          background: 'rgba(220,38,38,.10)',
                          color: '#DC2626',
                          border: '1px solid rgba(220,38,38,.15)',
                        }}
                      >
                        {activeAlertCount}
                      </span>
                    )}
                  </>
                )}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      {/* ── Daemon Footer ─────────────────────────────────────── */}
      <div
        className="px-4 py-3.5"
        style={{ borderTop: '1px solid var(--c-line)' }}
      >
        <div className="flex items-center gap-2.5">
          {daemonRunning
            ? <span className="live-dot" />
            : <span className="w-2 h-2 rounded-full flex-shrink-0 bg-gray-300" />
          }
          <span className="text-xs font-medium text-ink-muted flex-1">
            {daemonRunning ? 'Daemon active' : 'Daemon stopped'}
          </span>
          <span
            className="text-[9.5px] font-bold px-2 py-0.5 rounded-full"
            style={{
              background: daemonRunning ? '#ECFDF5' : 'var(--c-surface-subtle)',
              color: daemonRunning ? '#059669' : 'var(--c-ink-faint)',
            }}
          >
            {daemonRunning ? 'ON' : 'OFF'}
          </span>
        </div>
      </div>
    </aside>
  )
}
