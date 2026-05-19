const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export async function apiCall(path, { token, ...opts } = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(opts.headers || {})
  }

  let r
  try {
    r = await fetch(`${API_URL}${path}`, { ...opts, headers })
  } catch (e) {
    throw new Error('Impossible de joindre le backend (' + API_URL + ')')
  }

  if (!r.ok) {
    const body = await r.json().catch(() => ({}))
    throw new Error(body.detail || `HTTP ${r.status}`)
  }
  return r.json()
}

export { API_URL }
