import type { EnrichmentColumn, LeadRecord } from '../types'

export type TableMeta = {
  id: string
  name: string
  row_count: number
  updated_at?: string
  created_at?: string
}

export type SavedTable = {
  id: string
  name: string
  records: LeadRecord[]
  columns: EnrichmentColumn[]
  business_context?: string | null
  cac_limit_usd?: number | null
  created_at?: string
  updated_at?: string
}

const INDEX_KEY = 'claycomp-tables-index'
const ACTIVE_KEY = 'claycomp-active-table-id'
const tableKey = (id: string) => `claycomp-table-${id}`

export function getActiveTableId(): string | null {
  return localStorage.getItem(ACTIVE_KEY)
}

export function setActiveTableId(id: string) {
  localStorage.setItem(ACTIVE_KEY, id)
}

export function loadLocalIndex(): TableMeta[] {
  try {
    return JSON.parse(localStorage.getItem(INDEX_KEY) || '[]')
  } catch {
    return []
  }
}

function saveLocalIndex(index: TableMeta[]) {
  localStorage.setItem(INDEX_KEY, JSON.stringify(index))
}

export function loadLocalTable(id: string): SavedTable | null {
  try {
    const raw = localStorage.getItem(tableKey(id))
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function saveLocalTable(table: SavedTable) {
  const now = new Date().toISOString()
  const saved: SavedTable = {
    ...table,
    updated_at: now,
    created_at: table.created_at || now,
  }
  localStorage.setItem(tableKey(saved.id), JSON.stringify(saved))
  const index = loadLocalIndex().filter((t) => t.id !== saved.id)
  index.unshift({
    id: saved.id,
    name: saved.name,
    row_count: saved.records.length,
    updated_at: saved.updated_at,
    created_at: saved.created_at,
  })
  saveLocalIndex(index)
  return saved
}

export function deleteLocalTable(id: string) {
  localStorage.removeItem(tableKey(id))
  saveLocalIndex(loadLocalIndex().filter((t) => t.id !== id))
}

export function createEmptyTable(name = 'My Leads'): SavedTable {
  const id = crypto.randomUUID()
  return {
    id,
    name,
    records: [],
    columns: [],
    business_context: null,
    cac_limit_usd: 200,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  }
}
