<template>
  <div class="card">
    <div class="card-header">
      <div class="card-title">Users existants ({{ users.length }})</div>
      <button class="btn-ghost btn-sm" @click="$emit('refresh')" :disabled="loading">
        {{ loading ? '…' : '↻ Rafraîchir' }}
      </button>
    </div>

    <div v-if="users.length === 0" class="empty-state">
      <div class="emoji">👻</div>
      Aucun user pour l'instant.
    </div>

    <div v-else class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Pseudo</th>
            <th>Adresse</th>
            <th style="text-align: right">CAMP</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.username">
            <td><b>{{ u.username }}</b></td>
            <td class="mono">
              <a :href="'https://sepolia.basescan.org/address/' + u.address" target="_blank" rel="noreferrer">
                {{ shortAddr(u.address) }}
              </a>
            </td>
            <td class="balance mono">{{ formatNum(u.balance_camp) }}</td>
            <td class="actions">
              <button class="btn-ghost btn-sm credit" @click="open('credit', u)">+ Créditer</button>
              <button class="btn-ghost btn-sm debit" @click="open('debit', u)">− Débiter</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Mobile cards (alternative à la table) -->
    <div class="mobile-cards" v-if="users.length > 0">
      <div v-for="u in users" :key="'m-' + u.username" class="user-mini">
        <div>
          <div class="u-name">{{ u.username }}</div>
          <div class="u-addr mono">
            <a :href="'https://sepolia.basescan.org/address/' + u.address" target="_blank" rel="noreferrer">
              {{ shortAddr(u.address) }}
            </a>
          </div>
        </div>
        <div>
          <div class="u-bal mono">{{ formatNum(u.balance_camp) }} CAMP</div>
          <div class="u-actions">
            <button class="btn-ghost btn-sm credit" @click="open('credit', u)">+</button>
            <button class="btn-ghost btn-sm debit" @click="open('debit', u)">−</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Modal -->
    <div v-if="modal.open" class="modal-backdrop" @click.self="close">
      <div class="modal">
        <div class="modal-header">
          <h3>
            {{ modal.type === 'credit' ? 'Créditer' : 'Débiter' }}
            <span style="color: var(--camp)">{{ modal.user.username }}</span>
          </h3>
          <button class="modal-close" @click="close" aria-label="Fermer">×</button>
        </div>
        <p class="modal-current">
          Solde actuel : <b class="mono">{{ formatNum(modal.user.balance_camp) }} CAMP</b>
        </p>

        <div class="field">
          <label class="field-label">Montant (CAMP)</label>
          <input v-model.number="modal.amount" type="number" min="1" placeholder="0" />
        </div>
        <div class="field">
          <label class="field-label">Note (optionnel)</label>
          <input v-model="modal.note" placeholder="ex: bonus, ajustement, etc." />
        </div>

        <div class="modal-actions">
          <button class="btn-ghost" @click="close" :disabled="processing">Annuler</button>
          <button
            :class="modal.type === 'credit' ? 'btn-primary' : 'btn-danger'"
            @click="confirm"
            :disabled="processing || !modal.amount"
          >
            {{ processing ? 'Envoi…' : (modal.type === 'credit' ? 'Créditer' : 'Débiter') }}
          </button>
        </div>

        <div v-if="error" class="alert error">{{ error }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { apiCall } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

defineProps({
  users: { type: Array, required: true },
  loading: { type: Boolean, default: false }
})
const emit = defineEmits(['refresh', 'tx-success'])

const auth = useAuthStore()

const modal = reactive({ open: false, type: 'credit', user: {}, amount: 0, note: '' })
const processing = ref(false)
const error = ref('')

function open(type, user) {
  modal.open = true
  modal.type = type
  modal.user = user
  modal.amount = 0
  modal.note = ''
  error.value = ''
}
function close() {
  if (processing.value) return
  modal.open = false
}

async function confirm() {
  error.value = ''
  processing.value = true
  try {
    const path = modal.type === 'credit' ? '/admin/credit' : '/admin/debit'
    const d = await apiCall(path, {
      method: 'POST',
      token: auth.adminToken,
      body: JSON.stringify({
        username: modal.user.username,
        amount: modal.amount,
        note: modal.note
      })
    })
    const verb = modal.type === 'credit' ? 'crédité' : 'débité'
    emit('tx-success', {
      message: `${modal.user.username} ${verb} de ${modal.amount} CAMP (nouveau solde : ${d.new_balance_camp})`,
      tx_hash: d.tx_hash
    })
    close()
    emit('refresh')
  } catch (e) {
    error.value = e.message
  } finally {
    processing.value = false
  }
}

function shortAddr(a) {
  return a ? a.slice(0, 6) + '…' + a.slice(-4) : ''
}
function formatNum(n) {
  if (n == null) return '0'
  return Number(n).toLocaleString('fr-FR')
}
</script>

<style scoped>
.table-wrap {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
}
th, td {
  padding: 0.7em 0.5em;
  text-align: left;
  border-bottom: 1px solid var(--border);
}
th {
  font-size: 0.78em;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-2);
  font-weight: 600;
}
.balance {
  text-align: right;
  font-weight: 700;
}

.actions {
  text-align: right;
  white-space: nowrap;
}
.actions button {
  margin-left: 0.3em;
}
.btn-ghost.credit:hover {
  color: var(--green);
  border-color: var(--green);
}
.btn-ghost.debit:hover {
  color: var(--red);
  border-color: var(--red);
}

/* Mobile view : on cache la table, on affiche des mini-cards */
.mobile-cards { display: none; }

@media (max-width: 720px) {
  .table-wrap { display: none; }
  .mobile-cards {
    display: flex;
    flex-direction: column;
    gap: 0.6em;
  }
}

.user-mini {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.8em;
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}
.u-name { font-weight: 600; }
.u-addr {
  font-size: 0.78em;
  color: var(--text-2);
  margin-top: 0.15em;
}
.u-addr a { color: var(--text-2); }
.u-bal {
  font-weight: 700;
  text-align: right;
}
.u-actions {
  display: flex;
  gap: 0.3em;
  margin-top: 0.4em;
  justify-content: flex-end;
}

/* Modal */
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
  animation: fadeIn 0.15s ease-out;
}
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.modal {
  background: var(--bg-1);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius);
  padding: 1.5em;
  width: 100%;
  max-width: 420px;
  position: relative;
}
.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.4em;
}
.modal-header h3 {
  font-size: 1.2em;
  margin: 0;
}
.modal-close {
  background: none;
  border: none;
  color: var(--text-2);
  font-size: 1.6em;
  cursor: pointer;
  padding: 0 0.3em;
  line-height: 1;
}
.modal-close:hover {
  color: var(--text-0);
}

.modal-current {
  color: var(--text-2);
  font-size: 0.9em;
  margin-bottom: 1em;
}

.modal-actions {
  display: flex;
  gap: 0.6em;
  margin-top: 0.5em;
}
.modal-actions button {
  flex: 1;
}
</style>
