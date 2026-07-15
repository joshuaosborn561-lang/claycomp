import { useEffect, useRef, useState } from 'react'
import { Settings2, X } from 'lucide-react'
import type { EnrichmentColumn, RunCondition } from '../types'
import { summarizeRunCondition } from '../lib/runConditions'

type Props = {
  column: EnrichmentColumn
  sourceFieldOptions: string[]
  onChange: (patch: Partial<EnrichmentColumn>) => void
}

export default function ColumnSettingsPopover({ column, sourceFieldOptions, onChange }: Props) {
  const [open, setOpen] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)
  const cond = column.runCondition || {}
  const summary = summarizeRunCondition(cond)

  useEffect(() => {
    if (!open) return
    const onDoc = (e: MouseEvent) => {
      if (!panelRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open])

  const setCondition = (patch: Partial<RunCondition>) => {
    const next: RunCondition = { ...cond, ...patch }
    // Normalize empty strings to undefined
    if (!next.skipIfSourceFilled) delete next.skipIfSourceFilled
    if (!next.requireSourceFields?.length) delete next.requireSourceFields
    onChange({ runCondition: next })
  }

  return (
    <div className="relative" ref={panelRef}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={`p-1 rounded-md hover:bg-clay-200/60 ${summary ? 'text-clay-700' : 'text-slate-500'}`}
        title={summary ? `Settings · ${summary}` : 'Column settings'}
      >
        <Settings2 className="w-3 h-3" />
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 w-72 z-30 rounded-xl border border-slate-200 bg-white shadow-card p-3 space-y-3 animate-fade-in">
          <div className="flex items-center justify-between">
            <p className="text-[11px] font-semibold text-slate-700 uppercase tracking-wide">Column settings</p>
            <button type="button" onClick={() => setOpen(false)} className="p-0.5 rounded hover:bg-slate-100">
              <X className="w-3 h-3 text-slate-400" />
            </button>
          </div>

          <label className="flex items-start gap-2 text-[11px] text-slate-700 cursor-pointer">
            <input
              type="checkbox"
              className="mt-0.5"
              checked={Boolean(cond.skipIfOutputFilled)}
              onChange={(e) => setCondition({ skipIfOutputFilled: e.target.checked })}
            />
            <span>
              <span className="font-medium">Skip if already filled</span>
              <span className="block text-slate-400">Don’t re-run rows that already have a value in this column.</span>
            </span>
          </label>

          <div>
            <label className="text-[10px] font-medium text-slate-500 uppercase tracking-wide">
              Skip if source column has a value
            </label>
            <select
              value={cond.skipIfSourceFilled || ''}
              onChange={(e) => setCondition({ skipIfSourceFilled: e.target.value || undefined })}
              className="mt-1 w-full text-[11px] px-2 py-1.5 rounded-lg border border-slate-200 bg-white focus:outline-none focus:ring-1 focus:ring-clay-300"
            >
              <option value="">Never (always try)</option>
              {sourceFieldOptions.map((field) => (
                <option key={field} value={field}>
                  {field}
                </option>
              ))}
            </select>
            <p className="text-[10px] text-slate-400 mt-1">
              Example: for email waterfall, choose <span className="font-medium">email</span> so existing emails are left alone.
            </p>
          </div>

          {(column.enricherKey === 'custom' || column.customPrompt) && (
            <div>
              <label className="text-[10px] font-medium text-slate-500 uppercase tracking-wide">AI prompt</label>
              <textarea
                value={column.customPrompt || ''}
                onChange={(e) => onChange({ customPrompt: e.target.value })}
                rows={4}
                placeholder="Per-row instructions for this column…"
                className="mt-1 w-full text-[11px] px-2 py-1.5 rounded-lg border border-slate-200 resize-none focus:outline-none focus:ring-1 focus:ring-clay-300"
              />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
