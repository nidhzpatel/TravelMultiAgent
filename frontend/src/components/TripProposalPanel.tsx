import { useState } from 'react'
import { ApiError, commitTripProposal, previewTripProposal } from '../api'
import type { Operation, ProposalPreview, TripVersion } from '../types/v2'
import ChangePreview from './ChangePreview'

interface TripProposalPanelProps {
  tripId: string
  version: number
  onCommitted: (version: TripVersion) => void
  onConflict: () => Promise<void>
}

export default function TripProposalPanel({ tripId, version, onCommitted, onConflict }: TripProposalPanelProps) {
  const [title, setTitle] = useState('')
  const [preview, setPreview] = useState<ProposalPreview | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const previewChange = async () => {
    if (!title.trim()) return
    setBusy(true); setError(null)
    try {
      const operations: Operation[] = [{ kind: 'REPLACE', path: 'title', value: title.trim() }]
      setPreview(await previewTripProposal(tripId, { expected_version: version, idempotency_key: crypto.randomUUID(), operations }))
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to preview change') } finally { setBusy(false) }
  }
  const commit = async () => {
    if (!preview) return
    setBusy(true); setError(null)
    try { onCommitted(await commitTripProposal(tripId, preview.proposal_id)); setPreview(null); setTitle('') }
    catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setPreview(null)
        await onConflict()
        setError('The accepted trip changed. The latest version is loaded; preview this change again.')
      } else setError(err instanceof Error ? err.message : 'Unable to apply change')
    } finally { setBusy(false) }
  }
  return <section className="space-y-3" aria-label="Trip change controls">
    <div className="flex gap-2"><input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Rename trip" className="min-w-0 flex-1 rounded-lg border border-white/15 bg-slate-950/70 px-3 py-2 text-sm text-white" />
      <button type="button" onClick={previewChange} disabled={busy} className="rounded-lg border border-cyan-400/40 px-3 py-2 text-sm text-cyan-200 disabled:opacity-50">Preview</button></div>
    {error && <p className="text-sm text-rose-300">{error}</p>}
    {preview && <ChangePreview baseVersion={preview.base_version} title={preview.preview.title} changedFields={preview.changed_fields} committing={busy} onCommit={commit} onCancel={() => setPreview(null)} />}
  </section>
}
