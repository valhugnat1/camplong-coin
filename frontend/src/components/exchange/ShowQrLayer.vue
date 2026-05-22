<template>
  <div class="qr-layer" @click.self="$emit('close')">
    <button class="close-btn" @click="$emit('close')" aria-label="Fermer">✕</button>

    <div class="qr-content">
      <div class="qr-eyebrow">Reçois des CAMP</div>
      <div class="qr-title">@{{ username }}</div>
      <div class="qr-sub">Fais scanner ce QR avec l'app Camplong</div>

      <div class="qr-frame">
        <img v-if="dataUrl" :src="dataUrl" class="qr-img" alt="QR code" />
        <div v-else class="qr-skeleton">Génération…</div>
      </div>

      <button class="copy-pill" @click="copyHandle">
        <span v-if="copied">✓ Copié</span>
        <span v-else>📋 Copier @{{ username }}</span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import QRCode from 'qrcode'

const props = defineProps({
  username: { type: String, required: true }
})
defineEmits(['close'])

const dataUrl = ref('')
const copied = ref(false)

async function generate() {
  if (!props.username) return
  const payload = `camplong:${props.username}`
  dataUrl.value = await QRCode.toDataURL(payload, {
    errorCorrectionLevel: 'M',
    margin: 2,
    width: 520,
    color: { dark: '#0d0d12', light: '#ffffff' }
  })
}

async function copyHandle() {
  try {
    await navigator.clipboard.writeText(props.username)
    copied.value = true
    setTimeout(() => (copied.value = false), 1500)
  } catch (_) {}
}

watch(() => props.username, generate)
onMounted(generate)
</script>

<style scoped>
.qr-layer {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(7, 7, 10, 0.96);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5em;
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
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: var(--bg-2);
  border: 1px solid var(--border);
  color: var(--text-0);
  font-size: 1.1em;
  padding: 0;
}

.qr-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.6em;
  width: 100%;
  max-width: 420px;
}

.qr-eyebrow {
  color: var(--text-2);
  font-size: 0.8em;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-weight: 600;
}
.qr-title {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 700;
  font-size: 2em;
  letter-spacing: -0.02em;
}
.qr-sub {
  color: var(--text-2);
  font-size: 0.95em;
  margin-bottom: 0.8em;
  text-align: center;
}

.qr-frame {
  background: white;
  padding: 1.1em;
  border-radius: 20px;
  box-shadow:
    0 0 0 1px var(--border),
    0 20px 60px -20px var(--camp-glow);
  width: min(85vw, 360px);
  aspect-ratio: 1;
  display: grid;
  place-items: center;
}
.qr-img {
  width: 100%;
  height: 100%;
  display: block;
  image-rendering: pixelated;
}
.qr-skeleton {
  color: #999;
  font-size: 0.9em;
}

.copy-pill {
  margin-top: 1.2em;
  padding: 0.75em 1.4em;
  border-radius: 999px;
  background: var(--bg-2);
  border: 1px solid var(--border);
  color: var(--text-0);
  font-weight: 600;
  font-size: 0.95em;
}
.copy-pill:active {
  background: var(--bg-3);
}
</style>
