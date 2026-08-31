import { useCallback, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Plane, Sparkles, Globe, Send } from 'lucide-react'
import ChatInterface from './components/ChatInterface'
import ItineraryView from './components/ItineraryView'
import Scene3D from './components/Scene3D'
import RetroOverlay from './components/RetroOverlay'
import MagneticButton from './components/MagneticButton'
import ShimmerText from './components/ShimmerText'
import { startPlan, parsePrompt } from './api'
import type { MasterTravelItinerary, TravelPlanRequest, PromptParseResponse } from './types'
import type { Step, Message } from './components/ChatInterface'

type Scene = 'landing' | 'prompt' | 'chat' | 'itinerary'

const ALL_STEPS: Step[] = [
  {
    key: 'destination',
    question: 'Where do you want to go?',
    helper: 'City, country, or region.',
    type: 'text',
    placeholder: 'e.g., Tokyo, Paris, Bali',
    required: true,
  },
  {
    key: 'origin',
    question: 'Where will you be traveling from?',
    helper: 'City you are starting the trip from.',
    type: 'text',
    placeholder: 'e.g., New York, London, Delhi',
    required: true,
  },
  {
    key: 'start_date',
    question: 'When does your adventure begin?',
    type: 'date',
    required: true,
  },
  {
    key: 'end_date',
    question: 'When do you return home?',
    type: 'date',
    required: true,
  },
  {
    key: 'travelers',
    question: 'How many travelers are going?',
    type: 'number',
    placeholder: '2',
    required: true,
  },
  {
    key: 'total_budget_usd',
    question: 'What is your total budget?',
    helper: 'Include flights, stay, food, and activities. Add a currency, e.g., 40000 INR, €3000, $5000.',
    type: 'text',
    placeholder: 'e.g., 40000 INR',
    required: true,
  },
  {
    key: 'travel_style',
    question: 'What is your travel vibe?',
    helper: 'Optional — defaults to Balanced.',
    type: 'chips',
    chips: ['Budget', 'Balanced', 'Luxury'],
    required: false,
  },
  {
    key: 'interests',
    question: 'What are you most excited about?',
    helper: 'Pick as many as you like.',
    type: 'chips',
    chips: ['Street Food', 'Temples', 'Museums', 'Nature', 'Nightlife', 'Shopping', 'History', 'Tech', 'Beaches', 'Mountains'],
    required: true,
  },
  {
    key: 'dietary_notes',
    question: 'Any dietary preferences or restrictions?',
    helper: 'e.g., vegetarian, halal, gluten-free, none',
    type: 'text',
    placeholder: 'none',
    required: false,
  },
  {
    key: 'mobility_notes',
    question: 'Any mobility considerations?',
    helper: 'e.g., wheelchair access, prefer walking, none',
    type: 'text',
    placeholder: 'none',
    required: false,
  },
  {
    key: 'free_text',
    question: 'Anything else I should know?',
    helper: 'Special occasions, must-see spots, or things to avoid.',
    type: 'textarea',
    placeholder: 'e.g., I want minimal walking and great sunset views.',
    required: false,
  },
]

const REQUIRED_FIELDS: Array<keyof TravelPlanRequest> = [
  'destination',
  'origin',
  'start_date',
  'end_date',
  'travelers',
  'total_budget_usd',
  'interests',
]

function normalizeExtracted(extracted: PromptParseResponse['extracted']): Partial<TravelPlanRequest> {
  const normalized: Partial<TravelPlanRequest> = { ...extracted }
  if (normalized.travelers !== undefined) {
    normalized.travelers = Number(normalized.travelers)
  }
  if (normalized.total_budget_usd !== undefined) {
    normalized.total_budget_usd = Number(normalized.total_budget_usd)
  }
  return normalized
}

export default function App() {
  const [scene, setScene] = useState<Scene>('landing')
  const [isLoading, setIsLoading] = useState(false)
  const [itinerary, setItinerary] = useState<MasterTravelItinerary | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [prompt, setPrompt] = useState('')
  const [isParsing, setIsParsing] = useState(false)
  const [chatSteps, setChatSteps] = useState<Step[]>(ALL_STEPS)
  const [initialAnswers, setInitialAnswers] = useState<Partial<TravelPlanRequest>>({})
  const [initialMessages, setInitialMessages] = useState<Message[]>([])
  const planAbortRef = useRef<AbortController | null>(null)

  const handlePlan = useCallback(async (request: TravelPlanRequest) => {
    setIsLoading(true)
    setError(null)
    planAbortRef.current = new AbortController()

    try {
      const response = await startPlan(request, planAbortRef.current.signal)
      setSessionId(response.session_id || null)
      if (response.status === 'completed' && response.itinerary) {
        setItinerary(response.itinerary)
        setScene('itinerary')
      } else {
        setError(response.error || 'Planning failed without a specific error.')
      }
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        setError('Planning was cancelled.')
      } else {
        setError(err instanceof Error ? err.message : 'Unknown error')
      }
    } finally {
      setIsLoading(false)
      planAbortRef.current = null
    }
  }, [])

  const handleCancelPlan = useCallback(() => {
    planAbortRef.current?.abort()
  }, [])

  const handleReset = useCallback(() => {
    setItinerary(null)
    setSessionId(null)
    setError(null)
    setScene('chat')
  }, [])

  const handlePromptSubmit = useCallback(async () => {
    const text = prompt.trim()
    if (!text) return

    setIsParsing(true)
    setError(null)

    try {
      const result = await parsePrompt({ prompt: text })
      const extracted = normalizeExtracted(result.extracted)

      const missingFields = REQUIRED_FIELDS.filter((field) => {
        const value = extracted[field]
        if (value === undefined || value === null) return true
        if (typeof value === 'string' && value.trim() === '') return true
        if (Array.isArray(value) && value.length === 0) return true
        return false
      })

      const steps = ALL_STEPS.filter((step) => {
        if (missingFields.includes(step.key)) return true
        if (step.required) return false
        // Optional fields are only shown if the parser did NOT extract them.
        return extracted[step.key] === undefined
      })

      // Pass parsed interests through so the backend can use them as defaults,
      // while the interests step still lets the user confirm or modify them.
      setInitialAnswers(extracted)
      setChatSteps(steps)
      setInitialMessages([
        { role: 'user', text },
        {
          role: 'assistant',
          text:
            steps.length > 0
              ? `Thanks! I have most of the details. Just a few quick follow-ups:`
              : `Thanks! I have everything I need. Let's build your itinerary.`,
        },
      ])
      setScene('chat')

      // If every required field was extracted, start planning immediately.
      if (steps.length === 0) {
        const request: TravelPlanRequest = {
          destination: (extracted.destination as string) || '',
          origin: (extracted.origin as string) || '',
          start_date: (extracted.start_date as string) || '',
          end_date: (extracted.end_date as string) || '',
          travelers: Number(extracted.travelers) || 1,
          total_budget_usd: Number(extracted.total_budget_usd) || 1,
          interests: Array.isArray(extracted.interests) ? (extracted.interests as string[]) : [],
          travel_style: (extracted.travel_style as string) || 'balanced',
          dietary_notes: (extracted.dietary_notes as string) || undefined,
          mobility_notes: (extracted.mobility_notes as string) || undefined,
          free_text: (extracted.free_text as string) || undefined,
        }
        handlePlan(request)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to parse prompt')
    } finally {
      setIsParsing(false)
    }
  }, [prompt])

  return (
    <div className="relative min-h-screen w-full overflow-hidden bg-cosmic-dark">
      <Scene3D className="z-0" />
      <RetroOverlay />

      <div className="absolute inset-0 z-10 bg-gradient-to-b from-transparent via-[#020617]/40 to-[#020617]/90" />

      <AnimatePresence mode="wait">
        {scene === 'landing' && (
          <motion.div
            key="landing"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, y: -50 }}
            transition={{ duration: 0.6 }}
            className="relative z-20 flex min-h-screen flex-col items-center justify-center px-6 text-center"
          >
            <motion.div
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ duration: 0.8, ease: 'easeOut' }}
              className="mb-6 flex h-20 w-20 items-center justify-center rounded-3xl glass glow-border"
            >
              <Globe size={40} className="text-cyan-400" />
            </motion.div>

            <motion.h1
              initial={{ y: 20, opacity: 0, filter: 'blur(10px)' }}
              animate={{ y: 0, opacity: 1, filter: 'blur(0px)' }}
              transition={{ delay: 0.2, duration: 0.7, ease: [0.23, 1, 0.32, 1] }}
              className="max-w-4xl text-5xl font-black leading-tight text-white md:text-7xl lg:text-8xl"
            >
              Discover the world with{' '}
              <ShimmerText as="span" className="font-black">VoyageMind AI</ShimmerText>
            </motion.h1>

            <motion.p
              initial={{ y: 20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 0.4 }}
              className="mx-auto mt-6 max-w-2xl text-lg text-slate-300 md:text-xl"
            >
              A magical AI concierge that plans your entire journey — flights, stays,
              sightseeing, and hidden gems — tailored to your taste and budget.
            </motion.p>

            <motion.div
              initial={{ y: 20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 0.6 }}
              className="mt-10"
            >
              <MagneticButton
                onClick={() => setScene('prompt')}
                className="flex items-center gap-3 text-lg"
              >
                <Sparkles size={20} />
                Plan My Trip
                <Plane size={20} />
              </MagneticButton>
            </motion.div>

            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.9 }}
              className="mt-6 font-mono text-xs uppercase tracking-widest text-slate-600"
            >
              Powered by CrewAI · Ollama LLM · Real-time planning
            </motion.p>
          </motion.div>
        )}

        {scene === 'prompt' && (
          <motion.div
            key="prompt"
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -30 }}
            transition={{ duration: 0.5 }}
            className="relative z-20 flex min-h-screen flex-col items-center justify-center px-6"
          >
            <div className="w-full max-w-3xl text-center">
              <h2 className="text-3xl font-black text-white md:text-5xl">
                Describe your dream trip
              </h2>
              <p className="mx-auto mt-4 max-w-xl text-slate-300 md:text-lg">
                Include destination, dates, budget, travelers, travel style, and interests. We'll extract the details and only ask about what's missing.
              </p>

              <div className="mt-8 flex flex-col items-center gap-4">
                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="e.g., Two friends traveling from Mumbai to Tokyo from 10 Oct to 18 Oct 2026 with a budget of $4000. We love street food, temples, museums, and nightlife. Prefer balanced style."
                  rows={5}
                  disabled={isParsing}
                  className="w-full rounded-3xl border border-white/10 bg-white/5 p-6 text-left text-white placeholder:text-slate-500 focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500 resize-none"
                />

                <MagneticButton
                  onClick={handlePromptSubmit}
                  disabled={!prompt.trim() || isParsing}
                  className="flex items-center gap-3 text-lg"
                >
                  {isParsing ? (
                    <>
                      <Sparkles size={20} />
                      Understanding...
                    </>
                  ) : (
                    <>
                      <Send size={20} />
                      Continue
                    </>
                  )}
                </MagneticButton>
              </div>
            </div>
          </motion.div>
        )}

        {scene === 'chat' && (
          <motion.div
            key="chat"
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -30 }}
            transition={{ duration: 0.5 }}
            className="relative z-20 h-screen w-full"
          >
            <ChatInterface
              onSubmit={handlePlan}
              onCancel={handleCancelPlan}
              isLoading={isLoading}
              steps={chatSteps}
              initialAnswers={initialAnswers}
              initialMessages={initialMessages}
            />
          </motion.div>
        )}

        {scene === 'itinerary' && itinerary && (
          <motion.div
            key="itinerary"
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -30 }}
            transition={{ duration: 0.5 }}
            className="relative z-20 min-h-screen w-full overflow-y-auto"
          >
            <ItineraryView itinerary={itinerary} sessionId={sessionId} onReset={handleReset} />
          </motion.div>
        )}
      </AnimatePresence>

      {error && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="fixed bottom-28 left-1/2 z-50 w-[90%] max-w-md -translate-x-1/2 rounded-2xl border border-rose-500/30 bg-rose-950/80 px-6 py-4 text-center text-rose-200 backdrop-blur-xl"
        >
          <p className="font-semibold">Oops, something went wrong</p>
          <p className="mt-1 text-sm opacity-90">{error}</p>
        </motion.div>
      )}
    </div>
  )
}
