<template>
  <div class="login-wrap" :class="{ splashing }">
    <!-- Coin 3D en background -->
    <div class="bg-coin-wrap" aria-hidden="true">
      <!-- Halo statique (ne tourne pas) -->
      <div class="bg-coin-glow"></div>

      <!-- Rotor : tout ce qui tourne avec la pièce -->
      <div class="bg-coin-rotor">
        <!-- TRANCHE : 20 panneaux disposés en cercle autour de l'axe Z -->
        <div
          v-for="n in 20"
          :key="`edge-${n}`"
          class="coin-edge"
          :style="{ '--i': n - 1 }"
        ></div>

        <!-- Face avant : SVG translaté légèrement en avant -->
        <svg
          class="coin-face front"
          viewBox="-100 -100 200 200"
          xmlns="http://www.w3.org/2000/svg"
        >
          <defs>
            <linearGradient id="face-lite-f" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stop-color="#ffa64d" />
              <stop offset="100%" stop-color="#ff7a00" />
            </linearGradient>
            <linearGradient id="face-mid-f" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stop-color="#ff7a00" />
              <stop offset="100%" stop-color="#d35a00" />
            </linearGradient>
            <linearGradient id="face-dark-f" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stop-color="#c44d00" />
              <stop offset="100%" stop-color="#7a2e00" />
            </linearGradient>
            <linearGradient id="c-lite-f" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#fff8ee" />
              <stop offset="100%" stop-color="#ffe5c4" />
            </linearGradient>
            <linearGradient id="c-mid-f" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#ffe5c4" />
              <stop offset="100%" stop-color="#ffcc94" />
            </linearGradient>
            <linearGradient id="c-dark-f" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#ffcc94" />
              <stop offset="100%" stop-color="#ffa564" />
            </linearGradient>
          </defs>

          <!-- 16 facettes -->
          <polygon points="0,0  0,-78  29.85,-72.05" fill="url(#face-lite-f)" />
          <polygon
            points="0,0  29.85,-72.05  55.15,-55.15"
            fill="url(#face-lite-f)"
          />
          <polygon
            points="0,0  55.15,-55.15  72.05,-29.85"
            fill="url(#face-mid-f)"
          />
          <polygon points="0,0  72.05,-29.85  78,0" fill="url(#face-mid-f)" />
          <polygon points="0,0  78,0  72.05,29.85" fill="url(#face-mid-f)" />
          <polygon
            points="0,0  72.05,29.85  55.15,55.15"
            fill="url(#face-dark-f)"
          />
          <polygon
            points="0,0  55.15,55.15  29.85,72.05"
            fill="url(#face-dark-f)"
          />
          <polygon points="0,0  29.85,72.05  0,78" fill="url(#face-dark-f)" />
          <polygon points="0,0  0,78  -29.85,72.05" fill="url(#face-dark-f)" />
          <polygon
            points="0,0  -29.85,72.05  -55.15,55.15"
            fill="url(#face-dark-f)"
          />
          <polygon
            points="0,0  -55.15,55.15  -72.05,29.85"
            fill="url(#face-mid-f)"
          />
          <polygon points="0,0  -72.05,29.85  -78,0" fill="url(#face-mid-f)" />
          <polygon points="0,0  -78,0  -72.05,-29.85" fill="url(#face-mid-f)" />
          <polygon
            points="0,0  -72.05,-29.85  -55.15,-55.15"
            fill="url(#face-lite-f)"
          />
          <polygon
            points="0,0  -55.15,-55.15  -29.85,-72.05"
            fill="url(#face-lite-f)"
          />
          <polygon
            points="0,0  -29.85,-72.05  0,-78"
            fill="url(#face-lite-f)"
          />

          <circle
            cx="0"
            cy="0"
            r="78"
            fill="none"
            stroke="#5c2400"
            stroke-width="0.6"
            opacity="0.5"
          />

          <!-- C low-poly -->
          <polygon
            points="-35,-40  20,-40  28,-32  -18,-32"
            fill="url(#c-lite-f)"
          />
          <polygon
            points="-18,-32  28,-32  22,-20  -22,-20"
            fill="url(#c-lite-f)"
          />
          <polygon
            points="-22,-20  22,-20  10,-12  -22,-12"
            fill="url(#c-mid-f)"
          />
          <polygon
            points="-35,-40  -18,-32  -22,-20  -42,-28"
            fill="url(#c-mid-f)"
          />
          <polygon
            points="-42,-28  -22,-20  -22,-12  -48,-15"
            fill="url(#c-dark-f)"
          />
          <polygon
            points="-48,-15  -22,-12  -22,0   -50,0"
            fill="url(#c-dark-f)"
          />
          <polygon
            points="-50,0    -22,0   -22,12   -48,15"
            fill="url(#c-dark-f)"
          />
          <polygon
            points="-48,15   -22,12  -22,20   -42,28"
            fill="url(#c-mid-f)"
          />
          <polygon
            points="-42,28   -22,20  -18,32   -35,40"
            fill="url(#c-mid-f)"
          />
          <polygon
            points="-22,12   10,12  22,20   -22,20"
            fill="url(#c-mid-f)"
          />
          <polygon
            points="-22,20   22,20  28,32   -18,32"
            fill="url(#c-lite-f)"
          />
          <polygon
            points="-18,32   28,32  20,40   -35,40"
            fill="url(#c-lite-f)"
          />
        </svg>

        <!-- Face arrière : même SVG, rotated 180° → C reste lisible quand visible -->
        <svg
          class="coin-face back"
          viewBox="-100 -100 200 200"
          xmlns="http://www.w3.org/2000/svg"
        >
          <defs>
            <linearGradient id="face-lite-b" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stop-color="#ffa64d" />
              <stop offset="100%" stop-color="#ff7a00" />
            </linearGradient>
            <linearGradient id="face-mid-b" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stop-color="#ff7a00" />
              <stop offset="100%" stop-color="#d35a00" />
            </linearGradient>
            <linearGradient id="face-dark-b" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stop-color="#c44d00" />
              <stop offset="100%" stop-color="#7a2e00" />
            </linearGradient>
            <linearGradient id="c-lite-b" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#fff8ee" />
              <stop offset="100%" stop-color="#ffe5c4" />
            </linearGradient>
            <linearGradient id="c-mid-b" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#ffe5c4" />
              <stop offset="100%" stop-color="#ffcc94" />
            </linearGradient>
            <linearGradient id="c-dark-b" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#ffcc94" />
              <stop offset="100%" stop-color="#ffa564" />
            </linearGradient>
          </defs>

          <polygon points="0,0  0,-78  29.85,-72.05" fill="url(#face-lite-b)" />
          <polygon
            points="0,0  29.85,-72.05  55.15,-55.15"
            fill="url(#face-lite-b)"
          />
          <polygon
            points="0,0  55.15,-55.15  72.05,-29.85"
            fill="url(#face-mid-b)"
          />
          <polygon points="0,0  72.05,-29.85  78,0" fill="url(#face-mid-b)" />
          <polygon points="0,0  78,0  72.05,29.85" fill="url(#face-mid-b)" />
          <polygon
            points="0,0  72.05,29.85  55.15,55.15"
            fill="url(#face-dark-b)"
          />
          <polygon
            points="0,0  55.15,55.15  29.85,72.05"
            fill="url(#face-dark-b)"
          />
          <polygon points="0,0  29.85,72.05  0,78" fill="url(#face-dark-b)" />
          <polygon points="0,0  0,78  -29.85,72.05" fill="url(#face-dark-b)" />
          <polygon
            points="0,0  -29.85,72.05  -55.15,55.15"
            fill="url(#face-dark-b)"
          />
          <polygon
            points="0,0  -55.15,55.15  -72.05,29.85"
            fill="url(#face-mid-b)"
          />
          <polygon points="0,0  -72.05,29.85  -78,0" fill="url(#face-mid-b)" />
          <polygon points="0,0  -78,0  -72.05,-29.85" fill="url(#face-mid-b)" />
          <polygon
            points="0,0  -72.05,-29.85  -55.15,-55.15"
            fill="url(#face-lite-b)"
          />
          <polygon
            points="0,0  -55.15,-55.15  -29.85,-72.05"
            fill="url(#face-lite-b)"
          />
          <polygon
            points="0,0  -29.85,-72.05  0,-78"
            fill="url(#face-lite-b)"
          />

          <circle
            cx="0"
            cy="0"
            r="78"
            fill="none"
            stroke="#5c2400"
            stroke-width="0.6"
            opacity="0.5"
          />

          <polygon
            points="-35,-40  20,-40  28,-32  -18,-32"
            fill="url(#c-lite-b)"
          />
          <polygon
            points="-18,-32  28,-32  22,-20  -22,-20"
            fill="url(#c-lite-b)"
          />
          <polygon
            points="-22,-20  22,-20  10,-12  -22,-12"
            fill="url(#c-mid-b)"
          />
          <polygon
            points="-35,-40  -18,-32  -22,-20  -42,-28"
            fill="url(#c-mid-b)"
          />
          <polygon
            points="-42,-28  -22,-20  -22,-12  -48,-15"
            fill="url(#c-dark-b)"
          />
          <polygon
            points="-48,-15  -22,-12  -22,0   -50,0"
            fill="url(#c-dark-b)"
          />
          <polygon
            points="-50,0    -22,0   -22,12   -48,15"
            fill="url(#c-dark-b)"
          />
          <polygon
            points="-48,15   -22,12  -22,20   -42,28"
            fill="url(#c-mid-b)"
          />
          <polygon
            points="-42,28   -22,20  -18,32   -35,40"
            fill="url(#c-mid-b)"
          />
          <polygon
            points="-22,12   10,12  22,20   -22,20"
            fill="url(#c-mid-b)"
          />
          <polygon
            points="-22,20   22,20  28,32   -18,32"
            fill="url(#c-lite-b)"
          />
          <polygon
            points="-18,32   28,32  20,40   -35,40"
            fill="url(#c-lite-b)"
          />
        </svg>
      </div>
    </div>

    <!-- Splash message (visible pendant le chargement) -->
    <div v-if="splashing" class="splash-msg">
      <div class="splash-welcome">Bienvenue, {{ form.username }}</div>
      <div class="splash-sub">Entrée dans le CAMP…</div>
    </div>

    <!-- Login card -->
    <div class="login-card" :class="{ 'fade-out': splashing }">
      <div class="login-logo">
        <div class="logo-mark">C</div>
        <div>
          <div class="logo-text">CAMPLONGCOIN</div>
          <div class="sub-brand">base sepolia · custodial</div>
        </div>
      </div>

      <h1 class="login-title">Bienvenue,<br />futur millionnaire.</h1>
      <p class="login-sub">
        Connecte-toi pour accéder à ton wallet.
        <b>Ton 9-to-5 ne sait pas encore ce qui l'attend.</b>
      </p>

      <div v-if="redirectInfo" class="alert info" style="font-size: 0.88em">
        ↩ Connexion requise pour accéder à
        <span class="mono">{{ redirectInfo }}</span>
      </div>

      <div class="field">
        <label class="field-label">Pseudo</label>
        <input
          v-model="form.username"
          placeholder="ex: Hugo"
          autocomplete="username"
          @keyup.enter="submit"
        />
      </div>

      <div class="field">
        <label class="field-label">Mot de passe</label>
        <input
          v-model="form.password"
          type="password"
          placeholder="••••••••"
          autocomplete="current-password"
          @keyup.enter="submit"
        />
      </div>

      <button class="btn-primary btn-block" @click="submit" :disabled="loading">
        {{ loading ? "Connexion…" : "Entrer dans le CAMP →" }}
      </button>

      <div v-if="error" class="alert error">{{ error }}</div>

      <div class="footer">
        <span
          >Pas de compte&nbsp;? Demande à l'admin. C'est encore artisanal.</span
        >
        <router-link to="/admin/login" class="admin-link"
          >Accès admin →</router-link
        >
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, computed } from "vue";
import { useRouter, useRoute } from "vue-router";
import { apiCall } from "@/api/client";
import { useAuthStore } from "@/stores/auth";
import { useWalletStore } from "@/stores/wallet";

const router = useRouter();
const route = useRoute();
const auth = useAuthStore();
const wallet = useWalletStore();

const form = reactive({ username: "", password: "" });
const loading = ref(false);
const error = ref("");
const splashing = ref(false);

const redirectInfo = computed(() => {
  const r = route.query.redirect;
  return r && r !== "/wallet" ? String(r) : "";
});

async function submit() {
  error.value = "";
  loading.value = true;
  try {
    const d = await apiCall("/login", {
      method: "POST",
      body: JSON.stringify(form),
    });
    auth.setUserToken(d.token);
    await wallet.refresh();
    const target = String(route.query.redirect || "/wallet");
    splashing.value = true;
    loading.value = false;
    await new Promise((resolve) => setTimeout(resolve, 2400));
    router.push(target);
  } catch (e) {
    error.value = e.message;
    loading.value = false;
  }
}
</script>

<style scoped>
.login-wrap {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2em 1em;
  position: relative;
  overflow: hidden;
}

/* ════════════════════════════════════════
   COIN BACKGROUND : taille, position, halo
   ════════════════════════════════════════ */

.bg-coin-wrap {
  /* Variable maître pour toutes les dimensions du coin */
  --coin-size: min(100vmin, 820px);
  /* Demi-épaisseur de la pièce (= distance des faces au plan central) */
  --coin-half-thickness: calc(var(--coin-size) * 0.045);
  /* Rayon de la pièce */
  --coin-radius: calc(var(--coin-size) * 0.39);
  /* Largeur d'un panneau (chord pour 20 panneaux) ≈ 2R·sin(π/20) ≈ 0.31·R */
  --edge-chord: calc(var(--coin-size) * 0.122);

  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: var(--coin-size);
  height: var(--coin-size);
  z-index: 0;
  pointer-events: none;
  perspective: 1400px;
  perspective-origin: 50% 50%;
}

.bg-coin-glow {
  position: absolute;
  inset: 0;
  background: radial-gradient(
    circle at 50% 50%,
    rgba(255, 122, 0, 0.3) 0%,
    rgba(255, 122, 0, 0.1) 30%,
    rgba(255, 122, 0, 0.03) 55%,
    transparent 75%
  );
  pointer-events: none;
  filter: blur(20px);
}

/* ════════════════════════════════════════
   ROTOR : applique la rotation 3D
   ════════════════════════════════════════ */

.bg-coin-rotor {
  position: absolute;
  inset: 0;
  transform-style: preserve-3d;
  animation: coin-spin 18s linear infinite;
}

@keyframes coin-spin {
  from {
    transform: rotateY(0deg);
  }
  to {
    transform: rotateY(360deg);
  }
}

/* ════════════════════════════════════════
   MODE SPLASH (après login réussi)
   ════════════════════════════════════════ */

.login-wrap.splashing .bg-coin-rotor {
  animation: coin-spin 1.4s cubic-bezier(0.4, 0.05, 0.4, 1) infinite;
}

.login-wrap.splashing .bg-coin-wrap {
  animation: coin-pop 0.7s cubic-bezier(0.34, 1.4, 0.64, 1) forwards;
}

.login-wrap.splashing .coin-face {
  opacity: 1;
  filter: drop-shadow(0 30px 80px rgba(255, 122, 0, 0.6));
  transition: opacity 0.5s ease, filter 0.5s ease;
}

.login-wrap.splashing .coin-edge {
  opacity: 1;
  transition: opacity 0.5s ease;
}

.login-wrap.splashing .bg-coin-glow {
  animation: glow-pulse 1.6s ease-in-out infinite;
}

@keyframes coin-pop {
  0% {
    transform: translate(-50%, -50%) scale(1);
  }
  60% {
    transform: translate(-50%, -50%) scale(1.08);
  }
  100% {
    transform: translate(-50%, -50%) scale(1.04);
  }
}

@keyframes glow-pulse {
  0%, 100% {
    opacity: 1;
    filter: blur(20px);
  }
  50% {
    opacity: 1.4;
    filter: blur(28px);
  }
}

@media (prefers-reduced-motion: reduce) {
  .login-wrap.splashing .bg-coin-rotor,
  .login-wrap.splashing .bg-coin-wrap,
  .login-wrap.splashing .bg-coin-glow {
    animation: none;
  }
}

/* ════════════════════════════════════════
   SPLASH MESSAGE
   ════════════════════════════════════════ */

.splash-msg {
  position: absolute;
  bottom: 12%;
  left: 50%;
  transform: translateX(-50%);
  z-index: 2;
  text-align: center;
  pointer-events: none;
  animation: splash-msg-in 0.6s ease 0.15s both;
}

.splash-welcome {
  font-size: 1.5em;
  font-weight: 700;
  color: #fff;
  letter-spacing: 0.02em;
  text-shadow:
    0 2px 8px rgba(0, 0, 0, 0.9),
    0 0 24px rgba(255, 122, 0, 0.5);
}

.splash-sub {
  font-size: 0.85em;
  color: rgba(255, 255, 255, 0.7);
  margin-top: 0.4em;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.9);
  animation: splash-sub-blink 1.4s ease-in-out infinite;
}

@keyframes splash-msg-in {
  from {
    opacity: 0;
    transform: translate(-50%, 10px);
  }
  to {
    opacity: 1;
    transform: translate(-50%, 0);
  }
}

@keyframes splash-sub-blink {
  0%, 100% {
    opacity: 0.6;
  }
  50% {
    opacity: 1;
  }
}

@media (prefers-reduced-motion: reduce) {
  .bg-coin-rotor {
    animation: none;
    transform: rotateY(-25deg);
  }
}

/* ════════════════════════════════════════
   FACES (avant + arrière)
   ════════════════════════════════════════ */

.coin-face {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  backface-visibility: hidden;
  opacity: 0.65;
  filter: drop-shadow(0 20px 50px rgba(255, 122, 0, 0.25));
}

.coin-face.front {
  /* Face avant légèrement en avant sur Z */
  transform: translateZ(var(--coin-half-thickness));
}

.coin-face.back {
  /* Face arrière : tournée 180° autour de Y pour que :
     - Quand le rotor est à 0°, elle pointe vers l'arrière (cachée par backface-visibility)
     - Quand le rotor est à 180°, elle pointe vers nous et le C s'affiche LISIBLE
     Note : après rotateY(180), translateZ déplace vers -Z dans le monde */
  transform: rotateY(180deg) translateZ(var(--coin-half-thickness));
}

/* ════════════════════════════════════════
   PANNEAUX D'ÉPAISSEUR
   20 lames disposées en cercle autour de Z
   ════════════════════════════════════════ */

.coin-edge {
  position: absolute;
  top: 50%;
  left: 50%;
  /* IMPORTANT : à cause de l'ordre des transformations (rotateY(90) à droite
     = appliqué en premier), l'axe X local du div finit dans la direction Z monde,
     et l'axe Y local finit dans la direction tangentielle.
     Donc width correspond à l'épaisseur de la pièce, height à la chord. */
  width: calc(var(--coin-half-thickness) * 2);
  height: var(--edge-chord);
  margin-left: calc(var(--coin-half-thickness) * -1);
  margin-top: calc(var(--edge-chord) * -0.5);
  /* Dégradé horizontal (sur width = épaisseur Z) :
     centre clair, bords foncés → effet "highlight au milieu de la tranche" */
  background: linear-gradient(
    to right,
    #5c2400 0%,
    #c44d00 35%,
    #ff7a00 50%,
    #c44d00 65%,
    #5c2400 100%
  );
  backface-visibility: hidden;
  opacity: 0.7;
  transform: rotateZ(calc(var(--i) * 18deg)) translateX(var(--coin-radius))
    rotateY(90deg);
}

/* ════════════════════════════════════════
   LOGIN CARD
   ════════════════════════════════════════ */

.login-card {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 420px;
  background: linear-gradient(
    180deg,
    rgba(19, 19, 26, 0.2) 0%,
    rgba(13, 13, 18, 0.4) 100%
  );
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 2.5em 2em;
  overflow: hidden;
  box-shadow:
    0 25px 70px -20px rgba(0, 0, 0, 0.8),
    0 0 0 1px rgba(255, 255, 255, 0.05) inset; /* Bordure interne très légèrement accentuée */
  transition: opacity 0.5s ease, transform 0.5s ease, filter 0.5s ease;
}
.login-card.fade-out {
  opacity: 0;
  transform: scale(0.92);
  filter: blur(8px);
  pointer-events: none;
}
.login-title,
.login-sub,
.field-label,
.logo-text,
.sub-brand {
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.6);
}
.login-card::before {
  content: "";
  position: absolute;
  top: -1px;
  left: 50%;
  transform: translateX(-50%);
  width: 60%;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--camp), transparent);
}

.login-logo {
  display: flex;
  align-items: center;
  gap: 0.6em;
  margin-bottom: 1.5em;
}
.sub-brand {
  color: var(--text-3);
  font-size: 0.78em;
  letter-spacing: 0.05em;
}

.login-title {
  font-size: 2em;
  margin-bottom: 0.3em;
  line-height: 1.1;
}
.login-sub {
  color: var(--text-2);
  font-size: 0.95em;
  margin-bottom: 2em;
}
.login-sub b {
  color: var(--camp);
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.9);
}

.mono {
  font-family: "JetBrains Mono", monospace;
}

.footer {
  text-align: center;
  color: var(--text-3);
  font-size: 0.78em;
  margin-top: 2em;
  display: flex;
  flex-direction: column;
  gap: 0.5em;
}
.admin-link {
  color: var(--text-2);
  font-weight: 600;
}
.admin-link:hover {
  color: var(--camp);
  text-decoration: none;
}

.login-sub,
.sub-brand,
.field-label,
.footer {
  color: rgba(255, 255, 255, 0.9) !important;
  font-weight: 500;
  text-shadow:
    0 1px 3px rgba(0, 0, 0, 0.9),
    0 2px 8px rgba(0, 0, 0, 0.8);
}
</style>
