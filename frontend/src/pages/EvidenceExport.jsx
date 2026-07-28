import { useState } from 'react'
import {
  Download, FileJson, ClipboardList, Bell, ShieldCheck,
  FileText, Code, AlertOctagon, Eye, Calendar, Filter
} from 'lucide-react'
import { exportData, getState } from '../api/client'

const EXPORT_TYPES = [
  { value: 'full',         label: 'Full Ledger',          icon: FileJson,     desc: 'All blocks including genesis' },
  { value: 'events',       label: 'Events Only',          icon: ClipboardList, desc: 'Non-genesis event blocks' },
  { value: 'alerts',       label: 'Alerts Only',          icon: Bell,          desc: 'All recorded alert objects' },
  { value: 'verification', label: 'Verification History', icon: ShieldCheck,   desc: 'All verification run results' },
  { value: 'incident',     label: 'Incident Bundle',      icon: AlertOctagon,  desc: 'All data for a specific incident' },
]

const EXPORT_FORMATS = [
  { value: 'json',     label: 'JSON',     icon: Code,      desc: 'Machine-readable (default)', ext: 'json',   mime: 'application/json' },
  { value: 'markdown', label: 'Markdown', icon: FileText,  desc: 'Human-readable report',      ext: 'md',     mime: 'text/plain' },
  { value: 'html',     label: 'HTML',     icon: Eye,       desc: 'Pretty formatted report',    ext: 'html',   mime: 'text/html' },
]

const CHANGE_TYPES = ['data_added', 'data_deleted', 'file_created', 'file_deleted', 'content_modified']

function SectionCard({ title, children }) {
  return (
    <div className="card p-5 space-y-4">
      <p className="text-sm font-semibold text-ink">{title}</p>
      {children}
    </div>
  )
}

export default function EvidenceExport() {
  const [type,        setType]        = useState('full')
  const [format,      setFormat]      = useState('json')
  const [fromIdx,     setFromIdx]     = useState('')
  const [toIdx,       setToIdx]       = useState('')
  const [timeFrom,    setTimeFrom]    = useState('')
  const [timeTo,      setTimeTo]      = useState('')
  const [fileName,    setFileName]    = useState('')
  const [changeType,  setChangeType]  = useState('')
  const [alertId,     setAlertId]     = useState('')
  const [incidentId,  setIncidentId]  = useState('')
  const [result,      setResult]      = useState(null)
  const [loading,     setLoading]     = useState(false)
  const [error,       setError]       = useState(null)
  const [history,     setHistory]     = useState([])

  const handleExport = async () => {
    setLoading(true); setError(null); setResult(null)
    try {
      const opts = { format }
      if (fromIdx)    opts.from_index = parseInt(fromIdx)
      if (toIdx)      opts.to_index   = parseInt(toIdx)
      if (timeFrom)   opts.time_from   = new Date(timeFrom).toISOString()
      if (timeTo)     opts.time_to     = new Date(timeTo).toISOString()
      if (fileName)   opts.file_name   = fileName
      if (changeType) opts.change_type = changeType
      if (alertId)    opts.alert_id    = alertId
      if (incidentId) opts.incident_id = incidentId

      const res = await exportData(type, opts)
      setResult(res)
      setHistory(h => [{ ...res, data: undefined, report: undefined }, ...h.slice(0, 9)])
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleDownload = () => {
    if (!result) return
    const fmt = EXPORT_FORMATS.find(f => f.value === format)
    let content, mime, ext

    if (format === 'json') {
      content = JSON.stringify(result, null, 2)
      mime = 'application/json'
      ext = 'json'
    } else {
      content = result.report ?? JSON.stringify(result, null, 2)
      mime = fmt?.mime ?? 'text/plain'
      ext = fmt?.ext ?? 'txt'
    }

    const blob = new Blob([content], { type: `${mime};charset=utf-8` })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `microledger-export-${result.type}-${Date.now()}.${ext}`
    a.click()
    URL.revokeObjectURL(url)
  }

  const selectedFmt = EXPORT_FORMATS.find(f => f.value === format)

  return (
    <div className="space-y-6 animate-fade-in max-w-4xl">
      <div>
        <h1 className="page-title">Evidence Export</h1>
        <p className="page-subtitle">Generate tamper-evident evidence bundles from the ledger</p>
      </div>

      {/* Export type selector */}
      <SectionCard title="Export Type">
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
          {EXPORT_TYPES.map(({ value, label, icon: Icon, desc }) => (
            <button
              key={value}
              onClick={() => setType(value)}
              className={`flex items-start gap-3 p-4 rounded-xl border text-left transition-all duration-150
                ${type === value
                  ? 'border-ok-border bg-ok-bg'
                  : 'border-line hover:border-accent-light bg-surface-warm'
                }`}
            >
              <Icon className={`w-5 h-5 mt-0.5 flex-shrink-0 ${type === value ? 'text-accent' : 'text-ink-muted'}`} />
              <div>
                <p className={`text-sm font-medium ${type === value ? 'text-ink' : 'text-ink-secondary'}`}>{label}</p>
                <p className="text-xs text-slate-600 mt-0.5">{desc}</p>
              </div>
            </button>
          ))}
        </div>
      </SectionCard>

      {/* Output format selector */}
      <SectionCard title="Output Format">
        <div className="grid grid-cols-3 gap-3">
          {EXPORT_FORMATS.map(({ value, label, icon: Icon, desc }) => (
            <button
              key={value}
              onClick={() => setFormat(value)}
              className={`flex items-start gap-3 p-3 rounded-xl border text-left transition-all duration-150
                ${format === value
                  ? 'border-accent bg-accent-faint'
                  : 'border-line hover:border-line-strong bg-surface-warm'
                }`}
            >
              <Icon className={`w-4 h-4 mt-0.5 flex-shrink-0 ${format === value ? 'text-accent' : 'text-ink-muted'}`} />
              <div>
                <p className={`text-sm font-medium ${format === value ? 'text-ink' : 'text-ink-secondary'}`}>{label}</p>
                <p className="text-xs text-slate-600 mt-0.5">{desc}</p>
              </div>
            </button>
          ))}
        </div>
      </SectionCard>

      {/* Filters */}
      <SectionCard title={<span className="flex items-center gap-2"><Filter className="w-4 h-4 text-ink-muted" /> Filters (Optional)</span>}>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-ink-muted mb-1 block">Incident ID</label>
            <input placeholder="block-7-hash_mismatch" className="input-field"
              value={incidentId} onChange={e => setIncidentId(e.target.value)} />
          </div>
          <div>
            <label className="text-xs text-ink-muted mb-1 block">Alert ID</label>
            <input placeholder="alt-000001" className="input-field"
              value={alertId} onChange={e => setAlertId(e.target.value)} />
          </div>
          <div>
            <label className="text-xs text-ink-muted mb-1 block">File Name</label>
            <input placeholder="test_log.log" className="input-field"
              value={fileName} onChange={e => setFileName(e.target.value)} />
          </div>
          <div>
            <label className="text-xs text-ink-muted mb-1 block">Change Type</label>
            <select className="select-field"
              value={changeType} onChange={e => setChangeType(e.target.value)}>
              <option value="">All change types</option>
              {CHANGE_TYPES.map(ct => <option key={ct} value={ct}>{ct}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-ink-muted mb-1 block flex items-center gap-1"><Calendar className="w-3 h-3" /> From Time (UTC)</label>
            <input type="datetime-local" className="input-field"
              value={timeFrom} onChange={e => setTimeFrom(e.target.value)} />
          </div>
          <div>
            <label className="text-xs text-ink-muted mb-1 block flex items-center gap-1"><Calendar className="w-3 h-3" /> To Time (UTC)</label>
            <input type="datetime-local" className="input-field"
              value={timeTo} onChange={e => setTimeTo(e.target.value)} />
          </div>
          <div>
            <label className="text-xs text-ink-muted mb-1 block">From Block Index</label>
            <input type="number" min="0" placeholder="0 (start)" className="input-field"
              value={fromIdx} onChange={e => setFromIdx(e.target.value)} />
          </div>
          <div>
            <label className="text-xs text-ink-muted mb-1 block">To Block Index</label>
            <input type="number" min="0" placeholder="end" className="input-field"
              value={toIdx} onChange={e => setToIdx(e.target.value)} />
          </div>
        </div>

        <button onClick={handleExport} disabled={loading} className="btn-primary w-full justify-center mt-2">
          {loading
            ? <><span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> Generating…</>
            : <><Download className="w-4 h-4" /> Generate Export</>
          }
        </button>

        {error && <p className="text-sm text-rose-400">{error}</p>}
      </SectionCard>

      {/* Result */}
      {result && (
        <div className="card overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-[#E7E5E4]">
            <div>
              <p className="text-sm font-semibold text-ink">Export Ready</p>
              <p className="text-xs text-ink-muted mt-0.5">
                {result.record_count} record{result.record_count !== 1 ? 's' : ''} · {result.type} · {result.format?.toUpperCase()} · {result.export_id}
              </p>
            </div>
            <button onClick={handleDownload} className="btn-primary py-2">
              <Download className="w-4 h-4" /> Download {selectedFmt?.label}
            </button>
          </div>

          <div className="p-4 max-h-[500px] overflow-y-auto">
            {format === 'markdown' && result.report ? (
              // Markdown preview
              <pre className="text-xs text-ink-secondary font-mono whitespace-pre-wrap leading-relaxed">
                {result.report}
              </pre>
            ) : format === 'html' && result.report ? (
              // HTML preview in iframe-like container
              <div className="bg-slate-950 rounded-lg p-4">
                <p className="text-xs text-ink-muted mb-2">HTML Preview (simplified):</p>
                <pre className="text-xs text-ink-muted font-mono whitespace-pre-wrap overflow-x-auto max-h-96">
                  {result.report?.slice(0, 3000)}{result.report?.length > 3000 ? '\n\n… (download to view full report)' : ''}
                </pre>
              </div>
            ) : (
              // JSON preview
              <pre className="text-xs text-ink-muted font-mono">
                {JSON.stringify(
                  { ...result, data: `[${result.record_count} records — download to view all]`, report: result.report ? '[report included — download to view]' : undefined },
                  null, 2
                )}
              </pre>
            )}
          </div>
        </div>
      )}

      {/* Session history */}
      {history.length > 0 && (
        <div className="card overflow-hidden">
          <div className="px-5 py-4 border-b border-[#E7E5E4]">
            <p className="text-sm font-semibold text-ink">Session History</p>
          </div>
          <div className="divide-y divide-slate-800/50">
            {history.map((h, i) => (
              <div key={i} className="px-5 py-3 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="tag-info text-[10px]">{h.type}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full border ${
                    h.format === 'json'     ? 'bg-[#F5F4F2] text-ink-muted border-[#E7E5E4]'
                    : h.format === 'markdown' ? 'bg-violet-500/10 text-violet-400 border-violet-500/20'
                    : 'bg-blue-500/10 text-blue-400 border-blue-500/20'
                  }`}>{(h.format ?? 'json').toUpperCase()}</span>
                  <span className="text-xs text-ink-muted">{h.record_count} records</span>
                </div>
                <p className="text-xs text-slate-600">{h.exported_at?.slice(0, 19).replace('T', ' ')}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
