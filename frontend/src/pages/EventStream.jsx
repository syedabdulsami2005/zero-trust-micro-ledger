import { useEffect, useState, useMemo } from 'react'
import { Activity, Search, Link as LinkIcon, ArrowUpDown, ArrowDown, ArrowUp } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { getEvents } from '../api/client'
import DataTable from '../components/DataTable'
import Drawer from '../components/Drawer'
import { PageSpinner, ErrorState, EmptyState } from '../components/Spinner'
import { ChangeTypeBadge, CHANGE_LABELS } from '../components/StatusBadge'

function fmtTime(ts) {
  if (!ts) return '—'
  try { return new Date(ts).toLocaleString() } catch { return ts }
}

const CHANGE_TYPES = ['all', 'data_added', 'data_deleted', 'file_created', 'file_deleted', 'content_modified']

export default function EventStream() {
  const [events,      setEvents]     = useState([])
  const [search,      setSearch]     = useState('')
  const [typeFilter,  setTypeFilter] = useState('all')
  const [changeFilter,setChangeFilter] = useState('all')
  const [timeFrom,    setTimeFrom]   = useState('')
  const [timeTo,      setTimeTo]     = useState('')
  const [sortOrder,   setSortOrder]  = useState('desc') // desc = newest first
  const [sel,         setSel]        = useState(null)
  const [drawerOpen,  setDrawerOpen] = useState(false)
  const [loading,     setLoading]    = useState(true)
  const [error,       setError]      = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    getEvents(500)
      .then(data => setEvents(Array.isArray(data) ? data : []))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
    const t = setInterval(() => getEvents(500).then(data => setEvents(Array.isArray(data) ? data : [])).catch(() => {}), 15000)
    return () => clearInterval(t)
  }, [])

  const filtered = useMemo(() => {
    let result = [...events]

    // Sort first (events come newest-first from backend)
    if (sortOrder === 'asc') {
      result = result.reverse()
    }

    return result.filter(ev => {
      if (typeFilter !== 'all' && ev.event_type !== typeFilter) return false
      if (changeFilter !== 'all' && ev.change_type !== changeFilter) return false
      if (timeFrom && (ev.timestamp_utc ?? '') < timeFrom) return false
      if (timeTo   && (ev.timestamp_utc ?? '') > timeTo)   return false
      if (search) {
        const q = search.toLowerCase()
        const badgeLabel = CHANGE_LABELS[ev.change_type]?.label ?? ''
        const fileName = (ev.source_path ?? '').split(/[/\\]/).pop() ?? ''
        return (ev.source_path ?? '').toLowerCase().includes(q)
          || fileName.toLowerCase().includes(q)
          || (ev.source_identifier ?? '').toLowerCase().includes(q)
          || (ev.event_id ?? '').toLowerCase().includes(q)
          || (ev.event_type ?? '').toLowerCase().includes(q)
          || (ev.change_type ?? '').toLowerCase().includes(q)
          || (ev.change_label ?? '').toLowerCase().includes(q)
          || badgeLabel.toLowerCase().includes(q)
      }
      return true
    })
  }, [events, search, typeFilter, changeFilter, timeFrom, timeTo, sortOrder])

  // Collect unique event types from actual data
  const allEventTypes = useMemo(() => {
    const types = new Set(events.map(e => e.event_type).filter(Boolean))
    return ['all', ...types]
  }, [events])

  const columns = [
    {
      key: 'change_type', label: 'Change',
      render: (v, row) => <ChangeTypeBadge changeType={v} changeLabel={row.change_label} />,
    },
    { key: 'event_type',    label: 'Type',        render: v => <span className="tag-accent text-[10px]">{v}</span> },
    {
      key: 'source_path', label: 'Source Path',
      render: v => {
        if (!v) return '—'
        const parts = v.split(/[/\\]/)
        const fileName = parts.pop() || v
        const dirPath = parts.join('/') || ''
        return (
          <div className="max-w-[200px]" title={v}>
            <span className="text-ink font-semibold text-xs block truncate">{fileName}</span>
            {dirPath && <span className="mono text-[10px] text-ink-faint block truncate">{dirPath}</span>}
          </div>
        )
      }
    },
    { key: 'summary',       label: 'Summary',     render: v => <span className="text-ink-muted text-xs truncate block max-w-[200px]">{v}</span> },
    { key: 'timestamp_utc', label: 'Timestamp',   render: fmtTime },
    { key: 'block_index',   label: 'Block',       render: v => <span className="mono text-accent">#{v}</span> },
  ]

  if (loading) return <PageSpinner />
  if (error)   return <ErrorState message={error} />

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="page-title">Event Stream</h1>
        <p className="page-subtitle">{filtered.length} of {events.length} events</p>
      </div>

      {/* Filter ribbon */}
      <div className="card p-4 space-y-3">
        {/* Row 1: Search + sort */}
        <div className="flex items-center gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-faint" />
            <input
              className="input-field pl-9"
              placeholder="Search by file name, path, or change label…"
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>
          <button
            className="btn-secondary py-2 px-3 flex-shrink-0"
            onClick={() => setSortOrder(s => s === 'desc' ? 'asc' : 'desc')}
            title={sortOrder === 'desc' ? 'Newest first (click for oldest first)' : 'Oldest first (click for newest first)'}
          >
            {sortOrder === 'desc' ? <ArrowDown className="w-4 h-4" /> : <ArrowUp className="w-4 h-4" />}
            {sortOrder === 'desc' ? 'Newest first' : 'Oldest first'}
          </button>
        </div>

        {/* Row 2: Event type + Change type */}
        <div className="flex items-center gap-3 flex-wrap">
          <select
            className="select-field flex-1 min-w-36"
            value={typeFilter}
            onChange={e => setTypeFilter(e.target.value)}
          >
            {allEventTypes.map(t => (
              <option key={t} value={t}>{t === 'all' ? 'All event types' : t}</option>
            ))}
          </select>
          <select
            className="select-field flex-1 min-w-36"
            value={changeFilter}
            onChange={e => setChangeFilter(e.target.value)}
          >
            {CHANGE_TYPES.map(t => (
              <option key={t} value={t}>
                {t === 'all' ? 'All change types'
                  : t === 'data_added'       ? 'Data Added'
                  : t === 'data_deleted'     ? 'Data Deleted'
                  : t === 'file_created'     ? 'File Created'
                  : t === 'file_deleted'     ? 'File Deleted'
                  : 'Content Modified'}
              </option>
            ))}
          </select>
        </div>

        {/* Row 3: Time range */}
        <div className="flex items-center gap-3">
          <div className="flex-1">
            <label className="text-xs text-ink-muted mb-1 block">From (UTC)</label>
            <input
              type="datetime-local"
              className="input-field"
              value={timeFrom}
              onChange={e => setTimeFrom(e.target.value ? new Date(e.target.value).toISOString().slice(0,16) : '')}
            />
          </div>
          <div className="text-ink-faint pt-5">→</div>
          <div className="flex-1">
            <label className="text-xs text-ink-muted mb-1 block">To (UTC)</label>
            <input
              type="datetime-local"
              className="input-field"
              value={timeTo}
              onChange={e => setTimeTo(e.target.value ? new Date(e.target.value).toISOString().slice(0,16) : '')}
            />
          </div>
          {(timeFrom || timeTo || search || typeFilter !== 'all' || changeFilter !== 'all') && (
            <button
              className="btn-secondary py-2 px-3 flex-shrink-0 mt-5"
              onClick={() => { setSearch(''); setTypeFilter('all'); setChangeFilter('all'); setTimeFrom(''); setTimeTo('') }}
            >
              Clear
            </button>
          )}
        </div>
      </div>

      <div className="card overflow-hidden">
        {filtered.length === 0
          ? <EmptyState icon={Activity} title="No events match your filter" message="Try changing the search or event type filter." />
          : (
            <DataTable
              columns={columns}
              rows={filtered}
              keyField="event_id"
              selectedKey={sel?.event_id}
              onRowClick={row => { setSel(row); setDrawerOpen(true) }}
            />
          )
        }
      </div>

      {/* Event detail drawer */}
      <Drawer open={drawerOpen} onClose={() => setDrawerOpen(false)} title="Event Detail">
        {sel && (
          <div className="p-5 space-y-4">
            {/* Change type badge */}
            {sel.change_type && (
              <div className="flex items-center gap-2">
                <ChangeTypeBadge changeType={sel.change_type} changeLabel={sel.change_label} />
                <span className="text-sm text-ink-secondary">{sel.change_label}</span>
              </div>
            )}

            <div className="space-y-0 divide-y divide-[#F0EFED]">
              {[
                ['Event ID',        sel.event_id],
                ['Event Type',      sel.event_type],
                ['Change Type',     sel.change_type],
                ['Change Label',    sel.change_label],
                ['Source Path',     sel.source_path],
                ['Source Type',     sel.source_type],
                ['Identifier',      sel.source_identifier],
                ['Summary',         sel.summary],
                ['Timestamp',       fmtTime(sel.timestamp_utc)],
                ['Block Index',     `#${sel.block_index}`],
                ['Sequence',        sel.ingest_sequence],
                ['Previous Hash',   sel.previous_sha256],
                ['Current Hash',    sel.current_sha256],
              ].map(([k, v]) => (
                <div key={k} className="flex items-start justify-between gap-4 py-2.5">
                  <span className="text-xs text-ink-muted flex-shrink-0 pt-0.5 w-28 font-medium">{k}</span>
                  <span className="text-xs text-ink text-right font-mono break-all">{v ?? '—'}</span>
                </div>
              ))}
            </div>
            <div className="border-t border-[#E7E5E4] pt-4">
              <button
                className="btn-secondary w-full justify-center"
                onClick={() => { setDrawerOpen(false); navigate(`/ledger?block=${sel.block_index}`) }}
              >
                <LinkIcon className="w-4 h-4" /> View Block #{sel.block_index}
              </button>
            </div>
          </div>
        )}
      </Drawer>
    </div>
  )
}
