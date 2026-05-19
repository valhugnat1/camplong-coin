<template>
  <AdminTopBar :pending-count="ordersStore.pendingCount" />
  <main class="page fade-in">

    <div class="page-header">
      <h1 class="page-title">Backoffice CamplongCoin</h1>
      <p class="page-sub">Crée, crédite, débite. Ton 1 000 000 CAMP n'attend que toi.</p>
    </div>

    <!-- Bandeau demandes en attente -->
    <router-link
      v-if="ordersStore.pendingCount > 0"
      to="/admin/orders"
      class="pending-banner"
    >
      <span class="dot"></span>
      <span class="t">
        <b>{{ ordersStore.pendingCount }} demande{{ ordersStore.pendingCount > 1 ? 's' : '' }} en attente</b>
        — Hugo, t'as du taf.
      </span>
      <span class="arrow">→</span>
    </router-link>

    <TreasuryBox :treasury="treasury" :total-circ-camp="totalCirc" />

    <CreateUserForm @created="loadAll" />

    <div style="margin-top: 1.25em">
      <UsersTable
        :users="users"
        :loading="loadingUsers"
        @refresh="loadAll"
        @tx-success="onTxSuccess"
      />
    </div>

    <div v-if="globalSuccess" class="alert success" style="margin-top: 1em">
      {{ globalSuccess }}
      <div v-if="globalTx" style="margin-top:.4em; font-size:.85em">
        <a :href="'https://sepolia.basescan.org/tx/' + globalTx" target="_blank" rel="noreferrer">
          Voir la tx sur BaseScan →
        </a>
      </div>
    </div>
    <div v-if="globalError" class="alert error" style="margin-top: 1em">{{ globalError }}</div>

  </main>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import AdminTopBar from '@/components/admin/AdminTopBar.vue'
import TreasuryBox from '@/components/admin/TreasuryBox.vue'
import CreateUserForm from '@/components/admin/CreateUserForm.vue'
import UsersTable from '@/components/admin/UsersTable.vue'
import { apiCall } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useOrdersStore } from '@/stores/orders'

const auth = useAuthStore()
const ordersStore = useOrdersStore()

const treasury = ref({ address: '', balance_camp: 0, balance_eth: 0 })
const users = ref([])
const loadingUsers = ref(false)
const globalSuccess = ref('')
const globalTx = ref('')
const globalError = ref('')

const totalCirc = computed(() =>
  users.value.reduce((s, u) => s + Number(u.balance_camp || 0), 0)
)

async function loadAll() {
  loadingUsers.value = true
  globalError.value = ''
  try {
    const [t, u] = await Promise.all([
      apiCall('/admin/treasury', { token: auth.adminToken }),
      apiCall('/admin/users',    { token: auth.adminToken })
    ])
    treasury.value = t
    users.value = u
    // En parallèle on charge aussi les orders pour le compteur (silencieux si erreur)
    ordersStore.load('all').catch(() => {})
  } catch (e) {
    // Les 401 sont gérés globalement par apiCall (auto-logout + redirect).
    globalError.value = e.message
  } finally {
    loadingUsers.value = false
  }
}

function onTxSuccess({ message, tx_hash }) {
  globalSuccess.value = message
  globalTx.value = tx_hash
  setTimeout(() => { globalSuccess.value = ''; globalTx.value = '' }, 8000)
}

onMounted(loadAll)
</script>

<style scoped>
.pending-banner {
  display: flex;
  align-items: center;
  gap: 0.7em;
  padding: 0.9em 1.2em;
  background: linear-gradient(135deg, rgba(255, 122, 0, 0.15), rgba(255, 122, 0, 0.05));
  border: 1px solid rgba(255, 122, 0, 0.3);
  border-radius: var(--radius);
  margin-bottom: 1.25em;
  text-decoration: none;
  color: var(--text-0);
  transition: transform 0.15s, border-color 0.15s;
}
.pending-banner:hover {
  border-color: var(--camp);
  text-decoration: none;
  transform: translateX(2px);
}
.pending-banner .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--camp);
  box-shadow: 0 0 10px var(--camp);
  animation: pulse 1.4s infinite;
}
.pending-banner .t { flex: 1; }
.pending-banner .t b { color: var(--camp); }
.pending-banner .arrow {
  font-size: 1.2em;
  color: var(--camp);
}
</style>
