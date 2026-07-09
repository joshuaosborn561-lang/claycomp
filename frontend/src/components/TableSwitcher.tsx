import { useState } from 'react'
import { Check, ChevronDown, Cloud, CloudOff, HardDrive, Loader2, Plus, Table2, Trash2 } from 'lucide-react'
import { useTable } from '../context/TableContext'

export default function TableSwitcher() {
  const { tableName, tableId, tables, saveStatus, setTableName, createTable, switchTable, deleteTable } = useTable()
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(false)

  const StatusIcon = () => {
    if (saveStatus === 'saving') return <Loader2 className="w-3 h-3 animate-spin text-slate-400" />
    if (saveStatus === 'saved') return <Cloud className="w-3 h-3 text-emerald-500" />
    if (saveStatus === 'local') return <HardDrive className="w-3 h-3 text-amber-500" />
    if (saveStatus === 'error') return <CloudOff className="w-3 h-3 text-red-400" />
    return <Check className="w-3 h-3 text-slate-300" />
  }

  const statusLabel =
    saveStatus === 'saving' ? 'Saving…' :
    saveStatus === 'saved' ? 'Saved' :
    saveStatus === 'local' ? 'Saved locally' :
    saveStatus === 'error' ? 'Save failed' : ''

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-slate-50 text-left group"
      >
        <Table2 className="w-3.5 h-3.5 text-clay-500 shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-xs font-medium text-slate-800 truncate">{tableName}</p>
          <div className="flex items-center gap-1 mt-0.5">
            <StatusIcon />
            <span className="text-[10px] text-slate-400">{statusLabel}</span>
          </div>
        </div>
        <ChevronDown className={`w-3.5 h-3.5 text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="absolute left-0 right-0 top-full mt-1 z-30 bg-white rounded-xl border border-slate-200 shadow-card overflow-hidden animate-fade-in">
          <div className="p-2 border-b border-slate-100">
            {editing ? (
              <input
                autoFocus
                defaultValue={tableName}
                onBlur={(e) => {
                  setTableName(e.target.value || 'My Leads')
                  setEditing(false)
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') (e.target as HTMLInputElement).blur()
                }}
                className="w-full text-xs px-2 py-1 rounded border border-slate-200 focus:outline-none focus:ring-1 focus:ring-clay-300"
              />
            ) : (
              <button
                onClick={() => setEditing(true)}
                className="w-full text-left text-[10px] text-slate-400 hover:text-slate-600 px-1"
              >
                Rename table
              </button>
            )}
          </div>

          <div className="max-h-48 overflow-y-auto py-1">
            {tables.map((t) => (
              <div
                key={t.id}
                className={`flex items-center gap-1 px-2 py-1.5 hover:bg-slate-50 ${t.id === tableId ? 'bg-clay-50' : ''}`}
              >
                <button
                  onClick={() => { switchTable(t.id); setOpen(false) }}
                  className="flex-1 text-left text-xs text-slate-700 truncate"
                >
                  {t.name}
                  <span className="text-[10px] text-slate-400 ml-1">({t.row_count})</span>
                </button>
                {tables.length > 1 && (
                  <button
                    onClick={() => deleteTable(t.id)}
                    className="p-1 text-slate-300 hover:text-red-500 rounded"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                )}
              </div>
            ))}
          </div>

          <button
            onClick={() => { createTable(); setOpen(false) }}
            className="w-full flex items-center gap-2 px-3 py-2 text-xs text-clay-600 hover:bg-clay-50 border-t border-slate-100"
          >
            <Plus className="w-3.5 h-3.5" />
            New table
          </button>
        </div>
      )}
    </div>
  )
}
