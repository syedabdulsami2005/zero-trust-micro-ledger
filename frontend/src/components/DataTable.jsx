import { useState, useMemo } from 'react'
import { ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react'

export default function DataTable({
  columns,
  rows,
  onRowClick,
  selectedKey,
  keyField     = 'id',
  emptyMessage = 'No data available',
}) {
  const [sortCol, setSortCol] = useState(null)
  const [sortDir, setSortDir] = useState('asc')

  const sorted = useMemo(() => {
    if (!sortCol) return rows
    return [...rows].sort((a, b) => {
      const av = a[sortCol] ?? ''
      const bv = b[sortCol] ?? ''
      const cmp = String(av).localeCompare(String(bv), undefined, { numeric: true })
      return sortDir === 'asc' ? cmp : -cmp
    })
  }, [rows, sortCol, sortDir])

  const toggleSort = (key) => {
    if (sortCol === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortCol(key); setSortDir('asc') }
  }

  if (!rows?.length) {
    return (
      <div className="flex items-center justify-center py-16 text-ink-faint text-sm">
        {emptyMessage}
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr
            style={{
              background: 'var(--c-surface-warm)',
              borderBottom: '1px solid var(--c-line)',
            }}
          >
            {columns.map(col => (
              <th
                key={col.key}
                onClick={() => col.sortable !== false && toggleSort(col.key)}
                className={`px-4 py-3 text-left select-none first:pl-5 last:pr-5 ${
                  col.sortable !== false
                    ? 'cursor-pointer hover:text-ink-secondary'
                    : ''
                }`}
              >
                <div className="flex items-center gap-1.5 section-header transition-colors duration-100">
                  {col.label}
                  {col.sortable !== false && (
                    <span className="opacity-40">
                      {sortCol === col.key
                        ? sortDir === 'asc'
                          ? <ChevronUp className="w-3 h-3" />
                          : <ChevronDown className="w-3 h-3" />
                        : <ChevronsUpDown className="w-3 h-3" />
                      }
                    </span>
                  )}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, i) => {
            const key        = row[keyField] ?? i
            const isSelected = selectedKey !== undefined && key === selectedKey
            return (
              <tr
                key={key}
                onClick={() => onRowClick?.(row)}
                style={{
                  borderBottom: `1px solid ${isSelected ? 'rgba(15,118,110,.18)' : 'var(--c-surface-subtle)'}`,
                  background: isSelected
                    ? 'rgba(15,118,110,.06)'
                    : i % 2 === 0
                      ? 'var(--c-surface)'
                      : 'var(--c-surface-warm)',
                  transition: 'background var(--dur-fast)',
                  cursor: onRowClick ? 'pointer' : 'default',
                }}
                onMouseEnter={e => {
                  if (!isSelected) e.currentTarget.style.background = 'var(--c-surface-subtle)'
                }}
                onMouseLeave={e => {
                  if (!isSelected) e.currentTarget.style.background = i % 2 === 0
                    ? 'var(--c-surface)'
                    : 'var(--c-surface-warm)'
                }}
              >
                {columns.map(col => (
                  <td
                    key={col.key}
                    className={`px-4 py-3 first:pl-5 last:pr-5 ${
                      isSelected ? 'text-ink' : 'text-ink-secondary'
                    }`}
                  >
                    {col.render ? col.render(row[col.key], row) : (row[col.key] ?? '—')}
                  </td>
                ))}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
