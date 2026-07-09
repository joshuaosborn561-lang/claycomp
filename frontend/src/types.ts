export type LeadRecord = {
  id: string
  email?: string | null
  first_name?: string | null
  last_name?: string | null
  full_name?: string | null
  title?: string | null
  company?: string | null
  city?: string | null
  state?: string | null
  country?: string | null
  location?: string | null
  linkedin_url?: string | null
  raw: Record<string, string>
  enriched: Record<string, unknown>
}

export type Enricher = {
  key: string
  name: string
  description: string
  requires_api_key?: string | null
}

export type Provider = {
  id: string
  name: string
  env_key: string
  models: string[]
  default_model: string
  configured: boolean
}

export type ProviderSettings = {
  providerId: string
  model: string
}

export type EnrichmentColumn = {
  id: string
  enricherKey: string
  label: string
  columnName?: string
  customPrompt?: string
  provider?: string
  model?: string
  running?: boolean
}

export type ColumnProposal = {
  column_name: string
  label: string
  enricher_key: string
  custom_prompt?: string
  reasoning?: string
}

export type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  proposals?: ColumnProposal[]
}

export type AppMode = 'table' | 'chat'

export const DEFAULT_PROVIDER_SETTINGS: ProviderSettings = {
  providerId: 'openai',
  model: 'gpt-4o-mini',
}

export function displayName(r: LeadRecord): string {
  if (r.full_name) return r.full_name
  const parts = [r.first_name, r.last_name].filter(Boolean)
  return parts.join(' ') || r.email || r.id
}

export function displayLocation(r: LeadRecord): string {
  if (r.location) return r.location
  return [r.city, r.state, r.country].filter(Boolean).join(', ')
}

export function formatCell(value: unknown): string {
  if (value == null || value === '') return '—'
  if (typeof value === 'object') {
    const v = value as Record<string, unknown>
    if (v.talking_point) return String(v.talking_point)
    if (v.how_to_reference) return String(v.how_to_reference)
    if (v.nickname) return String(v.nickname)
    if (v.snippet) return String(v.snippet)
    if (v.team) return String(v.team)
    if (v.name) return String(v.name)
    if (v.value) return String(v.value)
    return JSON.stringify(value)
  }
  return String(value)
}

export function columnOutputKey(col: EnrichmentColumn, enrichers: Enricher[]): string {
  if (col.enricherKey === 'custom' && col.columnName) return col.columnName
  const e = enrichers.find((x) => x.key === col.enricherKey)
  return e?.name || col.label
}
