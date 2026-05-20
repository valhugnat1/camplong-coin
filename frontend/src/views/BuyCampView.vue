<template>
  <AppLayout>
    <main class="page fade-in">
      <div class="page-header">
        <h1 class="page-title">
          {{ mode === 'buy' ? '💶 Acheter du CAMP' : '💸 Vendre du CAMP' }}
        </h1>
        <p class="page-sub">
          Système artisanal : tu envoies un Wero ou un Revolut à Hugo, il crédite ton wallet à la main.
          C'est plus charmant comme ça.
        </p>
      </div>

      <!-- Pas d'email → on bloque -->
      <div v-if="!wallet.me.email" class="alert info" style="margin-bottom:1.5em">
        <span style="font-size:1.2em">📧</span>
        <span>
          Pour passer une demande, on a besoin de ton email
          (sinon Hugo peut pas te confirmer quand c'est traité).
          <router-link to="/profile" style="margin-left:0.4em; font-weight:600">
            Ajouter mon email →
          </router-link>
        </span>
      </div>

      <!-- Toggle Buy / Sell -->
      <div class="mode-toggle">
        <button :class="{ active: mode === 'buy' }" @click="mode = 'buy'">
          <span>📈</span> Acheter
        </button>
        <button :class="{ active: mode === 'sell' }" @click="mode = 'sell'">
          <span>📉</span> Vendre
        </button>
      </div>

      <div class="grid">
        <!-- ─── FORM ─── -->
        <div class="card form-card">
          <div class="card-header">
            <div class="card-title">
              {{ mode === 'buy' ? 'Combien tu veux acheter ?' : 'Combien tu veux vendre ?' }}
            </div>
          </div>

          <!-- BUY -->
          <template v-if="mode === 'buy'">
            <label class="field-label">Montant à payer</label>
            <div class="amount-wrap">
              <input v-model.number="eurInput" type="number" min="1" step="1" placeholder="0" :disabled="submitted" />
              <span class="amount-unit">EUR</span>
            </div>
            <div class="quick" v-if="!submitted">
              <button @click="eurInput = 5">5 €</button>
              <button @click="eurInput = 10">10 €</button>
              <button @click="eurInput = 20">20 €</button>
              <button @click="eurInput = 50">50 €</button>
              <button @click="eurInput = 100">100 €</button>
            </div>

            <div class="receive-box">
              <div class="receive-label">Tu vas recevoir</div>
              <div class="receive-amount">
                <span class="big mono">{{ formatNum(campOut) }}</span>
                <span class="unit">CAMP</span>
              </div>
            </div>

            <details class="breakdown" open>
              <summary>Détail du calcul</summary>
              <div class="row"><span>Taux</span><span class="mono">1 € = 100 CAMP</span></div>
              <div class="row"><span>Brut</span><span class="mono">{{ formatNum(grossBuy) }} CAMP</span></div>
              <div class="row dim"><span>Frais achat ({{ feePctBuy }} %)</span><span class="mono">−{{ formatNum(feeBuyCamp) }} CAMP</span></div>
              <div class="row total"><span>Net reçu</span><span class="mono">{{ formatNum(campOut) }} CAMP</span></div>
              <p class="fee-note">
                Les 5 % couvrent les serveurs et le gas Ethereum. La <b>vente est sans frais</b> :
                la valeur en € affichée sur ton solde est exactement ce que tu récupères si tu revends.
              </p>
            </details>
          </template>

          <!-- SELL -->
          <template v-else>
            <label class="field-label">Montant à vendre</label>
            <div class="amount-wrap">
              <input v-model.number="campInput" type="number" min="1" step="100" placeholder="0" :disabled="submitted" />
              <span class="amount-unit">CAMP</span>
            </div>
            <div class="quick" v-if="!submitted">
              <button @click="campInput = 100">100</button>
              <button @click="campInput = 500">500</button>
              <button @click="campInput = 1000">1k</button>
              <button @click="campInput = Math.floor((wallet.me.balance || 0) / 2)">50 %</button>
              <button @click="campInput = wallet.me.balance">MAX</button>
            </div>

            <div class="receive-box">
              <div class="receive-label">Hugo te renvoie</div>
              <div class="receive-amount">
                <span class="big mono">{{ formatEur(eurOut) }}</span>
              </div>
            </div>

            <div class="no-fee-pill">
              <span>✨</span> <b>Vente sans frais.</b>
              Le prix affiché correspond pile à la valeur de ton solde.
            </div>

            <div class="field" style="margin-top:1em">
              <label class="field-label">Ton handle Wero ou Revolut</label>
              <input v-model="sellHandle" placeholder="ex: +33 6 12 34 56 78 ou @tonpseudo" :disabled="submitted" />
            </div>

            <div v-if="campInput > (wallet.me.balance || 0)" class="alert error">
              Tu n'as pas assez de CAMP. Solde actuel : {{ formatNum(wallet.me.balance) }} CAMP.
            </div>
          </template>

          <!-- Submit -->
          <button
            v-if="!submitted"
            class="btn-primary btn-block"
            style="margin-top:1em"
            @click="submit"
            :disabled="!canSubmit || submitting || !wallet.me.email"
          >
            {{ submitting
                ? 'Création de la demande…'
                : (mode === 'buy'
                    ? `Demander l'achat de ${formatNum(campOut)} CAMP`
                    : `Demander la vente de ${formatNum(campInput || 0)} CAMP`) }}
          </button>

          <div v-else class="alert success" style="margin-top:1em">
            <div>
              ✓ <b>Demande #{{ lastOrder.id }} enregistrée.</b>
              Hugo a été notifié par email.
            </div>
            <div style="margin-top:0.4em; font-size:0.88em">
              <router-link to="/orders" style="font-weight:600">Suivre mes demandes →</router-link>
              ·
              <button class="link-btn" @click="resetForm">+ Nouvelle demande</button>
            </div>
          </div>

          <div v-if="error" class="alert error" style="margin-top:.8em">{{ error }}</div>
        </div>

        <!-- ─── PAYMENT INSTRUCTIONS ─── -->
        <div class="card pay-card">
          <div class="card-header">
            <div class="card-title">
              {{ mode === 'buy' ? '💳 Comment payer' : '🏦 Comment Hugo te paiera' }}
            </div>
          </div>

          <template v-if="mode === 'buy'">
            <p class="explain">
              Envoie <b>{{ formatEur(eurInput || 0) }}</b> à <b>{{ payment.recipient }}</b>
              via l'un de ces moyens :
            </p>

            <div class="pay-option">
              <div class="pay-name">
                <span class="logo">🇪🇺</span> Wero
                <span class="tag">recommandé</span>
              </div>
              <div class="pay-handle mono">{{ payment.wero }}</div>
              <button class="btn-ghost btn-sm" @click="copy(payment.wero, 'wero')">
                {{ copied === 'wero' ? '✓' : '📋' }} Copier
              </button>
            </div>

            <div class="pay-option">
              <div class="pay-name">
                <span class="logo">🇬🇧</span> Revolut
              </div>
              <div class="pay-handle mono">{{ payment.revolut }}</div>
              <button class="btn-ghost btn-sm" @click="copy(payment.revolut, 'rev')">
                {{ copied === 'rev' ? '✓' : '📋' }} Copier
              </button>
            </div>

            <div class="message-box">
              <div class="msg-label">📝 Message à mettre dans le paiement</div>
              <div class="msg-content mono">
                <span>{{ paymentMessage }}</span>
                <button class="btn-ghost btn-sm" @click="copy(paymentMessage, 'msg')">
                  {{ copied === 'msg' ? '✓' : '📋' }}
                </button>
              </div>
              <p class="msg-hint">Important : sans ce message, Hugo ne saura pas qui créditer.</p>
            </div>

            <p class="timeline">
              ⏱ Traité manuellement. Si t'as besoin que ça soit rapide,
              ping Hugo par message direct. Tu reçois un email quand c'est fait.
            </p>
          </template>

          <template v-else>
            <p class="explain">
              Hugo va t'envoyer <b>{{ formatEur(eurOut) }}</b> via Wero ou Revolut sur le handle que tu auras renseigné.
              Une fois fait, ton wallet sera débité de <b>{{ formatNum(campInput || 0) }} CAMP</b>
              et tu recevras un email de confirmation.
            </p>

            <p class="timeline">
              ⏱ Traité manuellement. Ping Hugo direct si urgent.
            </p>
          </template>

          <div class="fine-print">
            Pas de KYC, pas de blockchain analytics, pas de SEC.
            <b>C'est très exactement ce qui se passe avant que tout devienne un produit financier régulé.</b>
            Profite.
          </div>
        </div>
      </div>
    </main>
  </AppLayout>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import AppLayout from '@/components/layout/AppLayout.vue'
import { apiCall } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useWalletStore } from '@/stores/wallet'
import { RATES, PAYMENT, formatEur, formatNum } from '@/config'

const auth = useAuthStore()
const wallet = useWalletStore()
const payment = PAYMENT
const feePctBuy = RATES.feePctBuy

const mode = ref('buy')
const eurInput = ref(10)
const campInput = ref(1000)
const sellHandle = ref('')
const copied = ref('')

const submitting = ref(false)
const submitted = ref(false)
const lastOrder = ref(null)
const error = ref('')

// ─── Computations
const grossBuy = computed(() => Math.floor((eurInput.value || 0) * RATES.campPerEur))
const feeBuyCamp = computed(() => Math.floor(grossBuy.value * (RATES.feePctBuy / 100)))
const campOut = computed(() => Math.max(0, grossBuy.value - feeBuyCamp.value))
const eurOut = computed(() => (campInput.value || 0) / RATES.campPerEur)

const canSubmit = computed(() => {
  if (mode.value === 'buy') return eurInput.value > 0 && campOut.value > 0
  return campInput.value > 0
      && campInput.value <= (wallet.me.balance || 0)
      && sellHandle.value.trim().length > 3
})

const paymentMessage = computed(() => `CAMP ${wallet.me.username || ''}`.trim())

async function copy(text, key) {
  try {
    await navigator.clipboard.writeText(text)
    copied.value = key
    setTimeout(() => (copied.value = ''), 1500)
  } catch (e) { /* silencieux */ }
}

async function submit() {
  error.value = ''
  submitting.value = true
  try {
    const body = mode.value === 'buy'
      ? {
          type: 'buy',
          amount_camp: campOut.value,
          amount_eur: Number(eurInput.value || 0),
          handle: '',
          note: ''
        }
      : {
          type: 'sell',
          amount_camp: Number(campInput.value || 0),
          amount_eur: Number(eurOut.value),
          handle: sellHandle.value.trim(),
          note: ''
        }
    const order = await apiCall('/orders', {
      method: 'POST',
      token: auth.userToken,
      body: JSON.stringify(body)
    })
    lastOrder.value = order
    submitted.value = true
  } catch (e) {
    error.value = e.message
  } finally {
    submitting.value = false
  }
}

function resetForm() {
  submitted.value = false
  lastOrder.value = null
  error.value = ''
  eurInput.value = 10
  campInput.value = 1000
  sellHandle.value = ''
}

onMounted(() => {
  if (!wallet.me.username) wallet.refresh()
})
</script>

<style scoped>
.mode-toggle {
  display: inline-flex;
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0.3em;
  margin-bottom: 1.25em;
  gap: 0.3em;
}
.mode-toggle button {
  background: none;
  border: none;
  padding: 0.5em 1em;
  color: var(--text-2);
  font-weight: 600;
  border-radius: 6px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 0.4em;
  font-size: 0.92em;
}
.mode-toggle button:hover { color: var(--text-0); }
.mode-toggle button.active { background: var(--camp); color: white; }

.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.25em;
}
@media (max-width: 880px) {
  .grid { grid-template-columns: 1fr; }
}

.amount-wrap { position: relative; margin-bottom: 0.9em; }
.amount-wrap input {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-size: 2em;
  font-weight: 700;
  padding: 0.5em 4em 0.5em 0.6em;
  letter-spacing: -0.02em;
  background: var(--bg-2);
}
.amount-unit {
  position: absolute;
  right: 1em;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-2);
  font-weight: 600;
  pointer-events: none;
}

.quick {
  display: flex;
  gap: 0.4em;
  margin-top: -0.4em;
  margin-bottom: 0.9em;
  flex-wrap: wrap;
}
.quick button {
  padding: 0.35em 0.8em;
  background: var(--bg-2);
  color: var(--text-1);
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 0.85em;
}
.quick button:hover { background: var(--bg-3); color: var(--text-0); }

.receive-box {
  background: linear-gradient(135deg, rgba(20, 224, 142, 0.08), rgba(255, 122, 0, 0.04));
  border: 1px solid rgba(20, 224, 142, 0.2);
  border-radius: var(--radius-sm);
  padding: 0.9em 1em;
  margin: 0.9em 0;
}
.receive-label {
  font-size: 0.78em;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-2);
  font-weight: 600;
  margin-bottom: 0.2em;
}
.receive-amount { display: flex; align-items: baseline; gap: 0.5em; }
.receive-amount .big {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-size: 2em;
  font-weight: 700;
  color: var(--green);
  letter-spacing: -0.02em;
}
.receive-amount .unit { color: var(--text-2); font-weight: 600; }

.no-fee-pill {
  display: flex;
  align-items: center;
  gap: 0.5em;
  padding: 0.7em 1em;
  background: var(--green-soft);
  border: 1px solid rgba(20, 224, 142, 0.25);
  border-radius: var(--radius-sm);
  color: #6bf2b7;
  font-size: 0.88em;
  margin-top: 0.6em;
}
.no-fee-pill b { color: var(--green); }

.breakdown {
  margin-top: 0.6em;
  padding: 0.8em 1em;
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 0.9em;
}
.breakdown summary { cursor: pointer; color: var(--text-2); font-weight: 600; margin-bottom: 0.5em; }
.breakdown summary:hover { color: var(--text-0); }
.breakdown .row {
  display: flex; justify-content: space-between;
  padding: 0.4em 0;
  border-bottom: 1px solid var(--border);
}
.breakdown .row:last-of-type { border-bottom: none; }
.breakdown .row.dim { color: var(--text-2); }
.breakdown .row.total {
  font-weight: 700;
  border-top: 1px solid var(--border);
  margin-top: 0.3em;
  padding-top: 0.6em;
}
.breakdown .row.total .mono { color: var(--green); }
.fee-note { color: var(--text-3); font-size: 0.82em; font-style: italic; margin: 0.6em 0 0 0; }
.fee-note b { color: var(--text-1); font-style: normal; }

.pay-card .explain {
  color: var(--text-1);
  margin-bottom: 1em;
  line-height: 1.55;
}

.pay-option {
  display: flex;
  align-items: center;
  gap: 0.6em;
  padding: 0.8em;
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  margin-bottom: 0.6em;
  flex-wrap: wrap;
}
.pay-name { display: flex; align-items: center; gap: 0.4em; font-weight: 600; font-size: 0.9em; }
.pay-name .tag {
  background: var(--green-soft);
  color: var(--green);
  padding: 0.1em 0.45em;
  border-radius: 4px;
  font-size: 0.7em;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.pay-handle { flex: 1; font-size: 0.92em; color: var(--text-0); word-break: break-all; min-width: 100px; }

.message-box {
  margin-top: 0.6em;
  padding: 0.9em 1em;
  background: var(--camp-soft);
  border: 1px solid rgba(255, 122, 0, 0.25);
  border-radius: var(--radius-sm);
}
.msg-label { font-size: 0.82em; font-weight: 600; color: var(--camp); margin-bottom: 0.4em; }
.msg-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--bg-0);
  padding: 0.6em 0.8em;
  border-radius: 6px;
  font-size: 0.9em;
  color: var(--text-0);
  font-weight: 600;
}
.msg-hint { font-size: 0.8em; color: var(--text-2); margin: 0.4em 0 0 0; font-style: italic; }

.timeline {
  background: var(--bg-2);
  border-left: 3px solid var(--camp);
  padding: 0.7em 1em;
  margin: 1em 0 0 0;
  color: var(--text-1);
  font-size: 0.88em;
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}

.fine-print {
  margin-top: 1em;
  padding-top: 1em;
  border-top: 1px dashed var(--border);
  color: var(--text-3);
  font-size: 0.82em;
  font-style: italic;
  line-height: 1.5;
}
.fine-print b { color: var(--text-1); font-style: normal; }

.link-btn {
  background: none;
  border: none;
  color: var(--camp);
  font-weight: 600;
  cursor: pointer;
  padding: 0;
  font-size: inherit;
  font-family: inherit;
}
.link-btn:hover { text-decoration: underline; }
</style>
