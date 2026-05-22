// ═══════════════════════════════════════════════════════════
// CamplongCoin — API client : Casino (coinflip + futurs jeux)
// ═══════════════════════════════════════════════════════════

import { apiCall } from "./client";

/**
 * Endpoints user (JWT user).
 */
export const casinoApi = {
  /**
   * Lit la config courante (min/max bet, edge_pct, multiplicateur).
   * L'admin peut changer l'edge a chaud, donc le front doit re-lire
   * cette config au montage de la vue.
   */
  coinflipConfig(token) {
    return apiCall("/casino/coinflip/config", { token });
  },

  /**
   * Joue une partie de pile/face.
   * @param {string} token
   * @param {{bet: number, choice: 'heads'|'tails', client_seed: string}} payload
   */
  coinflipPlay(token, payload) {
    return apiCall("/casino/coinflip/play", {
      method: "POST",
      token,
      body: JSON.stringify(payload),
    });
  },

  /**
   * Historique des dernieres rounds du user courant.
   * @param {number} limit
   */
  myCoinflipHistory(token, limit = 20) {
    return apiCall(`/me/coinflip?limit=${limit}`, { token });
  },

  // ─── Roulette ────────────────────────────────────────
  rouletteConfig(token) {
    return apiCall("/casino/roulette/config", { token });
  },

  /**
   * Joue un spin avec N mises.
   * @param {string} token
   * @param {{bets: Array<{spot: string, amount: number}>, client_seed: string}} payload
   */
  rouletteSpin(token, payload) {
    return apiCall("/casino/roulette/spin", {
      method: "POST",
      token,
      body: JSON.stringify(payload),
    });
  },

  myRouletteHistory(token, limit = 20) {
    return apiCall(`/me/roulette?limit=${limit}`, { token });
  },

  // ─── Slots ──────────────────────────────────────────
  slotsConfig(token) {
    return apiCall("/casino/slots/config", { token });
  },

  /**
   * @param {string} token
   * @param {{bet: number, client_seed: string}} payload
   */
  slotsSpin(token, payload) {
    return apiCall("/casino/slots/spin", {
      method: "POST",
      token,
      body: JSON.stringify(payload),
    });
  },

  mySlotsHistory(token, limit = 20) {
    return apiCall(`/me/slots?limit=${limit}`, { token });
  },
};

/**
 * Endpoints admin (JWT admin).
 */
export const adminCasinoApi = {
  /**
   * Snapshot complet pour le dashboard admin casino.
   */
  stats(token) {
    return apiCall("/admin/casino/stats", { token });
  },
};

/**
 * Settings generiques (key/value) modifiables par l'admin.
 */
export const adminSettingsApi = {
  list(token) {
    return apiCall("/admin/settings", { token });
  },
  update(token, key, value) {
    return apiCall(`/admin/settings/${key}`, {
      method: "PATCH",
      token,
      body: JSON.stringify({ value: String(value) }),
    });
  },
};
