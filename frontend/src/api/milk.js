// ═══════════════════════════════════════════════════════════
// CamplongCoin — API client : Bourse du Lait (AMM x*y=k)
// ═══════════════════════════════════════════════════════════

import { apiCall } from "./client";

/**
 * Endpoints user (JWT user).
 */
export const milkApi = {
  pools(token) {
    return apiCall("/milk/pools", { token });
  },

  pool(token, symbol) {
    return apiCall(`/milk/pools/${encodeURIComponent(symbol)}`, { token });
  },

  chart(token, symbol, minutes = 24 * 60) {
    return apiCall(
      `/milk/pools/${encodeURIComponent(symbol)}/chart?minutes=${minutes}`,
      { token },
    );
  },

  quote(token, symbol, { side, amount }) {
    return apiCall(
      `/milk/pools/${encodeURIComponent(symbol)}/quote?side=${side}&amount=${amount}`,
      { token },
    );
  },

  swap(token, symbol, payload) {
    return apiCall(`/milk/pools/${encodeURIComponent(symbol)}/swap`, {
      method: "POST",
      token,
      body: JSON.stringify(payload),
    });
  },

  poolTrades(token, symbol, limit = 20) {
    return apiCall(
      `/milk/pools/${encodeURIComponent(symbol)}/trades?limit=${limit}`,
      { token },
    );
  },

  poolChaos(token, symbol, limit = 20) {
    return apiCall(
      `/milk/pools/${encodeURIComponent(symbol)}/chaos?limit=${limit}`,
      { token },
    );
  },

  myPositions(token) {
    return apiCall("/me/milk/positions", { token });
  },

  myTrades(token, limit = 50) {
    return apiCall(`/me/milk/trades?limit=${limit}`, { token });
  },
};

/**
 * Endpoints admin (JWT admin).
 */
export const adminMilkApi = {
  pools(token) {
    return apiCall("/admin/milk/pools", { token });
  },
  createPool(token, payload) {
    return apiCall("/admin/milk/pools", {
      method: "POST",
      token,
      body: JSON.stringify(payload),
    });
  },
  updatePool(token, id, payload) {
    return apiCall(`/admin/milk/pools/${id}`, {
      method: "PATCH",
      token,
      body: JSON.stringify(payload),
    });
  },
  injectChaos(token, id, payload) {
    return apiCall(`/admin/milk/pools/${id}/inject`, {
      method: "POST",
      token,
      body: JSON.stringify(payload),
    });
  },
  chaosHistory(token, { poolId, limit = 50 } = {}) {
    const q = new URLSearchParams();
    if (poolId != null) q.set("pool_id", poolId);
    if (limit) q.set("limit", limit);
    return apiCall(`/admin/milk/chaos?${q.toString()}`, { token });
  },
  recentTrades(token, { poolId, limit = 50 } = {}) {
    const q = new URLSearchParams();
    if (poolId != null) q.set("pool_id", poolId);
    if (limit) q.set("limit", limit);
    return apiCall(`/admin/milk/trades?${q.toString()}`, { token });
  },

  // ─── Chaos templates ───────────────────────────────
  listTemplates(token) {
    return apiCall("/admin/milk/templates", { token });
  },
  createTemplate(token, payload) {
    return apiCall("/admin/milk/templates", {
      method: "POST",
      token,
      body: JSON.stringify(payload),
    });
  },
  updateTemplate(token, id, payload) {
    return apiCall(`/admin/milk/templates/${id}`, {
      method: "PATCH",
      token,
      body: JSON.stringify(payload),
    });
  },
  deleteTemplate(token, id) {
    return apiCall(`/admin/milk/templates/${id}`, {
      method: "DELETE",
      token,
    });
  },
  previewTemplate(token, id) {
    return apiCall(`/admin/milk/templates/${id}/preview`, {
      method: "POST",
      token,
    });
  },
  chaosAnalysis(token, referenceBottles = 200) {
    return apiCall(
      `/admin/milk/chaos/analysis?reference_bottles=${referenceBottles}`,
      { token },
    );
  },
};
