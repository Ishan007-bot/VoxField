import { useEffect, useState } from 'react'

// Theme is stored on <html data-theme="..."> and persisted to localStorage.
// Defaults to the OS preference on first visit.
function initialTheme() {
  // Allow ?theme=dark|light to force a theme (handy for testing & shareable links).
  const param = new URLSearchParams(window.location.search).get('theme')
  if (param === 'light' || param === 'dark') return param
  const saved = localStorage.getItem('voxfield-theme')
  if (saved === 'light' || saved === 'dark') return saved
  // VoxField is dark-first: default to dark unless the OS explicitly prefers light.
  return window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches
    ? 'light' : 'dark'
}

export function useTheme() {
  const [theme, setTheme] = useState(initialTheme)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('voxfield-theme', theme)
    // Keep the PWA status bar / address bar in sync.
    const meta = document.querySelector('meta[name="theme-color"]')
    if (meta) meta.setAttribute('content', theme === 'dark' ? '#0c1014' : '#dde3ea')
  }, [theme])

  const toggle = () => setTheme(t => (t === 'dark' ? 'light' : 'dark'))
  return { theme, toggle }
}
