<template>
  <AppLayout>
    <main class="page fade-in">
      <div class="page-header">
        <router-link to="/casino" class="back-link">← Casino</router-link>
        <h1 class="page-title">🪙 Pile <span class="dim">ou</span> Face</h1>
        <p class="page-sub">
          Pile, je gagne. Face, tu perds. <span class="dim">(provably fair, vérifiable plus bas.)</span>
        </p>
      </div>

      <!-- Bandeau config dynamique : montre l'edge courant (modifié par l'admin) -->
      <div class="config-strip">
        <div class="config-item">
          <span class="k">Mise</span>
          <span class="v mono">{{ formatNum(casino.config.min_bet) }} – {{ formatNum(casino.config.max_bet) }} CAMP</span>
        </div>
        <div class="config-item">
          <span class="k">Edge maison</span>
          <span class="v mono">{{ casino.config.edge_pct }}%</span>
        </div>
        <div class="config-item">
          <span class="k">Tu gagnes</span>
          <span class="v mono accent">x{{ multiplierLabel }}</span>
        </div>
      </div>

      <!-- Carte principale : coin animé + form -->
      <div class="flip-card card">
        <div class="coin-stage" :class="{ flipping: animState === 'spinning', revealed: animState === 'revealed' }">
          <div class="coin" :class="coinClass" :style="coinStyle">
            <!-- PILE : la marque CamplongCoin -->
            <div class="face heads">
              <div class="face-inner">
                <div class="face-logo">C</div>
                <div class="face-label">PILE</div>
                <div class="face-stars">★ ★ ★</div>
              </div>
            </div>
            <!-- FACE : un visage stylisé (la "tête") -->
            <div class="face tails">
              <div class="face-inner">
                <div class="face-emoji">🐮</div>
                <div class="face-label">FACE</div>
                <div class="face-year">2026</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Résultat (apparaît après le flip) -->
        <transition name="fade-up">
          <div v-if="animState === 'revealed' && casino.lastResult" class="result-strip" :class="{ won: casino.lastResult.win, lost: !casino.lastResult.win }">
            <div class="r-icon">{{ casino.lastResult.win ? '🎉' : '💀' }}</div>
            <div class="r-text">
              <div class="r-title">
                <template v-if="casino.lastResult.win">
                  Tu gagnes <b class="mono">+{{ formatNum(casino.lastResult.payout) }} CAMP</b>
                </template>
                <template v-else>
                  Tu perds <b class="mono">-{{ formatNum(casino.lastResult.bet_amount) }} CAMP</b>
                </template>
              </div>
              <div class="r-sub">
                Tirage : <b>{{ casino.lastResult.outcome === 'heads' ? 'PILE' : 'FACE' }}</b>
                <span class="dim mono"> · seed#{{ casino.lastResult.id }}</span>
              </div>
            </div>
          </div>
        </transition>

        <!-- Formulaire de mise -->
        <div class="bet-controls">
          <div class="field">
            <label class="field-label">Mise (CAMP)</label>
            <div class="bet-input-row">
              <input
                type="number"
                v-model.number="bet"
                :min="casino.config.min_bet"
                :max="casino.config.max_bet"
                :disabled="casino.playing"
              />
              <div class="shortcuts">
                <button
                  v-for="amount in shortcuts"
                  :key="amount"
                  type="button"
                  class="chip"
                  :disabled="casino.playing"
                  @click="bet = clampBet(amount)"
                >
                  {{ amount === 'max' ? 'MAX' : amount }}
                </button>
              </div>
            </div>
            <div class="bet-hint mono dim">
              <span v-if="bet > balance" class="error-text">Solde insuffisant ({{ formatNum(balance) }} CAMP)</span>
              <span v-else-if="bet < casino.config.min_bet || bet > casino.config.max_bet" class="error-text">
                Hors limites ({{ casino.config.min_bet }} – {{ casino.config.max_bet }})
              </span>
              <span v-else>
                Gain potentiel :
                <b class="accent">{{ formatNum(potentialPayout) }} CAMP</b>
                <span class="dim"> (+{{ formatNum(potentialPayout - bet) }})</span>
              </span>
            </div>
          </div>

          <div class="field">
            <label class="field-label">Ton choix</label>
            <div class="choice-row">
              <button
                type="button"
                class="choice"
                :class="{ active: choice === 'heads' }"
                :disabled="casino.playing"
                @click="choice = 'heads'"
              >
                <span class="choice-icon">P</span>
                <span class="choice-label">PILE</span>
              </button>
              <button
                type="button"
                class="choice"
                :class="{ active: choice === 'tails' }"
                :disabled="casino.playing"
                @click="choice = 'tails'"
              >
                <span class="choice-icon">F</span>
                <span class="choice-label">FACE</span>
              </button>
            </div>
          </div>

          <button
            class="btn-primary btn-block flip-btn"
            :disabled="!canPlay"
            @click="flip"
          >
            {{ casino.playing ? 'Tirage en cours…' : '🎲 Lancer la pièce' }}
          </button>

          <div v-if="casino.error" class="alert error">{{ casino.error }}</div>
        </div>
      </div>

      <!-- Accordéon "Vérifier le tirage" (provably fair) -->
      <details v-if="casino.lastResult" class="verify card" :open="verifyOpen">
        <summary @click.prevent="verifyOpen = !verifyOpen">
          <span class="v-icon">🔬</span>
          Vérifier le tirage
          <span class="dim mono v-id">#{{ casino.lastResult.id }}</span>
        </summary>
        <div class="verify-body">
          <p class="dim">
            Le backend a publié <span class="mono">sha256(server_seed)</span> avant le flip,
            puis a révélé <span class="mono">server_seed</span> après. Tu peux vérifier toi-même
            que rien n'a été modifié.
          </p>
          <div class="kv">
            <div class="k">seed_hash <span class="dim">(publié avant)</span></div>
            <div class="v mono break">{{ casino.lastResult.seed_hash }}</div>
          </div>
          <div class="kv">
            <div class="k">server_seed <span class="dim">(révélé après)</span></div>
            <div class="v mono break">{{ casino.lastResult.server_seed }}</div>
          </div>
          <div class="kv">
            <div class="k">client_seed <span class="dim">(ton input)</span></div>
            <div class="v mono break">{{ casino.lastResult.client_seed }}</div>
          </div>
          <div class="kv">
            <div class="k">combined_hash</div>
            <div class="v mono break">{{ casino.lastResult.combined_hash }}</div>
          </div>
          <div class="kv">
            <div class="k">Formule</div>
            <div class="v mono small">
              outcome = (int(combined_hash[:8], 16) % 2 == 0) ? heads : tails
            </div>
          </div>
          <div v-if="casino.lastResult.tx_hash_lock" class="kv">
            <div class="k">Lock on-chain</div>
            <div class="v">
              <a :href="basescan(casino.lastResult.tx_hash_lock)" target="_blank" rel="noreferrer" class="mono">
                {{ shortTx(casino.lastResult.tx_hash_lock) }}
              </a>
            </div>
          </div>
          <div v-if="casino.lastResult.tx_hash_payout" class="kv">
            <div class="k">Payout on-chain</div>
            <div class="v">
              <a :href="basescan(casino.lastResult.tx_hash_payout)" target="_blank" rel="noreferrer" class="mono">
                {{ shortTx(casino.lastResult.tx_hash_payout) }}
              </a>
            </div>
          </div>
        </div>
      </details>

      <!-- Historique -->
      <section class="history-section">
        <div class="history-head">
          <h3 class="history-title">📜 Tes derniers flips</h3>
          <span v-if="casino.history.length" class="history-count mono dim">
            {{ casino.history.length }} flip{{ casino.history.length > 1 ? 's' : '' }}
          </span>
        </div>
        <div v-if="!casino.history.length" class="empty-state card">
          <div class="emoji">🪙</div>
          <div>Aucun flip pour l'instant. Lance ta première pièce !</div>
        </div>
        <div v-else class="history-list">
          <article
            v-for="r in pagedHistory"
            :key="r.id"
            class="history-row"
            :class="{ won: r.win, lost: !r.win }"
          >
            <div class="h-status">
              <span class="h-icon">{{ r.win ? '✓' : '✗' }}</span>
            </div>
            <div class="h-choice">
              <span class="dim">Joué</span>
              <b>{{ r.choice === 'heads' ? 'PILE' : 'FACE' }}</b>
            </div>
            <div class="h-outcome">
              <span class="dim">Sorti</span>
              <b>{{ r.outcome === 'heads' ? 'PILE' : 'FACE' }}</b>
            </div>
            <div class="h-amounts">
              <div class="mono dim">-{{ formatNum(r.bet_amount) }}</div>
              <div v-if="r.win" class="mono accent">+{{ formatNum(r.payout) }}</div>
            </div>
            <div class="h-ts mono dim">{{ formatShort(r.ts) }}</div>
          </article>
        </div>

        <!-- Pagination -->
        <nav v-if="totalPages > 1" class="pager">
          <button
            class="pager-btn"
            :disabled="historyPage <= 1"
            @click="historyPage--"
            aria-label="Page précédente"
          >←</button>
          <span class="pager-info mono">{{ historyPage }} / {{ totalPages }}</span>
          <button
            class="pager-btn"
            :disabled="historyPage >= totalPages"
            @click="historyPage++"
            aria-label="Page suivante"
          >→</button>
        </nav>
      </section>
    </main>
  </AppLayout>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import AppLayout from '@/components/layout/AppLayout.vue'
import { useCasinoStore } from '@/stores/casino'
import { useWalletStore } from '@/stores/wallet'
import { formatNum } from '@/config'

const casino = useCasinoStore()
const wallet = useWalletStore()

const bet = ref(10)
const choice = ref('heads')
const verifyOpen = ref(false)

// Pagination de l'historique (client-side : on fetch 50 du back, on
// tranche par pages de 10 ici).
const HISTORY_PAGE_SIZE = 10
const historyPage = ref(1)
const totalPages = computed(() =>
  Math.max(1, Math.ceil(casino.history.length / HISTORY_PAGE_SIZE)),
)
const pagedHistory = computed(() => {
  const start = (historyPage.value - 1) * HISTORY_PAGE_SIZE
  return casino.history.slice(start, start + HISTORY_PAGE_SIZE)
})
// Anim states : idle, spinning, revealed
const animState = ref('idle')
// Position cible (en degrés sur l'axe Y) - changée par flip()
const targetRotation = ref(0)

const balance = computed(() => Number(wallet.me?.balance || 0))

const shortcuts = computed(() => {
  const min = casino.config.min_bet || 1
  const max = casino.config.max_bet || 200
  return [min, 10, 50, Math.min(100, max), 'max']
})

const multiplierLabel = computed(() => {
  const m = casino.config.win_multiplier || 0
  return m ? m.toFixed(2) : '—'
})

const potentialPayout = computed(() => {
  return Math.floor((Number(bet.value) || 0) * (casino.config.win_multiplier || 0))
})

const canPlay = computed(() => {
  if (casino.playing) return false
  if (animState.value === 'spinning') return false
  const b = Number(bet.value) || 0
  if (b < casino.config.min_bet || b > casino.config.max_bet) return false
  if (b > balance.value) return false
  return true
})

// Anime la pièce vers la face PILE (rotation Y = 0) ou FACE (Y = 180)
const coinStyle = computed(() => {
  return { transform: `rotateY(${targetRotation.value}deg)` }
})
const coinClass = computed(() => ({
  spinning: animState.value === 'spinning',
}))

function clampBet(amount) {
  if (amount === 'max') return Math.min(balance.value, casino.config.max_bet)
  const v = Number(amount) || 0
  return Math.min(Math.max(v, casino.config.min_bet), casino.config.max_bet)
}

function basescan(hash) {
  return `https://sepolia.basescan.org/tx/${hash}`
}
function shortTx(hash) {
  if (!hash) return ''
  return `${hash.slice(0, 10)}…${hash.slice(-6)}`
}
function formatShort(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(d.getDate())}/${pad(d.getMonth() + 1)} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// Génère un client_seed aléatoire pour le tirage provably fair
function makeClientSeed() {
  // 16 bytes hex = 32 chars (assez pour la entropie front)
  const arr = new Uint8Array(16)
  ;(window.crypto || window.msCrypto).getRandomValues(arr)
  return Array.from(arr, (b) => b.toString(16).padStart(2, '0')).join('')
}

async function flip() {
  if (!canPlay.value) return
  animState.value = 'spinning'
  // Lance plusieurs tours visuels (multiple de 360) pendant que la requête tourne
  targetRotation.value = targetRotation.value + 360 * 6

  try {
    const result = await casino.play({
      bet: Number(bet.value),
      choice: choice.value,
      clientSeed: makeClientSeed(),
    })

    // Le nouveau flip est en tête de casino.history → on ramène l'user
    // sur la page 1 pour qu'il voie son résultat sans rien faire.
    historyPage.value = 1

    // Aligne la fin de rotation sur la face réelle :
    // PILE = 0deg, FACE = 180deg (modulo l'accumulation actuelle)
    const final = result.outcome === 'heads' ? 0 : 180
    const current = targetRotation.value
    const nearestMultipleOf360 = Math.round(current / 360) * 360
    targetRotation.value = nearestMultipleOf360 + final

    // Attend la fin de l'animation CSS (1.6s sur .coin) avant de "réveler"
    setTimeout(() => {
      animState.value = 'revealed'
    }, 1400)
  } catch (e) {
    // L'erreur est déjà dans casino.error
    animState.value = 'idle'
  }
}

watch(() => casino.lastResult, () => {
  // Ouvre l'accordéon automatiquement après le premier flip pour faire
  // découvrir le provably fair, puis l'utilisateur le ferme s'il veut.
  if (casino.lastResult && verifyOpen.value === false) {
    // pas d'auto-open, on laisse le user le découvrir.
  }
})

onMounted(async () => {
  await Promise.all([
    casino.loadConfig(),
    casino.loadHistory(),
    wallet.refresh(),
  ])
  // Ajuste la mise par défaut si elle est sous le min ou au-dessus du max
  bet.value = Math.min(Math.max(bet.value, casino.config.min_bet), casino.config.max_bet)
})
</script>

<style scoped>
.back-link {
  display: inline-block;
  color: var(--text-2);
  font-size: 0.88em;
  font-weight: 600;
  margin-bottom: 0.4em;
}
.back-link:hover {
  color: var(--camp);
  text-decoration: none;
}
.dim { color: var(--text-3); }
.accent { color: var(--camp); }

/* ─── Bandeau config ──────────────────────────────────── */
.config-strip {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.6em;
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 0.9em 1.2em;
  margin-bottom: 1.2em;
}
.config-item {
  display: flex;
  flex-direction: column;
  gap: 0.15em;
}
.config-item .k {
  font-size: 0.72em;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-2);
  font-weight: 600;
}
.config-item .v {
  font-size: 0.95em;
  font-weight: 600;
}

/* ─── Carte flip ──────────────────────────────────────── */
.flip-card {
  background:
    radial-gradient(circle at 80% 20%, rgba(245, 200, 66, 0.08), transparent 60%),
    var(--bg-1);
  border: 1px solid var(--border);
  padding: 2em 1.5em 1.5em;
  margin-bottom: 1.5em;
  position: relative;
  overflow: hidden;
}

.coin-stage {
  /* Une seule source de vérité pour la taille de la pièce. Toutes les
     tailles internes (logo, label, emoji) sont en em sur .face avec
     une font-size dérivée de --coin-size → tout scale ensemble quand
     la media query change la variable. */
  --coin-size: 140px;
  perspective: 900px;
  height: calc(var(--coin-size) + 40px);
  display: grid;
  place-items: center;
  margin-bottom: 1.4em;
  /* drop-shadow ici (et PAS sur .coin) : sur .coin ça crée un filter
     stacking-context qui casse transform-style: preserve-3d dans
     WebKit/Blink, et une des deux faces ne se rend plus. */
  filter: drop-shadow(0 12px 24px rgba(245, 200, 66, 0.35));
}
.coin {
  position: relative;
  width: var(--coin-size);
  height: var(--coin-size);
  transform-style: preserve-3d;
  -webkit-transform-style: preserve-3d;
  transform: rotateY(0deg);
  transition: transform 1.6s cubic-bezier(0.25, 0.7, 0.3, 1.05);
  will-change: transform;
}
.coin.spinning {
  animation: hover-bob 1.6s ease-in-out;
}
@keyframes hover-bob {
  0%, 100% { translate: 0 0; }
  50% { translate: 0 -18px; }
}

.face {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  display: grid;
  place-items: center;
  backface-visibility: hidden;
  -webkit-backface-visibility: hidden;
  color: #1a1308;
  border: 4px solid rgba(0, 0, 0, 0.25);
  box-shadow:
    inset 0 6px 18px rgba(255, 255, 255, 0.35),
    inset 0 -6px 18px rgba(0, 0, 0, 0.25);
  /* Base font-size proportionnelle au diamètre de la pièce :
     ~10% du diamètre. Le contenu (logo, label, stars) est sizé en em
     sur cette base donc tout reste cohérent quand --coin-size change. */
  font-size: calc(var(--coin-size) * 0.1);
}
.face.heads {
  background:
    radial-gradient(circle at 30% 30%, #ffe07a, transparent 60%),
    linear-gradient(135deg, var(--gold) 0%, #ff9700 100%);
  transform: rotateY(0deg);
}
.face.tails {
  background:
    radial-gradient(circle at 30% 30%, #c9b88a, transparent 60%),
    linear-gradient(135deg, #e0a93b 0%, #9b6a14 100%);
  transform: rotateY(180deg);
}
.face-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.05em;
  font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 800;
  letter-spacing: -0.02em;
  text-shadow:
    0 1px 0 rgba(255, 255, 255, 0.3),
    0 -1px 0 rgba(0, 0, 0, 0.15);
}
.face-logo {
  font-size: 3.4em;
  line-height: 1;
  color: #1a1308;
}
.face-emoji {
  font-size: 3em;
  line-height: 1;
  /* Cancel text-shadow on emoji for clarity */
  text-shadow: none;
  filter: drop-shadow(0 1px 0 rgba(0, 0, 0, 0.2));
}
.face-label {
  font-size: 0.85em;
  letter-spacing: 0.18em;
  margin-top: 0.3em;
  color: rgba(26, 19, 8, 0.85);
}
.face-stars,
.face-year {
  font-size: 0.55em;
  letter-spacing: 0.25em;
  color: rgba(26, 19, 8, 0.6);
  margin-top: 0.05em;
}

/* ─── Résultat ────────────────────────────────────────── */
.result-strip {
  display: flex;
  align-items: center;
  gap: 0.9em;
  padding: 0.9em 1.1em;
  border-radius: var(--radius-sm);
  margin-bottom: 1.2em;
  border: 1px solid;
}
.result-strip.won {
  background: var(--green-soft);
  border-color: rgba(20, 224, 142, 0.3);
}
.result-strip.lost {
  background: var(--red-soft);
  border-color: rgba(255, 69, 102, 0.3);
}
.r-icon { font-size: 1.8em; }
.r-title { font-size: 1.05em; font-weight: 600; }
.r-title b { color: inherit; }
.result-strip.won .r-title { color: var(--green); }
.result-strip.lost .r-title { color: var(--red); }
.r-sub { color: var(--text-2); font-size: 0.85em; margin-top: 0.15em; }

.fade-up-enter-active { transition: all 0.35s ease-out; }
.fade-up-enter-from { opacity: 0; transform: translateY(8px); }

/* ─── Form ────────────────────────────────────────────── */
.bet-controls .field { margin-bottom: 1em; }

.bet-input-row {
  display: flex;
  gap: 0.5em;
  align-items: stretch;
}
.bet-input-row input { flex: 1; }
.shortcuts {
  display: flex;
  gap: 0.3em;
  flex-wrap: wrap;
}
.chip {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 0 0.85em;
  color: var(--text-1);
  font-size: 0.85em;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
}
.chip:hover:not(:disabled) {
  border-color: var(--camp);
  color: var(--camp);
}
.bet-hint {
  margin-top: 0.45em;
  font-size: 0.82em;
}
.error-text { color: var(--red); }

.choice-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.6em;
}
.choice {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0.9em 0.5em;
  color: var(--text-1);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.3em;
  transition: all 0.15s;
}
.choice:hover:not(:disabled) {
  border-color: var(--border-strong);
}
.choice.active {
  background:
    radial-gradient(circle at 50% 0%, rgba(245, 200, 66, 0.15), transparent 60%),
    var(--bg-2);
  border-color: var(--gold);
  color: var(--gold);
  box-shadow: 0 0 0 3px rgba(245, 200, 66, 0.12);
}
.choice-icon {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 800;
  font-size: 2em;
  line-height: 1;
}
.choice-label {
  font-size: 0.8em;
  font-weight: 700;
  letter-spacing: 0.1em;
}

.flip-btn {
  margin-top: 0.4em;
  font-size: 1.05em;
  padding: 1em 1.4em;
}

/* ─── Vérification (provably fair) ────────────────────── */
.verify {
  margin-bottom: 1.5em;
}
.verify summary {
  cursor: pointer;
  list-style: none;
  display: flex;
  align-items: center;
  gap: 0.6em;
  padding: 0.2em 0;
}
.verify summary::-webkit-details-marker { display: none; }
.verify summary:hover { color: var(--camp); }
.v-icon { font-size: 1.2em; }
.v-id { margin-left: auto; font-size: 0.85em; }
.verify-body { margin-top: 1em; }
.verify-body .dim { font-size: 0.88em; margin-bottom: 0.8em; }
.kv {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4em 1em;
  padding: 0.5em 0;
  border-bottom: 1px dashed var(--border);
  font-size: 0.9em;
}
.kv:last-child { border-bottom: none; }
.kv .k {
  flex-basis: 180px;
  color: var(--text-2);
  font-weight: 600;
}
.kv .v {
  flex: 1;
  word-break: break-all;
  color: var(--text-0);
}
.kv .v.break { word-break: break-all; }
.kv .v.small { font-size: 0.85em; }

/* ─── Historique ──────────────────────────────────────── */
.history-section { margin-top: 1.5em; }
.history-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.6em;
  margin-bottom: 0.8em;
}
.history-count { font-size: 0.78em; }

/* Pagination compacte */
.pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.6em;
  margin-top: 0.8em;
}
.pager-btn {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-1);
  font-weight: 700;
  font-size: 1em;
  padding: 0;
  width: 40px;
  height: 40px;
  min-height: 40px;
  cursor: pointer;
  display: grid;
  place-items: center;
}
.pager-btn:hover:not(:disabled) {
  border-color: var(--camp);
  color: var(--camp);
}
.pager-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}
.pager-info {
  font-size: 0.85em;
  color: var(--text-2);
  min-width: 4ch;
  text-align: center;
}

.history-title {
  font-size: 1.1em;
  margin: 0;
}
.history-list {
  display: flex;
  flex-direction: column;
  gap: 0.4em;
}
.history-row {
  display: grid;
  grid-template-columns: 32px 1fr 1fr 1fr auto;
  align-items: center;
  gap: 0.6em;
  padding: 0.65em 0.9em;
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 0.9em;
}
.history-row.won { border-left: 3px solid var(--green); }
.history-row.lost { border-left: 3px solid var(--red); opacity: 0.85; }
.h-status .h-icon {
  display: inline-grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  font-weight: 800;
}
.history-row.won .h-icon { background: var(--green-soft); color: var(--green); }
.history-row.lost .h-icon { background: var(--red-soft); color: var(--red); }
.h-choice, .h-outcome { display: flex; flex-direction: column; gap: 0.1em; font-size: 0.85em; }
.h-choice .dim, .h-outcome .dim {
  font-size: 0.72em;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.h-amounts { display: flex; flex-direction: column; align-items: flex-end; font-size: 0.85em; }
.h-ts { font-size: 0.78em; }

@media (max-width: 640px) {
  .config-strip { grid-template-columns: 1fr; gap: 0.4em; padding: 0.7em 0.9em; }
  .config-item { flex-direction: row; justify-content: space-between; }
  .history-row { grid-template-columns: 28px 1fr 1fr auto; }
  .h-ts { display: none; }
  /* Une seule variable à changer : .coin et .face suivent automatiquement
     (largeur, hauteur, font-size base et donc logo/label/stars en em). */
  .coin-stage { --coin-size: 110px; }
}

@media (max-width: 380px) {
  /* iPhone SE / petits Android : on rétrécit encore la pièce.
     Tout le contenu (logo, label, emoji) suit via la base em. */
  .coin-stage { --coin-size: 92px; }
  .face-stars, .face-year { display: none; }   /* trop chargé sur si petit */
}
</style>
