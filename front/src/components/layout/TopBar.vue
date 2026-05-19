<template>
  <div class="topbar-inner">
    <router-link to="/wallet" class="brand">
      <div class="logo-mark">C</div>
      <span class="logo-text">CAMPLONGCOIN</span>
      <span class="brand-tag">beta</span>
    </router-link>

    <div class="spacer"></div>

    <div v-if="wallet.me.username" class="balance-pill">
      <span class="dot"></span>
      <span class="amount mono">{{ formatNum(wallet.me.balance) }}</span>
      <span class="currency">CAMP</span>
    </div>

    <button class="user-chip" @click="logout" :title="'Logout ' + (wallet.me.username || '')">
      <span class="username">{{ wallet.me.username || '—' }}</span>
      <span class="avatar">{{ initial }}</span>
    </button>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useWalletStore } from '@/stores/wallet'

const router = useRouter()
const auth = useAuthStore()
const wallet = useWalletStore()

const initial = computed(() => (wallet.me.username || '?').slice(0, 1).toUpperCase())

function formatNum(n) {
  if (n == null) return '0'
  return Number(n).toLocaleString('fr-FR')
}

function logout() {
  auth.logoutUser()
  wallet.reset()
  router.push({ name: 'login' })
}
</script>

<style scoped>
.topbar-inner {
  max-width: var(--max);
  margin: 0 auto;
  padding: 0.85em 1.25em;
  display: flex;
  align-items: center;
  gap: 0.8em;
}

.brand {
  display: flex;
  align-items: center;
  gap: 0.6em;
  text-decoration: none;
  color: inherit;
}
.brand:hover {
  text-decoration: none;
}
.brand .logo-mark {
  width: 32px;
  height: 32px;
  font-size: 1em;
}
.brand .logo-text {
  font-size: 1.1em;
}

.brand-tag {
  background: var(--camp-soft);
  color: var(--camp);
  padding: 0.15em 0.5em;
  border-radius: 4px;
  font-size: 0.65em;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.spacer {
  flex: 1;
}

.balance-pill {
  display: flex;
  align-items: center;
  gap: 0.5em;
  padding: 0.5em 0.9em;
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: 999px;
  font-size: 0.92em;
}
.balance-pill .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--green);
  box-shadow: 0 0 8px var(--green);
  animation: pulse 2s ease-in-out infinite;
}
.balance-pill .amount {
  font-weight: 600;
}
.balance-pill .currency {
  color: var(--text-2);
  font-size: 0.85em;
}

.user-chip {
  display: flex;
  align-items: center;
  gap: 0.5em;
  padding: 0.4em 0.5em 0.4em 0.85em;
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: 999px;
  cursor: pointer;
  font-size: 0.9em;
  color: var(--text-1);
}
.user-chip:hover {
  border-color: var(--border-strong);
  color: var(--text-0);
}
.avatar {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--violet), var(--camp));
  display: grid;
  place-items: center;
  color: white;
  font-weight: 700;
  font-size: 0.7em;
}

@media (max-width: 640px) {
  .topbar-inner { padding: 0.7em 1em; }
  .brand .logo-text { display: none; }
  .balance-pill .currency { display: none; }
  .username { display: none; }
}
</style>
