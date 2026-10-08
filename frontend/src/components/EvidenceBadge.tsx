import type { Evidence } from '../types/v2'

interface EvidenceBadgeProps {
  evidence: Evidence
  onSelect: (evidence: Evidence) => void
}

export default function EvidenceBadge({ evidence, onSelect }: EvidenceBadgeProps) {
  const stale = evidence.expires_at !== null && Date.parse(evidence.expires_at) <= Date.now()
  const label = stale ? 'Stale' : evidence.provenance === 'MOCK' ? 'Mock' : evidence.provider_outcome === 'SUCCESS' ? 'Verified source' : evidence.provider_outcome
  return (
    <button type="button" onClick={() => onSelect(evidence)} className="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-2.5 py-1 text-xs text-cyan-200 transition hover:bg-cyan-400/20 focus:outline-none focus:ring-2 focus:ring-cyan-300">
      {label} · {evidence.source}
    </button>
  )
}
