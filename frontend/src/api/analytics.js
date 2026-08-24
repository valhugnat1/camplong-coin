// ═══════════════════════════════════════════════════════════
// CamplongCoin — API client : Analytics
// ═══════════════════════════════════════════════════════════

import { apiCall } from "./client";

/**
 * Endpoints admin (JWT admin).
 */
export const adminAnalyticsApi = {
  /**
   * Rapport transverse par joueur : PnL borne a la periode, activite casino,
   * trading lait, positions par bourse et agregats globaux.
   *
   * @param {string} token  JWT admin
   * @param {string} [since] Date ISO (UTC). Filtre l'activite ; la base de
   *                         mesure est le solde reconstruit a cette date.
   */
  overview(token, since) {
    const qs = since ? `?since=${encodeURIComponent(since)}` : "";
    return apiCall(`/admin/analytics${qs}`, { token });
  },

  /**
   * Mouvements user <-> tresorerie avec leur classification courante,
   * pour l'ecran d'ajustement des depots.
   */
  flows(token, since) {
    const qs = since ? `?since=${encodeURIComponent(since)}` : "";
    return apiCall(`/admin/analytics/flows${qs}`, { token });
  },

  /**
   * Reclasse un mouvement. `label = null` retire la correction manuelle et
   * revient a la deduction automatique.
   *
   * @param {'onboarding'|'topup'|'withdrawal'|'ignore'|null} label
   */
  setLabel(token, txId, label, note = "") {
    return apiCall(`/admin/analytics/flows/${txId}`, {
      method: "PUT",
      token,
      body: JSON.stringify({ label, note }),
    });
  },
};

/**
 * Endpoints joueur (JWT user).
 */
export const myStatsApi = {
  /**
   * Recap perso du joueur courant : ses propres chiffres uniquement,
   * sans totaux ni podiums (ils n'auraient pas de sens sur une personne).
   */
  get(token, since) {
    const qs = since ? `?since=${encodeURIComponent(since)}` : "";
    return apiCall(`/me/stats${qs}`, { token });
  },

  /** Classement public par solde — la source du bandeau defilant. */
  leaderboard(token) {
    return apiCall("/leaderboard", { token });
  },
};
