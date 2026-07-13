export type ApiKeys = {
  OPENAI_API_KEY?: string
  PERPLEXITY_API_KEY?: string
  ANTHROPIC_API_KEY?: string
  GOOGLE_PLACES_API_KEY?: string
}

export type ApiKeyStatus = {
  set: boolean
  masked: string | null
}

export type ApiKeysStatus = {
  keys: Record<string, ApiKeyStatus>
  storage: string
}

export const API_KEY_FIELDS = [
  { key: 'OPENAI_API_KEY' as const, label: 'OpenAI', hint: 'Chat, Sculptor, AI enrichments' },
  { key: 'PERPLEXITY_API_KEY' as const, label: 'Perplexity', hint: 'Web-aware AI provider' },
  { key: 'ANTHROPIC_API_KEY' as const, label: 'Anthropic', hint: 'Claude models' },
  { key: 'GOOGLE_PLACES_API_KEY' as const, label: 'Google Places', hint: 'Restaurant & review enrichments' },
]

const STORAGE_KEY = 'claycomp-api-keys'

export const EMPTY_API_KEY_STATUS: ApiKeysStatus = {
  keys: Object.fromEntries(API_KEY_FIELDS.map((f) => [f.key, { set: false, masked: null }])),
  storage: 'file',
}

export function maskApiKey(value: string): string {
  if (value.length <= 8) return '••••••••'
  return `${value.slice(0, 4)}...${value.slice(-4)}`
}

export function loadApiKeys(): ApiKeys {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return JSON.parse(raw) as ApiKeys
  } catch {
    /* ignore */
  }
  return {}
}

export function saveApiKeys(updates: ApiKeys): ApiKeys {
  const current = loadApiKeys()
  for (const field of API_KEY_FIELDS) {
    const value = updates[field.key]
    if (value === undefined) continue
    const trimmed = value.trim()
    if (trimmed) current[field.key] = trimmed
    else delete current[field.key]
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(current))
  return current
}

export function apiKeyHeaders(): Record<string, string> {
  const keys = loadApiKeys()
  const filtered = Object.fromEntries(
    Object.entries(keys).filter(([, v]) => v?.trim()),
  )
  if (!Object.keys(filtered).length) return {}
  return { 'X-Claycomp-Keys': JSON.stringify(filtered) }
}

export function mergeKeyStatus(server: ApiKeysStatus, local: ApiKeys = loadApiKeys()): ApiKeysStatus {
  const keys: Record<string, ApiKeyStatus> = { ...server.keys }
  for (const field of API_KEY_FIELDS) {
    const value = local[field.key]?.trim()
    if (value) {
      keys[field.key] = { set: true, masked: maskApiKey(value) }
    }
  }
  return { ...server, keys }
}

export function hasLocalApiKey(key: (typeof API_KEY_FIELDS)[number]['key']): boolean {
  return Boolean(loadApiKeys()[key]?.trim())
}
