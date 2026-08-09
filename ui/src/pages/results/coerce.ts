export function asRecord(value: unknown): Record<string, unknown> | null {
  if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
    return value as Record<string, unknown>
  }
  return null
}

export function asString(value: unknown): string | null {
  if (typeof value === 'string' && value.trim() !== '') {
    return value
  }
  return null
}

export function asStringList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return []
  }
  return value.filter((item): item is string => typeof item === 'string')
}

export function asStringMap(value: unknown): Record<string, string> {
  const record = asRecord(value)
  if (record === null) {
    return {}
  }
  const out: Record<string, string> = {}
  for (const [key, val] of Object.entries(record)) {
    const str = asString(val)
    if (str !== null) {
      out[key] = str
    }
  }
  return out
}

export function asObjectList(value: unknown): Record<string, unknown>[] {
  if (!Array.isArray(value)) {
    return []
  }
  return value.filter(
    (item): item is Record<string, unknown> =>
      typeof item === 'object' && item !== null && !Array.isArray(item),
  )
}

export function pickString(
  record: Record<string, unknown> | null,
  key: string,
): string | null {
  return record === null ? null : asString(record[key])
}

export function pickNumber(
  record: Record<string, unknown> | null,
  key: string,
): number | null {
  if (record === null) {
    return null
  }
  const value = record[key]
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

export function pickList(
  record: Record<string, unknown> | null,
  key: string,
): string[] {
  return record === null ? [] : asStringList(record[key])
}

export function pickObjectList(
  record: Record<string, unknown> | null,
  key: string,
): Record<string, unknown>[] {
  return record === null ? [] : asObjectList(record[key])
}

export function pickText(
  record: Record<string, unknown> | null,
  key: string,
): string | null {
  if (record === null) {
    return null
  }
  const value = record[key]
  if (typeof value === 'string') {
    return value.trim() === '' ? null : value
  }
  if (Array.isArray(value)) {
    const parts = value.map((item) => String(item))
    return parts.length === 0 ? null : parts.join(', ')
  }
  const nested = asRecord(value)
  if (nested === null) {
    return null
  }
  const parts: string[] = []
  for (const [k, val] of Object.entries(nested)) {
    if (val !== null && val !== undefined && val !== '') {
      parts.push(`${k}: ${String(val)}`)
    }
  }
  return parts.length === 0 ? null : parts.join(', ')
}

export function textFromValue(value: unknown, keys: string[]): string | null {
  if (typeof value === 'string') {
    return value.trim() === '' ? null : value
  }
  const record = asRecord(value)
  if (record === null) {
    return null
  }
  for (const key of keys) {
    const text = pickText(record, key)
    if (text !== null) {
      return text
    }
  }
  return null
}

export function pickMap(
  record: Record<string, unknown> | null,
  key: string,
): Record<string, string> {
  return record === null ? {} : asStringMap(record[key])
}