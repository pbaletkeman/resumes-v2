/**
 * Models page: per-agent model summary table.
 *
 * Loads ``useModels()`` (``GET /api/models``) and renders one row per pipeline
 * agent with its provider and model. Providers map to a Tag severity
 * (openai = info, ollama = success, any future provider = warning fallback).
 * The paginator only appears once more than 10 rows exist.
 */
import { DataTable } from 'primereact/datatable'
import { Column } from 'primereact/column'
import { Tag } from 'primereact/tag'
import { useModels } from '../api/hooks'

/** Tag severity per LLM provider name; unknown providers get a warning tag. */
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