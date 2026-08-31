import { cn } from '../lib/utils'

interface ShimmerTextProps {
  children: React.ReactNode
  className?: string
  as?: 'h1' | 'h2' | 'h3' | 'p' | 'span'
}

export default function ShimmerText({ children, className, as: Component = 'span' }: ShimmerTextProps) {
  return (
    <Component className={cn('shimmer-text', className)}>
      {children}
    </Component>
  )
}
