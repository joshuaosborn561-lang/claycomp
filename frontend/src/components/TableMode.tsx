import { useRef, useState } from 'react'
import {
  Download,
  FlaskConical,
  Hammer,
  Loader2,
  Play,
  Plus,
  Sparkles,
  Upload,
} from 'lucide-react'
import { exportCsv, streamEnrich, uploadCsv } from '../api'
import { useSettings } from '../context/SettingsContext'
import { useTable } from '../context/TableContext'
import SculptorPanel from './SculptorPanel'
import TableSwitcher from './TableSwitcher'
import type { Enricher, EnrichmentColumn, LeadRecord } from '../types'
import { columnOutputKey, displayLocation, displayName, formatCell } from '../types'

const SOURCE_COLUMNS = [
  { key: 'name', label: 'Name', get: (r: LeadRecord) => displayName(r) },
  { key: 'email', label: 'Email', get: (r: LeadRecord) => r.email },
  { key: 'title', label: 'Title', get: (r: LeadRecord) => r.title },
  { key: 'company', label: 'Company', get: (r: LeadRecord) => r.company },
  { key: 'location', label: 'Location', get: (r: LeadRecord) => displayLocation(r) },
]

const SANDBOX_ROWS = 3

export default function TableMode() {
  const { settings } = useSettings()
  const { records, columns, enrichers, setRecords, setColumns } = useTable()
  const [showAddMenu, setShowAddMenu] = useState(false)
  const [showSculptor, setShowSculptor] = useState(true)
  const [runningCol, setRunningCol] = useState<string | null>(null)
  const [sandboxCol, setSandboxCol] = useState<string | null>(null)
  const [progress, setProgress] = useState<{ done: number; total: number; mode?: string } | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const addColumn = (col: EnrichmentColumn) => {
    setColumns([...columns, col])
    setShowAddMenu(false)
  }

  const addBuiltInColumn = (enricher: Enricher) => {
    addColumn({
      id: `${enricher.key}-${Date.now()}`,
      enricherKey: enricher.key,
      label: enricher.name,
      provider: settings.providerId,
      model: settings.model,
    })
  }

  const runColumn = async (col: EnrichmentColumn, sandbox = false) => {
    const enricherKey = col.enricherKey === 'custom' ? 'custom' : col.enricherKey
    const rowIds = sandbox ? records.slice(0, SANDBOX_ROWS).map((r) => r.id) : undefined
    const total = sandbox ? Math.min(SANDBOX_ROWS, records.length) : records.length

    setRunningCol(col.id)
    if (sandbox) setSandboxCol(col.id)
    setProgress({ done: 0, total, mode: sandbox ? 'sandbox' : 'full' })

    const updated = [...records]
    const outputKey = columnOutputKey(col, enrichers)

    const result = await streamEnrich(
      updated,
      enricherKey,
      (event) => {
        if (event.type === 'progress' || event.type === 'error') {
          setProgress({ done: event.done as number, total: event.total as number, mode: sandbox ? 'sandbox' : 'full' })
          const idx = updated.findIndex((r) => r.id === event.row_id)
          if (idx >= 0 && event.type === 'progress') {
            const column = (event.column as string) || outputKey
            updated[idx] = {
              ...updated[idx],
              enriched: { ...updated[idx].enriched, [column]: event.value },
            }
            setRecords([...updated])
          }
        }
      },
      {
        provider: col.provider || settings.providerId,
        model: col.model || settings.model,
        customPrompt: col.customPrompt,
        columnName: col.columnName || col.label,
        rowIds,
      },
    )

    setRecords(result)
    setRunningCol(null)
    setSandboxCol(null)
    setProgress(null)
  }

  const handleUpload = async (file: File) => {
    const { records: next } = await uploadCsv(file)
    setRecords(next)
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
      <aside className="w-56 shrink-0 border-r border-slate-200/80 bg-white flex flex-col">
        <div className="p-3 border-b border-slate-100">
          <TableSwitcher />
        </div>

        <div className="p-3 flex flex-col gap-1.5">
          <SidebarButton icon={<Upload className="w-3.5 h-3.5" />} onClick={() => fileRef.current?.click()}>
            Import CSV
          </SidebarButton>
          <SidebarButton icon={<Download className="w-3.5 h-3.5" />} onClick={handleExport}>
            Export CSV
          </SidebarButton>
          <SidebarButton icon={<Hammer className="w-3.5 h-3.5" />} onClick={() => setShowSculptor(!showSculptor)}>
            {showSculptor ? 'Hide Sculptor' : 'Open Sculptor'}
          </SidebarButton>
        </div>

        <div className="mt-auto p-4 border-t border-slate-100">
          <p className="text-[11px] text-slate-400 leading-relaxed">
            Tables auto-save as you work. Cloud sync when Upstash is configured on Vercel.
          </p>
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0 bg-[#fafafa]">
        <div className="h-12 shrink-0 border-b border-slate-200/60 bg-white flex items-center justify-between px-4">
          <div className="flex items-center gap-2">
            <span className="text-sm text-slate-600">{records.length} rows</span>
            {progress && (
              <span className="text-xs text-clay-600 bg-clay-50 px-2 py-0.5 rounded-full flex items-center gap-1">
                {progress.mode === 'sandbox' && <FlaskConical className="w-3 h-3" />}
                {progress.mode === 'sandbox' ? 'Sandbox' : 'Enriching'} {progress.done}/{progress.total}
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
                  <p className="text-[11px] font-medium text-slate-400 uppercase tracking-wide">AI columns</p>
                </div>
                {enrichers.map((e) => (
                  <button
                    key={e.key}
                    onClick={() => addBuiltInColumn(e)}
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

        <div className="flex-1 overflow-auto">
          <table className="w-full border-collapse text-sm">
            <thead className="sticky top-0 z-10">
              <tr className="bg-white border-b border-slate-200">
                <th className="w-10 px-3 py-2.5 text-left text-[11px] font-medium text-slate-400 border-r border-slate-100">#</th>
                {SOURCE_COLUMNS.map((col) => (
                  <th key={col.key} className="px-3 py-2.5 text-left text-[11px] font-semibold text-slate-500 uppercase tracking-wide border-r border-slate-100 min-w-[140px] bg-slate-50/50">
                    {col.label}
                  </th>
                ))}
                {columns.map((col) => (
                  <th key={col.id} className="px-3 py-2.5 text-left text-[11px] font-semibold text-clay-700 uppercase tracking-wide border-r border-clay-100 min-w-[160px] bg-clay-50/80">
                    <div className="flex items-center justify-between gap-1">
                      <span className="flex items-center gap-1 truncate">
                        <Sparkles className="w-3 h-3 shrink-0" />
                        <span className="truncate">{col.label}</span>
                      </span>
                      <div className="flex shrink-0">
                        <button onClick={() => runColumn(col, true)} disabled={runningCol === col.id} className="p-1 rounded-md hover:bg-clay-200/60 disabled:opacity-40" title="Sandbox (3 rows)">
                          <FlaskConical className="w-3 h-3" />
                        </button>
                        <button onClick={() => runColumn(col)} disabled={runningCol === col.id} className="p-1 rounded-md hover:bg-clay-200/60 disabled:opacity-40" title="Run all rows">
                          {runningCol === col.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
                        </button>
                      </div>
                    </div>
                  </th>
                ))}
                <th className="w-10" />
              </tr>
            </thead>
            <tbody>
              {records.map((row, i) => (
                <tr key={row.id} className={`border-b border-slate-100 hover:bg-white transition-colors ${sandboxCol && i < SANDBOX_ROWS ? 'bg-amber-50/30' : ''}`}>
                  <td className="px-3 py-2 text-xs text-slate-300 border-r border-slate-50">{i + 1}</td>
                  {SOURCE_COLUMNS.map((col) => (
                    <td key={col.key} className="px-3 py-2 text-slate-700 border-r border-slate-50 truncate max-w-[200px]">
                      {col.get(row) || <span className="text-slate-300">—</span>}
                    </td>
                  ))}
                  {columns.map((col) => {
                    const outputKey = columnOutputKey(col, enrichers)
                    const value = row.enriched[outputKey]
                    const isRunning = runningCol === col.id && value == null
                    return (
                      <td key={col.id} className="px-3 py-2 border-r border-clay-50/50 bg-clay-50/20 truncate max-w-[220px]">
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

      {showSculptor && (
        <SculptorPanel
          onAddColumn={addColumn}
          onApplyWorkflow={(steps) => { for (const col of steps) addColumn(col) }}
          onSandbox={(col) => {
            if (!columns.find((c) => c.id === col.id)) addColumn(col)
            runColumn(col, true)
          }}
        />
      )}

      <input ref={fileRef} type="file" accept=".csv" className="hidden" onChange={(e) => {
        const file = e.target.files?.[0]
        if (file) handleUpload(file)
        e.target.value = ''
      }} />
    </div>
  )
}

function SidebarButton({ icon, children, onClick }: { icon: React.ReactNode; children: React.ReactNode; onClick: () => void }) {
  return (
    <button onClick={onClick} className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium text-slate-600 hover:bg-slate-50 hover:text-slate-900 transition-colors w-full text-left">
      {icon}
      {children}
    </button>
  )
}
