import { useMemo, useRef, useState } from 'react'
import {
  Download,
  FlaskConical,
  Hammer,
  Loader2,
  Mail,
  Play,
  Plus,
  Sparkles,
  Trash2,
  Upload,
} from 'lucide-react'
import { exportCsv, streamEnrich, uploadCsv } from '../api'
import EditableCell from './EditableCell'
import EditableHeader from './EditableHeader'
import { isAbortError, useJobs } from '../context/JobsContext'
import { useSettings } from '../context/SettingsContext'
import { useTable } from '../context/TableContext'
import SculptorPanel from './SculptorPanel'
import TableSwitcher from './TableSwitcher'
import {
  addRow,
  addSourceColumn,
  clearEnrichedColumn,
  deleteRow,
  deleteSourceColumn,
  renameSourceColumn,
  updateEnrichedCell,
  updateSourceCell,
} from '../lib/tableEdits'
import type { Enricher, EnrichmentColumn } from '../types'
import { columnOutputKey, formatCell, sourceColumnsFromRecords } from '../types'

const TEST_ROWS = 10

export default function TableMode() {
  const { settings } = useSettings()
  const { track } = useJobs()
  const {
    records,
    columns,
    enrichers,
    setRecords,
    setColumns,
    businessContext,
    emailProviders,
    setEmailProviders,
  } = useTable()
  const sourceColumns = useMemo(() => sourceColumnsFromRecords(records), [records])
  const [showAddMenu, setShowAddMenu] = useState(false)
  const [showSculptor, setShowSculptor] = useState(true)
  const [showEmailProviders, setShowEmailProviders] = useState(false)
  const [previewColumn, setPreviewColumn] = useState<EnrichmentColumn | null>(null)
  const [runningCol, setRunningCol] = useState<string | null>(null)
  const [sandboxCol, setSandboxCol] = useState<string | null>(null)
  const [progress, setProgress] = useState<{ done: number; total: number; mode?: string } | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const displayColumns = useMemo(() => {
    if (!previewColumn) return columns
    if (columns.some((c) => c.id === previewColumn.id)) return columns
    return [...columns, previewColumn]
  }, [columns, previewColumn])

  const addColumn = (col: EnrichmentColumn) => {
    const exists = columns.some(
      (c) =>
        c.label.toLowerCase() === col.label.toLowerCase() ||
        (col.columnName && c.columnName?.toLowerCase() === col.columnName.toLowerCase()),
    )
    if (!exists) setColumns([...columns, { ...col, preview: undefined }])
    setPreviewColumn(null)
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

  const runColumn = async (col: EnrichmentColumn, testRun = false) => {
    const enricherKey = col.enricherKey === 'custom' ? 'custom' : col.enricherKey
    const rowIds = testRun ? records.slice(0, TEST_ROWS).map((r) => r.id) : undefined
    const total = testRun ? Math.min(TEST_ROWS, records.length) : records.length

    setRunningCol(col.id)
    if (testRun) setSandboxCol(col.id)
    setProgress({ done: 0, total, mode: testRun ? 'test' : 'full' })

    const updated = [...records]
    const outputKey = columnOutputKey(col, enrichers)

    try {
      const result = await track((signal) =>
        streamEnrich(
          updated,
          enricherKey,
          (event) => {
            if (event.type === 'progress' || event.type === 'error') {
              setProgress({
                done: event.done as number,
                total: event.total as number,
                mode: testRun ? 'test' : 'full',
              })
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
            businessContext,
            emailProviders,
          },
          signal,
        ),
      )
      setRecords(result)
    } catch (error) {
      if (!isAbortError(error)) throw error
    } finally {
      setRunningCol(null)
      setSandboxCol(null)
      setProgress(null)
    }
  }

  const addEmailWaterfall = () => {
    addColumn({
      id: `email-waterfall-${Date.now()}`,
      enricherKey: 'email_waterfall',
      label: 'Work Email',
      columnName: 'email_waterfall',
      provider: settings.providerId,
      model: settings.model,
    })
  }

  const toggleEmailProvider = (key: string) => {
    if (key === 'ai_ark') return // always on
    if (emailProviders.includes(key)) {
      setEmailProviders(emailProviders.filter((p) => p !== key))
    } else {
      setEmailProviders([...emailProviders, key])
    }
  }

  const moveEmailProvider = (key: string, dir: -1 | 1) => {
    const idx = emailProviders.indexOf(key)
    if (idx < 0) return
    const next = [...emailProviders]
    const swap = idx + dir
    if (swap < 0 || swap >= next.length) return
    ;[next[idx], next[swap]] = [next[swap], next[idx]]
    setEmailProviders(next)
  }

  const testProposal = (col: EnrichmentColumn) => {
    const preview = { ...col, id: `preview-${Date.now()}`, preview: true }
    setPreviewColumn(preview)
    void runColumn(preview, true)
  }

  const handleUpload = async (file: File) => {
    const { records: next, count } = await uploadCsv(file)
    if (count !== next.length) {
      console.warn(`Import count mismatch: reported ${count}, received ${next.length}`)
    }
    setRecords(next)
    setColumns([])
    setPreviewColumn(null)
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

  const handleAddRow = () => {
    const keys = sourceColumns.map((col) => col.key)
    setRecords(addRow(records, keys.length ? keys : ['Column 1']))
  }

  const handleAddSourceColumn = () => {
    const name = window.prompt('New column name')
    if (!name?.trim()) return
    setRecords(addSourceColumn(records, name.trim()))
  }

  const handleDeleteSourceColumn = (key: string) => {
    if (!window.confirm(`Delete column "${key}"?`)) return
    setRecords(deleteSourceColumn(records, key))
  }

  const handleRenameSourceColumn = (oldKey: string, newKey: string) => {
    setRecords(renameSourceColumn(records, oldKey, newKey))
  }

  const handleDeleteEnrichmentColumn = (col: EnrichmentColumn) => {
    if (!window.confirm(`Delete enrichment column "${col.label}"?`)) return
    const outputKey = columnOutputKey(col, enrichers)
    setColumns(columns.filter((c) => c.id !== col.id))
    if (previewColumn?.id === col.id) setPreviewColumn(null)
    setRecords(clearEnrichedColumn(records, outputKey))
  }

  const handleRenameEnrichmentColumn = (colId: string, label: string) => {
    const col = columns.find((c) => c.id === colId)
    if (!col) return
    const oldKey = columnOutputKey(col, enrichers)
    const updatedCol: EnrichmentColumn = {
      ...col,
      label,
      columnName: col.enricherKey === 'custom' ? label : col.columnName,
    }
    const newKey = columnOutputKey(updatedCol, enrichers)
    setColumns(columns.map((c) => (c.id === colId ? updatedCol : c)))
    if (oldKey !== newKey) {
      setRecords(
        records.map((record) => {
          if (!(oldKey in record.enriched)) return record
          const enriched = { ...record.enriched }
          enriched[newKey] = enriched[oldKey]
          delete enriched[oldKey]
          return { ...record, enriched }
        }),
      )
    }
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
            Tables auto-save as you work. Cloud sync when Supabase is connected on Vercel.
          </p>
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0 bg-[#fafafa]">
        <div className="h-12 shrink-0 border-b border-slate-200/60 bg-white flex items-center justify-between px-4">
          <div className="flex items-center gap-2">
            <span className="text-sm text-slate-600">
              {records.length} rows · {sourceColumns.length} columns
            </span>
            {progress && (
              <span className="text-xs text-clay-600 bg-clay-50 px-2 py-0.5 rounded-full flex items-center gap-1">
                {progress.mode === 'test' && <FlaskConical className="w-3 h-3" />}
                {progress.mode === 'test' ? 'Testing' : 'Enriching'} {progress.done}/{progress.total}
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleAddRow}
              className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-slate-200 bg-white text-xs font-medium text-slate-600 hover:border-clay-300 hover:text-clay-700"
            >
              <Plus className="w-3.5 h-3.5" />
              Add row
            </button>
            <button
              onClick={handleAddSourceColumn}
              className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-slate-200 bg-white text-xs font-medium text-slate-600 hover:border-clay-300 hover:text-clay-700"
            >
              <Plus className="w-3.5 h-3.5" />
              Add column
            </button>
            <div className="relative">
              <button
                onClick={() => {
                  setShowEmailProviders(!showEmailProviders)
                  setShowAddMenu(false)
                }}
                className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-slate-200 bg-white text-xs font-medium text-slate-600 hover:border-clay-300 hover:text-clay-700"
                title="Email finder waterfall providers for this table"
              >
                <Mail className="w-3.5 h-3.5" />
                Email waterfall
              </button>
              {showEmailProviders && (
                <div className="absolute right-0 top-full mt-1 w-80 bg-white rounded-xl shadow-card border border-slate-200/80 z-20 overflow-hidden animate-fade-in p-3 space-y-2">
                  <p className="text-[11px] font-medium text-slate-500 uppercase tracking-wide">Providers (this table)</p>
                  <p className="text-[10px] text-slate-400 leading-snug">
                    Runs in order until an email is found. AI Ark always stays available — we use their sync export/single path (not Clay's broken trackId flow).
                  </p>
                  <ul className="space-y-1.5">
                    {emailProviders.map((key, i) => (
                      <li key={key} className="flex items-center gap-2 text-xs text-slate-700 bg-slate-50 rounded-lg px-2 py-1.5">
                        <span className="text-[10px] text-slate-400 w-4">{i + 1}.</span>
                        <span className="flex-1 font-medium">{key === 'ai_ark' ? 'AI Ark' : 'Prospeo'}</span>
                        {key === 'ai_ark' ? (
                          <span className="text-[9px] text-clay-600">required</span>
                        ) : (
                          <button type="button" onClick={() => toggleEmailProvider(key)} className="text-[10px] text-red-500">Remove</button>
                        )}
                        <button type="button" onClick={() => moveEmailProvider(key, -1)} className="text-[10px] text-slate-400 hover:text-slate-700" disabled={i === 0}>↑</button>
                        <button type="button" onClick={() => moveEmailProvider(key, 1)} className="text-[10px] text-slate-400 hover:text-slate-700" disabled={i === emailProviders.length - 1}>↓</button>
                      </li>
                    ))}
                  </ul>
                  {!emailProviders.includes('prospeo') && (
                    <button
                      type="button"
                      onClick={() => toggleEmailProvider('prospeo')}
                      className="text-[11px] text-clay-700 hover:underline"
                    >
                      + Add Prospeo
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => {
                      addEmailWaterfall()
                      setShowEmailProviders(false)
                    }}
                    className="w-full mt-1 py-1.5 rounded-lg bg-clay-600 text-white text-[11px] font-medium hover:bg-clay-700"
                  >
                    Add Work Email column
                  </button>
                </div>
              )}
            </div>
            <div className="relative">
              <button
                onClick={() => {
                  setShowAddMenu(!showAddMenu)
                  setShowEmailProviders(false)
                }}
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
        </div>

        <div className="flex-1 overflow-auto">
          <table className="w-full border-collapse text-sm">
            <thead className="sticky top-0 z-10">
              <tr className="bg-white border-b border-slate-200">
                <th className="w-10 px-3 py-2.5 text-left text-[11px] font-medium text-slate-400 border-r border-slate-100">#</th>
                {sourceColumns.map((col) => (
                  <th key={col.key} className="px-3 py-2.5 text-left text-[11px] font-semibold text-slate-500 uppercase tracking-wide border-r border-slate-100 min-w-[140px] bg-slate-50/50">
                    <EditableHeader
                      label={col.label}
                      onRename={(label) => handleRenameSourceColumn(col.key, label)}
                      onDelete={() => handleDeleteSourceColumn(col.key)}
                    />
                  </th>
                ))}
                {displayColumns.map((col) => (
                  <th key={col.id} className={`px-3 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wide border-r min-w-[160px] ${col.preview ? 'text-amber-700 border-amber-100 bg-amber-50/80' : 'text-clay-700 border-clay-100 bg-clay-50/80'}`}>
                    <div className="flex items-center justify-between gap-1">
                      <span className="flex items-center gap-1 min-w-0 flex-1">
                        <Sparkles className="w-3 h-3 shrink-0" />
                        {col.preview ? (
                          <span className="truncate">{col.label} (test)</span>
                        ) : (
                          <EditableHeader
                            label={col.label}
                            onRename={(label) => handleRenameEnrichmentColumn(col.id, label)}
                            onDelete={() => handleDeleteEnrichmentColumn(col)}
                            className="text-clay-700"
                          />
                        )}
                      </span>
                      {!col.preview && (
                        <div className="flex shrink-0">
                          <button onClick={() => runColumn(col, true)} disabled={runningCol === col.id} className="p-1 rounded-md hover:bg-clay-200/60 disabled:opacity-40" title={`Test (${TEST_ROWS} rows)`}>
                            <FlaskConical className="w-3 h-3" />
                          </button>
                          <button onClick={() => runColumn(col)} disabled={runningCol === col.id} className="p-1 rounded-md hover:bg-clay-200/60 disabled:opacity-40" title="Run all rows">
                            {runningCol === col.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
                          </button>
                        </div>
                      )}
                    </div>
                  </th>
                ))}
                <th className="w-10" />
              </tr>
            </thead>
            <tbody>
              {records.map((row, i) => (
                <tr key={`${row.id}-${i}`} className={`group border-b border-slate-100 hover:bg-white transition-colors ${sandboxCol && i < TEST_ROWS ? 'bg-amber-50/30' : ''}`}>
                  <td className="px-2 py-2 text-xs text-slate-300 border-r border-slate-50">
                    <div className="flex items-center justify-between gap-1">
                      <span>{i + 1}</span>
                      <button
                        type="button"
                        onClick={() => setRecords(deleteRow(records, row.id))}
                        className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-red-100"
                        title="Delete row"
                      >
                        <Trash2 className="w-3 h-3 text-red-500" />
                      </button>
                    </div>
                  </td>
                  {sourceColumns.map((col) => (
                    <td key={col.key} className="px-2 py-1 text-slate-700 border-r border-slate-50 max-w-[200px]">
                      <EditableCell
                        value={col.get(row) || ''}
                        onSave={(value) => setRecords(updateSourceCell(records, row.id, col.key, value))}
                      />
                    </td>
                  ))}
                  {displayColumns.map((col) => {
                    const outputKey = columnOutputKey(col, enrichers)
                    const value = row.enriched[outputKey]
                    const isRunning = runningCol === col.id && value == null
                    return (
                      <td key={col.id} className="px-2 py-1 border-r border-clay-50/50 bg-clay-50/20 max-w-[220px]">
                        {isRunning ? (
                          <span className="text-xs text-clay-400 animate-pulse-soft px-1">Running…</span>
                        ) : (
                          <EditableCell
                            value={formatCell(value) === '—' ? '' : formatCell(value)}
                            onSave={(text) => setRecords(updateEnrichedCell(records, row.id, outputKey, text))}
                          />
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
            <div className="flex flex-col items-center justify-center py-24 text-slate-400 gap-3">
              <Upload className="w-8 h-8 opacity-40" />
              <p className="text-sm">Import a CSV or add a row to get started</p>
              <button
                onClick={handleAddRow}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-xs font-medium text-slate-600 hover:border-clay-300"
              >
                <Plus className="w-3.5 h-3.5" />
                Add row
              </button>
            </div>
          )}
        </div>
      </div>

      {showSculptor && (
        <SculptorPanel
          onAddColumn={addColumn}
          onApplyWorkflow={(steps) => { for (const col of steps) addColumn(col) }}
          onTest={testProposal}
          onClearPreview={() => setPreviewColumn(null)}
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
