import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { fetchEnrichers, fetchTable, fetchTables, loadSample, saveTableRemote } from '../api'
import {
  createEmptyTable,
  deleteLocalTable,
  getActiveTableId,
  loadLocalIndex,
  loadLocalTable,
  saveLocalTable,
  setActiveTableId,
} from '../persistence/localTables'
import type { EnrichmentColumn, Enricher, LeadRecord } from '../types'
import type { SavedTable, TableMeta } from '../persistence/localTables'

export type SaveStatus = 'idle' | 'saving' | 'saved' | 'local' | 'error'

export const DEFAULT_EMAIL_PROVIDERS = ['ai_ark', 'prospeo'] as const

type TableContextValue = {
  tableId: string
  tableName: string
  records: LeadRecord[]
  columns: EnrichmentColumn[]
  businessContext: string
  emailProviders: string[]
  tables: TableMeta[]
  enrichers: Enricher[]
  saveStatus: SaveStatus
  loading: boolean
  setTableName: (name: string) => void
  setRecords: (records: LeadRecord[]) => void
  setColumns: (columns: EnrichmentColumn[]) => void
  setBusinessContext: (ctx: string) => void
  setEmailProviders: (providers: string[]) => void
  createTable: (name?: string) => Promise<void>
  switchTable: (id: string) => Promise<void>
  deleteTable: (id: string) => Promise<void>
}

const TableContext = createContext<TableContextValue | null>(null)

function normalizeEmailProviders(providers: string[] | null | undefined): string[] {
  const out: string[] = []
  const seen = new Set<string>()
  for (const p of providers || DEFAULT_EMAIL_PROVIDERS) {
    const key = p.trim().toLowerCase()
    if ((key === 'ai_ark' || key === 'prospeo') && !seen.has(key)) {
      out.push(key)
      seen.add(key)
    }
  }
  if (!seen.has('ai_ark')) out.push('ai_ark')
  return out.length ? out : [...DEFAULT_EMAIL_PROVIDERS]
}

function tableSnapshot(
  id: string,
  name: string,
  records: LeadRecord[],
  columns: EnrichmentColumn[],
  businessContext: string,
  emailProviders: string[],
  created_at?: string,
): SavedTable {
  return {
    id,
    name,
    records,
    columns,
    business_context: businessContext,
    email_providers: emailProviders,
    created_at,
  }
}

export function TableProvider({ children }: { children: ReactNode }) {
  const [tableId, setTableId] = useState('')
  const [tableName, setTableNameState] = useState('My Leads')
  const [records, setRecordsState] = useState<LeadRecord[]>([])
  const [columns, setColumnsState] = useState<EnrichmentColumn[]>([])
  const [businessContext, setBusinessContextState] = useState('')
  const [emailProviders, setEmailProvidersState] = useState<string[]>([...DEFAULT_EMAIL_PROVIDERS])
  const [tables, setTables] = useState<TableMeta[]>([])
  const [enrichers, setEnrichers] = useState<Enricher[]>([])
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle')
  const [loading, setLoading] = useState(true)
  const createdAtRef = useRef<string | undefined>()
  const saveTimer = useRef<ReturnType<typeof setTimeout>>()

  const applyTable = (t: SavedTable) => {
    setTableId(t.id)
    setTableNameState(t.name)
    setRecordsState(t.records)
    setColumnsState(t.columns || [])
    setBusinessContextState(t.business_context || '')
    setEmailProvidersState(normalizeEmailProviders(t.email_providers))
    createdAtRef.current = t.created_at
    setActiveTableId(t.id)
  }

  const refreshIndex = useCallback(async () => {
    const remote = await fetchTables()
    const local = loadLocalIndex()
    const merged = new Map<string, TableMeta>()
    for (const t of [...remote, ...local]) merged.set(t.id, t)
    setTables([...merged.values()].sort((a, b) => (b.updated_at || '').localeCompare(a.updated_at || '')))
  }, [])

  const persist = useCallback(
    async (
      id: string,
      name: string,
      recs: LeadRecord[],
      cols: EnrichmentColumn[],
      ctx: string,
      providers: string[],
    ) => {
      const snap = tableSnapshot(id, name, recs, cols, ctx, providers, createdAtRef.current)
      setSaveStatus('saving')
      saveLocalTable(snap)
      const remote = await saveTableRemote(snap)
      setSaveStatus(remote ? 'saved' : 'local')
      await refreshIndex()
    },
    [refreshIndex],
  )

  const scheduleSave = useCallback(
    (
      id: string,
      name: string,
      recs: LeadRecord[],
      cols: EnrichmentColumn[],
      ctx: string,
      providers: string[],
    ) => {
      if (!id) return
      if (saveTimer.current) clearTimeout(saveTimer.current)
      saveTimer.current = setTimeout(() => persist(id, name, recs, cols, ctx, providers), 1200)
    },
    [persist],
  )

  useEffect(() => {
    async function init() {
      const e = await fetchEnrichers()
      setEnrichers(e)
      await refreshIndex()

      const activeId = getActiveTableId()
      let table: SavedTable | null = null

      if (activeId) {
        table = (await fetchTable(activeId)) || loadLocalTable(activeId)
      }

      if (!table) {
        const index = loadLocalIndex()
        if (index.length > 0) {
          table = loadLocalTable(index[0].id)
        }
      }

      if (!table) {
        const sample = await loadSample()
        const empty = createEmptyTable('My Leads')
        empty.records = sample.records
        table = saveLocalTable(empty)
        await saveTableRemote(table)
      }

      applyTable(table!)
      await refreshIndex()
      setLoading(false)
    }
    init()
  }, [refreshIndex])

  const setTableName = (name: string) => {
    setTableNameState(name)
    scheduleSave(tableId, name, records, columns, businessContext, emailProviders)
  }

  const setRecords = (recs: LeadRecord[]) => {
    setRecordsState(recs)
    scheduleSave(tableId, tableName, recs, columns, businessContext, emailProviders)
  }

  const setColumns = (cols: EnrichmentColumn[]) => {
    setColumnsState(cols)
    scheduleSave(tableId, tableName, records, cols, businessContext, emailProviders)
  }

  const setBusinessContext = (ctx: string) => {
    setBusinessContextState(ctx)
    scheduleSave(tableId, tableName, records, columns, ctx, emailProviders)
  }

  const setEmailProviders = (providers: string[]) => {
    const next = normalizeEmailProviders(providers)
    setEmailProvidersState(next)
    scheduleSave(tableId, tableName, records, columns, businessContext, next)
  }

  const createTable = async (name = 'New Table') => {
    const t = createEmptyTable(name)
    saveLocalTable(t)
    await saveTableRemote(t)
    applyTable(t)
    await refreshIndex()
  }

  const switchTable = async (id: string) => {
    const t = (await fetchTable(id)) || loadLocalTable(id)
    if (t) {
      applyTable(t)
      setSaveStatus('saved')
    }
  }

  const deleteTable = async (id: string) => {
    deleteLocalTable(id)
    await refreshIndex()
    if (id === tableId) {
      const remaining = loadLocalIndex()
      if (remaining.length > 0) {
        await switchTable(remaining[0].id)
      } else {
        await createTable('My Leads')
      }
    }
  }

  return (
    <TableContext.Provider
      value={{
        tableId,
        tableName,
        records,
        columns,
        businessContext,
        emailProviders,
        tables,
        enrichers,
        saveStatus,
        loading,
        setTableName,
        setRecords,
        setColumns,
        setBusinessContext,
        setEmailProviders,
        createTable,
        switchTable,
        deleteTable,
      }}
    >
      {children}
    </TableContext.Provider>
  )
}

export function useTable() {
  const ctx = useContext(TableContext)
  if (!ctx) throw new Error('useTable must be used within TableProvider')
  return ctx
}
