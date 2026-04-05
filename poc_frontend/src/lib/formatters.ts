import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import utc from 'dayjs/plugin/utc'
import timezone from 'dayjs/plugin/timezone'
import duration from 'dayjs/plugin/duration'

dayjs.extend(relativeTime)
dayjs.extend(utc)
dayjs.extend(timezone)
dayjs.extend(duration)

/**
 * Format timestamp to relative time string (e.g. '2 minutes ago').
 * Handles missing 'Z' suffix for UTC.
 */
export function formatRelativeTime(dateStr?: string | null): string {
  if (!dateStr) return '—'
  const d = dateStr.endsWith('Z') ? dateStr : `${dateStr}Z`
  return dayjs(d).fromNow()
}

/**
 * Format timestamp to a human-readable exact time (e.g. 'Apr 5, 2026, 15:14:56').
 */
export function formatExactTime(dateStr?: string | null): string {
  if (!dateStr) return '—'
  const d = dateStr.endsWith('Z') ? dateStr : `${dateStr}Z`
  return dayjs(d).format('MMM D, YYYY, HH:mm:ss')
}

/**
 * Calculate and format duration between two timestamps.
 */
export function formatDuration(startStr?: string | null, endStr?: string | null): string {
  if (!startStr || !endStr) return '—'
  const s = dayjs(startStr.endsWith('Z') ? startStr : `${startStr}Z`)
  const e = dayjs(endStr.endsWith('Z') ? endStr : `${endStr}Z`)
  const ms = e.diff(s)
  return formatMs(ms)
}

/**
 * Format milliseconds into human readable string.
 */
export function formatMs(ms: number): string {
  if (ms < 0) return '0ms'
  if (ms < 1000) return `${ms}ms`
  const sec = (ms / 1000).toFixed(1)
  if (parseFloat(sec) < 60) return `${sec}s`
  const min = (ms / 60000).toFixed(1)
  return `${min}m`
}

/**
 * Create a short preview of input data.
 */
export function inputPreview(data?: Record<string, unknown> | null): string {
  if (!data) return 'No input'
  const text = data.text || data.url || data.file_path || JSON.stringify(data)
  const str = String(text)
  return str.length > 100 ? `${str.slice(0, 100)}...` : str
}

/**
 * Map ISO language codes to human names.
 */
export function languageName(code: string): string {
  const names: Record<string, string> = {
    en: 'English',
    es: 'Spanish',
    fr: 'French',
    de: 'German',
    it: 'Italian',
    pt: 'Portuguese',
    ru: 'Russian',
    zh: 'Chinese',
    ja: 'Japanese',
    ko: 'Korean',
  }
  return names[code.toLowerCase()] || code.toUpperCase()
}
