import { useState } from 'react'
import { Button } from 'primereact/button'
import { Column } from 'primereact/column'
import { ConfirmDialog } from 'primereact/confirmdialog'
import { DataTable } from 'primereact/datatable'
import { Dropdown } from 'primereact/dropdown'
import { InputText } from 'primereact/inputtext'
import { TabMenu } from 'primereact/tabmenu'
import { fileDownloadUrl } from '../api/download'
import { useDeleteFiles, useFiles } from '../api/hooks'
import type { FileMeta } from '../api/types'
import { useToast } from '../toast/ToastContext'

type FileKind = 'generated' | 'uploaded'

// ---------------------------------------------------------------------------
// File listing configuration
// ---------------------------------------------------------------------------
// The listing-kind toggle, the search/type/sort filter choices, and the
// page-size options offered by the lazy DataTable paginator. All four drive
// the query params passed to `useFiles(kind, params)`.

const KIND_OPTIONS: { label: string; value: FileKind }[] = [
  { label: 'Generated', value: 'generated' },
  { label: 'Uploaded', value: 'uploaded' },
]

const PAGE_SIZE_OPTIONS = [
  { label: '5', value: 5 },
  { label: '10', value: 10 },
  { label: '20', value: 20 },
  { label: '50', value: 50 },
]

const FILE_TYPE_OPTIONS = [
  { label: 'All types', value: null },
  { label: 'txt', value: 'txt' },
  { label: 'md', value: 'md' },
  { label: 'docx', value: 'docx' },
  { label: 'pdf', value: 'pdf' },
]

const SORT_OPTIONS = [
  { label: 'Newest', value: 'newest' },
  { label: 'Oldest', value: 'oldest' },
  { label: 'Name A-Z', value: 'name_asc' },
  { label: 'Name Z-A', value: 'name_desc' },
]

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

/**
 * Format a byte count as a human-readable size ("512 B", "2.0 KB", "1.5 MB").
 *
 * Args:
 *   bytes: The file size in bytes (non-negative).
 *
 * Returns:
 *   The formatted size string.
 */
function formatSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`
  }
  const kb = bytes / 1024
  if (kb < 1024) {
    return `${kb.toFixed(1)} KB`
  }
  return `${(kb / 1024).toFixed(1)} MB`
}

/**
 * The Files page: browse generated outputs and uploaded source files.
 *
 * The TabMenu toggles the listing kind: 'generated' queries
 * ``GET /api/files/generated``, 'uploaded' queries ``GET /api/files/uploaded``
 * (both via `useFiles`). Rows are filtered by search text / file type / sort
 * on the backend, with the lazy paginator fetching one page at a time.
 *
 * Downloads use `fileDownloadUrl(row.path)` (``GET /api/outputs/{basename}``);
 * deletions send the selected row paths to ``DELETE /api/files``. Both work
 * the same for the two kinds, and the delete mutation invalidates the
 * listings so the table reflects the change. Switching kinds resets the page
 * and clears the selection.
 */
function FilesPage() {
  // --- state -----------------------------------------------------------------

  const [kind, setKind] = useState<FileKind>('generated')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [searchQuery, setSearchQuery] = useState<{ value: string; applied: string }>({
    value: '',
    applied: '',
  })
  const [fileTypeFilter, setFileTypeFilter] = useState<string | null>(null)
  const [sort, setSort] = useState('newest')
  const [selectedFiles, setSelectedFiles] = useState<FileMeta[]>([])
  const [confirmVisible, setConfirmVisible] = useState(false)
  const { show } = useToast()

  // --- data queries ----------------------------------------------------------

  // Lazy listing for the current kind. The search box keeps the typed `value`
  // separate from the `applied` text so only an explicit search (button or
  // Enter key) triggers a new request against the backend.
  const query = useFiles(kind, {
    q: searchQuery.applied || undefined,
    file_type: fileTypeFilter ?? undefined,
    page,
    page_size: pageSize,
    sort,
  })

  const deleteMutation = useDeleteFiles()

  const files: FileMeta[] = query.data?.items ?? []

  // --- event handlers --------------------------------------------------------

  /** Commit the typed search text and reset to the first page. */
  function applySearch() {
    setPage(1)
    setSearchQuery((prev) => ({ ...prev, applied: prev.value.trim() }))
  }

  /**
   * Handle a DataTable paginator change: remember the page size when it
   * changes and derive the 1-based page number from the first-row offset.
   */
  function handlePage(event: { first: number; rows: number }) {
    if (event.rows !== pageSize) {
      setPageSize(event.rows)
    }
    setPage(event.first / event.rows + 1)
  }

  /** Open the delete confirmation dialog for the selected files. */
  function confirmDelete() {
    setConfirmVisible(true)
  }

  /**
   * Execute the deletion of the selected files, close the dialog, and report
   * the result: a success toast for the deleted count and a warn toast for any
   * paths the backend reported missing.
   */
  function handleDeleteAccept() {
    const paths = selectedFiles.map((file) => file.path)
    deleteMutation.mutate(paths, {
      onSuccess: (result) => {
        setSelectedFiles([])
        setConfirmVisible(false)
        if (result.deleted.length > 0) {
          show({
            severity: 'success',
            summary: 'Deleted',
            detail: `Deleted ${result.deleted.length} file(s).`,
          })
        }
        if (result.missing.length > 0) {
          show({
            severity: 'warn',
            summary: 'Missing',
            detail: `${result.missing.length} file(s) not found.`,
          })
        }
      },
      onError: (error) => {
        setConfirmVisible(false)
        show({ severity: 'error', summary: 'Delete failed', detail: error.message })
      },
    })
  }

  // --- column renderers ------------------------------------------------------

  // Download link: goes to the shared outputs route via the row path.
  const linkBody = (row: FileMeta) => (
    <a className="p-button p-button-sm p-button-secondary p-button-text" href={fileDownloadUrl(row.path)}>
      <span className="pi pi-download p-button-icon" />
    </a>
  )

  const nameBody = (row: FileMeta) => <span className="files-name">{row.name}</span>
  const typeBody = (row: FileMeta) => <span className="files-type">{row.type}</span>
  const modifiedBody = (row: FileMeta) => (
    <span className="files-modified">{new Date(row.modified).toLocaleString()}</span>
  )
  const sizeBody = (row: FileMeta) => (
    <span className="files-size">{formatSize(row.size)}</span>
  )

  // --- render ----------------------------------------------------------------

  return (
    <section className="files-page">
      <h1>Files</h1>

      {/* Toolbar: listing-kind toggle plus search / type / sort filters */}
      <div className="files-toolbar">
        <TabMenu
          model={KIND_OPTIONS.map((option) => ({
            label: option.label,
            icon: option.value === 'generated' ? 'pi pi-folder' : 'pi pi-upload',
          }))}
          activeIndex={kind === 'generated' ? 0 : 1}
          onTabChange={(event) => {
            setKind(KIND_OPTIONS[event.index]?.value ?? 'generated')
            setPage(1)
            setSelectedFiles([])
          }}
        />
        <div className="files-filters">
          <span className="p-input-icon-left">
            <i className="pi pi-search" />
            <InputText
              value={searchQuery.value}
              onChange={(event) => setSearchQuery((prev) => ({ ...prev, value: event.target.value }))}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  applySearch()
                }
              }}
              placeholder="Search files"
            />
          </span>
          <Dropdown
            value={fileTypeFilter}
            options={FILE_TYPE_OPTIONS}
            onChange={(event) => {
              setFileTypeFilter(event.value as string | null)
              setPage(1)
            }}
            placeholder="Type"
            className="files-filter-type"
          />
          <Dropdown
            value={sort}
            options={SORT_OPTIONS}
            onChange={(event) => {
              setSort(event.value as string)
              setPage(1)
            }}
            placeholder="Sort"
            className="files-filter-sort"
          />
        </div>
      </div>

      {/* Delete action: enabled only while rows are selected */}
      <div className="files-actions">
        <Button
          type="button"
          icon="pi pi-trash"
          label={selectedFiles.length > 0 ? `Delete selected (${selectedFiles.length})` : 'Delete selected'}
          severity="danger"
          outlined
          disabled={selectedFiles.length === 0 || deleteMutation.isPending}
          onClick={confirmDelete}
        />
      </div>

      {/* Table: lazy, paginated listing of the current kind */}
      <DataTable
        value={files}
        dataKey="path"
        selection={selectedFiles}
        onSelectionChange={(event) => setSelectedFiles(event.value as FileMeta[])}
        selectionMode="checkbox"
        selectionPageOnly
        lazy
        loading={query.isFetching}
        paginator
        rows={pageSize}
        first={(page - 1) * pageSize}
        totalRecords={query.data?.total ?? 0}
        rowsPerPageOptions={PAGE_SIZE_OPTIONS.map((option) => option.value)}
        onPage={handlePage}
        emptyMessage={query.isLoading ? 'Loading...' : 'No files found'}
      >
        <Column selectionMode="multiple" headerStyle={{ width: '3rem' }} />
        <Column header="Name" body={nameBody} />
        <Column header="Type" body={typeBody} />
        <Column header="Modified" body={modifiedBody} />
        <Column header="Size" body={sizeBody} />
        <Column header="Link" body={linkBody} />
      </DataTable>

      {/* Delete confirmation dialog */}
      <ConfirmDialog
        visible={confirmVisible}
        onHide={() => setConfirmVisible(false)}
        message={`Delete ${selectedFiles.length} selected file(s)? This cannot be undone.`}
        header="Confirm deletion"
        acceptLabel="Delete"
        rejectLabel="Cancel"
        accept={handleDeleteAccept}
        reject={() => setConfirmVisible(false)}
        acceptClassName="p-button-danger"
      />
    </section>
  )
}

export default FilesPage