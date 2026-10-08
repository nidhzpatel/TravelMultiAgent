import { motion, useReducedMotion } from 'framer-motion'
import type { Evidence } from '../types/v2'

interface EvidenceDrawerProps {
  evidence: Evidence
  onClose: () => void
}

export default function EvidenceDrawer({ evidence, onClose }: EvidenceDrawerProps) {
  const reduceMotion = useReducedMotion()
  return (
    <motion.aside initial={{ opacity: 0, x: reduceMotion ? 0 : 16 }} animate={{ opacity: 1, x: 0 }} className="rounded-2xl border border-violet-400/30 bg-slate-950/90 p-4" aria-label="Evidence details">
      <div className="flex items-start justify-between gap-4">
        <div><p className="font-semibold text-white">{evidence.source}</p><p className="mt-1 text-xs text-slate-400">{evidence.provenance} · {evidence.provider_outcome}</p></div>
        <button type="button" onClick={onClose} className="text-sm text-slate-300 hover:text-white">Close</button>
      </div>
      <dl className="mt-4 space-y-2 text-xs text-slate-300">
        <div><dt className="text-slate-500">Covered fields</dt><dd>{evidence.covered_fields.join(', ') || 'None recorded'}</dd></div>
        <div><dt className="text-slate-500">Retrieved</dt><dd>{new Date(evidence.retrieved_at).toLocaleString()}</dd></div>
        <div><dt className="text-slate-500">Expires</dt><dd>{evidence.expires_at ? new Date(evidence.expires_at).toLocaleString() : 'No expiry supplied'}</dd></div>
        <div><dt className="text-slate-500">Retention</dt><dd>{evidence.retention_permitted ? (evidence.retention_until ? `Until ${new Date(evidence.retention_until).toLocaleString()}` : 'Permitted') : 'Not permitted'}</dd></div>
      </dl>
      {evidence.reference_url && <a href={evidence.reference_url} target="_blank" rel="noreferrer" className="mt-4 inline-block text-xs text-cyan-300 underline">Open source</a>}
    </motion.aside>
  )
}
