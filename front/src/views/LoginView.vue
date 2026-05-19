<template>
  <div class="login-wrap">
    <div class="login-card">
      <div class="login-logo">
        <div class="logo-mark">C</div>
        <div>
          <div class="logo-text">CAMPLONGCOIN</div>
          <div class="sub-brand">base sepolia · custodial</div>
        </div>
      </div>

      <h1 class="login-title">Bienvenue,<br />futur millionnaire.</h1>
      <p class="login-sub">
        Connecte-toi pour accéder à ton wallet.
        <b>Ton 9-to-5 ne sait pas encore ce qui l'attend.</b>
      </p>

      <div class="field">
        <label class="field-label">Pseudo</label>
        <input
          v-model="form.username"
          placeholder="ex: Hugo"
          autocomplete="username"
          @keyup.enter="submit"
        />
      </div>

      <div class="field">
        <label class="field-label">Mot de passe</label>
        <input
          v-model="form.password"
          type="password"
          placeholder="••••••••"
          autocomplete="current-password"
          @keyup.enter="submit"
        />
      </div>

      <button class="btn-primary btn-block" @click="submit" :disabled="loading">
        {{ loading ? 'Connexion…' : 'Entrer dans le CAMP →' }}
      </button>

      <div v-if="error" class="alert error">{{ error }}</div>

      <div class="footer">
        <span>Pas de compte&nbsp;? Demande à l'admin. C'est encore artisanal.</span>
        <router-link to="/admin/login" class="admin-link">Accès admin →</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { apiCall } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useWalletStore } from '@/stores/wallet'

const router = useRouter()
const auth = useAuthStore()
const wallet = useWalletStore()

const form = reactive({ username: '', password: '' })
const loading = ref(false)
const error = ref('')

async function submit() {
  error.value = ''
  loading.value = true
  try {
    const d = await apiCall('/login', {
      method: 'POST',
      body: JSON.stringify(form)
    })
    auth.setUserToken(d.token)
    await wallet.refresh()
    router.push({ name: 'wallet' })
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2em 1em;
}

.login-card {
  width: 100%;
  max-width: 420px;
  background: linear-gradient(180deg, var(--bg-2) 0%, var(--bg-1) 100%);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 2.5em 2em;
  position: relative;
  overflow: hidden;
}
.login-card::before {
  content: '';
  position: absolute;
  top: -1px;
  left: 50%;
  transform: translateX(-50%);
  width: 60%;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--camp), transparent);
}

.login-logo {
  display: flex;
  align-items: center;
  gap: 0.6em;
  margin-bottom: 1.5em;
}
.sub-brand {
  color: var(--text-3);
  font-size: 0.78em;
  letter-spacing: 0.05em;
}

.login-title {
  font-size: 2em;
  margin-bottom: 0.3em;
  line-height: 1.1;
}
.login-sub {
  color: var(--text-2);
  font-size: 0.95em;
  margin-bottom: 2em;
}
.login-sub b {
  color: var(--camp);
  font-weight: 600;
}

.footer {
  text-align: center;
  color: var(--text-3);
  font-size: 0.78em;
  margin-top: 2em;
  display: flex;
  flex-direction: column;
  gap: 0.5em;
}
.admin-link {
  color: var(--text-2);
  font-weight: 600;
}
.admin-link:hover {
  color: var(--camp);
  text-decoration: none;
}
</style>
