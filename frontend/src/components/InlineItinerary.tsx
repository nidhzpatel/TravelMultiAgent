import { useState } from 'react'
import { motion } from 'framer-motion'
import { MapPin, Plane, Hotel, Sparkles, Download, Car } from 'lucide-react'
import BudgetMeter from './BudgetMeter'
import DayCard from './DayCard'
import BookingCTA from './BookingCTA'
import AnimatedNumber from './AnimatedNumber'
import TiltCard from './TiltCard'
import ShimmerText from './ShimmerText'
import ConfettiCelebration from './ConfettiCelebration'
import MagneticButton from './MagneticButton'
import type { MasterTravelItinerary } from '../types'

interface InlineItineraryProps {
  itinerary: MasterTravelItinerary
  sessionId?: string | null
}

const CURRENCY_SYMBOLS: Record<string, string> = {
  USD: '$',
  INR: '₹',
  EUR: '€',
  GBP: '£',
  AED: 'AED ',
  JPY: '¥',
  AUD: 'A$',
  CAD: 'C$',
}

function currencySymbol(code: string) {
  return CURRENCY_SYMBOLS[code] || `${code} `
}

export default function InlineItinerary({ itinerary, sessionId }: InlineItineraryProps) {
  const symbol = currencySymbol(itinerary.currency)
  const savings = Math.max(itinerary.total_budget - itinerary.actual_calculated_cost, 0)
  const [showConfetti, setShowConfetti] = useState(false)
  const [isDownloading, setIsDownloading] = useState(false)

  const handleDownloadPdf = async () => {
    if (!sessionId || isDownloading) return
    setIsDownloading(true)
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 60_000)
    try {
      const res = await fetch(`http://localhost:8000/plan/${sessionId}/pdf`, { signal: controller.signal })
      if (!res.ok) throw new Error('Failed to download PDF')
      const blob = await res.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${itinerary.destination.toLowerCase().replace(/\s+/g, '_')}-itinerary.pdf`
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      alert(err instanceof Error && err.name === 'AbortError' ? 'PDF download timed out. Please try again.' : err instanceof Error ? err.message : 'PDF download failed')
    } finally {
      clearTimeout(timeout)
      setIsDownloading(false)
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      className="my-4 overflow-hidden rounded-2xl border border-white/10 bg-white/[0.03]"
    >
      <ConfettiCelebration trigger={showConfetti} />

      {/* Header */}
      <div className="border-b border-white/[0.06] p-5 text-center">
        <div className="mb-2 flex items-center justify-center gap-2">
          <Sparkles size={16} className="text-cyan-400" />
          <ShimmerText as="span" className="text-xs font-medium uppercase tracking-widest">
            Your Dream Itinerary
          </ShimmerText>
          <Sparkles size={16} className="text-cyan-400" />
        </div>
        <h2 className="text-3xl font-extrabold text-white">{itinerary.destination}</h2>
        <p className="mt-1 text-sm text-slate-400">
          {itinerary.travelers} traveler{itinerary.travelers > 1 ? 's' : ''} · {itinerary.days.length} day
          {itinerary.days.length > 1 ? 's' : ''} · {itinerary.currency}
        </p>
        {itinerary.origin && (
          <div className="mt-3 inline-flex items-center gap-2 rounded-full glass px-3 py-1.5 text-xs text-slate-300">
            <Plane size={14} className="text-cyan-400" />
            From {itinerary.origin}
          </div>
        )}
        {itinerary.trip_scope && <p className="mt-2 text-xs text-slate-500">{itinerary.trip_scope}</p>}
        {sessionId && (
          <MagneticButton
            onClick={handleDownloadPdf}
            disabled={isDownloading}
            className="!rounded-full !bg-cyan-500/10 !px-4 !py-2 !text-xs text-cyan-300 hover:text-cyan-200 disabled:opacity-50 mt-4"
            strength={0.15}
          >
            <Download size={14} />
            {isDownloading ? 'Generating PDF...' : 'Download PDF'}
          </MagneticButton>
        )}
      </div>

      <div className="p-5">
        {/* Budget */}
        <div className="mb-6 grid gap-4 md:grid-cols-3">
          <div className="md:col-span-2">
            <BudgetMeter
              budget={itinerary.total_budget}
              actual={itinerary.actual_calculated_cost}
              currency={itinerary.currency}
            />
          </div>
          <TiltCard className="glass glow-border flex flex-col items-center justify-center rounded-2xl p-4 text-center">
            <p className="text-xs text-slate-400">Money saved vs budget</p>
            <AnimatedNumber
              value={savings}
              prefix={symbol}
              className="text-2xl font-bold text-emerald-400"
            />
            <p className="mt-1 text-[11px] text-slate-500">Estimated prices include taxes & fees</p>
          </TiltCard>
        </div>

        {/* Summaries */}
        <div className="mb-6 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <TiltCard className="glass rounded-2xl p-4">
            <div className="mb-1.5 flex items-center gap-2 text-cyan-400">
              <Plane size={16} /> <span className="text-sm font-semibold">Transit</span>
            </div>
            <p className="text-xs text-slate-300">{itinerary.transit_summary}</p>
          </TiltCard>
          <TiltCard className="glass rounded-2xl p-4">
            <div className="mb-1.5 flex items-center gap-2 text-violet-400">
              <Hotel size={16} /> <span className="text-sm font-semibold">Stay</span>
            </div>
            <p className="text-xs text-slate-300">{itinerary.stay_summary}</p>
          </TiltCard>
          <TiltCard className="glass rounded-2xl p-4">
            <div className="mb-1.5 flex items-center gap-2 text-amber-400">
              <MapPin size={16} /> <span className="text-sm font-semibold">Sightseeing</span>
            </div>
            <p className="text-xs text-slate-300">{itinerary.sightseeing_summary}</p>
          </TiltCard>
          {itinerary.cab_service && (
            <TiltCard className="glass glow-border rounded-2xl p-4">
              <div className="mb-1.5 flex items-center gap-2 text-emerald-400">
                <Car size={16} /> <span className="text-sm font-semibold">Cab Services</span>
              </div>
              <p className="text-xs text-slate-300">{itinerary.cab_service.vehicle_type}</p>
              <p className="mt-1 text-xs text-slate-400">{itinerary.cab_service.coverage}</p>
              <p className="mt-2 text-lg font-bold text-white">
                {symbol}{itinerary.cab_service.estimated_cost.toLocaleString()}
                <span className="ml-1 text-xs font-normal text-slate-400">for all {itinerary.cab_service.total_days} days</span>
              </p>
            </TiltCard>
          )}
        </div>

        {/* Days */}
        <div className="mb-6 space-y-4">
          {itinerary.days.map((day, idx) => (
            <DayCard key={day.day_number} day={day} index={idx} currency={itinerary.currency} />
          ))}
        </div>

        {/* Inclusions / Exclusions */}
        {(itinerary.inclusions.length > 0 || itinerary.exclusions.length > 0) && (
          <div className="mb-6 grid gap-3 md:grid-cols-2">
            {itinerary.inclusions.length > 0 && (
              <div className="rounded-2xl border border-emerald-500/20 bg-emerald-950/20 p-4">
                <h3 className="mb-2 text-sm font-semibold text-emerald-300">Inclusions</h3>
                <ul className="list-inside list-disc space-y-1 text-xs text-slate-400">
                  {itinerary.inclusions.map((item, idx) => (
                    <li key={idx}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
            {itinerary.exclusions.length > 0 && (
              <div className="rounded-2xl border border-rose-500/20 bg-rose-950/20 p-4">
                <h3 className="mb-2 text-sm font-semibold text-rose-300">Exclusions</h3>
                <ul className="list-inside list-disc space-y-1 text-xs text-slate-400">
                  {itinerary.exclusions.map((item, idx) => (
                    <li key={idx}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* Notes */}
        {itinerary.notes.length > 0 && (
          <div className="mb-6 rounded-2xl border border-white/10 bg-white/5 p-4">
            <h3 className="mb-2 text-sm font-semibold text-slate-300">Notes</h3>
            <ul className="list-inside list-disc space-y-1 text-xs text-slate-400">
              {itinerary.notes.map((note, idx) => (
                <li key={idx}>{note}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Book CTA at the end of the plan */}
        <div className="mx-auto max-w-xl">
          <BookingCTA onClick={() => setShowConfetti(true)} />
        </div>
      </div>
    </motion.div>
  )
}
