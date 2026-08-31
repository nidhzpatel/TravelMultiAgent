import { motion } from 'framer-motion'
import { CalendarCheck } from 'lucide-react'

interface BookingCTAProps {
  onClick?: () => void
}

export default function BookingCTA({ onClick }: BookingCTAProps) {
  return (
    <motion.button
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ scale: 1.03 }}
      whileTap={{ scale: 0.98 }}
      onClick={onClick}
      className="group relative w-full overflow-hidden rounded-2xl bg-gradient-to-r from-violet-600 via-sky-500 to-violet-600 p-[1px]"
      style={{ backgroundSize: '200% 100%' }}
    >
      <div className="relative flex items-center justify-center gap-3 rounded-2xl bg-[#020617]/80 px-8 py-4 transition-colors group-hover:bg-[#020617]/60">
        <motion.div
          animate={{ rotate: [0, 10, -10, 0] }}
          transition={{ duration: 2, repeat: Infinity }}
        >
          <CalendarCheck className="text-cyan-300" size={24} />
        </motion.div>
        <span className="text-lg font-bold text-white">Book This Trip</span>
      </div>
      <div className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/20 to-transparent transition-transform duration-1000 group-hover:translate-x-full" />
    </motion.button>
  )
}
