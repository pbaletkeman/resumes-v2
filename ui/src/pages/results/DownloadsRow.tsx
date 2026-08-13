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
  cover_letter_docx: 'Cover letter (docx)',
  cover_letter_pdf: 'Cover letter (pdf)',
  resume_modern_plaintext: 'Resume Modern (txt)',
  resume_modern_markdown: 'Resume Modern (md)',
  resume_modern_docx: 'Resume Modern (docx)',
  resume_modern_pdf: 'Resume Modern (pdf)',
  resume_classic_plaintext: 'Resume Classic (txt)',
  resume_classic_markdown: 'Resume Classic (md)',
  resume_classic_docx: 'Resume Classic (docx)',
  resume_classic_pdf: 'Resume Classic (pdf)',
  resume_minimal_plaintext: 'Resume Minimal (txt)',
  resume_minimal_markdown: 'Resume Minimal (md)',
  resume_minimal_docx: 'Resume Minimal (docx)',
  resume_minimal_pdf: 'Resume Minimal (pdf)',
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