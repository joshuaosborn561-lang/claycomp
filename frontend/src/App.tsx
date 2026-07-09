import { useCallback, useEffect, useState } from 'react'
import { LayoutGrid, MessageSquare, Sparkles } from 'lucide-react'
import { fetchEnrichers, loadSample } from './api'
import ChatMode from './components/ChatMode'
import TableMode from './components/TableMode'
import type { AppMode, Enricher, LeadRecord } from './types'

export default function App() {
  const [mode, setMode] = useState<AppMode>('table')
  const [records, setRecords] = useState<LeadRecord[]>([])
  const [enrichers, setEnrichers] = useState<Enricher[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([fetchEnrichers(), loadSample()])
      .then(([e, sample]) => {
        setEnrichers(e)
        setRecords(sample.records)
      })
      .finally(() => setLoading(false))
  }, [])

  const handleRecordsChange = useCallback((next: LeadRecord[]) => {
    setRecords(next)
  }, [])

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center bg-[#fafafa]">
        <div className="flex items-center gap-3 text-slate-500">
          <Sparkles className="w-5 h-5 text-clay-500 animate-pulse-soft" />
          <span className="text-sm font-medium">Loading Claycomp…</span>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      <header className="h-14 shrink-0 border-b border-slate-200/80 bg-white/80 backdrop-blur-md flex items-center justify-between px-5">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-clay-500 to-clay-700 flex items-center justify-center shadow-sm">
            <Sparkles className="w-4 h-4 text-white" />
          </div>
          <div>
            <h1 className="text-sm font-semibold tracking-tight">Claycomp</h1>
            <p className="text-[11px] text-slate-400 leading-none mt-0.5">
              {records.length} leads loaded
            </p>
          </div>
        </div>

        <div className="flex items-center bg-slate-100 rounded-xl p-1 gap-0.5">
          <ModeButton
            active={mode === 'table'}
            onClick={() => setMode('table')}
            icon={<LayoutGrid className="w-3.5 h-3.5" />}
            label="Table"
          />
          <ModeButton
            active={mode === 'chat'}
            onClick={() => setMode('chat')}
            icon={<MessageSquare className="w-3.5 h-3.5" />}
            label="Chat"
          />
        </div>
      </header>

      <main className="flex-1 min-h-0">
        {mode === 'table' ? (
          <TableMode
            records={records}
            enrichers={enrichers}
            onRecordsChange={handleRecordsChange}
          />
        ) : (
          <ChatMode
            records={records}
            enrichers={enrichers}
            onRecordsChange={handleRecordsChange}
          />
        )}
      </main>
    </div>
  )
}

function ModeButton({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean
  onClick: () => void
  icon: React.ReactNode
  label: string
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
        active
          ? 'bg-white text-slate-900 shadow-sm'
          : 'text-slate-500 hover:text-slate-700'
      }`}
    >
      {icon}
      {label}
    </button>
  )
}
