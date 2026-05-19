<template>
  <AdminTopBar :pending-count="ordersStore.pendingCount" />

  <main class="page fade-in">
    <div class="page-header">
      <h1 class="page-title">📋 Demandes d'achat / vente</h1>
      <p class="page-sub">
        Marque "Traité" une fois que tu as envoyé/reçu le Wero/Revolut.
        Le user reçoit un email de confirmation automatiquement.
      </p>
    </div>

    <!-- Filtres -->
    <div class="filters">
      <button
        v-for="f in filters"
        :key="f.value"
        class="filter"
        :class="{ active: filter === f.value }"
        @click="setFilter(f.value)"
      >
        {{ f.label }}
        <span v-if="counts[f.value]" class="count">{{ counts[f.value] }}</span>
      </button>

      <div class="spacer"></div>

      <button class="btn-ghost btn-sm" @click="load" :disabled="ordersStore.loading">
        {{ ordersStore.loading ? '…' : '↻ Rafraîchir' }}
      </button>
    </div>

    <div v-if="ordersStore.lastError" class="alert error">{{ ordersStore.lastError }}</div>

    <div v-if="filtered.length === 0 && !ordersStore.loading" class="empty-state card">
      <div class="emoji">📭</div>
      Aucune demande {{ filter === 'all' ? '' : statusLabel(filter).toLowerCase() }}.
    </div>

    <div v-else class="orders">
      <article
        v-for="o in filtered"
        :key="o.id"
        class="order-card"
        :class="o.status"
      >
        <!-- Header -->
        <div class="order-head">
          <div class="left">
            <div class="type-badge" :class="o.type">
              {{ o.type === 'buy' ? '📈 ACHAT' : '📉 VENTE' }}
            </div>
            <div class="order-id mono">#{{ o.id }}</div>
            <div class="user-chip-line">
              <span class="username">{{ o.username }}</span>
              <a
                v-if="o.user_email"
                :href="'mailto:' + o.user_email"
                class="email-link"
              >
                {{ o.user_email }}
              </a>
              <span v-else class="no-email">⚠ pas d'email</span>
            </div>
          </div>
          <div class="right">
            <div class="status-pill" :class="o.status">{{ statusLabel(o.status) }}</div>
            <div class="date mono">{{ formatDate(o.ts) }}</div>
          </div>
        </div>

        <!-- Body -->
        <div class="order-body">
          <div class="amount-line">
            <span class="big mono">{{ formatNum(o.amount_camp) }}</span>
            <span class="unit">CAMP</span>
            <span class="sep">·</span>
            <span class="big mono eur">{{ formatEur(o.amount_eur) }}</span>
          </div>

          <div v-if="o.handle" class="row">
            <span class="k">Handle Wero / Revolut</span>
            <span class="v mono">
              {{ o.handle }}
              <button class="copy" @click="copy(o.handle, 'h' + o.id)">
                {{ copiedKey === 'h' + o.id ? '✓' : '📋' }}
              </button>
            </span>
          </div>
          <div v-if="o.note" class="row">
            <span class="k">Note user</span>
            <span class="v">« {{ o.note }} »</span>
          </div>
          <div v-if="o.admin_note" class="row admin-note">
            <span class="k">Ton message (envoyé au user)</span>
            <span class="v">{{ o.admin_note }}</span>
          </div>
          <div v-if="o.done_at" class="row">
            <span class="k">Traitée le</span>
            <span class="v mono">{{ formatDate(o.done_at) }}</span>
          </div>
        </div>

        <!-- Actions -->
        <div class="order-actions">
          <button
            v-if="o.status !== 'done'"
            class="btn-primary btn-sm"
            @click="openDoneModal(o)"
          >
            ✓ Marquer comme traité
          </button>
          <button
            v-if="o.status === 'done'"
            class="btn-ghost btn-sm"
            @click="setStatus(o, 'pending')"
          >
            ↩ Repasser en attente
          </button>
          <button
            v-if="o.status === 'pending'"
            class="btn-ghost btn-sm cancel"
            @click="setStatus(o, 'cancelled')"
          >
            ✕ Annuler
          </button>
          <button
            class="btn-ghost btn-sm delete"
            @click="openDeleteModal(o)"
          >
            🗑
          </button>
        </div>
      </article>
    </div>
  </main>

  <!-- Modal "Marquer comme traité" -->
  <div v-if="doneModal.open" class="modal-backdrop" @click.self="closeDoneModal">
    <div class="modal">
      <div class="modal-header">
        <h3>✓ Marquer comme traité</h3>
        <button class="modal-close" @click="closeDoneModal">×</button>
      </div>

      <p class="modal-explain">
        Demande #{{ doneModal.order.id }} —
        {{ doneModal.order.type === 'buy' ? 'ACHAT' : 'VENTE' }} de
        <b class="mono">{{ formatNum(doneModal.order.amount_camp) }} CAMP</b>
        ({{ formatEur(doneModal.order.amount_eur) }}) par
        <b>{{ doneModal.order.username }}</b>.
      </p>

      <div v-if="doneModal.order.type === 'buy'" class="reminder">
        ⚠ Vérifie d'abord :<br />
        1. Tu as bien reçu <b>{{ formatEur(doneModal.order.amount_eur) }}</b> sur Wero/Revolut.<br />
        2. Tu as crédité <b>{{ formatNum(doneModal.order.amount_camp) }} CAMP</b>
        à <b>{{ doneModal.order.username }}</b> via le backoffice.
      </div>
      <div v-else class="reminder">
        ⚠ Vérifie d'abord :<br />
        1. Tu as débité <b>{{ formatNum(doneModal.order.amount_camp) }} CAMP</b>
        à <b>{{ doneModal.order.username }}</b> via le backoffice.<br />
        2. Tu as envoyé <b>{{ formatEur(doneModal.order.amount_eur) }}</b>
        sur <span class="mono">{{ doneModal.order.handle }}</span>.
      </div>

      <div class="field">
        <label class="field-label">Message au user (optionnel, visible dans l'email)</label>
        <textarea
          v-model="doneModal.adminNote"
          rows="2"
          placeholder="ex: J'ai mis 50 CAMP en bonus parce que t'es sympa"
        ></textarea>
      </div>

      <div v-if="doneModal.order.user_email" class="email-info">
        📧 Email auto envoyé à <b>{{ doneModal.order.user_email }}</b>
      </div>
      <div v-else class="email-info warn">
        ⚠ Ce user n'a pas d'email, aucune notif ne sera envoyée.
      </div>

      <div class="modal-actions">
        <button class="btn-ghost" @click="closeDoneModal" :disabled="doneModal.busy">Annuler</button>
        <button class="btn-primary" @click="confirmDone" :disabled="doneModal.busy">
          {{ doneModal.busy ? 'Envoi…' : 'Marquer comme traité' }}
        </button>
      </div>

      <div v-if="doneModal.error" class="alert error">{{ doneModal.error }}</div>
    </div>
  </div>

  <!-- Modal suppression -->
  <div v-if="delModal.open" class="modal-backdrop" @click.self="closeDeleteModal">
    <div class="modal">
      <div class="modal-header">
        <h3>🗑 Supprimer la demande #{{ delModal.order.id }}</h3>
        <button class="modal-close" @click="closeDeleteModal">×</button>
      </div>
      <p class="modal-explain">
        Cette action est définitive. Utilise plutôt "Annuler" si tu veux garder une trace.
      </p>
      <div class="modal-actions">
        <button class="btn-ghost" @click="closeDeleteModal" :disabled="delModal.busy">Annuler</button>
        <button class="btn-danger" @click="confirmDelete" :disabled="delModal.busy">
          {{ delModal.busy ? 'Suppression…' : 'Supprimer' }}
        </button>
      </div>
      <div v-if="delModal.error" class="alert error">{{ delModal.error }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import AdminTopBar from '@/components/admin/AdminTopBar.vue'
import { useOrdersStore } from '@/stores/orders'
import { formatEur, formatNum } from '@/config'

const ordersStore = useOrdersStore()

const filter = ref('pending')
const filters = [
  { value: 'pending',   label: 'En attente' },
  { value: 'done',      label: 'Traitées' },
  { value: 'cancelled', label: 'Annulées' },
  { value: 'all',       label: 'Toutes' }
]

const copiedKey = ref('')

const counts = computed(() => ({
  all: ordersStore.orders.length,
  pending: ordersStore.orders.filter((o) => o.status === 'pending').length,
  done: ordersStore.orders.filter((o) => o.status === 'done').length,
  cancelled: ordersStore.orders.filter((o) => o.status === 'cancelled').length
}))

const filtered = computed(() => {
  if (filter.value === 'all') return ordersStore.orders
  return ordersStore.orders.filter((o) => o.status === filter.value)
})

function statusLabel(s) {
  return { pending: 'En attente', done: 'Traitée', cancelled: 'Annulée' }[s] || s
}

function formatDate(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${String(d.getFullYear()).slice(-2)} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function copy(text, key) {
  try {
    await navigator.clipboard.writeText(text)
    copiedKey.value = key
    setTimeout(() => (copiedKey.value = ''), 1500)
  } catch (e) { /* silencieux */ }
}

async function load() {
  // On charge toujours toutes les orders, le filtre est côté client
  await ordersStore.load('all')
}

function setFilter(f) {
  filter.value = f
}

async function setStatus(order, status) {
  try {
    await ordersStore.update(order.id, { status })
  } catch (e) {
    alert(e.message)
  }
}

// ─── Modal "marquer comme traité"
const doneModal = reactive({ open: false, order: {}, adminNote: '', busy: false, error: '' })

function openDoneModal(order) {
  doneModal.open = true
  doneModal.order = order
  doneModal.adminNote = ''
  doneModal.busy = false
  doneModal.error = ''
}
function closeDoneModal() {
  if (doneModal.busy) return
  doneModal.open = false
}
async function confirmDone() {
  doneModal.busy = true
  doneModal.error = ''
  try {
    await ordersStore.update(doneModal.order.id, {
      status: 'done',
      admin_note: doneModal.adminNote
    })
    closeDoneModal()
  } catch (e) {
    doneModal.error = e.message
  } finally {
    doneModal.busy = false
  }
}

// ─── Modal suppression
const delModal = reactive({ open: false, order: {}, busy: false, error: '' })
function openDeleteModal(order) {
  delModal.open = true
  delModal.order = order
  delModal.busy = false
  delModal.error = ''
}
function closeDeleteModal() {
  if (delModal.busy) return
  delModal.open = false
}
async function confirmDelete() {
  delModal.busy = true
  delModal.error = ''
  try {
    await ordersStore.remove(delModal.order.id)
    closeDeleteModal()
  } catch (e) {
    delModal.error = e.message
  } finally {
    delModal.busy = false
  }
}

onMounted(load)
</script>

<style scoped>
.filters {
  display: flex;
  align-items: center;
  gap: 0.4em;
  margin-bottom: 1.25em;
  flex-wrap: wrap;
}
.filters .spacer { flex: 1; }

.filter {
  background: var(--bg-2);
  color: var(--text-2);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 0.45em 0.9em;
  cursor: pointer;
  font-size: 0.88em;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 0.4em;
}
.filter:hover { color: var(--text-0); }
.filter.active {
  background: var(--camp);
  color: white;
  border-color: var(--camp);
}
.filter .count {
  background: rgba(0, 0, 0, 0.25);
  padding: 0.05em 0.5em;
  border-radius: 999px;
  font-size: 0.78em;
}
.filter:not(.active) .count {
  background: var(--bg-3);
  color: var(--text-2);
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
.order-card.pending   { border-left: 3px solid var(--camp); }
.order-card.done      { border-left: 3px solid var(--green); }
.order-card.cancelled { border-left: 3px solid var(--text-3); opacity: 0.65; }

.order-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 0.8em;
  margin-bottom: 0.8em;
}
.left, .right {
  display: flex;
  align-items: center;
  gap: 0.6em;
  flex-wrap: wrap;
}
.right { flex-direction: column; align-items: flex-end; gap: 0.3em; }

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

.user-chip-line {
  display: flex;
  align-items: center;
  gap: 0.5em;
  font-size: 0.9em;
  flex-wrap: wrap;
}
.username { font-weight: 600; }
.email-link {
  color: var(--text-1);
  font-size: 0.85em;
  text-decoration: underline;
  text-decoration-color: transparent;
  text-underline-offset: 3px;
}
.email-link:hover { text-decoration-color: var(--text-1); }
.no-email { color: var(--red); font-size: 0.78em; font-style: italic; }

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

.date { color: var(--text-3); font-size: 0.82em; }

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
.row .v {
  text-align: right;
  word-break: break-all;
  color: var(--text-0);
  display: inline-flex;
  align-items: center;
  gap: 0.4em;
}
.row.admin-note {
  background: var(--camp-soft);
  padding: 0.6em 0.8em;
  border-radius: var(--radius-sm);
  margin-top: 0.3em;
}
.row.admin-note .k { color: var(--camp); font-weight: 600; }

.copy {
  background: var(--bg-3);
  border: none;
  border-radius: 4px;
  padding: 0.15em 0.4em;
  cursor: pointer;
  font-size: 0.85em;
}

.order-actions {
  margin-top: 1em;
  padding-top: 0.8em;
  border-top: 1px dashed var(--border);
  display: flex;
  gap: 0.5em;
  justify-content: flex-end;
  flex-wrap: wrap;
}
.btn-ghost.cancel:hover { color: var(--red); border-color: var(--red); }
.btn-ghost.delete:hover { color: var(--red); border-color: var(--red); background: var(--red-soft); }

/* Modals */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(7, 7, 10, 0.75);
  backdrop-filter: blur(4px);
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1em;
}
.modal {
  background: var(--bg-1);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius);
  padding: 1.5em;
  width: 100%;
  max-width: 460px;
}
.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.6em;
}
.modal-header h3 { font-size: 1.2em; margin: 0; }
.modal-close {
  background: none;
  border: none;
  color: var(--text-2);
  font-size: 1.6em;
  cursor: pointer;
  line-height: 1;
  padding: 0 0.3em;
}
.modal-close:hover { color: var(--text-0); }

.modal-explain {
  color: var(--text-1);
  font-size: 0.92em;
  margin: 0 0 1em 0;
}

.reminder {
  background: var(--camp-soft);
  border: 1px solid rgba(255, 122, 0, 0.2);
  border-radius: var(--radius-sm);
  padding: 0.8em 1em;
  color: var(--text-1);
  font-size: 0.88em;
  line-height: 1.6;
  margin-bottom: 1em;
}

.email-info {
  padding: 0.5em 0.8em;
  background: var(--bg-2);
  border-radius: var(--radius-sm);
  font-size: 0.85em;
  color: var(--text-1);
  margin: 0.8em 0;
}
.email-info.warn {
  background: var(--red-soft);
  color: #ffb3c1;
}

textarea {
  resize: vertical;
  min-height: 60px;
  font-family: inherit;
}

.modal-actions {
  display: flex;
  gap: 0.6em;
  margin-top: 0.5em;
}
.modal-actions button { flex: 1; }
</style>
