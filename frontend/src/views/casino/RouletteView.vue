<template>
  <AppLayout>
    <main class="page fade-in">
      <div class="page-header">
        <router-link to="/casino" class="back-link">← Casino</router-link>
        <h1 class="page-title">🎡 Roulette <span class="dim">européenne</span></h1>
        <p class="page-sub">
          37 cases, 1 zéro vert, edge maison 2.70% (mécanique).
          <span class="dim">Pose tes jetons, fais tourner.</span>
        </p>
      </div>

      <!-- Bandeau config -->
      <div class="config-strip">
        <div class="config-item">
          <span class="k">Mise totale</span>
          <span class="v mono">{{ formatNum(rouletteConfig.min_bet) }} – {{ formatNum(rouletteConfig.max_bet) }} CAMP</span>
        </div>
        <div class="config-item">
          <span class="k">Edge maison</span>
          <span class="v mono">{{ rouletteConfig.house_edge_pct }}% <span class="dim">(1/37)</span></span>
        </div>
        <div class="config-item">
          <span class="k">Solde</span>
          <span class="v mono accent">{{ formatNum(balance) }} CAMP</span>
        </div>
      </div>

      <!-- Roue + résultat -->
      <div class="wheel-card card">
        <div class="wheel-stage">
          <div class="wheel" :style="wheelStyle">
            <div
              v-for="(num, i) in WHEEL_ORDER"
              :key="num"
              class="wheel-slot"
              :class="numberColor(num)"
              :style="slotStyle(i)"
            >
              <span class="slot-num">{{ num }}</span>
            </div>
          </div>
          <div class="wheel-pointer">▼</div>
        </div>

        <!-- Résultat -->
        <transition name="fade-up">
          <div
            v-if="result"
            class="result-strip"
            :class="resultClass"
          >
            <div class="r-ball" :class="result.outcome_color">{{ result.outcome_number }}</div>
            <div class="r-text">
              <div class="r-title">
                <template v-if="result.net_pnl > 0">
                  Tu gagnes <b class="mono">+{{ formatNum(result.net_pnl) }} CAMP</b>
                </template>
                <template v-else-if="result.net_pnl < 0">
                  Tu perds <b class="mono">{{ formatNum(result.net_pnl) }} CAMP</b>
                </template>
                <template v-else>
                  Push <span class="dim">(rien gagné, rien perdu)</span>
                </template>
              </div>
              <div class="r-sub">
                Tirage <b>{{ result.outcome_number }}</b>
                ({{ colorLabel(result.outcome_color) }})
                <span v-if="result.winning_spots?.length" class="dim">
                  · gagnants : {{ result.winning_spots.join(', ') }}
                </span>
              </div>
            </div>
          </div>
        </transition>
      </div>

      <!-- Toolbar mises -->
      <div class="bet-toolbar card">
        <div class="bet-row">
          <!-- Sélecteur de jetons (chips visuels) -->
          <div class="chips-block">
            <div class="block-label">Jeton actif</div>
            <div class="chips">
              <button
                v-for="c in CHIP_VALUES"
                :key="c"
                class="chip-token"
                :class="['v' + c, { active: activeChip === c }]"
                :disabled="isSpinning"
                @click="activeChip = c"
                :aria-label="`Jeton ${c} CAMP`"
              >
                <span class="chip-value">{{ c }}</span>
              </button>
            </div>
          </div>

          <!-- Total au centre, gros chiffre -->
          <div class="total-block">
            <div class="block-label">Total sur le tapis</div>
            <div class="total-amount mono">
              <span class="big">{{ formatNum(totalBet) }}</span>
              <span class="unit">CAMP</span>
            </div>
            <div class="total-sub dim mono">
              {{ Object.keys(bets).length }} mise{{ Object.keys(bets).length > 1 ? 's' : '' }}
            </div>
          </div>

          <!-- Actions secondaires : 2 petits boutons côte à côte -->
          <div class="actions-block">
            <div class="block-label">Actions</div>
            <div class="action-row">
              <button
                class="action-btn"
                :disabled="!totalBet || isSpinning"
                @click="clearBets"
                title="Retirer tous les jetons"
              >
                <span class="ab-ic">✕</span>
                <span class="ab-lbl">Retirer</span>
              </button>
              <button
                class="action-btn"
                :disabled="!lastBets || isSpinning"
                @click="repeatLast"
                title="Re-placer les mises du dernier spin"
              >
                <span class="ab-ic">↻</span>
                <span class="ab-lbl">Refaire</span>
              </button>
            </div>
          </div>
        </div>

        <!-- Bouton principal : pleine largeur -->
        <button
          class="btn-primary spin-btn"
          :disabled="!canSpin"
          @click="spin"
        >
          {{ spinBtnLabel }}
        </button>

        <div v-if="betError" class="bet-error">{{ betError }}</div>
      </div>

      <div v-if="casino.error" class="alert error">{{ casino.error }}</div>

      <!-- Tapis -->
      <div class="layout-card card">
        <h3 class="layout-title">🎲 Tapis</h3>
        <div class="layout-grid">
          <!-- 0 (occupe 3 lignes à gauche) -->
          <button
            class="cell number green zero-cell"
            :class="{ has: bets['n=0'], winning: isWinning('n=0') }"
            :disabled="isSpinning"
            @click="placeBet('n=0')"
          >
            <span class="cell-num">0</span>
            <span v-if="bets['n=0']" class="cell-chip">{{ bets['n=0'] }}</span>
          </button>

          <!-- Grille 1-36 + colonnes "2:1" en bout de chaque ligne -->
          <div class="numbers-block">
            <div class="numbers-row" v-for="(row, i) in NUMBERS_ROWS" :key="row[0]">
              <button
                v-for="n in row"
                :key="n"
                class="cell number"
                :class="[numberColor(n), { has: bets['n=' + n], winning: isWinning('n=' + n) }]"
                :disabled="isSpinning"
                @click="placeBet('n=' + n)"
              >
                <span class="cell-num">{{ n }}</span>
                <span v-if="bets['n=' + n]" class="cell-chip">{{ bets['n=' + n] }}</span>
              </button>
              <!-- col=3 sur la 1re ligne (3,6,9...36), col=2 sur la 2e, col=1 sur la 3e -->
              <button
                class="cell special col-cell"
                :class="{ has: bets['col=' + (3 - i)], winning: isWinning('col=' + (3 - i)) }"
                :disabled="isSpinning"
                @click="placeBet('col=' + (3 - i))"
              >
                <span>2:1</span>
                <span v-if="bets['col=' + (3 - i)]" class="cell-chip">{{ bets['col=' + (3 - i)] }}</span>
              </button>
            </div>
            <!-- Douzaines -->
            <div class="dozens-row">
              <button
                v-for="d in 3"
                :key="'d' + d"
                class="cell special"
                :class="{ has: bets['dozen=' + d], winning: isWinning('dozen=' + d) }"
                :disabled="isSpinning"
                @click="placeBet('dozen=' + d)"
              >
                <span>{{ d === 1 ? '1er' : d === 2 ? '2e' : '3e' }} <span class="dim">12</span></span>
                <span v-if="bets['dozen=' + d]" class="cell-chip">{{ bets['dozen=' + d] }}</span>
              </button>
            </div>
            <!-- Lignes du bas : low / even / red / black / odd / high -->
            <div class="outside-row">
              <button class="cell outside" :class="{ has: bets['low'], winning: isWinning('low') }" :disabled="isSpinning" @click="placeBet('low')">
                <span>1-18</span>
                <span v-if="bets['low']" class="cell-chip">{{ bets['low'] }}</span>
              </button>
              <button class="cell outside" :class="{ has: bets['even'], winning: isWinning('even') }" :disabled="isSpinning" @click="placeBet('even')">
                <span>PAIR</span>
                <span v-if="bets['even']" class="cell-chip">{{ bets['even'] }}</span>
              </button>
              <button class="cell outside red-bg" :class="{ has: bets['red'], winning: isWinning('red') }" :disabled="isSpinning" @click="placeBet('red')">
                <span>♦</span>
                <span v-if="bets['red']" class="cell-chip">{{ bets['red'] }}</span>
              </button>
              <button class="cell outside black-bg" :class="{ has: bets['black'], winning: isWinning('black') }" :disabled="isSpinning" @click="placeBet('black')">
                <span>♠</span>
                <span v-if="bets['black']" class="cell-chip">{{ bets['black'] }}</span>
              </button>
              <button class="cell outside" :class="{ has: bets['odd'], winning: isWinning('odd') }" :disabled="isSpinning" @click="placeBet('odd')">
                <span>IMPAIR</span>
                <span v-if="bets['odd']" class="cell-chip">{{ bets['odd'] }}</span>
              </button>
              <button class="cell outside" :class="{ has: bets['high'], winning: isWinning('high') }" :disabled="isSpinning" @click="placeBet('high')">
                <span>19-36</span>
                <span v-if="bets['high']" class="cell-chip">{{ bets['high'] }}</span>
              </button>
            </div>
          </div>
        </div>

        <div class="layout-legend">
          <span class="dim">Clic = ajoute le jeton actif. Re-clic = ajoute encore. Shift+clic = retire.</span>
        </div>
      </div>

      <!-- Vérifier le tirage (provably fair) -->
      <details v-if="result" class="verify card" :open="verifyOpen">
        <summary @click.prevent="verifyOpen = !verifyOpen">
          <span class="v-icon">🔬</span>
          Vérifier le tirage
          <span class="dim mono v-id">#{{ result.id }}</span>
        </summary>
        <div class="verify-body">
          <p class="dim">
            outcome = <span class="mono">int(combined_hash[:8], 16) % 37</span>.
          </p>
          <div class="kv"><div class="k">seed_hash</div><div class="v mono break">{{ result.seed_hash }}</div></div>
          <div class="kv"><div class="k">server_seed</div><div class="v mono break">{{ result.server_seed }}</div></div>
          <div class="kv"><div class="k">client_seed</div><div class="v mono break">{{ result.client_seed }}</div></div>
          <div class="kv"><div class="k">combined_hash</div><div class="v mono break">{{ result.combined_hash }}</div></div>
          <div v-if="result.tx_hash_lock" class="kv">
            <div class="k">Lock on-chain</div>
            <div class="v">
              <a :href="basescan(result.tx_hash_lock)" target="_blank" rel="noreferrer" class="mono">
                {{ shortTx(result.tx_hash_lock) }}
              </a>
            </div>
          </div>
          <div v-if="result.tx_hash_payout" class="kv">
            <div class="k">Payout on-chain</div>
            <div class="v">
              <a :href="basescan(result.tx_hash_payout)" target="_blank" rel="noreferrer" class="mono">
                {{ shortTx(result.tx_hash_payout) }}
              </a>
            </div>
          </div>
        </div>
      </details>

      <!-- Historique -->
      <section class="history-section">
        <h3 class="history-title">📜 Tes derniers spins</h3>
        <div v-if="!casino.rouletteHistory.length" class="empty-state card">
          <div class="emoji">🎡</div>
          <div>Aucun spin pour l'instant. Pose tes jetons et lance la roue !</div>
        </div>
        <div v-else class="history-list">
          <article
            v-for="r in casino.rouletteHistory"
            :key="r.id"
            class="history-row"
            :class="{ won: r.net_pnl > 0, lost: r.net_pnl < 0, push: r.net_pnl === 0 }"
          >
            <div class="h-ball" :class="r.outcome_color">{{ r.outcome_number }}</div>
            <div class="h-bets">
              <div class="dim mono">{{ r.bets?.length || 0 }} mise{{ (r.bets?.length || 0) > 1 ? 's' : '' }}</div>
              <div class="mono">-{{ formatNum(r.total_bet) }} CAMP</div>
            </div>
            <div class="h-payout">
              <div class="dim mono">payout</div>
              <div class="mono" :class="{ accent: r.total_payout > 0 }">
                +{{ formatNum(r.total_payout) }} CAMP
              </div>
            </div>
            <div class="h-pnl mono" :class="{ positive: r.net_pnl > 0, negative: r.net_pnl < 0 }">
              {{ r.net_pnl > 0 ? '+' : '' }}{{ formatNum(r.net_pnl) }}
            </div>
            <div class="h-ts mono dim">{{ formatShort(r.ts) }}</div>
          </article>
        </div>
      </section>
    </main>
  </AppLayout>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import AppLayout from '@/components/layout/AppLayout.vue'
import { useCasinoStore } from '@/stores/casino'
import { useWalletStore } from '@/stores/wallet'
import { formatNum } from '@/config'

const casino = useCasinoStore()
const wallet = useWalletStore()

const rouletteConfig = computed(() => casino.rouletteConfig)
// Le résultat affiché à l'écran (panneau gain/perte + accordéon verify)
// n'est PAS lié directement à casino.rouletteLastResult : on attend que
// la roue ait fini de tourner pour le révéler, sinon le numéro est
// "spoilé" avant la fin de l'animation.
const displayResult = ref(null)
const result = displayResult  // alias pour le template

const balance = computed(() => Number(wallet.me?.balance || 0))

// Numeros rouges (cf. RED_NUMBERS dans backend)
const RED_SET = new Set([
  1, 3, 5, 7, 9, 12, 14, 16, 18,
  19, 21, 23, 25, 27, 30, 32, 34, 36,
])

// Ordre standard d'une roulette europeenne (clockwise depuis le 0)
const WHEEL_ORDER = [
  0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10,
  5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26,
]

// Grille du tapis : 3 lignes, du haut au bas
//  - Ligne du haut : 3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36
//  - Ligne milieu  : 2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35
//  - Ligne du bas  : 1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 34
const NUMBERS_ROWS = [
  [3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36],
  [2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35],
  [1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 34],
]

const CHIP_VALUES = [1, 5, 10, 25, 50]

const activeChip = ref(5)
// bets = { 'n=17': 10, 'red': 20, ... }
const bets = reactive({})
const lastBets = ref(null)
const verifyOpen = ref(false)
const wheelRotation = ref(0)
// Spots gagnants du dernier spin : utilise pour faire briller les cases
// pendant ~2s apres le tirage avant de clear le tapis.
const winningSpots = ref(new Set())
// Phase visuelle de l'anim (au-dela de la duree de l'API call), pour
// pouvoir desactiver les actions et adapter le label du bouton.
const visualSpinning = ref(false)
const isSpinning = computed(() => casino.rouletteSpinning || visualSpinning.value)
const spinBtnLabel = computed(() => {
  if (casino.rouletteSpinning) return '🎲 Préparation du tirage…'
  if (visualSpinning.value) return '🎡 La roue tourne…'
  return '🎯 Lancer la roue'
})

function numberColor(n) {
  if (n === 0) return 'green'
  return RED_SET.has(n) ? 'red' : 'black'
}
function colorLabel(c) {
  return { red: 'rouge', black: 'noir', green: 'vert' }[c] || c
}

const totalBet = computed(() =>
  Object.values(bets).reduce((s, v) => s + Number(v), 0),
)

const betError = computed(() => {
  const t = totalBet.value
  if (!t) return ''
  if (t > balance.value) return `Solde insuffisant (${formatNum(balance.value)} CAMP)`
  if (t < rouletteConfig.value.min_bet) return `Total < ${rouletteConfig.value.min_bet} CAMP`
  if (t > rouletteConfig.value.max_bet) return `Total > ${rouletteConfig.value.max_bet} CAMP`
  return ''
})

const canSpin = computed(() => {
  if (isSpinning.value) return false
  if (totalBet.value <= 0) return false
  if (betError.value) return false
  return true
})

const resultClass = computed(() => {
  if (!result.value) return ''
  if (result.value.net_pnl > 0) return 'won'
  if (result.value.net_pnl < 0) return 'lost'
  return 'push'
})

function placeBet(spot, event) {
  if (isSpinning.value) return
  // Shift+clic retire
  if (event && event.shiftKey) {
    delete bets[spot]
    return
  }
  bets[spot] = (Number(bets[spot]) || 0) + Number(activeChip.value)
}

function isWinning(spot) {
  return winningSpots.value.has(spot)
}

function clearBets() {
  for (const k of Object.keys(bets)) delete bets[k]
}

function repeatLast() {
  if (!lastBets.value) return
  clearBets()
  for (const b of lastBets.value) {
    bets[b.spot] = (Number(bets[b.spot]) || 0) + Number(b.amount)
  }
}

function makeClientSeed() {
  const arr = new Uint8Array(16)
  ;(window.crypto || window.msCrypto).getRandomValues(arr)
  return Array.from(arr, (b) => b.toString(16).padStart(2, '0')).join('')
}

// Durée totale (en ms) de l'animation de décélération de la roue.
// Doit matcher la `transition: transform Xs ...` sur .wheel.
// 7s : laisse le temps au suspense de s'installer, surtout avec une
// courbe très ralentie sur la fin.
const SPIN_DURATION_MS = 7000
// Durée du glow des cases gagnantes avant qu'on retire les jetons.
const GLOW_DURATION_MS = 3000

async function spin() {
  if (!canSpin.value) return

  // Snapshot des mises pour pouvoir "Reprendre la dernière"
  const betsArray = Object.entries(bets).map(([spot, amount]) => ({
    spot,
    amount: Number(amount),
  }))
  lastBets.value = betsArray.map((b) => ({ ...b }))
  winningSpots.value = new Set()
  // Cache l'ancien résultat avant le nouveau spin (sinon l'ancien
  // panneau gain/perte reste affiché pendant la rotation).
  displayResult.value = null

  // ─── Étape 1 : on attend d'abord la réponse, la roue ne bouge pas
  //              encore (le bouton affiche "Préparation…").
  //              Pas d'animation pre-spin → pas de risque de
  //              backtrack quand la cible finale arrive.
  let res
  try {
    res = await casino.rouletteSpin({
      bets: betsArray,
      clientSeed: makeClientSeed(),
    })
  } catch (e) {
    // L'erreur est déjà dans casino.error, on sort.
    return
  }

  // ─── Étape 2 : on lance UNE seule animation qui décélère et atterrit
  //              pile sur le bon numéro. Forward-only (jamais de marche
  //              arrière).
  visualSpinning.value = true

  const idx = WHEEL_ORDER.indexOf(res.outcome_number)
  const slotAngle = 360 / WHEEL_ORDER.length  // ~9.73° par case

  // On veut que la position finale modulo 360 corresponde au slot.
  // Le pointeur est en haut donc on rote dans le sens inverse (-idx).
  const desiredFinalMod = ((-idx * slotAngle) % 360 + 360) % 360
  const current = wheelRotation.value
  const currentMod = ((current % 360) + 360) % 360
  let delta = desiredFinalMod - currentMod
  if (delta <= 0) delta += 360  // toujours forward

  // 8 tours complets + l'ajustement pour finir pile sur le numéro.
  // Plus de tours = anim plus longue à la même duration => sensation
  // de vitesse au début, puis décélération marquée à la fin.
  const turns = 8
  wheelRotation.value = current + turns * 360 + delta

  // ─── Étape 3 : à la fin de l'anim seulement (la roue est arrêtée),
  //              on révèle le panneau résultat + glow des gagnants.
  setTimeout(() => {
    displayResult.value = res
    winningSpots.value = new Set(res.winning_spots || [])
  }, SPIN_DURATION_MS)
  // Puis on clear le tapis pour préparer le prochain spin.
  setTimeout(() => {
    clearBets()
    winningSpots.value = new Set()
    visualSpinning.value = false
  }, SPIN_DURATION_MS + GLOW_DURATION_MS)
}

const wheelStyle = computed(() => ({
  // translateZ(0) force GPU compositing => rotation sans wobble
  transform: `rotate(${wheelRotation.value}deg) translateZ(0)`,
}))

function slotStyle(i) {
  const angle = (360 / WHEEL_ORDER.length) * i
  return {
    transform: `rotate(${angle}deg) translateY(-110px)`,
  }
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

onMounted(async () => {
  await Promise.all([
    casino.loadRouletteConfig(),
    casino.loadRouletteHistory(),
    wallet.refresh(),
  ])
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
.back-link:hover { color: var(--camp); text-decoration: none; }
.dim { color: var(--text-3); }
.accent { color: var(--camp); }
.positive { color: var(--green); }
.negative { color: var(--red); }

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
.config-item { display: flex; flex-direction: column; gap: 0.15em; }
.config-item .k {
  font-size: 0.72em; text-transform: uppercase; letter-spacing: 0.08em;
  color: var(--text-2); font-weight: 600;
}
.config-item .v { font-size: 0.95em; font-weight: 600; }

/* ─── Roue ────────────────────────────────────────────── */
.wheel-card {
  background:
    radial-gradient(circle at 50% 30%, rgba(20, 100, 50, 0.12), transparent 70%),
    var(--bg-1);
  padding: 1.5em;
  margin-bottom: 1.2em;
  position: relative;
}
.wheel-stage {
  position: relative;
  width: 260px;
  height: 260px;
  margin: 0 auto 1em;
}
.wheel {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: radial-gradient(circle, #2a1809 0%, #1a0d04 60%, #0a0501 100%);
  border: 4px solid #4a3520;
  box-shadow:
    0 0 0 6px #2a1c10,
    0 0 0 8px #58422a,
    inset 0 6px 16px rgba(255, 255, 255, 0.08),
    inset 0 -8px 24px rgba(0, 0, 0, 0.5),
    0 16px 40px rgba(0, 0, 0, 0.6);
  /* Décélération très marquée sur la fin pour le suspense :
       - début rapide (y monte vite jusqu'à ~0.9 dès t=0.4)
       - traînée longue sur les ~3 dernières secondes
     Sans overshoot (y2=1) pour éviter tout micro-recul en fin de course. */
  transition: transform 7s cubic-bezier(0.04, 0.86, 0.12, 1);
  /* Force GPU compositing pour eviter le sub-pixel jitter pendant
     la rotation (l'origine de transformation est l'axe de la roue). */
  transform-origin: 50% 50%;
  will-change: transform;
  transform: rotate(0deg) translateZ(0);
}
.wheel::after {
  content: '';
  position: absolute;
  top: 50%; left: 50%;
  width: 30px; height: 30px;
  margin: -15px 0 0 -15px;
  background: radial-gradient(circle, var(--gold), #b8860b);
  border-radius: 50%;
  box-shadow: 0 0 14px var(--camp-glow);
}
.wheel-slot {
  position: absolute;
  top: 50%; left: 50%;
  width: 24px;
  height: 36px;
  margin: -18px 0 0 -12px;     /* centre la slot sur l'axe de la roue */
  display: grid;
  place-items: center;
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
  font-size: 0.75em;
  color: white;
  /* Origine au centre de la slot (== centre de la roue, grace au margin
     ci-dessus). Sans ca le slot tourne autour d'un point decale et
     ca cree un wobble visible quand la roue tourne. */
  transform-origin: 50% 50%;
  border-radius: 3px;
}
.wheel-slot.red { background: #c4302b; }
.wheel-slot.black { background: #1a1a1a; border: 1px solid #2a2a2a; }
.wheel-slot.green { background: #0d8050; }
.slot-num { transform: rotate(0); }

.wheel-pointer {
  position: absolute;
  top: -10px; left: 50%;
  transform: translateX(-50%);
  color: var(--gold);
  font-size: 1.6em;
  text-shadow: 0 2px 6px rgba(0, 0, 0, 0.6);
  z-index: 2;
}

/* ─── Résultat ────────────────────────────────────────── */
.result-strip {
  display: flex;
  align-items: center;
  gap: 1em;
  padding: 0.9em 1.1em;
  border-radius: var(--radius-sm);
  border: 1px solid;
}
.result-strip.won { background: var(--green-soft); border-color: rgba(20, 224, 142, 0.3); }
.result-strip.lost { background: var(--red-soft); border-color: rgba(255, 69, 102, 0.3); }
.result-strip.push { background: var(--bg-2); border-color: var(--border); }

.r-ball {
  width: 48px; height: 48px;
  border-radius: 50%;
  display: grid; place-items: center;
  font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 800;
  font-size: 1.3em;
  color: white;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
}
.r-ball.red { background: linear-gradient(135deg, #d83a35, #8a2521); }
.r-ball.black { background: linear-gradient(135deg, #2a2a2a, #0a0a0a); }
.r-ball.green { background: linear-gradient(135deg, #14b870, #0a7045); }

.r-title { font-size: 1.05em; font-weight: 600; }
.r-title b { color: inherit; }
.result-strip.won .r-title { color: var(--green); }
.result-strip.lost .r-title { color: var(--red); }
.r-sub { color: var(--text-2); font-size: 0.85em; margin-top: 0.15em; }

.fade-up-enter-active { transition: all 0.35s ease-out; }
.fade-up-enter-from { opacity: 0; transform: translateY(8px); }

/* ─── Toolbar mises ───────────────────────────────────── */
.bet-toolbar {
  padding: 1.1em 1.2em;
  margin-bottom: 1.2em;
  display: flex;
  flex-direction: column;
  gap: 0.9em;
}
.bet-row {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 1.4em;
  align-items: stretch;
}
.block-label {
  font-size: 0.7em;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--text-2);
  font-weight: 600;
  margin-bottom: 0.5em;
}

/* Chips visuels (jetons de casino) */
.chips-block { min-width: 0; }
.chips { display: flex; gap: 0.45em; flex-wrap: wrap; }
.chip-token {
  position: relative;
  width: 46px;
  height: 46px;
  padding: 0;
  border-radius: 50%;
  border: 2px dashed rgba(255, 255, 255, 0.45);
  font-family: 'JetBrains Mono', monospace;
  font-weight: 800;
  font-size: 0.85em;
  color: white;
  cursor: pointer;
  display: grid;
  place-items: center;
  box-shadow:
    inset 0 0 0 3px rgba(0, 0, 0, 0.18),
    0 3px 8px rgba(0, 0, 0, 0.4);
  transition: transform 0.12s, box-shadow 0.12s;
}
.chip-token::before {
  content: '';
  position: absolute;
  inset: 6px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.18);
}
.chip-value {
  position: relative;
  z-index: 1;
  text-shadow: 0 1px 0 rgba(0, 0, 0, 0.35);
}
.chip-token:hover:not(:disabled) { transform: translateY(-2px); }
.chip-token:disabled { opacity: 0.5; cursor: not-allowed; }
.chip-token.active {
  transform: translateY(-3px);
  box-shadow:
    inset 0 0 0 3px rgba(0, 0, 0, 0.18),
    0 0 0 3px var(--gold),
    0 8px 18px rgba(245, 200, 66, 0.45);
}
/* Couleurs par valeur (codes "casino-like") */
.chip-token.v1 { background: linear-gradient(135deg, #d1d5db, #9ca3af); color: #1a1a1a; }
.chip-token.v5 { background: linear-gradient(135deg, #ef4444, #b91c1c); }
.chip-token.v10 { background: linear-gradient(135deg, #3b82f6, #1d4ed8); }
.chip-token.v25 { background: linear-gradient(135deg, #10b981, #047857); }
.chip-token.v50 { background: linear-gradient(135deg, #1f2937, #0a0a0a); }

/* Bloc total au centre */
.total-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-width: 160px;
  padding: 0 0.4em;
  border-left: 1px solid var(--border);
  border-right: 1px solid var(--border);
}
.total-block .block-label { text-align: center; }
.total-amount {
  display: flex;
  align-items: baseline;
  gap: 0.3em;
}
.total-amount .big {
  font-family: 'Bricolage Grotesque', sans-serif;
  font-size: 2em;
  font-weight: 800;
  letter-spacing: -0.03em;
  color: var(--gold);
  line-height: 1;
}
.total-amount .unit {
  font-size: 0.85em;
  color: var(--text-2);
  font-weight: 600;
}
.total-sub { font-size: 0.8em; margin-top: 0.25em; }

/* Actions secondaires (Retirer / Refaire) */
.actions-block { min-width: 0; display: flex; flex-direction: column; }
.actions-block .block-label { text-align: right; }
.action-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.5em;
}
.action-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.15em;
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0.7em 0.4em;
  color: var(--text-1);
  font-weight: 600;
  font-size: 0.78em;
  cursor: pointer;
  transition: all 0.12s;
}
.action-btn:hover:not(:disabled) {
  border-color: var(--camp);
  color: var(--camp);
  background: var(--bg-3);
}
.action-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.ab-ic { font-size: 1.25em; line-height: 1; }
.ab-lbl { font-size: 0.85em; letter-spacing: 0.04em; }

/* Bouton principal pleine largeur */
.spin-btn {
  width: 100%;
  font-size: 1.1em;
  padding: 1em 1.2em;
  font-weight: 700;
  letter-spacing: 0.02em;
}
.bet-error {
  color: var(--red);
  font-size: 0.88em;
  font-weight: 600;
  text-align: center;
}

/* ─── Tapis ───────────────────────────────────────────── */
.layout-card { margin-bottom: 1.2em; padding: 1.2em; }
.layout-title { font-size: 1em; margin-bottom: 0.9em; color: var(--text-1); }

.layout-grid {
  --num-row-h: 40px;
  display: grid;
  grid-template-columns: 50px 1fr;
  gap: 4px;
  background: linear-gradient(180deg, #0c5a32 0%, #094a28 100%);
  padding: 8px;
  border-radius: var(--radius-sm);
  border: 1px solid #052414;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.zero-cell {
  display: flex; align-items: center; justify-content: center;
  border-radius: 4px 0 0 4px;
  /* Le 0 prend la hauteur des 3 rangees de numeros (et seulement
     celles-la, pas les douzaines / outside en dessous).
     --num-row-h synchronise avec .cell min-height + gap. */
  align-self: start;
  height: calc(3 * var(--num-row-h, 40px) + 2 * 4px);
}

.numbers-block {
  display: flex; flex-direction: column; gap: 4px;
}
/* Chaque ligne de numeros : 12 numeros + 1 "2:1" en bout (col-cell) */
.numbers-row {
  display: grid;
  grid-template-columns: repeat(12, 1fr) 50px;
  gap: 4px;
}
.col-cell {
  /* Meme hauteur que les numeros qui l'entourent */
  font-size: 0.78em;
}
.dozens-row {
  display: grid;
  /* 3 cases occupent l'equivalent de 12 numeros (+ une colonne vide
     a droite pour s'aligner sous les "2:1") */
  grid-template-columns: repeat(3, 1fr) 50px;
  gap: 4px;
}
.dozens-row::after {
  content: '';
}
.outside-row {
  display: grid;
  grid-template-columns: repeat(6, 1fr) 50px;
  gap: 4px;
}
.outside-row::after {
  content: '';
}

.cell {
  position: relative;
  background: var(--bg-2);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 3px;
  padding: 0.6em 0.3em;
  color: white;
  font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 800;
  font-size: 0.95em;
  cursor: pointer;
  transition: all 0.1s;
  min-height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  letter-spacing: -0.01em;
}
.cell:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 0 0 1px var(--gold);
}
.cell:disabled { cursor: not-allowed; opacity: 0.75; }
.cell.red { background: #c4302b; }
.cell.black { background: #1a1a1a; border-color: #2a2a2a; }
.cell.green { background: #0d8050; }
.cell.outside { background: #1f3a28; font-size: 0.82em; }
.cell.outside.red-bg { background: #c4302b; }
.cell.outside.black-bg { background: #1a1a1a; }
.cell.special { background: #1f3a28; font-size: 0.85em; }
.cell .dim { color: rgba(255, 255, 255, 0.7); }

.cell.has::after {
  content: '';
  position: absolute;
  inset: 0;
  border: 2px solid var(--gold);
  border-radius: 3px;
  pointer-events: none;
}
/* Cellule gagnante : pulse doré pendant ~2s avant le clear du tapis */
.cell.winning {
  animation: cell-pulse 0.7s ease-in-out infinite;
  z-index: 2;
}
.cell.winning::before {
  content: '';
  position: absolute;
  inset: -3px;
  border-radius: 5px;
  box-shadow:
    0 0 12px 2px var(--gold),
    0 0 24px 4px rgba(245, 200, 66, 0.6);
  pointer-events: none;
}
@keyframes cell-pulse {
  0%, 100% { transform: scale(1); filter: brightness(1.15); }
  50% { transform: scale(1.06); filter: brightness(1.5); }
}
.cell-chip {
  position: absolute;
  bottom: 2px; right: 2px;
  background: var(--gold);
  color: #1a1308;
  font-size: 0.7em;
  font-weight: 800;
  font-family: 'JetBrains Mono', monospace;
  padding: 0 0.35em;
  border-radius: 999px;
  min-width: 18px;
  text-align: center;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.5);
}

.layout-legend { margin-top: 0.7em; font-size: 0.78em; }

/* ─── Verify (provably fair) ──────────────────────────── */
.verify summary {
  cursor: pointer; list-style: none;
  display: flex; align-items: center; gap: 0.6em;
}
.verify summary::-webkit-details-marker { display: none; }
.verify summary:hover { color: var(--camp); }
.v-icon { font-size: 1.2em; }
.v-id { margin-left: auto; font-size: 0.85em; }
.verify-body { margin-top: 1em; }
.kv {
  display: flex; flex-wrap: wrap; gap: 0.4em 1em;
  padding: 0.5em 0; border-bottom: 1px dashed var(--border);
  font-size: 0.9em;
}
.kv:last-child { border-bottom: none; }
.kv .k { flex-basis: 160px; color: var(--text-2); font-weight: 600; }
.kv .v { flex: 1; word-break: break-all; color: var(--text-0); }

/* ─── Historique ──────────────────────────────────────── */
.history-section { margin-top: 1.5em; }
.history-title { font-size: 1.1em; margin-bottom: 0.8em; }
.history-list { display: flex; flex-direction: column; gap: 0.4em; }
.history-row {
  display: grid;
  grid-template-columns: 40px 1fr 1fr auto auto;
  align-items: center;
  gap: 0.8em;
  padding: 0.65em 0.9em;
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 0.88em;
}
.history-row.won { border-left: 3px solid var(--green); }
.history-row.lost { border-left: 3px solid var(--red); opacity: 0.85; }
.history-row.push { border-left: 3px solid var(--text-3); }
.h-ball {
  width: 32px; height: 32px;
  border-radius: 50%;
  display: grid; place-items: center;
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700; font-size: 0.85em;
  color: white;
}
.h-ball.red { background: #c4302b; }
.h-ball.black { background: #1a1a1a; }
.h-ball.green { background: #0d8050; }
.h-bets, .h-payout { display: flex; flex-direction: column; font-size: 0.85em; }
.h-bets .dim, .h-payout .dim {
  font-size: 0.72em; text-transform: uppercase; letter-spacing: 0.08em;
}
.h-pnl { font-weight: 700; font-size: 1em; }
.h-ts { font-size: 0.78em; }

@media (max-width: 760px) {
  .config-strip { grid-template-columns: 1fr; }
  .config-item { flex-direction: row; justify-content: space-between; }
  .bet-row { grid-template-columns: 1fr; gap: 0.8em; }
  .total-block { border-left: none; border-right: none; border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); padding: 0.6em 0; }
  .actions-block .block-label { text-align: left; }
  .chip-token { width: 40px; height: 40px; font-size: 0.75em; }
  .total-amount .big { font-size: 1.6em; }
  .layout-grid { --num-row-h: 32px; grid-template-columns: 40px 1fr; padding: 5px; gap: 3px; }
  .numbers-row { grid-template-columns: repeat(12, 1fr) 36px; }
  .dozens-row { grid-template-columns: repeat(3, 1fr) 36px; }
  .outside-row { grid-template-columns: repeat(6, 1fr) 36px; }
  .cell { font-size: 0.78em; min-height: 32px; padding: 0.4em 0.15em; }
  .cell-chip { font-size: 0.6em; min-width: 14px; }
  .wheel-stage { width: 220px; height: 220px; }
  .history-row { grid-template-columns: 32px 1fr 1fr auto; }
  .h-ts { display: none; }
}
</style>
