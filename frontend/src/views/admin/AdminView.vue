<template>
  <AdminTopBar />
  <main class="page fade-in">

    <div class="page-header">
      <h1 class="page-title">Backoffice CamplongCoin</h1>
      <p class="page-sub">Crée, crédite, débite. Ton 1 000 000 CAMP n'attend que toi.</p>
    </div>

    <TreasuryBox :treasury="treasury" />

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
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AdminTopBar from '@/components/admin/AdminTopBar.vue'
import TreasuryBox from '@/components/admin/TreasuryBox.vue'
import CreateUserForm from '@/components/admin/CreateUserForm.vue'
import UsersTable from '@/components/admin/UsersTable.vue'
import { apiCall } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const treasury = ref({ address: '', balance_camp: 0, balance_eth: 0 })
const users = ref([])
const loadingUsers = ref(false)
const globalSuccess = ref('')
const globalTx = ref('')
const globalError = ref('')

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
  } catch (e) {
    if (/401|Token|invalid/i.test(String(e.message))) {
      auth.logoutAdmin()
      router.push({ name: 'admin-login' })
    } else {
      globalError.value = e.message
    }
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
