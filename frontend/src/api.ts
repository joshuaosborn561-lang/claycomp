import type { ChatMessage, ColumnProposal, Enricher, LeadRecord, Provider, ProviderSettings } from './types'

const API = '/api'

export type EnrichOptions = {
  provider?: string
  model?: string
  customPrompt?: string
  columnName?: string
  rowIds?: string[]
}

export async function fetchProviders(): Promise<Provider[]> {
  const res = await fetch(`${API}/providers`)
  return res.json()
}

export async function fetchEnrichers(): Promise<Enricher[]> {
  const res = await fetch(`${API}/enrichers`)
  return res.json()
}

export async function uploadCsv(file: File): Promise<{ records: LeadRecord[]; count: number }> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${API}/upload`, { method: 'POST', body: form })
  if (!res.ok) throw new Error('Upload failed')
  return res.json()
}

export async function loadSample(): Promise<{ records: LeadRecord[]; count: number }> {
  const res = await fetch(`${API}/sample`)
  return res.json()
}

export async function exportCsv(records: LeadRecord[]): Promise<Blob> {
  const res = await fetch(`${API}/export`, {
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
  const res = await fetch(`${API}/enrich/stream`, {
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
  const res = await fetch(`${API}/chat/stream`, {
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
  columns: { enricherKey: string; label: string }[],
  onEvent: (data: Record<string, unknown>) => void,
  settings?: ProviderSettings,
): Promise<{ proposals: ColumnProposal[] }> {
  const res = await fetch(`${API}/sculptor/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      messages: messages.map((m) => ({ role: m.role, content: m.content })),
      records,
      columns,
      provider: settings?.providerId,
      model: settings?.model,
    }),
  })

  if (!res.ok || !res.body) throw new Error('Sculptor failed')

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  const proposals: ColumnProposal[] = []

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
    }
  }
  return { proposals }
}
