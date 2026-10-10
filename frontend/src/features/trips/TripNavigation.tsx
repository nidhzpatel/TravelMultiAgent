import type { Destination, TripDay } from '../../types/v2'

interface TripNavigationProps {
  days: TripDay[]
  destinations: Destination[]
  selectedDestinationId: string | null
  onSelectDestination: (id: string) => void
}

export default function TripNavigation({ days, destinations, selectedDestinationId, onSelectDestination }: TripNavigationProps) {
  return (
    <nav className="rounded-2xl border border-white/10 bg-white/5 p-4" aria-label="Trip city and day navigation">
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">Days</p>
      <div className="mt-2 flex flex-wrap gap-2">{days.map((day, index) => <a key={day.id} href={`#${day.id}`} className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-slate-200 hover:border-cyan-300/40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-200">Day {index + 1}</a>)}</div>
      <p className="mt-4 text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">Cities</p>
      <div className="mt-2 flex flex-wrap gap-2">{destinations.map((destination) => <button key={destination.id} type="button" aria-pressed={destination.id === selectedDestinationId} onClick={() => onSelectDestination(destination.id)} className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-slate-200 hover:border-violet-300/40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-violet-200 aria-pressed:border-violet-300 aria-pressed:bg-violet-300/10">{destination.name}</button>)}</div>
      {days.length === 0 && destinations.length === 0 && <p className="mt-2 text-sm text-slate-400">No accepted cities or days yet.</p>}
    </nav>
  )
}
