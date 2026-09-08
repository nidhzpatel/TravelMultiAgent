import { useState } from 'react'
import { motion } from 'framer-motion'
import { Sparkles, Compass, Send } from 'lucide-react'
import ShimmerText from './ShimmerText'

const SUGGESTIONS = [
  {
    icon: '🏖️',
    title: 'Beach getaway',
    prompt:
      'Two friends traveling from Mumbai to Goa from 10/10/2026 to 16/10/2026 with budget 40000 INR, we love beaches, nightlife, shopping, and historical places.',
  },
  {
    icon: '🏔️',
    title: 'Mountain escape',
    prompt:
      'Plan a 5 day trip to Manali from Delhi starting 20 October 2026 for a couple with budget 25000 INR, interested in mountains, nature, and food.',
  },
  {
    icon: '🏙️',
    title: 'City exploration',
    prompt:
      'Plan a trip to Dubai from Ahmedabad from 5 Dec to 10 Dec 2026 for 2 people with budget 80000 INR, interested in shopping, tech, and nightlife.',
  },
  {
    icon: '🌏',
    title: 'International trip',
    prompt:
      'Plan a 7 day trip to Tokyo from Mumbai from 15 Jan to 21 Jan 2027 for 2 people with budget 300000 INR, interested in temples, museums, tech, and street food.',
  },
]

interface HomeScreenProps {
  onSubmit: (prompt: string) => void
  isLoading: boolean
}

export default function HomeScreen({ onSubmit, isLoading }: HomeScreenProps) {
  const [input, setInput] = useState('')

  const handleSubmit = () => {
    if (!input.trim() || isLoading) return
    onSubmit(input.trim())
  }

  return (
    <div className="flex h-full flex-col items-center justify-center px-6">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="flex w-full max-w-4xl flex-col items-center"
      >
        {/* Greeting */}
        <div className="mb-10 flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl glass glow-border">
            <Compass size={22} className="text-cyan-400" />
          </div>
          <h1 className="text-3xl font-bold text-white md:text-4xl">
            <ShimmerText>What can I do for you?</ShimmerText>
          </h1>
        </div>

        {/* Suggestion cards */}
        <div className="mb-10 grid w-full grid-cols-1 gap-3 sm:grid-cols-2">
          {SUGGESTIONS.map((suggestion, idx) => (
            <motion.button
              key={suggestion.title}
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 + idx * 0.06 }}
              onClick={() => !isLoading && onSubmit(suggestion.prompt)}
              disabled={isLoading}
              className="group rounded-2xl border border-white/[0.08] bg-white/[0.04] p-4 text-left transition hover:border-cyan-500/30 hover:bg-white/[0.07]"
            >
              <p className="mb-1 text-lg">{suggestion.icon}</p>
              <p className="text-sm font-semibold text-slate-200 group-hover:text-white">
                {suggestion.title}
              </p>
              <p className="mt-1 line-clamp-2 text-xs text-slate-500">{suggestion.prompt}</p>
            </motion.button>
          ))}
        </div>

        {/* Big input box */}
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35 }}
          className="w-full"
        >
          <div className="rounded-3xl border border-white/10 bg-white/[0.05] p-4 backdrop-blur-xl transition focus-within:border-cyan-500/50 focus-within:ring-1 focus-within:ring-cyan-500/30">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSubmit()
                }
              }}
              placeholder="Describe your dream trip — destination, dates, budget, travelers, interests..."
              rows={3}
              disabled={isLoading}
              className="w-full resize-none bg-transparent text-[15px] leading-relaxed text-white placeholder:text-slate-500 focus:outline-none"
            />

            <div className="mt-2 flex items-center justify-between">
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <Sparkles size={13} className="text-cyan-400" />
                <span>AI Travel Concierge</span>
              </div>

              <div className="flex items-center gap-2">
                {isLoading ? (
                  <span className="text-xs text-cyan-300">Planning...</span>
                ) : (
                  <button
                    onClick={handleSubmit}
                    disabled={!input.trim()}
                    className={`flex h-9 w-9 items-center justify-center rounded-full transition ${
                      input.trim()
                        ? 'bg-cyan-500 text-white hover:bg-cyan-400'
                        : 'bg-white/[0.06] text-slate-500'
                    }`}
                    aria-label="Send"
                  >
                    <Send size={16} />
                  </button>
                )}
              </div>
            </div>
          </div>

          <p className="mt-3 text-center text-xs text-slate-600">
            Press Enter to send · Shift+Enter for a new line
          </p>
        </motion.div>
      </motion.div>
    </div>
  )
}
