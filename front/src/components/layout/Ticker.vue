<template>
  <div class="ticker">
    <div class="ticker-track">
      <span v-for="(t, i) in loop" :key="i" class="ticker-item" :class="t.dir">
        <span class="name">{{ t.name }}</span>
        <span class="value">{{ t.value }}</span>
        <span class="arrow">{{ t.dir === 'up' ? '▲' : '▼' }}</span>
      </span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const items = [
  { name: 'CAMP/USD',    value: '$0.00',  dir: 'down' },
  { name: 'LAIT-ENTIER', value: '1.247',  dir: 'up' },
  { name: 'LAIT-AVOINE', value: '2.881',  dir: 'up' },
  { name: 'LAIT-SOJA',   value: '1.612',  dir: 'down' },
  { name: 'BAGUETTE',    value: '0.42',   dir: 'up' },
  { name: 'RACLETTE-IDX',value: '12.04',  dir: 'up' },
  { name: 'BIERE-1664',  value: '3.50',   dir: 'down' },
  { name: 'RIBA',        value: '0.07',   dir: 'up' },
  { name: 'CAFE-OFFICE', value: '0.85',   dir: 'down' },
  { name: 'KEBAB-LYON',  value: '8.50',   dir: 'up' }
]

const loop = computed(() => [...items, ...items])
</script>

<style scoped>
.ticker {
  background: var(--bg-1);
  border-bottom: 1px solid var(--border);
  overflow: hidden;
  height: 36px;
  position: relative;
}
.ticker-track {
  display: flex;
  gap: 2em;
  align-items: center;
  height: 100%;
  animation: scroll 60s linear infinite;
  white-space: nowrap;
  padding-left: 100%;
}
@keyframes scroll {
  0% { transform: translateX(0); }
  100% { transform: translateX(-50%); }
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
.ticker-item.up .value  { color: var(--green); }
.ticker-item.down .value { color: var(--red); }
.ticker-item .arrow { opacity: 0.4; }
</style>
