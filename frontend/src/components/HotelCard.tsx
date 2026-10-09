import type { NormalizedProviderItem } from '../types/v2'

interface HotelCardProps {
  item: NormalizedProviderItem
  onInspect: (item: NormalizedProviderItem) => void
}

export default function HotelCard({ item, onInspect }: HotelCardProps) {
  const stale = item.expires_at !== null && Date.parse(item.expires_at) <= Date.now()
  const mock = item.evidence.some((evidence) => evidence.provenance === 'MOCK')
  return (
    <article className="rounded-xl border border-violet-400/20 bg-violet-400/5 p-4">
      <div className="flex items-start justify-between gap-3"><div><p className="font-medium text-white">{item.title}</p><p className="mt-1 text-xs text-slate-400">{item.detail}</p></div><span className="font-mono text-sm text-violet-200">{item.price?.amount ? `${item.price.currency} ${item.price.amount}` : 'Price unknown'}</span></div>
      <p className="mt-3 text-xs text-slate-400">Availability: {item.availability?.status ?? 'UNKNOWN'}</p>
      <div className="mt-3 flex items-center gap-3"><button type="button" onClick={() => onInspect(item)} className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-white transition active:scale-[0.97] focus:outline-none focus:ring-2 focus:ring-violet-300">Evidence</button>{item.handoff_url && !stale && !mock && <a href={item.handoff_url} target="_blank" rel="noreferrer" className="text-xs text-violet-300 underline">Open provider</a>}{stale && <span className="text-xs text-amber-300">Rate stale</span>}{mock && <span className="text-xs text-amber-300">Development fixture</span>}</div>
    </article>
  )
}
