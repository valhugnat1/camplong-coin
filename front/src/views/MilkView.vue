<template>
  <AppLayout>
    <main class="page fade-in">
      <div class="page-header">
        <h1 class="page-title">Bourse du Lait 🥛</h1>
        <p class="page-sub">Le lait n'a jamais été aussi liquide. Investis maintenant.</p>
      </div>

      <div class="milk-hero">
        <div class="milk-chart-card">
          <h3>$LAIT-ENTIER · Lait Entier 1L UHT</h3>
          <div class="milk-chart-price">
            <span class="big">1.247</span>
            <span class="unit">CAMP / litre</span>
            <span class="change mono">+4.21% (24h) ▲</span>
          </div>

          <svg class="milk-chart-svg" viewBox="0 0 600 180" preserveAspectRatio="none">
            <defs>
              <linearGradient id="milkGrad" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stop-color="#14e08e" stop-opacity="0.4" />
                <stop offset="100%" stop-color="#14e08e" stop-opacity="0" />
              </linearGradient>
            </defs>
            <path :d="chartArea" fill="url(#milkGrad)" />
            <path :d="chartLine" fill="none" stroke="#14e08e" stroke-width="2" stroke-linejoin="round" />
            <circle :cx="chartLast.x" :cy="chartLast.y" r="4" fill="#14e08e" />
            <circle :cx="chartLast.x" :cy="chartLast.y" r="8" fill="#14e08e" opacity="0.3">
              <animate attributeName="r" values="4;12;4" dur="2s" repeatCount="indefinite" />
              <animate attributeName="opacity" values="0.5;0;0.5" dur="2s" repeatCount="indefinite" />
            </circle>
          </svg>

          <div class="trade-actions">
            <button class="btn-primary" disabled>📈 Acheter (bientôt)</button>
            <button class="btn-ghost" disabled>📉 Vendre (bientôt)</button>
          </div>
        </div>

        <aside class="milk-side">
          <h4>Top movers du jour</h4>
          <div class="milk-row" v-for="(m, i) in movers" :key="i">
            <div>
              <div class="name">{{ m.name }}</div>
              <div class="ticker mono">{{ m.ticker }}</div>
            </div>
            <div class="delta mono" :class="m.change > 0 ? 'up' : 'down'">
              {{ m.change > 0 ? '+' : '' }}{{ m.change.toFixed(2) }}%
            </div>
          </div>
        </aside>
      </div>

      <div class="milk-disclaimer">
        <span class="accent">⚠ Disclaimer :</span> le lait peut tourner. Vos CAMP aussi. Ceci n'est
        pas un conseil en investissement, mais quand même : <i>achetez du lait d'avoine, frérot.</i>
      </div>
    </main>
  </AppLayout>
</template>

<script setup>
import AppLayout from '@/components/layout/AppLayout.vue'

const movers = [
  { name: "Lait d'avoine bio",  ticker: '$LAIT-AVN', change: 12.4 },
  { name: 'Lait demi-écrémé',   ticker: '$LAIT-DE',  change: 2.1  },
  { name: 'Lait de coco',       ticker: '$LAIT-COC', change: -3.8 },
  { name: 'Lait de soja',       ticker: '$LAIT-SOJ', change: -1.4 },
  { name: "Lait d'amande",      ticker: '$LAIT-AMD', change: 5.7  },
  { name: 'Lait cru fermier',   ticker: '$LAIT-CRU', change: 22.0 },
  { name: 'Lait en poudre',     ticker: '$LAIT-PDR', change: -8.2 }
]

// Procedural chart (deterministic, no randomness so SSR-safe)
const W = 600
const H = 180
const N = 48
const pts = []
for (let i = 0; i < N; i++) {
  const x = (i / (N - 1)) * W
  const y =
    H * 0.6 -
    Math.sin(i * 0.4) * 20 -
    Math.sin(i * 0.13) * 30 +
    Math.sin(i * 0.9) * 6 -
    (i / N) * 25
  pts.push({ x, y: Math.max(20, Math.min(H - 10, y)) })
}
const chartLine = 'M ' + pts.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' L ')
const chartArea = chartLine + ` L ${W},${H} L 0,${H} Z`
const chartLast = pts[pts.length - 1]
</script>

<style scoped>
.milk-hero {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 1em;
  margin-bottom: 1.25em;
}
@media (max-width: 880px) {
  .milk-hero { grid-template-columns: 1fr; }
}

.milk-chart-card {
  position: relative;
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.4em;
  overflow: hidden;
}
.milk-chart-card h3 {
  font-size: 1.1em;
  margin-bottom: 0.3em;
}

.milk-chart-price {
  display: flex;
  align-items: baseline;
  gap: 0.6em;
  margin-bottom: 1em;
  flex-wrap: wrap;
}
.milk-chart-price .big {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-size: 2.4em;
  font-weight: 700;
  letter-spacing: -0.03em;
}
.milk-chart-price .unit {
  color: var(--text-2);
}
.milk-chart-price .change {
  color: var(--green);
  font-weight: 600;
  font-size: 0.92em;
}

.milk-chart-svg {
  width: 100%;
  height: 180px;
  display: block;
}

.trade-actions {
  display: flex;
  gap: 0.5em;
  margin-top: 1em;
}
.trade-actions button {
  flex: 1;
}

.milk-side {
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.3em;
}
.milk-side h4 {
  font-size: 1em;
  margin-bottom: 0.8em;
}

.milk-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.6em 0;
  border-bottom: 1px solid var(--border);
  font-size: 0.92em;
}
.milk-row:last-child {
  border-bottom: none;
}
.milk-row .name {
  font-weight: 500;
}
.milk-row .ticker {
  color: var(--text-3);
  font-size: 0.78em;
}
.delta {
  font-weight: 600;
  font-size: 0.85em;
}
.delta.up { color: var(--green); }
.delta.down { color: var(--red); }

.milk-disclaimer {
  padding: 0.9em 1em;
  background: var(--bg-2);
  border: 1px dashed var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-2);
  font-size: 0.85em;
  font-style: italic;
  text-align: center;
}
.milk-disclaimer .accent {
  color: var(--camp);
  font-style: normal;
  font-weight: 600;
}
</style>
