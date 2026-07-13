import type { ChatMessage, ColumnProposal, Enricher, LeadRecord, Provider, ProviderSettings } from './types'
import type { SavedTable, TableMeta } from './persistence/localTables'
import { EMPTY_API_KEY_STATUS, apiKeyHeaders, type ApiKeys, type ApiKeysStatus } from './keys'

const API = '/api'

export type EnrichOptions = {
  provider?: string
  model?: string
  customPrompt?: string
  columnName?: string
  rowIds?: string[]
}

function apiFetch(input: string, init?: RequestInit): Promise<Response> {
  const headers = new Headers(init?.headers)
  for (const [key, value] of Object.entries(apiKeyHeaders())) {
    headers.set(key, value)
  }
  return fetch(input, { ...init, headers })
}

export async function fetchApiKeyStatus(): Promise<ApiKeysStatus> {
  try {
    const res = await apiFetch(`${API}/settings/keys`)
    if (!res.ok) return EMPTY_API_KEY_STATUS
    return res.json()
  } catch {
    return EMPTY_API_KEY_STATUS
  }
}

export async function saveApiKeysRemote(keys: ApiKeys): Promise<ApiKeysStatus> {
  const res = await apiFetch(`${API}/settings/keys`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ keys }),
  })
  if (!res.ok) throw new Error('Failed to save API keys')
  return res.json()
}

export async function fetchProviders(): Promise<Provider[]> {
  const res = await apiFetch(`${API}/providers`)
  return res.json()
}

export async function fetchEnrichers(): Promise<Enricher[]> {
  const res = await apiFetch(`${API}/enrichers`)
  return res.json()
}

export async function uploadCsv(file: File): Promise<{ records: LeadRecord[]; count: number }> {
  const form = new FormData()
  form.append('file', file)
  const res = await apiFetch(`${API}/upload`, { method: 'POST', body: form })
  if (!res.ok) throw new Error('Upload failed')
  return res.json()
}

export async function loadSample(): Promise<{ records: LeadRecord[]; count: number }> {
  const res = await apiFetch(`${API}/sample`)
  return res.json()
}

export async function exportCsv(records: LeadRecord[]): Promise<Blob> {
  const res = await apiFetch(`${API}/export`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ records }),
  })
  return res.blob()
}

export async function streamEnrich(
  records: LeadRecord[],
  enricher: string,
  onEvent: (data: Record<string, unknown>) => void,
  options: EnrichOptions = {},
): Promise<LeadRecord[]> {
  const res = await apiFetch(`${API}/enrich/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      records,
      enricher,
      provider: options.provider,
      model: options.model,
      custom_prompt: options.customPrompt,
      column_name: options.columnName,
      row_ids: options.rowIds,
    }),
  })

  if (!res.ok || !res.body) throw new Error('Enrichment failed')

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let finalRecords = records

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      const data = JSON.parse(line.slice(6))
      onEvent(data)
      if (data.type === 'complete') finalRecords = data.records
    }
  }
  return finalRecords
}

export async function streamChat(
  messages: ChatMessage[],
  records: LeadRecord[],
  onEvent: (data: Record<string, unknown>) => void,
  settings?: ProviderSettings,
): Promise<LeadRecord[] | null> {
  const res = await apiFetch(`${API}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      messages: messages.map((m) => ({ role: m.role, content: m.content })),
      records,
      provider: settings?.providerId,
      model: settings?.model,
    }),
  })

  if (!res.ok || !res.body) throw new Error('Chat failed')

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let updatedRecords: LeadRecord[] | null = null

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      const data = JSON.parse(line.slice(6))
      onEvent(data)
      if (data.type === 'records') updatedRecords = data.records
    }
  }
  return updatedRecords
}

export async function streamSculptor(
  messages: ChatMessage[],
  records: LeadRecord[],
  columns: { enricherKey: string; label: string; customPrompt?: string; columnName?: string }[],
  onEvent: (data: Record<string, unknown>) => void,
  settings?: ProviderSettings,
  businessContext?: string,
): Promise<{ proposals: ColumnProposal[]; records: LeadRecord[] }> {
  const res = await apiFetch(`${API}/sculptor/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      messages: messages.map((m) => ({ role: m.role, content: m.content })),
      records,
      columns,
      provider: settings?.providerId,
      model: settings?.model,
      business_context: businessContext || null,
    }),
  })

  if (!res.ok || !res.body) throw new Error('Sculptor failed')

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  const proposals: ColumnProposal[] = []
  let finalRecords = records

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      const data = JSON.parse(line.slice(6))
      onEvent(data)
      if (data.type === 'proposal') proposals.push(data.proposal as ColumnProposal)
      if (data.type === 'records') finalRecords = data.records as LeadRecord[]
    }
  }
  return { proposals, records: finalRecords }
}

export async function fetchTables(): Promise<TableMeta[]> {
  try {
    const res = await apiFetch(`${API}/tables`)
    if (!res.ok) throw new Error('failed')
    const data = await res.json()
    return data.tables as TableMeta[]
  } catch {
    return []
  }
}

export async function fetchTable(id: string): Promise<SavedTable | null> {
  try {
    const res = await apiFetch(`${API}/tables/${id}`)
    if (!res.ok) return null
    return res.json()
  } catch {
    return null
  }
}

export async function saveTableRemote(table: SavedTable): Promise<SavedTable | null> {
  try {
    const method = table.id ? 'PUT' : 'POST'
    const url = table.id ? `${API}/tables/${table.id}` : `${API}/tables`
    const res = await apiFetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(table),
    })
    if (!res.ok) return null
    return res.json()
  } catch {
    return null
  }
}

export async function deleteTableRemote(id: string): Promise<boolean> {
  try {
    const res = await apiFetch(`${API}/tables/${id}`, { method: 'DELETE' })
    return res.ok
  } catch {
    return false
  }
}
