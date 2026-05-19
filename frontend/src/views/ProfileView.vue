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
            <span class="k">Email</span>
            <span class="v">
              <span v-if="wallet.me.email">{{ wallet.me.email }}</span>
              <span v-else class="dim">— pas renseigné</span>
            </span>
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

        <!-- Email -->
        <div class="card">
          <div class="card-header">
            <div class="card-title">📧 Mon email</div>
          </div>
          <p class="hint" style="margin-top:0">
            Pour recevoir les confirmations quand Hugo traite tes achats/ventes.
            On ne l'utilisera pas pour autre chose (pas de newsletter, juré).
          </p>

          <div class="field">
            <label class="field-label">Email</label>
            <input
              v-model="emailForm.email"
              type="email"
              placeholder="toi@exemple.com"
              autocomplete="email"
              @keyup.enter="saveEmail"
            />
          </div>

          <button class="btn-primary btn-block" @click="saveEmail" :disabled="savingEmail || !validEmail">
            {{ savingEmail ? 'Enregistrement…' : (wallet.me.email ? 'Mettre à jour' : 'Enregistrer') }}
          </button>

          <div v-if="emailErr" class="alert error">{{ emailErr }}</div>
          <div v-if="emailOk" class="alert success">{{ emailOk }}</div>
        </div>

        <!-- Change password -->
        <div class="card">
          <div class="card-header">
            <div class="card-title">🔒 Changer mon mot de passe</div>
          </div>

          <div class="field">
            <label class="field-label">Mot de passe actuel</label>
            <input v-model="pwdForm.current" type="password" autocomplete="current-password" />
          </div>

          <div class="field">
            <label class="field-label">Nouveau mot de passe</label>
            <input v-model="pwdForm.next" type="password" autocomplete="new-password" />
          </div>

          <div class="field">
            <label class="field-label">Confirmer le nouveau mot de passe</label>
            <input
              v-model="pwdForm.confirm"
              type="password"
              autocomplete="new-password"
              @keyup.enter="submitPwd"
            />
          </div>

          <button class="btn-primary btn-block" @click="submitPwd" :disabled="savingPwd || !canSubmitPwd">
            {{ savingPwd ? 'Modification…' : 'Mettre à jour' }}
          </button>

          <div v-if="pwdErr" class="alert error">{{ pwdErr }}</div>
          <div v-if="pwdOk" class="alert success">{{ pwdOk }}</div>

          <p class="hint">
            Tu seras déconnecté(e) après le changement. Note bien le nouveau mot de passe :
            l'admin peut le reset, pas le récupérer.
          </p>
        </div>

        <!-- Danger zone -->
        <div class="card danger-zone">
          <div class="card-header">
            <div class="card-title">⚠ Zone rouge</div>
          </div>
          <p class="danger-text">
            Tu veux <b>exporter ta clé privée</b> et passer en self-custody ?
            <router-link to="/self-custody">Direction la page MetaMask →</router-link>
          </p>
          <p class="danger-text dim">
            Suppression de compte : seul l'admin peut le faire (et il faut d'abord vider ton solde).
            Si tu veux partir, ping Hugo.
          </p>
        </div>
      </div>
    </main>
  </AppLayout>
</template>

<script setup>
import { reactive, ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '@/components/layout/AppLayout.vue'
import { apiCall } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useWalletStore } from '@/stores/wallet'
import { campToEur, formatEur, formatNum } from '@/config'

const router = useRouter()
const auth = useAuthStore()
const wallet = useWalletStore()

// ─── Email
const emailForm = reactive({ email: '' })
const savingEmail = ref(false)
const emailErr = ref('')
const emailOk = ref('')
const validEmail = computed(() => /\S+@\S+\.\S+/.test(emailForm.email))

watch(() => wallet.me.email, (v) => {
  emailForm.email = v || ''
})

async function saveEmail() {
  emailErr.value = ''
  emailOk.value = ''
  savingEmail.value = true
  try {
    const d = await apiCall('/me/email', {
      method: 'POST',
      token: auth.userToken,
      body: JSON.stringify({ email: emailForm.email })
    })
    wallet.me.email = d.email
    emailOk.value = 'Email enregistré.'
    setTimeout(() => (emailOk.value = ''), 3000)
  } catch (e) {
    emailErr.value = e.message
  } finally {
    savingEmail.value = false
  }
}

// ─── Password
const pwdForm = reactive({ current: '', next: '', confirm: '' })
const savingPwd = ref(false)
const pwdErr = ref('')
const pwdOk = ref('')

const canSubmitPwd = computed(
  () => pwdForm.current && pwdForm.next && pwdForm.next === pwdForm.confirm && pwdForm.next.length >= 4
)

async function submitPwd() {
  pwdErr.value = ''
  pwdOk.value = ''
  if (pwdForm.next !== pwdForm.confirm) {
    pwdErr.value = 'Les deux nouveaux mots de passe ne correspondent pas.'
    return
  }
  savingPwd.value = true
  try {
    await apiCall('/me/password', {
      method: 'POST',
      token: auth.userToken,
      body: JSON.stringify({
        current_password: pwdForm.current,
        new_password: pwdForm.next
      })
    })
    pwdOk.value = 'Mot de passe modifié. Déconnexion…'
    setTimeout(() => {
      auth.logoutUser()
      wallet.reset()
      router.push({ name: 'login' })
    }, 1500)
  } catch (e) {
    pwdErr.value = e.message
  } finally {
    savingPwd.value = false
  }
}

function shortAddr(a) {
  return a ? a.slice(0, 6) + '…' + a.slice(-4) : '—'
}

onMounted(() => {
  if (!wallet.me.username) wallet.refresh()
  else emailForm.email = wallet.me.email || ''
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
.info-row:last-child { border-bottom: none; }
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
.info-row .v.small { font-size: 0.78em; }
.info-row .v a { color: var(--text-0); }
.dim { color: var(--text-3); font-style: italic; }

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
