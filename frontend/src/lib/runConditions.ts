import type { Enricher, EnrichmentColumn, LeadRecord, RunCondition } from '../types'
import { columnOutputKey, formatCell } from '../types'

function nonempty(value: unknown): boolean {
  if (value == null) return false
  if (typeof value === 'string') return value.trim().length > 0
  if (typeof value === 'object') {
    const obj = value as Record<string, unknown>
    if (typeof obj.email === 'string' && obj.email.includes('@')) return true
    if (typeof obj.value === 'string' && obj.value.trim()) return true
    const formatted = formatCell(value)
    return formatted !== '—' && formatted.trim().length > 0
  }
  return String(value).trim().length > 0
}

/** Resolve a source field from mapped lead fields or raw CSV columns. */
export function getSourceFieldValue(record: LeadRecord, field: string): unknown {
  const key = field.trim()
  if (!key) return null
  const lower = key.toLowerCase().replace(/\s+/g, '_')

  const mapped: Record<string, unknown> = {
    email: record.email,
    first_name: record.first_name,
    last_name: record.last_name,
    full_name: record.full_name,
    title: record.title,
    company: record.company,
    city: record.city,
    state: record.state,
    country: record.country,
    location: record.location,
    linkedin_url: record.linkedin_url,
  }
  if (lower in mapped && nonempty(mapped[lower])) return mapped[lower]

  if (nonempty(record.raw[key])) return record.raw[key]
  for (const [rawKey, rawVal] of Object.entries(record.raw)) {
    if (rawKey.toLowerCase().replace(/\s+/g, '_') === lower && nonempty(rawVal)) return rawVal
  }

  // Common email aliases in imported sheets
  if (lower === 'email') {
    for (const [rawKey, rawVal] of Object.entries(record.raw)) {
      const nk = rawKey.toLowerCase().replace(/\s+/g, '_')
      if (['work_email', 'corporate_email', 'business_email', 'email_address'].includes(nk) && nonempty(rawVal)) {
        return rawVal
      }
    }
  }
  return null
}

export function hasFilledOutput(
  record: LeadRecord,
  col: EnrichmentColumn,
  enrichers: Enricher[],
): boolean {
  const outputKey = columnOutputKey(col, enrichers)
  const value = record.enriched[outputKey]
  if (!nonempty(value)) return false
  // Ignore enriched payloads that only report skip/miss without an email
  if (typeof value === 'object' && value && 'email' in (value as object)) {
    const email = (value as { email?: unknown }).email
    return typeof email === 'string' && email.includes('@')
  }
  return true
}

export function shouldSkipRow(
  record: LeadRecord,
  col: EnrichmentColumn,
  enrichers: Enricher[],
): { skip: boolean; reason?: string } {
  const cond: RunCondition = col.runCondition || {}
  if (cond.skipIfOutputFilled && hasFilledOutput(record, col, enrichers)) {
    return { skip: true, reason: 'output already filled' }
  }
  if (cond.skipIfSourceFilled) {
    const sourceVal = getSourceFieldValue(record, cond.skipIfSourceFilled)
    if (nonempty(sourceVal)) {
      return { skip: true, reason: `${cond.skipIfSourceFilled} already filled` }
    }
  }
  if (cond.requireSourceFields?.length) {
    for (const field of cond.requireSourceFields) {
      if (!nonempty(getSourceFieldValue(record, field))) {
        return { skip: true, reason: `missing ${field}` }
      }
    }
  }
  return { skip: false }
}

export function rowsEligibleForColumn(
  records: LeadRecord[],
  col: EnrichmentColumn,
  enrichers: Enricher[],
): { eligible: LeadRecord[]; skipped: number } {
  const eligible: LeadRecord[] = []
  let skipped = 0
  for (const record of records) {
    if (shouldSkipRow(record, col, enrichers).skip) skipped += 1
    else eligible.push(record)
  }
  return { eligible, skipped }
}

export function defaultRunConditionForEnricher(enricherKey: string): RunCondition | undefined {
  if (enricherKey === 'email_waterfall') {
    return {
      skipIfOutputFilled: true,
      skipIfSourceFilled: 'email',
    }
  }
  return { skipIfOutputFilled: true }
}

export function summarizeRunCondition(cond?: RunCondition): string | null {
  if (!cond) return null
  const parts: string[] = []
  if (cond.skipIfOutputFilled) parts.push('skip if already filled')
  if (cond.skipIfSourceFilled) parts.push(`skip if ${cond.skipIfSourceFilled} exists`)
  if (cond.requireSourceFields?.length) {
    parts.push(`require ${cond.requireSourceFields.join(', ')}`)
  }
  return parts.length ? parts.join(' · ') : null
}
