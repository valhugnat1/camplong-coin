<template>
  <div class="card">
    <div class="card-header">
      <div class="card-title">Users existants ({{ users.length }})</div>
      <div class="header-right">
        <span class="hint mono">total: {{ formatNum(totalCamp) }} CAMP · {{ formatEur(campToEur(totalCamp)) }}</span>
        <button class="btn-ghost btn-sm" @click="$emit('refresh')" :disabled="loading">
          {{ loading ? '…' : '↻ Rafraîchir' }}
        </button>
      </div>
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
            <th>Email</th>
            <th>Adresse</th>
            <th style="text-align: right">CAMP</th>
            <th style="text-align: right">Valeur (€)</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.username">
            <td><b>{{ u.username }}</b></td>
            <td>
              <span v-if="u.email" class="email-cell">{{ u.email }}</span>
              <span v-else class="dim">—</span>
            </td>
            <td class="mono">
              <a :href="'https://sepolia.basescan.org/address/' + u.address" target="_blank" rel="noreferrer">
                {{ shortAddr(u.address) }}
              </a>
            </td>
            <td class="balance mono">{{ formatNum(u.balance_camp) }}</td>
            <td class="balance-eur mono">{{ formatEur(campToEur(u.balance_camp)) }}</td>
            <td class="actions">
              <button class="btn-ghost btn-sm credit" @click="open('credit', u)">+ Créditer</button>
              <button class="btn-ghost btn-sm debit"  @click="open('debit', u)">− Débiter</button>
              <button class="btn-ghost btn-sm danger" @click="openDelete(u)">🗑</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Mobile cards -->
    <div class="mobile-cards" v-if="users.length > 0">
      <div v-for="u in users" :key="'m-' + u.username" class="user-mini">
        <div class="user-mini-top">
          <div>
            <div class="u-name">{{ u.username }}</div>
            <div v-if="u.email" class="u-email">{{ u.email }}</div>
            <div class="u-addr mono">
              <a :href="'https://sepolia.basescan.org/address/' + u.address" target="_blank" rel="noreferrer">
                {{ shortAddr(u.address) }}
              </a>
            </div>
          </div>
          <div class="u-bal-wrap">
            <div class="u-bal mono">{{ formatNum(u.balance_camp) }} CAMP</div>
            <div class="u-bal-eur mono">{{ formatEur(campToEur(u.balance_camp)) }}</div>
          </div>
        </div>
        <div class="u-actions">
          <button class="btn-ghost btn-sm credit" @click="open('credit', u)">+ Créditer</button>
          <button class="btn-ghost btn-sm debit"  @click="open('debit', u)">− Débiter</button>
          <button class="btn-ghost btn-sm danger" @click="openDelete(u)">🗑 Supprimer</button>
        </div>
      </div>
    </div>

    <!-- Modal Credit/Debit -->
    <div v-if="modal.open" class="modal-backdrop" @click.self="close">
      <div class="modal">
        <div class="modal-header">
          <h3>
            {{ modal.type === 'credit' ? 'Créditer' : 'Débiter' }}
            <span style="color: var(--camp)">{{ modal.user.username }}</span>
          </h3>
          <button class="modal-close" @click="close">×</button>
        </div>
        <p class="modal-current">
          Solde actuel : <b class="mono">{{ formatNum(modal.user.balance_camp) }} CAMP</b>
          <span class="mono dim">· {{ formatEur(campToEur(modal.user.balance_camp)) }}</span>
        </p>

        <div class="field">
          <label class="field-label">Montant (CAMP)</label>
          <input v-model.number="modal.amount" type="number" min="1" placeholder="0" />
          <div v-if="modal.amount" class="modal-eur mono">
            ≈ {{ formatEur(campToEur(modal.amount)) }}
          </div>
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

    <!-- Modal Suppression -->
    <div v-if="delModal.open" class="modal-backdrop" @click.self="closeDelete">
      <div class="modal">
        <div class="modal-header">
          <h3>🗑 Supprimer <span style="color: var(--red)">{{ delModal.user.username }}</span></h3>
          <button class="modal-close" @click="closeDelete">×</button>
        </div>

        <div class="alert error" v-if="delModal.user.balance_camp > 0">
          ⚠ Ce user a encore <b>{{ formatNum(delModal.user.balance_camp) }} CAMP</b>
          ({{ formatEur(campToEur(delModal.user.balance_camp)) }}).
          <br />
          Débite-le d'abord pour ne pas laisser de CAMP orphelins.
        </div>

        <p class="del-warn" v-else>
          La suppression est <b>définitive</b>. Les transactions historiques restent
          (pour audit) mais ses demandes en cours seront supprimées.
        </p>

        <div class="field">
          <label class="field-label">
            Tape <code class="mono">{{ delModal.user.username }}</code> pour confirmer
          </label>
          <input v-model="delModal.confirm" :placeholder="delModal.user.username" />
        </div>

        <div class="modal-actions">
          <button class="btn-ghost" @click="closeDelete" :disabled="delProcessing">Annuler</button>
          <button
            class="btn-danger"
            @click="confirmDelete"
            :disabled="delProcessing || !canDelete"
          >
            {{ delProcessing ? 'Suppression…' : 'Supprimer définitivement' }}
          </button>
        </div>

        <div v-if="delError" class="alert error">{{ delError }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, computed } from 'vue'
import { apiCall } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { campToEur, formatEur, formatNum } from '@/config'

const props = defineProps({
  users: { type: Array, required: true },
  loading: { type: Boolean, default: false }
})
const emit = defineEmits(['refresh', 'tx-success'])

const auth = useAuthStore()

const totalCamp = computed(() =>
  props.users.reduce((s, u) => s + Number(u.balance_camp || 0), 0)
)

// ─── Credit/Debit modal
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

// ─── Delete modal
const delModal = reactive({ open: false, user: {}, confirm: '' })
const delProcessing = ref(false)
const delError = ref('')

const canDelete = computed(
  () => delModal.confirm === delModal.user.username
        && (delModal.user.balance_camp || 0) === 0
)

function openDelete(user) {
  delModal.open = true
  delModal.user = user
  delModal.confirm = ''
  delError.value = ''
}
function closeDelete() {
  if (delProcessing.value) return
  delModal.open = false
}

async function confirmDelete() {
  delError.value = ''
  delProcessing.value = true
  try {
    await apiCall(`/admin/users/${encodeURIComponent(delModal.user.username)}`, {
      method: 'DELETE',
      token: auth.adminToken
    })
    emit('tx-success', {
      message: `User « ${delModal.user.username} » supprimé.`,
      tx_hash: ''
    })
    closeDelete()
    emit('refresh')
  } catch (e) {
    delError.value = e.message
  } finally {
    delProcessing.value = false
  }
}

function shortAddr(a) {
  return a ? a.slice(0, 6) + '…' + a.slice(-4) : ''
}
</script>

<style scoped>
.header-right { display: flex; align-items: center; gap: 0.8em; flex-wrap: wrap; }
.hint { color: var(--text-3); font-size: 0.8em; }
.dim  { color: var(--text-3); margin-left: 0.4em; font-style: italic; }

.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 0.7em 0.5em; text-align: left; border-bottom: 1px solid var(--border); }
th { font-size: 0.78em; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-2); font-weight: 600; }

.email-cell { font-size: 0.85em; color: var(--text-1); }
.balance { text-align: right; font-weight: 700; }
.balance-eur { text-align: right; color: var(--text-2); font-size: 0.88em; font-weight: 500; }

.actions {
  text-align: right;
  white-space: nowrap;
  display: flex;
  gap: 0.3em;
  justify-content: flex-end;
}
.btn-ghost.credit:hover { color: var(--green); border-color: var(--green); }
.btn-ghost.debit:hover  { color: var(--red); border-color: var(--red); }
.btn-ghost.danger { padding: 0.5em 0.6em; }
.btn-ghost.danger:hover { color: var(--red); border-color: var(--red); background: var(--red-soft); }

.mobile-cards { display: none; }

@media (max-width: 760px) {
  .table-wrap { display: none; }
  .mobile-cards {
    display: flex;
    flex-direction: column;
    gap: 0.6em;
  }
}

.user-mini {
  padding: 0.9em;
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}
.user-mini-top {
  display: flex;
  justify-content: space-between;
  gap: 1em;
  margin-bottom: 0.6em;
}
.u-name { font-weight: 600; }
.u-email { font-size: 0.82em; color: var(--text-1); margin-top: 0.1em; }
.u-addr { font-size: 0.78em; color: var(--text-2); margin-top: 0.15em; }
.u-addr a { color: var(--text-2); }
.u-bal-wrap { text-align: right; }
.u-bal { font-weight: 700; }
.u-bal-eur { color: var(--text-2); font-size: 0.82em; margin-top: 0.15em; }
.u-actions {
  display: flex;
  gap: 0.4em;
  justify-content: flex-end;
  flex-wrap: wrap;
}

/* Modal commun */
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
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

.modal {
  background: var(--bg-1);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius);
  padding: 1.5em;
  width: 100%;
  max-width: 420px;
}
.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.4em;
}
.modal-header h3 { font-size: 1.2em; margin: 0; }
.modal-close {
  background: none;
  border: none;
  color: var(--text-2);
  font-size: 1.6em;
  cursor: pointer;
  padding: 0 0.3em;
  line-height: 1;
}
.modal-close:hover { color: var(--text-0); }

.modal-current { color: var(--text-2); font-size: 0.9em; margin-bottom: 1em; }
.modal-eur { margin-top: 0.4em; color: var(--text-2); font-size: 0.85em; text-align: right; }

.modal-actions {
  display: flex;
  gap: 0.6em;
  margin-top: 0.5em;
}
.modal-actions button { flex: 1; }

.del-warn {
  color: var(--text-1);
  font-size: 0.92em;
  background: var(--bg-2);
  padding: 0.8em 1em;
  border-radius: var(--radius-sm);
  border-left: 3px solid var(--red);
  margin: 0.5em 0 1em;
}
.del-warn b { color: var(--red); }
code.mono {
  background: var(--bg-3);
  padding: 0.1em 0.4em;
  border-radius: 4px;
  color: var(--camp);
}
</style>
