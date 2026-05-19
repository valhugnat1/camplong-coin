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
      <div v-for="t in history" :key="t.tx_hash" class="tx-row">
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
    </div>
  </div>
</template>

<script setup>
defineProps({
  history: { type: Array, required: true },
  meUsername: { type: String, required: true }
})

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
