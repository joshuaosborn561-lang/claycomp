import { useRef, useState } from 'react'
import {
  Download,
  Loader2,
  Play,
  Plus,
  Sparkles,
  Table2,
  Upload,
} from 'lucide-react'
import { exportCsv, loadSample, streamEnrich, uploadCsv } from '../api'
import type { Enricher, EnrichmentColumn, LeadRecord } from '../types'
import { displayLocation, displayName, formatCell } from '../types'

const SOURCE_COLUMNS = [
  { key: 'name', label: 'Name', get: (r: LeadRecord) => displayName(r) },
  { key: 'email', label: 'Email', get: (r: LeadRecord) => r.email },
  { key: 'title', label: 'Title', get: (r: LeadRecord) => r.title },
  { key: 'company', label: 'Company', get: (r: LeadRecord) => r.company },
  { key: 'location', label: 'Location', get: (r: LeadRecord) => displayLocation(r) },
]

type Props = {
  records: LeadRecord[]
  enrichers: Enricher[]
  onRecordsChange: (records: LeadRecord[]) => void
}

export default function TableMode({ records, enrichers, onRecordsChange }: Props) {
  const [columns, setColumns] = useState<EnrichmentColumn[]>([])
  const [showAddMenu, setShowAddMenu] = useState(false)
  const [runningCol, setRunningCol] = useState<string | null>(null)
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const addColumn = (enricher: Enricher) => {
    const col: EnrichmentColumn = {
      id: `${enricher.key}-${Date.now()}`,
      enricherKey: enricher.key,
      label: enricher.name,
    }
    setColumns((c) => [...c, col])
    setShowAddMenu(false)
  }

  const runColumn = async (col: EnrichmentColumn) => {
    const enricher = enrichers.find((e) => e.key === col.enricherKey)
    if (!enricher) return

    setRunningCol(col.id)
    setProgress({ done: 0, total: records.length })

    const updated = [...records]
    const result = await streamEnrich(updated, col.enricherKey, (event) => {
      if (event.type === 'progress' || event.type === 'error') {
        setProgress({ done: event.done as number, total: event.total as number })
        const idx = updated.findIndex((r) => r.id === event.row_id)
        if (idx >= 0) {
          const column = event.column as string
          if (event.type === 'progress') {
            updated[idx] = {
              ...updated[idx],
              enriched: { ...updated[idx].enriched, [column]: event.value },
            }
          }
          onRecordsChange([...updated])
        }
      }
    })

    onRecordsChange(result)
    setRunningCol(null)
    setProgress(null)
  }

  const handleUpload = async (file: File) => {
    const { records: next } = await uploadCsv(file)
    onRecordsChange(next)
    setColumns([])
  }

  const handleExport = async () => {
    const blob = await exportCsv(records)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'enriched.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="h-full flex">
      {/* Sidebar */}
      <aside className="w-56 shrink-0 border-r border-slate-200/80 bg-white flex flex-col">
        <div className="p-4 border-b border-slate-100">
          <div className="flex items-center gap-2 text-slate-700">
            <Table2 className="w-4 h-4 text-clay-500" />
            <span className="text-sm font-medium">Lead Table</span>
          </div>
        </div>

        <div className="p-3 flex flex-col gap-1.5">
          <SidebarButton icon={<Upload className="w-3.5 h-3.5" />} onClick={() => fileRef.current?.click()}>
            Import CSV
          </SidebarButton>
          <SidebarButton
            icon={<Table2 className="w-3.5 h-3.5" />}
            onClick={async () => {
              const { records: next } = await loadSample()
              onRecordsChange(next)
              setColumns([])
            }}
          >
            Load sample
          </SidebarButton>
          <SidebarButton icon={<Download className="w-3.5 h-3.5" />} onClick={handleExport}>
            Export CSV
          </SidebarButton>
        </div>

        <div className="mt-auto p-4 border-t border-slate-100">
          <p className="text-[11px] text-slate-400 leading-relaxed">
            Clay-style table. Add AI enrichment columns, then run them row by row.
          </p>
        </div>
      </aside>

      {/* Table area */}
      <div className="flex-1 flex flex-col min-w-0 bg-[#fafafa]">
        {/* Toolbar */}
        <div className="h-12 shrink-0 border-b border-slate-200/60 bg-white flex items-center justify-between px-4">
          <div className="flex items-center gap-2">
            <span className="text-sm text-slate-600">{records.length} rows</span>
            {progress && (
              <span className="text-xs text-clay-600 bg-clay-50 px-2 py-0.5 rounded-full">
                Enriching {progress.done}/{progress.total}
              </span>
            )}
          </div>

          <div className="relative">
            <button
              onClick={() => setShowAddMenu(!showAddMenu)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-clay-600 hover:bg-clay-700 text-white text-xs font-medium transition-colors shadow-sm"
            >
              <Plus className="w-3.5 h-3.5" />
              Add enrichment
            </button>

            {showAddMenu && (
              <div className="absolute right-0 top-full mt-1 w-72 bg-white rounded-xl shadow-card border border-slate-200/80 z-20 overflow-hidden animate-fade-in">
                <div className="px-3 py-2 border-b border-slate-100">
                  <p className="text-[11px] font-medium text-slate-400 uppercase tracking-wide">
                    AI columns
                  </p>
                </div>
                {enrichers.map((e) => (
                  <button
                    key={e.key}
                    onClick={() => addColumn(e)}
                    className="w-full text-left px-3 py-2.5 hover:bg-clay-50 transition-colors flex items-start gap-2.5"
                  >
                    <Sparkles className="w-3.5 h-3.5 text-clay-500 mt-0.5 shrink-0" />
                    <div>
                      <p className="text-sm font-medium text-slate-800">{e.name}</p>
                      <p className="text-xs text-slate-400 mt-0.5">{e.description}</p>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Spreadsheet */}
        <div className="flex-1 overflow-auto">
          <table className="w-full border-collapse text-sm">
            <thead className="sticky top-0 z-10">
              <tr className="bg-white border-b border-slate-200">
                <th className="w-10 px-3 py-2.5 text-left text-[11px] font-medium text-slate-400 border-r border-slate-100">
                  #
                </th>
                {SOURCE_COLUMNS.map((col) => (
                  <th
                    key={col.key}
                    className="px-3 py-2.5 text-left text-[11px] font-semibold text-slate-500 uppercase tracking-wide border-r border-slate-100 min-w-[140px] bg-slate-50/50"
                  >
                    {col.label}
                  </th>
                ))}
                {columns.map((col) => (
                  <th
                    key={col.id}
                    className="px-3 py-2.5 text-left text-[11px] font-semibold text-clay-700 uppercase tracking-wide border-r border-clay-100 min-w-[160px] bg-clay-50/80"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="flex items-center gap-1">
                        <Sparkles className="w-3 h-3" />
                        {col.label}
                      </span>
                      <button
                        onClick={() => runColumn(col)}
                        disabled={runningCol === col.id}
                        className="p-1 rounded-md hover:bg-clay-200/60 disabled:opacity-40 transition-colors"
                        title="Run column"
                      >
                        {runningCol === col.id ? (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        ) : (
                          <Play className="w-3 h-3" />
                        )}
                      </button>
                    </div>
                  </th>
                ))}
                <th className="w-10" />
              </tr>
            </thead>
            <tbody>
              {records.map((row, i) => (
                <tr
                  key={row.id}
                  className="border-b border-slate-100 hover:bg-white transition-colors group"
                >
                  <td className="px-3 py-2 text-xs text-slate-300 border-r border-slate-50">
                    {i + 1}
                  </td>
                  {SOURCE_COLUMNS.map((col) => (
                    <td
                      key={col.key}
                      className="px-3 py-2 text-slate-700 border-r border-slate-50 truncate max-w-[200px]"
                    >
                      {col.get(row) || <span className="text-slate-300">—</span>}
                    </td>
                  ))}
                  {columns.map((col) => {
                    const enricher = enrichers.find((e) => e.key === col.enricherKey)
                    const value = enricher ? row.enriched[enricher.name] : null
                    const isRunning = runningCol === col.id && !value
                    return (
                      <td
                        key={col.id}
                        className="px-3 py-2 border-r border-clay-50/50 bg-clay-50/20 truncate max-w-[220px]"
                      >
                        {isRunning ? (
                          <span className="text-xs text-clay-400 animate-pulse-soft">Running…</span>
                        ) : (
                          <span className="text-slate-700">{formatCell(value)}</span>
                        )}
                      </td>
                    )
                  })}
                  <td />
                </tr>
              ))}
            </tbody>
          </table>

          {records.length === 0 && (
            <div className="flex flex-col items-center justify-center py-24 text-slate-400">
              <Upload className="w-8 h-8 mb-3 opacity-40" />
              <p className="text-sm">Import a CSV to get started</p>
            </div>
          )}
        </div>
      </div>

      <input
        ref={fileRef}
        type="file"
        accept=".csv"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) handleUpload(file)
          e.target.value = ''
        }}
      />
    </div>
  )
}

function SidebarButton({
  icon,
  children,
  onClick,
}: {
  icon: React.ReactNode
  children: React.ReactNode
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium text-slate-600 hover:bg-slate-50 hover:text-slate-900 transition-colors w-full text-left"
    >
      {icon}
      {children}
    </button>
  )
}
