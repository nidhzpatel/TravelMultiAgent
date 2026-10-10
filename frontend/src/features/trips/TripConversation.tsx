import { Send } from 'lucide-react'
import { useState } from 'react'
import { ApiError, commitTripProposal, sendV2TripMessage } from '../../api'
import type { ProposalPreview, TripVersion } from '../../types/v2'
import ChangePreview from '../../components/ChangePreview'

interface TripConversationProps {
  tripId: string
  onCommitted: (version: TripVersion) => void
  onConflict: () => Promise<void>
}

interface ConversationEntry { role: 'user' | 'assistant'; text: string }

export default function TripConversation({ tripId, onCommitted, onConflict }: TripConversationProps) {
  const [input, setInput] = useState('')
  const [entries, setEntries] = useState<ConversationEntry[]>([])
  const [preview, setPreview] = useState<ProposalPreview | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function send() {
    const message = input.trim()
    if (!message || busy) return
    setBusy(true); setError(null); setInput('')
    setEntries((current) => [...current, { role: 'user', text: message }])
    try {
      const response = await sendV2TripMessage(tripId, message)
      if (response.status === 'proposal') {
        setPreview(response)
        setEntries((current) => [...current, { role: 'assistant', text: 'I prepared a pending change. Review it before applying.' }])
      } else setEntries((current) => [...current, { role: 'assistant', text: response.message }])
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to process that message') }
    finally { setBusy(false) }
  }

  async function commit() {
    if (!preview) return
    setBusy(true); setError(null)
    try {
      const accepted = await commitTripProposal(tripId, preview.proposal_id)
      onCommitted(accepted); setPreview(null)
      setEntries((current) => [...current, { role: 'assistant', text: `Applied to accepted version ${accepted.version}.` }])
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 409) {
        setPreview(null); await onConflict()
        setError('The trip changed. I loaded the latest accepted version; ask for the change again.')
      } else setError(reason instanceof Error ? reason.message : 'Unable to apply the pending change')
    } finally { setBusy(false) }
  }

  return (
    <section className="flex min-h-[28rem] flex-col rounded-2xl border border-cyan-400/20 bg-slate-950/75 p-4" aria-label="Trip conversation">
      <div><p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan-300">Trip conversation</p><p className="mt-1 text-xs text-slate-400">Questions are read-only. Changes stay pending until you apply them.</p></div>
      <div className="mt-4 flex-1 space-y-3 overflow-y-auto" aria-live="polite">
        {entries.length === 0 && <p className="text-sm text-slate-400">Ask about this trip or request a scoped change.</p>}
        {entries.map((entry, index) => <p key={`${entry.role}-${index}`} className={`rounded-xl p-3 text-sm ${entry.role === 'user' ? 'ml-5 bg-cyan-400/10 text-cyan-50' : 'mr-5 bg-white/5 text-slate-200'}`}>{entry.text}</p>)}
        {preview && <ChangePreview baseVersion={preview.base_version} title={preview.preview.title} changedFields={preview.changed_fields} committing={busy} onCommit={() => void commit()} onCancel={() => setPreview(null)} />}
      </div>
      {error && <p className="mt-3 text-sm text-rose-300">{error}</p>}
      <form className="mt-4 flex gap-2" onSubmit={(event) => { event.preventDefault(); void send() }}><label className="sr-only" htmlFor="trip-message">Message</label><input id="trip-message" value={input} onChange={(event) => setInput(event.target.value)} maxLength={2000} placeholder="Ask or change this trip" className="min-w-0 flex-1 rounded-xl border border-white/15 bg-slate-900 px-3 py-2 text-sm text-white focus:border-cyan-300 focus:outline-none" /><button type="submit" disabled={busy || !input.trim()} aria-label="Send trip message" className="rounded-xl bg-cyan-300 p-2.5 text-slate-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-100 disabled:opacity-50"><Send className="h-4 w-4" /></button></form>
    </section>
  )
}
