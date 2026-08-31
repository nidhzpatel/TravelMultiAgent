import { useState } from 'react'
import { motion } from 'framer-motion'
import { MapPin, Plane, Hotel, Sparkles, ArrowLeft, Download } from 'lucide-react'
import BudgetMeter from './BudgetMeter'
import DayCard from './DayCard'
import BookingCTA from './BookingCTA'
import AnimatedNumber from './AnimatedNumber'
import TiltCard from './TiltCard'
import ShimmerText from './ShimmerText'
import ConfettiCelebration from './ConfettiCelebration'
import MagneticButton from './MagneticButton'
import type { MasterTravelItinerary } from '../types'

interface ItineraryViewProps {
  itinerary: MasterTravelItinerary
  sessionId?: string | null
  onReset: () => void
}

export default function ItineraryView({ itinerary, sessionId, onReset }: ItineraryViewProps) {
  const savings = Math.max(itinerary.total_budget_usd - itinerary.actual_calculated_cost_usd, 0)
  const [showConfetti, setShowConfetti] = useState(false)
  const [isDownloading, setIsDownloading] = useState(false)

  const handleDownloadPdf = async () => {
    if (!sessionId) return
    setIsDownloading(true)
    try {
      const res = await fetch(`http://localhost:8000/plan/${sessionId}/pdf`)
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
      alert(err instanceof Error ? err.message : 'PDF download failed')
    } finally {
      setIsDownloading(false)
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="min-h-screen w-full px-4 pb-32 pt-8 md:px-8"
    >
      <ConfettiCelebration trigger={showConfetti} />

      <div className="mx-auto max-w-5xl">
        <div className="mb-6 flex flex-wrap items-center gap-3">
          <MagneticButton
            onClick={onReset}
            className="!rounded-full !bg-white/5 !px-4 !py-2 text-sm text-slate-400 hover:text-white"
            strength={0.15}
          >
            <ArrowLeft size={16} /> Plan another trip
          </MagneticButton>
          <MagneticButton
            onClick={handleDownloadPdf}
            disabled={!sessionId || isDownloading}
            className="!rounded-full !bg-cyan-500/10 !px-4 !py-2 text-sm text-cyan-300 hover:text-cyan-200 disabled:opacity-50"
            strength={0.15}
          >
            <Download size={16} />
            {isDownloading ? 'Generating PDF...' : 'Download PDF'}
          </MagneticButton>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8 text-center"
        >
          <div className="mb-3 flex items-center justify-center gap-2">
            <Sparkles size={18} className="text-cyan-400" />
            <ShimmerText as="span" className="text-sm font-medium uppercase tracking-widest">
              Your Dream Itinerary
            </ShimmerText>
            <Sparkles size={18} className="text-cyan-400" />
          </div>
          <h1 className="text-4xl font-extrabold text-white md:text-6xl">
            {itinerary.destination}
          </h1>
          <p className="mx-auto mt-3 max-w-2xl text-lg text-slate-400">
            {itinerary.travelers} traveler{itinerary.travelers > 1 ? 's' : ''} · {itinerary.days.length} day{itinerary.days.length > 1 ? 's' : ''} · {itinerary.currency}
          </p>
          {itinerary.origin && (
            <div className="mt-4 inline-flex items-center gap-2 rounded-full glass px-4 py-2 text-sm text-slate-300">
              <Plane size={16} className="text-cyan-400" />
              From {itinerary.origin}
            </div>
          )}
          {itinerary.trip_scope && (
            <p className="mt-3 text-sm text-slate-400">{itinerary.trip_scope}</p>
          )}
        </motion.div>

        <div className="mb-8 grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <BudgetMeter
              budget={itinerary.total_budget_usd}
              actual={itinerary.actual_calculated_cost_usd}
              currency={itinerary.currency}
            />
          </div>
          <TiltCard className="glass glow-border flex flex-col items-center justify-center rounded-2xl p-6 text-center">
            <p className="text-sm text-slate-400">Money saved vs budget</p>
            <AnimatedNumber
              value={savings}
              prefix="$"
              className="text-3xl font-bold text-emerald-400"
            />
            <p className="mt-1 text-xs text-slate-500">Estimated prices include taxes & fees</p>
          </TiltCard>
        </div>

        <div className="mb-8 grid gap-4 md:grid-cols-3">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
          >
            <TiltCard className="glass rounded-2xl p-5 h-full">
              <div className="mb-2 flex items-center gap-2 text-cyan-400">
                <Plane size={18} /> <span className="font-semibold">Transit</span>
              </div>
              <p className="text-sm text-slate-300">{itinerary.transit_summary}</p>
            </TiltCard>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            <TiltCard className="glass rounded-2xl p-5 h-full">
              <div className="mb-2 flex items-center gap-2 text-violet-400">
                <Hotel size={18} /> <span className="font-semibold">Stay</span>
              </div>
              <p className="text-sm text-slate-300">{itinerary.stay_summary}</p>
            </TiltCard>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
          >
            <TiltCard className="glass rounded-2xl p-5 h-full">
              <div className="mb-2 flex items-center gap-2 text-amber-400">
                <MapPin size={18} /> <span className="font-semibold">Sightseeing</span>
              </div>
              <p className="text-sm text-slate-300">{itinerary.sightseeing_summary}</p>
            </TiltCard>
          </motion.div>
        </div>

        <div className="mb-8 space-y-6">
          {itinerary.days.map((day, idx) => (
            <DayCard key={day.day_number} day={day} index={idx} />
          ))}
        </div>

        {(itinerary.inclusions.length > 0 || itinerary.exclusions.length > 0) && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.5 }}
            className="mb-8 grid gap-4 md:grid-cols-2"
          >
            {itinerary.inclusions.length > 0 && (
              <div className="rounded-2xl border border-emerald-500/20 bg-emerald-950/20 p-5">
                <h3 className="mb-2 text-sm font-semibold text-emerald-300">Inclusions</h3>
                <ul className="list-inside list-disc space-y-1 text-sm text-slate-400">
                  {itinerary.inclusions.map((item, idx) => (
                    <li key={idx}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
            {itinerary.exclusions.length > 0 && (
              <div className="rounded-2xl border border-rose-500/20 bg-rose-950/20 p-5">
                <h3 className="mb-2 text-sm font-semibold text-rose-300">Exclusions</h3>
                <ul className="list-inside list-disc space-y-1 text-sm text-slate-400">
                  {itinerary.exclusions.map((item, idx) => (
                    <li key={idx}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
          </motion.div>
        )}

        {itinerary.notes.length > 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.6 }}
            className="mb-8 rounded-2xl border border-white/10 bg-white/5 p-5"
          >
            <h3 className="mb-2 text-sm font-semibold text-slate-300">Notes</h3>
            <ul className="list-inside list-disc space-y-1 text-sm text-slate-400">
              {itinerary.notes.map((note, idx) => (
                <li key={idx}>{note}</li>
              ))}
            </ul>
          </motion.div>
        )}

        <div className="sticky bottom-6 z-10 mx-auto max-w-xl">
          <BookingCTA onClick={() => setShowConfetti(true)} />
        </div>
      </div>
    </motion.div>
  )
}
