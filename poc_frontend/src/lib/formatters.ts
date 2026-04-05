export function formatRelativeTime(isoString: string): string {
  const utcString = isoString.endsWith('Z') ? isoString : isoString + 'Z'
  const now = Date.now()
  const then = new Date(utcString).getTime()
  const diffMs = now - then
  const diffSec = Math.floor(diffMs / 1000)
  if (diffSec < 60) return `${diffSec < 0 ? 0 : diffSec}s ago`
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHour = Math.floor(diffMin / 60)
  if (diffHour < 24) return `${diffHour}h ago`
  return new Date(utcString).toLocaleDateString()
}

export function formatDuration(startIso: string, endIso: string): string {
  const startUtc = startIso.endsWith('Z') ? startIso : startIso + 'Z'
  const endUtc = endIso.endsWith('Z') ? endIso : endIso + 'Z'
  const ms = new Date(endUtc).getTime() - new Date(startUtc).getTime()
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`
}

export function formatMs(ms: number | null): string {
  if (ms === null) return '—'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(2)}s`
}

export function truncate(str: string, len = 60): string {
  if (str.length <= len) return str
  return str.slice(0, len) + '…'
}

export function inputPreview(inputData: Record<string, unknown>): string {
  if (typeof inputData.text === 'string') return truncate(inputData.text)
  if (typeof inputData.url === 'string') return truncate(inputData.url as string)
  if (typeof inputData.file_path === 'string') return inputData.file_path as string
  return JSON.stringify(inputData).slice(0, 60)
}

export function languageName(code: string): string {
  try {
    return new Intl.DisplayNames(['en'], { type: 'language' }).of(code) ?? code
  } catch {
    return code
  }
}
