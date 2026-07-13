export type ApiKeys = {
  OPENAI_API_KEY?: string
  PERPLEXITY_API_KEY?: string
  ANTHROPIC_API_KEY?: string
  GOOGLE_PLACES_API_KEY?: string
}

export const API_KEY_FIELDS = [
  { key: 'OPENAI_API_KEY' as const, label: 'OpenAI', hint: 'Chat, Sculptor, AI enrichments' },
  { key: 'PERPLEXITY_API_KEY' as const, label: 'Perplexity', hint: 'Web-aware AI provider' },
  { key: 'ANTHROPIC_API_KEY' as const, label: 'Anthropic', hint: 'Claude models' },
  { key: 'GOOGLE_PLACES_API_KEY' as const, label: 'Google Places', hint: 'Restaurant & review enrichments' },
]

const STORAGE_KEY = 'claycomp-api-keys'

export function loadApiKeys(): ApiKeys {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return JSON.parse(raw) as ApiKeys
  } catch {
    /* ignore */
  }
  return {}
}

export function saveApiKeys(keys: ApiKeys): void {
  const trimmed: ApiKeys = {}
  for (const [k, v] of Object.entries(keys)) {
    if (v?.trim()) trimmed[k as keyof ApiKeys] = v.trim()
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed))
}

export function apiKeyHeaders(): Record<string, string> {
  const keys = loadApiKeys()
  const filtered = Object.fromEntries(
    Object.entries(keys).filter(([, v]) => v?.trim()),
  )
  if (!Object.keys(filtered).length) return {}
  return { 'X-Claycomp-Keys': JSON.stringify(filtered) }
}
