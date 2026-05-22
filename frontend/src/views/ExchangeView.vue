<template>
  <AppLayout>
    <main class="page fade-in">
      <div class="page-header">
        <h1 class="page-title">Échange</h1>
        <p class="page-sub">Envoie ou reçois des CAMP — en mode pote, ou par QR.</p>
      </div>

      <!-- Solde rapide -->
      <div class="quick-balance" @click="$router.push('/buy')" role="button">
        <div>
          <div class="qb-label">Solde dispo</div>
          <div class="qb-amount mono">{{ formatNum(wallet.me.balance) }} <small>CAMP</small></div>
        </div>
        <div class="qb-eur">{{ formatEur(campToEur(wallet.me.balance)) }}</div>
      </div>

      <div class="exchange-grid">
        <!-- ─── RECEVOIR ─── -->
        <section class="card receive-card">
          <div class="card-header">
            <div class="card-title">📥 Recevoir</div>
            <span class="hint">Ton identifiant Camplong</span>
          </div>

          <div class="handle-row">
            <div class="handle-at">@</div>
            <div class="handle-name">{{ wallet.me.username || '—' }}</div>
          </div>

          <div class="address-row" @click="copyAddress" :class="{ copied: addrCopied }">
            <div class="addr-k">Adresse on-chain</div>
            <div class="addr-v mono">{{ truncatedAddress }}</div>
            <div class="addr-hint">{{ addrCopied ? '✓ Copié' : 'Touche pour copier' }}</div>
          </div>

          <button class="btn-primary btn-block btn-qr" @click="showQr = true" :disabled="!wallet.me.username">
            <span class="ic">🔳</span> Afficher mon QR
          </button>
        </section>

        <!-- ─── ENVOYER ─── -->
        <section class="card send-card">
          <div class="card-header">
            <div class="card-title">💸 Envoyer</div>
            <span class="hint">Gratuit, la treasury paie le gas</span>
          </div>

          <button class="btn-ghost btn-block btn-scan" @click="openScan">
            <span class="ic">📷</span> Scanner un QR Camplong
          </button>

          <div class="or-sep"><span>ou choisis un pote</span></div>

          <div class="field">
            <label class="field-label">Destinataire</label>
            <select v-model="form.to_username">
              <option value="" disabled>— choisir un pote —</option>
              <option v-for="u in wallet.users" :key="u.username" :value="u.username">
                {{ u.username }}
              </option>
            </select>
          </div>

          <label class="field-label">Montant</label>
          <div class="amount-wrap">
            <input v-model.number="form.amount" type="number" min="1" inputmode="numeric" placeholder="0" />
            <span class="amount-currency">CAMP</span>
          </div>
          <div class="quick">
            <button @click="form.amount = 10">+10</button>
            <button @click="form.amount = 50">+50</button>
            <button @click="form.amount = 100">+100</button>
            <button @click="form.amount = Math.floor((wallet.me.balance || 0) / 2)">50%</button>
            <button @click="form.amount = wallet.me.balance">MAX</button>
          </div>

          <div class="field" style="margin-top: 0.9em;">
            <label class="field-label">Note (optionnel)</label>
            <input v-model="form.note" placeholder="ex: bière, raclette, dette de poker…" maxlength="120" />
          </div>

          <button class="btn-primary btn-block" @click="submit" :disabled="sending || !canSend">
            {{ sending ? 'Envoi on-chain…' : `Envoyer ${form.amount || ''} CAMP` }}
          </button>

          <div v-if="success" class="alert success">
            {{ success }}
            <div v-if="lastTxHash" style="margin-top:.4em; font-size:.85em">
              <a :href="'https://sepolia.basescan.org/tx/' + lastTxHash" target="_blank" rel="noreferrer">
                Voir la tx sur BaseScan →
              </a>
            </div>
          </div>
          <div v-if="error" class="alert error">{{ error }}</div>
        </section>
      </div>
    </main>

    <ShowQrLayer
      v-if="showQr && wallet.me.username"
      :username="wallet.me.username"
      @close="showQr = false"
    />
    <ScanQrLayer
      v-if="showScan"
      :balance="wallet.me.balance || 0"
      :my-username="wallet.me.username || ''"
      @close="showScan = false"
      @sent="onScanSent"
    />
  </AppLayout>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import AppLayout from '@/components/layout/AppLayout.vue'
import ShowQrLayer from '@/components/exchange/ShowQrLayer.vue'
import ScanQrLayer from '@/components/exchange/ScanQrLayer.vue'
import { apiCall } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useWalletStore } from '@/stores/wallet'
import { campToEur, formatEur, formatNum } from '@/config'

const auth = useAuthStore()
const wallet = useWalletStore()

const showQr = ref(false)
const showScan = ref(false)
const addrCopied = ref(false)

const form = reactive({ to_username: '', amount: 0, note: '' })
const sending = ref(false)
const error = ref('')
const success = ref('')
const lastTxHash = ref('')

const canSend = computed(() => form.to_username && form.amount > 0)

const truncatedAddress = computed(() => {
  const a = wallet.me.address || ''
  if (!a) return '—'
  if (a.length <= 22) return a
  return `${a.slice(0, 10)}…${a.slice(-8)}`
})

async function copyAddress() {
  if (!wallet.me.address) return
  try {
    await navigator.clipboard.writeText(wallet.me.address)
    addrCopied.value = true
    setTimeout(() => (addrCopied.value = false), 1500)
  } catch (_) {}
}

function openScan() {
  error.value = ''
  success.value = ''
  showScan.value = true
}

function onScanSent() {
  // Le ScanQrLayer affiche déjà son écran succès ; on n'a rien à faire ici
  // sauf rafraîchir (déjà fait dans le layer).
}

async function submit() {
  error.value = ''
  success.value = ''
  lastTxHash.value = ''
  sending.value = true
  try {
    const d = await apiCall('/transfer', {
      method: 'POST',
      token: auth.userToken,
      body: JSON.stringify(form)
    })
    lastTxHash.value = d.tx_hash
    success.value = `Envoyé ! Nouveau solde : ${d.new_balance} CAMP.`
    form.amount = 0
    form.note = ''
    form.to_username = ''
    await wallet.refresh()
  } catch (e) {
    error.value = e.message
  } finally {
    sending.value = false
  }
}

onMounted(() => {
  if (!wallet.me.username) wallet.refresh()
})
</script>

<style scoped>
.quick-balance {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1em;
  padding: 1em 1.2em;
  background:
    linear-gradient(135deg, rgba(255, 122, 0, 0.10) 0%, rgba(164, 132, 255, 0.06) 100%),
    var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin-bottom: 1.25em;
  cursor: pointer;
  transition: border-color 0.15s, transform 0.15s;
}
.quick-balance:active { transform: scale(0.99); }
.qb-label {
  color: var(--text-2);
  font-size: 0.78em;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  font-weight: 600;
  margin-bottom: 0.15em;
}
.qb-amount {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 700;
  font-size: 1.6em;
  letter-spacing: -0.02em;
}
.qb-amount small {
  color: var(--camp);
  font-size: 0.55em;
  margin-left: 0.2em;
  font-weight: 600;
  vertical-align: top;
  position: relative;
  top: 0.4em;
}
.qb-eur {
  color: var(--text-1);
  font-weight: 600;
  font-family: 'JetBrains Mono', monospace;
}

.exchange-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.25em;
}
@media (max-width: 880px) {
  .exchange-grid {
    grid-template-columns: 1fr;
  }
}

/* ─── Recevoir ─── */
.handle-row {
  display: flex;
  align-items: baseline;
  gap: 0.15em;
  margin-bottom: 1em;
  padding: 0.8em 0;
}
.handle-at {
  color: var(--camp);
  font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 700;
  font-size: 1.6em;
  line-height: 1;
}
.handle-name {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 700;
  font-size: 2em;
  letter-spacing: -0.02em;
  line-height: 1;
}

.address-row {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0.9em 1em;
  margin-bottom: 1.2em;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
  user-select: none;
}
.address-row:active {
  background: var(--bg-3);
}
.address-row.copied {
  border-color: var(--green);
  background: var(--green-soft);
}
.addr-k {
  font-size: 0.72em;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-3);
  font-weight: 600;
  margin-bottom: 0.2em;
}
.addr-v {
  font-size: 0.95em;
  color: var(--text-0);
  word-break: break-all;
  margin-bottom: 0.2em;
}
.addr-hint {
  font-size: 0.75em;
  color: var(--text-2);
}
.address-row.copied .addr-hint {
  color: var(--green);
  font-weight: 600;
}

.btn-qr,
.btn-scan {
  padding: 1em 1.2em;
  font-size: 1em;
}
.btn-qr .ic,
.btn-scan .ic {
  font-size: 1.2em;
}

/* ─── Envoyer ─── */
.or-sep {
  display: flex;
  align-items: center;
  gap: 0.7em;
  color: var(--text-3);
  font-size: 0.78em;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  font-weight: 600;
  margin: 1.1em 0 0.9em;
}
.or-sep::before,
.or-sep::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--border);
}

.amount-wrap {
  position: relative;
  margin-bottom: 0.6em;
}
.amount-wrap input {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-size: 1.8em;
  font-weight: 700;
  padding: 0.6em 4em 0.6em 0.6em;
  letter-spacing: -0.02em;
  background: var(--bg-2);
}
.amount-currency {
  position: absolute;
  right: 1em;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-2);
  font-weight: 600;
  pointer-events: none;
  font-size: 0.95em;
}

.quick {
  display: flex;
  gap: 0.4em;
  margin-top: 0.2em;
  margin-bottom: 0.6em;
  flex-wrap: wrap;
}
.quick button {
  padding: 0.4em 0.8em;
  background: var(--bg-2);
  color: var(--text-1);
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 0.85em;
}

.hint {
  color: var(--text-3);
  font-size: 0.82em;
}

@media (max-width: 640px) {
  .qb-amount { font-size: 1.4em; }
  .handle-name { font-size: 1.7em; }
}
</style>
