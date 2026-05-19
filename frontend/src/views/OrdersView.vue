<template>
  <AppLayout>
    <main class="page fade-in">
      <div class="page-header">
        <h1 class="page-title">📋 Mes demandes</h1>
        <p class="page-sub">Tes achats et ventes de CAMP, du plus récent au plus ancien.</p>
      </div>

      <div class="toolbar">
        <button class="btn-ghost btn-sm" @click="load" :disabled="loading">
          {{ loading ? '…' : '↻ Rafraîchir' }}
        </button>
        <router-link to="/buy" class="btn-primary btn-sm">+ Nouvelle demande</router-link>
      </div>

      <div v-if="loading && orders.length === 0" class="empty-state">
        <div class="emoji">⌛</div>
        Chargement…
      </div>

      <div v-else-if="orders.length === 0" class="card empty-state">
        <div class="emoji">📭</div>
        <div>
          Aucune demande pour l'instant.<br />
          <router-link to="/buy" style="font-weight:600">Lancer ta première demande →</router-link>
        </div>
      </div>

      <div v-else class="orders">
        <article v-for="o in orders" :key="o.id" class="order-card" :class="o.status">
          <div class="order-head">
            <div class="left">
              <div class="type-badge" :class="o.type">
                {{ o.type === 'buy' ? '📈 ACHAT' : '📉 VENTE' }}
              </div>
              <div class="order-id mono">#{{ o.id }}</div>
              <div class="status-pill" :class="o.status">{{ statusLabel(o.status) }}</div>
            </div>
            <div class="date mono">{{ formatDate(o.ts) }}</div>
          </div>

          <div class="order-body">
            <div class="amount-line">
              <span class="big mono">{{ formatNum(o.amount_camp) }}</span>
              <span class="unit">CAMP</span>
              <span class="sep">·</span>
              <span class="big mono eur">{{ formatEur(o.amount_eur) }}</span>
            </div>

            <div v-if="o.handle" class="row">
              <span class="k">Handle</span>
              <span class="v mono">{{ o.handle }}</span>
            </div>
            <div v-if="o.note" class="row">
              <span class="k">Ta note</span>
              <span class="v">« {{ o.note }} »</span>
            </div>
            <div v-if="o.admin_note" class="row admin-note">
              <span class="k">Message d'Hugo</span>
              <span class="v">{{ o.admin_note }}</span>
            </div>
            <div v-if="o.done_at" class="row">
              <span class="k">Traitée le</span>
              <span class="v mono">{{ formatDate(o.done_at) }}</span>
            </div>
            <div v-if="o.tx_hash" class="row">
              <span class="k">Transaction</span>
              <span class="v mono">
                <a :href="'https://sepolia.basescan.org/tx/' + o.tx_hash" target="_blank" rel="noreferrer">
                  Voir sur BaseScan →
                </a>
              </span>
            </div>
          </div>
        </article>
      </div>

      <div v-if="error" class="alert error">{{ error }}</div>
    </main>
  </AppLayout>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import AppLayout from '@/components/layout/AppLayout.vue'
import { apiCall } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { formatEur, formatNum } from '@/config'

const auth = useAuthStore()

const orders = ref([])
const loading = ref(false)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    orders.value = await apiCall('/me/orders', { token: auth.userToken })
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function statusLabel(s) {
  return { pending: 'En attente', done: 'Traitée', cancelled: 'Annulée' }[s] || s
}

function formatDate(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(d.getDate())}/${pad(d.getMonth() + 1)} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

onMounted(load)
</script>

<style scoped>
.toolbar {
  display: flex;
  gap: 0.6em;
  margin-bottom: 1.25em;
  flex-wrap: wrap;
  align-items: center;
}
.btn-primary.btn-sm {
  text-decoration: none;
  font-size: 0.88em;
  padding: 0.5em 0.9em;
}

.orders {
  display: flex;
  flex-direction: column;
  gap: 0.9em;
}

.order-card {
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.2em;
  transition: border-color 0.15s;
}
.order-card:hover { border-color: var(--border-strong); }
.order-card.pending { border-left: 3px solid var(--camp); }
.order-card.done    { border-left: 3px solid var(--green); }
.order-card.cancelled { border-left: 3px solid var(--text-3); opacity: 0.7; }

.order-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.8em;
  margin-bottom: 0.8em;
}
.left {
  display: flex;
  gap: 0.6em;
  align-items: center;
  flex-wrap: wrap;
}

.type-badge {
  font-size: 0.78em;
  font-weight: 700;
  letter-spacing: 0.05em;
  padding: 0.25em 0.6em;
  border-radius: 6px;
}
.type-badge.buy  { background: var(--green-soft); color: var(--green); }
.type-badge.sell { background: var(--red-soft);   color: var(--red); }

.order-id { color: var(--text-3); font-size: 0.85em; }

.status-pill {
  font-size: 0.72em;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 0.25em 0.7em;
  border-radius: 999px;
}
.status-pill.pending   { background: var(--camp-soft); color: var(--camp); }
.status-pill.done      { background: var(--green-soft); color: var(--green); }
.status-pill.cancelled { background: var(--bg-3); color: var(--text-2); }

.date { color: var(--text-3); font-size: 0.85em; }

.order-body {
  display: flex;
  flex-direction: column;
  gap: 0.4em;
}

.amount-line {
  display: flex;
  align-items: baseline;
  gap: 0.5em;
  margin-bottom: 0.5em;
  flex-wrap: wrap;
}
.amount-line .big {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-size: 1.6em;
  font-weight: 700;
  letter-spacing: -0.02em;
}
.amount-line .eur { color: var(--green); }
.amount-line .unit { color: var(--text-2); font-weight: 600; }
.amount-line .sep { color: var(--text-3); }

.row {
  display: flex;
  justify-content: space-between;
  gap: 1em;
  padding: 0.3em 0;
  font-size: 0.9em;
}
.row .k { color: var(--text-2); flex-shrink: 0; }
.row .v { text-align: right; word-break: break-all; color: var(--text-0); }
.row.admin-note {
  background: var(--camp-soft);
  padding: 0.6em 0.8em;
  border-radius: var(--radius-sm);
  margin-top: 0.3em;
}
.row.admin-note .k { color: var(--camp); font-weight: 600; }

@media (max-width: 540px) {
  .row { flex-direction: column; gap: 0.1em; }
  .row .v { text-align: left; }
}
</style>
