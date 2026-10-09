import type { ProviderRun } from '../types/v2'

interface ProviderStatusProps {
  outcomes: ProviderRun[]
}

export default function ProviderStatus({ outcomes }: ProviderStatusProps) {
  if (outcomes.length === 0) return <p className="rounded-xl border border-white/10 bg-white/5 p-3 text-sm text-slate-400">Provider data has not been requested for this accepted version.</p>
  return (
    <ul className="flex flex-wrap gap-2" aria-label="Provider status">
      {outcomes.map((outcome) => (
        <li key={`${outcome.kind}-${outcome.provider}`} className="rounded-full border border-white/10 bg-white/5 px-3 py-1 font-mono text-xs text-slate-300">
          {outcome.kind.toLowerCase()} · {outcome.provider} · <span className={outcome.status === 'SUCCESS' ? 'text-cyan-300' : outcome.status === 'MOCK' ? 'text-amber-300' : 'text-violet-300'}>{outcome.status}</span>{outcome.error_code ? ` (${outcome.error_code})` : ''}
        </li>
      ))}
    </ul>
  )
}
