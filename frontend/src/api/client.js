import router from '@/router'
import { useAuthStore } from '@/stores/auth'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

/**
 * Wrapper fetch.
 *
 * - Injecte automatiquement le Bearer token (param `token`).
 * - Sur 401, déduit du token utilisé si c'est une session user ou admin,
 *   nettoie l'auth, redirige vers le login adapté en gardant l'URL actuelle.
 * - Throw une Error avec un message lisible dans tous les autres cas d'erreur.
 */
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

  if (r.status === 401 && token) {
    handleUnauthorized(token)
    throw new Error('Session expirée. Reconnecte-toi.')
  }

  if (!r.ok) {
    const body = await r.json().catch(() => ({}))
    throw new Error(body.detail || `HTTP ${r.status}`)
  }
  return r.json()
}

function handleUnauthorized(usedToken) {
  // Lazy import pour éviter une circular dependency à l'init du store
  const auth = useAuthStore()
  const currentPath = router.currentRoute.value.fullPath

  // Distingue les sessions user et admin : on regarde quel token a servi
  // pour la requête qui vient de fail.
  if (usedToken === auth.adminToken) {
    auth.logoutAdmin()
    router.push({
      name: 'admin-login',
      query: { redirect: currentPath }
    })
  } else if (usedToken === auth.userToken) {
    auth.logoutUser()
    router.push({
      name: 'login',
      query: { redirect: currentPath }
    })
  }
  // Sinon : token utilisé inconnu (cas tordu), on ne fait rien
}

export { API_URL }
