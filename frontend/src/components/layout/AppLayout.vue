<template>
  <div class="app-shell">
    <header class="topbar">
      <TopBar />
      <Ticker />
      <TabNav />
    </header>
    <slot />
  </div>
</template>

<script setup>
import { onMounted, watch } from 'vue'
import TopBar from './TopBar.vue'
import Ticker from './Ticker.vue'
import TabNav from './TabNav.vue'
import { useAuthStore } from '@/stores/auth'
import { useWalletStore } from '@/stores/wallet'

// Hydrate wallet.me dès qu'on est sur une page authentifiée : sinon, après
// un F5 sur /casino, /milk, /paris, /poker, le store Pinia est vide et le
// bandeau profil + solde affichent "—" alors que le token est toujours en
// localStorage. WalletView faisait ce refresh seul ; on le centralise ici
// pour que toutes les pages enveloppées par AppLayout en bénéficient.
const auth = useAuthStore()
const wallet = useWalletStore()

function hydrateIfNeeded() {
  if (auth.userToken && !wallet.me.username && !wallet.loading) {
    wallet.refresh()
  }
}

onMounted(hydrateIfNeeded)
watch(() => auth.userToken, hydrateIfNeeded)
</script>

<style scoped>
.topbar {
  position: sticky;
  top: 0;
  z-index: 50;
  background: rgba(7, 7, 10, 0.85);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--border);
}
</style>
