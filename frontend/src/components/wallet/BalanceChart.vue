<template>
  <div class="chart-card">
    <div class="chart-toolbar">
      <div>
        <h3 class="chart-title">Evolution du solde</h3>
        <div class="chart-sub" v-if="!loading && points.length">
          <span class="mono" :class="changeClass">
            {{ deltaSign }}{{ formatNum(Math.abs(delta)) }} CAMP
          </span>
          <span class="dim">·</span>
          <span class="mono" :class="changeClass">
            {{ deltaPct }}
          </span>
        </div>
      </div>
      <div class="range-pills">
        <button
          v-for="r in ranges"
          :key="r.key"
          class="range-pill"
          :class="{ active: window === r.key }"
          @click="setRange(r.key)"
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
            <linearGradient id="balanceGrad" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stop-color="#ff7a00" stop-opacity="0.35" />
              <stop offset="100%" stop-color="#ff7a00" stop-opacity="0" />
            </linearGradient>
          </defs>
          <path v-if="chartArea" :d="chartArea" fill="url(#balanceGrad)" />
          <path
            v-if="chartLine"
            :d="chartLine"
            fill="none"
            stroke="#ff7a00"
            stroke-width="2"
            stroke-linejoin="round"
          />
        </svg>
        <!-- Pulse dot en HTML : sinon le <circle> SVG est deforme en ovale
             par preserveAspectRatio="none" sur les ecrans etroits. -->
        <div
          v-if="lastPoint"
          class="last-dot"
          :style="{
            left: `${(lastPoint.x / 600) * 100}%`,
            top:  `${(lastPoint.y / 200) * 100}%`,
          }"
        ></div>
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
    <p v-if="!loading && !points.length" class="chart-empty dim">
      Pas encore de donnees sur cette fenetre.
    </p>
    <p v-else-if="loading && !points.length" class="chart-empty dim">
      Chargement…
    </p>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { apiCall } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { formatNum } from '@/config'

const props = defineProps({
  // Le solde live de la BalanceCard. Quand il change, on rafraichit le chart
  // pour que la derniere valeur reste synchro avec le solde affiche au-dessus.
  liveBalance: { type: Number, default: null },
})

const auth = useAuthStore()

const ranges = [
  { key: '15m', label: '15m' },
  { key: '1h',  label: '1h' },
  { key: '6h',  label: '6h' },
  { key: '1d',  label: '1j' },
  { key: '7d',  label: '7j' },
]

const window = ref('1d')
const points = ref([])
const loading = ref(false)

async function load() {
  if (!auth.userToken) return
  loading.value = true
  try {
    const data = await apiCall(`/balance-history?window=${window.value}`, {
      token: auth.userToken,
    })
    points.value = data.points || []
  } catch (_) {
    points.value = []
  } finally {
    loading.value = false
  }
}

function setRange(k) {
  if (window.value === k) return
  window.value = k
  load()
}

let timer = null
onMounted(() => {
  load()
  timer = setInterval(load, 30_000)
})
onUnmounted(() => { if (timer) clearInterval(timer) })

// Re-fetch quand le solde live change (transfer, achat...), pour eviter
// que le dernier point reste obsolete.
watch(() => props.liveBalance, () => { load() })

// ─── Chart geometry ─────────────────────────────────────
const dims = { W: 600, H: 200, padTop: 12, padBottom: 12 }

const range = computed(() => {
  if (!points.value.length) return null
  const vals = points.value.map((p) => p.balance)
  const min = Math.min(...vals)
  const max = Math.max(...vals)
  const span = max - min || Math.max(max * 0.02, 1)
  return { min, max, span }
})

const scaled = computed(() => {
  const pts = points.value
  const r = range.value
  if (!pts.length || !r) return []
  const { W, H, padTop, padBottom } = dims
  return pts.map((p, i) => {
    const x = pts.length === 1 ? W : (i / (pts.length - 1)) * W
    const yNorm = (p.balance - r.min) / r.span
    const y = padTop + (1 - yNorm) * (H - padTop - padBottom)
    return { ...p, x, y }
  })
})

const chartLine = computed(() => {
  const pts = scaled.value
  if (pts.length < 2) return null
  return 'M ' + pts.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' L ')
})
const chartArea = computed(() => {
  const line = chartLine.value
  if (!line) return null
  const { W, H } = dims
  return `${line} L ${W},${H} L 0,${H} Z`
})
const lastPoint = computed(() => {
  const pts = scaled.value
  return pts.length ? pts[pts.length - 1] : null
})

const yAxisLabels = computed(() => {
  const r = range.value
  if (!r) return []
  const { H, padTop, padBottom } = dims
  const yToPct = (y) => ((y / H) * 100).toFixed(1) + '%'
  return [
    { label: formatNum(Math.round(r.max)), top: yToPct(padTop) },
    { label: formatNum(Math.round((r.max + r.min) / 2)), top: yToPct(H / 2) },
    { label: formatNum(Math.round(r.min)), top: yToPct(H - padBottom) },
  ]
})

const timeAxisLabels = computed(() => {
  const pts = points.value
  if (pts.length < 2) return []
  const first = pts[0]
  const last = pts[pts.length - 1]
  const mid = pts[Math.floor(pts.length / 2)]
  // Labels en relatif (-15min, -30min, maintenant...) : sinon les fenetres
  // 15m et 1h sans variation paraissent identiques alors que le pas differe.
  return [
    { label: formatRelative(first.ts), left: '0%' },
    { label: formatRelative(mid.ts), left: '50%' },
    { label: formatRelative(last.ts), left: '100%' },
  ]
})

// ─── Delta affiche dans le header (diff entre 1er et dernier point) ───
const delta = computed(() => {
  if (points.value.length < 2) return 0
  const first = points.value[0].balance
  const last = points.value[points.value.length - 1].balance
  return last - first
})
const deltaSign = computed(() => (delta.value > 0 ? '+' : delta.value < 0 ? '−' : ''))
const deltaPct = computed(() => {
  if (points.value.length < 2) return '0,00 %'
  const first = points.value[0].balance
  const last = points.value[points.value.length - 1].balance
  if (first === 0) return last > 0 ? '+∞ %' : '0,00 %'
  const pct = ((last - first) / first) * 100
  const sign = pct > 0 ? '+' : ''
  return `${sign}${pct.toFixed(2)} %`
})
const changeClass = computed(() => {
  if (delta.value > 0) return 'up'
  if (delta.value < 0) return 'down'
  return 'flat'
})

function formatRelative(iso) {
  if (!iso) return ''
  const diffMin = Math.round((Date.now() - new Date(iso).getTime()) / 60000)
  if (diffMin < 1) return 'maintenant'
  if (diffMin < 60) return `−${diffMin}min`
  const diffH = diffMin / 60
  if (diffH < 24) {
    const v = diffH >= 10 ? Math.round(diffH) : Math.round(diffH * 10) / 10
    return `−${String(v).replace('.', ',')}h`
  }
  const diffD = diffH / 24
  const v = diffD >= 10 ? Math.round(diffD) : Math.round(diffD * 10) / 10
  return `−${String(v).replace('.', ',')}j`
}
</script>

<style scoped>
.chart-card {
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.2em 1.3em 1em;
}
.chart-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.6em;
  margin-bottom: 0.8em;
  flex-wrap: wrap;
}
.chart-title {
  font-size: 1em;
  margin: 0;
}
.chart-sub {
  margin-top: 0.25em;
  font-size: 0.82em;
  display: flex;
  gap: 0.4em;
  align-items: center;
}
.chart-sub .up { color: var(--green); }
.chart-sub .down { color: var(--red); }
.chart-sub .flat { color: var(--text-2); }
.chart-sub .dim { color: var(--text-3); }

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

.chart-wrapper {
  display: flex;
  align-items: stretch;
  gap: 6px;
}
.y-axis {
  position: relative;
  width: 50px;
  height: 200px;
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
  height: 200px;
  min-width: 0;
}
.chart-svg {
  width: 100%;
  height: 200px;
  display: block;
}

.last-dot {
  position: absolute;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #ff7a00;
  transform: translate(-50%, -50%);
  pointer-events: none;
  z-index: 1;
}
.last-dot::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #ff7a00;
  opacity: 0.25;
  transform: translate(-50%, -50%);
  animation: last-pulse 2s infinite;
}
@keyframes last-pulse {
  0%   { transform: translate(-50%, -50%) scale(0.5); opacity: 0.4; }
  100% { transform: translate(-50%, -50%) scale(2.0); opacity: 0;   }
}

.time-axis {
  position: relative;
  height: 1.3em;
  margin-top: 0.2em;
  margin-left: 56px;
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

.chart-empty {
  text-align: center;
  padding: 1em;
  font-size: 0.85em;
}
.mono { font-family: 'JetBrains Mono', monospace; }
.dim { color: var(--text-3); }

@media (max-width: 640px) {
  .chart-card {
    padding: 1em 0.9em 0.8em;
  }
  .chart-toolbar {
    gap: 0.5em;
    margin-bottom: 0.6em;
  }
  .chart-title { font-size: 0.95em; }
  .chart-sub {
    font-size: 0.78em;
    flex-wrap: wrap;
  }
  .range-pills {
    width: 100%;
    justify-content: space-between;
  }
  .range-pill {
    flex: 1;
    padding: 0.35em 0.4em;
    font-size: 0.75em;
    text-align: center;
  }
  .y-axis {
    width: 38px;
    height: 160px;
  }
  .y-tick { font-size: 0.65em; }
  .chart-canvas,
  .chart-svg {
    height: 160px;
  }
  .time-axis { margin-left: 44px; }
  .time-tick { font-size: 0.65em; }
}

@media (max-width: 380px) {
  .y-axis { width: 32px; }
  .y-tick { font-size: 0.6em; }
  .time-axis { margin-left: 38px; }
  .range-pill { font-size: 0.7em; padding: 0.3em 0.3em; }
}
</style>
