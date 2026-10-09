import { useState } from 'react'
import type { Evidence, NormalizedProviderItem } from '../types/v2'
import EvidenceBadge from './EvidenceBadge'
import EvidenceDrawer from './EvidenceDrawer'

interface WeatherPanelProps {
  forecasts: NormalizedProviderItem[]
}

export default function WeatherPanel({ forecasts }: WeatherPanelProps) {
  const [selectedEvidence, setSelectedEvidence] = useState<Evidence | null>(null)
  return (
    <section className="rounded-2xl border border-cyan-400/20 bg-slate-950/70 p-4" aria-label="Weather forecast">
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan-300">Provider forecast</p>
      {forecasts.length === 0 && <p className="mt-3 text-sm text-slate-400">No supported forecast is available for this accepted trip version.</p>}
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        {forecasts.map((forecast) => (
          <article key={forecast.id} className="rounded-xl border border-white/10 bg-white/5 p-3">
            <p className="font-mono text-xs text-slate-400">{forecast.local_date ?? 'Date unavailable'}</p>
            <p className="mt-1 font-medium text-white">{forecast.title}</p>
            {forecast.detail && <p className="mt-1 text-sm text-slate-300">{forecast.detail}</p>}
            <div className="mt-3 flex flex-wrap gap-2">{forecast.evidence.map((evidence) => <EvidenceBadge key={evidence.id} evidence={evidence} onSelect={setSelectedEvidence} />)}</div>
          </article>
        ))}
      </div>
      {selectedEvidence && <div className="mt-4"><EvidenceDrawer evidence={selectedEvidence} onClose={() => setSelectedEvidence(null)} /></div>}
    </section>
  )
}
