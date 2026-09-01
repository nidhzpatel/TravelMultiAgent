import { useState, useRef, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Send, Sparkles, Calendar, Users, Wallet, Compass, Utensils, Footprints, MessageSquare } from 'lucide-react'
import MessageBubble from './MessageBubble'
import TypingIndicator from './TypingIndicator'
import OrbitingLoader from './OrbitingLoader'
import MagneticButton from './MagneticButton'
import ShimmerText from './ShimmerText'
import { cn } from '../lib/utils'
import { parsePrompt } from '../api'
import type { TravelPlanRequest } from '../types'

interface ChatInterfaceProps {
  onSubmit: (request: TravelPlanRequest) => void
  onCancel?: () => void
  isLoading: boolean
  steps: Step[]
  initialAnswers?: Partial<TravelPlanRequest>
  initialMessages?: Message[]
}

function normalizeInterests(value: unknown): string[] {
  if (value === undefined || value === null) return []

  const raw: string[] = []
  if (typeof value === 'string') {
    raw.push(...value.split(','))
  } else if (Array.isArray(value)) {
    for (const item of value) {
      if (typeof item === 'string') {
        raw.push(...item.split(','))
      }
    }
  }

  return Array.from(new Set(raw.map((i) => i.trim().toLowerCase()).filter(Boolean)))
}

export type Message = {
  role: 'user' | 'assistant'
  text: string
}

type FieldKey =
  | 'destination'
  | 'origin'
  | 'start_date'
  | 'end_date'
  | 'travelers'
  | 'total_budget_usd'
  | 'travel_style'
  | 'interests'
  | 'dietary_notes'
  | 'mobility_notes'
  | 'free_text'

export interface Step {
  key: FieldKey
  question: string
  helper?: string
  type: 'text' | 'date' | 'number' | 'chips' | 'textarea'
  chips?: string[]
  placeholder?: string
  required?: boolean
}

export default function ChatInterface({
  onSubmit,
  onCancel,
  isLoading,
  steps,
  initialAnswers = {},
  initialMessages = [],
}: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>(initialMessages)
  const [currentStepIndex, setCurrentStepIndex] = useState(0)
  const [answers, setAnswers] = useState<Partial<TravelPlanRequest>>(initialAnswers)
  const [inputValue, setInputValue] = useState('')
  const [isTyping, setIsTyping] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const hasSubmittedRef = useRef(false)

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, isTyping, scrollToBottom])

  useEffect(() => {
    if (currentStepIndex >= steps.length) return
    setIsTyping(true)
    const timer = setTimeout(() => {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', text: steps[currentStepIndex].question },
      ])
      setIsTyping(false)
    }, 800)
    return () => clearTimeout(timer)
  }, [currentStepIndex, steps])

  const addUserMessage = useCallback((text: string) => {
    setMessages((prev) => [...prev, { role: 'user', text }])
  }, [])

  const advance = useCallback(() => {
    setCurrentStepIndex((prev) => prev + 1)
    setInputValue('')
  }, [])

  const handleUserResponse = useCallback(
    async (value: string) => {
      const step = steps[currentStepIndex]
      if (!step) return

      addUserMessage(value)

      let answerValue: string | number = value
      if (step.key === 'travelers') {
        answerValue = Number(value)
        setAnswers((prev) => ({ ...prev, [step.key]: answerValue }))
        advance()
        return
      }

      if (step.key === 'total_budget_usd') {
        const hasCurrency = /[^0-9.,\s]/.test(value)
        if (hasCurrency) {
          try {
            const parsed = await parsePrompt({ prompt: value })
            const extracted = parsed.extracted
            if (extracted.total_budget_usd !== undefined) {
              setAnswers((prev) => ({
                ...prev,
                total_budget_usd: Number(extracted.total_budget_usd),
                total_budget: Number(extracted.total_budget ?? extracted.total_budget_usd),
                currency: (extracted.currency as string) || (prev.currency as string) || 'USD',
                exchange_rate: Number(extracted.exchange_rate ?? prev.exchange_rate ?? 1),
              }))
              advance()
              return
            }
          } catch {
            // fall through to numeric fallback
          }
        }

        const numeric = Number(value.replace(/[^0-9.]/g, '')) || 0
        setAnswers((prev) => {
          const currency = (prev.currency as string) || 'USD'
          const exchangeRate = Number(prev.exchange_rate) || 1
          const usdAmount = currency === 'USD' ? numeric : numeric / exchangeRate
          return {
            ...prev,
            total_budget_usd: usdAmount,
            total_budget: numeric,
            currency,
            exchange_rate: exchangeRate,
          }
        })
        advance()
        return
      }

      setAnswers((prev) => ({ ...prev, [step.key]: answerValue }))
      advance()
    },
    [currentStepIndex, steps, addUserMessage, advance]
  )

  useEffect(() => {
    if (currentStepIndex >= steps.length && !isLoading && !hasSubmittedRef.current) {
      hasSubmittedRef.current = true

      const finalAnswers = { ...answers }
      if (!finalAnswers.origin) finalAnswers.origin = ''
      if (!finalAnswers.dietary_notes) finalAnswers.dietary_notes = undefined
      if (!finalAnswers.mobility_notes) finalAnswers.mobility_notes = undefined
      if (!finalAnswers.free_text) finalAnswers.free_text = undefined

      const request: TravelPlanRequest = {
        destination: finalAnswers.destination || '',
        origin: finalAnswers.origin || '',
        start_date: finalAnswers.start_date || '',
        end_date: finalAnswers.end_date || '',
        travelers: Number(finalAnswers.travelers) || 1,
        total_budget_usd: Number(finalAnswers.total_budget_usd) || 1,
        currency: (finalAnswers.currency as string) || 'USD',
        total_budget: Number(finalAnswers.total_budget) || Number(finalAnswers.total_budget_usd) || 1,
        exchange_rate: Number(finalAnswers.exchange_rate) || 1,
        interests: normalizeInterests(finalAnswers.interests),
        travel_style: (finalAnswers.travel_style as string) || 'balanced',
        cover_nearby:
          finalAnswers.cover_nearby === undefined ? true : Boolean(finalAnswers.cover_nearby),
        dietary_notes: finalAnswers.dietary_notes || undefined,
        mobility_notes: finalAnswers.mobility_notes || undefined,
        free_text: finalAnswers.free_text || undefined,
      }
      onSubmit(request)
    }
  }, [currentStepIndex, answers, isLoading, onSubmit, steps.length])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!inputValue.trim() || isTyping || isLoading) return
    await handleUserResponse(inputValue.trim())
  }

  const handleChipClick = (chip: string) => {
    if (isTyping || isLoading) return

    const step = steps[currentStepIndex]
    if (!step) return

    const chipKey = chip.toLowerCase()

    if (step.key === 'interests') {
      setAnswers((prev) => {
        const existing = normalizeInterests(prev.interests)
        const selected = existing.includes(chipKey)
          ? existing.filter((i) => i !== chipKey)
          : [...existing, chipKey]
        return { ...prev, interests: selected }
      })
      return
    }

    // Single-select chips (e.g. travel_style): select and advance immediately.
    addUserMessage(chip)
    setAnswers((prev) => ({ ...prev, [step.key]: chipKey }))
    advance()
  }

  const handleContinue = () => {
    if (isTyping || isLoading) return
    const selected = selectedInterests
    if (selected.length === 0) return
    addUserMessage(`Continue with ${selected.length} interest${selected.length > 1 ? 's' : ''}: ${selected.join(', ')}`)
    advance()
  }

  const step = steps[currentStepIndex]
  const isInterestsStep = step?.key === 'interests'
  const selectedInterests = normalizeInterests(answers.interests)

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-y-auto px-4 pb-32 pt-6 scrollbar-hide md:px-8">
        <div className="mx-auto flex max-w-3xl flex-col gap-5">
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-4 flex items-center justify-center gap-2"
          >
            <Sparkles size={18} className="text-cyan-300" />
            <ShimmerText as="span" className="text-sm font-medium tracking-wide uppercase">
              AI Travel Concierge
            </ShimmerText>
            <Sparkles size={18} className="text-cyan-300" />
          </motion.div>

          <AnimatePresence initial={false}>
            {messages.map((msg, idx) => (
              <MessageBubble
                key={idx}
                role={msg.role}
                text={msg.text}
                delay={0}
                isLatest={idx === messages.length - 1 && msg.role === 'assistant'}
              />
            ))}
          </AnimatePresence>

          {isTyping && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex justify-start"
            >
              <div className="message-assistant rounded-2xl rounded-bl-sm">
                <TypingIndicator />
              </div>
            </motion.div>
          )}

          {isLoading && (
            <div className="flex flex-col items-center gap-3">
              <OrbitingLoader />
              {onCancel && (
                <button
                  type="button"
                  onClick={onCancel}
                  className="rounded-full border border-rose-500/30 bg-rose-950/60 px-4 py-2 text-sm text-rose-200 backdrop-blur-xl transition hover:bg-rose-900/60"
                >
                  Cancel planning
                </button>
              )}
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {!isLoading && step && (
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          className="fixed bottom-0 left-0 right-0 z-20 border-t border-white/10 bg-[#020617]/80 backdrop-blur-xl px-4 py-5"
        >
          <div className="mx-auto max-w-3xl">
            {step.helper && (
              <p className="mb-3 text-center text-sm text-slate-400">{step.helper}</p>
            )}

            {step.type === 'chips' && (
              <div className="mb-4 flex flex-wrap justify-center gap-2">
                {step.chips?.map((chip) => {
                  const isSelected = selectedInterests.includes(chip.toLowerCase())
                  const isMultiSelect = step.key === 'interests'
                  return (
                    <button
                      key={chip}
                      type="button"
                      onClick={() => handleChipClick(chip)}
                      disabled={isTyping}
                      className={cn(
                        'chip',
                        isMultiSelect && isSelected && 'chip-selected',
                        !isMultiSelect && 'hover:chip-selected'
                      )}
                    >
                      {chip}
                    </button>
                  )
                })}
              </div>
            )}

            {isInterestsStep && selectedInterests.length > 0 && (
              <div className="mb-4 flex justify-center">
                <MagneticButton
                  onClick={handleContinue}
                  disabled={isTyping}
                  className="text-sm"
                >
                  Continue with {selectedInterests.length} interest{selectedInterests.length > 1 ? 's' : ''}
                </MagneticButton>
              </div>
            )}

            {step.type !== 'chips' && (
              <form onSubmit={handleSubmit} className="flex items-center gap-3">
                <div className="relative flex-1">
                  {step.type === 'date' && <Calendar className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={18} />}
                  {step.type === 'number' && step.key === 'travelers' && <Users className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={18} />}
                  {step.type === 'number' && step.key === 'total_budget_usd' && <Wallet className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={18} />}
                  {step.type === 'text' && step.key === 'destination' && <Compass className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={18} />}
                  {step.type === 'text' && step.key === 'dietary_notes' && <Utensils className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={18} />}
                  {step.type === 'text' && step.key === 'mobility_notes' && <Footprints className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={18} />}
                  {step.type === 'textarea' && <MessageSquare className="absolute left-4 top-4 text-slate-400" size={18} />}

                  {step.type === 'textarea' ? (
                    <textarea
                      value={inputValue}
                      onChange={(e) => setInputValue(e.target.value)}
                      placeholder={step.placeholder}
                      rows={2}
                      className="w-full rounded-2xl border border-white/10 bg-white/5 px-12 py-3 text-white placeholder:text-slate-500 focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500 resize-none"
                    />
                  ) : (
                    <input
                      type={step.type === 'number' ? 'number' : step.type}
                      value={inputValue}
                      onChange={(e) => setInputValue(e.target.value)}
                      placeholder={step.placeholder}
                      min={step.type === 'number' ? 1 : undefined}
                      className="h-12 w-full rounded-full border border-white/10 bg-white/5 px-12 text-white placeholder:text-slate-500 focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500"
                    />
                  )}
                </div>

                <MagneticButton
                  onClick={() => {}}
                  disabled={!inputValue.trim() || isTyping}
                  className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full p-0"
                  strength={0.2}
                >
                  <Send size={20} />
                </MagneticButton>
              </form>
            )}
          </div>
        </motion.div>
      )}
    </div>
  )
}
