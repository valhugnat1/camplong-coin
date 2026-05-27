// ═══════════════════════════════════════════════════════════
// CamplongCoin — Store Pinia : Poker (Texas Hold'em)
// ═══════════════════════════════════════════════════════════
//
// Pas de WebSocket : on poll /casino/poker/tables/{id}/state toutes
// les 2s tant qu'on est sur la vue. La fonction `startPolling()`
// retourne un `stop()` a appeler en `onBeforeUnmount`.
//
// Le state local est intentionnellement "dumb" : il reflete juste la
// derniere reponse serveur. Toutes les regles metier (qui doit jouer,
// montant min de raise, etc.) sont calculees cote backend.

import { defineStore } from "pinia";
import { ref } from "vue";
import { useAuthStore } from "./auth";
import { useWalletStore } from "./wallet";
import { pokerApi } from "@/api/poker";

const POLL_MS = 2000;

export const usePokerStore = defineStore("poker", () => {
  const auth = useAuthStore();
  const wallet = useWalletStore();

  // ─── State ─────────────────────────────────────────────
  const tables = ref([]);            // lobby
  const tableState = ref(null);      // state courant de la table affichee
  const loading = ref(false);
  const acting = ref(false);
  const error = ref(null);
  const history = ref([]);

  // ─── Lobby ─────────────────────────────────────────────
  async function loadTables() {
    loading.value = true;
    error.value = null;
    try {
      tables.value = await pokerApi.listTables(auth.userToken);
    } catch (e) {
      error.value = e.message;
    } finally {
      loading.value = false;
    }
  }

  // ─── Une table ─────────────────────────────────────────
  async function fetchState(tableId) {
    try {
      tableState.value = await pokerApi.state(auth.userToken, tableId);
    } catch (e) {
      error.value = e.message;
    }
  }

  /**
   * Lance un polling toutes les POLL_MS ms. Retourne stop().
   */
  function startPolling(tableId) {
    let stopped = false;
    let timer = null;

    const tick = async () => {
      if (stopped) return;
      await fetchState(tableId);
      if (!stopped) timer = setTimeout(tick, POLL_MS);
    };
    tick();

    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
    };
  }

  async function sit(tableId, buyin) {
    acting.value = true;
    error.value = null;
    try {
      const r = await pokerApi.sit(auth.userToken, tableId, buyin);
      await fetchState(tableId);
      wallet.refresh().catch(() => {});
      return r;
    } catch (e) {
      error.value = e.message;
      throw e;
    } finally {
      acting.value = false;
    }
  }

  async function leave(tableId) {
    acting.value = true;
    error.value = null;
    try {
      const r = await pokerApi.leave(auth.userToken, tableId);
      await fetchState(tableId);
      wallet.refresh().catch(() => {});
      return r;
    } catch (e) {
      error.value = e.message;
      throw e;
    } finally {
      acting.value = false;
    }
  }

  async function startHand(tableId) {
    acting.value = true;
    error.value = null;
    try {
      const r = await pokerApi.startHand(auth.userToken, tableId);
      await fetchState(tableId);
      return r;
    } catch (e) {
      error.value = e.message;
      throw e;
    } finally {
      acting.value = false;
    }
  }

  async function act(tableId, move, amount = 0) {
    acting.value = true;
    error.value = null;
    try {
      const r = await pokerApi.act(auth.userToken, tableId, move, amount);
      // Re-fetch tout de suite pour avoir la suite (street suivante, prochain joueur, etc.)
      await fetchState(tableId);
      return r;
    } catch (e) {
      error.value = e.message;
      throw e;
    } finally {
      acting.value = false;
    }
  }

  async function createTable(payload) {
    acting.value = true;
    error.value = null;
    try {
      const r = await pokerApi.createTable(auth.userToken, payload);
      await loadTables();
      return r;
    } catch (e) {
      error.value = e.message;
      throw e;
    } finally {
      acting.value = false;
    }
  }

  async function deleteTable(tableId) {
    acting.value = true;
    error.value = null;
    try {
      const r = await pokerApi.deleteTable(auth.userToken, tableId);
      await loadTables();
      return r;
    } catch (e) {
      error.value = e.message;
      throw e;
    } finally {
      acting.value = false;
    }
  }

  async function loadHistory(limit = 20) {
    try {
      history.value = await pokerApi.myHistory(auth.userToken, limit);
    } catch (e) {
      error.value = e.message;
    }
  }

  function reset() {
    tables.value = [];
    tableState.value = null;
    history.value = [];
    error.value = null;
  }

  return {
    // state
    tables,
    tableState,
    history,
    loading,
    acting,
    error,
    // actions
    loadTables,
    fetchState,
    startPolling,
    sit,
    leave,
    startHand,
    act,
    createTable,
    deleteTable,
    loadHistory,
    reset,
  };
});
