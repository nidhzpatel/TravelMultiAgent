import { useRef, useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Sparkles, X, ArrowUp } from 'lucide-react'
import type { ChatSession, ChatMessage, MasterTravelItinerary } from '../types'
import MessageBubble from './MessageBubble'
import TypingIndicator from './TypingIndicator'
import ShimmerText from './ShimmerText'
import InlineItinerary from './InlineItinerary'

interface ConversationProps {
  session: ChatSession
  isLoading: boolean
  inputValue: string
  onInputChange: (value: string) => void
  onSend: () => void
  onCancel?: () => void
  sidebarCollapsed?: boolean
  sessionId?: string | null
}

function ItineraryPreview({
  itinerary,
  expanded,
  onToggle,
}: {
  itinerary: MasterTravelItinerary
  expanded: boolean
  onToggle: () => void
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="my-4 rounded-2xl border border-cyan-500/20 bg-cyan-950/20 p-5"
    >
      <div className="mb-3 flex items-center gap-2 text-cyan-300">
        <Sparkles size={16} />
        <span className="text-sm font-semibold uppercase tracking-wider">Your Itinerary</span>
      </div>
      <h3 className="text-xl font-bold text-white">{itinerary.destination}</h3>
      <p className="mt-1 text-sm text-slate-400">
        {itinerary.travelers} traveler{itinerary.travelers > 1 ? 's' : ''} · {itinerary.days.length} day
        {itinerary.days.length > 1 ? 's' : ''} · {itinerary.currency}
      </p>
      <p className="mt-2 text-sm text-slate-300">
        Estimated cost: {itinerary.actual_calculated_cost.toLocaleString()} {itinerary.currency}
      </p>
      <button
        onClick={onToggle}
        className="mt-4 rounded-lg bg-cyan-500/10 px-4 py-2 text-sm font-medium text-cyan-300 transition hover:bg-cyan-500/20"
      >
        {expanded ? 'Hide full itinerary' : 'View full itinerary'}
      </button>
    </motion.div>
  )
}

export default function Conversation({
  session,
  isLoading,
  inputValue,
  onInputChange,
  onSend,
  onCancel,
  sidebarCollapsed = false,
  sessionId,
}: ConversationProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const [showItinerary, setShowItinerary] = useState(false)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [session.messages, isLoading, showItinerary])

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault()
    if (!inputValue.trim() || isLoading) return
    onSend()
  }

  return (
    <div className="flex h-full flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-36 pt-6 scrollbar-hide md:px-8">
        <div className={`mx-auto flex w-full flex-col gap-5 transition-[max-width] duration-300 ${showItinerary ? 'max-w-5xl' : 'max-w-3xl'}`}>
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-4 flex items-center justify-center gap-2"
          >
            <Sparkles size={18} className="text-cyan-300" />
            <ShimmerText as="span" className="text-sm font-medium uppercase tracking-wide">
              AI Travel Concierge
            </ShimmerText>
            <Sparkles size={18} className="text-cyan-300" />
          </motion.div>

          {session.messages.map((msg: ChatMessage, idx: number) => (
            <div key={idx}>
              <MessageBubble
                role={msg.role === 'system' ? 'assistant' : msg.role}
                text={msg.content}
                delay={0}
                isLatest={idx === session.messages.length - 1 && msg.role === 'assistant'}
              />
              {msg.type === 'itinerary_update' && msg.payload?.itinerary && (
                <>
                  <ItineraryPreview
                    itinerary={msg.payload.itinerary}
                    expanded={showItinerary}
                    onToggle={() => setShowItinerary((v) => !v)}
                  />
                  {showItinerary && (
                    <InlineItinerary itinerary={msg.payload.itinerary} sessionId={sessionId} />
                  )}
                </>
              )}
            </div>
          ))}

          {isLoading && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center gap-3">
              <div className="message-assistant rounded-2xl rounded-bl-sm">
                <TypingIndicator />
              </div>
              {onCancel && (
                <button
                  type="button"
                  onClick={onCancel}
                  className="flex h-8 w-8 items-center justify-center rounded-full border border-rose-500/30 bg-rose-950/60 text-rose-200 transition hover:bg-rose-900/60"
                  aria-label="Stop generating"
                >
                  <X size={14} />
                </button>
              )}
            </motion.div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      <div className={`fixed bottom-0 left-0 right-0 z-20 bg-gradient-to-t from-[#020617] via-[#020617]/80 to-transparent px-4 pb-6 pt-10 ${sidebarCollapsed ? 'md:left-16' : 'md:left-72'}`}>
        <form onSubmit={handleSubmit} className={`mx-auto w-full transition-[max-width] duration-300 ${showItinerary ? 'max-w-5xl' : 'max-w-3xl'}`}>
          <div className="rounded-3xl border border-white/10 bg-white/[0.06] p-4 backdrop-blur-xl transition focus-within:border-cyan-500/50 focus-within:ring-1 focus-within:ring-cyan-500/30">
            <textarea
              value={inputValue}
              onChange={(e) => onInputChange(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSubmit()
                }
              }}
              placeholder="Ask a follow-up question — change transport, list hotels, modify activities..."
              rows={2}
              disabled={isLoading}
              className="w-full resize-none bg-transparent text-[15px] leading-relaxed text-white placeholder:text-slate-500 focus:outline-none"
            />

            <div className="mt-2 flex items-center justify-between">
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <Sparkles size={13} className="text-cyan-400" />
                <span>AI Travel Concierge</span>
              </div>

              <div className="flex items-center gap-2">
                {isLoading && onCancel && (
                  <button
                    type="button"
                    onClick={onCancel}
                    className="flex h-8 w-8 items-center justify-center rounded-full border border-rose-500/30 bg-rose-950/60 text-rose-200 transition hover:bg-rose-900/60"
                    aria-label="Stop generating"
                  >
                    <X size={13} />
                  </button>
                )}
                <button
                  type="submit"
                  disabled={!inputValue.trim() || isLoading}
                  className={`flex h-9 w-9 items-center justify-center rounded-full transition ${
                    inputValue.trim() && !isLoading
                      ? 'bg-cyan-500 text-white hover:bg-cyan-400'
                      : 'bg-white/[0.06] text-slate-500'
                  }`}
                  aria-label="Send"
                >
                  <ArrowUp size={16} />
                </button>
              </div>
            </div>
          </div>
        </form>
      </div>
    </div>
  )
}
