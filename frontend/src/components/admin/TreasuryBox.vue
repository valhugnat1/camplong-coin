<template>
  <div class="treasury-box">
    <div class="treasury-header">
      <h2>Treasury</h2>
      <span class="hint">ton portefeuille on-chain · owner du contrat</span>
    </div>
    <div class="addr mono">
      <a v-if="treasury.address" :href="'https://sepolia.basescan.org/address/' + treasury.address" target="_blank" rel="noreferrer">
        {{ treasury.address }}
      </a>
      <span v-else>—</span>
    </div>
    <div class="stats">
      <div class="stat">
        <div class="stat-label">CAMP en treasury</div>
        <div class="stat-value mono">{{ formatNum(treasury.balance_camp) }}</div>
        <div class="stat-sub mono">≈ {{ formatEur(campToEur(treasury.balance_camp)) }}</div>
      </div>
      <div class="stat">
        <div class="stat-label">ETH (gas)</div>
        <div class="stat-value mono">{{ (treasury.balance_eth ?? 0).toFixed(4) }}</div>
        <div v-if="lowGas" class="warn">⚠ Refund bientôt</div>
        <div v-else class="stat-sub">ok</div>
      </div>
      <div class="stat">
        <div class="stat-label">CAMP en circulation</div>
        <div class="stat-value mono">{{ formatNum(circulating) }}</div>
        <div class="stat-sub mono">≈ {{ formatEur(campToEur(circulating)) }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { campToEur, formatEur, formatNum } from '@/config'

const props = defineProps({
  treasury: { type: Object, required: true },
  totalCircCamp: { type: Number, default: 0 }   // somme des CAMP des users
})

const lowGas = computed(() => (props.treasury.balance_eth ?? 0) < 0.01)
const circulating = computed(() => props.totalCircCamp)
</script>

<style scoped>
.treasury-box {
  position: relative;
  background:
    radial-gradient(circle at 90% 0%, rgba(255, 122, 0, 0.12), transparent 60%),
    linear-gradient(135deg, #1a1a23 0%, #0d0d14 100%);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius);
  padding: 1.5em;
  margin-bottom: 1.25em;
  overflow: hidden;
  color: white;
}
.treasury-box::before {
  content: '';
  position: absolute;
  top: 0; left: 0;
  width: 100%; height: 1px;
  background: linear-gradient(90deg, transparent, var(--camp), transparent);
}

.treasury-header {
  display: flex;
  align-items: baseline;
  gap: 0.6em;
  flex-wrap: wrap;
  margin-bottom: 0.3em;
}
.treasury-header h2 {
  margin: 0;
  font-size: 1.2em;
}
.hint {
  color: var(--text-2);
  font-size: 0.82em;
  font-style: italic;
}

.addr {
  word-break: break-all;
  font-size: 0.85em;
  color: var(--text-1);
  margin-bottom: 1em;
}
.addr a {
  color: var(--text-1);
}

.stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1em;
}
@media (max-width: 720px) {
  .stats { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 480px) {
  .stats { grid-template-columns: 1fr; }
}

.stat {
  padding: 0.6em 0.8em;
  background: rgba(255, 255, 255, 0.02);
  border-radius: var(--radius-sm);
}
.stat-label {
  font-size: 0.72em;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-2);
  font-weight: 600;
}
.stat-value {
  font-size: 1.4em;
  font-weight: 700;
  margin-top: 0.15em;
}
.stat-sub {
  color: var(--text-2);
  font-size: 0.78em;
  margin-top: 0.15em;
}
.warn {
  color: var(--red);
  font-size: 0.78em;
  font-weight: 600;
  margin-top: 0.2em;
}
</style>
