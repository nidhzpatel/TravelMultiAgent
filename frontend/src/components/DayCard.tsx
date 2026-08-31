import { motion } from 'framer-motion'
import { Bed, Bus, MapPin, Clock, Coffee, Camera, ShoppingBag, Moon, Utensils } from 'lucide-react'
import TiltCard from './TiltCard'
import type { DayItinerary } from '../types'

interface DayCardProps {
  day: DayItinerary
  index: number
}

const categoryIcons: Record<string, React.ReactNode> = {
  food: <Coffee size={14} />,
  sightseeing: <Camera size={14} />,
  shopping: <ShoppingBag size={14} />,
  rest: <Moon size={14} />,
  transit: <Bus size={14} />,
}

const categoryColors: Record<string, string> = {
  food: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
  sightseeing: 'bg-sky-500/20 text-sky-300 border-sky-500/30',
  shopping: 'bg-pink-500/20 text-pink-300 border-pink-500/30',
  rest: 'bg-violet-500/20 text-violet-300 border-violet-500/30',
  transit: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
}

export default function DayCard({ day, index }: DayCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: index * 0.1 }}
    >
      <TiltCard className="glass glow-border rounded-2xl overflow-hidden">
      <div className="border-b border-white/10 bg-white/5 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-cyan-400">
              Day {day.day_number}
            </p>
            <h3 className="text-xl font-bold text-white">{day.theme}</h3>
            {day.region && (
              <p className="text-xs text-slate-400">{day.region}</p>
            )}
          </div>
          <p className="text-sm text-slate-400">{day.date}</p>
        </div>
      </div>

      <div className="p-6">
        {day.stay && (
          <div className="mb-5 flex items-start gap-3 rounded-xl bg-white/5 p-4">
            <Bed className="mt-0.5 shrink-0 text-violet-400" size={20} />
            <div>
              <p className="font-semibold text-white">{day.stay.hotel_name}</p>
              <p className="text-sm text-slate-400">{day.stay.location} · {day.stay.room_type}</p>
              <p className="mt-1 text-sm font-medium text-emerald-400">
                ${day.stay.estimated_cost_usd.toLocaleString()}
              </p>
            </div>
          </div>
        )}

        {day.transit_legs.length > 0 && (
          <div className="mb-5">
            <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-300">
              <Bus size={16} /> Transit
            </h4>
            <div className="space-y-3">
              {day.transit_legs.map((leg, idx) => (
                <div key={idx} className="relative flex items-start gap-3 pl-4">
                  <div className="absolute left-0 top-2 h-full w-px bg-gradient-to-b from-cyan-500/50 to-transparent" />
                  <div className="absolute left-[-3px] top-2 h-2 w-2 rounded-full bg-cyan-400" />
                  <div className="flex-1 rounded-lg bg-white/5 px-3 py-2">
                    <div className="flex items-center justify-between">
                      <p className="text-sm font-medium text-white">
                        {leg.from_location} → {leg.to_location}
                      </p>
                      <span className="text-xs text-slate-400">{leg.mode}</span>
                    </div>
                    <div className="mt-1 flex items-center gap-3 text-xs text-slate-400">
                      <span className="flex items-center gap-1"><Clock size={12} /> {leg.duration_minutes} min</span>
                      <span>${leg.estimated_cost_usd.toLocaleString()}</span>
                    </div>
                    {leg.notes && <p className="mt-1 text-xs text-slate-500">{leg.notes}</p>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {day.activities.length > 0 && (
          <div>
            <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-300">
              <MapPin size={16} /> Activities
            </h4>
            <div className="space-y-3">
              {day.activities.map((activity, idx) => (
                <div
                  key={idx}
                  className="flex items-start justify-between gap-4 rounded-xl bg-white/5 p-4 transition-colors hover:bg-white/10"
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium text-cyan-300">{activity.time_slot}</span>
                      <span
                        className={`flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${
                          categoryColors[activity.category] || categoryColors.sightseeing
                        }`}
                      >
                        {categoryIcons[activity.category] || categoryIcons.sightseeing}
                        {activity.category}
                      </span>
                    </div>
                    <p className="mt-1 font-semibold text-white">{activity.activity_name}</p>
                    <p className="text-sm text-slate-400">{activity.location}</p>
                    {activity.notes && <p className="mt-1 text-xs text-slate-500">{activity.notes}</p>}
                  </div>
                  <p className="text-sm font-medium text-emerald-400">
                    ${activity.estimated_cost_usd.toLocaleString()}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {day.meals_included.length > 0 && (
          <div className="mt-5 flex items-center gap-2 text-xs text-slate-400">
            <Utensils size={14} />
            <span>Meals: {day.meals_included.join(', ')}</span>
          </div>
        )}

        <div className="mt-5 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-3">
          <span className="text-sm text-slate-400">Daily total</span>
          <span className="text-lg font-bold text-white">${day.total_daily_cost_usd.toLocaleString()}</span>
        </div>
      </div>
      </TiltCard>
    </motion.div>
  )
}
