import { useReveal } from '../lib/useReveal.js'

// A neumorphic card that animates into view on scroll.
export function RevealCard({ className = '', children, as: Tag = 'div', ...rest }) {
  const ref = useReveal()
  return (
    <Tag ref={ref} className={`card reveal ${className}`} {...rest}>
      {children}
    </Tag>
  )
}

export function Reveal({ className = '', children }) {
  const ref = useReveal()
  return <div ref={ref} className={`reveal ${className}`}>{children}</div>
}
