import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { fetchApiKeyStatus, fetchProviders, saveApiKeysRemote } from '../api'
import { API_KEY_FIELDS, EMPTY_API_KEY_STATUS, type ApiKeys, type ApiKeysStatus } from '../keys'
import { DEFAULT_PROVIDER_SETTINGS, type Provider, type ProviderSettings } from '../types'

const STORAGE_KEY = 'claycomp-provider-settings'

type SettingsContextValue = {
  providers: Provider[]
  settings: ProviderSettings
  setSettings: (s: ProviderSettings) => void
  activeProvider: Provider | undefined
  apiKeyStatus: ApiKeysStatus
  setApiKeys: (keys: ApiKeys) => Promise<void>
  refreshProviders: () => Promise<void>
  refreshApiKeys: () => Promise<void>
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
  const [apiKeyStatus, setApiKeyStatus] = useState<ApiKeysStatus>(EMPTY_API_KEY_STATUS)

  const refreshProviders = useCallback(async () => {
    const list = await fetchProviders()
    setProviders(list)
  }, [])

  const refreshApiKeys = useCallback(async () => {
    const status = await fetchApiKeyStatus()
    setApiKeyStatus(status)
  }, [])

  useEffect(() => {
    refreshApiKeys().then(() => refreshProviders())
  }, [refreshApiKeys, refreshProviders])

  const setSettings = (s: ProviderSettings) => {
    setSettingsState(s)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(s))
  }

  const setApiKeys = async (keys: ApiKeys) => {
    const status = await saveApiKeysRemote(keys)
    setApiKeyStatus(status)
    await refreshProviders()
  }

  const activeProvider = providers.find((p) => p.id === settings.providerId)

  return (
    <SettingsContext.Provider
      value={{
        providers,
        settings,
        setSettings,
        activeProvider,
        apiKeyStatus,
        setApiKeys,
        refreshProviders,
        refreshApiKeys,
      }}
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

export function isKeyConfigured(status: ApiKeysStatus, key: (typeof API_KEY_FIELDS)[number]['key']): boolean {
  return status.keys[key]?.set ?? false
}
