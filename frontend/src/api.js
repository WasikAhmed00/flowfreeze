const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
const WRITE_API_KEY = import.meta.env.VITE_DEMO_WRITE_KEY || ''

export async function api(path, options = {}) {
  let response
  try { response = await fetch(`${API_BASE}${path}`, { ...options, headers: { ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...(WRITE_API_KEY && options.body ? { 'X-FlowFreeze-Write-Key': WRITE_API_KEY } : {}), ...options.headers } }) } catch { throw new Error(`Cannot reach FlowFreeze API at ${API_BASE}. Start the backend and try again.`) }
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(typeof payload.detail === 'string' ? payload.detail : `Request failed (${response.status}).`)
  return payload
}

export const formatMoney = (value) => `৳${Math.round(Number(value || 0)).toLocaleString('en-BD')}`
export const shortCaseId = (value = '') => {
  const match = String(value).match(/(\d{1,})$/)
  return match ? `FF-${match[1].padStart(4, '0')}` : value
}
export const maskWallet = (value = '') => {
  const digits = String(value).replace(/\D/g, '')
  return digits.length >= 6 ? `${digits.slice(0, 3)}XX-XXX${digits.slice(-3)}` : value
}
export function formatDate(value) {
  if (!value) return '—'
  return new Intl.DateTimeFormat('en-BD', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Dhaka' }).format(new Date(value))
}
export function relativeTime(value) {
  if (!value) return '—'
  const seconds = Math.max(0, Math.round((Date.now() - new Date(value).getTime()) / 1000))
  if (seconds < 60) return `${seconds} s ago`
  if (seconds < 3600) return `${Math.round(seconds / 60)} min ago`
  if (seconds < 86400) return `${Math.round(seconds / 3600)} h ago`
  return `${Math.round(seconds / 86400)} d ago`
}
