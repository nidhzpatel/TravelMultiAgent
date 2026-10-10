import { useState } from 'react'
import { acceptTripShare } from '../../api'

interface ShareAcceptanceProps { token: string }

export default function ShareAcceptance({ token }: ShareAcceptanceProps) {
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  async function accept() {
    setBusy(true); setError(null)
    try {
      const result = await acceptTripShare(token)
      window.location.assign(`${window.location.pathname}?trip_id=${encodeURIComponent(result.trip_id)}`)
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to accept invitation'); setBusy(false) }
  }
  return <main className="relative z-20 m-auto w-[min(90vw,28rem)] rounded-3xl border border-violet-300/20 bg-slate-950/90 p-8 text-center text-white"><h1 className="text-xl font-semibold">Trip invitation</h1><p className="mt-2 text-sm text-slate-400">Accept this invitation to add the trip to your workspace.</p><button type="button" disabled={busy} onClick={() => void accept()} className="mt-6 rounded-xl bg-violet-300 px-5 py-2.5 font-semibold text-slate-950 disabled:opacity-50">{busy ? 'Accepting…' : 'Accept invitation'}</button>{error && <p className="mt-4 text-sm text-rose-300">{error}</p>}</main>
}
