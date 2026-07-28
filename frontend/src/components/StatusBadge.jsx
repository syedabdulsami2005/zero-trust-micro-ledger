import { CheckCircle, AlertTriangle, XCircle, HelpCircle } from 'lucide-react'

const CONFIG = {
  healthy:  { cls: 'tag-healthy',  Icon: CheckCircle,   label: 'Healthy' },
  degraded: { cls: 'tag-warning',  Icon: AlertTriangle, label: 'Degraded' },
  broken:   { cls: 'tag-broken',   Icon: XCircle,       label: 'Broken', pulse: true },
  unknown:  { cls: 'tag-info',     Icon: HelpCircle,    label: 'Unknown' },
}

export default function StatusBadge({ status, size = 'sm' }) {
  const cfg = CONFIG[status] ?? CONFIG.unknown
  const { cls, Icon, label, pulse } = cfg

  return (
    <span className={`${cls} ${pulse ? 'animate-pulse' : ''}`}>
      <Icon className={size === 'lg' ? 'w-3.5 h-3.5' : 'w-3 h-3'} />
      {label}
    </span>
  )
}

export const CHANGE_LABELS = {
  data_added:       { label: 'Data Added',   cls: 'bg-ok-bg text-ok border border-ok-border' },
  data_deleted:     { label: 'Data Deleted', cls: 'bg-danger-bg text-danger border border-danger-border' },
  file_created:     { label: 'New File',     cls: 'bg-info-bg text-info border border-info-border' },
  file_deleted:     { label: 'File Deleted', cls: 'bg-danger-bg text-danger border border-danger-border' },
  content_modified: { label: 'Modified',     cls: 'bg-warn-bg text-warn border border-warn-border' },
}

export function ChangeTypeBadge({ changeType, changeLabel }) {
  const cfg = CHANGE_LABELS[changeType]
  if (!cfg && !changeLabel) return null
  return (
    <span
      className={`inline-flex text-[10px] font-semibold px-2 py-0.5 rounded-full leading-none ${
        cfg ? cfg.cls : 'bg-surface-subtle text-ink-muted border border-line'
      }`}
    >
      {cfg ? cfg.label : changeLabel}
    </span>
  )
}
