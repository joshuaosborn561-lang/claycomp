import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { fetchProviders } from '../api'
import { DEFAULT_PROVIDER_SETTINGS, type Provider, type ProviderSettings } from '../types'

const STORAGE_KEY = 'claycomp-provider-settings'

type SettingsContextValue = {
  providers: Provider[]
  settings: ProviderSettings
  setSettings: (s: ProviderSettings) => void
  activeProvider: Provider | undefined
}

const SettingsContext = createContext<SettingsContextValue | null>(null)

function loadSettings(): ProviderSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return JSON.parse(raw) as ProviderSettings
  } catch {
    /* ignore */
  }
  return DEFAULT_PROVIDER_SETTINGS
}

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [providers, setProviders] = useState<Provider[]>([])
  const [settings, setSettingsState] = useState<ProviderSettings>(loadSettings)

  useEffect(() => {
    fetchProviders().then(setProviders)
  }, [])

  const setSettings = (s: ProviderSettings) => {
    setSettingsState(s)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(s))
  }

  const activeProvider = providers.find((p) => p.id === settings.providerId)

  return (
    <SettingsContext.Provider value={{ providers, settings, setSettings, activeProvider }}>
      {children}
    </SettingsContext.Provider>
  )
}

export function useSettings() {
  const ctx = useContext(SettingsContext)
  if (!ctx) throw new Error('useSettings must be used within SettingsProvider')
  return ctx
}
