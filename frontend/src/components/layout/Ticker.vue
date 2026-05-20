<template>
  <div class="ticker">
    <div class="ticker-track">
      <span v-for="(t, i) in loop" :key="i" class="ticker-item" :class="t.dir">
        <span class="name">{{ t.name }}</span>
        <span class="value">{{ t.value }}</span>
        <span class="arrow">{{ t.dir === 'up' ? '▲' : t.dir === 'down' ? '▼' : '◆' }}</span>
      </span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

// Mix entre vrais tickers (lait/café/baguette) et private jokes.
// `dir` = 'up' (vert), 'down' (rouge), 'flat' (gris diamant) — pour varier visuellement.
const items = [
  // Tickers "officiels"
  { name: 'CAMP/USD',     value: '$0.0099',      dir: 'up' },
  { name: 'CAMP/EUR',     value: '€0.01',        dir: 'flat' },
  { name: 'LAIT-ENTIER',  value: '1.247',        dir: 'up' },
  { name: 'LAIT-AVOINE',  value: '2.881',        dir: 'up' },
  { name: 'LAIT-SOJA',    value: '1.612',        dir: 'down' },
  { name: 'LAIT-AMANDE',  value: '2.105',        dir: 'up' },
  { name: 'LAIT-COCO',    value: '3.220',        dir: 'down' },
  { name: 'LAIT-RIZ',     value: '1.890',        dir: 'flat' },
  { name: 'BAGUETTE',     value: '1.20',         dir: 'up' },
  { name: 'RACLETTE-IDX', value: '12.04',        dir: 'up' },
  { name: 'BIERE-1664',   value: '3.50',         dir: 'down' },
  { name: 'CAFE-OFFICE',  value: '0.85',         dir: 'down' },
  { name: 'KEBAB-LYON',   value: '8.50',         dir: 'up' },
  { name: 'CROISSANT',    value: '1.40',         dir: 'flat' },
  { name: 'ROUTARD-PIZZA',value: '12.00',        dir: 'up' },
  // Macro / market wide
  { name: 'CAC-40',       value: '7654.21',      dir: 'down' },
  { name: 'BTC',          value: '$84 220',      dir: 'up' },
  { name: 'ETH',          value: '$3 412',       dir: 'up' },
  { name: 'GAS-BASE',     value: '0.001 gwei',   dir: 'flat' },
  // Private jokes
  { name: 'RIBA',         value: '0.07',         dir: 'up' },
  { name: 'HOLLOW-KNIGHT',value: '∞',            dir: 'flat' },
  { name: 'DUNE-IMP',     value: '9.5/10',       dir: 'up' },
  { name: 'CATAN-WINS',   value: 'Alice: 12',    dir: 'up' },
  { name: 'CROAGH-PATRICK', value: 'Météo: ☔',  dir: 'down' },
  { name: 'MISTRAL-AI',   value: 'EMBAUCHE',     dir: 'up' },
  { name: 'BNP-DEPLOY',   value: 'READY',        dir: 'up' },
  { name: 'SCALEWAY-9TO5',value: 'TICK TOCK',    dir: 'down' },
  { name: 'LUXEMBOURG',   value: '+€465/mo',     dir: 'up' },
  { name: 'METZ-LUX-TGV', value: 'CANCELLED',    dir: 'down' },
  { name: 'IRELAND-TRIP', value: 'J−42',         dir: 'up' },
  { name: 'IMPOTS-FR',    value: '~€1 000',      dir: 'down' },
  { name: 'LMNP-PARIS',   value: 'EN COURS',     dir: 'flat' },
  { name: 'CHESS-RAPID',  value: '900 ELO',      dir: 'up' },
  { name: 'TRADE-REP-DE', value: 'FORM 3916',    dir: 'flat' }
]

// On répète la liste 3× pour assurer un remplissage immédiat sur grand écran
// et permettre l'animation infinie sans coupure visuelle.
const loop = computed(() => [...items, ...items, ...items])
</script>

<style scoped>
.ticker {
  background: var(--bg-1);
  border-bottom: 1px solid var(--border);
  overflow: hidden;
  height: 36px;
  position: relative;
  /* fade left + right pour atténuer les bords */
  -webkit-mask-image: linear-gradient(90deg, transparent 0, black 60px, black calc(100% - 60px), transparent 100%);
          mask-image: linear-gradient(90deg, transparent 0, black 60px, black calc(100% - 60px), transparent 100%);
}

.ticker-track {
  display: flex;
  gap: 2em;
  align-items: center;
  height: 100%;
  width: max-content;
  /* On translate de 1/3 (= 1× la liste de base) pour boucler proprement
     vu qu'on a 3 copies. */
  animation: scroll 120s linear infinite;
  white-space: nowrap;
  padding-left: 1em;
}

@keyframes scroll {
  0%   { transform: translateX(0); }
  100% { transform: translateX(calc(-100% / 3)); }
}

.ticker-item {
  display: flex;
  align-items: center;
  gap: 0.4em;
  font-size: 0.82em;
  color: var(--text-1);
  font-family: 'JetBrains Mono', monospace;
}
.ticker-item .name {
  color: var(--text-2);
  font-weight: 600;
}
.ticker-item.up   .value { color: var(--green); }
.ticker-item.down .value { color: var(--red); }
.ticker-item.flat .value { color: var(--text-1); }
.ticker-item .arrow {
  opacity: 0.5;
  font-size: 0.85em;
}
.ticker-item.up   .arrow { color: var(--green); }
.ticker-item.down .arrow { color: var(--red); }
.ticker-item.flat .arrow { color: var(--text-3); }
</style>
