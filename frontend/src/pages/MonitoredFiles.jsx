import { useEffect, useState } from 'react'
import { FolderOpen, Activity } from 'lucide-react'
import { getFiles, getEvents, getFileContent, writeFile, deleteFile } from '../api/client'
import DataTable from '../components/DataTable'
import Drawer from '../components/Drawer'
import { PageSpinner, ErrorState, EmptyState } from '../components/Spinner'
import { ChangeTypeBadge } from '../components/StatusBadge'

function fmtTime(ts) {
  if (!ts) return '—'
  try { return new Date(ts).toLocaleString() } catch { return ts }
}

function statusTag(v) {
  const s = v || 'monitored'
  if (s === 'modified')              return 'tag-warning'
  if (s === 'missing' || s === 'error') return 'tag-broken'
  return 'tag-healthy'
}

export default function MonitoredFiles() {
  const [files,      setFiles]      = useState([])
  const [events,     setEvents]     = useState([])
  const [sel,        setSel]        = useState(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [loading,    setLoading]    = useState(true)
  const [error,      setError]      = useState(null)
  const [fileContent, setFileContent] = useState('')
  const [contentLoading, setContentLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [newPath, setNewPath] = useState('')
  const [newContent, setNewContent] = useState('')
  const [actionMsg, setActionMsg] = useState(null)

  const load = () => {
    return Promise.all([getFiles(), getEvents(500)])
      .then(([f, ev]) => { setFiles(f); setEvents(ev) })
      .catch(e => setError(e.message))
  }

  useEffect(() => {
    load()
      .finally(() => setLoading(false))
  }, [])

  const handleRowClick = async (row) => {
    setSel(row)
    setDrawerOpen(true)
    setActionMsg(null)
    setContentLoading(true)
    try {
      const relPath = row.source_path.replace(/\\/g, '/').split('/watched/').pop()
      const res = await getFileContent(relPath)
      setFileContent(res?.content ?? '')
    } catch {
      setFileContent('')
    } finally {
      setContentLoading(false)
    }
  }

  const fileEvents = sel
    ? events.filter(ev => ev.source_path === sel.source_path)
    : []

  const selectedRelativePath = sel?.source_path
    ? sel.source_path.replace(/\\/g, '/').split('/watched/').pop()
    : ''

  const handleSaveSelected = async () => {
    if (!selectedRelativePath) return
    setSaving(true)
    setActionMsg(null)
    try {
      await writeFile(selectedRelativePath, fileContent)
      await load()
      setActionMsg({ type: 'success', text: 'File saved successfully' })
    } catch (e) {
      setActionMsg({ type: 'error', text: e.message })
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteSelected = async () => {
    if (!selectedRelativePath) return
    setDeleting(true)
    setActionMsg(null)
    try {
      await deleteFile(selectedRelativePath)
      await load()
      setDrawerOpen(false)
      setSel(null)
      setActionMsg({ type: 'success', text: 'File deleted' })
    } catch (e) {
      setActionMsg({ type: 'error', text: e.message })
    } finally {
      setDeleting(false)
    }
  }

  const handleCreateFile = async () => {
    if (!newPath.trim()) return
    setSaving(true)
    setActionMsg(null)
    try {
      await writeFile(newPath.trim(), newContent)
      setNewPath('')
      setNewContent('')
      await load()
      setActionMsg({ type: 'success', text: 'New watched file created' })
    } catch (e) {
      setActionMsg({ type: 'error', text: e.message })
    } finally {
      setSaving(false)
    }
  }

  const columns = [
    {
      key: 'source_path', label: 'Source Path',
      render: v => <span className="mono text-ink">{v}</span>
    },
    {
      key: 'source_type', label: 'Type',
      render: v => <span className="tag-accent">{v}</span>
    },
    {
      key: 'status', label: 'Status',
      render: v => <span className={statusTag(v)}>{v || 'monitored'}</span>
    },
    {
      key: 'event_count', label: 'Events',
      render: v => <span className="font-bold text-ink tabular-nums">{v}</span>
    },
    { key: 'first_seen_utc', label: 'First Seen', render: fmtTime },
    { key: 'last_seen_utc',  label: 'Last Seen',  render: fmtTime },
  ]

  if (loading) return <PageSpinner />
  if (error)   return <ErrorState message={error} />

  return (
    <div className="space-y-6 animate-fade-in">

      {/* ── Header ───────────────────────────────────────── */}
      <div>
        <h1 className="page-title">Monitored Files</h1>
        <p className="page-subtitle">
          {files.length} unique source{files.length !== 1 ? 's' : ''} observed
        </p>
      </div>

      {/* ── Table card ───────────────────────────────────── */}
      <div className="card overflow-hidden">
        <div className="p-4 border-b border-surface-subtle space-y-2 bg-surface-warm">
          <p className="section-header">Create / Edit Watched File</p>
          <input
            className="input-field"
            placeholder="relative/path/file.txt"
            value={newPath}
            onChange={e => setNewPath(e.target.value)}
          />
          <textarea
            className="input-field min-h-24"
            placeholder="Initial file content"
            value={newContent}
            onChange={e => setNewContent(e.target.value)}
          />
          <button className="btn-primary" disabled={saving || !newPath.trim()} onClick={handleCreateFile}>
            {saving ? 'Saving…' : 'Create File'}
          </button>
        </div>
        <div className="panel-header">
          <h2 className="card-title flex items-center gap-2">
            <FolderOpen className="w-4 h-4 text-accent" />
            File Sources
          </h2>
          <span className="tag-neutral">{files.length} sources</span>
        </div>
        {files.length === 0
          ? <EmptyState
              icon={FolderOpen}
              title="No files recorded"
              message="Events will appear here once the ledger engine captures file activity."
            />
          : <DataTable
              columns={columns}
              rows={files}
              keyField="source_path"
              selectedKey={sel?.source_path}
              onRowClick={handleRowClick}
            />
        }
      </div>

      {/* ── Drawer: file detail ──────────────────────────── */}
      <Drawer open={drawerOpen} onClose={() => setDrawerOpen(false)} title={sel?.source_path ?? ''}>
        {sel && (
          <div className="p-5 space-y-5">

            {/* Metadata rows */}
            <div className="card overflow-hidden">
              <div className="px-4 py-3 border-b" style={{ borderColor: 'var(--c-line)', background: 'var(--c-surface-warm)' }}>
                <p className="section-header">File Details</p>
              </div>
              <div className="px-4 py-1">
                {[
                  ['Status',       <span className={statusTag(sel.status)}>{sel.status || 'monitored'}</span>],
                  ['Source Type',  sel.source_type],
                  ['Identifier',   sel.source_identifier],
                  ['Size (bytes)', sel.size_bytes !== undefined ? sel.size_bytes.toLocaleString() : '—'],
                  ['First Seen',   fmtTime(sel.first_seen_utc)],
                  ['Last Seen',    fmtTime(sel.last_seen_utc)],
                  ['Total Events', <span className="font-bold text-ink">{sel.event_count}</span>],
                ].map(([k, v]) => (
                  <div key={k} className="flex items-start justify-between gap-4 py-3 border-b border-surface-subtle last:border-0">
                    <span className="text-xs text-ink-muted flex-shrink-0 pt-0.5 font-medium">{k}</span>
                    <span className="text-sm text-ink text-right">{v ?? '—'}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Events list */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <p className="section-header">Events ({fileEvents.length})</p>
                <Activity className="w-3.5 h-3.5 text-ink-faint" />
              </div>
              {fileEvents.length === 0
                ? <p className="text-ink-muted text-sm">No events found for this file</p>
                : (
                  <div className="space-y-2 max-h-96 overflow-y-auto">
                    {fileEvents.map(ev => (
                      <div
                        key={ev.event_id ?? ev.block_index}
                        className="rounded-xl p-3.5"
                        style={{ background: 'var(--c-accent-faint)', border: '1px solid rgba(15,118,110,0.18)' }}
                      >
                        <div className="flex items-center justify-between mb-1.5">
                          <div className="flex items-center gap-1.5">
                            <span className="tag-accent text-[10px]">{ev.event_type}</span>
                            <ChangeTypeBadge changeType={ev.change_type} changeLabel={ev.change_label} />
                          </div>
                          <span className="mono text-ink-faint">#{ev.block_index}</span>
                        </div>
                        <p className="text-xs text-ink-muted">{fmtTime(ev.timestamp_utc)}</p>
                      </div>
                    ))}
                  </div>
                )
              }
            </div>

            {/* Manual editor */}
            <div className="border-t border-surface-subtle pt-4 space-y-3">
              <p className="section-header">Manual Edit</p>
              <textarea
                className="input-field min-h-36 mono"
                value={fileContent}
                onChange={e => setFileContent(e.target.value)}
                disabled={contentLoading}
              />
              <div className="flex gap-2">
                <button className="btn-primary" onClick={handleSaveSelected} disabled={saving || contentLoading}>
                  {saving ? 'Saving…' : 'Save File'}
                </button>
                <button className="btn-secondary" onClick={handleDeleteSelected} disabled={deleting || contentLoading}>
                  {deleting ? 'Deleting…' : 'Delete File'}
                </button>
              </div>
              {actionMsg && (
                <p className={`text-xs ${actionMsg.type === 'success' ? 'text-ok' : 'text-danger'}`}>
                  {actionMsg.text}
                </p>
              )}
            </div>
          </div>
        )}
      </Drawer>
    </div>
  )
}
