import { useState } from 'react'
import { Copy, Check, Hash, Link2 } from 'lucide-react'
import { ChangeTypeBadge } from './StatusBadge'

export default function BlockInspector({ block }) {
  const [copied, setCopied] = useState(false)

  if (!block) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-ink-faint p-8">
        <div className="w-12 h-12 rounded-2xl flex items-center justify-center" style={{ background: 'var(--c-surface-subtle)', border: '1px solid var(--c-line)' }}>
          <Hash className="w-6 h-6 text-ink-faint" strokeWidth={1.5} />
        </div>
        <p className="text-sm font-medium">Select a block to inspect</p>
        <p className="text-xs text-center text-ink-faint">Click any row in the ledger to view its full block details</p>
      </div>
    )
  }

  const json         = JSON.stringify(block, null, 2)
  const isTampered   = !!block._tampered

  const handleCopy = () => {
    navigator.clipboard.writeText(json)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* ── Header ─────────────────────────────────────── */}
      <div className="flex items-center justify-between px-4 py-3.5 flex-shrink-0" style={{ borderBottom: '1px solid var(--c-line)', background: 'var(--c-surface-warm)' }}>
        <div>
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-lg flex items-center justify-center" style={{ background: 'var(--c-accent-faint)', border: '1px solid rgba(15,118,110,0.18)' }}>
              <span className="text-[10px] font-bold text-accent">#{block.block_index}</span>
            </div>
            <p className="text-sm font-semibold text-ink">Block Detail</p>
          </div>
          <div className="flex items-center gap-2 mt-1">
            <p className="mono truncate max-w-xs">{block.event_type}</p>
            <ChangeTypeBadge
              changeType={block.change_type || (block.log_data && block.log_data.change_type)}
              changeLabel={block.change_label || (block.log_data && block.log_data.change_label)}
            />
          </div>
        </div>
        <button onClick={handleCopy} className="btn-secondary py-1.5 px-3 text-xs">
          {copied
            ? <><Check className="w-3.5 h-3.5 text-ok" /> Copied</>
            : <><Copy className="w-3.5 h-3.5" /> Copy</>
          }
        </button>
      </div>

      {/* ── Tamper indicator ──────────────────────────── */}
      {isTampered && (
        <div className="px-4 py-2.5 bg-red-50 border-b border-red-100 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
          <span className="text-xs font-semibold text-red-700">⚠ Tamper detected on this block</span>
        </div>
      )}

      {/* ── Hash chain ────────────────────────────────── */}
      <div className="px-4 py-3.5 space-y-3 flex-shrink-0" style={{ borderBottom: '1px solid var(--c-line)' }}>
        <div>
          <div className="flex items-center gap-1.5 mb-1">
            <Link2 className="w-3 h-3 text-ink-faint" />
            <p className="section-header">Previous Hash</p>
          </div>
          <p className="mono text-ink-muted truncate px-2.5 py-1.5 rounded-lg" style={{ background: 'var(--c-surface-subtle)', border: '1px solid var(--c-line)' }}>
            {block.previous_hash}
          </p>
        </div>
        <div>
          <div className="flex items-center gap-1.5 mb-1">
            <Hash className="w-3 h-3 text-accent" />
            <p className="section-header">Current Hash</p>
          </div>
          <p className="mono text-accent truncate px-2.5 py-1.5 rounded-lg" style={{ background: 'var(--c-accent-faint)', border: '1px solid rgba(15,118,110,0.18)' }}>
            {block.current_hash}
          </p>
        </div>
      </div>

      {/* ── Full JSON ─────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto p-4" style={{ background: 'var(--c-canvas)' }}>
        <pre className="text-xs text-ink-secondary font-mono leading-relaxed whitespace-pre-wrap break-all">
          {json}
        </pre>
      </div>
    </div>
  )
}
