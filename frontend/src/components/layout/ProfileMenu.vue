<template>
  <div class="profile-menu" ref="root">
    <button class="user-chip" :class="{ active: open }" @click="open = !open">
      <span class="username">{{ wallet.me.username || '—' }}</span>
      <span class="avatar">{{ initial }}</span>
      <span class="caret" :class="{ open }">▾</span>
    </button>

    <transition name="drop">
      <div v-if="open" class="dropdown" @click.stop>
        <div class="dropdown-header">
          <div class="username-big">{{ wallet.me.username || '—' }}</div>
          <div class="addr mono" :title="wallet.me.address">
            {{ shortAddr(wallet.me.address) }}
          </div>
        </div>

        <div class="divider"></div>

        <button class="item" @click="go('/profile')">
          <span class="ico">👤</span>
          <div class="txt">
            <div class="t">Mon profil</div>
            <div class="s">Email, mot de passe</div>
          </div>
        </button>

        <button class="item" @click="go('/orders')">
          <span class="ico">📋</span>
          <div class="txt">
            <div class="t">Mes demandes</div>
            <div class="s">Historique des achats/ventes</div>
          </div>
        </button>

        <button class="item" @click="go('/self-custody')">
          <span class="ico">🦊</span>
          <div class="txt">
            <div class="t">Connecter à MetaMask</div>
            <div class="s">Récupérer ma clé · self-custody</div>
          </div>
        </button>

        <button class="item" @click="go('/buy')">
          <span class="ico">💶</span>
          <div class="txt">
            <div class="t">Acheter / Vendre du CAMP</div>
            <div class="s">10 € = 950 CAMP</div>
          </div>
        </button>

        <div class="divider"></div>

        <button class="item logout" @click="logout">
          <span class="ico">🚪</span>
          <div class="txt">
            <div class="t">Déconnexion</div>
          </div>
        </button>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useWalletStore } from '@/stores/wallet'

const router = useRouter()
const auth = useAuthStore()
const wallet = useWalletStore()

const open = ref(false)
const root = ref(null)

const initial = computed(() => (wallet.me.username || '?').slice(0, 1).toUpperCase())

function shortAddr(a) {
  return a ? a.slice(0, 6) + '…' + a.slice(-4) : '—'
}

function go(path) {
  open.value = false
  router.push(path)
}

function logout() {
  open.value = false
  auth.logoutUser()
  wallet.reset()
  router.push({ name: 'login' })
}

function onDocClick(e) {
  if (!open.value) return
  if (root.value && !root.value.contains(e.target)) open.value = false
}
function onKey(e) {
  if (e.key === 'Escape') open.value = false
}

onMounted(() => {
  document.addEventListener('click', onDocClick)
  document.addEventListener('keydown', onKey)
})
onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick)
  document.removeEventListener('keydown', onKey)
})
</script>

<style scoped>
.profile-menu { position: relative; }

.user-chip {
  display: flex;
  align-items: center;
  gap: 0.5em;
  padding: 0.4em 0.7em 0.4em 0.85em;
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: 999px;
  cursor: pointer;
  font-size: 0.9em;
  color: var(--text-1);
}
.user-chip:hover, .user-chip.active {
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
.caret {
  font-size: 0.7em;
  color: var(--text-2);
  transition: transform 0.2s;
}
.caret.open { transform: rotate(180deg); }

.dropdown {
  position: absolute;
  top: calc(100% + 0.6em);
  right: 0;
  min-width: 280px;
  background: var(--bg-1);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius);
  padding: 0.5em;
  z-index: 100;
  box-shadow: 0 12px 40px -8px rgba(0, 0, 0, 0.6);
}
.drop-enter-active, .drop-leave-active {
  transition: opacity 0.15s, transform 0.15s;
  transform-origin: top right;
}
.drop-enter-from, .drop-leave-to {
  opacity: 0;
  transform: scale(0.95) translateY(-4px);
}

.dropdown-header { padding: 0.7em 0.8em 0.4em; }
.username-big { font-weight: 700; font-size: 1em; }
.addr { font-size: 0.78em; color: var(--text-2); margin-top: 0.15em; }
.divider { height: 1px; background: var(--border); margin: 0.4em 0; }

.item {
  display: flex;
  align-items: center;
  gap: 0.8em;
  width: 100%;
  padding: 0.7em 0.8em;
  background: none;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  text-align: left;
  color: var(--text-0);
  font-size: 0.93em;
  font-weight: 500;
  justify-content: flex-start;
}
.item:hover { background: var(--bg-2); }
.item .ico { font-size: 1.2em; flex-shrink: 0; width: 1.5em; text-align: center; }
.item .txt { flex: 1; min-width: 0; }
.item .t { font-weight: 600; line-height: 1.2; }
.item .s { font-size: 0.78em; color: var(--text-2); margin-top: 0.15em; font-weight: 400; }
.item.logout { color: var(--red); }
.item.logout:hover { background: var(--red-soft); }

@media (max-width: 640px) {
  .username { display: none; }
  .dropdown { min-width: 260px; }
}
</style>
