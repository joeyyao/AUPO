/** Display helpers shared by the components. */

const AUD = new Intl.NumberFormat('en-AU', {
  style: 'currency',
  currency: 'AUD',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

/** Format any amount as Australian dollars with exactly two decimals. */
export function money(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return 'A$0.00'
  // Intl renders AUD as "$1,234.56" / "-$1,234.56"; the brief requires AUD to be explicit.
  const formatted = AUD.format(number)
  const withCurrency = formatted.replace('$', 'A$')
  return withCurrency
}

/** Plain decimal formatting for non-currency numbers. */
export function decimal(value, digits = 2) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed.toFixed(digits) : '0.00'
}

const STATUS_LABELS = {
  completed: 'Completed',
  in_transit: 'In Transit',
  pending: 'Pending',
  cancelled: 'Cancelled',
}

export function orderStatusLabel(status) {
  return STATUS_LABELS[String(status || '').toLowerCase()] || status || 'Unknown'
}

export function orderStatusClass(status) {
  const key = String(status || '').toLowerCase().replace(/\s+/g, '_')
  return `status-pill status-${key}`
}

/** Courier states returned by the API -> badge class + label. */
export function trackingBadge(state, statusCode) {
  if (state === 'available') {
    const map = {
      delivered: { label: 'Delivered', css: 'badge-delivered' },
      in_transit: { label: 'In Transit', css: 'badge-transit' },
      awaiting_collection: { label: 'Awaiting Collection', css: 'badge-awaiting' },
      unknown: { label: 'Status Returned', css: 'badge-transit' },
    }
    return map[statusCode] || { label: 'Status Returned', css: 'badge-transit' }
  }
  if (state === 'not_implemented') return { label: 'Not Implemented', css: 'badge-notimpl' }
  if (state === 'error') return { label: 'API Error', css: 'badge-error' }
  return { label: 'Unavailable', css: 'badge-unavailable' }
}

/** ISO timestamp -> "13 Feb 2025, 11:49 am AEST" (Australia/Melbourne). */
export function formatDateTime(iso) {
  if (!iso) return ''
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return String(iso)
  try {
    return new Intl.DateTimeFormat('en-AU', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      timeZoneName: 'short',
      timeZone: 'Australia/Melbourne',
    }).format(date)
  } catch {
    return date.toISOString()
  }
}
