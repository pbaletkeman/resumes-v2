/**
 * Models page: per-agent model summary table with inline editing.
 *
 * Loads ``useModels()`` (``GET /api/models``) and renders one row per pipeline
 * agent. Each row exposes an editable provider Dropdown + model InputText and
 * a Save button that ``PATCH``es the override (``useUpdateAgentModel``); the
 * Reset button (only enabled for overridden rows) ``DELETE``s the override so
 * the agent falls back to the environment defaults. Every successful change
 * invalidates the ``['models']`` query so the table reflects the persisted
 * state, and the mutations surface success/error toasts.
 *
 * The editable cells are small components that keep the in-progress value in
 * their own state and report changes up via ``onChange``; the page mirrors
 * those values in ``drafts`` so Save knows what to send. Seeding the draft
 * from the fetched rows never overwrites a draft the user has already
 * touched, so a background refetch cannot clobber an in-progress edit, and
 * reset flows refresh the cell values through the cells' sync effect.
 */
import { useEffect, useRef, useState } from 'react'
import { Button } from 'primereact/button'
import { Column } from 'primereact/column'
import { DataTable } from 'primereact/datatable'
import { Dropdown } from 'primereact/dropdown'
import { InputText } from 'primereact/inputtext'
import {
  useModels,
  useResetAgentModel,
  useUpdateAgentModel,
} from '../api/hooks'
import type { ModelSummary } from '../api/types'
import { useToast } from '../toast/ToastContext'

/** The provider choices offered per agent. */
const PROVIDER_OPTIONS = [
  { label: 'Ollama', value: 'ollama' },
  { label: 'OpenAI', value: 'openai' },
]

type Draft = { provider: string; model: string }

/** Editable provider Dropdown for one row; keeps its in-progress value locally. */
function ProviderCell({
  value,
  disabled,
  onChange,
}: {
  value: string
  disabled: boolean
  onChange: (value: string) => void
}) {
  const [local, setLocal] = useState(value)
  useEffect(() => {
    setLocal(value)
  }, [value])
  return (
    <Dropdown
      value={local}
      options={PROVIDER_OPTIONS}
      onChange={(event) => {
        const next = event.value as string
        setLocal(next)
        onChange(next)
      }}
      disabled={disabled}
      className="models-provider"
    />
  )
}

/** Editable model InputText for one row; keeps its in-progress value locally. */
function ModelCell({
  value,
  disabled,
  onChange,
}: {
  value: string
  disabled: boolean
  onChange: (value: string) => void
}) {
  const [local, setLocal] = useState(value)
  useEffect(() => {
    setLocal(value)
  }, [value])
  return (
    <InputText
      value={local}
      onChange={(event) => {
        const next = event.target.value
        setLocal(next)
        onChange(next)
      }}
      disabled={disabled}
      className="models-model"
    />
  )
}

function ModelsPage() {
  const { data, isLoading, isError } = useModels()
  const updateMutation = useUpdateAgentModel()
  const resetMutation = useResetAgentModel()
  const { show } = useToast()

  /** Per-agent in-progress provider/model edits, keyed by agent name. */
  const [drafts, setDrafts] = useState<Record<string, Draft>>({})

  // DataTable memoizes the column body closures, so handlers rendered inside
  // row cells never see state updates. Keep a ref mirror so stale closures can
  // still read the current draft at event time.
  const draftsRef = useRef<Record<string, Draft>>({})

  function commitDrafts(next: Record<string, Draft>) {
    draftsRef.current = next
    setDrafts(next)
  }

  // Seed drafts from the fetched rows. Existing drafts are kept so a refetch
  // never overwrites an edit the user is still typing.
  useEffect(() => {
    const next = { ...draftsRef.current }
    for (const row of data ?? []) {
      if (!(row.agent in next)) {
        next[row.agent] = { provider: row.provider, model: row.model }
      }
    }
    commitDrafts(next)
  }, [data])

  /** Update part of one agent's draft, initializing it if absent. */
  function setDraft(agent: string, patch: Partial<Draft>) {
    const next = {
      ...draftsRef.current,
      [agent]: {
        ...(draftsRef.current[agent] ?? { provider: '', model: '' }),
        ...patch,
      },
    }
    commitDrafts(next)
  }

  /** Persist an agent's draft via PATCH and report the result. */
  function handleSave(row: ModelSummary) {
    const draft = draftsRef.current[row.agent]
    if (!draft) return
    updateMutation.mutate(
      { agent: row.agent, provider: draft.provider, model: draft.model.trim() },
      {
        onSuccess: (updated) => {
          commitDrafts({
            ...draftsRef.current,
            [row.agent]: { provider: updated.provider, model: updated.model },
          })
          show({
            severity: 'success',
            summary: 'Saved',
            detail: `Updated ${row.agent}.`,
          })
        },
        onError: (error) => {
          show({
            severity: 'error',
            summary: 'Update failed',
            detail: error.message,
          })
        },
      },
    )
  }

  /** Reset an agent to the environment defaults via DELETE. */
  function handleReset(row: ModelSummary) {
    resetMutation.mutate(row.agent, {
      onSuccess: (updated) => {
        commitDrafts({
          ...draftsRef.current,
          [row.agent]: { provider: updated.provider, model: updated.model },
        })
        show({
          severity: 'success',
          summary: 'Reset',
          detail: `Reset ${row.agent} to defaults.`,
        })
      },
      onError: (error) => {
        show({
          severity: 'error',
          summary: 'Reset failed',
          detail: error.message,
        })
      },
    })
  }

  const pending = updateMutation.isPending || resetMutation.isPending

  const agentBody = (row: ModelSummary) => <span>{row.agent}</span>

  const providerBody = (row: ModelSummary) => {
    const draft = drafts[row.agent]
    return (
      <ProviderCell
        value={draft?.provider ?? row.provider}
        disabled={pending}
        onChange={(value) => setDraft(row.agent, { provider: value })}
      />
    )
  }

  const modelBody = (row: ModelSummary) => {
    const draft = drafts[row.agent]
    return (
      <ModelCell
        value={draft?.model ?? row.model}
        disabled={pending}
        onChange={(value) => setDraft(row.agent, { model: value })}
      />
    )
  }

  const actionsBody = (row: ModelSummary) => {
    const draft = drafts[row.agent]
    const unchanged =
      draft?.provider === row.provider && draft?.model === row.model
    return (
      <span className="models-actions">
        <Button
          type="button"
          icon="pi pi-check"
          label="Save"
          outlined
          disabled={pending || unchanged}
          onClick={() => handleSave(row)}
          className="models-save"
        />
        <Button
          type="button"
          icon="pi pi-refresh"
          label="Reset"
          severity="secondary"
          outlined
          disabled={pending || !row.is_overridden}
          onClick={() => handleReset(row)}
          className="models-reset"
        />
      </span>
    )
  }

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
        <Column header="Actions" body={actionsBody} />
      </DataTable>
    </section>
  )
}

export default ModelsPage