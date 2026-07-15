export type ApiKeys = {
  OPENAI_API_KEY?: string
  PERPLEXITY_API_KEY?: string
  ANTHROPIC_API_KEY?: string
  GOOGLE_PLACES_API_KEY?: string
  AI_ARK_API_KEY?: string
  PROSPEO_API_KEY?: string
}

export type ApiKeyStatus = {
  set: boolean
  masked: string | null
}

export type ApiKeysStatus = {
  keys: Record<string, ApiKeyStatus>
  storage: string
  setup_required?: boolean
  setup_message?: string | null
}

export const API_KEY_FIELDS = [
  { key: 'OPENAI_API_KEY' as const, label: 'OpenAI', hint: 'Chat, Sculptor, AI enrichments' },
  { key: 'PERPLEXITY_API_KEY' as const, label: 'Perplexity', hint: 'Web-aware AI provider' },
  { key: 'ANTHROPIC_API_KEY' as const, label: 'Anthropic', hint: 'Claude models' },
  { key: 'GOOGLE_PLACES_API_KEY' as const, label: 'Google Places', hint: 'Restaurant & review enrichments' },
  { key: 'AI_ARK_API_KEY' as const, label: 'AI Ark', hint: 'Email finder waterfall (docs.ai-ark.com — X-TOKEN)' },
  { key: 'PROSPEO_API_KEY' as const, label: 'Prospeo', hint: 'Email finder waterfall (X-KEY)' },
]

export const EMPTY_API_KEY_STATUS: ApiKeysStatus = {
  keys: Object.fromEntries(API_KEY_FIELDS.map((f) => [f.key, { set: false, masked: null }])),
  storage: 'file',
}
