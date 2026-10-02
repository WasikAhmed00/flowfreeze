const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

export async function api(path, options = {}) {
  let response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        ...options.headers,
      },
    })
  } catch {
    throw new Error(`Cannot reach FlowFreeze API at ${API_BASE}. Start the backend and try again.`)
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
