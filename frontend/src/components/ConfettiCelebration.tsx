import { useEffect } from 'react'
import confetti from 'canvas-confetti'

interface ConfettiCelebrationProps {
  trigger: boolean
}

export default function ConfettiCelebration({ trigger }: ConfettiCelebrationProps) {
  useEffect(() => {
    if (!trigger) return

    const duration = 2500
    const end = Date.now() + duration

    const colors = ['#67e8f9', '#a78bfa', '#fbbf24', '#f472b6']

    const frame = () => {
      confetti({
        particleCount: 4,
        angle: 60,
        spread: 55,
        origin: { x: 0 },
        colors,
        disableForReducedMotion: true,
      })
      confetti({
        particleCount: 4,
        angle: 120,
        spread: 55,
        origin: { x: 1 },
        colors,
        disableForReducedMotion: true,
      })

      if (Date.now() < end) {
        requestAnimationFrame(frame)
      }
    }

    frame()
  }, [trigger])

  return null
}
