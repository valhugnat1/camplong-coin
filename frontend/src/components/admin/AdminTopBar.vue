<template>
  <div class="admin-topbar">
    <div class="admin-topbar-inner">
      <router-link to="/admin" class="brand">
        <div class="logo-mark admin-mark">A</div>
        <span class="logo-text">BACKOFFICE</span>
        <span class="brand-tag">admin</span>
      </router-link>

      <nav class="nav">
        <router-link
          to="/admin"
          class="nav-link"
          :class="{ active: $route.path === '/admin' }"
        >
          🏠 Vue d'ensemble
        </router-link>
        <router-link
          to="/admin/orders"
          class="nav-link"
          :class="{ active: $route.path === '/admin/orders' }"
        >
          📋 Demandes
          <span v-if="pendingCount > 0" class="badge">{{ pendingCount }}</span>
        </router-link>
        <router-link
          to="/admin/bets"
          class="nav-link"
          :class="{ active: $route.path.startsWith('/admin/bets') }"
        >
          🎲 Paris
        </router-link>
        <router-link
          to="/admin/casino"
          class="nav-link"
          :class="{ active: $route.path.startsWith('/admin/casino') }"
        >
          🪙 Casino
        </router-link>
        <router-link
          to="/admin/milk"
          class="nav-link"
          :class="{ active: $route.path.startsWith('/admin/milk') }"
        >
          🥛 Lait
        </router-link>
      </nav>

      <div class="spacer"></div>

      <router-link to="/wallet" class="link-back">← Vue user</router-link>

      <button class="user-chip" @click="logout">
        <span style="color: var(--text-1)">Logout admin</span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";

defineProps({
  pendingCount: { type: Number, default: 0 },
});

const router = useRouter();
const auth = useAuthStore();

function logout() {
  auth.logoutAdmin();
  router.push({ name: "admin-login" });
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
  gap: 1em;
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

.nav {
  display: flex;
  gap: 0.3em;
}
.nav-link {
  padding: 0.5em 0.9em;
  border-radius: var(--radius-sm);
  color: var(--text-2);
  text-decoration: none;
  font-size: 0.92em;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 0.4em;
  transition:
    color 0.15s,
    background 0.15s;
}
.nav-link:hover {
  color: var(--text-0);
  background: var(--bg-2);
  text-decoration: none;
}
.nav-link.active {
  color: white;
  background: var(--bg-3);
}

.badge {
  background: var(--camp);
  color: white;
  border-radius: 999px;
  font-size: 0.7em;
  padding: 0.05em 0.5em;
  font-weight: 700;
  min-width: 1.2em;
  text-align: center;
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

@media (max-width: 760px) {
  .admin-topbar-inner {
    padding: 0.7em 0.8em;
    flex-wrap: wrap;
    row-gap: 0.5em;
  }
  .brand .logo-text {
    display: none;
  }
  .link-back {
    display: none;
  }
  .nav-link {
    padding: 0.4em 0.6em;
    font-size: 0.85em;
  }
}
</style>
