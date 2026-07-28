import { useEffect, useState } from 'react'
import { ShieldCheck, Play, CheckCircle, XCircle, TrendingUp, AlertTriangle } from 'lucide-react'
import { getVerification, runVerification } from '../api/client'
import DataTable from '../components/DataTable'
import { PageSpinner, ErrorState, EmptyState } from '../components/Spinner'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts'

function fmtTime(ts) {
  if (!ts) return '—'
  try { return new Date(ts).toLocaleString() } catch { return ts }
}

function fmtShort(ts) {
  if (!ts) return ''
  try { return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) } catch { return '' }
}

/* Light-theme chart tooltip */
const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-[#E7E5E4] rounded-xl px-3 py-2.5 text-xs shadow-card-md">
      <p className="text-ink-muted mb-1 font-medium">{label}</p>
      <p className={`font-bold ${payload[0].value === 1 ? 'text-ok' : 'text-danger'}`}>
        {payload[0].value === 1 ? '✓ Pass' : '✗ Fail'}
      </p>
      {payload[1] && <p className="text-ink-faint mt-0.5">Blocks: {payload[1].value}</p>}
    </div>
  )
}

export default function Verification() {
  const [history,    setHistory]    = useState([])
  const [loading,    setLoading]    = useState(true)
  const [error,      setError]      = useState(null)
  const [running,    setRunning]    = useState(false)
  const [lastResult, setLastResult] = useState(null)

  const load = () =>
    getVerification(50)
      .then(h => setHistory([...h].reverse()))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))

  useEffect(() => { load() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleRun = async () => {
    setRunning(true)
    try {
      const result = await runVerification()
      setLastResult(result)
      await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setRunning(false)
    }
  }

  const chartData = history.map((r, i) => ({
    name:    fmtShort(r.timestamp_utc) || `#${i + 1}`,
    healthy: r.healthy ? 1 : 0,
    blocks:  r.blocks_checked,
  }))

  const latest    = history[history.length - 1]
  const passCount = history.filter(r => r.healthy).length
  const failCount = history.length - passCount

  const columns = [
    { key: 'verification_id', label: 'ID',           render: v => <span className="mono text-accent">{v}</span> },
    { key: 'timestamp_utc',   label: 'Timestamp',    render: fmtTime },
    {
      key: 'healthy', label: 'Result',
      render: v => v
        ? <span className="tag-healthy"><CheckCircle className="w-3 h-3" /> Pass</span>
        : <span className="tag-broken"><XCircle className="w-3 h-3" /> Fail</span>
    },
    { key: 'blocks_checked',     label: 'Blocks',       render: v => <span className="tabular-nums font-medium text-ink">{v}</span> },
    {
      key: 'first_invalid_index', label: 'First Invalid',
      render: v => v != null ? <span className="text-red-600 mono font-bold">#{v}</span> : <span className="text-ink-faint">—</span>
    },
    { key: 'duration_ms', label: 'Duration', render: v => v != null ? <span className="mono">{v} ms</span> : '—' },
  ]

  if (loading) return <PageSpinner />
  if (error)   return <ErrorState message={error} />

  return (
    <div className="space-y-6 animate-fade-in">

      {/* ── Header ───────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="page-title">Verification</h1>
          <p className="page-subtitle">Chain integrity verification history and controls</p>
        </div>
        <button
          onClick={handleRun}
          disabled={running}
          className="btn-primary"
        >
          {running
            ? <><span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> Running…</>
            : <><Play className="w-4 h-4" /> Run Verification</>
          }
        </button>
      </div>

      {/* ── Last result flash ─────────────────────────────── */}
      {lastResult && (
        <div
          className={`card p-4 flex items-center gap-4 animate-slide-up ${
            lastResult.healthy
              ? 'border-ok-border'
              : 'border-danger-border'
          }`}
          style={{ background: lastResult.healthy ? '#ECFDF5' : '#FFF1F2' }}
        >
          <div
            className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0`}
            style={{ background: lastResult.healthy ? '#D1FAE5' : '#FEE2E2' }}
          >
            {lastResult.healthy
              ? <CheckCircle className="w-5 h-5 text-ok" />
              : <XCircle    className="w-5 h-5 text-danger" />
            }
          </div>
          <div>
            <p className={`text-sm font-bold ${lastResult.healthy ? 'text-ok' : 'text-danger'}`}>
              {lastResult.healthy ? 'Verification passed successfully' : 'Verification FAILED — tamper detected'}
            </p>
            <p className="text-xs text-ink-muted mt-0.5">
              {lastResult.blocks_checked} blocks · {lastResult.duration_ms} ms · <span className="mono">{lastResult.verification_id}</span>
            </p>
          </div>
        </div>
      )}

      {/* ── Stats row ─────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 stagger">
        {[
          { label: 'Total Runs',   value: history.length,  icon: TrendingUp,  iconBg: 'bg-accent-faint', iconColor: 'text-accent' },
          { label: 'Passed',       value: passCount,        icon: CheckCircle, iconBg: 'bg-ok-bg',       iconColor: 'text-ok' },
          { label: 'Failed',       value: failCount,        icon: XCircle,     iconBg: failCount > 0 ? 'bg-danger-bg' : 'bg-surface-subtle', iconColor: failCount > 0 ? 'text-danger' : 'text-ink-faint' },
          { label: 'Last Checked', value: latest?.blocks_checked ?? 0, icon: ShieldCheck, iconBg: 'bg-accent-faint', iconColor: 'text-accent' },
        ].map(({ label, value, icon: Icon, iconBg, iconColor }) => (
          <div key={label} className="card card-hover p-5">
            <div className="flex items-start justify-between mb-3">
              <p className="section-header">{label}</p>
              <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${iconBg}`}>
                <Icon className={`w-4 h-4 ${iconColor}`} strokeWidth={2} />
              </div>
            </div>
            <p className="stat-value">{value}</p>
          </div>
        ))}
      </div>

      {/* ── Chart ────────────────────────────────────────── */}
      {chartData.length > 1 && (
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <p className="card-title">Health History</p>
            <span className="tag-accent text-[10px]">{history.length} runs</span>
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="healthGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#059669" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#059669" stopOpacity={0}    />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#F0EFED" />
              <XAxis
                dataKey="name"
                tick={{ fill: '#A8A29E', fontSize: 10, fontFamily: 'Inter' }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                domain={[0, 1]}
                ticks={[0, 1]}
                tick={{ fill: '#A8A29E', fontSize: 10, fontFamily: 'Inter' }}
                tickFormatter={v => v ? 'Pass' : 'Fail'}
                axisLine={false}
                tickLine={false}
                width={32}
              />
              <Tooltip content={<CustomTooltip />} />
              <Area
                type="step"
                dataKey="healthy"
                stroke="#059669"
                fill="url(#healthGrad)"
                strokeWidth={2.5}
                dot={false}
                activeDot={{ r: 4, fill: '#059669', stroke: '#fff', strokeWidth: 2 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* ── History table ────────────────────────────────── */}
      <div className="card overflow-hidden">
        <div className="panel-header">
          <h2 className="card-title flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-accent" />
            Verification Log
          </h2>
          <span className="tag-neutral">{history.length} entries</span>
        </div>
        {history.length === 0
          ? <EmptyState icon={ShieldCheck} title="No verification runs yet" message='Click "Run Verification" to start verifying chain integrity.' />
          : <DataTable columns={columns} rows={[...history].reverse()} keyField="verification_id" />
        }
      </div>
    </div>
  )
}
