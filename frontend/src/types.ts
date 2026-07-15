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
  preview?: boolean
}

export type ColumnProposal = {
  column_name: string
  label: string
  enricher_key: string
  custom_prompt?: string
  reasoning?: string
}

export type WorkflowProposal = {
  name: string
  steps: ColumnProposal[]
  reasoning?: string
}

export type OutreachDraft = {
  lead_name: string
  lead_id?: string
  subject?: string
  opener: string
  full_email?: string
}

export type TableAnalysis = {
  stats: Record<string, unknown>
  insights?: {
    focus?: string
    insights?: string[]
    priority_segment?: string
  }
}

export type DiagnosisIssue = {
  severity: 'error' | 'warning' | 'info'
  issue: string
  fix: string
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
    if (v.winner && typeof v.winner === 'object') {
      const w = v.winner as Record<string, unknown>
      const cost = w.estimated_cost_usd != null ? ` ($${w.estimated_cost_usd})` : ''
      return `${w.title || w.idea || 'Offer'}${cost}`
    }
    if (v.best_hook) return String(v.best_hook)
    if (v.tier != null && v.score != null) return `${v.tier} (${v.score})`
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

export type SourceColumn = {
  key: string
  label: string
  get: (r: LeadRecord) => string | null | undefined
}

const DEFAULT_SOURCE_COLUMNS: SourceColumn[] = [
  { key: 'name', label: 'Name', get: (r) => displayName(r) },
  { key: 'email', label: 'Email', get: (r) => r.email },
  { key: 'title', label: 'Title', get: (r) => r.title },
  { key: 'company', label: 'Company', get: (r) => r.company },
  { key: 'location', label: 'Location', get: (r) => displayLocation(r) },
]

/** All CSV columns from imported data, preserving header order. */
export function sourceColumnsFromRecords(records: LeadRecord[]): SourceColumn[] {
  if (!records.length) return DEFAULT_SOURCE_COLUMNS

  const ordered: string[] = []
  const seen = new Set<string>()
  for (const key of Object.keys(records[0].raw)) {
    ordered.push(key)
    seen.add(key)
  }
  for (const record of records) {
    for (const key of Object.keys(record.raw)) {
      if (!seen.has(key)) {
        ordered.push(key)
        seen.add(key)
      }
    }
  }

  if (!ordered.length) return DEFAULT_SOURCE_COLUMNS

  return ordered.map((key) => ({
    key,
    label: key,
    get: (r) => r.raw[key] ?? null,
  }))
}
