import { useCallback, useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Menu } from 'lucide-react'
import Conversation from './components/Conversation'
import Scene3D from './components/Scene3D'
import RetroOverlay from './components/RetroOverlay'
import Sidebar from './components/Sidebar'
import HomeScreen from './components/HomeScreen'
import V2ProposalWorkspace from './components/V2ProposalWorkspace'
import { createChat, sendChatMessage, listChats } from './api'
import type { ChatSession } from './types'
import ShareAcceptance from './features/trips/ShareAcceptance'

type Scene = 'prompt' | 'chat'

export default function App() {
  const v2TripId = new URLSearchParams(window.location.search).get('trip_id')
  const shareToken = new URLSearchParams(window.location.search).get('share_token')
  const [scene, setScene] = useState<Scene>('prompt')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [isParsing, setIsParsing] = useState(false)

  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [followUpInput, setFollowUpInput] = useState('')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  const createAbortRef = useRef<AbortController | null>(null)
  const messageAbortRef = useRef<AbortController | null>(null)

  const activeSession = sessions.find((s) => s.id === activeSessionId) || null

  // Load chat sessions on mount.
  useEffect(() => {
    listChats()
      .then(setSessions)
      .catch(() => {})
  }, [])

  const handleStartChat = useCallback(async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed) return

    setIsParsing(true)
    setIsLoading(true)
    setError(null)
    createAbortRef.current = new AbortController()

    try {
      const result = await createChat({ message: trimmed }, createAbortRef.current.signal)
      const session = result.session

      setSessions((prev) => {
        const filtered = prev.filter((s) => s.id !== session.id)
        return [session, ...filtered]
      })
      setActiveSessionId(session.id)
      setScene('chat')
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        setError('Planning was cancelled.')
      } else {
        setError(err instanceof Error ? err.message : 'Failed to start chat')
      }
    } finally {
      setIsParsing(false)
      setIsLoading(false)
      createAbortRef.current = null
    }
  }, [])

  const handleSendFollowUp = useCallback(async () => {
    if (!activeSessionId || !followUpInput.trim() || isLoading) return

    const message = followUpInput.trim()
    setIsLoading(true)
    setError(null)
    messageAbortRef.current = new AbortController()

    // Optimistically append user message.
    setSessions((prev) =>
      prev.map((s) =>
        s.id === activeSessionId
          ? {
              ...s,
              messages: [
                ...s.messages,
                { role: 'user', content: message, type: 'text' as const, created_at: new Date().toISOString() },
              ],
            }
          : s,
      ),
    )
    setFollowUpInput('')

    try {
      const result = await sendChatMessage(activeSessionId, { message }, messageAbortRef.current.signal)
      const session = result.session

      setSessions((prev) => {
        const filtered = prev.filter((s) => s.id !== session.id)
        return [session, ...filtered]
      })
      return result.message.type
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        setError('Response was cancelled.')
      } else {
        setError(err instanceof Error ? err.message : 'Failed to send message')
      }
      return undefined
    } finally {
      setIsLoading(false)
      messageAbortRef.current = null
    }
  }, [activeSessionId, followUpInput, isLoading])

  const handleCancel = useCallback(() => {
    createAbortRef.current?.abort()
    messageAbortRef.current?.abort()
  }, [])

  const handleNewChat = useCallback(() => {
    setActiveSessionId(null)
    setScene('prompt')
    setSidebarOpen(false)
  }, [])

  const handleSelectSession = useCallback((sessionId: string) => {
    const session = sessions.find((s) => s.id === sessionId)
    if (session) {
      setActiveSessionId(sessionId)
      setScene('chat')
      setSidebarOpen(false)
    }
  }, [sessions])

  return (
    <div className="relative flex h-screen w-full overflow-hidden bg-cosmic-dark">
      <Scene3D className="z-0" />
      <RetroOverlay />

      <div className="absolute inset-0 z-10 bg-gradient-to-b from-transparent via-[#020617]/40 to-[#020617]/90" />

      {shareToken && !v2TripId ? <ShareAcceptance token={shareToken} /> : v2TripId ? <V2ProposalWorkspace tripId={v2TripId} /> : <>

      <button
        onClick={() => setSidebarOpen(true)}
        className="fixed left-4 top-4 z-50 rounded-xl border border-white/10 bg-white/5 p-2 text-slate-300 hover:bg-white/10 hover:text-white md:hidden"
      >
        <Menu size={20} />
      </button>
      <Sidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed((v) => !v)}
        sessions={sessions}
        activeSessionId={activeSessionId}
        onNewChat={handleNewChat}
        onSelectSession={handleSelectSession}
      />

      <AnimatePresence mode="wait">
        {scene === 'prompt' && (
          <motion.div
            key="prompt"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.5 }}
            className="relative z-20 h-screen min-w-0 flex-1"
          >
            <HomeScreen onSubmit={handleStartChat} isLoading={isParsing} />
          </motion.div>
        )}

        {scene === 'chat' && activeSession && (
          <motion.div
            key="chat"
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -30 }}
            transition={{ duration: 0.5 }}
            className="relative z-20 h-screen min-w-0 flex-1"
          >
            <Conversation
              session={activeSession}
              sidebarCollapsed={sidebarCollapsed}
              isLoading={isLoading}
              inputValue={followUpInput}
              onInputChange={setFollowUpInput}
              onSend={handleSendFollowUp}
              onCancel={handleCancel}
              sessionId={activeSessionId}
            />
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
      </>}
    </div>
  )
}
