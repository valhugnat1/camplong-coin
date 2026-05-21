// ═══════════════════════════════════════════════════════════
// CamplongCoin — Store Pinia : Casino (coinflip + futurs jeux)
// ═══════════════════════════════════════════════════════════

import { defineStore } from "pinia";
import { ref } from "vue";
import { useAuthStore } from "./auth";
import { useWalletStore } from "./wallet";
import { casinoApi } from "@/api/casino";

export const useCasinoStore = defineStore("casino", () => {
  const auth = useAuthStore();
  const wallet = useWalletStore();

  // ─── State ────────────────────────────────────────────
  // Config dynamique : l'admin peut changer l'edge, donc on refetch
  // la config a chaque entree dans la vue Coinflip.
  const config = ref({
    min_bet: 1,
    max_bet: 200,
    edge_pct: 2,
    win_multiplier: 1.96,
  });
  const history = ref([]);
  const lastResult = ref(null); // PlayResult du dernier flip (pour confettis + verifier)
  const loading = ref(false);
  const playing = ref(false);
  const error = ref(null);

  // ─── Roulette ──────────────────────────────────────────
  const rouletteConfig = ref({
    min_bet: 1,
    max_bet: 200,
    house_edge_pct: 2.7,
  });
  const rouletteHistory = ref([]);
  const rouletteLastResult = ref(null);
  const rouletteSpinning = ref(false);

  // ─── Actions ──────────────────────────────────────────
  async function loadConfig() {
    try {
      config.value = await casinoApi.coinflipConfig(auth.userToken);
    } catch (e) {
      error.value = e.message;
    }
  }

  async function loadHistory(limit = 20) {
    loading.value = true;
    try {
      history.value = await casinoApi.myCoinflipHistory(auth.userToken, limit);
    } catch (e) {
      error.value = e.message;
    } finally {
      loading.value = false;
    }
  }

  /**
   * Tire au sort une partie. Retourne le PlayResult brut.
   * Le composant utilise `lastResult` pour l'animation/affichage.
   */
  async function play({ bet, choice, clientSeed }) {
    playing.value = true;
    error.value = null;
    try {
      const result = await casinoApi.coinflipPlay(auth.userToken, {
        bet,
        choice,
        client_seed: clientSeed,
      });
      lastResult.value = result;
      // Prepend dans l'historique local pour eviter un refetch
      history.value.unshift({
        id: result.id,
        username: wallet.me?.username || "",
        bet_amount: result.bet_amount,
        choice: result.choice,
        outcome: result.outcome,
        win: result.win,
        payout: result.payout,
        status: "settled",
        ts: result.ts,
        tx_hash_lock: result.tx_hash_lock,
        tx_hash_payout: result.tx_hash_payout,
      });
      // Rafraichit le solde (lock/release on-chain a deja eu lieu)
      wallet.refresh().catch(() => {});
      return result;
    } catch (e) {
      error.value = e.message;
      throw e;
    } finally {
      playing.value = false;
    }
  }

  function reset() {
    history.value = [];
    lastResult.value = null;
    rouletteHistory.value = [];
    rouletteLastResult.value = null;
    error.value = null;
  }

  // ─── Roulette actions ──────────────────────────────────
  async function loadRouletteConfig() {
    try {
      rouletteConfig.value = await casinoApi.rouletteConfig(auth.userToken);
    } catch (e) {
      error.value = e.message;
    }
  }

  async function loadRouletteHistory(limit = 20) {
    loading.value = true;
    try {
      rouletteHistory.value = await casinoApi.myRouletteHistory(
        auth.userToken,
        limit,
      );
    } catch (e) {
      error.value = e.message;
    } finally {
      loading.value = false;
    }
  }

  /**
   * Tire un spin avec N mises.
   * @param {{bets: Array, clientSeed: string}} args
   */
  async function rouletteSpinAction({ bets, clientSeed }) {
    rouletteSpinning.value = true;
    error.value = null;
    try {
      const result = await casinoApi.rouletteSpin(auth.userToken, {
        bets,
        client_seed: clientSeed,
      });
      rouletteLastResult.value = result;
      // Prepend dans l'historique local (pas de refetch)
      rouletteHistory.value.unshift({
        id: result.id,
        username: wallet.me?.username || "",
        total_bet: result.total_bet,
        total_payout: result.total_payout,
        net_pnl: result.net_pnl,
        bets: result.bets,
        outcome_number: result.outcome_number,
        outcome_color: result.outcome_color,
        status: "settled",
        ts: result.ts,
        tx_hash_lock: result.tx_hash_lock,
        tx_hash_payout: result.tx_hash_payout,
      });
      wallet.refresh().catch(() => {});
      return result;
    } catch (e) {
      error.value = e.message;
      throw e;
    } finally {
      rouletteSpinning.value = false;
    }
  }

  return {
    // state
    config,
    history,
    lastResult,
    loading,
    playing,
    error,
    rouletteConfig,
    rouletteHistory,
    rouletteLastResult,
    rouletteSpinning,
    // actions
    loadConfig,
    loadHistory,
    play,
    loadRouletteConfig,
    loadRouletteHistory,
    rouletteSpin: rouletteSpinAction,
    reset,
  };
});
