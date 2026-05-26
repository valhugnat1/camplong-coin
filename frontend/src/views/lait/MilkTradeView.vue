<template>
  <AppLayout>
    <main class="page fade-in milk-trade-page">
      <div v-if="milk.error" class="alert error">{{ milk.error }}</div>

      <div v-if="!pool && milk.loading" class="loading">Chargement…</div>

      <template v-if="pool">
        <header class="trade-header">
          <router-link to="/milk" class="back-link">← Tous les pools</router-link>
          <div class="title-row">
            <div>
              <h1 class="page-title">
                <span class="emoji">🥛</span>
                {{ pool.name }}
                <span class="ticker mono">${{ pool.symbol }}</span>
              </h1>
              <div class="meta">
                <span class="status-badge" :class="pool.status">
                  {{ pool.status === 'active' ? 'live' : 'pause' }}
                </span>
                <span class="dim mono">{{ formatNum(pool.bottles) }} btl en réserve</span>
                <span class="dim mono">frais {{ pool.fee_pct }}%</span>
              </div>
            </div>
            <div class="price-block">
              <div class="price-big mono">{{ pool.price.toFixed(2) }}</div>
              <div class="price-unit">CAMP / bouteille</div>
              <div class="change" v-if="pool.change_24h_pct !== null" :class="changeClass">
                {{ pool.change_24h_pct > 0 ? '+' : '' }}{{ pool.change_24h_pct }}% (24h)
              </div>
            </div>
          </div>
        </header>

        <!-- ─── Chart + side panel ───────────────────────── -->
        <section class="layout-grid">
          <article class="card chart-card">
            <div class="chart-toolbar">
              <h3>Cours</h3>
              <div class="range-pills">
                <button
                  v-for="r in ranges"
                  :key="r.m"
                  class="range-pill"
                  :class="{ active: chartMinutes === r.m }"
                  @click="setRange(r.m)"
                >
                  {{ r.label }}
                </button>
              </div>
            </div>
            <div class="chart-wrapper">
              <div v-if="yAxisLabels.length" class="y-axis">
                <span
                  v-for="(y, i) in yAxisLabels"
                  :key="i"
                  class="y-tick mono dim"
                  :style="{ top: y.top }"
                >
                  {{ y.label }}
                </span>
              </div>
              <div class="chart-canvas">
                <svg class="chart-svg" viewBox="0 0 600 200" preserveAspectRatio="none">
                  <defs>
                    <linearGradient id="milkPriceGrad" x1="0" x2="0" y1="0" y2="1">
                      <stop offset="0%" stop-color="#14e08e" stop-opacity="0.4" />
                      <stop offset="100%" stop-color="#14e08e" stop-opacity="0" />
                    </linearGradient>
                  </defs>
                  <path v-if="chartArea" :d="chartArea" fill="url(#milkPriceGrad)" />
                  <path
                    v-if="chartLine"
                    :d="chartLine"
                    fill="none"
                    stroke="#14e08e"
                    stroke-width="2"
                    stroke-linejoin="round"
                  />
                  <!-- Markers : uniquement MES trades (buy/sell). -->
                  <!-- Hit area transparent + cercle visuel, pour faciliter le survol. -->
                  <g
                    v-for="(m, i) in myMarkers"
                    :key="`m${i}`"
                    class="marker-group"
                    @mouseenter="hoveredMarker = m"
                    @mouseleave="hoveredMarker = null"
                  >
                    <circle
                      :cx="m.x"
                      :cy="m.y"
                      r="14"
                      fill="transparent"
                      class="marker-hit"
                    />
                    <circle
                      :cx="m.x"
                      :cy="m.y"
                      r="6"
                      :fill="m.side === 'buy' ? '#14e08e' : '#ff7a00'"
                      stroke="#0d0d14"
                      stroke-width="2"
                      pointer-events="none"
                    />
                  </g>
                  <circle
                    v-if="lastPoint"
                    :cx="lastPoint.x"
                    :cy="lastPoint.y"
                    r="3"
                    fill="#14e08e"
                    opacity="0.6"
                    pointer-events="none"
                  />
                  <circle
                    v-if="lastPoint"
                    :cx="lastPoint.x"
                    :cy="lastPoint.y"
                    r="7"
                    fill="#14e08e"
                    opacity="0.25"
                    pointer-events="none"
                  >
                    <animate attributeName="r" values="4;12;4" dur="2s" repeatCount="indefinite" />
                    <animate attributeName="opacity" values="0.4;0;0.4" dur="2s" repeatCount="indefinite" />
                  </circle>
                </svg>
                <!-- HTML tooltip (positionne sur le marker hover) -->
                <div
                  v-if="hoveredMarker"
                  class="chart-tooltip"
                  :style="tooltipStyle"
                >
                  <div class="tt-head">
                    <span
                      class="tt-side"
                      :class="hoveredMarker.side"
                    >
                      {{ hoveredMarker.side === 'buy' ? '📈 Achat' : '📉 Vente' }}
                    </span>
                    <span class="tt-ts mono dim">{{ formatShort(hoveredMarker.ts) }}</span>
                  </div>
                  <div class="tt-body mono">
                    <template v-if="hoveredMarker.side === 'buy'">
                      {{ formatNum(hoveredMarker.amount_camp_in) }} CAMP
                      → {{ formatBottles(hoveredMarker.amount_milk_out) }} btl
                    </template>
                    <template v-else>
                      {{ formatBottles(hoveredMarker.amount_milk_in) }} btl
                      → {{ formatNum(hoveredMarker.amount_camp_out) }} CAMP
                    </template>
                  </div>
                  <div class="tt-foot mono dim">
                    @ {{ Number(hoveredMarker.price).toFixed(2) }} CAMP/btl
                  </div>
                </div>
              </div>
            </div>
            <div v-if="timeAxisLabels.length" class="time-axis">
              <span
                v-for="(t, i) in timeAxisLabels"
                :key="i"
                class="time-tick mono dim"
                :style="{ left: t.left }"
              >
                {{ t.label }}
              </span>
            </div>
            <p v-if="myMarkers.length" class="chart-legend dim small">
              <span class="legend-dot buy"></span> mes achats
              <span class="legend-dot sell"></span> mes ventes
              <span class="dim">— survole pour voir le détail</span>
            </p>
            <p
              v-else-if="myUsername && chartPoints.length"
              class="chart-legend dim small"
            >
              <span class="dim">Aucun trade sur cette fenêtre. Change la plage temporelle pour les retrouver.</span>
            </p>
            <p v-if="!chartPoints.length" class="chart-empty dim">
              Pas encore d'historique de prix.
            </p>
          </article>

          <aside class="card swap-card">
            <div class="tabs-mini">
              <button
                class="tab-mini"
                :class="{ active: side === 'buy' }"
                @click="setSide('buy')"
              >
                📈 Acheter
              </button>
              <button
                class="tab-mini"
                :class="{ active: side === 'sell' }"
                @click="setSide('sell')"
              >
                📉 Vendre
              </button>
            </div>

            <div v-if="pool.status !== 'active'" class="alert info">
              Pool en pause. Les swaps sont bloqués.
            </div>

            <template v-else>
              <label class="field">
                <span class="field-head">
                  <span>
                    {{ side === 'buy' ? 'Tu mises (CAMP)' : 'Tu vends (bouteilles)' }}
                  </span>
                  <button
                    v-if="side === 'sell' && myPosition && myPosition.balance_milk > 0"
                    type="button"
                    class="btn-max"
                    @click="setSellMax"
                    title="Vendre tout"
                  >
                    Max
                  </button>
                </span>
                <input
                  type="number"
                  :min="0"
                  :step="side === 'buy' ? 1 : 0.001"
                  v-model.number="amountInput"
                  :placeholder="side === 'buy' ? 'ex: 100' : 'ex: 5'"
                />
              </label>

              <div class="quote-box" v-if="quote && !quoteError">
                <div class="quote-row">
                  <span class="qk">Tu reçois</span>
                  <span class="qv mono">
                    <template v-if="side === 'buy'">
                      {{ formatBottles(quote.amount_out) }} btl
                    </template>
                    <template v-else>
                      {{ formatNum(quote.amount_out) }} CAMP
                    </template>
                  </span>
                </div>
                <div class="quote-row">
                  <span class="qk">Frais</span>
                  <span class="qv mono dim">
                    {{ formatNum(quote.fee) }} CAMP
                    <span class="dim">({{ pool.fee_pct }}%)</span>
                  </span>
                </div>
                <div class="quote-row">
                  <span class="qk">Prix avant</span>
                  <span class="qv mono">{{ quote.price_before.toFixed(2) }}</span>
                </div>
                <div class="quote-row">
                  <span class="qk">Prix après</span>
                  <span class="qv mono">{{ quote.price_after.toFixed(2) }}</span>
                </div>
                <div class="quote-row impact">
                  <span class="qk">Impact prix</span>
                  <span class="qv mono" :class="impactClass">
                    {{ priceImpactPct > 0 ? '+' : '' }}{{ priceImpactPct.toFixed(2) }}%
                  </span>
                </div>
              </div>

              <div v-else-if="quoteError" class="alert error small">
                {{ quoteError }}
              </div>

              <details class="advanced">
                <summary>
                  <span>⚙️ Options avancées</span>
                  <span class="adv-hint mono dim">slippage : {{ slippagePct }}%</span>
                </summary>
                <div class="advanced-body">
                  <p class="adv-explain">
                    <b>Tolérance slippage</b> : protection si le prix bouge entre
                    ton clic et l'exécution (autre trader ou event chaos pile
                    avant ta tx). Au-dessus de cet écart en %, le swap est
                    refusé proprement, sans tx on-chain.
                    <br />
                    <span class="dim">
                      Si pas sûr : laisse <b>1%</b>. Plus haut = plus permissif
                      (tu prends ce qu'il y a). Plus bas = plus strict (mais le
                      swap peut échouer en marché agité).
                    </span>
                  </p>
                  <label class="field slippage-field">
                    <span>
                      Tolérance slippage :
                      <b class="mono">{{ slippagePct }}%</b>
                    </span>
                    <input
                      type="range"
                      min="0.1"
                      max="10"
                      step="0.1"
                      v-model.number="slippagePct"
                    />
                  </label>
                </div>
              </details>

              <button
                class="btn-primary btn-block"
                :disabled="!canSwap || swapping"
                @click="doSwap"
              >
                {{ swapping ? '…' : swapLabel }}
              </button>

              <p v-if="swapMsg" class="swap-msg" :class="{ success: !swapError, error: swapError }">
                {{ swapMsg }}
              </p>
            </template>

            <!-- Position user -->
            <div class="position" v-if="myPosition">
              <h4>Ma position</h4>
              <div class="pos-row">
                <span>Stock</span>
                <span class="mono">{{ formatBottles(myPosition.balance_milk) }} btl</span>
              </div>
              <div class="pos-row">
                <span>
                  Valeur réalisable
                  <small class="dim" v-if="sellAllImpactPct < -0.1">
                    (impact {{ sellAllImpactPct.toFixed(2) }}%)
                  </small>
                </span>
                <span class="mono">{{ formatNum(realisableValue) }} CAMP</span>
              </div>
              <div
                class="pos-row"
                :class="performancePct >= 0 ? 'positive' : 'negative'"
              >
                <span>Performance</span>
                <span class="mono">
                  {{ performancePct >= 0 ? '+' : '' }}{{ performancePct.toFixed(2) }}%
                </span>
              </div>
              <div class="pos-row pnl" :class="realisablePnl >= 0 ? 'positive' : 'negative'">
                <span>P&amp;L</span>
                <span class="mono">
                  {{ realisablePnl >= 0 ? '+' : '' }}{{ formatNum(realisablePnl) }} CAMP
                </span>
              </div>
              <details v-if="myPosition.current_value_camp !== realisableValue" class="pos-details">
                <summary class="dim small">ℹ️ Pourquoi pas la valeur au prix affiché ?</summary>
                <p class="dim small">
                  Le prix affiché ({{ formatNum(myPosition.current_price) }} CAMP/btl)
                  est le prix d'un trade infinitésimal. Vendre toute ta position
                  ({{ formatBottles(myPosition.balance_milk) }} btl) ferait
                  chuter le prix de {{ Math.abs(sellAllImpactPct).toFixed(2) }}%,
                  donc tu toucherais réellement
                  <b class="mono">{{ formatNum(realisableValue) }} CAMP</b>
                  (au lieu de
                  <span class="mono">{{ formatNum(myPosition.current_value_camp) }} CAMP</span>
                  en théorie spot).
                </p>
              </details>
            </div>
          </aside>
        </section>

        <!-- ─── Tape + Chaos ─────────────────────────────── -->
        <section class="layout-grid two-col">
          <article class="card list-card">
            <h3>📜 Derniers trades</h3>
            <ul class="trade-list" v-if="milk.trades.length">
              <li v-for="t in milk.trades" :key="t.id" :class="t.side">
                <span class="t-side">{{ t.side === 'buy' ? '📈' : '📉' }}</span>
                <span class="t-user mono">{{ t.username }}</span>
                <span class="t-amount mono">
                  <template v-if="t.side === 'buy'">
                    {{ formatNum(t.amount_camp_in) }} CAMP → {{ formatBottles(t.amount_milk_out) }} btl
                  </template>
                  <template v-else>
                    {{ formatBottles(t.amount_milk_in) }} btl → {{ formatNum(t.amount_camp_out) }} CAMP
                  </template>
                </span>
                <span class="t-price mono dim">@{{ t.price_after.toFixed(2) }}</span>
              </li>
            </ul>
            <p v-else class="dim small">Aucun trade pour l'instant.</p>
          </article>

          <article class="card list-card chaos-card">
            <h3>🌪️ Événements chaos</h3>
            <ul class="chaos-list" v-if="milk.chaosEvents.length">
              <li v-for="c in milk.chaosEvents" :key="c.id" :class="c.kind">
                <div class="chaos-head">
                  <span class="chaos-kind">{{ kindLabel(c.kind) }}</span>
                  <span class="dim mono small">{{ formatShort(c.ts) }}</span>
                </div>
                <div class="chaos-narrative">{{ c.narrative }}</div>
                <div class="chaos-delta mono dim small">
                  prix : {{ c.price_before.toFixed(2) }} → {{ c.price_after.toFixed(2) }}
                  ({{ pctChange(c.price_before, c.price_after) }}%)
                </div>
              </li>
            </ul>
            <p v-else class="dim small">
              Tout est calme. Pour l'instant.
            </p>
          </article>
        </section>
      </template>
    </main>
  </AppLayout>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppLayout from '@/components/layout/AppLayout.vue'
import { useMilkStore } from '@/stores/milk'
import { useWalletStore } from '@/stores/wallet'
import { formatNum, MILK } from '@/config'

const route = useRoute()
const router = useRouter()
const milk = useMilkStore()
const wallet = useWalletStore()
const myUsername = computed(() => wallet.me?.username || '')

const symbol = computed(() => String(route.params.symbol || ''))
const pool = computed(() => milk.pool)
const myPosition = computed(() => milk.myPosition)

// Performance % = pnl_realisable / cost_basis * 100.
// On utilise la valeur REALISABLE (sell_quote sur tout le stock), pas le
// mark-to-market spot, pour refleter ce qu'on toucherait reellement en
// debouclant la position (price impact compris).
const performancePct = computed(() => {
  const p = myPosition.value
  if (!p || !p.balance_milk) return 0
  const cost = Number(p.cost_basis_camp ?? 0)
  const pnl = Number(p.realisable_pnl_camp ?? p.pnl_camp ?? 0)
  if (cost <= 0) return 0
  return (pnl / cost) * 100
})

const realisableValue = computed(() => {
  const p = myPosition.value
  if (!p) return 0
  return Number(p.realisable_value_camp ?? p.current_value_camp ?? 0)
})

const realisablePnl = computed(() => {
  const p = myPosition.value
  if (!p) return 0
  return Number(p.realisable_pnl_camp ?? p.pnl_camp ?? 0)
})

const sellAllImpactPct = computed(() => {
  const p = myPosition.value
  if (!p) return 0
  return Number(p.price_impact_sell_all_pct ?? 0)
})

// ─── Side & input ────────────────────────────────────
const side = ref('buy')
const amountInput = ref(null)
const slippagePct = ref(MILK.defaultSlippagePct)

const quote = ref(null)
const quoteError = ref('')
const swapping = ref(false)
const swapMsg = ref('')
const swapError = ref(false)

function setSide(s) {
  side.value = s
  amountInput.value = null
  quote.value = null
  quoteError.value = ''
}

// amount passed to API : raw CAMP for buy, milli-bottles for sell
const apiAmount = computed(() => {
  const v = Number(amountInput.value)
  if (!v || v <= 0) return 0
  if (side.value === 'buy') return Math.floor(v)
  // sell : input en bouteilles -> milli-bouteilles. Math.round (pas floor)
  // pour gerer la dust flottante (0.999 * 1000 = 998.999... en IEEE754).
  // Si l'utilisateur tape 0.999 et a balance_milk=999, on doit envoyer 999.
  let milli = Math.round(v * MILK.milkUnit)
  // Clamp a la balance courante pour permettre de tout vendre meme si
  // l'input depasse legerement (ex: typo, ou Max button qui a roundtripped).
  const bal = myPosition.value?.balance_milk ?? 0
  if (milli > bal) milli = bal
  return milli
})

function setSellMax() {
  if (!myPosition.value || myPosition.value.balance_milk <= 0) return
  // Affichage en bouteilles flottantes. Le clamp dans apiAmount garantit
  // qu'on enverra exactement balance_milk au backend, peu importe le round.
  amountInput.value = myPosition.value.balance_milk / MILK.milkUnit
}

// Debounced quote fetch. Subtilite : on annule TOUJOURS le timer
// en cours en debut de watcher (meme en early-return), sinon un timer
// programme avant un changement (ex: post-swap, amountInput reset a null)
// peut fire 220ms plus tard et envoyer amount=0 -> 422.
// On capture aussi les valeurs au moment du fire pour eviter qu'un
// changement entre temps fasse partir une requete avec des valeurs incoherentes.
let quoteTimer = null
watch([apiAmount, side, () => pool.value?.symbol, () => pool.value?.reserve_camp], async () => {
  quoteError.value = ''
  if (quoteTimer) {
    clearTimeout(quoteTimer)
    quoteTimer = null
  }
  if (!pool.value || apiAmount.value <= 0) {
    quote.value = null
    return
  }
  if (pool.value.status !== 'active') {
    quote.value = null
    return
  }
  const capturedAmount = apiAmount.value
  const capturedSide = side.value
  const capturedSymbol = pool.value.symbol
  quoteTimer = setTimeout(async () => {
    quoteTimer = null
    if (capturedAmount <= 0) return
    try {
      const q = await milk.quote(capturedSymbol, {
        side: capturedSide,
        amount: capturedAmount,
      })
      // Ne pas ecraser un quote si l'input courant a depuis change
      // pour 0 / vide (le user a clear apres le scheduling du timer)
      if (apiAmount.value > 0) {
        quote.value = q
      }
    } catch (e) {
      quote.value = null
      quoteError.value = e.message
    }
  }, 220)
})

const priceImpactPct = computed(() => {
  if (!quote.value || !quote.value.price_before) return 0
  return ((quote.value.price_after - quote.value.price_before) / quote.value.price_before) * 100
})
const impactClass = computed(() => {
  const p = priceImpactPct.value
  if (p > 3) return 'down'
  if (p < -3) return 'up'
  return 'flat'
})

const canSwap = computed(() => {
  if (!pool.value || pool.value.status !== 'active') return false
  if (apiAmount.value <= 0) return false
  if (!quote.value || quote.value.amount_out <= 0) return false
  return true
})

const swapLabel = computed(() => {
  if (!quote.value) {
    return side.value === 'buy' ? 'Acheter' : 'Vendre'
  }
  if (side.value === 'buy') {
    return `Acheter ${formatBottles(quote.value.amount_out)} btl`
  }
  return `Vendre pour ${formatNum(quote.value.amount_out)} CAMP`
})

async function doSwap() {
  if (!canSwap.value) return
  swapping.value = true
  swapError.value = false
  swapMsg.value = ''
  try {
    const expected = quote.value?.price_after ?? null
    const res = await milk.swap(pool.value.symbol, {
      side: side.value,
      amount: apiAmount.value,
      expected_price: expected,
      max_slippage_pct: slippagePct.value,
    })
    swapMsg.value = side.value === 'buy'
      ? `Acheté ${formatBottles(res.amount_milk_out)} btl pour ${formatNum(res.amount_camp_in)} CAMP ✓`
      : `Vendu ${formatBottles(res.amount_milk_in)} btl contre ${formatNum(res.amount_camp_out)} CAMP ✓`
    amountInput.value = null
    quote.value = null
  } catch (e) {
    swapError.value = true
    swapMsg.value = e.message
  } finally {
    swapping.value = false
    setTimeout(() => { swapMsg.value = '' }, 6000)
  }
}

// ─── Chart ───────────────────────────────────────────
// Plages en minutes (le backend prend `minutes` en query param).
const ranges = [
  { m: 15,           label: '15 min' },
  { m: 60,           label: '1h' },
  { m: 60 * 24,      label: '24h' },
  { m: 60 * 24 * 7,  label: '7j' },
]
const chartMinutes = ref(60 * 24)
async function setRange(m) {
  chartMinutes.value = m
  if (pool.value) await milk.loadChart(pool.value.symbol, m)
}

const chartPoints = computed(() => milk.chart?.points || [])

const chartDims = { W: 600, H: 200, padTop: 12, padBottom: 12 }

// Range de prix sur la fenetre (utilise pour scaler le chart ET pour
// l'axe Y). Extrait dans son propre computed pour pouvoir l'afficher.
const priceRange = computed(() => {
  const pts = chartPoints.value
  if (!pts.length) return null
  const prices = pts.map((p) => p.price).filter((v) => v > 0)
  if (!prices.length) return null
  const min = Math.min(...prices)
  const max = Math.max(...prices)
  const span = max - min || max * 0.02 || 1
  return { min, max, span }
})

const scaledPoints = computed(() => {
  const pts = chartPoints.value
  const range = priceRange.value
  if (!pts.length || !range) return []
  const { W, H, padTop, padBottom } = chartDims
  return pts.map((p, i) => {
    const x = pts.length === 1 ? W : (i / (pts.length - 1)) * W
    const yNorm = (p.price - range.min) / range.span
    const y = padTop + (1 - yNorm) * (H - padTop - padBottom)
    return { ...p, x, y }
  })
})

const chartLine = computed(() => {
  const pts = scaledPoints.value
  if (pts.length < 2) return null
  return 'M ' + pts.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' L ')
})
const chartArea = computed(() => {
  const line = chartLine.value
  if (!line) return null
  const { W, H } = chartDims
  return `${line} L ${W},${H} L 0,${H} Z`
})
const lastPoint = computed(() => {
  const pts = scaledPoints.value
  return pts.length ? pts[pts.length - 1] : null
})

// Markers visibles : uniquement les trades du user courant.
const myMarkers = computed(() => {
  const u = myUsername.value
  if (!u) return []
  return scaledPoints.value.filter(
    (p) => p.source === 'trade' && p.username === u,
  )
})

// Tooltip hover : marker survole + position en % de la chart-canvas.
const hoveredMarker = ref(null)
const tooltipStyle = computed(() => {
  if (!hoveredMarker.value) return {}
  const { W, H } = chartDims
  // % par rapport au container .chart-canvas (= taille du SVG)
  const leftPct = (hoveredMarker.value.x / W) * 100
  const topPct = (hoveredMarker.value.y / H) * 100
  return {
    left: `${leftPct}%`,
    top: `${topPct}%`,
  }
})

// Tick labels en bas du chart : 3 reperes temporels (debut, milieu, fin)
const timeAxisLabels = computed(() => {
  const pts = scaledPoints.value
  if (pts.length < 2) return []
  const first = pts[0]
  const last = pts[pts.length - 1]
  const mid = pts[Math.floor(pts.length / 2)]
  const fmt = (iso) => formatShort(iso)
  return [
    { label: fmt(first.ts), left: '0%' },
    { label: fmt(mid.ts), left: '50%' },
    { label: fmt(last.ts), left: '100%' },
  ]
})

// Axe Y : 3 ticks de prix (max, mid, min) - en CSS absolu sur l'overlay.
const yAxisLabels = computed(() => {
  const r = priceRange.value
  if (!r) return []
  const { H, padTop, padBottom } = chartDims
  // y -> top% : padTop -> top du chart, H-padBottom -> bottom du chart
  const yToPct = (y) => ((y / H) * 100).toFixed(1) + '%'
  const fmt = (v) => v.toFixed(2)
  return [
    { label: fmt(r.max), top: yToPct(padTop) },
    { label: fmt((r.max + r.min) / 2), top: yToPct(H / 2) },
    { label: fmt(r.min), top: yToPct(H - padBottom) },
  ]
})

const changeClass = computed(() => {
  const p = pool.value?.change_24h_pct
  if (p == null) return 'flat'
  if (p > 0) return 'up'
  if (p < 0) return 'down'
  return 'flat'
})

// ─── Helpers ─────────────────────────────────────────
function formatBottles(milliBottles) {
  // 1 bouteille = MILK.milkUnit milli-bouteilles.
  // On TRONQUE (floor) au lieu d'arrondir : 999 milli doit s'afficher "0.99",
  // pas "1.00" -- sinon le user croit pouvoir vendre 1 btl alors qu'il n'en
  // a que 0.999 et le backend refuse.
  const milli = Math.max(0, Math.floor(milliBottles || 0))
  if (milli % MILK.milkUnit === 0) return formatNum(milli / MILK.milkUnit)
  // Floor a 2 decimales (toFixed arrondit, ce qu'on veut eviter)
  return (Math.floor(milli / 10) / 100).toFixed(2)
}
function pctChange(a, b) {
  if (!a || a === 0) return '—'
  return ((b - a) / a * 100).toFixed(2)
}
function kindLabel(kind) {
  return ({
    famine: '🌾 Famine',
    spoil: '☣️ Avariation',
    overstock: '📦 Surproduction',
    import: '🚛 Import',
  })[kind] || kind
}
function formatShort(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(d.getDate())}/${pad(d.getMonth() + 1)} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// ─── Lifecycle ───────────────────────────────────────
let refreshTimer = null

async function refreshAll() {
  const s = symbol.value
  if (!s) return
  await Promise.all([
    milk.loadPool(s),
    milk.loadChart(s, chartMinutes.value),
    milk.loadTrades(s, 12),
    milk.loadChaos(s, 8),
    milk.loadMyPositions(),
    // wallet.me.username pilote le filtre "mes markers" sur le chart.
    // Si on arrive en deep-link sans passer par /wallet, le store est vide,
    // donc on force un refresh ici.
    wallet.refresh().catch(() => {}),
  ])
}

onMounted(async () => {
  await refreshAll()
  // Refresh leger toutes les 30s pour suivre les mouvements (chaos, autres users)
  refreshTimer = setInterval(refreshAll, 30000)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})

// Si l'utilisateur navigue entre deux symbols
watch(symbol, async (newSym, old) => {
  if (newSym && newSym !== old) {
    quote.value = null
    amountInput.value = null
    await refreshAll()
  }
})
</script>

<style scoped>
.milk-trade-page { padding-bottom: 3em; }

.back-link {
  color: var(--text-2);
  font-size: 0.88em;
  text-decoration: none;
  display: inline-block;
  margin-bottom: 0.7em;
}
.back-link:hover { color: var(--camp); }

.trade-header { margin-bottom: 1.3em; }
.title-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1em;
  flex-wrap: wrap;
}
.page-title {
  font-size: 1.7em;
  display: flex;
  align-items: center;
  gap: 0.4em;
  letter-spacing: -0.02em;
  margin: 0;
}
.page-title .emoji { font-size: 1em; }
.page-title .ticker {
  color: var(--text-3);
  font-size: 0.55em;
  letter-spacing: 0.05em;
  font-weight: 500;
}

.meta {
  display: flex;
  gap: 0.7em;
  align-items: center;
  margin-top: 0.3em;
  font-size: 0.85em;
}
.status-badge {
  font-size: 0.7em;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  padding: 0.2em 0.55em;
  border-radius: 999px;
}
.status-badge.active { background: rgba(20, 224, 142, 0.15); color: #14e08e; }
.status-badge.paused { background: var(--bg-3); color: var(--text-3); }

.price-block { text-align: right; }
.price-big {
  font-size: 2em;
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1;
}
.price-unit {
  font-size: 0.78em;
  color: var(--text-2);
  margin-top: 0.2em;
}
.price-block .change {
  font-size: 0.9em;
  margin-top: 0.4em;
  font-weight: 600;
}
.change.up { color: #14e08e; }
.change.down { color: var(--red); }
.change.flat { color: var(--text-3); }

/* ─── Layout grid ───────────────────────────── */
.layout-grid {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 1em;
  margin-bottom: 1em;
}
.layout-grid.two-col {
  grid-template-columns: 1fr 1fr;
}
@media (max-width: 880px) {
  .layout-grid,
  .layout-grid.two-col {
    grid-template-columns: 1fr;
  }
}

.card {
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.2em;
}

.chart-card { display: flex; flex-direction: column; gap: 0.8em; }
.chart-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.5em;
}
.chart-toolbar h3 { font-size: 1em; margin: 0; }

.range-pills { display: flex; gap: 0.25em; }
.range-pill {
  padding: 0.3em 0.8em;
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: 999px;
  font-size: 0.78em;
  color: var(--text-2);
  cursor: pointer;
}
.range-pill.active {
  background: var(--bg-3);
  color: var(--text-0);
  border-color: var(--border-strong);
}

/* Chart : axe Y a gauche, canvas (SVG + tooltip) a droite */
.chart-wrapper {
  display: flex;
  align-items: stretch;
  gap: 6px;
}
.y-axis {
  position: relative;
  width: 40px;
  height: 220px;
  flex-shrink: 0;
  pointer-events: none;
}
.y-tick {
  position: absolute;
  right: 0;
  font-size: 0.7em;
  transform: translateY(-50%);
  white-space: nowrap;
}
.chart-canvas {
  position: relative;
  flex: 1;
  height: 220px;
  min-width: 0;
}
.chart-svg {
  width: 100%;
  height: 220px;
  display: block;
}

/* Markers : hit area transparent r=14 pour avoir une zone de hover
   genereuse meme si visuellement le point fait 6px. */
.marker-group { cursor: pointer; }
.marker-hit { cursor: pointer; }

/* Tooltip flottante, positionnee sur .chart-canvas par left/top en % */
.chart-tooltip {
  position: absolute;
  transform: translate(-50%, calc(-100% - 12px));
  background: var(--bg-3, #1a1a24);
  border: 1px solid var(--border-strong, #2a2a3a);
  border-radius: 6px;
  padding: 0.55em 0.75em;
  font-size: 0.8em;
  pointer-events: none;
  z-index: 5;
  white-space: nowrap;
  box-shadow: 0 8px 24px -8px rgba(0, 0, 0, 0.7);
  min-width: 160px;
}
.chart-tooltip::after {
  content: '';
  position: absolute;
  bottom: -6px;
  left: 50%;
  transform: translateX(-50%) rotate(45deg);
  width: 10px;
  height: 10px;
  background: var(--bg-3, #1a1a24);
  border-right: 1px solid var(--border-strong, #2a2a3a);
  border-bottom: 1px solid var(--border-strong, #2a2a3a);
}
.tt-head {
  display: flex;
  justify-content: space-between;
  gap: 0.6em;
  margin-bottom: 0.25em;
}
.tt-side {
  font-weight: 700;
  font-size: 0.88em;
}
.tt-side.buy { color: #14e08e; }
.tt-side.sell { color: #ff7a00; }
.tt-ts { font-size: 0.78em; }
.tt-body { font-size: 0.9em; color: var(--text-0); }
.tt-foot { font-size: 0.78em; margin-top: 0.15em; }
.chart-empty {
  text-align: center;
  padding: 1em;
  font-size: 0.85em;
}
.time-axis {
  position: relative;
  height: 1.3em;
  margin-top: 0.2em;
  margin-left: 46px;  /* aligne avec la chart-canvas (y-axis 40 + gap 6) */
}
.time-tick {
  position: absolute;
  top: 0;
  font-size: 0.72em;
  transform: translateX(-50%);
  white-space: nowrap;
}
.time-tick:first-child { transform: translateX(0); }
.time-tick:last-child { transform: translateX(-100%); }

.chart-legend {
  margin: 0.3em 0 0 0;
  font-size: 0.78em;
  display: flex;
  align-items: center;
  gap: 0.5em;
  flex-wrap: wrap;
}
.legend-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 0.2em;
}
.legend-dot.buy { background: #14e08e; }
.legend-dot.sell { background: #ff7a00; }

/* ─── Swap card ─────────────────────────────── */
.swap-card { display: flex; flex-direction: column; gap: 0.9em; }
.tabs-mini {
  display: flex;
  background: var(--bg-2);
  padding: 0.25em;
  border-radius: var(--radius-sm);
  gap: 0.2em;
}
.tab-mini {
  flex: 1;
  padding: 0.55em 0.6em;
  background: transparent;
  border: none;
  color: var(--text-2);
  font-weight: 600;
  cursor: pointer;
  border-radius: 6px;
  font-size: 0.92em;
}
.tab-mini.active {
  background: var(--bg-3);
  color: var(--text-0);
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.3em;
  font-size: 0.85em;
  color: var(--text-2);
}
.field-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.btn-max {
  background: var(--bg-3);
  border: 1px solid var(--border);
  color: var(--camp);
  font-size: 0.72em;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 0.15em 0.55em;
  border-radius: 4px;
  cursor: pointer;
}
.btn-max:hover {
  border-color: var(--camp);
}
.field input[type='number'] {
  padding: 0.6em 0.7em;
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-0);
  font-family: 'JetBrains Mono', monospace;
  font-size: 1em;
}
.slippage-field input[type='range'] {
  width: 100%;
}

/* Options avancees (slippage) cachees dans un details/summary */
.advanced {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}
.advanced > summary {
  list-style: none;
  cursor: pointer;
  padding: 0.55em 0.8em;
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 0.82em;
  color: var(--text-2);
  user-select: none;
}
.advanced > summary::-webkit-details-marker { display: none; }
.advanced > summary:hover { color: var(--text-0); }
.advanced[open] > summary {
  border-bottom: 1px dashed var(--border);
}
.advanced .adv-hint {
  font-size: 0.88em;
}
.advanced-body {
  padding: 0.8em 0.8em 0.9em;
}
.adv-explain {
  font-size: 0.8em;
  line-height: 1.55;
  color: var(--text-2);
  margin: 0 0 0.8em 0;
}
.adv-explain .dim { font-size: 0.95em; }

.quote-box {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0.7em 0.9em;
  display: flex;
  flex-direction: column;
  gap: 0.3em;
}
.quote-row {
  display: flex;
  justify-content: space-between;
  font-size: 0.85em;
}
.quote-row .qk { color: var(--text-2); }
.quote-row .qv { color: var(--text-0); font-weight: 500; }
.quote-row.impact { padding-top: 0.4em; border-top: 1px dashed var(--border); margin-top: 0.2em; }
.quote-row .down { color: var(--red); }
.quote-row .up { color: #14e08e; }
.quote-row .flat { color: var(--text-3); }

.btn-block { width: 100%; }

.swap-msg {
  font-size: 0.85em;
  text-align: center;
  margin: 0;
}
.swap-msg.success { color: #14e08e; }
.swap-msg.error { color: var(--red); }

.alert.small { font-size: 0.85em; padding: 0.6em 0.8em; }
.alert.info {
  background: var(--bg-2);
  color: var(--text-2);
  border: 1px solid var(--border);
}

.position {
  margin-top: 0.6em;
  padding-top: 0.9em;
  border-top: 1px dashed var(--border);
}
.position h4 {
  font-size: 0.88em;
  margin-bottom: 0.5em;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-2);
}
.pos-row {
  display: flex;
  justify-content: space-between;
  padding: 0.25em 0;
  font-size: 0.88em;
}
.pos-row.pnl { font-weight: 700; padding-top: 0.5em; border-top: 1px solid var(--border); margin-top: 0.2em; }
.pos-row.positive .mono { color: #14e08e; }
.pos-row.negative .mono { color: var(--red); }

/* ─── Tape & chaos ──────────────────────────── */
.list-card h3 { font-size: 1em; margin: 0 0 0.7em 0; }
.trade-list,
.chaos-list {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: 320px;
  overflow-y: auto;
}
.trade-list li {
  display: grid;
  grid-template-columns: 22px 80px 1fr auto;
  gap: 0.5em;
  align-items: center;
  padding: 0.5em 0.2em;
  border-bottom: 1px dashed var(--border);
  font-size: 0.85em;
}
.trade-list li:last-child { border-bottom: none; }
.trade-list li.buy .t-side { color: #14e08e; }
.trade-list li.sell .t-side { color: var(--red); }
.trade-list .t-user { color: var(--text-1); }
.trade-list .t-amount { color: var(--text-0); }
.trade-list .t-price { font-size: 0.85em; }

.chaos-list li {
  padding: 0.6em 0.2em;
  border-bottom: 1px dashed var(--border);
}
.chaos-list li:last-child { border-bottom: none; }
.chaos-list .chaos-head {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.15em;
}
.chaos-list .chaos-kind {
  font-size: 0.8em;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.chaos-list li.famine .chaos-kind,
.chaos-list li.spoil .chaos-kind { color: #ff4566; }
.chaos-list li.overstock .chaos-kind,
.chaos-list li.import .chaos-kind { color: #14e08e; }
.chaos-list .chaos-narrative {
  font-size: 0.88em;
  font-style: italic;
  color: var(--text-1);
}
.chaos-list .chaos-delta { margin-top: 0.15em; }

.dim { color: var(--text-3); }
.small { font-size: 0.8em; }

@media (max-width: 640px) {
  .price-block { text-align: left; }
  .title-row { flex-direction: column; }
}
</style>
