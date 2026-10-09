import { useEffect, useState } from 'react'
import { getV2Budget, getV2ProviderData, getV2Trip } from '../api'
import type { BudgetView, ProviderDataView, TripVersion } from '../types/v2'
import AlternativeDrawer from './AlternativeDrawer'
import BudgetBreakdown from './BudgetBreakdown'
import TripProposalPanel from './TripProposalPanel'
import MapPanel from './MapPanel'
import ScheduledTimeline from './ScheduledTimeline'
import ProviderStatus from './ProviderStatus'
import WeatherPanel from './WeatherPanel'

interface V2ProposalWorkspaceProps {
  tripId: string
}

export default function V2ProposalWorkspace({ tripId }: V2ProposalWorkspaceProps) {
  const [trip, setTrip] = useState<TripVersion | null>(null)
  const [budget, setBudget] = useState<BudgetView | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selectedDestinationId, setSelectedDestinationId] = useState<string | null>(null)
  const [providerData, setProviderData] = useState<ProviderDataView | null>(null)

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

  useEffect(() => {
    if (!trip) return
    let active = true
    getV2ProviderData(tripId, trip.version).then((value) => { if (active) setProviderData(value) }).catch(() => { if (active) setProviderData(null) })
    return () => { active = false }
  }, [tripId, trip?.version])

  return (
    <main className="relative z-20 mx-auto h-screen w-full max-w-7xl overflow-y-auto px-6 py-12 text-white">
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
            <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
              <div className="space-y-6">
                <ProviderStatus outcomes={providerData?.outcomes ?? []} />
                {trip.trip.days.length > 0 && <ScheduledTimeline days={trip.trip.days} selectedDestinationId={selectedDestinationId} onSelectDestination={setSelectedDestinationId} />}
                <WeatherPanel forecasts={providerData?.items.filter((item) => item.kind === 'WEATHER') ?? []} />
                {budget && <BudgetBreakdown view={budget} />}
                <TripProposalPanel tripId={trip.trip_id} version={trip.version} onCommitted={setTrip} />
              </div>
              <div className="space-y-6"><MapPanel destinations={trip.trip.destinations} selectedDestinationId={selectedDestinationId} onSelect={setSelectedDestinationId} /><AlternativeDrawer items={providerData?.items.filter((item) => item.kind !== 'WEATHER') ?? []} /></div>
            </div>
          </div>
        )}
      </section>
    </main>
  )
}
