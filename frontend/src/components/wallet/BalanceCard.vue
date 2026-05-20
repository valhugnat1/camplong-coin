<template>
  <div class="balance-card">
    <div class="balance-label">
      Solde <span class="live">live · on-chain</span>
    </div>
    <div class="balance-amount">
      {{ formatNum(me.balance) }}<sup>CAMP</sup>
    </div>
    <div class="balance-eur">
      ≈ <span class="mono">{{ formatEur(campToEur(me.balance)) }}</span>
      <router-link to="/buy" class="topup-link">+ ajouter</router-link>
    </div>

    <div class="conversions">
      ≈ <span class="mono">{{ formatNum(Math.round((me.balance || 0) / 120)) }}</span> baguettes ·
      ≈ <span class="mono">{{ formatNum(Math.round((me.balance || 0) / 600)) }}</span> bières ·
      ≈ <span class="mono">{{ formatNum(Math.round((me.balance || 0) / 2500)) }}</span> raclettes
    </div>

    <div class="meta">
      <div class="meta-item">
        <div class="k">Ton adresse on-chain</div>
        <div class="v">
          <a :href="'https://sepolia.basescan.org/address/' + me.address" target="_blank" rel="noreferrer">
            {{ me.address }}
          </a>
        </div>
      </div>
    </div>

    <div class="actions">
      <button class="btn-ghost" @click="copyAddress">
        {{ copied ? '✓ Copié' : '📋 Copier adresse' }}
      </button>
      <button class="btn-ghost" @click="$emit('refresh')" :disabled="loading">
        {{ loading ? '…' : '↻ Rafraîchir' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { campToEur, formatEur, formatNum } from '@/config'

const props = defineProps({
  me: { type: Object, required: true },
  loading: { type: Boolean, default: false }
})
defineEmits(['refresh'])

const copied = ref(false)
async function copyAddress() {
  try {
    await navigator.clipboard.writeText(props.me.address || '')
    copied.value = true
    setTimeout(() => (copied.value = false), 1500)
  } catch (e) {
    // silencieux
  }
}
</script>

<style scoped>
.balance-card {
  position: relative;
  background:
    radial-gradient(circle at 90% 0%, rgba(255, 122, 0, 0.18), transparent 60%),
    linear-gradient(135deg, #11111a 0%, #0d0d14 100%);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius);
  padding: 2em 1.8em;
  overflow: hidden;
}
.balance-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--camp), transparent);
}
.balance-card::after {
  content: 'CAMP';
  position: absolute;
  right: -20px;
  bottom: -30px;
  font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 800;
  font-size: 11em;
  color: rgba(255, 122, 0, 0.04);
  letter-spacing: -0.04em;
  pointer-events: none;
}

.balance-label {
  display: flex;
  align-items: center;
  gap: 0.5em;
  color: var(--text-2);
  font-size: 0.82em;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  margin-bottom: 0.5em;
  font-weight: 600;
}
.balance-label .live {
  display: inline-flex;
  align-items: center;
  gap: 0.35em;
  color: var(--green);
  font-size: 0.85em;
}
.balance-label .live::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--green);
  animation: pulse 2s infinite;
  box-shadow: 0 0 6px var(--green);
}

.balance-amount {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 700;
  font-size: 3.6em;
  letter-spacing: -0.04em;
  line-height: 1;
  margin-bottom: 0.15em;
  background: linear-gradient(180deg, #fff 0%, #a1a1aa 130%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
.balance-amount sup {
  font-size: 0.35em;
  color: var(--camp);
  -webkit-text-fill-color: var(--camp);
  margin-left: 0.3em;
  font-weight: 600;
  letter-spacing: 0;
  vertical-align: top;
  position: relative;
  top: 1em;
}

.balance-eur {
  display: flex;
  align-items: center;
  gap: 0.6em;
  color: var(--text-2);
  font-size: 0.95em;
  margin-bottom: 0.8em;
}
.balance-eur .mono {
  color: var(--text-1);
  font-weight: 600;
}
.topup-link {
  font-size: 0.78em;
  font-weight: 600;
  padding: 0.15em 0.5em;
  border-radius: 999px;
  background: var(--camp-soft);
  color: var(--camp);
  text-decoration: none;
}
.topup-link:hover {
  background: var(--camp);
  color: white;
  text-decoration: none;
}

.conversions {
  color: var(--text-3);
  font-size: 0.85em;
}

.meta {
  display: flex;
  gap: 1.5em;
  margin-top: 1.2em;
  padding-top: 1.2em;
  border-top: 1px dashed var(--border);
  flex-wrap: wrap;
}
.meta-item {
  flex: 1;
  min-width: 0;
}
.meta-item .k {
  font-size: 0.72em;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-3);
  font-weight: 600;
  margin-bottom: 0.2em;
}
.meta-item .v {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85em;
  color: var(--text-1);
  word-break: break-all;
}
.meta-item .v a { color: var(--text-1); }

.actions {
  display: flex;
  gap: 0.6em;
  margin-top: 1.4em;
}
.actions button {
  flex: 1;
  padding: 0.7em 1em;
}

@media (max-width: 640px) {
  .balance-card { padding: 1.5em 1.3em; }
  .balance-amount { font-size: 2.6em; }
}
</style>
