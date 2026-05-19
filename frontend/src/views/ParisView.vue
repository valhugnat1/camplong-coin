<template>
  <AppLayout>
    <main class="page fade-in">
      <div class="page-header">
        <h1 class="page-title">Paris <span class="dot">·</span> Pronostics</h1>
        <p class="page-sub">Si t'es plus malin que les autres (tu l'es), tu vas en vivre.</p>
      </div>

      <div class="alert info" style="margin-bottom: 1.5em">
        <span style="font-size: 1.2em">⏳</span>
        <span>
          <b>Bientôt.</b> Les marchés sont en pré-prod. En attendant, voici à quoi ça ressemblera. Affûte tes intuitions.
        </span>
      </div>

      <div class="paris-grid">
        <article v-for="(m, i) in markets" :key="i" class="market-card">
          <div class="market-cat">{{ m.category }}</div>
          <h3 class="market-q">{{ m.question }}</h3>
          <div class="market-odds">
            <button class="odd-btn yes" disabled>
              <span class="label">OUI</span>
              <span class="pct mono">{{ m.yes }}¢</span>
            </button>
            <button class="odd-btn no" disabled>
              <span class="label">NON</span>
              <span class="pct mono">{{ 100 - m.yes }}¢</span>
            </button>
          </div>
          <div class="market-meta mono">
            <span>Vol: {{ m.volume }} CAMP</span>
            <span>Clôt: {{ m.close }}</span>
          </div>
        </article>
      </div>
    </main>
  </AppLayout>
</template>

<script setup>
import AppLayout from '@/components/layout/AppLayout.vue'

const markets = [
  { category: 'Crypto',    question: 'Le CAMP va-t-il atteindre 1$ avant 2027 ?',                 yes: 8,  volume: '12.4k', close: '31 Déc' },
  { category: 'Pro',       question: 'Hugo signera chez Mistral avant le 1er août 2026 ?',        yes: 92, volume: '8.2k',  close: '1 Août' },
  { category: 'Sport',     question: 'Le PSG remporte la Ligue des Champions 2026-27 ?',          yes: 27, volume: '44.1k', close: 'Juin 27' },
  { category: 'Lifestyle', question: 'Alice va-t-elle gagner au prochain Catan ?',                yes: 18, volume: '0.6k',  close: 'Samedi' },
  { category: 'Macro',     question: 'Le prix du litre de lait dépasse 1.30€ en France en Q4 ?',  yes: 64, volume: '3.3k',  close: '31 Déc' },
  { category: 'Bullshit',  question: 'Quelqu\'un dans le groupe quitte son 9-to-5 en 2026 ?',     yes: 41, volume: '5.5k',  close: '31 Déc' },
  { category: 'Tech',      question: 'GPT-6 sort avant juin 2026 ?',                              yes: 33, volume: '9.0k',  close: 'Juin 26' },
  { category: 'Météo',     question: 'Il pleut le jour de la sortie Croagh Patrick ?',            yes: 88, volume: '1.1k',  close: 'Juillet' }
]
</script>

<style scoped>
.dot { color: var(--violet); }

.paris-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1em;
}

.market-card {
  position: relative;
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.3em;
  overflow: hidden;
  transition: transform 0.2s, border-color 0.2s;
}
.market-card:hover {
  transform: translateY(-2px);
  border-color: var(--border-strong);
}

.market-cat {
  display: inline-block;
  font-size: 0.68em;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--violet);
  font-weight: 700;
  margin-bottom: 0.6em;
}

.market-q {
  font-size: 1.1em;
  line-height: 1.3;
  letter-spacing: -0.01em;
  margin-bottom: 1em;
  min-height: 2.6em;
}

.market-odds {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.5em;
  margin-bottom: 0.9em;
}

.odd-btn {
  padding: 0.7em;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--bg-2);
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.odd-btn .label {
  font-weight: 600;
  font-size: 0.85em;
}
.odd-btn.yes .label { color: var(--green); }
.odd-btn.no .label  { color: var(--red); }
.odd-btn .pct {
  font-weight: 700;
  font-size: 1em;
}

.market-meta {
  display: flex;
  justify-content: space-between;
  font-size: 0.78em;
  color: var(--text-2);
}
</style>
