import type { BudgetView, TripVersion } from '../../types/v2'

interface ReadinessPanelProps {
  trip: TripVersion
  budget: BudgetView | null
}

export default function ReadinessPanel({ trip, budget }: ReadinessPanelProps) {
  const unknownRoutes = trip.trip.transport_legs.filter((leg) => leg.route_status !== 'REACHABLE').length
  const mandatoryUnknown = budget?.breakdown.mandatory_unknown_expense_ids.length ?? 0
  return (
    <section className="rounded-2xl border border-amber-300/20 bg-slate-950/70 p-4" aria-label="Trip readiness">
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-amber-300">Readiness</p>
      <p className="mt-2 font-semibold text-white">{trip.trip.readiness.replace(/_/g, ' ')}</p>
      <p className="mt-1 text-xs text-slate-400">Planning status only. No reservation is confirmed.</p>
      <dl className="mt-3 grid grid-cols-2 gap-3 text-sm"><div><dt className="text-slate-500">Unknown routes</dt><dd className="font-mono text-white">{unknownRoutes}</dd></div><div><dt className="text-slate-500">Mandatory unknown costs</dt><dd className="font-mono text-white">{mandatoryUnknown}</dd></div></dl>
    </section>
  )
}
