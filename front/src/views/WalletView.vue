<template>
  <AppLayout>
    <main class="page fade-in">
      <div class="page-header">
        <h1 class="page-title">Salut {{ wallet.me.username }}.</h1>
        <p class="page-sub">{{ greeting }}</p>
      </div>

      <div class="wallet-grid">
        <BalanceCard :me="wallet.me" :loading="wallet.loading" @refresh="wallet.refresh()" />

        <div class="hype-card">
          <h3 class="hype-title">Le plan, étape par étape</h3>
          <p class="hype-text">
            <span class="accent">1.</span> Accumuler. <br />
            <span class="accent">2.</span> Continuer d'accumuler. <br />
            <span class="accent">3.</span> Démissionner par .docx (déjà rédigé). <br />
            <span class="accent">4.</span> Acheter une ferme. Lait. <br />
            <span class="accent">5.</span> Devenir le sujet de chuchotements.
          </p>
        </div>

        <div class="full-width">
          <SendForm :users="wallet.users" :balance="wallet.me.balance || 0" />
        </div>

        <div class="full-width">
          <HistoryList :history="wallet.history" :me-username="wallet.me.username || ''" />
        </div>
      </div>
    </main>
  </AppLayout>
</template>

<script setup>
import { onMounted, computed } from 'vue'
import AppLayout from '@/components/layout/AppLayout.vue'
import BalanceCard from '@/components/wallet/BalanceCard.vue'
import SendForm from '@/components/wallet/SendForm.vue'
import HistoryList from '@/components/wallet/HistoryList.vue'
import { useWalletStore } from '@/stores/wallet'

const wallet = useWalletStore()

const greetings = [
  "Aujourd'hui c'est le jour où tu deviens riche. Peut-être pas. Mais peut-être.",
  "Petit rappel : ton banquier ne sait toujours pas ce qui se prépare.",
  "Mode trader activé. Café en main. Démission en .docx.",
  "Les Lambo Camplong arrivent. Pas tout de suite. Mais elles arrivent.",
  "Tes parents pensent que c'est une arnaque. Spoiler : eux non plus n'ont pas compris Bitcoin en 2009.",
  "Une journée de plus, un CAMP de plus. C'est mathématique.",
  "« On y croit, on y croit » — toi à toi-même, devant le miroir, ce matin."
]
const greeting = computed(() => greetings[Math.floor(Math.random() * greetings.length)])

onMounted(() => {
  wallet.refresh()
})
</script>

<style scoped>
.wallet-grid {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 1.25em;
}
.full-width {
  grid-column: 1 / -1;
}

@media (max-width: 880px) {
  .wallet-grid { grid-template-columns: 1fr; }
}

.hype-card {
  background:
    linear-gradient(135deg, rgba(255, 122, 0, 0.08), rgba(164, 132, 255, 0.06)),
    var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.4em;
  position: relative;
  overflow: hidden;
}
.hype-card::before {
  content: '✦';
  position: absolute;
  top: -10px;
  right: -10px;
  font-size: 6em;
  color: rgba(255, 122, 0, 0.06);
  font-family: serif;
}
.hype-title {
  font-size: 1.3em;
  margin-bottom: 0.3em;
}
.hype-text {
  color: var(--text-1);
  font-size: 0.92em;
  line-height: 1.55;
  margin: 0;
}
.hype-text .accent {
  color: var(--camp);
  font-weight: 600;
}
</style>
