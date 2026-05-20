<template>
  <div class="login-wrap">

    <!-- Coin low-poly en background, tourne sur son axe vertical -->
    <div class="bg-coin-wrap" aria-hidden="true">
      <div class="bg-coin-rotor">
        <svg
          class="bg-coin"
          viewBox="-100 -100 200 200"
          xmlns="http://www.w3.org/2000/svg"
        >
          <defs>
            <linearGradient id="face-lite" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%"  stop-color="#ff9a3d" />
              <stop offset="100%" stop-color="#ff7a00" />
            </linearGradient>
            <linearGradient id="face-mid" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%"  stop-color="#ff7a00" />
              <stop offset="100%" stop-color="#d35a00" />
            </linearGradient>
            <linearGradient id="face-dark" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%"  stop-color="#c44d00" />
              <stop offset="100%" stop-color="#7a2e00" />
            </linearGradient>
            <linearGradient id="face-rim" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%"  stop-color="#ff7a00" />
              <stop offset="50%" stop-color="#c44d00" />
              <stop offset="100%" stop-color="#5c2400" />
            </linearGradient>
            <linearGradient id="c-lite" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%"  stop-color="#fff8ee" />
              <stop offset="100%" stop-color="#ffe5c4" />
            </linearGradient>
            <linearGradient id="c-mid" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%"  stop-color="#ffe5c4" />
              <stop offset="100%" stop-color="#ffcc94" />
            </linearGradient>
            <linearGradient id="c-dark" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%"  stop-color="#ffcc94" />
              <stop offset="100%" stop-color="#ffa564" />
            </linearGradient>
          </defs>

          <!-- Tranche visible (épaisseur de la pièce) -->
          <ellipse cx="0" cy="6" rx="78" ry="78" fill="url(#face-rim)" opacity="0.7" />

          <!-- 16 facettes triangulaires -->
          <polygon points="0,0  0,-78  29.85,-72.05"        fill="url(#face-lite)" />
          <polygon points="0,0  29.85,-72.05  55.15,-55.15" fill="url(#face-lite)" />
          <polygon points="0,0  55.15,-55.15  72.05,-29.85" fill="url(#face-mid)" />
          <polygon points="0,0  72.05,-29.85  78,0"          fill="url(#face-mid)" />
          <polygon points="0,0  78,0  72.05,29.85"           fill="url(#face-mid)" />
          <polygon points="0,0  72.05,29.85  55.15,55.15"    fill="url(#face-dark)" />
          <polygon points="0,0  55.15,55.15  29.85,72.05"    fill="url(#face-dark)" />
          <polygon points="0,0  29.85,72.05  0,78"           fill="url(#face-dark)" />
          <polygon points="0,0  0,78  -29.85,72.05"          fill="url(#face-dark)" />
          <polygon points="0,0  -29.85,72.05  -55.15,55.15"  fill="url(#face-dark)" />
          <polygon points="0,0  -55.15,55.15  -72.05,29.85"  fill="url(#face-mid)" />
          <polygon points="0,0  -72.05,29.85  -78,0"          fill="url(#face-mid)" />
          <polygon points="0,0  -78,0  -72.05,-29.85"         fill="url(#face-mid)" />
          <polygon points="0,0  -72.05,-29.85  -55.15,-55.15" fill="url(#face-lite)" />
          <polygon points="0,0  -55.15,-55.15  -29.85,-72.05" fill="url(#face-lite)" />
          <polygon points="0,0  -29.85,-72.05  0,-78"          fill="url(#face-lite)" />

          <!-- Anneau périphérique -->
          <circle cx="0" cy="0" r="78" fill="none" stroke="#5c2400" stroke-width="0.6" opacity="0.5" />

          <!-- C low-poly -->
          <polygon points="-35,-40  20,-40  28,-32  -18,-32" fill="url(#c-lite)" />
          <polygon points="-18,-32  28,-32  22,-20  -22,-20" fill="url(#c-lite)" />
          <polygon points="-22,-20  22,-20  10,-12  -22,-12" fill="url(#c-mid)" />
          <polygon points="-35,-40  -18,-32  -22,-20  -42,-28" fill="url(#c-mid)" />
          <polygon points="-42,-28  -22,-20  -22,-12  -48,-15" fill="url(#c-dark)" />
          <polygon points="-48,-15  -22,-12  -22,0   -50,0"    fill="url(#c-dark)" />
          <polygon points="-50,0    -22,0   -22,12   -48,15"   fill="url(#c-dark)" />
          <polygon points="-48,15   -22,12  -22,20   -42,28"   fill="url(#c-mid)" />
          <polygon points="-42,28   -22,20  -18,32   -35,40"   fill="url(#c-mid)" />
          <polygon points="-22,12   10,12  22,20   -22,20"  fill="url(#c-mid)" />
          <polygon points="-22,20   22,20  28,32   -18,32"  fill="url(#c-lite)" />
          <polygon points="-18,32   28,32  20,40   -35,40"  fill="url(#c-lite)" />
        </svg>
      </div>

      <!-- Halo statique derrière -->
      <div class="bg-coin-glow"></div>
    </div>

    <!-- Login card -->
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

      <div v-if="redirectInfo" class="alert info" style="font-size:0.88em">
        ↩ Connexion requise pour accéder à <span class="mono">{{ redirectInfo }}</span>
      </div>

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
import { reactive, ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { apiCall } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useWalletStore } from '@/stores/wallet'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const wallet = useWalletStore()

const form = reactive({ username: '', password: '' })
const loading = ref(false)
const error = ref('')

const redirectInfo = computed(() => {
  const r = route.query.redirect
  return r && r !== '/wallet' ? String(r) : ''
})

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
    const target = String(route.query.redirect || '/wallet')
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
  position: relative;
  overflow: hidden;
}

/* ─── Coin background : wrapper centré, taille fixe ─── */
.bg-coin-wrap {
  position: absolute;
  top: 50%;
  left: 50%;
  /* Centre PARFAITEMENT au milieu de l'écran */
  transform: translate(-50%, -50%);
  width: min(80vmin, 720px);
  height: min(80vmin, 720px);
  z-index: 0;
  pointer-events: none;
  /* perspective sur le parent pour que rotateY ait du volume */
  perspective: 1400px;
  perspective-origin: 50% 50%;
}

/* Halo orange statique derrière la pièce */
.bg-coin-glow {
  position: absolute;
  inset: 0;
  background: radial-gradient(
    circle at 50% 50%,
    rgba(255, 122, 0, 0.20) 0%,
    rgba(255, 122, 0, 0.05) 35%,
    transparent 65%
  );
  pointer-events: none;
}

/* Le rotor applique la rotation 3D autour de Y, c'est lui qui "tourne" */
.bg-coin-rotor {
  position: absolute;
  inset: 0;
  transform-style: preserve-3d;
  animation: coin-spin 16s linear infinite;
  /* Origine bien centrée verticalement et horizontalement */
  transform-origin: 50% 50%;
}

.bg-coin {
  width: 100%;
  height: 100%;
  opacity: 0.28;          /* semi-transparent pour rester en background */
  filter: drop-shadow(0 30px 60px rgba(255, 122, 0, 0.25));
  display: block;
}

@keyframes coin-spin {
  from { transform: rotateY(0deg);   }
  to   { transform: rotateY(360deg); }
}

@media (prefers-reduced-motion: reduce) {
  .bg-coin-rotor { animation: none; }
}

/* ─── Card login (devant le coin) ─── */
.login-card {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 420px;
  background: linear-gradient(180deg, rgba(19, 19, 26, 0.88) 0%, rgba(13, 13, 18, 0.94) 100%);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 2.5em 2em;
  overflow: hidden;
  box-shadow:
    0 20px 60px -20px rgba(0, 0, 0, 0.75),
    0 0 0 1px rgba(255, 255, 255, 0.02) inset;
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

.mono {
  font-family: 'JetBrains Mono', monospace;
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
