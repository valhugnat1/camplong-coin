<template>
  <div class="ticker">
    <div class="ticker-track" v-if="loop.length">
      <span v-for="(t, i) in loop" :key="i" class="ticker-item" :class="medalClass(t.rank)">
        <span class="rank">#{{ t.rank }}</span>
        <span class="name">{{ t.username }}</span>
        <span class="value">{{ formatNum(t.balance) }} CAMP</span>
      </span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { apiCall } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { formatNum } from '@/config'

const auth = useAuthStore()
const items = ref([])

async function fetchLeaderboard() {
  if (!auth.userToken) return
  try {
    items.value = await apiCall('/leaderboard', { token: auth.userToken })
  } catch (_) {
    // silencieux : si ca foire, on garde l'ancien rendu
  }
}

let timer = null
onMounted(() => {
  fetchLeaderboard()
  timer = setInterval(fetchLeaderboard, 30_000)
})
onUnmounted(() => { if (timer) clearInterval(timer) })

// On repete la liste 3x pour assurer un remplissage immediat sur grand ecran
// et permettre l'animation infinie sans coupure visuelle.
const loop = computed(() => [...items.value, ...items.value, ...items.value])

function medalClass(rank) {
  if (rank === 1) return 'gold'
  if (rank === 2) return 'silver'
  if (rank === 3) return 'bronze'
  return ''
}
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
  gap: 0.5em;
  font-size: 0.82em;
  color: var(--text-1);
  font-family: 'JetBrains Mono', monospace;
}
.ticker-item .rank {
  color: var(--text-3);
  font-weight: 700;
  min-width: 2.2em;
  text-align: right;
}
.ticker-item .name {
  color: var(--text-2);
  font-weight: 600;
}
.ticker-item .value {
  color: var(--text-1);
}
.ticker-item.gold   .rank { color: #ffd34a; }
.ticker-item.silver .rank { color: #cfd6dd; }
.ticker-item.bronze .rank { color: #d99060; }
.ticker-item.gold   .name { color: #ffd34a; }
.ticker-item.silver .name { color: #cfd6dd; }
.ticker-item.bronze .name { color: #d99060; }
</style>
