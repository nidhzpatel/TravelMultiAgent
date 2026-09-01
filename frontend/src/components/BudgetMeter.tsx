import { motion } from 'framer-motion'
import AnimatedNumber from './AnimatedNumber'

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

interface BudgetMeterProps {
  budget: number
  actual: number
  currency?: string
}

export default function BudgetMeter({ budget, actual, currency = 'USD' }: BudgetMeterProps) {
  const symbol = currencySymbol(currency)
  const percentage = Math.min((actual / budget) * 100, 100)
  const remaining = Math.max(budget - actual, 0)

  let colorClass = 'from-emerald-500 to-emerald-400'
  if (percentage > 85) colorClass = 'from-amber-500 to-amber-400'
  if (percentage > 100) colorClass = 'from-rose-500 to-rose-400'

  return (
    <div className="glass rounded-2xl p-6">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <p className="text-sm text-slate-400">Estimated total</p>
          <p className="text-3xl font-bold text-white">
            <AnimatedNumber value={actual} prefix={symbol} className="text-3xl font-bold text-white" />
            <span className="text-base font-normal text-slate-400"> {currency}</span>
          </p>
        </div>
        <div className="text-right">
          <p className="text-sm text-slate-400">Budget</p>
          <p className="text-xl font-semibold text-white">
            {symbol}{budget.toLocaleString()} {currency}
          </p>
        </div>
      </div>

      <div className="relative h-4 w-full overflow-hidden rounded-full bg-white/10">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${percentage}%` }}
          transition={{ duration: 1.2, ease: 'easeOut' }}
          className={`h-full rounded-full bg-gradient-to-r ${colorClass} shadow-[0_0_20px_rgba(52,211,153,0.4)]`}
        />
      </div>

      <div className="mt-3 flex items-center justify-between text-sm">
        <span className={percentage > 100 ? 'text-rose-400' : 'text-emerald-400'}>
          {percentage > 100
            ? `${symbol}${(actual - budget).toLocaleString()} over budget`
            : `${percentage.toFixed(0)}% of budget used`}
        </span>
        <span className="text-slate-400">{symbol}{remaining.toLocaleString()} remaining</span>
      </div>
    </div>
  )
}
