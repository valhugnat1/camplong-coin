// ═══════════════════════════════════════════════════════════
// CamplongCoin — API client : Poker (Texas Hold'em)
// ═══════════════════════════════════════════════════════════

import { apiCall } from "./client";

export const pokerApi = {
  // ─── User ─────────────────────────────────────────────
  listTables(token) {
    return apiCall("/casino/poker/tables", { token });
  },

  createTable(token, payload) {
    return apiCall("/casino/poker/tables", {
      method: "POST",
      token,
      body: JSON.stringify(payload),
    });
  },

  deleteTable(token, tableId) {
    return apiCall(`/casino/poker/tables/${tableId}`, {
      method: "DELETE",
      token,
    });
  },

  state(token, tableId) {
    return apiCall(`/casino/poker/tables/${tableId}/state`, { token });
  },

  sit(token, tableId, buyin) {
    return apiCall(`/casino/poker/tables/${tableId}/sit`, {
      method: "POST",
      token,
      body: JSON.stringify({ buyin }),
    });
  },

  leave(token, tableId) {
    return apiCall(`/casino/poker/tables/${tableId}/leave`, {
      method: "POST",
      token,
    });
  },

  startHand(token, tableId) {
    return apiCall(`/casino/poker/tables/${tableId}/start-hand`, {
      method: "POST",
      token,
    });
  },

  /**
   * @param {string} move 'fold'|'check'|'call'|'bet'|'raise'
   * @param {number} amount pour bet = montant ; pour raise = NOUVEAU total
   */
  act(token, tableId, move, amount = 0) {
    return apiCall(`/casino/poker/tables/${tableId}/act`, {
      method: "POST",
      token,
      body: JSON.stringify({ move, amount }),
    });
  },

  myHistory(token, limit = 20) {
    return apiCall(`/me/poker/history?limit=${limit}`, { token });
  },
};

export const adminPokerApi = {
  listTables(token) {
    return apiCall("/admin/poker/tables", { token });
  },
  createTable(token, payload) {
    return apiCall("/admin/poker/tables", {
      method: "POST",
      token,
      body: JSON.stringify(payload),
    });
  },
  updateTable(token, id, payload) {
    return apiCall(`/admin/poker/tables/${id}`, {
      method: "PATCH",
      token,
      body: JSON.stringify(payload),
    });
  },
  deleteTable(token, id) {
    return apiCall(`/admin/poker/tables/${id}`, {
      method: "DELETE",
      token,
    });
  },
  forceEndHand(token, id) {
    return apiCall(`/admin/poker/tables/${id}/force-end`, {
      method: "POST",
      token,
    });
  },
};
