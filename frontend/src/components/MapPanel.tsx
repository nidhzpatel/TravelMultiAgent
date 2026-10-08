import type { Destination } from '../types/v2'

interface MapPanelProps {
  destinations: Destination[]
  selectedDestinationId: string | null
  onSelect: (destinationId: string) => void
}

export default function MapPanel({ destinations, selectedDestinationId, onSelect }: MapPanelProps) {
  const resolved = destinations.filter((item) => item.latitude !== null && item.longitude !== null)
  return (
    <section className="rounded-2xl border border-violet-400/20 bg-slate-950/70 p-4" aria-label="Trip map places">
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-violet-300">Resolved places</p>
      {resolved.length === 0 && <p className="mt-3 text-sm text-slate-400">No verified coordinates are available, so no map markers are shown.</p>}
      <div className="mt-3 space-y-2">
        {resolved.map((destination) => (
          <button key={destination.id} type="button" aria-pressed={selectedDestinationId === destination.id} onClick={() => onSelect(destination.id)} className="w-full rounded-xl border border-white/10 bg-white/5 p-3 text-left transition hover:border-violet-300/40 focus:outline-none focus:ring-2 focus:ring-violet-300 aria-pressed:border-violet-300 aria-pressed:bg-violet-400/10">
            <span className="block font-medium text-white">{destination.name}</span>
            <span className="mt-1 block font-mono text-xs text-slate-400">{destination.latitude}, {destination.longitude} · {destination.timezone}</span>
          </button>
        ))}
      </div>
    </section>
  )
}
