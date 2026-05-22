<template>
  <div class="card history-card">
    <div class="card-header">
      <div class="card-title">📜 Historique</div>
      <span class="hint">{{ history.length }} tx</span>
    </div>

    <div v-if="history.length === 0" class="empty-state">
      <div class="emoji">🤷</div>
      <div>
        Aucune transaction.<br />
        <span style="color: var(--text-3); font-size: 0.9em">Faut bien commencer quelque part.</span>
      </div>
    </div>

    <div v-else>
      <div v-for="t in paginated" :key="t.tx_hash" class="tx-row">
        <div class="tx-icon" :class="t.from === meUsername ? 'out' : 'in'">
          {{ t.from === meUsername ? '↗' : '↙' }}
        </div>
        <div class="tx-main">
          <div class="tx-counter">
            {{ t.from === meUsername ? 'À ' + t.to : 'De ' + t.from }}
          </div>
          <div class="tx-note" v-if="t.note">« {{ t.note }} »</div>
        </div>
        <div class="tx-date mono">{{ formatDate(t.ts) }}</div>
        <div class="tx-amount mono" :class="t.from === meUsername ? 'out' : 'in'">
          {{ t.from === meUsername ? '−' : '+' }}{{ formatNum(t.amount) }}
        </div>
      </div>

      <div v-if="totalPages > 1" class="pager">
        <button
          class="pager-btn"
          @click="page = Math.max(1, page - 1)"
          :disabled="page === 1"
          aria-label="Page précédente"
        >←</button>
        <div class="pager-info mono">
          {{ page }} / {{ totalPages }}
        </div>
        <button
          class="pager-btn"
          @click="page = Math.min(totalPages, page + 1)"
          :disabled="page === totalPages"
          aria-label="Page suivante"
        >→</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  history: { type: Array, required: true },
  meUsername: { type: String, required: true }
})

const PAGE_SIZE = 8
const page = ref(1)

const totalPages = computed(() =>
  Math.max(1, Math.ceil((props.history?.length || 0) / PAGE_SIZE))
)
const paginated = computed(() => {
  const start = (page.value - 1) * PAGE_SIZE
  return props.history.slice(start, start + PAGE_SIZE)
})

watch(
  () => props.history.length,
  () => {
    if (page.value > totalPages.value) page.value = totalPages.value
  }
)

function formatDate(ts) {
  const d = new Date(ts)
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(d.getDate())}/${pad(d.getMonth() + 1)} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}
function formatNum(n) {
  if (n == null) return '0'
  return Number(n).toLocaleString('fr-FR')
}
</script>

<style scoped>
.hint {
  color: var(--text-3);
  font-size: 0.82em;
}

.tx-row {
  display: grid;
  grid-template-columns: auto 1fr auto auto;
  align-items: center;
  gap: 1em;
  padding: 0.85em 0;
  border-bottom: 1px solid var(--border);
}
.tx-row:last-child {
  border-bottom: none;
}

.tx-icon {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  font-weight: 700;
  font-size: 1.1em;
}
.tx-icon.out { background: var(--red-soft); color: var(--red); }
.tx-icon.in  { background: var(--green-soft); color: var(--green); }

.tx-main {
  min-width: 0;
}
.tx-counter {
  font-weight: 600;
  font-size: 0.95em;
  margin-bottom: 0.15em;
}
.tx-note {
  color: var(--text-2);
  font-size: 0.85em;
  font-style: italic;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.tx-date {
  color: var(--text-3);
  font-size: 0.82em;
}
.tx-amount {
  font-weight: 600;
  font-size: 1em;
  text-align: right;
}
.tx-amount.out { color: var(--red); }
.tx-amount.in { color: var(--green); }

.pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1em;
  margin-top: 1em;
  padding-top: 1em;
  border-top: 1px solid var(--border);
}
.pager-btn {
  width: 40px;
  height: 40px;
  padding: 0;
  border-radius: 10px;
  background: var(--bg-2);
  color: var(--text-0);
  border: 1px solid var(--border);
  font-size: 1.1em;
  display: grid;
  place-items: center;
}
.pager-btn:hover:not(:disabled) {
  background: var(--bg-3);
  border-color: var(--border-strong);
}
.pager-btn:active:not(:disabled) {
  transform: scale(0.95);
}
.pager-info {
  color: var(--text-1);
  font-size: 0.92em;
  min-width: 4em;
  text-align: center;
}

@media (max-width: 640px) {
  .tx-row {
    grid-template-columns: auto 1fr auto;
    grid-template-areas:
      "icon main amount"
      "icon date date";
    row-gap: 0.2em;
  }
  .tx-icon { grid-area: icon; }
  .tx-main { grid-area: main; }
  .tx-amount { grid-area: amount; }
  .tx-date {
    grid-area: date;
    text-align: left;
    padding-left: 0;
  }
}
</style>
