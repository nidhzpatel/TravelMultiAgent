import { motion } from 'framer-motion'
import { Bot, User } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import TextReveal from './TextReveal'

interface MessageBubbleProps {
  role: 'user' | 'assistant'
  text: string
  delay?: number
  isLatest?: boolean
}

export default function MessageBubble({ role, text, delay = 0, isLatest = false }: MessageBubbleProps) {
  const isUser = role === 'user'

  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.4, delay }}
      className={`flex w-full ${isUser ? 'justify-end' : 'justify-start'}`}
    >
      <div
        className={`flex max-w-[85%] md:max-w-[70%] items-start gap-3 ${
          isUser ? 'flex-row-reverse' : 'flex-row'
        }`}
      >
        <div
          className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${
            isUser
              ? 'bg-gradient-to-br from-sky-500 to-violet-600'
              : 'glass border-white/10'
          }`}
        >
          {isUser ? <User size={16} /> : <Bot size={16} className="text-cyan-300" />}
        </div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.3, delay: delay + 0.1 }}
          className={`rounded-2xl px-5 py-3 text-[15px] leading-relaxed shadow-lg ${
            isUser
              ? 'message-user text-white rounded-br-sm'
              : 'message-assistant text-slate-100 rounded-bl-sm'
          }`}
        >
          {isUser || !isLatest ? (
            <ReactMarkdown
              components={{
                p: ({ children }) => <p className="m-0">{children}</p>,
                strong: ({ children }) => <span className="font-semibold text-cyan-300">{children}</span>,
                em: ({ children }) => <span className="italic text-violet-300">{children}</span>,
              }}
            >
              {text}
            </ReactMarkdown>
          ) : (
            <TextReveal text={text} />
          )}
        </motion.div>
      </div>
    </motion.div>
  )
}
