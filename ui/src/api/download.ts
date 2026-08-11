/**
 * URL helpers for downloading rendered output files.
 *
 * The backend serves rendered files from ``GET /api/outputs/{filename}``
 * (``app/main.py``), reading them out of the ``output/`` directory.
 * ``outputDownloadUrl`` builds a URL for a bare filename; ``fileDownloadUrl``
 * accepts the dir-qualified ``path`` keys that the file listings return (e.g.
 * ``output/2026/resume.md``) and reduces them to the basename the outputs
 * route expects.
 */

/** Build the download URL for a rendered output file by name. */
export function outputDownloadUrl(name: string): string {
  return `/api/outputs/${encodeURIComponent(name)}`
}

/**
 * Build a download URL from a dir-qualified file path (as returned by
 * ``FileMeta.path``).  Normalizes Windows backslashes, takes the basename, and
 * delegates to ``outputDownloadUrl``.
 */
export function fileDownloadUrl(path: string): string {
  const normalized = path.replace(/\\/g, '/')
  const basename = normalized.split('/').pop() ?? ''
  return outputDownloadUrl(basename)
}