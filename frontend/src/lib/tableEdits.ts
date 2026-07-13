import type { LeadRecord } from '../types'

const FIELD_ALIASES: Record<string, keyof LeadRecord> = {
  email: 'email',
  work_email: 'email',
  corporate_email: 'email',
  business_email: 'email',
  first_name: 'first_name',
  firstname: 'first_name',
  last_name: 'last_name',
  lastname: 'last_name',
  name: 'full_name',
  full_name: 'full_name',
  title: 'title',
  job_title: 'title',
  company: 'company',
  organization_name: 'company',
  company_name: 'company',
  organization: 'company',
  city: 'city',
  state: 'state',
  country: 'country',
  location: 'location',
  linkedin_url: 'linkedin_url',
  person_linkedin_url: 'linkedin_url',
  linkedin: 'linkedin_url',
}

function normalizeCol(name: string): string {
  return name.trim().toLowerCase().replace(/\s+/g, '_')
}

export function syncMappedFields(record: LeadRecord): LeadRecord {
  const next: LeadRecord = { ...record, raw: { ...record.raw } }
  for (const [col, val] of Object.entries(record.raw)) {
    const field = FIELD_ALIASES[normalizeCol(col)]
    if (!field || field === 'id') continue
    ;(next as Record<string, unknown>)[field] = val || null
  }
  return next
}

export function updateSourceCell(
  records: LeadRecord[],
  rowId: string,
  columnKey: string,
  value: string,
): LeadRecord[] {
  return records.map((record) => {
    if (record.id !== rowId) return record
    return syncMappedFields({
      ...record,
      raw: { ...record.raw, [columnKey]: value },
    })
  })
}

export function updateEnrichedCell(
  records: LeadRecord[],
  rowId: string,
  outputKey: string,
  value: string,
): LeadRecord[] {
  return records.map((record) =>
    record.id === rowId
      ? { ...record, enriched: { ...record.enriched, [outputKey]: value } }
      : record,
  )
}

export function addRow(records: LeadRecord[], columnKeys: string[]): LeadRecord[] {
  const raw = Object.fromEntries(columnKeys.map((key) => [key, '']))
  const row: LeadRecord = {
    id: `row-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    raw,
    enriched: {},
  }
  return [...records, row]
}

export function deleteRow(records: LeadRecord[], rowId: string): LeadRecord[] {
  return records.filter((record) => record.id !== rowId)
}

export function addSourceColumn(records: LeadRecord[], name: string): LeadRecord[] {
  const trimmed = name.trim()
  if (!trimmed) return records
  if (!records.length) {
    return [{ id: `row-${Date.now()}`, raw: { [trimmed]: '' }, enriched: {} }]
  }
  return records.map((record) => ({
    ...record,
    raw: { ...record.raw, [trimmed]: record.raw[trimmed] ?? '' },
  }))
}

export function deleteSourceColumn(records: LeadRecord[], key: string): LeadRecord[] {
  return records.map((record) => {
    const raw = { ...record.raw }
    delete raw[key]
    return syncMappedFields({ ...record, raw })
  })
}

export function renameSourceColumn(
  records: LeadRecord[],
  oldKey: string,
  newKey: string,
): LeadRecord[] {
  const trimmed = newKey.trim()
  if (!trimmed || trimmed === oldKey) return records
  return records.map((record) => {
    const raw = { ...record.raw }
    raw[trimmed] = raw[oldKey] ?? ''
    delete raw[oldKey]
    return syncMappedFields({ ...record, raw })
  })
}

export function clearEnrichedColumn(records: LeadRecord[], outputKey: string): LeadRecord[] {
  return records.map((record) => {
    const enriched = { ...record.enriched }
    delete enriched[outputKey]
    return { ...record, enriched }
  })
}
