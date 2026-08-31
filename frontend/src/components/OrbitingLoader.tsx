import { motion } from 'framer-motion'
import { Plane } from 'lucide-react'

interface OrbitingLoaderProps {
  text?: string
  subtext?: string
}

export default function OrbitingLoader({
  text = 'Crafting your dream trip...',
  subtext = 'Comparing stays, transit, and experiences across the globe.',
}: OrbitingLoaderProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass glow-border rounded-3xl p-8 text-center"
    >
      <div className="relative mx-auto mb-6 h-24 w-24">
        <motion.div
          className="absolute inset-0 rounded-full border border-cyan-500/20"
          animate={{ rotate: 360 }}
          transition={{ duration: 8, repeat: Infinity, ease: 'linear' }}
        >
          <div className="absolute -top-1 left-1/2 -translate-x-1/2">
            <div className="h-2 w-2 rounded-full bg-cyan-400 shadow-[0_0_10px_rgba(6,182,212,0.8)]" />
          </div>
        </motion.div>

        <motion.div
          className="absolute inset-3 rounded-full border border-violet-500/20"
          animate={{ rotate: -360 }}
          transition={{ duration: 12, repeat: Infinity, ease: 'linear' }}
        >
          <div className="absolute -bottom-1 left-1/2 -translate-x-1/2">
            <div className="h-1.5 w-1.5 rounded-full bg-violet-400 shadow-[0_0_10px_rgba(139,92,246,0.8)]" />
          </div>
        </motion.div>

        <motion.div
          className="absolute inset-0 flex items-center justify-center"
          animate={{ rotate: 360 }}
          transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
        >
          <Plane size={28} className="text-cyan-400" />
        </motion.div>
      </div>

      <p className="text-lg font-semibold text-white">{text}</p>
      <p className="mt-2 text-sm text-slate-400">{subtext}</p>
    </motion.div>
  )
}
