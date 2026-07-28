import { useEffect, useState, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Database, ChevronLeft, ChevronRight, Hash } from 'lucide-react'
import { getLedger } from '../api/client'
import BlockInspector from '../components/BlockInspector'
import { PageSpinner, ErrorState, EmptyState } from '../components/Spinner'
import { ChangeTypeBadge } from '../components/StatusBadge'

function fmtTime(ts) {
  if (!ts) return '—'
  try { return new Date(ts).toLocaleString() } catch { return ts }
}

const PAGE_SIZE = 20

export default function MicroLedger() {
  const [searchParams] = useSearchParams()
  const [data,    setData]    = useState({ blocks: [], total: 0 })
  const [sel,     setSel]     = useState(null)
  const [offset,  setOffset]  = useState(0)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  const load = useCallback((off) => {
    setLoading(true)
    getLedger(PAGE_SIZE, off)
      .then(d => {
        setData(d)
        const blockParam = searchParams.get('block')
        if (blockParam) {
          const found = d.blocks.find(b => String(b.block_index) === blockParam)
          if (found) setSel(found)
        }
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [searchParams])

  useEffect(() => { load(offset) }, [offset]) // eslint-disable-line react-hooks/exhaustive-deps

  const totalPages  = Math.max(1, Math.ceil(data.total / PAGE_SIZE))
  const currentPage = Math.floor(offset / PAGE_SIZE)

  if (loading && !data.blocks.length) return <PageSpinner />
  if (error)                          return <ErrorState message={error} />

  return (
    <div className="flex h-[calc(100vh-5rem)] gap-0 animate-fade-in -mx-6 -mt-6 mt-0">

      {/* ── Left: block list ─────────────────────────────── */}
      <div
        className="w-80 flex-shrink-0 border-r border-[#E7E5E4] flex flex-col"
        style={{ background: 'var(--c-canvas)' }}
      >
        {/* List header */}
        <div className="px-4 py-4 border-b" style={{ borderColor: 'var(--c-line)', background: 'var(--c-surface)' }}>
          <div className="flex items-center gap-2 mb-0.5">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: 'var(--c-accent-faint)', border: '1px solid rgba(15,118,110,0.18)' }}>
              <Database className="w-3.5 h-3.5 text-accent" />
            </div>
            <h1 className="text-sm font-bold text-ink">Micro-Ledger</h1>
          </div>
          <p className="text-xs text-ink-faint pl-9">
            {data.total} block{data.total !== 1 ? 's' : ''} total
          </p>
        </div>

        {/* Block list */}
        {data.blocks.length === 0
          ? <EmptyState icon={Database} title="Empty ledger" />
          : (
            <div className="flex-1 overflow-y-auto divide-y" style={{ borderColor: 'var(--c-surface-subtle)' }}>
              {data.blocks.map(block => {
                const isSelected = sel?.block_index === block.block_index
                const isGenesis  = block.block_index === 0
                return (
                  <button
                    key={block.block_index}
                    onClick={() => setSel(block)}
                    className={`w-full text-left px-4 py-3.5 border-l-2 transition-all duration-100 ${
                      isSelected
                        ? 'border-l-accent'
                        : isGenesis
                          ? 'border-l-transparent hover:bg-white'
                          : 'border-l-transparent hover:bg-white hover:border-l-accent'
                    }`}
                    style={isSelected ? { background: 'var(--c-accent-faint)' } : {}}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className={`text-xs font-bold ${isSelected ? 'text-accent' : 'text-ink'}`}>
                        #{block.block_index}
                        {isGenesis && <span className="ml-1.5 text-[9px] text-ink-faint normal-case font-medium">genesis</span>}
                      </span>
                      <div className="flex items-center gap-1">
                        <span className="tag-info text-[9px] py-0">{block.event_type}</span>
                        <ChangeTypeBadge
                          changeType={block.change_type || (block.log_data && block.log_data.change_type)}
                          changeLabel={block.change_label || (block.log_data && block.log_data.change_label)}
                        />
                      </div>
                    </div>
                    <p className="mono text-ink-faint truncate text-[10px]">
                      {block.current_hash?.slice(0, 18)}…
                    </p>
                    <p className="text-[10px] text-ink-faint mt-1">{fmtTime(block.timestamp_utc)}</p>
                  </button>
                )
              })}
            </div>
          )
        }

        {/* Pagination */}
        <div className="px-4 py-3 border-t flex items-center justify-between" style={{ borderColor: 'var(--c-line)', background: 'var(--c-surface)' }}>
          <button
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            className="btn-ghost py-1.5 px-2.5 disabled:opacity-30"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span className="text-xs text-ink-muted font-medium">
            {currentPage + 1} / {totalPages}
          </span>
          <button
            disabled={offset + PAGE_SIZE >= data.total}
            onClick={() => setOffset(offset + PAGE_SIZE)}
            className="btn-ghost py-1.5 px-2.5 disabled:opacity-30"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* ── Right: block inspector ────────────────────────── */}
      <div className="flex-1 bg-white overflow-hidden" style={{ borderLeft: '1px solid var(--c-line)' }}>
        <BlockInspector block={sel} />
      </div>
    </div>
  )
}
