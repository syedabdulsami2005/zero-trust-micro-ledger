// API client for the MicroLedger SOC Gateway
// Base URL read from env (default: http://127.0.0.1:8765)

const BASE_URL = import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8765'

export class ApiError extends Error {
  constructor(code, message) {
    super(message)
    this.code = code
    this.name = 'ApiError'
  }
}

async function apiFetch(path, options = {}) {
  const url = `${BASE_URL}${path}`
  try {
    const res = await fetch(url, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      throw new ApiError(res.status, data.error ?? `HTTP ${res.status}`)
    }
    return data
  } catch (err) {
    if (err instanceof ApiError) throw err
    throw new ApiError(0, 'Gateway unreachable — is the Python server running?')
  }
}

// ── Endpoints ─────────────────────────────────────────────────────────────────

export const getHealth = () => apiFetch('/api/health')

export const getState = () => apiFetch('/api/state')

export const getFiles = () => apiFetch('/api/files')

export const getEvents = (limit = 100, filters = {}) => {
  const params = new URLSearchParams({ limit: String(limit) })
  if (filters.change_type) params.set('change_type', filters.change_type)
  if (filters.file_name)   params.set('file_name',   filters.file_name)
  if (filters.time_from)   params.set('time_from',   filters.time_from)
  if (filters.time_to)     params.set('time_to',     filters.time_to)
  if (filters.sort)        params.set('sort',         filters.sort)
  return apiFetch(`/api/events?${params}`)
}

export const getLedger = (limit = 50, offset = 0) =>
  apiFetch(`/api/ledger?limit=${limit}&offset=${offset}`)

export const getLedgerBlock = (index) =>
  apiFetch(`/api/ledger/${index}`)

export const getVerification = (limit = 50) =>
  apiFetch(`/api/verification?limit=${limit}`)

/**
 * Get alerts, optionally filtered by lifecycle status.
 * @param {number} limit
 * @param {string} status  "all"|"active"|"acknowledged"|"resolved"|"unresolved"
 */
export const getAlerts = (limit = 100, status = 'all') => {
  const params = new URLSearchParams({ limit: String(limit), status })
  return apiFetch(`/api/alerts?${params}`)
}

export const runVerification = () =>
  apiFetch('/api/actions/run-verification', { method: 'POST', body: '{}' })

/**
 * Acknowledge an alert by ID (active → acknowledged).
 * @param {string} alertId
 */
export const acknowledgeAlert = (alertId) =>
  apiFetch(`/api/alerts/${alertId}/acknowledge`, { method: 'POST', body: '{}' })

/**
 * Export a data bundle.
 * @param {string} type  "full"|"events"|"alerts"|"verification"|"incident"
 * @param {object} options  { format, from_index, to_index, time_from, time_to,
 *                            file_name, change_type, alert_id, incident_id }
 */
export const exportData = (type = 'full', options = {}) =>
  apiFetch('/api/exports', {
    method: 'POST',
    body: JSON.stringify({ type, ...options }),
  })

export const getCheckpoints = () => apiFetch('/api/checkpoints')

export const restoreCheckpoint = (checkpointFilename) =>
  apiFetch('/api/actions/restore-checkpoint', {
    method: 'POST',
    body: JSON.stringify({ checkpoint_filename: checkpointFilename }),
  })

export const getAuditActivity = (sessionId = null) => {
  const params = new URLSearchParams()
  if (sessionId) params.set('session_id', sessionId)
  return apiFetch(`/api/audit/activity?${params}`)
}

export const loginUser = (user = 'admin', role = 'system_administrator', sessionId = null) =>
  apiFetch('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ user, role, session_id: sessionId }),
  })

export const logoutUser = (sessionId = 'sess-default', user = 'admin') =>
  apiFetch('/api/auth/logout', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId, user }),
  })

export { BASE_URL }
