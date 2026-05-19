<template>
  <div class="card">
    <div class="card-header">
      <div class="card-title">+ Créer un nouveau user</div>
      <span class="hint">1 clic, le user reçoit ses CAMP directement</span>
    </div>

    <div class="form-row">
      <input v-model="form.username" placeholder="pseudo (ex: Charles)" />
      <input v-model="form.user_password" type="text" placeholder="mot de passe initial" />
      <input v-model="form.email" type="email" placeholder="email (optionnel)" />
      <input v-model.number="form.initial_camp" type="number" min="0" placeholder="CAMP initial" />
      <button class="btn-primary" @click="submit" :disabled="creating || !canCreate">
        {{ creating ? 'Création…' : 'Créer' }}
      </button>
    </div>

    <p class="footer-hint">
      Plus besoin d'ETH côté user : la treasury paie tout le gas via <span class="mono">adminTransfer</span>.
      L'email permet au user de recevoir les confirmations de demandes d'achat/vente.
    </p>

    <div v-if="success" class="alert success">
      {{ success }}
      <div v-if="lastTx" style="margin-top:.4em; font-size:.85em">
        <a :href="'https://sepolia.basescan.org/tx/' + lastTx" target="_blank" rel="noreferrer">
          Voir la tx sur BaseScan →
        </a>
      </div>
    </div>
    <div v-if="error" class="alert error">{{ error }}</div>
  </div>
</template>

<script setup>
import { reactive, ref, computed } from 'vue'
import { apiCall } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const emit = defineEmits(['created'])
const auth = useAuthStore()

const form = reactive({ username: '', user_password: '', email: '', initial_camp: 0 })
const creating = ref(false)
const error = ref('')
const success = ref('')
const lastTx = ref('')

const canCreate = computed(
  () =>
    form.username &&
    form.user_password &&
    form.initial_camp != null &&
    form.initial_camp >= 0
)

async function submit() {
  error.value = ''
  success.value = ''
  lastTx.value = ''
  creating.value = true
  try {
    const payload = { ...form }
    if (!payload.email) delete payload.email  // évite envoyer une string vide
    const d = await apiCall('/admin/users', {
      method: 'POST',
      token: auth.adminToken,
      body: JSON.stringify(payload)
    })
    success.value = `User « ${d.username} » créé. Adresse ${d.address}`
    lastTx.value = d.camp_tx
    form.username = ''
    form.user_password = ''
    form.email = ''
    form.initial_camp = 0
    emit('created')
  } catch (e) {
    error.value = e.message
  } finally {
    creating.value = false
  }
}
</script>

<style scoped>
.hint {
  color: var(--text-3);
  font-size: 0.82em;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr auto auto;
  gap: 0.6em;
}
.form-row input { min-width: 0; }
.form-row input[type=number] { width: 140px; }

.footer-hint {
  color: var(--text-3);
  font-size: 0.85em;
  margin: 0.6em 0 0 0;
}
.mono {
  font-family: 'JetBrains Mono', monospace;
  color: var(--text-1);
}

@media (max-width: 920px) {
  .form-row { grid-template-columns: 1fr 1fr; }
  .form-row input[type=number] { width: 100%; }
}
@media (max-width: 540px) {
  .form-row { grid-template-columns: 1fr; }
}
</style>
