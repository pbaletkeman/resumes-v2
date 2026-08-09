import { fileDownloadUrl } from '../../api/download'

interface DownloadsRowProps {
  outputFiles: Record<string, string> | null | undefined
}

const DOWNLOAD_LABELS: Record<string, string> = {
  resume_plaintext: 'Resume (txt)',
  resume_markdown: 'Resume (md)',
  resume_docx: 'Resume (docx)',
  resume_pdf: 'Resume (pdf)',
  cover_letter_plaintext: 'Cover letter (txt)',
  cover_letter_markdown: 'Cover letter (md)',
}

function DownloadsRow({ outputFiles }: DownloadsRowProps) {
  if (outputFiles === null || outputFiles === undefined) {
    return null
  }

  const files = Object.entries(outputFiles).filter(([key]) => key in DOWNLOAD_LABELS)

  if (files.length === 0) {
    return null
  }

  return (
    <section className="run-results">
      <h2>Downloads</h2>
      <div className="run-downloads">
        {files.map(([key, path]) => (
          <a
            key={key}
            className="p-button p-button-secondary p-button-outlined"
            href={fileDownloadUrl(path)}
          >
            <span className="pi pi-download p-button-icon" />
            <span className="p-button-label">{DOWNLOAD_LABELS[key]}</span>
          </a>
        ))}
      </div>
    </section>
  )
}

export default DownloadsRow