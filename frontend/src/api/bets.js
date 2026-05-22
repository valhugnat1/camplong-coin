// ═══════════════════════════════════════════════════════════
// CamplongCoin — API client : Paris communautaires
// ═══════════════════════════════════════════════════════════

import { apiCall } from "./client";

/**
 * Endpoints publics (user authentifié).
 *
 * Modele : mise unique fixe, 2 a 6 options par pari (yes_no ou
 * multi_choice). 1 mise/user/pari. Resolution = arbitre OU 2 votes
 * communautaires concordants OU admin.
 */
export const betsApi = {
  list(token, params = {}) {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v != null && v !== ""),
    ).toString();
    return apiCall(`/bets${qs ? "?" + qs : ""}`, { token });
  },

  get(token, id) {
    return apiCall(`/bets/${id}`, { token });
  },

  /**
   * payload :
   *   { statement, deadline (ISO), type: 'yes_no'|'multi_choice',
   *     stake, options?: string[], creator_option_index?: number,
   *     arbiter_username?: string }
   */
  create(token, payload) {
    return apiCall("/bets", {
      method: "POST",
      token,
      body: JSON.stringify(payload),
    });
  },

  /**
   * Rejoindre un pari sur une option.
   */
  join(token, id, optionId) {
    return apiCall(`/bets/${id}/join`, {
      method: "POST",
      token,
      body: JSON.stringify({ option_id: optionId }),
    });
  },

  cancel(token, id) {
    return apiCall(`/bets/${id}`, {
      method: "DELETE",
      token,
    });
  },

  /**
   * Resolution arbitre. optionId = null → void.
   */
  resolve(token, id, optionId) {
    return apiCall(`/bets/${id}/resolve`, {
      method: "POST",
      token,
      body: JSON.stringify({ option_id: optionId }),
    });
  },

  /**
   * Vote communautaire. optionId = null → vote 'void'.
   */
  vote(token, id, optionId) {
    return apiCall(`/bets/${id}/vote`, {
      method: "POST",
      token,
      body: JSON.stringify({ option_id: optionId }),
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

  /**
   * optionId = null → void.
   */
  resolve(token, id, optionId) {
    return apiCall(`/admin/bets/${id}/resolve`, {
      method: "POST",
      token,
      body: JSON.stringify({ option_id: optionId }),
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
