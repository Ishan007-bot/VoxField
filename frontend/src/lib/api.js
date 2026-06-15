// Backend API client. In dev, Vite proxies /api -> http://127.0.0.1:8000.
// Override with VITE_API_BASE for a deployed backend.
const BASE = import.meta.env.VITE_API_BASE || '/api'

async function req(path, opts = {}) {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!res.ok) {
    const detail = await res.text().catch(() => '')
    throw new Error(`API ${res.status}: ${detail}`)
  }
  return res.json()
}

export const api = {
  health: () => req('/health'),
  aiStatus: () => req('/ai-status'),
  stats: () => req('/stats'),
  activity: (limit = 8) => req(`/activity?limit=${limit}`),
  dashboard: () => req('/dashboard'),
  vocabulary: () => req('/vocabulary'),
  assets: (type) => req('/assets' + (type ? `?type=${encodeURIComponent(type)}` : '')),
  asset: (code) => req(`/assets/${encodeURIComponent(code)}`),
  assetTypes: () => req('/asset-types'),

  extract: (transcript, technician, language) =>
    req('/extract', { method: 'POST', body: JSON.stringify({ transcript, technician, language }) }),

  query: (question, technician, language) =>
    req('/query', { method: 'POST', body: JSON.stringify({ question, technician, language }) }),

  listWorkOrders: (status) => req('/work-orders' + (status ? `?status=${status}` : '')),
  createWorkOrder: (wo) => req('/work-orders', { method: 'POST', body: JSON.stringify(wo) }),
  updateWorkOrder: (id, patch) => req(`/work-orders/${id}`, { method: 'PATCH', body: JSON.stringify(patch) }),
  closeWorkOrder: (id) => req(`/work-orders/${id}/close`, { method: 'POST' }),
}

// Simple connectivity check used by the offline queue (Phase 4).
export async function isBackendReachable() {
  try {
    const ctrl = new AbortController()
    const t = setTimeout(() => ctrl.abort(), 2500)
    const res = await fetch((BASE) + '/health', { signal: ctrl.signal })
    clearTimeout(t)
    return res.ok
  } catch {
    return false
  }
}
