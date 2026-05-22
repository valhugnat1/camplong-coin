<template>
  <AppLayout>
    <main class="page fade-in">
      <div class="page-header">
        <router-link to="/casino" class="back-link">← Casino</router-link>
        <h1 class="page-title">🎰 Machine à sous</h1>
        <p class="page-sub">
          3 rouleaux, payline centrale. Trois symboles identiques sur la ligne du milieu.
          <span class="dim">RTP théorique {{ slotsConfig.rtp_theoretical_pct }}%.</span>
        </p>
      </div>

      <!-- Bandeau config -->
      <div class="config-strip">
        <div class="config-item">
          <span class="k">Mise</span>
          <span class="v mono">{{ formatNum(slotsConfig.min_bet) }} – {{ formatNum(slotsConfig.max_bet) }}</span>
        </div>
        <div class="config-item">
          <span class="k">Edge</span>
          <span class="v mono">{{ edgePct }}%</span>
        </div>
        <div class="config-item">
          <span class="k">Solde</span>
          <span class="v mono accent">{{ formatNum(balance) }}</span>
        </div>
      </div>

      <!-- Machine -->
      <div class="machine card">
        <div class="reels-frame">
          <div class="reels">
            <div
              v-for="i in 3"
              :key="i"
              class="reel"
              :class="{ 'win-glow': reelWon[i-1] }"
            >
              <div
                class="reel-strip"
                :ref="(el) => { if (el) reelRefs[i-1] = el }"
              >
                <span
                  v-for="(s, j) in reelStrips[i-1]"
                  :key="j"
                  class="reel-symbol"
                >{{ s }}</span>
              </div>
            </div>
          </div>
          <!-- Payline au milieu (ligne du centre) -->
          <div class="payline"></div>
        </div>

        <!-- Résultat -->
        <transition name="fade-up">
          <div v-if="displayResult" class="result-strip" :class="{ won: displayResult.win, lost: !displayResult.win }">
            <div class="r-emoji">{{ displayResult.win ? '🎉' : '🤷' }}</div>
            <div class="r-text">
              <div class="r-title">
                <template v-if="displayResult.win">
                  <b class="mono">+{{ formatNum(displayResult.payout) }} CAMP</b>
                  <span class="dim"> ×{{ displayResult.multiplier }}</span>
                </template>
                <template v-else>
                  <b class="mono red">-{{ formatNum(displayResult.bet_amount) }}</b>
                </template>
              </div>
              <div class="r-sub">
                {{ displayResult.reels.map(r => r.emoji).join(' · ') }}
              </div>
            </div>
          </div>
        </transition>

        <!-- Form de mise -->
        <div class="controls">
          <div class="field">
            <label class="field-label">Mise (CAMP)</label>
            <div class="bet-input-row">
              <input
                type="number"
                inputmode="numeric"
                v-model.number="bet"
                :min="slotsConfig.min_bet"
                :max="slotsConfig.max_bet"
                :disabled="isSpinning"
              />
              <div class="shortcuts">
                <button
                  v-for="amount in shortcuts"
                  :key="amount"
                  type="button"
                  class="chip"
                  :disabled="isSpinning"
                  @click="bet = clampBet(amount)"
                >
                  {{ amount === 'max' ? 'MAX' : amount }}
                </button>
              </div>
            </div>
            <div class="bet-hint mono dim">
              <span v-if="bet > balance" class="error-text">Solde insuffisant</span>
              <span v-else-if="bet < slotsConfig.min_bet || bet > slotsConfig.max_bet" class="error-text">
                Hors limites ({{ slotsConfig.min_bet }} – {{ slotsConfig.max_bet }})
              </span>
              <span v-else>
                Gain max possible : <b class="accent">{{ formatNum(bet * jackpotMultiplier) }} CAMP</b>
              </span>
            </div>
          </div>

          <button
            class="btn-primary btn-block lever-btn"
            :disabled="!canSpin"
            @click="spin"
          >
            {{ spinBtnLabel }}
          </button>

          <div v-if="casino.error" class="alert error">{{ casino.error }}</div>
        </div>
      </div>

      <!-- Table des payouts (compact, scroll horiz sur mobile) -->
      <div class="paytable card">
        <h3 class="paytable-title">💰 Gains <span class="dim">(3 sur la payline)</span></h3>
        <div class="paytable-list">
          <article
            v-for="row in slotsConfig.paytable"
            :key="row.code"
            class="paytable-row"
          >
            <div class="pt-combo">{{ row.label }}</div>
            <div class="pt-mult mono accent">×{{ row.multiplier }}</div>
            <div class="pt-prob mono dim">{{ (row.probability * 100).toFixed(2) }}%</div>
          </article>
        </div>
        <div class="paytable-foot dim">
          Gain ≈ <b>1 spin sur {{ winFrequencyLabel }}</b>.
          Pas de gain sur les pairs (2 identiques ne payent pas).
        </div>
      </div>

      <!-- Verify -->
      <details v-if="displayResult" class="verify card" :open="verifyOpen">
        <summary @click.prevent="verifyOpen = !verifyOpen">
          <span class="v-icon">🔬</span>
          Vérifier le tirage
          <span class="dim mono v-id">#{{ displayResult.id }}</span>
        </summary>
        <div class="verify-body">
          <p class="dim">
            Pour chaque rouleau <span class="mono">i ∈ [0,2]</span> :
            <span class="mono">int(sha256(combined+":"+i)[:8], 16) % 16</span>
            puis lookup pondéré sur la table.
          </p>
          <div class="kv"><div class="k">seed_hash</div><div class="v mono break">{{ displayResult.seed_hash }}</div></div>
          <div class="kv"><div class="k">server_seed</div><div class="v mono break">{{ displayResult.server_seed }}</div></div>
          <div class="kv"><div class="k">client_seed</div><div class="v mono break">{{ displayResult.client_seed }}</div></div>
          <div class="kv"><div class="k">combined_hash</div><div class="v mono break">{{ displayResult.combined_hash }}</div></div>
          <div v-if="displayResult.tx_hash_lock" class="kv">
            <div class="k">Lock</div>
            <div class="v"><a :href="basescan(displayResult.tx_hash_lock)" target="_blank" rel="noreferrer" class="mono">{{ shortTx(displayResult.tx_hash_lock) }}</a></div>
          </div>
          <div v-if="displayResult.tx_hash_payout" class="kv">
            <div class="k">Payout</div>
            <div class="v"><a :href="basescan(displayResult.tx_hash_payout)" target="_blank" rel="noreferrer" class="mono">{{ shortTx(displayResult.tx_hash_payout) }}</a></div>
          </div>
        </div>
      </details>

      <!-- Historique -->
      <section class="history-section">
        <div class="history-head">
          <h3 class="history-title">📜 Tes derniers spins</h3>
          <span v-if="casino.slotsHistory.length" class="history-count mono dim">
            {{ casino.slotsHistory.length }} spin{{ casino.slotsHistory.length > 1 ? 's' : '' }}
          </span>
        </div>
        <div v-if="!casino.slotsHistory.length" class="empty-state card">
          <div class="emoji">🎰</div>
          <div>Aucun spin. Tire sur le levier !</div>
        </div>
        <div v-else class="history-list">
          <article
            v-for="r in pagedHistory"
            :key="r.id"
            class="history-row"
            :class="{ won: r.win, lost: !r.win }"
          >
            <div class="h-reels">{{ r.reels.map(s => s.emoji).join('') }}</div>
            <div class="h-bet mono dim">-{{ formatNum(r.bet_amount) }}</div>
            <div class="h-payout mono" :class="{ accent: r.payout > 0 }">
              {{ r.payout ? '+' + formatNum(r.payout) : '0' }}
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
          <span class="pager-info mono">
            {{ historyPage }} / {{ totalPages }}
          </span>
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
import { ref, computed, onMounted } from 'vue'
import AppLayout from '@/components/layout/AppLayout.vue'
import { useCasinoStore } from '@/stores/casino'
import { useWalletStore } from '@/stores/wallet'
import { formatNum } from '@/config'

const casino = useCasinoStore()
const wallet = useWalletStore()

const slotsConfig = computed(() => casino.slotsConfig)

const bet = ref(5)
const verifyOpen = ref(false)
const displayResult = ref(null)             // setté APRÈS l'arrêt du dernier rouleau
const visualSpinning = ref(false)
const reelRefs = ref([null, null, null])    // refs DOM des strips
const reelStrips = ref([[], [], []])        // listes de symboles affichées
const reelWon = ref([false, false, false])  // glow par rouleau quand gagné

// Pagination de l'historique (client-side : on fetch 50 spins du back
// puis on tranche localement par pages de 10).
const HISTORY_PAGE_SIZE = 10
const historyPage = ref(1)
const totalPages = computed(() =>
  Math.max(1, Math.ceil(casino.slotsHistory.length / HISTORY_PAGE_SIZE)),
)
const pagedHistory = computed(() => {
  const start = (historyPage.value - 1) * HISTORY_PAGE_SIZE
  return casino.slotsHistory.slice(start, start + HISTORY_PAGE_SIZE)
})

// Constantes d'animation
const SYMBOL_HEIGHT_FALLBACK_PX = 72   // si on n'arrive pas a measure le DOM
const STRIP_RANDOM_LEN = 30            // nombre de symboles random avant le target
const STRIP_TAIL_LEN = 3               // symboles random après le target (visibles sous)
// Durée d'arrêt par rouleau (cascade gauche → droite)
const STOP_DELAYS_MS = [1800, 2600, 3400]

const isSpinning = computed(() => casino.slotsSpinning || visualSpinning.value)
const spinBtnLabel = computed(() => {
  if (casino.slotsSpinning) return '🎲 Tirage en cours…'
  if (visualSpinning.value) return '🎰 Les rouleaux tournent…'
  return '🕹️ Tirer le levier'
})

const balance = computed(() => Number(wallet.me?.balance || 0))

const edgePct = computed(() => {
  const rtp = Number(slotsConfig.value.rtp_theoretical_pct || 0)
  if (!rtp) return '—'
  return (100 - rtp).toFixed(1)
})

const jackpotMultiplier = computed(() => {
  const pt = slotsConfig.value.paytable || []
  return pt.reduce((m, r) => Math.max(m, Number(r.multiplier || 0)), 0)
})

const totalWinProb = computed(() => {
  const pt = slotsConfig.value.paytable || []
  return pt.reduce((s, r) => s + Number(r.probability || 0), 0)
})
const winFrequencyLabel = computed(() => {
  const p = totalWinProb.value
  if (!p) return '—'
  return Math.round(1 / p)
})

const shortcuts = computed(() => {
  const min = slotsConfig.value.min_bet || 1
  const max = slotsConfig.value.max_bet || 50
  return [min, 5, 10, Math.min(25, max), 'max']
})

const canSpin = computed(() => {
  if (isSpinning.value) return false
  const b = Number(bet.value) || 0
  if (b < slotsConfig.value.min_bet || b > slotsConfig.value.max_bet) return false
  if (b > balance.value) return false
  return true
})

function clampBet(amount) {
  if (amount === 'max') return Math.min(balance.value, slotsConfig.value.max_bet)
  const v = Number(amount) || 0
  return Math.min(Math.max(v, slotsConfig.value.min_bet), slotsConfig.value.max_bet)
}

function poolEmojis() {
  const pt = slotsConfig.value?.paytable || []
  const pool = pt.map(r => r.emoji)
  if (pool.length) return pool
  return ['🍒', '🍋', '🍊', '🔔', '⭐']
}

function buildStrip(targetEmoji) {
  // Strip avec : ~30 symboles random, le targetEmoji à l'index STRIP_RANDOM_LEN,
  // puis ~3 symboles random après (pour que le symbole "en dessous" du
  // target soit visible quand le strip est à l'arret).
  const pool = poolEmojis()
  const strip = []
  for (let i = 0; i < STRIP_RANDOM_LEN; i++) {
    strip.push(pool[Math.floor(Math.random() * pool.length)])
  }
  strip.push(targetEmoji)
  for (let i = 0; i < STRIP_TAIL_LEN; i++) {
    strip.push(pool[Math.floor(Math.random() * pool.length)])
  }
  return strip
}

function buildIdleStrip() {
  // Strip d'attente (avant le premier spin) : juste 3 symboles random
  // pour remplir la fenêtre 3-lignes sans paraître vide.
  const pool = poolEmojis()
  return [
    pool[Math.floor(Math.random() * pool.length)],
    pool[Math.floor(Math.random() * pool.length)],
    pool[Math.floor(Math.random() * pool.length)],
  ]
}

function makeClientSeed() {
  const arr = new Uint8Array(16)
  ;(window.crypto || window.msCrypto).getRandomValues(arr)
  return Array.from(arr, (b) => b.toString(16).padStart(2, '0')).join('')
}

async function spin() {
  if (!canSpin.value) return
  // Reset visuel
  displayResult.value = null
  reelWon.value = [false, false, false]

  // Appel API : on a besoin du résultat AVANT de construire les bandes
  // (pour positionner le bon symbole au milieu de chaque rouleau).
  let res
  try {
    res = await casino.slotsSpin({
      bet: Number(bet.value),
      clientSeed: makeClientSeed(),
    })
  } catch (e) {
    return
  }

  visualSpinning.value = true

  // Construit les 3 strips avec le target à l'index STRIP_RANDOM_LEN
  reelStrips.value = res.reels.map(r => buildStrip(r.emoji))

  // Force Vue à rendre les nouvelles strips AVANT de démarrer les anims
  // (sinon les refs pointent encore sur d'anciens elements DOM)
  await new Promise(resolve => requestAnimationFrame(resolve))

  // Mesure la hauteur réelle d'un symbole dans le DOM (la CSS variable
  // --slot-h change selon le viewport : 72px desktop, 62px mobile,
  // 54px très petit). Utiliser une constante JS hardcodée nous faisait
  // viser à côté de la payline sur mobile.
  const firstSymbol = reelRefs.value[0]?.children?.[0]
  const symbolH = firstSymbol?.getBoundingClientRect().height || SYMBOL_HEIGHT_FALLBACK_PX

  // Position cible : on veut que le symbole à l'index STRIP_RANDOM_LEN
  // soit aligné sur la payline (ligne du milieu de la fenêtre 3-lignes).
  // La fenêtre montre 3 symboles consécutifs. Si la fenêtre commence
  // visuellement à l'index K, alors la ligne du milieu affiche
  // strip[K+1]. Pour avoir target au milieu : K = STRIP_RANDOM_LEN - 1.
  // Donc le strip doit être translaté de -(STRIP_RANDOM_LEN - 1) * h.
  const targetTranslate = -(STRIP_RANDOM_LEN - 1) * symbolH

  // Lance une animation Web Animations API par rouleau, avec une durée
  // qui augmente de gauche à droite (cascade naturelle).
  // L'animation ne dépend PAS d'un état CSS persistant → pas de bug
  // "ça ne re-anime pas au 2e spin" comme avec les transitions.
  for (let i = 0; i < 3; i++) {
    const el = reelRefs.value[i]
    if (!el) continue
    const duration = STOP_DELAYS_MS[i]
    el.animate(
      [
        { transform: 'translateY(0px)' },
        { transform: `translateY(${targetTranslate}px)` },
      ],
      {
        duration,
        easing: 'cubic-bezier(0.12, 0.78, 0.18, 1)',  // ease-out marqué
        fill: 'forwards',  // garde la position finale après l'anim
      }
    )
  }

  // Quand le dernier rouleau s'est arrêté : reveal du panneau résultat
  // + glow doré (uniquement sur les rouleaux en cas de gain).
  // C'est SEULEMENT MAINTENANT qu'on commit (historique + refresh du
  // solde wallet) — sinon la TopBar et la liste "derniers spins"
  // afficheraient le résultat avant que les rouleaux s'arrêtent.
  setTimeout(() => {
    displayResult.value = res
    if (res.win) {
      reelWon.value = [true, true, true]
    }
    casino.commitSlotsResult(res)
    // Le nouveau spin est en tête → on ramène l'user sur la page 1
    // pour qu'il voie son spin sans rien faire.
    historyPage.value = 1
    visualSpinning.value = false
    // Éteint le glow après 2.5s pour préparer le prochain spin
    setTimeout(() => { reelWon.value = [false, false, false] }, 2500)
  }, STOP_DELAYS_MS[STOP_DELAYS_MS.length - 1] + 200)
}

function basescan(hash) { return `https://sepolia.basescan.org/tx/${hash}` }
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

onMounted(async () => {
  await Promise.all([
    casino.loadSlotsConfig(),
    casino.loadSlotsHistory(),
    wallet.refresh(),
  ])
  // Strip d'attente (avant le 1er spin) : 3 symboles random visibles
  reelStrips.value = [buildIdleStrip(), buildIdleStrip(), buildIdleStrip()]
  // Ajuste la mise par défaut
  bet.value = Math.min(
    Math.max(bet.value, slotsConfig.value.min_bet),
    slotsConfig.value.max_bet,
  )
})
</script>

<style scoped>
/* ─── Layout général ─────────────────────────────────── */
.back-link {
  display: inline-block;
  color: var(--text-2);
  font-size: 0.88em;
  font-weight: 600;
  margin-bottom: 0.4em;
}
.back-link:hover { color: var(--camp); text-decoration: none; }
.dim { color: var(--text-3); }
.accent { color: var(--camp); }
.red { color: var(--red); }

/* ─── Bandeau config (3 colonnes desktop, 3 quand mobile aussi) ──── */
.config-strip {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.5em;
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 0.7em 0.9em;
  margin-bottom: 1em;
}
.config-item {
  display: flex;
  flex-direction: column;
  gap: 0.1em;
  min-width: 0;
}
.config-item .k {
  font-size: 0.68em;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-2);
  font-weight: 600;
}
.config-item .v {
  font-size: 0.92em;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ─── Machine ─────────────────────────────────────────── */
.machine {
  background:
    radial-gradient(circle at 50% 0%, rgba(245, 200, 66, 0.1), transparent 60%),
    linear-gradient(180deg, #2a1d0a 0%, #1a1207 100%);
  border-color: #5a4220;
  padding: 1em;
  margin-bottom: 1.2em;
  /* On variable la hauteur des slots ici, repris dans .reel-symbol */
  --slot-h: 72px;
}

.reels-frame {
  position: relative;
  background: #0a0501;
  border: 4px solid #58422a;
  border-radius: var(--radius-sm);
  padding: 0.5em;
  box-shadow:
    inset 0 6px 16px rgba(0, 0, 0, 0.7),
    inset 0 -2px 8px rgba(255, 255, 255, 0.04),
    0 4px 16px rgba(0, 0, 0, 0.5);
  margin-bottom: 1em;
}

/* Fenêtre 3-lignes : hauteur = 3 × slot-h, overflow caché.
   Le strip défile à l'intérieur en translateY. */
.reels {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.5em;
  height: calc(3 * var(--slot-h));
}

.reel {
  position: relative;
  background: linear-gradient(180deg, #1a1308 0%, #0a0501 50%, #1a1308 100%);
  border: 2px solid #3a2a18;
  border-radius: 6px;
  overflow: hidden;
  box-shadow:
    inset 0 8px 12px rgba(0, 0, 0, 0.5),
    inset 0 -8px 12px rgba(0, 0, 0, 0.5);
  transition: box-shadow 0.3s, filter 0.3s;
}
.reel.win-glow {
  box-shadow:
    inset 0 8px 12px rgba(0, 0, 0, 0.4),
    inset 0 -8px 12px rgba(0, 0, 0, 0.4),
    0 0 0 2px var(--gold),
    0 0 14px 3px rgba(245, 200, 66, 0.65);
  animation: reel-pulse 0.7s ease-in-out infinite;
}
@keyframes reel-pulse {
  0%, 100% { filter: brightness(1.1); }
  50% { filter: brightness(1.45); }
}

.reel-strip {
  display: flex;
  flex-direction: column;
  align-items: center;
  /* Pas de transition CSS ici : on utilise Web Animations API depuis JS,
     ce qui évite le bug "ça ne se rejoue pas au 2e spin" qu'on avait
     avec les transitions persistantes. */
  will-change: transform;
}
.reel-symbol {
  height: var(--slot-h);
  width: 100%;
  display: grid;
  place-items: center;
  font-size: calc(var(--slot-h) * 0.55);
  line-height: 1;
  filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.55));
}

/* Payline centrale : ligne dorée sur la 2e rangée de symboles */
.payline {
  position: absolute;
  left: 0.6em;
  right: 0.6em;
  /* Centre vertical de la 2e ligne = padding-top + 1.5 × slot-h */
  top: calc(0.5em + 1.5 * var(--slot-h));
  height: 2px;
  background: linear-gradient(90deg, transparent, rgba(245, 200, 66, 0.7), transparent);
  transform: translateY(-50%);
  pointer-events: none;
  z-index: 1;
}

/* ─── Résultat ────────────────────────────────────────── */
.result-strip {
  display: flex;
  align-items: center;
  gap: 0.8em;
  padding: 0.8em 1em;
  border-radius: var(--radius-sm);
  border: 1px solid;
  margin-bottom: 1em;
}
.result-strip.won { background: var(--green-soft); border-color: rgba(20, 224, 142, 0.3); }
.result-strip.lost { background: var(--red-soft); border-color: rgba(255, 69, 102, 0.3); }
.r-emoji { font-size: 1.7em; line-height: 1; }
.r-title { font-size: 1em; font-weight: 600; }
.result-strip.won .r-title { color: var(--green); }
.result-strip.lost .r-title { color: var(--red); }
.r-sub { color: var(--text-2); font-size: 0.85em; margin-top: 0.15em; }

.fade-up-enter-active { transition: all 0.35s ease-out; }
.fade-up-enter-from { opacity: 0; transform: translateY(8px); }

/* ─── Form de mise ────────────────────────────────────── */
.controls .field { margin-bottom: 0.8em; }
.bet-input-row {
  display: flex;
  gap: 0.4em;
  align-items: stretch;
  flex-wrap: wrap;
}
.bet-input-row input {
  flex: 1 1 110px;
  min-width: 0;
  font-size: 1em;
}
.shortcuts {
  display: flex;
  gap: 0.3em;
  flex-wrap: wrap;
}
.chip {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 0.45em 0.8em;
  color: var(--text-1);
  font-size: 0.8em;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  min-height: 36px;
}
.chip:hover:not(:disabled) { border-color: var(--gold); color: var(--gold); }
.bet-hint {
  margin-top: 0.45em;
  font-size: 0.8em;
}
.error-text { color: var(--red); }

.lever-btn {
  font-size: 1.05em;
  padding: 0.9em 1.2em;
  min-height: 52px;
}

/* ─── Paytable ────────────────────────────────────────── */
.paytable { margin-bottom: 1.2em; padding: 1em; }
.paytable-title { font-size: 1em; margin-bottom: 0.7em; }
.paytable-list {
  display: flex;
  flex-direction: column;
  gap: 0.35em;
}
.paytable-row {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 0.7em;
  padding: 0.5em 0.7em;
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}
.pt-combo {
  font-size: 1.4em;
  line-height: 1;
  letter-spacing: -2px;
}
.pt-mult { font-weight: 700; font-size: 1em; }
.pt-prob { font-size: 0.78em; }
.paytable-foot {
  margin-top: 0.7em;
  font-size: 0.82em;
  line-height: 1.5;
}

/* ─── Verify ──────────────────────────────────────────── */
.verify { margin-bottom: 1.2em; padding: 1em; }
.verify summary {
  cursor: pointer;
  list-style: none;
  display: flex;
  align-items: center;
  gap: 0.5em;
}
.verify summary::-webkit-details-marker { display: none; }
.verify summary:hover { color: var(--camp); }
.v-icon { font-size: 1.1em; }
.v-id { margin-left: auto; font-size: 0.8em; }
.verify-body { margin-top: 0.9em; }
.verify-body p.dim { font-size: 0.85em; margin: 0 0 0.7em 0; }
.kv {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3em 0.8em;
  padding: 0.45em 0;
  border-bottom: 1px dashed var(--border);
  font-size: 0.85em;
}
.kv:last-child { border-bottom: none; }
.kv .k { flex-basis: 110px; color: var(--text-2); font-weight: 600; }
.kv .v {
  flex: 1;
  min-width: 0;
  word-break: break-all;
  color: var(--text-0);
}

/* ─── Historique ──────────────────────────────────────── */
.history-section { margin-top: 1.2em; }
.history-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.6em;
  margin-bottom: 0.7em;
}
.history-title { font-size: 1em; margin: 0; }
.history-count { font-size: 0.78em; }

/* Pagination compacte, mobile-friendly */
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
.history-list {
  display: flex;
  flex-direction: column;
  gap: 0.35em;
}
.history-row {
  display: grid;
  grid-template-columns: auto 1fr auto auto;
  align-items: center;
  gap: 0.6em;
  padding: 0.55em 0.8em;
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 0.88em;
}
.history-row.won { border-left: 3px solid var(--green); }
.history-row.lost { border-left: 3px solid var(--red); opacity: 0.85; }
.h-reels {
  font-size: 1.3em;
  line-height: 1;
  letter-spacing: -1px;
}
.h-bet { text-align: right; }
.h-payout { text-align: right; font-weight: 600; }
.h-ts { font-size: 0.75em; }

/* ─── Mobile (≤ 480px) ──────────────────────────────────
   Site utilisé majoritairement sur téléphone : on optimise pour
   les écrans étroits. */
@media (max-width: 480px) {
  .machine { padding: 0.7em; --slot-h: 62px; }
  .reels-frame { padding: 0.4em; }
  .reels { gap: 0.35em; }
  .reel-symbol { font-size: calc(var(--slot-h) * 0.6); }

  .config-strip { padding: 0.55em 0.7em; gap: 0.35em; }
  .config-item .v { font-size: 0.82em; }

  .paytable { padding: 0.8em; }
  .paytable-row { padding: 0.4em 0.6em; gap: 0.5em; }
  .pt-combo { font-size: 1.2em; }
  .pt-prob { font-size: 0.7em; }

  .lever-btn { font-size: 1em; padding: 0.85em 1em; min-height: 48px; }
  .chip { padding: 0.4em 0.7em; min-height: 32px; font-size: 0.78em; }

  .h-ts { display: none; }
  .h-reels { font-size: 1.2em; }
}

/* Très petits écrans (≤ 360px) : on réduit encore */
@media (max-width: 360px) {
  .machine { --slot-h: 54px; padding: 0.5em; }
  .config-strip { grid-template-columns: 1fr 1fr; }
  .config-item:nth-child(3) { grid-column: span 2; flex-direction: row; justify-content: space-between; }
  .bet-input-row { flex-direction: column; align-items: stretch; }
  .shortcuts { justify-content: space-between; }
  .shortcuts .chip { flex: 1; text-align: center; }
}
</style>
