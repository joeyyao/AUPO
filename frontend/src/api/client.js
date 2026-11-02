/**
 * Thin fetch wrapper around the FastAPI backend.
 *
 * The base URL is always same-origin "/api" in production; in development the
 * Vite dev server proxies "/api" to the FastAPI port (see vite.config.js).
 */
const BASE_URL = import.meta.env.VITE_API_BASE || '/api'

export class ApiError extends Error {
  constructor(message, status, kind) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.kind = kind
  }
}

async function request(path, { timeoutMs = 20000 } = {}) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  let response
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      headers: { Accept: 'application/json' },
      signal: controller.signal,
    })
  } catch (error) {
    clearTimeout(timer)
    if (error.name === 'AbortError') {
      throw new ApiError('The request timed out. The backend may be unreachable.', 0, 'timeout')
    }
    throw new ApiError('Could not reach the backend API.', 0, 'network')
  }
  clearTimeout(timer)

  const text = await response.text()
  let payload = null
  if (text) {
    try {
      payload = JSON.parse(text)
    } catch {
      payload = null
    }
  }

  if (!response.ok) {
    const detail =
      (payload && (payload.detail || payload.message)) ||
      text ||
      `Request failed with HTTP ${response.status}`
    throw new ApiError(
      typeof detail === 'string' ? detail : JSON.stringify(detail),
      response.status,
      'http',
    )
  }
  return payload
}

export const api = {
  health: () => request('/health'),
  listOrders: () => request('/orders'),
  getOrder: (orderNo) => request(`/orders/${encodeURIComponent(orderNo)}`),
  getTracking: (orderNo, { refresh = false } = {}) =>
    request(`/orders/${encodeURIComponent(orderNo)}/tracking${refresh ? '?refresh=true' : ''}`, {
      timeoutMs: 30000,
    }),
}
