import { motion, useReducedMotion } from 'framer-motion'
import { useState } from 'react'
import type { Evidence, NormalizedProviderItem } from '../types/v2'
import EvidenceBadge from './EvidenceBadge'
import EvidenceDrawer from './EvidenceDrawer'
import FlightCard from './FlightCard'
import HotelCard from './HotelCard'

interface AlternativeDrawerProps {
  items: NormalizedProviderItem[]
}

export default function AlternativeDrawer({ items }: AlternativeDrawerProps) {
  const reduceMotion = useReducedMotion()
  const [inspected, setInspected] = useState<NormalizedProviderItem | null>(null)
  const [evidence, setEvidence] = useState<Evidence | null>(null)
  const flights = items.filter((item) => item.kind === 'FLIGHT')
  const hotels = items.filter((item) => item.kind === 'HOTEL')
  const places = items.filter((item) => item.kind === 'SEARCH')
  return (
    <motion.section initial={{ opacity: 0, x: reduceMotion ? 0 : 16 }} animate={{ opacity: 1, x: 0 }} transition={{ type: 'spring', stiffness: 320, damping: 30 }} className="rounded-2xl border border-violet-400/20 bg-slate-950/70 p-4" aria-label="Provider alternatives">
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-violet-300">Provider alternatives</p>
      {items.length === 0 && <p className="mt-3 text-sm text-slate-400">No provider alternatives have been retained for this version.</p>}
      {flights.length > 0 && <div className="mt-4 space-y-3"><h2 className="text-sm font-semibold text-white">Flights</h2>{flights.map((item) => <FlightCard key={item.id} item={item} onInspect={setInspected} />)}</div>}
      {hotels.length > 0 && <div className="mt-4 space-y-3"><h2 className="text-sm font-semibold text-white">Stays</h2>{hotels.map((item) => <HotelCard key={item.id} item={item} onInspect={setInspected} />)}</div>}
      {places.length > 0 && <div className="mt-4 space-y-3"><h2 className="text-sm font-semibold text-white">Research</h2>{places.map((item) => <article key={item.id} className="rounded-xl border border-white/10 bg-white/5 p-3"><p className="font-medium text-white">{item.title}</p>{item.detail && <p className="mt-1 text-sm text-slate-300">{item.detail}</p>}<div className="mt-3 flex flex-wrap gap-2">{item.evidence.map((source) => <EvidenceBadge key={source.id} evidence={source} onSelect={setEvidence} />)}</div>{item.reference_url && <a href={item.reference_url} target="_blank" rel="noreferrer" className="mt-2 inline-block text-xs text-cyan-300 underline">Open source</a>}</article>)}</div>}
      {inspected && <div className="mt-4 rounded-xl border border-white/10 bg-white/5 p-3"><div className="flex items-center justify-between gap-3"><p className="text-sm font-medium text-white">Evidence for {inspected.title}</p><button type="button" onClick={() => setInspected(null)} className="text-xs text-slate-300 focus:outline-none focus:ring-2 focus:ring-violet-300">Close</button></div><div className="mt-3 flex flex-wrap gap-2">{inspected.evidence.map((source) => <EvidenceBadge key={source.id} evidence={source} onSelect={setEvidence} />)}</div></div>}
      {evidence && <div className="mt-4"><EvidenceDrawer evidence={evidence} onClose={() => setEvidence(null)} /></div>}
    </motion.section>
  )
}
