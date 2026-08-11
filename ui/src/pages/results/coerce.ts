/**
 * Coercion helpers for result data.
 *
 * The backend result dicts (the `StageResult<T>` values inside
 * `PipelineRunResponse`) are loosely typed: a field may be missing, null, a
 * different type than expected, or a string where a list is expected.  These
 * helpers coerce unknown shapes safely — they never throw and always return a
 * predictable default (`null` for singletons, `[]`/`{}` for collections) — so
 * the tab components can render declaratively without defensive checks.
 */

/** Return `value` as a plain object when it is one, else `null` (arrays excluded). */
export function asRecord(value: unknown): Record<string, unknown> | null {
  if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
    return value as Record<string, unknown>
  }
  return null
}

/** Return `value` as a non-blank string (trimmed check), else `null`. Empty strings are dropped. */
export function asString(value: unknown): string | null {
  if (typeof value === 'string' && value.trim() !== '') {
    return value
  }
  return null
}

/** Return `value` as an array of strings, filtering out non-string elements. `[]` for non-arrays. */
export function asStringList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return []
  }
  return value.filter((item): item is string => typeof item === 'string')
}

/** Return `value` as a string map, keeping only entries whose values coerce to a non-blank string. */
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

/** Return `value` as an array of plain objects, filtering out non-object elements. `[]` for non-arrays. */
export function asObjectList(value: unknown): Record<string, unknown>[] {
  if (!Array.isArray(value)) {
    return []
  }
  return value.filter(
    (item): item is Record<string, unknown> =>
      typeof item === 'object' && item !== null && !Array.isArray(item),
  )
}

/** Pick `record[key]` as a non-blank string, else `null`. `null` for a null record. */
export function pickString(
  record: Record<string, unknown> | null,
  key: string,
): string | null {
  if (record === null) {
    return null
  }
  return asString(record[key])
}

/**
 * Pick `record[key]` as a finite number.  Accepts a number directly or a
 * numeric string; returns `null` for anything else (and for a null record).
 */
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

/** Pick `record[key]` as a string list. `[]` for a null record or non-array value. */
export function pickList(
  record: Record<string, unknown> | null,
  key: string,
): string[] {
  if (record === null) {
    return []
  }
  return asStringList(record[key])
}

/** Pick `record[key]` as an object list. `[]` for a null record or non-array value. */
export function pickObjectList(
  record: Record<string, unknown> | null,
  key: string,
): Record<string, unknown>[] {
  if (record === null) {
    return []
  }
  return asObjectList(record[key])
}

/**
 * Pick `record[key]` as displayable text, tolerating several shapes: a string
 * (blank -> `null`), an array (joined with `', '`), or a nested object
 * (`key: value` pairs joined with `', '`).  `null` when nothing usable exists.
 */
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

/**
 * Find the first non-empty text among the given `keys` on `value` (a string or
 * a record).  `null` when `value` is neither or none of the keys has text.
 */
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

/** Pick `record[key]` as a string map. `{}` for a null record or non-object value. */
export function pickMap(
  record: Record<string, unknown> | null,
  key: string,
): Record<string, string> {
  if (record === null) {
    return {}
  }
  return asStringMap(record[key])
}
