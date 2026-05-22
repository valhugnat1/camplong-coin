// ═══════════════════════════════════════════════════════════
// CamplongCoin — Store Pinia : Paris communautaires
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
  const myBets = ref([]); // /me/bets
  const detail = ref(null); // /bets/:id
  const loading = ref(false);
  const error = ref(null);

  // ─── Getters ──────────────────────────────────────────
  const myOpenCount = computed(
    () =>
      myBets.value.filter(
        (b) => b.status === "open" && b.my_role === "creator",
      ).length,
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

  async function _refreshWallet() {
    try {
      if (typeof wallet.refresh === "function") await wallet.refresh();
      else if (typeof wallet.load === "function") await wallet.load();
      else if (typeof wallet.fetch === "function") await wallet.fetch();
    } catch (e) {
      /* silent */
    }
  }

  function _replaceInList(list, bet) {
    const i = list.findIndex((b) => b.id === bet.id);
    if (i >= 0) list[i] = bet;
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
    // Solde diminué si le créateur a participé
    if (payload.creator_option_index != null) await _refreshWallet();
    return bet;
  });

  const join = _withLoading(async (id, optionId) => {
    const bet = await betsApi.join(auth.userToken, id, optionId);
    _replaceInList(openBets.value, bet);
    if (detail.value?.id === id) detail.value = bet;
    await _refreshWallet();
    return bet;
  });

  const cancel = _withLoading(async (id) => {
    const bet = await betsApi.cancel(auth.userToken, id);
    openBets.value = openBets.value.filter((b) => b.id !== id);
    if (detail.value?.id === id) detail.value = bet;
    await _refreshWallet();
    return bet;
  });

  const resolve = _withLoading(async (id, optionId) => {
    const bet = await betsApi.resolve(auth.userToken, id, optionId);
    if (detail.value?.id === id) detail.value = bet;
    openBets.value = openBets.value.filter((b) => b.id !== id);
    await _refreshWallet();
    return bet;
  });

  const vote = _withLoading(async (id, optionId) => {
    const bet = await betsApi.vote(auth.userToken, id, optionId);
    if (detail.value?.id === id) detail.value = bet;
    // Si l'accord vient d'etre trouve, settlement et payouts on-chain
    if (bet.status === "resolved") {
      openBets.value = openBets.value.filter((b) => b.id !== id);
      await _refreshWallet();
    }
    return bet;
  });

  function reset() {
    openBets.value = [];
    myBets.value = [];
    detail.value = null;
    loading.value = false;
    error.value = null;
  }

  return {
    openBets,
    myBets,
    detail,
    loading,
    error,
    myOpenCount,
    fetchOpen,
    fetchMine,
    fetchDetail,
    create,
    join,
    cancel,
    resolve,
    vote,
    reset,
  };
});
