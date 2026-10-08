import { motion, useReducedMotion } from 'framer-motion'

interface ChangePreviewProps {
  baseVersion: number
  title: string
  changedFields: string[]
  onCommit: () => void
  onCancel: () => void
  committing?: boolean
}

export default function ChangePreview({ baseVersion, title, changedFields, onCommit, onCancel, committing = false }: ChangePreviewProps) {
  const reduceMotion = useReducedMotion()
  return (
    <motion.aside
      initial={{ opacity: 0, y: reduceMotion ? 0 : 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl border border-cyan-400/30 bg-slate-950/80 p-4 text-slate-100 shadow-[0_0_24px_rgba(34,211,238,0.12)] backdrop-blur-xl"
      aria-label="Pending trip change preview"
    >
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan-300">Pending change · version {baseVersion}</p>
      <p className="mt-2 text-sm text-slate-300">Proposed trip title</p>
      <p className="mt-1 font-semibold text-white">{title}</p>
      <p className="mt-2 text-xs text-slate-400">Changes: {changedFields.join(', ') || 'none'}</p>
      <div className="mt-4 flex gap-2">
        <button type="button" onClick={onCancel} disabled={committing} className="rounded-lg border border-white/15 px-3 py-2 text-sm text-slate-200 transition hover:bg-white/10 disabled:opacity-50">
          Cancel
        </button>
        <button type="button" onClick={onCommit} disabled={committing} className="rounded-lg bg-cyan-400 px-3 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:opacity-50">
          {committing ? 'Applying…' : 'Apply change'}
        </button>
      </div>
    </motion.aside>
  )
}
