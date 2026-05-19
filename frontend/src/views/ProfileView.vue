<template>
  <AppLayout>
    <main class="page fade-in">
      <div class="page-header">
        <h1 class="page-title">Mon profil</h1>
        <p class="page-sub">{{ wallet.me.username }} · {{ shortAddr(wallet.me.address) }}</p>
      </div>

      <div class="grid">
        <!-- Infos -->
        <div class="card">
          <div class="card-header">
            <div class="card-title">📇 Mes infos</div>
          </div>
          <div class="info-row">
            <span class="k">Pseudo</span>
            <span class="v">{{ wallet.me.username }}</span>
          </div>
          <div class="info-row">
            <span class="k">Solde</span>
            <span class="v mono">{{ formatNum(wallet.me.balance) }} CAMP</span>
          </div>
          <div class="info-row">
            <span class="k">Valeur</span>
            <span class="v mono">{{ formatEur(campToEur(wallet.me.balance)) }}</span>
          </div>
          <div class="info-row">
            <span class="k">Adresse</span>
            <span class="v mono small">
              <a :href="'https://sepolia.basescan.org/address/' + wallet.me.address" target="_blank" rel="noreferrer">
                {{ wallet.me.address }}
              </a>
            </span>
          </div>
        </div>

        <!-- Change password -->
        <div class="card">
          <div class="card-header">
            <div class="card-title">🔒 Changer mon mot de passe</div>
          </div>

          <div class="field">
            <label class="field-label">Mot de passe actuel</label>
            <input v-model="form.current" type="password" autocomplete="current-password" />
          </div>

          <div class="field">
            <label class="field-label">Nouveau mot de passe</label>
            <input v-model="form.next" type="password" autocomplete="new-password" />
          </div>

          <div class="field">
            <label class="field-label">Confirmer le nouveau mot de passe</label>
            <input
              v-model="form.confirm"
              type="password"
              autocomplete="new-password"
              @keyup.enter="submit"
            />
          </div>

          <button class="btn-primary btn-block" @click="submit" :disabled="saving || !canSubmit">
            {{ saving ? 'Modification…' : 'Mettre à jour' }}
          </button>

          <div v-if="error" class="alert error">{{ error }}</div>
          <div v-if="success" class="alert success">{{ success }}</div>

          <p class="hint">
            Si tu changes ton mot de passe, tu seras déconnecté(e) automatiquement.
            Note bien le nouveau, l'admin ne peut pas le récupérer (juste le reset).
          </p>
        </div>

        <!-- Danger zone (placeholder) -->
        <div class="card danger-zone">
          <div class="card-header">
            <div class="card-title">⚠ Zone rouge</div>
          </div>
          <p class="danger-text">
            Tu veux <b>exporter ta clé privée</b> et passer en self-custody ?
            <router-link to="/self-custody">Direction la page MetaMask →</router-link>
          </p>
          <p class="danger-text dim">
            Suppression de compte : pas dispo. Si tu pars, demande à Hugo de te débiter tout ton solde, c'est l'équivalent.
          </p>
        </div>
      </div>
    </main>
  </AppLayout>
</template>

<script setup>
import { reactive, ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '@/components/layout/AppLayout.vue'
import { apiCall } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useWalletStore } from '@/stores/wallet'
import { campToEur, formatEur, formatNum } from '@/config'

const router = useRouter()
const auth = useAuthStore()
const wallet = useWalletStore()

const form = reactive({ current: '', next: '', confirm: '' })
const saving = ref(false)
const error = ref('')
const success = ref('')

const canSubmit = computed(
  () => form.current && form.next && form.next === form.confirm && form.next.length >= 4
)

function shortAddr(a) {
  return a ? a.slice(0, 6) + '…' + a.slice(-4) : '—'
}

async function submit() {
  error.value = ''
  success.value = ''
  if (form.next !== form.confirm) {
    error.value = 'Les deux nouveaux mots de passe ne correspondent pas.'
    return
  }
  saving.value = true
  try {
    // Endpoint à implémenter côté back : POST /me/password
    // Payload : { current_password, new_password }
    await apiCall('/me/password', {
      method: 'POST',
      token: auth.userToken,
      body: JSON.stringify({
        current_password: form.current,
        new_password: form.next
      })
    })
    success.value = 'Mot de passe modifié. Tu vas être déconnecté(e)…'
    setTimeout(() => {
      auth.logoutUser()
      wallet.reset()
      router.push({ name: 'login' })
    }, 1500)
  } catch (e) {
    // Si endpoint pas encore implémenté
    if (/404|Not Found/i.test(e.message)) {
      error.value =
        "L'endpoint /me/password n'existe pas encore côté back. À implémenter (POST avec { current_password, new_password })."
    } else {
      error.value = e.message
    }
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  if (!wallet.me.username) wallet.refresh()
})
</script>

<style scoped>
.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.25em;
}
.grid > .card:last-child {
  grid-column: 1 / -1;
}
@media (max-width: 880px) {
  .grid { grid-template-columns: 1fr; }
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 0.6em 0;
  border-bottom: 1px solid var(--border);
  gap: 1em;
}
.info-row:last-child {
  border-bottom: none;
}
.info-row .k {
  color: var(--text-2);
  font-size: 0.85em;
  flex-shrink: 0;
}
.info-row .v {
  text-align: right;
  font-weight: 500;
  min-width: 0;
  word-break: break-all;
}
.info-row .v.small {
  font-size: 0.78em;
}
.info-row .v a {
  color: var(--text-0);
}

.hint {
  color: var(--text-3);
  font-size: 0.82em;
  margin-top: 0.8em;
  font-style: italic;
}

.danger-zone {
  border-color: rgba(255, 69, 102, 0.2);
  background: linear-gradient(180deg, rgba(255, 69, 102, 0.04), var(--bg-1));
}
.danger-text {
  color: var(--text-1);
  font-size: 0.92em;
  margin: 0.4em 0;
}
.danger-text.dim {
  color: var(--text-2);
  font-size: 0.85em;
  font-style: italic;
}
</style>
