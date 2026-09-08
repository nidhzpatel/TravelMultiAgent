import { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { Plus, MessageSquare, PanelLeft, User } from 'lucide-react'
import type { ChatSession } from '../types'

function useIsDesktop() {
  const [isDesktop, setIsDesktop] = useState(
    () => typeof window !== 'undefined' && window.innerWidth >= 768,
  )
  useEffect(() => {
    const mq = window.matchMedia('(min-width: 768px)')
    const onChange = (e: MediaQueryListEvent) => setIsDesktop(e.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])
  return isDesktop
}

interface SidebarProps {
  isOpen: boolean
  onClose: () => void
  collapsed: boolean
  onToggle: () => void
  sessions: ChatSession[]
  activeSessionId: string | null
  onNewChat: () => void
  onSelectSession: (sessionId: string) => void
}

type SessionGroup = {
  label: string
  sessions: ChatSession[]
}

function groupSessions(sessions: ChatSession[]): SessionGroup[] {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = new Date(today.getTime() - 86400000)
  const sevenDaysAgo = new Date(today.getTime() - 7 * 86400000)
  const thirtyDaysAgo = new Date(today.getTime() - 30 * 86400000)

  const groups: SessionGroup[] = []
  const buckets: Record<string, ChatSession[]> = {
    Today: [],
    Yesterday: [],
    'Previous 7 Days': [],
    'Previous 30 Days': [],
  }
  const monthBuckets: Record<string, ChatSession[]> = {}

  for (const session of sessions) {
    const updated = new Date(session.updated_at)
    const day = new Date(updated.getFullYear(), updated.getMonth(), updated.getDate())

    if (day.getTime() === today.getTime()) {
      buckets['Today'].push(session)
    } else if (day.getTime() === yesterday.getTime()) {
      buckets['Yesterday'].push(session)
    } else if (updated >= sevenDaysAgo) {
      buckets['Previous 7 Days'].push(session)
    } else if (updated >= thirtyDaysAgo) {
      buckets['Previous 30 Days'].push(session)
    } else {
      const key = updated.toLocaleDateString(undefined, { year: 'numeric', month: 'long' })
      if (!monthBuckets[key]) monthBuckets[key] = []
      monthBuckets[key].push(session)
    }
  }

  for (const label of ['Today', 'Yesterday', 'Previous 7 Days', 'Previous 30 Days']) {
    if (buckets[label].length > 0) {
      groups.push({ label, sessions: buckets[label] })
    }
  }

  const monthKeys = Object.keys(monthBuckets).sort((a, b) => {
    // Sort newest month first.
    return new Date(b).getTime() - new Date(a).getTime()
  })

  for (const key of monthKeys) {
    groups.push({ label: key, sessions: monthBuckets[key] })
  }

  return groups
}

export default function Sidebar({
  isOpen,
  onClose,
  collapsed,
  onToggle,
  sessions,
  activeSessionId,
  onNewChat,
  onSelectSession,
}: SidebarProps) {
  const groups = useMemo(() => groupSessions(sessions), [sessions])
  const isDesktop = useIsDesktop()

  // On desktop the expanded panel is hidden while collapsed (icon rail shown instead).
  const showExpanded = !isDesktop || !collapsed

  return (
    <>
      {/* Mobile overlay */}
      {!isDesktop && isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm md:hidden"
        />
      )}

      {/* Collapsed icon rail (desktop only) */}
      {isDesktop && collapsed && (
        <aside className="relative z-30 flex h-full w-16 flex-col items-center border-r border-white/[0.06] bg-[#0a0f1e] py-4">
          <button
            onClick={onToggle}
            title="Expand sidebar"
            aria-label="Expand sidebar"
            className="mb-3 rounded-xl p-2 text-slate-400 transition hover:bg-white/[0.06] hover:text-white"
          >
            <PanelLeft size={18} />
          </button>
          <button
            onClick={onNewChat}
            title="New chat"
            aria-label="New chat"
            className="rounded-xl bg-white/[0.07] p-2 text-cyan-400 transition hover:bg-white/[0.12]"
          >
            <Plus size={18} />
          </button>
          <div className="min-h-0 flex-1" />
          <div
            title="Traveler — Free plan"
            className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-cyan-500 to-violet-600"
          >
            <User size={15} className="text-white" />
          </div>
        </aside>
      )}

      {showExpanded && (
      <motion.aside
        initial={false}
        animate={{ x: isDesktop ? 0 : isOpen ? 0 : '-100%' }}
        transition={{ type: 'spring', damping: 28, stiffness: 220 }}
        className="fixed left-0 top-0 z-50 flex h-full w-72 flex-col border-r border-white/[0.06] bg-[#0a0f1e] md:relative md:z-30"
      >
        {/* Brand header */}
        <div className="flex items-center justify-between px-4 pb-2 pt-4">
          <div className="flex items-center gap-2">
            <span className="text-lg font-black tracking-tight text-white">
              Voyage<span className="text-cyan-400">Mind</span> AI
            </span>
          </div>
          <button
            onClick={() => (isDesktop ? onToggle() : onClose())}
            className="rounded-lg p-1.5 text-slate-400 transition hover:bg-white/[0.06] hover:text-white"
            aria-label={isDesktop ? 'Collapse sidebar' : 'Close sidebar'}
          >
            <PanelLeft size={17} />
          </button>
        </div>

        {/* New chat button */}
        <div className="px-3 pt-2">
          <button
            onClick={onNewChat}
            className="flex w-full items-center gap-3 rounded-xl bg-white/[0.07] px-4 py-3 text-sm font-medium text-slate-200 transition hover:bg-white/[0.12]"
          >
            <Plus size={17} className="text-cyan-400" />
            New chat
          </button>
        </div>

        {/* Chat list grouped by date */}
        <div className="mt-2 min-h-0 flex-1 space-y-5 overflow-y-auto px-3 py-4 scrollbar-hide">
          {groups.length === 0 && (
            <p className="px-2 pt-8 text-center text-sm text-slate-600">No chats yet</p>
          )}

          {groups.map((group) => (
            <div key={group.label}>
              <p className="mb-1.5 px-2 text-xs font-medium uppercase tracking-wider text-slate-500">
                {group.label}
              </p>
              <div className="space-y-0.5">
                {group.sessions.map((session) => (
                  <button
                    key={session.id}
                    onClick={() => onSelectSession(session.id)}
                    className={`group flex w-full items-start gap-2.5 rounded-lg px-2.5 py-2 text-left transition ${
                      activeSessionId === session.id
                        ? 'bg-white/[0.08] text-white'
                        : 'text-slate-400 hover:bg-white/[0.05] hover:text-slate-200'
                    }`}
                  >
                    <MessageSquare
                      size={15}
                      className={`mt-0.5 shrink-0 ${
                        activeSessionId === session.id ? 'text-cyan-400' : 'text-slate-600'
                      }`}
                    />
                    <span className="min-w-0 flex-1 truncate text-sm">{session.title}</span>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* User profile placeholder */}
        <div className="border-t border-white/[0.06] px-3 py-3">
          <div className="flex items-center gap-3 rounded-lg px-2 py-1.5">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-cyan-500 to-violet-600">
              <User size={15} className="text-white" />
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-slate-200">Traveler</p>
              <p className="truncate text-xs text-slate-500">Free plan</p>
            </div>
          </div>
        </div>
      </motion.aside>
      )}
    </>
  )
}
