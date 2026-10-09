import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { CircleAlert, CircleCheck, LoaderCircle, OctagonX, Sparkles, Square } from 'lucide-react'
import { cancelPlanningJob, createPlanningJob, getPlanningJob, getPlanningJobEvents, listPlanningJobs } from '../api'
import type { PlanningJob, PlanningJobEvent, PlanningJobStatus } from '../types/v2'

interface PlanningProgressProps {
  tripId: string
  onAccepted: () => Promise<void>
}

const TERMINAL: ReadonlySet<PlanningJobStatus> = new Set(['NEEDS_INPUT', 'SUCCEEDED', 'FAILED', 'CANCELLED', 'EXPIRED'])

const terminalCopy: Partial<Record<PlanningJobStatus, string>> = {
  SUCCEEDED: 'Accepted draft ready',
  NEEDS_INPUT: 'More trip details are needed',
  FAILED: 'Planning ended safely without changing the trip',
  CANCELLED: 'Planning cancelled',
  EXPIRED: 'Planning deadline expired',
}

function newIdempotencyKey(): string {
  return `planning-${crypto.randomUUID()}`
}

export default function PlanningProgress({ tripId, onAccepted }: PlanningProgressProps) {
  const [job, setJob] = useState<PlanningJob | null>(null)
  const [events, setEvents] = useState<PlanningJobEvent[]>([])
  const [error, setError] = useState<string | null>(null)
  const [starting, setStarting] = useState(false)
  const acceptedVersion = useRef<number | null>(null)

  const loadEvents = useCallback(async (jobId: string) => {
    const after = events.length > 0 ? events[events.length - 1].sequence : 0
    const additions = await getPlanningJobEvents(tripId, jobId, after)
    if (additions.length > 0) setEvents((current) => [...current, ...additions])
  }, [events, tripId])

  useEffect(() => {
    let active = true
    listPlanningJobs(tripId)
      .then((jobs) => {
        if (!active || jobs.length === 0) return
        setJob(jobs[0])
        return getPlanningJobEvents(tripId, jobs[0].id).then((items) => { if (active) setEvents(items) })
      })
      .catch((reason: unknown) => { if (active) setError(reason instanceof Error ? reason.message : 'Unable to load planning status') })
    return () => { active = false }
  }, [tripId])

  useEffect(() => {
    if (!job || TERMINAL.has(job.status)) return
    let active = true
    const timer = window.setTimeout(async () => {
      try {
        const current = await getPlanningJob(tripId, job.id)
        if (!active) return
        setJob(current)
        await loadEvents(job.id)
      } catch (reason) {
        if (active) setError(reason instanceof Error ? reason.message : 'Unable to refresh planning status')
      }
    }, 1500)
    return () => { active = false; window.clearTimeout(timer) }
  }, [job, loadEvents, tripId])

  useEffect(() => {
    if (job?.status !== 'SUCCEEDED' || job.result_version === null || acceptedVersion.current === job.result_version) return
    acceptedVersion.current = job.result_version
    void onAccepted().catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : 'The draft was accepted, but the trip could not be refreshed')
    })
  }, [job, onAccepted])

  const progress = events.length > 0 ? events[events.length - 1].progress_percent : (job?.status === 'SUCCEEDED' ? 100 : 0)
  const isActive = job !== null && !TERMINAL.has(job.status)
  const label = job ? terminalCopy[job.status] ?? (job.status === 'RETRY_WAIT' ? 'Retry scheduled' : 'Building a bounded draft') : 'Create a new planning draft'
  const StatusIcon = job?.status === 'SUCCEEDED' ? CircleCheck : job?.status === 'NEEDS_INPUT' ? CircleAlert : job && TERMINAL.has(job.status) ? OctagonX : LoaderCircle
  const latestMessages = useMemo(() => events.slice(-4).reverse(), [events])

  async function start() {
    setStarting(true)
    setError(null)
    setEvents([])
    acceptedVersion.current = null
    try {
      setJob(await createPlanningJob(tripId, { idempotency_key: newIdempotencyKey() }))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to start planning')
    } finally {
      setStarting(false)
    }
  }

  async function cancel() {
    if (!job) return
    try {
      setJob(await cancelPlanningJob(tripId, job.id))
      await loadEvents(job.id)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to cancel planning')
    }
  }

  return (
    <section className="rounded-2xl border border-cyan-400/20 bg-slate-900/70 p-5" aria-live="polite">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 items-start gap-3">
          <StatusIcon className={`mt-0.5 h-5 w-5 shrink-0 ${isActive ? 'animate-spin text-cyan-300 motion-reduce:animate-none' : job?.status === 'SUCCEEDED' ? 'text-emerald-300' : 'text-amber-300'}`} aria-hidden="true" />
          <div>
            <h2 className="font-semibold text-white">{label}</h2>
            {job && <p className="mt-1 font-mono text-xs text-slate-400">Attempt {job.attempt_count} of {job.max_attempts} · {job.tokens_used.toLocaleString()} tokens · ${job.cost_used_usd}</p>}
          </div>
        </div>
        <div className="flex gap-2">
          {isActive && <button type="button" onClick={() => void cancel()} className="inline-flex items-center gap-2 rounded-xl border border-amber-300/30 px-3 py-2 text-sm text-amber-100 transition-colors hover:bg-amber-300/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-200"><Square className="h-3.5 w-3.5" />Cancel</button>}
          {!isActive && <button type="button" disabled={starting} onClick={() => void start()} className="inline-flex items-center gap-2 rounded-xl bg-cyan-300 px-4 py-2 text-sm font-semibold text-slate-950 transition-opacity hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-100 disabled:cursor-not-allowed disabled:opacity-50"><Sparkles className="h-4 w-4" />{starting ? 'Queuing…' : 'Plan draft'}</button>}
        </div>
      </div>
      {job && <progress className="mt-4 h-2 w-full accent-cyan-300" max={100} value={progress} aria-label="Planning progress" />}
      {error && <p className="mt-3 rounded-xl border border-rose-400/30 bg-rose-950/40 p-3 text-sm text-rose-200">{error}</p>}
      {latestMessages.length > 0 && <ol className="mt-4 space-y-2">{latestMessages.map((event) => <li key={event.sequence} className="flex justify-between gap-4 text-sm text-slate-300"><span>{event.message}</span><span className="font-mono text-xs text-slate-500">{event.progress_percent}%</span></li>)}</ol>}
      {job?.error_code && <p className="mt-3 text-xs text-slate-400">Reference: <span className="font-mono">{job.error_code}</span></p>}
    </section>
  )
}
