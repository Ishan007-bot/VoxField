import { useEffect, useRef } from 'react'

// Adds the `.visible` class to a `.reveal` element once it is 20% on screen.
// Used everywhere for the scroll-into-view animation.
export function useReveal() {
  const ref = useRef(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const obs = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add('visible')
            obs.unobserve(e.target)
          }
        })
      },
      { threshold: 0.2 }
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [])
  return ref
}

// Reveal a whole container's `.reveal` children (for staggered grids).
export function useRevealGroup() {
  const ref = useRef(null)
  useEffect(() => {
    const root = ref.current
    if (!root) return
    const items = root.querySelectorAll('.reveal')
    const obs = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add('visible')
            obs.unobserve(e.target)
          }
        })
      },
      { threshold: 0.2 }
    )
    items.forEach((i) => obs.observe(i))
    return () => obs.disconnect()
  }, [])
  return ref
}
