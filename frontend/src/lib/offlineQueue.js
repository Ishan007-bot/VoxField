// Offline queue backed by IndexedDB.
// Every voice action is recorded here first, then synced to the backend.
// When offline, items wait; on reconnect we drain the queue in order.
//
// Item shape: { id, type, payload, transcript, status, createdAt, error }
//   type: 'create_wo' | 'query' | 'update_wo' | 'close_wo'
//   status: 'pending' | 'done' | 'error'

const DB_NAME = 'voxfield'
const STORE = 'queue'
const DB_VERSION = 1

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
// Returns { synced, failed }.
export async function drain(processor) {
  const all = await getAll()
  const pending = all.filter(i => i.status === 'pending')
  let synced = 0, failed = 0
  for (const item of pending) {
    try {
      const result = await processor(item)
      item.status = 'done'
      item.result = result || null
      item.error = null
      await update(item)
      synced++
    } catch (e) {
      item.status = 'error'
      item.error = String(e.message || e)
      await update(item)
      failed++
    }
  }
  return { synced, failed }
}

// Re-arm errored items as pending (manual retry).
export async function retryErrored() {
  const all = await getAll()
  await Promise.all(
    all.filter(i => i.status === 'error').map(i => { i.status = 'pending'; i.error = null; return update(i) })
  )
}
