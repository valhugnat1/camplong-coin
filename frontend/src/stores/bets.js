// ═══════════════════════════════════════════════════════════
// CamplongCoin — Store Pinia : Paris (bets)
// ═══════════════════════════════════════════════════════════

import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { useAuthStore } from "./auth";
import { useWalletStore } from "./wallet";
import { betsApi } from "@/api/bets";

export const useBetsStore = defineStore("bets", () => {
  const auth = useAuthStore();
  const wallet = useWalletStore();

  // ─── State ────────────────────────────────────────────
  const openBets = ref([]); // /bets?status=open
  const myBets = ref([]); // /me/bets (avec my_role par item)
  const detail = ref(null); // /bets/:id courant
  const loading = ref(false);
  const error = ref(null);

  // ─── Getters ──────────────────────────────────────────
  const openByCategory = computed(() => {
    const groups = {};
    for (const b of openBets.value) {
      const cat = b.category || "Autre";
      (groups[cat] ||= []).push(b);
    }
    return groups;
  });

  const myOpenCount = computed(
    () =>
      myBets.value.filter((b) => b.status === "open" && b.my_role === "creator")
        .length,
  );

  // ─── Helpers internes ─────────────────────────────────
  function _withLoading(fn) {
    return async (...args) => {
      loading.value = true;
      error.value = null;
      try {
        return await fn(...args);
      } catch (e) {
        error.value = e.message;
        throw e;
      } finally {
        loading.value = false;
      }
    };
  }

  // Tente de rafraichir le wallet sans crasher si l'API du store differe.
  async function _refreshWallet() {
    try {
      if (typeof wallet.refresh === "function") await wallet.refresh();
      else if (typeof wallet.load === "function") await wallet.load();
      else if (typeof wallet.fetch === "function") await wallet.fetch();
    } catch (e) {
      /* silent */
    }
  }

  // ─── Actions ──────────────────────────────────────────
  const fetchOpen = _withLoading(async (params = {}) => {
    openBets.value = await betsApi.list(auth.userToken, {
      status: "open",
      ...params,
    });
  });

  const fetchMine = _withLoading(async () => {
    myBets.value = await betsApi.mine(auth.userToken);
  });

  const fetchDetail = _withLoading(async (id) => {
    detail.value = await betsApi.get(auth.userToken, id);
    return detail.value;
  });

  const create = _withLoading(async (payload) => {
    const bet = await betsApi.create(auth.userToken, payload);
    openBets.value.unshift(bet);
    await _refreshWallet(); // solde a diminue (lock du creator)
    return bet;
  });

  const match = _withLoading(async (id) => {
    const bet = await betsApi.match(auth.userToken, id);
    // L'ancien open n'apparait plus dans la liste publique
    openBets.value = openBets.value.filter((b) => b.id !== id);
    if (detail.value?.id === id) detail.value = bet;
    await _refreshWallet();
    return bet;
  });

  const cancel = _withLoading(async (id) => {
    await betsApi.cancel(auth.userToken, id);
    openBets.value = openBets.value.filter((b) => b.id !== id);
    if (detail.value?.id === id)
      detail.value = { ...detail.value, status: "cancelled" };
    await _refreshWallet();
  });

  const resolve = _withLoading(async (id, resolution) => {
    const bet = await betsApi.resolve(auth.userToken, id, resolution);
    if (detail.value?.id === id) detail.value = bet;
    await _refreshWallet();
    return bet;
  });

  const vote = _withLoading(async (id, resolution) => {
    const bet = await betsApi.vote(auth.userToken, id, resolution);
    if (detail.value?.id === id) detail.value = bet;
    // Si l'accord vient d'etre trouve, le payout a deja eu lieu → solde change.
    if (bet.status === "resolved") await _refreshWallet();
    return bet;
  });

  // ─── Reset (utile au logout) ──────────────────────────
  function reset() {
    openBets.value = [];
    myBets.value = [];
    detail.value = null;
    loading.value = false;
    error.value = null;
  }

  return {
    // state
    openBets,
    myBets,
    detail,
    loading,
    error,
    // getters
    openByCategory,
    myOpenCount,
    // actions
    fetchOpen,
    fetchMine,
    fetchDetail,
    create,
    match,
    cancel,
    resolve,
    vote,
    reset,
  };
});
