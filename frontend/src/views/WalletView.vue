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
          <ol class="hype-steps">
            <li><span class="step-num">1</span> Accumuler du CAMP</li>
            <li><span class="step-num">2</span> Acheter une ferme</li>
            <li><span class="step-num">3</span> Produire du lait <em>en quantité massive</em></li>
            <li><span class="step-num">4</span> Vendre sur les marchés actions</li>
            <li><span class="step-num">5</span> Titriser le lait en produits dérivés</li>
            <li><span class="step-num">6</span> Devenir <b>le Loup du Wall Street</b></li>
          </ol>
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
  font-size: 1.15em;
  margin-bottom: 0.6em;
}
.hype-steps {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.25em;
}
.hype-steps li {
  display: flex;
  align-items: center;
  gap: 0.6em;
  color: var(--text-1);
  font-size: 0.88em;
  line-height: 1.3;
  padding: 0.25em 0;
}
.hype-steps em {
  color: var(--text-0);
  font-style: italic;
  font-weight: 500;
}
.hype-steps b {
  color: var(--camp);
  font-weight: 700;
}
.step-num {
  display: inline-grid;
  place-items: center;
  width: 1.4em;
  height: 1.4em;
  border-radius: 50%;
  background: var(--camp-soft);
  color: var(--camp);
  font-size: 0.78em;
  font-weight: 700;
  flex-shrink: 0;
  font-family: 'JetBrains Mono', monospace;
}
.hype-steps li:last-child .step-num {
  background: var(--camp);
  color: white;
  box-shadow: 0 0 12px var(--camp-glow);
}
</style>
