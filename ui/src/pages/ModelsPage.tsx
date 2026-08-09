import { DataTable } from 'primereact/datatable'
import { Column } from 'primereact/column'
import { Tag } from 'primereact/tag'
import { useModels } from '../api/hooks'

const PROVIDER_SEVERITY: Record<string, 'info' | 'success' | 'warning'> = {
  openai: 'info',
  ollama: 'success',
}

function ModelsPage() {
  const { data, isLoading, isError } = useModels()

  const agentBody = (row: { agent: string }) => <span>{row.agent}</span>
  const providerBody = (row: { provider: string }) => (
    <Tag value={row.provider} severity={PROVIDER_SEVERITY[row.provider] ?? 'warning'} />
  )
  const modelBody = (row: { model: string }) => <span>{row.model}</span>

  return (
    <section className="models-page">
      <h1>Models</h1>
      <DataTable
        value={data ?? []}
        loading={isLoading}
        dataKey="agent"
        emptyMessage={
          isError ? 'Failed to load models. Is the backend running?' : 'No models found'
        }
        paginator={data !== undefined && data.length > 10}
        rows={10}
      >
        <Column header="Agent" body={agentBody} sortable />
        <Column header="Provider" body={providerBody} sortable />
        <Column header="Model" body={modelBody} sortable />
      </DataTable>
    </section>
  )
}

export default ModelsPage