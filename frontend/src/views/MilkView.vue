<template>
  <AppLayout>
    <main class="page fade-in">
      <div class="milk-hero">
        <h2>
          Le lait est <span class="gold">liquide.</span> Tes CAMP aussi.
        </h2>
        <p>
          Bourse du Lait — un AMM <span class="mono">x·y=k</span> par produit
          laitier. Achète quand c'est calme, vends quand l'orage gronde.
          <span class="dim">(le bot dieu peut frapper sans prévenir.)</span>
        </p>
      </div>

      <div v-if="milk.error" class="alert error">{{ milk.error }}</div>

      <div v-if="milk.loading && !milk.pools.length" class="loading">
        Chargement des pools…
      </div>

      <div v-else-if="!milk.pools.length" class="empty">
        Aucun pool actif pour l'instant. L'admin doit en créer un depuis le
        backoffice <code>/admin/milk</code>.
      </div>

      <div v-else class="milk-grid">
        <router-link
          v-for="p in milk.pools"
          :key="p.id"
          :to="`/milk/${encodeURIComponent(p.symbol)}`"
          class="pool-tile"
          :class="{ paused: p.status === 'paused' }"
        >
          <div class="pool-head">
            <div>
              <h3>{{ p.name }}</h3>
              <div class="ticker mono">${{ p.symbol }}</div>
            </div>
            <div class="status-badge" :class="p.status">
              {{ p.status === 'active' ? 'live' : 'pause' }}
            </div>
          </div>

          <div class="pool-price">
            <span class="big mono">{{ p.price.toFixed(2) }}</span>
            <span class="unit">CAMP / bouteille</span>
          </div>

          <div class="pool-change" v-if="p.change_24h_pct !== null">
            <span :class="changeClass(p.change_24h_pct)">
              {{ p.change_24h_pct > 0 ? '+' : '' }}{{ p.change_24h_pct }}% (24h)
              {{ p.change_24h_pct > 0 ? '▲' : (p.change_24h_pct < 0 ? '▼' : '·') }}
            </span>
          </div>
          <div class="pool-change dim" v-else>
            <span class="mono">— pas d'activité 24h</span>
          </div>

          <div class="pool-foot">
            <span class="mono dim">{{ formatNum(p.bottles) }} btl en réserve</span>
            <span class="mono dim">frais {{ p.fee_pct }}%</span>
          </div>
        </router-link>
      </div>

      <div class="milk-disclaimer">
        <span class="accent">⚠ Disclaimer :</span> le lait peut tourner. Vos
        CAMP aussi. Ceci n'est pas un conseil en investissement, mais quand
        même : <i>achetez du lait d'avoine, frérot.</i>
      </div>
    </main>
  </AppLayout>
</template>

<script setup>
import { onMounted } from 'vue'
import AppLayout from '@/components/layout/AppLayout.vue'
import { useMilkStore } from '@/stores/milk'
import { formatNum } from '@/config'

const milk = useMilkStore()

function changeClass(pct) {
  if (pct > 0) return 'up'
  if (pct < 0) return 'down'
  return 'flat'
}

onMounted(() => {
  milk.loadPools()
})
</script>

<style scoped>
.milk-hero {
  background:
    radial-gradient(circle at 80% 50%, rgba(20, 224, 142, 0.12), transparent 60%),
    radial-gradient(circle at 20% 50%, rgba(255, 122, 0, 0.10), transparent 60%),
    linear-gradient(135deg, #0d1614 0%, #0d0d14 100%);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius);
  padding: 2em 1.8em;
  margin-bottom: 1.4em;
  position: relative;
  overflow: hidden;
}
.milk-hero h2 {
  font-size: 2.2em;
  line-height: 1.05;
  letter-spacing: -0.03em;
  max-width: 18ch;
  margin-bottom: 0.3em;
}
.milk-hero .gold {
  background: linear-gradient(90deg, var(--gold, #f5c842), #14e08e);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
.milk-hero p {
  color: var(--text-1);
  max-width: 50ch;
  margin: 0;
}
.milk-hero .dim {
  color: var(--text-2);
  font-style: italic;
}
.milk-hero::after {
  content: '🥛';
  position: absolute;
  right: -10px;
  bottom: -40px;
  font-size: 10em;
  opacity: 0.15;
  transform: rotate(-12deg);
  pointer-events: none;
}

.loading,
.empty {
  text-align: center;
  color: var(--text-2);
  padding: 3em 1em;
}
.empty code {
  background: var(--bg-2);
  padding: 0.15em 0.4em;
  border-radius: 4px;
  font-size: 0.9em;
}

.milk-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 1em;
}

.pool-tile {
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.3em 1.2em;
  text-decoration: none;
  color: inherit;
  display: flex;
  flex-direction: column;
  gap: 0.6em;
  transition: transform 0.2s, border-color 0.2s, box-shadow 0.2s;
}
.pool-tile:hover {
  transform: translateY(-2px);
  border-color: var(--green, #14e08e);
  box-shadow: 0 12px 28px -16px rgba(20, 224, 142, 0.4);
}
.pool-tile.paused {
  opacity: 0.6;
}
.pool-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}
.pool-head h3 {
  font-size: 1em;
  margin-bottom: 0.1em;
}
.pool-head .ticker {
  font-size: 0.78em;
  color: var(--text-3);
  letter-spacing: 0.04em;
}
.status-badge {
  font-size: 0.7em;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  padding: 0.2em 0.55em;
  border-radius: 999px;
}
.status-badge.active {
  background: rgba(20, 224, 142, 0.15);
  color: #14e08e;
}
.status-badge.paused {
  background: var(--bg-3);
  color: var(--text-3);
}

.pool-price {
  display: flex;
  align-items: baseline;
  gap: 0.5em;
}
.pool-price .big {
  font-size: 1.7em;
  font-weight: 700;
  letter-spacing: -0.02em;
}
.pool-price .unit {
  color: var(--text-2);
  font-size: 0.82em;
}

.pool-change {
  font-size: 0.88em;
  font-weight: 600;
}
.pool-change .up { color: #14e08e; }
.pool-change .down { color: var(--red); }
.pool-change .flat { color: var(--text-3); }

.pool-foot {
  margin-top: auto;
  display: flex;
  justify-content: space-between;
  padding-top: 0.8em;
  border-top: 1px dashed var(--border);
  font-size: 0.78em;
}

.milk-disclaimer {
  margin-top: 1.4em;
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

@media (max-width: 640px) {
  .milk-hero {
    padding: 1.3em 1.1em;
    margin-bottom: 1em;
  }
  .milk-hero h2 { font-size: 1.5em; }
  .milk-hero p { font-size: 0.9em; }
  .milk-hero::after { font-size: 7em; bottom: -25px; }

  .milk-grid { gap: 0.7em; }
  .pool-tile { padding: 1em 1em; gap: 0.5em; }
  .pool-head h3 { font-size: 0.95em; }
  .pool-price .big { font-size: 1.45em; }
  .pool-price .unit { font-size: 0.75em; }
  .pool-change { font-size: 0.82em; }
  .pool-foot { font-size: 0.72em; padding-top: 0.6em; }

  .milk-disclaimer {
    margin-top: 1em;
    padding: 0.7em 0.8em;
    font-size: 0.78em;
  }
}
</style>
