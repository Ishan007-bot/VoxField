// Offline queue backed by IndexedDB.
// Every voice action is recorded here first, then synced to the backend.
// When offline, items wait; on reconnect we drain the queue in order.
//
// Item shape: { id, type, payload, transcript, status, attempts, createdAt, error }
//   type: 'create_wo' | 'query' | 'update_wo' | 'close_wo'
//   status: 'pending' | 'done' | 'error'
//     'pending' — waiting to sync (auto-retried on every drain)
//     'done'    — synced; cleared by clearDone()
//     'error'   — failed MAX_ATTEMPTS times; parked for a manual retry

const DB_NAME = 'voxfield'
const STORE = 'queue'
const DB_VERSION = 1

// A sync can fail transiently in the field — a blip mid-drain, an upstream 5xx.
// Such items stay 'pending' and are retried on the next drain, up to this many
// attempts, before being parked as 'error' for a manual retry. This guarantees
// nothing is silently stranded: every queued note eventually syncs or is shown
// to the worker to retry by hand.
const MAX_ATTEMPTS = 5

function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: 'id', autoIncrement: true })
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

async function tx(mode, fn) {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const t = db.transaction(STORE, mode)
    const store = t.objectStore(STORE)
    const result = fn(store)
    t.oncomplete = () => resolve(result)
    t.onerror = () => reject(t.error)
  })
}

// Add an action to the queue. Returns the stored item's id.
export async function enqueue(type, payload, transcript = '') {
  const item = {
    type, payload, transcript,
    status: 'pending',
    attempts: 0,
    createdAt: new Date().toISOString(),
    error: null,
  }
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const t = db.transaction(STORE, 'readwrite')
    const req = t.objectStore(STORE).add(item)
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

export async function getAll() {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const req = db.transaction(STORE, 'readonly').objectStore(STORE).getAll()
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

export async function pendingCount() {
  const all = await getAll()
  return all.filter(i => i.status === 'pending').length
}

// Items that exhausted their retries and now need a manual retry.
export async function errorCount() {
  const all = await getAll()
  return all.filter(i => i.status === 'error').length
}

async function update(item) {
  return tx('readwrite', (store) => store.put(item))
}

export async function remove(id) {
  return tx('readwrite', (store) => store.delete(id))
}

export async function clearDone() {
  const all = await getAll()
  await Promise.all(all.filter(i => i.status === 'done').map(i => remove(i.id)))
}

// Drain the queue: process each pending item with the provided processor fn.
// processor(item) should perform the network call and throw on failure.
//
// On failure an item is retried on the next drain until MAX_ATTEMPTS, after
// which it is parked as 'error' for a manual retry — so a single transient
// blip can no longer strand a note forever. Returns { synced, retrying, failed }:
//   synced   — items that synced this pass
//   retrying — items that failed but stay queued for the next drain
//   failed   — items that hit MAX_ATTEMPTS and now need a manual retry
export async function drain(processor) {
  const all = await getAll()
  const pending = all.filter(i => i.status === 'pending')
  let synced = 0, retrying = 0, failed = 0
  for (const item of pending) {
    try {
      const result = await processor(item)
      item.status = 'done'
      item.result = result || null
      item.error = null
      await update(item)
      synced++
    } catch (e) {
      item.attempts = (item.attempts || 0) + 1
      item.error = String(e.message || e)
      if (item.attempts >= MAX_ATTEMPTS) {
        item.status = 'error'    // give up auto-retry; await a manual retry
        failed++
      } else {
        item.status = 'pending'  // keep queued — the next drain retries it
        retrying++
      }
      await update(item)
    }
  }
  return { synced, retrying, failed }
}

// Re-arm errored items as pending with a fresh attempt budget (manual retry).
export async function retryErrored() {
  const all = await getAll()
  await Promise.all(
    all.filter(i => i.status === 'error').map(i => {
      i.status = 'pending'; i.attempts = 0; i.error = null
      return update(i)
    })
  )
}
