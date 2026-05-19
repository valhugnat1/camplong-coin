<template>
  <div class="login-wrap">
    <div class="login-card admin">
      <div class="login-logo">
        <div class="logo-mark admin-mark">A</div>
        <div>
          <div class="logo-text">BACKOFFICE</div>
          <div class="sub-brand">admin · camplongcoin</div>
        </div>
      </div>

      <h1 class="login-title">Accès restreint.</h1>
      <p class="login-sub">Tu es l'owner du contrat. Sois prudent.</p>

      <div v-if="redirectInfo" class="alert info" style="font-size:0.88em">
        ↩ Connexion admin requise pour accéder à <span class="mono">{{ redirectInfo }}</span>
      </div>

      <div class="field">
        <label class="field-label">Mot de passe admin</label>
        <input
          v-model="password"
          type="password"
          placeholder="••••••••"
          autocomplete="current-password"
          @keyup.enter="submit"
        />
      </div>

      <button class="btn-primary btn-block" @click="submit" :disabled="loading || !password">
        {{ loading ? 'Connexion…' : 'Connexion admin →' }}
      </button>

      <div v-if="error" class="alert error">{{ error }}</div>

      <div class="footer">
        <router-link to="/login" class="back-link">← Retour à l'app user</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { apiCall } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const password = ref('')
const loading = ref(false)
const error = ref('')

const redirectInfo = computed(() => {
  const r = route.query.redirect
  return r && r !== '/admin' ? String(r) : ''
})

async function submit() {
  error.value = ''
  loading.value = true
  try {
    const d = await apiCall('/admin/login', {
      method: 'POST',
      body: JSON.stringify({ password: password.value })
    })
    auth.setAdminToken(d.token)
    password.value = ''
    const target = String(route.query.redirect || '/admin')
    router.push(target)
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
.login-card.admin::before {
  content: '';
  position: absolute;
  top: -1px;
  left: 50%;
  transform: translateX(-50%);
  width: 60%;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--red), transparent);
}

.admin-mark {
  background: linear-gradient(135deg, #ff4566 0%, #d12d4e 100%) !important;
  box-shadow: 0 4px 20px rgba(255, 69, 102, 0.35) !important;
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

.mono {
  font-family: 'JetBrains Mono', monospace;
}

.footer {
  text-align: center;
  margin-top: 2em;
}
.back-link {
  color: var(--text-2);
  font-size: 0.85em;
  font-weight: 600;
}
.back-link:hover {
  color: var(--camp);
  text-decoration: none;
}
</style>
