import { useState } from 'react'
import { LayoutGrid, MessageSquare, Settings, Sparkles } from 'lucide-react'
import ChatMode from './components/ChatMode'
import SettingsModal from './components/SettingsModal'
import TableMode from './components/TableMode'
import { SettingsProvider, useSettings } from './context/SettingsContext'
import { TableProvider, useTable } from './context/TableContext'
import type { AppMode } from './types'

function AppContent() {
  const [mode, setMode] = useState<AppMode>('table')
  const [settingsOpen, setSettingsOpen] = useState(false)
  const { activeProvider, settings } = useSettings()
  const { records, loading, saveStatus } = useTable()

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center bg-[#fafafa]">
        <div className="flex items-center gap-3 text-slate-500">
          <Sparkles className="w-5 h-5 text-clay-500 animate-pulse-soft" />
          <span className="text-sm font-medium">Loading your tables…</span>
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
              {records.length} leads · {activeProvider?.name || 'AI'}
              {saveStatus === 'saving' && ' · saving…'}
              {saveStatus === 'saved' && ' · saved'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setSettingsOpen(true)}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs text-slate-500 hover:bg-slate-100 hover:text-slate-700 transition-colors"
          >
            <Settings className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">{settings.model}</span>
          </button>

          <div className="flex items-center bg-slate-100 rounded-xl p-1 gap-0.5">
            <ModeButton active={mode === 'table'} onClick={() => setMode('table')} icon={<LayoutGrid className="w-3.5 h-3.5" />} label="Table" />
            <ModeButton active={mode === 'chat'} onClick={() => setMode('chat')} icon={<MessageSquare className="w-3.5 h-3.5" />} label="Chat" />
          </div>
        </div>
      </header>

      <main className="flex-1 min-h-0">
        {mode === 'table' ? <TableMode /> : <ChatMode />}
      </main>

      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  )
}

export default function App() {
  return (
    <SettingsProvider>
      <TableProvider>
        <AppContent />
      </TableProvider>
    </SettingsProvider>
  )
}

function ModeButton({ active, onClick, icon, label }: { active: boolean; onClick: () => void; icon: React.ReactNode; label: string }) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
        active ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'
      }`}
    >
      {icon}
      {label}
    </button>
  )
}
