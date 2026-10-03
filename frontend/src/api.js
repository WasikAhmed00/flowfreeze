const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
const WRITE_API_KEY = import.meta.env.VITE_DEMO_WRITE_KEY || ''

export async function api(path, options = {}) {
  let response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: { ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...(WRITE_API_KEY && options.body ? { 'X-FlowFreeze-Write-Key': WRITE_API_KEY } : {}), ...options.headers },
    })
  } catch { throw new Error(`Cannot reach FlowFreeze API at ${API_BASE}. Start the backend and try again.`) }
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(typeof payload.detail === 'string' ? payload.detail : `Request failed (${response.status}).`)
  return payload
}

export const formatMoney = (value) => `৳${Math.round(Number(value || 0)).toLocaleString('en-IN')}`
export const shortCaseId = (value = '') => { const match = String(value).match(/(\d{1,})$/); return match ? `FF-${match[1].padStart(4, '0')}` : value }
export const formatDate = (value) => value ? new Intl.DateTimeFormat('en-BD', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Dhaka', timeZoneName: 'short' }).format(new Date(value)) : '—'
export const relativeTime = (value) => { if (!value) return '—'; const seconds = Math.max(0, Math.round((Date.now() - new Date(value).getTime()) / 1000)); if (seconds < 60) return `${seconds} seconds ago`; if (seconds < 3600) return `${Math.round(seconds / 60)} minutes ago`; if (seconds < 86400) return `${Math.round(seconds / 3600)} hours ago`; return `${Math.round(seconds / 86400)} days ago` }

const categories = {
  fanout: 'Fan-out', fanout_cashout: 'Fan-out', rapid_cashout: 'Rapid movement', multi_hop: 'Rapid movement',
  direct_fraud: 'Mule', mixed_balance: 'Mule', slow_mule: 'Slow mule', false_positive: 'Likely legitimate',
  wrong_recipient: 'Likely legitimate', legitimate_relay: 'Likely legitimate', payroll_split: 'Likely legitimate',
}
export const categoryOf = (scenarioType = '') => categories[scenarioType] || 'Pattern pending'
export const walletTypeLabel = (type = '') => ({ individual: 'Personal', agent: 'Agent', merchant: 'Merchant', cash_destination: 'Cash-out point' }[type] || 'Personal')
export function walletAlias(walletId = '') {
  let hash = 2166136261
  for (const char of String(walletId)) hash = Math.imul(hash ^ char.charCodeAt(0), 16777619) >>> 0
  const prefixes = ['013', '014', '015', '016', '017', '018', '019']
  return `${prefixes[hash % prefixes.length]}${String(hash % 100000000).padStart(8, '0')}`
}
export const maskWallet = (value = '') => { const digits = String(value).replace(/\D/g, ''); return digits.length >= 6 ? `${digits.slice(0, 3)}XX-XXX${digits.slice(-3)}` : value }
export const displayWallet = (walletId) => maskWallet(walletAlias(walletId))
export function nodeRole(node = {}, edges = []) {
  if (node.customer_type === 'cash_destination') return 'Cash-out'
  if (node.role === 'direct_recipient' || node.isDirectRecipient) return 'Direct recipient'
  if (node.role === 'cash_out' || edges.some((edge) => edge.sender_wallet === node.wallet_id && edge.is_cashout)) return 'Cash-out'
  return 'Relay'
}
