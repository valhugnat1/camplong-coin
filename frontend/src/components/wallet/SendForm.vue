<template>
  <div class="card send-card">
    <div class="card-header">
      <div class="card-title">💸 Envoyer des CAMP</div>
      <span class="hint">Gratuit, la treasury paie le gas (merci patron)</span>
    </div>

    <div class="field">
      <label class="field-label">Destinataire</label>
      <select v-model="form.to_username">
        <option value="" disabled>— choisir un pote —</option>
        <option v-for="u in users" :key="u.username" :value="u.username">
          {{ u.username }}
        </option>
      </select>
    </div>

    <label class="field-label">Montant</label>
    <div class="amount-wrap">
      <input v-model.number="form.amount" type="number" min="1" placeholder="0" />
      <span class="amount-currency">CAMP</span>
    </div>
    <div class="quick">
      <button @click="form.amount = 10">+10</button>
      <button @click="form.amount = 50">+50</button>
      <button @click="form.amount = 100">+100</button>
      <button @click="form.amount = Math.floor((balance || 0) / 2)">50%</button>
      <button @click="form.amount = balance">MAX</button>
    </div>

    <div class="field">
      <label class="field-label">Note (optionnel)</label>
      <input v-model="form.note" placeholder="ex: bière, raclette, dette de poker…" maxlength="120" />
    </div>

    <button class="btn-primary btn-block" @click="submit" :disabled="sending || !canSend">
      {{ sending ? 'Envoi on-chain…' : `Envoyer ${form.amount || ''} CAMP` }}
    </button>

    <div v-if="success" class="alert success">
      {{ success }}
      <div v-if="lastTxHash" style="margin-top:.4em; font-size:.85em">
        <a :href="'https://sepolia.basescan.org/tx/' + lastTxHash" target="_blank" rel="noreferrer">
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
import { useWalletStore } from '@/stores/wallet'

const props = defineProps({
  users: { type: Array, required: true },
  balance: { type: Number, default: 0 }
})

const auth = useAuthStore()
const wallet = useWalletStore()

const form = reactive({ to_username: '', amount: 0, note: '' })
const sending = ref(false)
const error = ref('')
const success = ref('')
const lastTxHash = ref('')

const canSend = computed(() => form.to_username && form.amount > 0)

async function submit() {
  error.value = ''
  success.value = ''
  lastTxHash.value = ''
  sending.value = true
  try {
    const d = await apiCall('/transfer', {
      method: 'POST',
      token: auth.userToken,
      body: JSON.stringify(form)
    })
    lastTxHash.value = d.tx_hash
    success.value = `Envoyé ! Nouveau solde : ${d.new_balance} CAMP. Tu te rapproches.`
    form.amount = 0
    form.note = ''
    form.to_username = ''
    await wallet.refresh()
  } catch (e) {
    error.value = e.message
  } finally {
    sending.value = false
  }
}
</script>

<style scoped>
.hint {
  color: var(--text-3);
  font-size: 0.82em;
}

.amount-wrap {
  position: relative;
  margin-bottom: 0.9em;
}
.amount-wrap input {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-size: 1.8em;
  font-weight: 700;
  padding: 0.6em 4em 0.6em 0.6em;
  letter-spacing: -0.02em;
  background: var(--bg-2);
}
.amount-currency {
  position: absolute;
  right: 1em;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-2);
  font-weight: 600;
  pointer-events: none;
  font-size: 0.95em;
}

.quick {
  display: flex;
  gap: 0.4em;
  margin-top: -0.4em;
  margin-bottom: 0.9em;
  flex-wrap: wrap;
}
.quick button {
  padding: 0.35em 0.7em;
  background: var(--bg-2);
  color: var(--text-1);
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 0.8em;
}
.quick button:hover {
  background: var(--bg-3);
  color: var(--text-0);
}
</style>
