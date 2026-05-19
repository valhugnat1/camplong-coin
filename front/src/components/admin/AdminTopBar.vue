<template>
  <div class="admin-topbar">
    <div class="admin-topbar-inner">
      <div class="brand">
        <div class="logo-mark admin-mark">A</div>
        <span class="logo-text">BACKOFFICE</span>
        <span class="brand-tag">admin</span>
      </div>

      <div class="spacer"></div>

      <router-link to="/wallet" class="link-back">← Vue user</router-link>

      <button class="user-chip" @click="logout">
        <span style="color: var(--text-1)">Logout admin</span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

function logout() {
  auth.logoutAdmin()
  router.push({ name: 'admin-login' })
}
</script>

<style scoped>
.admin-topbar {
  position: sticky;
  top: 0;
  z-index: 50;
  background: rgba(7, 7, 10, 0.85);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--border);
}

.admin-topbar-inner {
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
}
.brand .logo-mark {
  width: 32px;
  height: 32px;
  font-size: 1em;
}
.brand .logo-text {
  font-size: 1.1em;
}

.admin-mark {
  background: linear-gradient(135deg, #ff4566 0%, #d12d4e 100%) !important;
  box-shadow: 0 4px 20px rgba(255, 69, 102, 0.35) !important;
}

.brand-tag {
  background: var(--red-soft);
  color: var(--red);
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

.link-back {
  color: var(--text-2);
  font-size: 0.85em;
  font-weight: 600;
}
.link-back:hover {
  color: var(--camp);
  text-decoration: none;
}

.user-chip {
  display: flex;
  align-items: center;
  gap: 0.5em;
  padding: 0.4em 0.85em;
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: 999px;
  cursor: pointer;
  font-size: 0.85em;
}
.user-chip:hover {
  border-color: var(--border-strong);
}

@media (max-width: 640px) {
  .admin-topbar-inner { padding: 0.7em 1em; }
  .brand .logo-text { display: none; }
  .link-back { display: none; }
}
</style>
