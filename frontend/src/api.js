const API_BASE = import.meta.env.VITE_API_BASE_URL || ''
const WRITE_API_KEY = import.meta.env.VITE_DEMO_WRITE_KEY || ''

export async function api(path, options = {}) {
  let response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        ...(WRITE_API_KEY && options.body ? { 'X-FlowFreeze-Write-Key': WRITE_API_KEY } : {}),
        ...options.headers,
      },
    })
  } catch {
    const endpoint = API_BASE || 'the same-origin /api endpoint'
    throw new Error(`Cannot reach FlowFreeze API at ${endpoint}. Start the backend and try again.`)
  }
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = payload.detail
    throw new Error(typeof detail === 'string' ? detail : `Request failed (${response.status}).`)
  }
  return payload
}

export const formatMoney = (value) => `৳${Number(value || 0).toLocaleString('en-BD', { maximumFractionDigits: 2 })}`

export function formatDate(value) {
  if (!value) return '—'
  return new Intl.DateTimeFormat('en-BD', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}
