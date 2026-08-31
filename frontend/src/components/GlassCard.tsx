import { motion } from 'framer-motion'
import { cn } from '../lib/utils'

interface GlassCardProps {
  children: React.ReactNode
  className?: string
  hover?: boolean
  delay?: number
}

export default function GlassCard({ children, className, hover = true, delay = 0 }: GlassCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay }}
      whileHover={hover ? { y: -4, boxShadow: '0 0 40px rgba(6, 182, 212, 0.2)' } : undefined}
      className={cn(
        'glass rounded-2xl p-6',
        className
      )}
    >
      {children}
    </motion.div>
  )
}
