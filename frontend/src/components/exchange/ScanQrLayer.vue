<template>
  <div class="scan-layer">
    <button class="close-btn" @click="close" aria-label="Fermer">✕</button>

    <!-- ÉTAPE 1 : caméra qui cherche un QR -->
    <template v-if="step === 'scan'">
      <div class="cam-wrap">
        <video ref="videoEl" class="cam-video" autoplay playsinline muted />
        <div class="viewfinder">
          <div class="vf-corner tl"></div>
          <div class="vf-corner tr"></div>
          <div class="vf-corner bl"></div>
          <div class="vf-corner br"></div>
          <div class="vf-laser" />
        </div>
      </div>

      <div class="bottom-sheet">
        <div class="sheet-title">Scanne un QR Camplong</div>
        <div class="sheet-sub">Cadre le QR de ton destinataire dans la zone.</div>
        <div v-if="error" class="alert error">{{ error }}</div>
      </div>
    </template>

    <!-- ÉTAPE 2 : montant + confirmation -->
    <template v-else-if="step === 'amount'">
      <div class="amount-pane">
        <div class="recipient-card">
          <div class="recipient-eyebrow">Envoyer à</div>
          <div class="recipient-name">@{{ scanned }}</div>
        </div>

        <label class="field-label">Montant</label>
        <div class="amount-wrap">
          <input
            ref="amountInput"
            v-model.number="amount"
            type="number"
            min="1"
            inputmode="numeric"
            placeholder="0"
          />
          <span class="amount-currency">CAMP</span>
        </div>

        <div class="quick">
          <button @click="amount = 10">+10</button>
          <button @click="amount = 50">+50</button>
          <button @click="amount = 100">+100</button>
          <button @click="amount = Math.floor((balance || 0) / 2)">50%</button>
          <button @click="amount = balance">MAX</button>
        </div>

        <div class="field" style="margin-top: 0.9em;">
          <label class="field-label">Note (optionnel)</label>
          <input v-model="note" placeholder="ex: bière, raclette, dette…" maxlength="120" />
        </div>

        <button
          class="btn-primary btn-block send-btn"
          :disabled="sending || !canSend"
          @click="confirmSend"
        >
          {{ sending ? 'Envoi on-chain…' : `Envoyer ${amount || ''} CAMP` }}
        </button>

        <button class="btn-ghost btn-block" style="margin-top:.6em;" @click="restartScan">
          ← Scanner un autre QR
        </button>

        <div v-if="error" class="alert error">{{ error }}</div>
      </div>
    </template>

    <!-- ÉTAPE 3 : succès -->
    <template v-else-if="step === 'success'">
      <div class="success-pane">
        <div class="check">✓</div>
        <div class="success-title">Envoyé !</div>
        <div class="success-sub">{{ amount }} CAMP → @{{ scanned }}</div>
        <a
          v-if="txHash"
          :href="'https://sepolia.basescan.org/tx/' + txHash"
          target="_blank"
          rel="noreferrer"
          class="tx-link"
        >Voir la tx sur BaseScan →</a>
        <button class="btn-ghost btn-block" style="margin-top:1.4em;" @click="close">Fermer</button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { apiCall } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useWalletStore } from '@/stores/wallet'

const props = defineProps({
  balance: { type: Number, default: 0 },
  myUsername: { type: String, default: '' }
})
const emit = defineEmits(['close', 'sent'])

const auth = useAuthStore()
const wallet = useWalletStore()

const step = ref('scan')          // 'scan' | 'amount' | 'success'
const scanned = ref('')
const amount = ref(0)
const note = ref('')
const sending = ref(false)
const error = ref('')
const txHash = ref('')

const videoEl = ref(null)
const amountInput = ref(null)

let stream = null
let detector = null
let rafId = null
let active = true

const canSend = computed(
  () => !!scanned.value && amount.value > 0 && amount.value <= props.balance
)

function parseQr(raw) {
  if (!raw) return ''
  const trimmed = raw.trim()
  if (trimmed.toLowerCase().startsWith('camplong:')) {
    return trimmed.slice('camplong:'.length).trim()
  }
  // Fallback : on accepte aussi un username brut, tant qu'il n'a pas l'air d'une URL
  if (/^[a-zA-Z0-9_\-.]{2,40}$/.test(trimmed)) return trimmed
  return ''
}

async function startCamera() {
  error.value = ''
  if (!('BarcodeDetector' in window)) {
    error.value = "Ton navigateur ne supporte pas le scan QR. Sur iOS, utilise Safari 17+."
    return
  }
  try {
    detector = new window.BarcodeDetector({ formats: ['qr_code'] })
  } catch (_) {
    error.value = "Détecteur QR indisponible sur ce navigateur."
    return
  }

  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: 'environment' } },
      audio: false
    })
  } catch (e) {
    error.value = "Impossible d'accéder à la caméra. Autorise l'accès dans les réglages."
    return
  }

  await nextTick()
  if (!videoEl.value) return
  videoEl.value.srcObject = stream
  try { await videoEl.value.play() } catch (_) {}

  loop()
}

async function loop() {
  if (!active || !detector || !videoEl.value) return
  try {
    const barcodes = await detector.detect(videoEl.value)
    if (barcodes && barcodes.length) {
      const username = parseQr(barcodes[0].rawValue)
      if (username && username !== props.myUsername) {
        scanned.value = username
        await goToAmount()
        return
      }
    }
  } catch (_) { /* frame skipped */ }
  rafId = requestAnimationFrame(loop)
}

function stopCamera() {
  active = false
  if (rafId) { cancelAnimationFrame(rafId); rafId = null }
  if (stream) {
    stream.getTracks().forEach(t => t.stop())
    stream = null
  }
  if (videoEl.value) videoEl.value.srcObject = null
}

async function goToAmount() {
  stopCamera()
  step.value = 'amount'
  await nextTick()
  amountInput.value?.focus()
}

async function restartScan() {
  step.value = 'scan'
  amount.value = 0
  note.value = ''
  error.value = ''
  active = true
  await startCamera()
}

async function confirmSend() {
  if (!canSend.value) return
  error.value = ''
  sending.value = true
  try {
    const d = await apiCall('/transfer', {
      method: 'POST',
      token: auth.userToken,
      body: JSON.stringify({
        to_username: scanned.value,
        amount: amount.value,
        note: note.value
      })
    })
    txHash.value = d.tx_hash || ''
    step.value = 'success'
    await wallet.refresh()
    emit('sent', { to: scanned.value, amount: amount.value, tx_hash: txHash.value })
  } catch (e) {
    error.value = e.message
  } finally {
    sending.value = false
  }
}

function close() {
  stopCamera()
  emit('close')
}

onMounted(startCamera)
onBeforeUnmount(stopCamera)
</script>

<style scoped>
.scan-layer {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: #000;
  display: flex;
  flex-direction: column;
  animation: fadeIn 0.2s ease-out;
}
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.close-btn {
  position: absolute;
  top: max(1em, env(safe-area-inset-top));
  right: max(1em, env(safe-area-inset-right));
  z-index: 5;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.55);
  border: 1px solid rgba(255, 255, 255, 0.15);
  color: white;
  font-size: 1.1em;
  padding: 0;
  backdrop-filter: blur(10px);
}

/* ─── Étape SCAN ─── */
.cam-wrap {
  position: relative;
  flex: 1;
  overflow: hidden;
  background: #000;
}
.cam-video {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.viewfinder {
  position: absolute;
  inset: 0;
  pointer-events: none;
  display: grid;
  place-items: center;
}
.viewfinder::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(
      ellipse at center,
      transparent 0,
      transparent 38%,
      rgba(0, 0, 0, 0.55) 70%
    );
}
.vf-corner {
  position: absolute;
  width: 38px;
  height: 38px;
  border-color: var(--camp);
  border-style: solid;
  border-width: 0;
  box-shadow: 0 0 12px var(--camp-glow);
}
.vf-corner.tl { top: 22%; left: 12%; border-top-width: 3px; border-left-width: 3px; border-top-left-radius: 8px; }
.vf-corner.tr { top: 22%; right: 12%; border-top-width: 3px; border-right-width: 3px; border-top-right-radius: 8px; }
.vf-corner.bl { bottom: 32%; left: 12%; border-bottom-width: 3px; border-left-width: 3px; border-bottom-left-radius: 8px; }
.vf-corner.br { bottom: 32%; right: 12%; border-bottom-width: 3px; border-right-width: 3px; border-bottom-right-radius: 8px; }
.vf-laser {
  position: absolute;
  left: 14%;
  right: 14%;
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--camp), transparent);
  box-shadow: 0 0 12px var(--camp-glow);
  animation: laser 2.4s ease-in-out infinite;
}
@keyframes laser {
  0%   { top: 26%; opacity: 0; }
  20%  { opacity: 1; }
  80%  { opacity: 1; }
  100% { top: 64%; opacity: 0; }
}

.bottom-sheet {
  padding: 1.4em 1.25em max(1.4em, env(safe-area-inset-bottom));
  background: linear-gradient(180deg, transparent 0, rgba(7, 7, 10, 0.92) 30%);
  color: white;
}
.sheet-title {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 700;
  font-size: 1.2em;
  margin-bottom: 0.2em;
}
.sheet-sub {
  color: var(--text-2);
  font-size: 0.9em;
}

/* ─── Étape AMOUNT ─── */
.amount-pane {
  flex: 1;
  padding: max(4em, calc(env(safe-area-inset-top) + 3em)) 1.25em max(1.4em, env(safe-area-inset-bottom));
  background: var(--bg-0);
  color: var(--text-0);
  overflow-y: auto;
  max-width: 480px;
  margin: 0 auto;
  width: 100%;
}
.recipient-card {
  background:
    radial-gradient(circle at 90% 0%, rgba(255, 122, 0, 0.18), transparent 60%),
    var(--bg-1);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius);
  padding: 1.2em 1.3em;
  margin-bottom: 1.5em;
}
.recipient-eyebrow {
  color: var(--text-2);
  font-size: 0.78em;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  font-weight: 600;
  margin-bottom: 0.2em;
}
.recipient-name {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 700;
  font-size: 1.8em;
  letter-spacing: -0.02em;
}

.amount-wrap {
  position: relative;
}
.amount-wrap input {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-size: 2em;
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
  margin-top: 0.6em;
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
.send-btn {
  margin-top: 1.4em;
  padding: 1em 1.4em;
  font-size: 1.05em;
}

/* ─── Étape SUCCESS ─── */
.success-pane {
  flex: 1;
  padding: 4em 1.5em max(1.4em, env(safe-area-inset-bottom));
  background: var(--bg-0);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  max-width: 420px;
  margin: 0 auto;
  width: 100%;
}
.check {
  width: 88px;
  height: 88px;
  border-radius: 50%;
  background: var(--green-soft);
  color: var(--green);
  display: grid;
  place-items: center;
  font-size: 3em;
  font-weight: 700;
  box-shadow: 0 0 40px rgba(20, 224, 142, 0.35);
  margin-bottom: 1em;
}
.success-title {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-size: 1.8em;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin-bottom: 0.2em;
}
.success-sub {
  color: var(--text-2);
  font-size: 1.05em;
}
.tx-link {
  display: inline-block;
  margin-top: 1em;
  color: var(--camp);
  font-size: 0.92em;
}
</style>
