import type { TripDay } from '../types/v2'

interface ScheduledTimelineProps {
  days: TripDay[]
  selectedDestinationId: string | null
  onSelectDestination: (destinationId: string) => void
}

export default function ScheduledTimeline({ days, selectedDestinationId, onSelectDestination }: ScheduledTimelineProps) {
  const formatTime = (value: string | null, timezone: string) => value ? new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit', timeZone: timezone }).format(new Date(value)) : 'Time unknown'
  return (
    <section className="space-y-4" aria-label="Scheduled trip timeline">
      {days.map((day) => <article id={day.id} key={day.id} className="scroll-mt-6 rounded-2xl border border-white/10 bg-white/5 p-4">
        <div className="flex items-baseline justify-between gap-3"><h2 className="font-semibold text-white">{day.local_date}</h2><span className="font-mono text-xs text-slate-400">{day.timezone}</span></div>
        <div className="mt-3 space-y-2">{day.scheduled_items.map((item) => (
          <button key={item.id} type="button" disabled={!item.destination_id} aria-pressed={item.destination_id !== null && selectedDestinationId === item.destination_id} onClick={() => item.destination_id && onSelectDestination(item.destination_id)} className="w-full rounded-xl border border-white/10 bg-slate-950/60 p-3 text-left transition hover:border-cyan-300/40 focus:outline-none focus:ring-2 focus:ring-cyan-300 disabled:cursor-default aria-pressed:border-cyan-300 aria-pressed:bg-cyan-400/10">
            <span className="flex items-center justify-between gap-3"><span className="font-medium capitalize text-white">{item.kind}</span><span className="font-mono text-xs text-slate-400">{formatTime(item.start_at, day.timezone)}–{formatTime(item.end_at, day.timezone)}</span></span>
            {item.start_at === null && item.critical && <span className="mt-1 block text-xs text-amber-300">Critical time unresolved</span>}
          </button>
        ))}</div>
      </article>)}
    </section>
  )
}
