import { useEffect, useState, useCallback } from 'react'
import { isBackendReachable } from './api.js'

// Tracks whether we are truly online (browser says online AND backend reachable).
// Fires the `online` browser event handler so the queue can auto-sync on reconnect.
export function useConnectivity(onReconnect) {
  const [online, setOnline] = useState(navigator.onLine)
  const [checking, setChecking] = useState(false)

  const verify = useCallback(async () => {
    setChecking(true)
    const ok = navigator.onLine && (await isBackendReachable())
    setOnline(ok)
    setChecking(false)
    return ok
  }, [])

  useEffect(() => {
    let mounted = true
    const goOnline = async () => {
      const ok = await verify()
      if (ok && mounted && onReconnect) onReconnect()
    }
    const goOffline = () => setOnline(false)

    window.addEventListener('online', goOnline)
    window.addEventListener('offline', goOffline)
    // Initial check + periodic re-check (catches backend coming back without a browser event).
    verify().then(ok => { if (ok && mounted && onReconnect) onReconnect() })
    const iv = setInterval(goOnline, 15000)

    return () => {
      mounted = false
      window.removeEventListener('online', goOnline)
      window.removeEventListener('offline', goOffline)
      clearInterval(iv)
    }
  }, [verify, onReconnect])

  return { online, checking, verify }
}
