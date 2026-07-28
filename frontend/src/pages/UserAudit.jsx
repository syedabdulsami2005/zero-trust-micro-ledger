import { useEffect, useState } from 'react'
import {
  Users, Activity, CheckCircle2, Clock,
  Search, LogIn, LogOut, UserCheck, Zap,
  RefreshCw, Layers, ChevronRight, FileText, AlertCircle
} from 'lucide-react'
import { getAuditActivity, loginUser, logoutUser } from '../api/client'
import { Spinner } from '../components/Spinner'

export default function UserAudit() {
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('timeline') // 'timeline' | 'sessions'
  const [search, setSearch] = useState('')
  const [filterType, setFilterType] = useState('all')
  const [selectedSessionId, setSelectedSessionId] = useState(null)

  // Login Simulator State
  const [activeSession, setActiveSession] = useState(null)
  const [authLoading, setAuthLoading] = useState(false)
  const [simUsername, setSimUsername] = useState('admin')
  const [simRole, setSimRole] = useState('system_administrator')

  const fetchActivity = async () => {
    try {
      setError(null)
      const res = await getAuditActivity()
      const data = res.activity ?? []
      setEntries(data)
      if (data.length > 0) {
        const latestLogin = data.find(e => e.action_type === 'LOGIN')
        if (latestLogin) {
          const hasLogout = data.some(e => e.session_id === latestLogin.session_id && e.action_type === 'LOGOUT')
          if (!hasLogout) {
            setActiveSession(latestLogin)
          } else {
            setActiveSession(null)
          }
        }
      }
    } catch (err) {
      setError(err.message || 'Failed to load user audit logs')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchActivity()
    const interval = setInterval(fetchActivity, 5000)
    return () => clearInterval(interval)
  }, [])

  const handleSimulatedLogin = async (e) => {
    e.preventDefault()
    setAuthLoading(true)
    try {
      const res = await loginUser(simUsername, simRole)
      if (res.session) setActiveSession(res.session)
      await fetchActivity()
    } catch (err) {
      alert(`Login error: ${err.message}`)
    } finally {
      setAuthLoading(false)
    }
  }

  const handleSimulatedLogout = async () => {
    if (!activeSession) return
    setAuthLoading(true)
    try {
      await logoutUser(activeSession.session_id, activeSession.user)
      setActiveSession(null)
      await fetchActivity()
    } catch (err) {
      alert(`Logout error: ${err.message}`)
    } finally {
      setAuthLoading(false)
    }
  }

  const filteredEntries = entries.filter((item) => {
    if (selectedSessionId && item.session_id !== selectedSessionId) return false
    if (filterType !== 'all') {
      if (filterType === 'auth' && !['LOGIN', 'LOGOUT'].includes(item.action_type)) return false
      if (filterType === 'actions' && ['LOGIN', 'LOGOUT'].includes(item.action_type)) return false
    }
    if (!search.trim()) return true
    const q = search.toLowerCase()
    return (
      (item.user || '').toLowerCase().includes(q) ||
      (item.action_type || '').toLowerCase().includes(q) ||
      (item.details || '').toLowerCase().includes(q) ||
      (item.session_id || '').toLowerCase().includes(q)
    )
  })

  const sessionGroups = () => {
    const map = {}
    entries.forEach((e) => {
      const sid = e.session_id || 'unknown'
      if (!map[sid]) {
        map[sid] = {
          session_id: sid,
          user: e.user || 'admin',
          role: e.role || 'operator',
          login_time: null,
          logout_time: null,
          duration: null,
          actions_count: 0,
          events: [],
        }
      }
      map[sid].events.push(e)
      if (e.action_type === 'LOGIN') {
        map[sid].login_time = e.timestamp_utc
        if (e.role) map[sid].role = e.role
      } else if (e.action_type === 'LOGOUT') {
        map[sid].logout_time = e.timestamp_utc
        if (e.duration_seconds !== undefined) map[sid].duration = e.duration_seconds
      } else {
        map[sid].actions_count += 1
      }
    })
    return Object.values(map).sort((a, b) => (b.login_time || '').localeCompare(a.login_time || ''))
  }

  const getBadgeStyle = (actionType) => {
    switch (actionType) {
      case 'LOGIN':           return 'bg-ok-bg text-ok border-ok-border'
      case 'LOGOUT':          return 'bg-rose-50 text-rose-700 border-rose-200'
      case 'RUN_VERIFICATION':return 'bg-accent-faint text-accent border-[rgba(15,118,110,0.20)]'
      case 'RESTORE_CHECKPOINT': return 'bg-purple-50 text-purple-700 border-purple-200'
      case 'ACKNOWLEDGE_ALERT':  return 'bg-warn-bg text-warn border-warn-border'
      case 'EXPORT_DATA':        return 'bg-info-bg text-info border-info-border'
      default:                   return 'bg-surface-subtle text-ink-secondary border-line'
    }
  }

  const totalLogins  = entries.filter(e => e.action_type === 'LOGIN').length
  const totalActions = entries.filter(e => !['LOGIN', 'LOGOUT'].includes(e.action_type)).length
  const uniqueSessions = new Set(entries.map(e => e.session_id)).size

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12 animate-fade-in">

      {/* ── Header ──────────────────────────────────────────── */}
      <div className="card p-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-6"
        style={{ background: 'linear-gradient(135deg, #F0FDFA 0%, #FDFCFA 60%, #F7F6F4 100%)', borderColor: 'rgba(15,118,110,0.18)' }}>
        <div className="space-y-2">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-accent-faint border text-accent" style={{ borderColor: 'rgba(15,118,110,0.20)' }}>
              <Users className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-ink tracking-tight">User Activity &amp; Session Audit</h1>
              <p className="text-xs text-ink-muted flex items-center gap-1.5 mt-0.5">
                <span className="w-2 h-2 rounded-full bg-ok animate-pulse-slow"></span>
                Isolated in <code className="text-accent font-mono">data/audit/user_activity.jsonl</code> — Zero ledger bloat, 100% accountability.
              </p>
            </div>
          </div>
        </div>

        {/* Active Session Simulator Panel */}
        <div className="bg-surface-subtle border border-line rounded-xl p-4 flex flex-col sm:flex-row items-center gap-4 w-full md:w-auto">
          {activeSession ? (
            <div className="flex items-center justify-between gap-4 w-full">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-full bg-ok-bg border border-ok-border flex items-center justify-center text-ok font-bold text-sm">
                  {activeSession.user ? activeSession.user[0].toUpperCase() : 'U'}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-ink">{activeSession.user}</span>
                    <span className="text-[10px] bg-ok-bg text-ok px-1.5 py-0.5 rounded font-mono border border-ok-border">
                      ACTIVE SESSION
                    </span>
                  </div>
                  <p className="text-[11px] text-ink-muted font-mono mt-0.5">
                    ID: {activeSession.session_id}
                  </p>
                </div>
              </div>
              <button
                onClick={handleSimulatedLogout}
                disabled={authLoading}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-danger-bg hover:bg-red-100 text-danger border border-danger-border text-xs font-medium transition-all duration-150"
              >
                <LogOut className="w-3.5 h-3.5" />
                <span>Log Out</span>
              </button>
            </div>
          ) : (
            <form onSubmit={handleSimulatedLogin} className="flex flex-wrap sm:flex-nowrap items-center gap-2 w-full">
              <input
                type="text"
                placeholder="Username (e.g. admin)"
                value={simUsername}
                onChange={(e) => setSimUsername(e.target.value)}
                className="input-field w-28 sm:w-32"
                required
              />
              <select
                value={simRole}
                onChange={(e) => setSimRole(e.target.value)}
                className="select-field"
              >
                <option value="system_administrator">System Admin</option>
                <option value="security_auditor">Security Auditor</option>
                <option value="soc_operator">SOC Operator</option>
              </select>
              <button
                type="submit"
                disabled={authLoading}
                className="btn-primary whitespace-nowrap"
              >
                <LogIn className="w-3.5 h-3.5" />
                <span>Start Session</span>
              </button>
            </form>
          )}
        </div>
      </div>

      {/* ── KPI Cards ───────────────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card card-hover p-4 flex items-center justify-between">
          <div>
            <p className="section-header">Total Sessions</p>
            <p className="text-2xl font-bold text-ink mt-1 font-mono">{uniqueSessions}</p>
          </div>
          <div className="p-3 rounded-xl bg-accent-faint border text-accent" style={{ borderColor: 'rgba(15,118,110,0.20)' }}>
            <UserCheck className="w-5 h-5" />
          </div>
        </div>

        <div className="card card-hover p-4 flex items-center justify-between">
          <div>
            <p className="section-header">Logins Recorded</p>
            <p className="text-2xl font-bold text-ok mt-1 font-mono">{totalLogins}</p>
          </div>
          <div className="p-3 rounded-xl bg-ok-bg border border-ok-border text-ok">
            <LogIn className="w-5 h-5" />
          </div>
        </div>

        <div className="card card-hover p-4 flex items-center justify-between">
          <div>
            <p className="section-header">Admin Actions Tracked</p>
            <p className="text-2xl font-bold text-ink mt-1 font-mono">{totalActions}</p>
          </div>
          <div className="p-3 rounded-xl bg-purple-50 border border-purple-200 text-purple-700">
            <Activity className="w-5 h-5" />
          </div>
        </div>

        <div className="card card-hover p-4 flex items-center justify-between">
          <div>
            <p className="section-header">Storage Isolation</p>
            <p className="text-sm font-semibold text-accent mt-1 flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4 text-ok inline" />
              Outside Watched Dir
            </p>
          </div>
          <div className="p-3 rounded-xl bg-info-bg border border-info-border text-info">
            <Layers className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* ── Tabs & Search Controls ──────────────────────────── */}
      <div className="card p-4 flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-1 p-1 rounded-xl w-full md:w-auto" style={{ background: 'var(--c-surface-subtle)', border: '1px solid var(--c-line)' }}>
          <button
            onClick={() => { setActiveTab('timeline'); setSelectedSessionId(null) }}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all duration-150 ${
              activeTab === 'timeline'
                ? 'bg-white text-accent border border-line shadow-xs'
                : 'text-ink-muted hover:text-ink'
            }`}
          >
            <Activity className="w-3.5 h-3.5" />
            <span>Action Timeline</span>
          </button>
          <button
            onClick={() => setActiveTab('sessions')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all duration-150 ${
              activeTab === 'sessions'
                ? 'bg-white text-accent border border-line shadow-xs'
                : 'text-ink-muted hover:text-ink'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            <span>Sessions History ({sessionGroups().length})</span>
          </button>
        </div>

        {activeTab === 'timeline' && (
          <div className="flex flex-wrap sm:flex-nowrap items-center gap-3 w-full md:w-auto">
            {selectedSessionId && (
              <div className="flex items-center gap-2 bg-purple-50 border border-purple-200 text-purple-700 text-xs px-3 py-1.5 rounded-lg font-mono">
                <span>Filter: {selectedSessionId}</span>
                <button
                  onClick={() => setSelectedSessionId(null)}
                  className="hover:text-ink font-bold ml-1"
                >×</button>
              </div>
            )}
            <div className="relative flex-1 sm:w-64">
              <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" />
              <input
                type="text"
                placeholder="Search user, action, details..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full input-field pl-9"
              />
            </div>
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="select-field"
            >
              <option value="all">All Event Types</option>
              <option value="auth">Logins / Logouts Only</option>
              <option value="actions">Admin Actions Only</option>
            </select>
            <button
              onClick={fetchActivity}
              className="btn-icon"
              title="Refresh Logs"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
      </div>

      {/* ── Content Area ────────────────────────────────────── */}
      {loading ? (
        <div className="py-20 flex justify-center">
          <Spinner />
        </div>
      ) : error ? (
        <div className="card p-6 flex items-center gap-3" style={{ borderColor: 'var(--c-danger-border)', background: 'var(--c-danger-bg)' }}>
          <AlertCircle className="w-5 h-5 text-danger flex-shrink-0" />
          <span className="text-danger text-sm">{error}</span>
        </div>
      ) : activeTab === 'timeline' ? (
        /* TIMELINE VIEW */
        filteredEntries.length === 0 ? (
          <div className="card p-12 text-center text-ink-muted">
            <FileText className="w-10 h-10 mx-auto text-ink-faint mb-3" />
            <p className="font-medium text-ink-secondary">No matching audit events recorded</p>
            <p className="text-xs text-ink-muted mt-1">
              Start a session above or trigger manual verifications to record real-time administrative actions.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredEntries.map((item, idx) => (
              <div
                key={item.event_id || idx}
                className="card card-hover p-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-4"
              >
                <div className="flex items-start gap-4 flex-1">
                  <div className="mt-1">
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold border ${getBadgeStyle(item.action_type)}`}>
                      {item.action_type === 'LOGIN' && <LogIn className="w-3.5 h-3.5" />}
                      {item.action_type === 'LOGOUT' && <LogOut className="w-3.5 h-3.5" />}
                      {item.action_type === 'RUN_VERIFICATION' && <CheckCircle2 className="w-3.5 h-3.5" />}
                      {item.action_type === 'RESTORE_CHECKPOINT' && <RefreshCw className="w-3.5 h-3.5" />}
                      {item.action_type}
                    </span>
                  </div>

                  <div className="space-y-1 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-semibold text-ink">
                        {item.user || 'system'}
                      </span>
                      {item.role && (
                        <span className="text-[10px] text-ink-muted bg-surface-subtle px-2 py-0.5 rounded border border-line font-mono">
                          {item.role}
                        </span>
                      )}
                      <span className="text-ink-faint">•</span>
                      <button
                        onClick={() => setSelectedSessionId(item.session_id)}
                        className="text-xs text-accent hover:underline font-mono underline-offset-2"
                        title="Click to filter by this Session ID"
                      >
                        {item.session_id}
                      </button>
                    </div>

                    <p className="text-xs text-ink-secondary leading-relaxed">
                      {item.details || 'Action completed successfully.'}
                    </p>

                    {item.ip_address && (
                      <p className="text-[10px] text-ink-muted font-mono">
                        Source IP: {item.ip_address}
                      </p>
                    )}
                  </div>
                </div>

                <div className="text-right flex flex-col md:items-end justify-between self-stretch md:self-auto">
                  <span className="text-xs text-ink-muted font-mono flex items-center gap-1">
                    <Clock className="w-3 h-3 text-ink-muted" />
                    {item.timestamp_utc ? new Date(item.timestamp_utc).toLocaleTimeString() : '—'}
                  </span>
                  <span className="text-[10px] text-ink-muted font-mono mt-1">
                    {item.timestamp_utc ? new Date(item.timestamp_utc).toLocaleDateString() : ''}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )
      ) : (
        /* SESSIONS VIEW */
        <div className="card overflow-hidden">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr style={{ background: 'var(--c-surface-warm)', borderBottom: '1px solid var(--c-line)' }} className="text-[11px] font-semibold text-ink-muted uppercase tracking-wider">
                <th className="py-3.5 px-4">Session ID</th>
                <th className="py-3.5 px-4">User &amp; Role</th>
                <th className="py-3.5 px-4">Login Timestamp</th>
                <th className="py-3.5 px-4">Status &amp; Duration</th>
                <th className="py-3.5 px-4">Actions Performed</th>
                <th className="py-3.5 px-4 text-right">Inspect</th>
              </tr>
            </thead>
            <tbody className="text-xs">
              {sessionGroups().length === 0 ? (
                <tr>
                  <td colSpan="6" className="py-8 text-center text-ink-muted">
                    No sessions found.
                  </td>
                </tr>
              ) : (
                sessionGroups().map((group) => {
                  const isActive = !group.logout_time
                  return (
                    <tr
                      key={group.session_id}
                      style={{ borderBottom: '1px solid var(--c-surface-subtle)' }}
                      onMouseEnter={e => e.currentTarget.style.background = 'var(--c-surface-warm)'}
                      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                    >
                      <td className="py-3.5 px-4 font-mono text-accent font-medium">
                        {group.session_id}
                      </td>
                      <td className="py-3.5 px-4">
                        <div className="font-semibold text-ink">{group.user}</div>
                        <div className="text-[10px] text-ink-muted font-mono">{group.role}</div>
                      </td>
                      <td className="py-3.5 px-4 font-mono text-ink-secondary">
                        {group.login_time ? new Date(group.login_time).toLocaleString() : 'Unknown'}
                      </td>
                      <td className="py-3.5 px-4">
                        {isActive ? (
                          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-ok-bg text-ok border border-ok-border">
                            <span className="w-1.5 h-1.5 rounded-full bg-ok animate-pulse-slow"></span>
                            Active Now
                          </span>
                        ) : (
                          <div>
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-surface-subtle text-ink-muted border border-line">
                              Logged Out
                            </span>
                            {group.duration !== null && (
                              <div className="text-[10px] text-ink-muted font-mono mt-0.5">
                                Duration: {group.duration}s
                              </div>
                            )}
                          </div>
                        )}
                      </td>
                      <td className="py-3.5 px-4">
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-purple-50 text-purple-700 border border-purple-200 font-mono font-medium">
                          {group.actions_count} action(s)
                        </span>
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <button
                          onClick={() => {
                            setSelectedSessionId(group.session_id)
                            setActiveTab('timeline')
                          }}
                          className="btn-secondary text-xs px-3 py-1 inline-flex items-center gap-1"
                        >
                          <span>View Timeline</span>
                          <ChevronRight className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
