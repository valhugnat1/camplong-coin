// ═══════════════════════════════════════════════════════════
// CamplongCoin — Store Pinia : Bourse du Lait (AMM x*y=k)
// ═══════════════════════════════════════════════════════════

import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { useAuthStore } from "./auth";
import { useWalletStore } from "./wallet";
import { milkApi } from "@/api/milk";

export const useMilkStore = defineStore("milk", () => {
  const auth = useAuthStore();
  const wallet = useWalletStore();

  // ─── State ───────────────────────────────────────────
  const pools = ref([]); // tous les pools (hub)
  const pool = ref(null); // pool selectionne (vue trade)
  const chart = ref(null); // serie temporelle du pool selectionne
  const trades = ref([]); // tape du pool selectionne
  const chaosEvents = ref([]); // events chaos du pool selectionne
  const positions = ref([]); // positions du user (toutes pools)
  const myTrades = ref([]); // trades du user (toutes pools)

  const loading = ref(false);
  const error = ref(null);

  // ─── Helpers ─────────────────────────────────────────
  function findPool(symbol) {
    return pools.value.find((p) => p.symbol === symbol);
  }

  const myPosition = computed(() => {
    if (!pool.value) return null;
    return positions.value.find((p) => p.pool_id === pool.value.id) || null;
  });

  // ─── Actions ─────────────────────────────────────────

  async function loadPools() {
    loading.value = true;
    error.value = null;
    try {
      pools.value = await milkApi.pools(auth.userToken);
    } catch (e) {
      error.value = e.message;
    } finally {
      loading.value = false;
    }
  }

  async function loadPool(symbol) {
    loading.value = true;
    error.value = null;
    try {
      pool.value = await milkApi.pool(auth.userToken, symbol);
    } catch (e) {
      error.value = e.message;
      pool.value = null;
    } finally {
      loading.value = false;
    }
  }

  async function loadChart(symbol, minutes = 24 * 60) {
    try {
      chart.value = await milkApi.chart(auth.userToken, symbol, minutes);
    } catch (e) {
      error.value = e.message;
    }
  }

  async function loadTrades(symbol, limit = 20) {
    try {
      trades.value = await milkApi.poolTrades(auth.userToken, symbol, limit);
    } catch (e) {
      error.value = e.message;
    }
  }

  async function loadChaos(symbol, limit = 20) {
    try {
      chaosEvents.value = await milkApi.poolChaos(auth.userToken, symbol, limit);
    } catch (e) {
      error.value = e.message;
    }
  }

  async function loadMyPositions() {
    try {
      positions.value = await milkApi.myPositions(auth.userToken);
    } catch (e) {
      error.value = e.message;
    }
  }

  async function loadMyTrades(limit = 50) {
    try {
      myTrades.value = await milkApi.myTrades(auth.userToken, limit);
    } catch (e) {
      error.value = e.message;
    }
  }

  async function quote(symbol, { side, amount }) {
    return milkApi.quote(auth.userToken, symbol, { side, amount });
  }

  /**
   * Execute un swap. payload = { side, amount, expected_price?, max_slippage_pct? }
   * Apres swap : rafraichit pool, position, historique trades + balance wallet.
   */
  async function swap(symbol, payload) {
    error.value = null;
    try {
      const result = await milkApi.swap(auth.userToken, symbol, payload);
      // Maj pool et positions / trades / wallet
      await Promise.all([
        loadPool(symbol),
        loadMyPositions(),
        loadTrades(symbol, 20),
        loadMyTrades(50),
        wallet.refresh().catch(() => {}),
      ]);
      return result;
    } catch (e) {
      error.value = e.message;
      throw e;
    }
  }

  function reset() {
    pools.value = [];
    pool.value = null;
    chart.value = null;
    trades.value = [];
    chaosEvents.value = [];
    positions.value = [];
    myTrades.value = [];
    error.value = null;
  }

  return {
    // state
    pools,
    pool,
    chart,
    trades,
    chaosEvents,
    positions,
    myTrades,
    loading,
    error,
    // computed
    myPosition,
    // actions
    loadPools,
    loadPool,
    loadChart,
    loadTrades,
    loadChaos,
    loadMyPositions,
    loadMyTrades,
    quote,
    swap,
    findPool,
    reset,
  };
});
