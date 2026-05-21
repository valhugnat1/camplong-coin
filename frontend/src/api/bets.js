// ═══════════════════════════════════════════════════════════
// CamplongCoin — API client : Paris (bets)
// ═══════════════════════════════════════════════════════════

import { apiCall } from "./client";

/**
 * Endpoints publics (user authentifié).
 */
export const betsApi = {
  /**
   * @param {string} token
   * @param {{status?: 'open'|'matched'|'resolved'|'cancelled'|'expired'|'all',
   *          category?: string}} params
   */
  list(token, params = {}) {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v != null && v !== ""),
    ).toString();
    return apiCall(`/bets${qs ? "?" + qs : ""}`, { token });
  },

  get(token, id) {
    return apiCall(`/bets/${id}`, { token });
  },

  create(token, payload) {
    return apiCall("/bets", {
      method: "POST",
      token,
      body: JSON.stringify(payload),
    });
  },

  match(token, id) {
    return apiCall(`/bets/${id}/match`, {
      method: "POST",
      token,
    });
  },

  cancel(token, id) {
    return apiCall(`/bets/${id}`, {
      method: "DELETE",
      token,
    });
  },

  /**
   * @param {'yes'|'no'|'void'} resolution
   */
  resolve(token, id, resolution) {
    return apiCall(`/bets/${id}/resolve`, {
      method: "POST",
      token,
      body: JSON.stringify({ resolution }),
    });
  },

  mine(token) {
    return apiCall("/me/bets", { token });
  },
};

/**
 * Endpoints admin.
 */
export const adminBetsApi = {
  list(token, params = {}) {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v != null && v !== ""),
    ).toString();
    return apiCall(`/admin/bets${qs ? "?" + qs : ""}`, { token });
  },

  resolve(token, id, resolution) {
    return apiCall(`/admin/bets/${id}/resolve`, {
      method: "POST",
      token,
      body: JSON.stringify({ resolution }),
    });
  },

  cancel(token, id) {
    return apiCall(`/admin/bets/${id}/cancel`, {
      method: "POST",
      token,
    });
  },

  delete(token, id) {
    return apiCall(`/admin/bets/${id}`, {
      method: "DELETE",
      token,
    });
  },
};
