import { useState } from 'react'
import type { BudgetView, Evidence } from '../types/v2'
import EvidenceBadge from './EvidenceBadge'
import EvidenceDrawer from './EvidenceDrawer'

interface BudgetBreakdownProps { view: BudgetView }

export default function BudgetBreakdown({ view }: BudgetBreakdownProps) {
  const [selectedEvidence, setSelectedEvidence] = useState<Evidence | null>(null)
  const { breakdown } = view
  const amount = (value: string) => `${breakdown.currency} ${value}`
  return (
    <section className="space-y-4 rounded-2xl border border-white/10 bg-white/5 p-4" aria-label="Budget breakdown">
      <div className="flex items-start justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-[0.16em] text-amber-300">Budget ledger</p><p className="mt-1 text-2xl font-semibold">{amount(breakdown.known_total)}</p><p className="mt-1 text-xs text-slate-400">of {view.target.currency} {view.target.amount ?? 'unknown'} target</p></div><span className="rounded-full border border-white/15 px-2.5 py-1 text-xs text-slate-300">{breakdown.feasibility.replace(/_/g, ' ')}</span></div>
      <dl className="grid grid-cols-2 gap-3 text-sm">
        <div><dt className="text-slate-400">Verified</dt><dd>{amount(breakdown.verified_subtotal)}</dd></div>
        <div><dt className="text-slate-400">Estimated</dt><dd>{amount(breakdown.estimated_subtotal)}</dd></div>
        <div><dt className="text-slate-400">User provided</dt><dd>{amount(breakdown.user_provided_subtotal)}</dd></div>
        <div><dt className="text-slate-400">Taxes</dt><dd>{amount(breakdown.taxes_total)}</dd></div>
        <div><dt className="text-slate-400">Contingency</dt><dd>{amount(breakdown.contingency_total)}</dd></div>
        {breakdown.shortfall && <div><dt className="text-rose-300">Shortfall</dt><dd className="text-rose-200">{amount(breakdown.shortfall)}</dd></div>}
      </dl>
      {breakdown.mandatory_unknown_expense_ids.length > 0 && <p className="rounded-xl border border-amber-400/30 bg-amber-400/10 p-3 text-sm text-amber-100">Mandatory costs are still unknown. The known total does not establish budget feasibility.</p>}
      {view.evidence.length > 0 && <div className="flex flex-wrap gap-2">{view.evidence.map((item) => <EvidenceBadge key={item.id} evidence={item} onSelect={setSelectedEvidence} />)}</div>}
      {selectedEvidence && <EvidenceDrawer evidence={selectedEvidence} onClose={() => setSelectedEvidence(null)} />}
    </section>
  )
}
