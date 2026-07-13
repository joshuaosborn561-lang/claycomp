import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { fetchProviders } from '../api'
import { loadApiKeys, saveApiKeys, type ApiKeys } from '../keys'
import { DEFAULT_PROVIDER_SETTINGS, type Provider, type ProviderSettings } from '../types'

const STORAGE_KEY = 'claycomp-provider-settings'

type SettingsContextValue = {
  providers: Provider[]
  settings: ProviderSettings
  setSettings: (s: ProviderSettings) => void
  activeProvider: Provider | undefined
  apiKeys: ApiKeys
  setApiKeys: (keys: ApiKeys) => void
  refreshProviders: () => Promise<void>
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
  const [apiKeys, setApiKeysState] = useState<ApiKeys>(loadApiKeys)

  const refreshProviders = useCallback(async () => {
    const list = await fetchProviders()
    setProviders(list)
  }, [])

  useEffect(() => {
    refreshProviders()
  }, [refreshProviders])

  const setSettings = (s: ProviderSettings) => {
    setSettingsState(s)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(s))
  }

  const setApiKeys = (keys: ApiKeys) => {
    saveApiKeys(keys)
    setApiKeysState(keys)
    refreshProviders()
  }

  const activeProvider = providers.find((p) => p.id === settings.providerId)

  return (
    <SettingsContext.Provider
      value={{ providers, settings, setSettings, activeProvider, apiKeys, setApiKeys, refreshProviders }}
    >
      {children}
    </SettingsContext.Provider>
  )
}

export function useSettings() {
  const ctx = useContext(SettingsContext)
  if (!ctx) throw new Error('useSettings must be used within SettingsProvider')
  return ctx
}
