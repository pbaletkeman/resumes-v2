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

function FilesPage() {
  const [kind, setKind] = useState<FileKind>('generated')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [q, setQ] = useState<{ value: string; applied: string }>({ value: '', applied: '' })
  const [fileType, setFileType] = useState<string | null>(null)
  const [sort, setSort] = useState('newest')
  const [selected, setSelected] = useState<FileMeta[]>([])
  const [confirmVisible, setConfirmVisible] = useState(false)
  const { show } = useToast()

  const query = useFiles(kind, {
    q: q.applied || undefined,
    file_type: fileType ?? undefined,
    page,
    page_size: pageSize,
    sort,
  })

  const deleteMutation = useDeleteFiles()

  const files: FileMeta[] = query.data?.items ?? []

  function applySearch() {
    setPage(1)
    setQ((prev) => ({ ...prev, applied: prev.value.trim() }))
  }

  function handlePage(event: { first: number; rows: number }) {
    if (event.rows !== pageSize) {
      setPageSize(event.rows)
    }
    setPage(event.first / event.rows + 1)
  }

  function confirmDelete() {
    setConfirmVisible(true)
  }

  function handleDeleteAccept() {
    const paths = selected.map((file) => file.path)
    deleteMutation.mutate(paths, {
      onSuccess: (result) => {
        setSelected([])
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

  return (
    <section className="files-page">
      <h1>Files</h1>
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
            setSelected([])
          }}
        />
        <div className="files-filters">
          <span className="p-input-icon-left">
            <i className="pi pi-search" />
            <InputText
              value={q.value}
              onChange={(event) => setQ((prev) => ({ ...prev, value: event.target.value }))}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  applySearch()
                }
              }}
              placeholder="Search files"
            />
          </span>
          <Dropdown
            value={fileType}
            options={FILE_TYPE_OPTIONS}
            onChange={(event) => {
              setFileType(event.value as string | null)
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
      <div className="files-actions">
        <Button
          type="button"
          icon="pi pi-trash"
          label={selected.length > 0 ? `Delete selected (${selected.length})` : 'Delete selected'}
          severity="danger"
          outlined
          disabled={selected.length === 0 || deleteMutation.isPending}
          onClick={confirmDelete}
        />
      </div>
      <DataTable
        value={files}
        dataKey="path"
        selection={selected}
        onSelectionChange={(event) => setSelected(event.value as FileMeta[])}
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
      <ConfirmDialog
        visible={confirmVisible}
        onHide={() => setConfirmVisible(false)}
        message={`Delete ${selected.length} selected file(s)? This cannot be undone.`}
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