export function outputDownloadUrl(name: string): string {
  return `/api/outputs/${encodeURIComponent(name)}`
}

export function fileDownloadUrl(path: string): string {
  const normalized = path.replace(/\\/g, '/')
  const basename = normalized.split('/').pop() ?? ''
  return outputDownloadUrl(basename)
}