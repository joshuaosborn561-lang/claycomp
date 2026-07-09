import { Settings, X } from 'lucide-react'
import { useSettings } from '../context/SettingsContext'

type Props = {
  open: boolean
  onClose: () => void
}

export default function SettingsModal({ open, onClose }: Props) {
  const { providers, settings, setSettings, activeProvider } = useSettings()

  if (!open) return null

  const selected = providers.find((p) => p.id === settings.providerId) || activeProvider

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-md bg-white rounded-2xl shadow-card border border-slate-200/80 animate-fade-in">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <Settings className="w-4 h-4 text-clay-500" />
            <h2 className="text-sm font-semibold">AI Provider</h2>
          </div>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-slate-100 text-slate-400">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          <div>
            <label className="text-xs font-medium text-slate-500 uppercase tracking-wide">Provider</label>
            <div className="mt-2 grid gap-2">
              {providers.map((p) => (
                <button
                  key={p.id}
                  onClick={() =>
                    setSettings({ providerId: p.id, model: p.default_model })
                  }
                  className={`flex items-center justify-between px-3 py-2.5 rounded-xl border text-left transition-all ${
                    settings.providerId === p.id
                      ? 'border-clay-400 bg-clay-50 ring-1 ring-clay-200'
                      : 'border-slate-200 hover:border-slate-300'
                  }`}
                >
                  <div>
                    <p className="text-sm font-medium text-slate-800">{p.name}</p>
                    <p className="text-[11px] text-slate-400 mt-0.5">{p.env_key}</p>
                  </div>
                  <span
                    className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${
                      p.configured
                        ? 'bg-emerald-50 text-emerald-600'
                        : 'bg-amber-50 text-amber-600'
                    }`}
                  >
                    {p.configured ? 'Ready' : 'No key'}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {selected && (
            <div>
              <label className="text-xs font-medium text-slate-500 uppercase tracking-wide">Model</label>
              <select
                value={settings.model}
                onChange={(e) => setSettings({ ...settings, model: e.target.value })}
                className="mt-2 w-full px-3 py-2 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-clay-300"
              >
                {selected.models.map((m: string) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>
          )}

          <p className="text-xs text-slate-400 leading-relaxed">
            Add API keys to your <code className="text-slate-500">.env</code> file. Provider
            applies to Chat, Sculptor, and AI enrichment columns.
          </p>
        </div>
      </div>
    </div>
  )
}
