import { Key, Settings, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { API_KEY_FIELDS } from '../keys'
import { useSettings } from '../context/SettingsContext'

type Props = {
  open: boolean
  onClose: () => void
}

export default function SettingsModal({ open, onClose }: Props) {
  const { providers, settings, setSettings, activeProvider, apiKeys, setApiKeys } = useSettings()
  const [draftKeys, setDraftKeys] = useState(apiKeys)
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({})

  useEffect(() => {
    if (open) setDraftKeys(apiKeys)
  }, [open, apiKeys])

  if (!open) return null

  const selected = providers.find((p) => p.id === settings.providerId) || activeProvider

  const handleSaveKeys = () => {
    setApiKeys(draftKeys)
  }

  const hasDraftChanges = JSON.stringify(draftKeys) !== JSON.stringify(apiKeys)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-md max-h-[90vh] overflow-y-auto bg-white rounded-2xl shadow-card border border-slate-200/80 animate-fade-in">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 sticky top-0 bg-white z-10">
          <div className="flex items-center gap-2">
            <Settings className="w-4 h-4 text-clay-500" />
            <h2 className="text-sm font-semibold">Settings</h2>
          </div>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-slate-100 text-slate-400">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-5 space-y-6">
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Key className="w-3.5 h-3.5 text-slate-400" />
              <label className="text-xs font-medium text-slate-500 uppercase tracking-wide">API Keys</label>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed mb-3">
              Keys are stored in your browser only and sent with each request over HTTPS. Server env vars
              are used as a fallback when a key is not set here.
            </p>
            <div className="space-y-3">
              {API_KEY_FIELDS.map((field) => (
                <div key={field.key}>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-xs font-medium text-slate-600">{field.label}</label>
                    <span className="text-[10px] text-slate-400">{field.hint}</span>
                  </div>
                  <div className="relative">
                    <input
                      type={showKeys[field.key] ? 'text' : 'password'}
                      value={draftKeys[field.key] || ''}
                      onChange={(e) =>
                        setDraftKeys((prev) => ({ ...prev, [field.key]: e.target.value }))
                      }
                      placeholder={apiKeys[field.key] ? '••••••••' : `Paste ${field.label} key`}
                      className="w-full px-3 py-2 pr-16 rounded-xl border border-slate-200 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-clay-300"
                      autoComplete="off"
                    />
                    <button
                      type="button"
                      onClick={() => setShowKeys((s) => ({ ...s, [field.key]: !s[field.key] }))}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] text-slate-400 hover:text-slate-600 px-2 py-1"
                    >
                      {showKeys[field.key] ? 'Hide' : 'Show'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
            {hasDraftChanges && (
              <button
                onClick={handleSaveKeys}
                className="mt-3 w-full py-2 rounded-xl bg-clay-500 text-white text-sm font-medium hover:bg-clay-600 transition-colors"
              >
                Save API keys
              </button>
            )}
          </div>

          <div className="border-t border-slate-100 pt-5">
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
        </div>
      </div>
    </div>
  )
}
