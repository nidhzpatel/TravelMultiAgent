import { useEffect, useState } from 'react'
import { getV2Budget, getV2Trip } from '../api'
import type { BudgetView, TripVersion } from '../types/v2'
import BudgetBreakdown from './BudgetBreakdown'
import TripProposalPanel from './TripProposalPanel'

interface V2ProposalWorkspaceProps {
  tripId: string
}

export default function V2ProposalWorkspace({ tripId }: V2ProposalWorkspaceProps) {
  const [trip, setTrip] = useState<TripVersion | null>(null)
  const [budget, setBudget] = useState<BudgetView | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    getV2Trip(tripId)
      .then((value) => { if (active) setTrip(value) })
      .catch((reason: unknown) => { if (active) setError(reason instanceof Error ? reason.message : 'Unable to load trip') })
    return () => { active = false }
  }, [tripId])

  useEffect(() => {
    if (!trip) return
    let active = true
    getV2Budget(tripId).then((value) => { if (active) setBudget(value) }).catch(() => { if (active) setBudget(null) })
    return () => { active = false }
  }, [tripId, trip?.version])

  return (
    <main className="relative z-20 mx-auto flex h-screen w-full max-w-3xl items-center px-6 py-12 text-white">
      <section className="w-full rounded-3xl border border-white/10 bg-slate-950/80 p-6 shadow-[0_0_60px_rgba(34,211,238,0.12)] backdrop-blur-xl">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-300">Versioned trip workspace</p>
        {error && <p className="mt-4 rounded-xl border border-rose-400/30 bg-rose-950/40 p-3 text-sm text-rose-200">{error}</p>}
        {!trip && !error && <p className="mt-4 text-sm text-slate-400">Loading accepted trip version…</p>}
        {trip && (
          <div className="mt-4 space-y-6">
            <div>
              <h1 className="text-2xl font-semibold">{trip.trip.title}</h1>
              <p className="mt-1 font-mono text-xs text-slate-400">Accepted version {trip.version}</p>
            </div>
            {budget && <BudgetBreakdown view={budget} />}
            <TripProposalPanel tripId={trip.trip_id} version={trip.version} onCommitted={setTrip} />
          </div>
        )}
      </section>
    </main>
  )
}
