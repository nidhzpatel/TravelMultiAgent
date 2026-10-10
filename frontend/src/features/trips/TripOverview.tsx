import { Download, Users } from 'lucide-react'
import { useState } from 'react'
import { downloadV2TripPdf } from '../../api'
import type { TripVersion } from '../../types/v2'

interface TripOverviewProps {
  trip: TripVersion
}

export default function TripOverview({ trip }: TripOverviewProps) {
  const [exporting, setExporting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function exportPdf() {
    setExporting(true)
    setError(null)
    try { await downloadV2TripPdf(trip.trip_id, trip.version) }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to export this version') }
    finally { setExporting(false) }
  }

  return (
    <header className="rounded-2xl border border-white/10 bg-slate-950/70 p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-300">Accepted version {trip.version}</p>
          <h1 className="mt-1 text-2xl font-semibold text-white">{trip.trip.title}</h1>
          <p className="mt-2 text-sm text-slate-300">{trip.trip.brief.origin ?? 'Origin unknown'} → {trip.trip.brief.destination_text}</p>
          <p className="mt-1 flex items-center gap-2 text-xs text-slate-400"><Users className="h-3.5 w-3.5" />{trip.trip.brief.travelers} traveler(s) · {trip.trip.brief.start_date ?? 'date unknown'} to {trip.trip.brief.end_date ?? 'date unknown'}</p>
        </div>
        <button type="button" onClick={() => void exportPdf()} disabled={exporting} className="inline-flex items-center gap-2 rounded-xl border border-violet-300/30 px-4 py-2 text-sm text-violet-100 transition-colors hover:bg-violet-300/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-200 disabled:opacity-50"><Download className="h-4 w-4" />{exporting ? 'Exporting…' : `Export v${trip.version} PDF`}</button>
      </div>
      {error && <p className="mt-3 text-sm text-rose-300">{error}</p>}
    </header>
  )
}
