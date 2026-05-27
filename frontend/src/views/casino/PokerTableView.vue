<template>
  <AppLayout>
    <main class="page fade-in">
      <header class="header">
        <router-link to="/casino/poker" class="back">← Lobby</router-link>
        <h2 v-if="table">{{ table.name }}</h2>
        <span v-if="table" class="blinds mono"
          >blinds {{ table.blind_small }} / {{ table.blind_big }}</span
        >
      </header>

      <div v-if="error" class="alert err">{{ error }}</div>

      <!-- ─── Pas encore assis : panneau de sit-in ─── -->
      <section v-if="table && !mySession" class="sit-card card">
        <h3>Prendre place</h3>
        <div class="dim">
          {{ activePlayers.length }} / {{ table.max_players }} joueurs assis ·
          buy-in {{ table.min_buyin }}–{{ table.max_buyin }} CAMP
        </div>
        <div class="form-row">
          <input
            v-model.number="sitBuyin"
            type="number"
            :min="table.min_buyin"
            :max="table.max_buyin"
            class="input"
          />
          <button
            class="btn primary"
            :disabled="
              poker.acting ||
              table.status !== 'open' ||
              activePlayers.length >= table.max_players ||
              sitBuyin < table.min_buyin ||
              sitBuyin > table.max_buyin
            "
            @click="onSit"
          >
            S'asseoir
          </button>
        </div>
        <p v-if="table.status !== 'open'" class="dim small">
          Table fermée : plus de sit-in autorisé.
        </p>
      </section>

      <!-- ─── Table en jeu ─── -->
      <section v-if="table" class="board-wrap">
        <div class="board-frame">
          <!-- Centre : board + pot -->
          <div class="centre">
            <div class="board-cards">
              <PlayingCard
                v-for="(c, i) in boardCards"
                :key="`b-${i}`"
                :card="c"
                size="lg"
              />
              <PlayingCard
                v-for="i in 5 - boardCards.length"
                :key="`p-${i}`"
                hidden
                size="lg"
              />
            </div>
            <div class="pot mono">
              <span class="lbl">POT</span>
              <span class="val">{{ pot }} CAMP</span>
            </div>
            <div class="street-tag" v-if="hand">
              <span>{{ streetLabel }}</span>
            </div>
            <div class="street-tag" v-else-if="lastHand">
              <span>Main {{ lastHand.hand_number }} terminée</span>
            </div>
          </div>

          <!-- Sieges autour -->
          <div
            v-for="seat in seatSlots"
            :key="seat.idx"
            class="seat"
            :class="{
              filled: !!seat.player,
              folded: seat.player && seat.player.folded,
              all_in: seat.player && seat.player.all_in,
              to_act: seat.player && hand && hand.to_act_seat === seat.player.seat,
              me: seat.player && seat.player.username === me,
              dealer: hand && hand.dealer_seat === seat.idx,
            }"
            :style="seatStyle(seat.idx)"
          >
            <template v-if="seat.player">
              <div class="seat-head">
                <span class="seat-name">{{ seat.player.username }}</span>
                <span class="seat-stack mono">{{ seat.player.stack }}</span>
              </div>
              <div class="seat-hole">
                <PlayingCard
                  v-for="(c, i) in seatHoleCards(seat.player)"
                  :key="`s${seat.idx}-${i}`"
                  :card="c.card"
                  :hidden="c.hidden"
                  size="sm"
                  :class="{ 'card-faded': c.faded }"
                />
              </div>
              <div class="seat-bet mono" v-if="seat.player.bet > 0">
                {{ seat.player.bet }}
              </div>
              <div class="seat-tags">
                <span v-if="hand && hand.dealer_seat === seat.player.seat" class="tag dealer-tag">D</span>
                <span v-if="hand && hand.sb_seat === seat.player.seat" class="tag">SB</span>
                <span v-if="hand && hand.bb_seat === seat.player.seat" class="tag">BB</span>
                <span v-if="seat.player.folded" class="tag fold-tag">fold</span>
                <span v-if="seat.player.all_in" class="tag allin-tag">all-in</span>
              </div>
            </template>
            <template v-else>
              <div class="empty-seat">siège {{ seat.idx + 1 }}</div>
            </template>
          </div>
        </div>
      </section>

      <!-- ─── Actions disponibles ─── -->
      <section v-if="mySession && myPlayer && isMyTurn" class="actions-bar card">
        <div class="actions-info">
          <span class="lbl">Ton tour ·</span>
          <span class="dim">stack {{ myPlayer.stack }} · mise {{ myPlayer.bet }}</span>
          <span class="dim" v-if="toCall > 0">· à suivre {{ toCall }}</span>
        </div>
        <div class="actions-buttons">
          <button
            class="btn ghost danger"
            :disabled="poker.acting"
            @click="onAct('fold')"
          >
            Fold
          </button>
          <button
            v-if="toCall === 0"
            class="btn"
            :disabled="poker.acting"
            @click="onAct('check')"
          >
            Check
          </button>
          <button
            v-if="toCall > 0"
            class="btn"
            :disabled="poker.acting"
            @click="onAct('call')"
          >
            Call {{ Math.min(toCall, myPlayer.stack) }}
          </button>

          <!-- Bet (current_bet = 0) -->
          <template v-if="hand && hand.current_bet === 0">
            <input
              v-model.number="raiseAmount"
              type="number"
              class="input num"
              :min="hand.min_raise"
              :max="myPlayer.stack"
            />
            <button
              class="btn primary"
              :disabled="
                poker.acting || raiseAmount < hand.min_raise || raiseAmount > myPlayer.stack
              "
              @click="onAct('bet', raiseAmount)"
            >
              Bet
            </button>
          </template>
          <!-- Raise (current_bet > 0) -->
          <template v-else>
            <input
              v-model.number="raiseAmount"
              type="number"
              class="input num"
              :min="hand.current_bet + hand.min_raise"
              :max="myPlayer.bet + myPlayer.stack"
            />
            <button
              class="btn primary"
              :disabled="poker.acting || !canRaise"
              @click="onAct('raise', raiseAmount)"
            >
              Raise
            </button>
            <button
              v-if="myPlayer.stack > 0"
              class="btn gold"
              :disabled="poker.acting"
              @click="onAct('raise', myPlayer.bet + myPlayer.stack)"
            >
              All-in
            </button>
          </template>
        </div>
      </section>

      <!-- ─── Bouton "Nouvelle main" ─── -->
      <section
        v-if="mySession && !hand"
        class="new-hand-bar card"
        :class="{ ready: canStartHand }"
      >
        <div class="new-hand-info">
          <span class="lbl">{{ lastHand ? "Main terminée" : "En attente" }}</span>
          <span v-if="!canStartHand" class="dim small">
            {{ startHandReason || "Pas encore prêt" }}
          </span>
        </div>
        <button
          class="btn primary big"
          :disabled="!canStartHand || poker.acting"
          @click="onStartHand"
        >
          🃏 Nouvelle main
        </button>
      </section>

      <!-- ─── Resultat de la derniere main ─── -->
      <section v-if="lastHand && lastHand.settlement && !hand" class="result card">
        <header class="result-head">
          <h3>Main #{{ lastHand.hand_number }}</h3>
        </header>

        <div v-if="lastHand.settlement.voided" class="alert dim">
          Main annulée par l'admin. Mises remboursées.
        </div>

        <template v-else>
          <!-- Un bloc par pot (main + side pots) -->
          <div
            v-for="(pot, i) in lastHand.settlement.pots"
            :key="i"
            class="pot-block"
          >
            <div class="pot-head">
              <span class="pot-tag">{{
                lastHand.settlement.pots.length > 1
                  ? (i === 0 ? "Main pot" : `Side pot ${i}`)
                  : "Pot"
              }}</span>
              <span class="pot-total mono">{{ pot.amount }} CAMP</span>
            </div>
            <article
              v-for="w in pot.winners"
              :key="w.seat"
              class="winner-card"
            >
              <div class="winner-row">
                <div class="winner-id">
                  <div class="avatar">{{ initial(w.username) }}</div>
                  <div>
                    <div class="winner-name">
                      <b>{{ w.username }}</b>
                      <span class="trophy">🏆</span>
                    </div>
                    <div class="winner-label">{{ w.hand_label }}</div>
                  </div>
                </div>
                <div class="winner-amount">+{{ w.share }} CAMP</div>
              </div>
              <div v-if="w.display_cards?.length" class="card-row">
                <PlayingCard
                  v-for="(c, j) in w.display_cards"
                  :key="`wd${w.seat}-${j}`"
                  :card="c"
                  size="sm"
                  :highlight="(w.defining_cards || []).includes(c)"
                  :class="{
                    'card-faded': !(w.defining_cards || []).includes(c),
                  }"
                />
              </div>
            </article>
          </div>

          <!-- Autres joueurs : reveal de tous (showdown + folded) -->
          <div v-if="nonWinnerShowdown.length" class="losers">
            <h4 class="losers-title">Autres joueurs</h4>
            <article
              v-for="sh in nonWinnerShowdown"
              :key="`l-${sh.seat}`"
              class="loser-row"
              :class="{ folded: sh.folded }"
            >
              <div class="loser-head">
                <div class="loser-id">
                  <div class="avatar small">{{ initial(sh.username) }}</div>
                  <div class="loser-meta">
                    <div class="loser-name">
                      <b>{{ sh.username }}</b>
                      <span v-if="sh.folded" class="fold-mark">fold</span>
                      <span v-if="sh.username === me" class="me-tag">toi</span>
                    </div>
                    <div class="dim small">{{ sh.label }}</div>
                  </div>
                </div>
                <div
                  v-if="netByUsername[sh.username] !== undefined"
                  class="loser-amount"
                  :class="{ pos: netByUsername[sh.username] > 0 }"
                >
                  {{ formatNet(netByUsername[sh.username]) }}
                </div>
              </div>
              <div v-if="sh.display_cards?.length" class="card-row">
                <PlayingCard
                  v-for="(c, j) in sh.display_cards"
                  :key="`lc${sh.seat}-${j}`"
                  :card="c"
                  size="sm"
                  :highlight="
                    !sh.folded && (sh.defining_cards || []).includes(c)
                  "
                  :class="{
                    'card-faded':
                      sh.folded || !(sh.defining_cards || []).includes(c),
                  }"
                />
              </div>
            </article>
          </div>

          <!-- Scoreboard final : tous les joueurs et leur P&L sur cette main -->
          <div v-if="finalPlayers.length" class="scoreboard">
            <h4 class="losers-title">Bilan de la main</h4>
            <div class="score-rows">
              <div
                v-for="fp in finalPlayers"
                :key="`s-${fp.seat}`"
                class="score-row"
                :class="{ winner: fp.net > 0, loser: fp.net < 0, me: fp.username === me }"
              >
                <span class="score-name">
                  {{ fp.username }}
                  <span v-if="fp.username === me" class="me-tag">toi</span>
                  <span v-if="fp.folded" class="fold-mark">fold</span>
                </span>
                <span class="score-net mono">{{ formatNet(fp.net) }}</span>
              </div>
            </div>
          </div>
        </template>
      </section>

      <!-- ─── Bouton Sit-out ─── -->
      <section v-if="mySession" class="leave-row">
        <button class="btn ghost" :disabled="poker.acting" @click="onLeave">
          Quitter la table (cashout {{ mySession.stack }} CAMP)
        </button>
        <p v-if="hand && myPlayer && !myPlayer.folded" class="dim small">
          Si tu pars maintenant, tu es auto-fold et ta mise courante reste
          dans le pot.
        </p>
      </section>
    </main>
  </AppLayout>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import AppLayout from "@/components/layout/AppLayout.vue";
import PlayingCard from "@/components/poker/PlayingCard.vue";
import { usePokerStore } from "@/stores/poker";
import { useWalletStore } from "@/stores/wallet";

const route = useRoute();
const poker = usePokerStore();
const wallet = useWalletStore();

const tableId = computed(() => Number(route.params.id));
const sitBuyin = ref(0);
const raiseAmount = ref(0);
const error = ref(null);

const me = computed(() => wallet.me?.username || "");
const table = computed(() => poker.tableState?.table || null);
const hand = computed(() => poker.tableState?.hand || null);
const lastHand = computed(() => poker.tableState?.last_hand || null);
const activePlayers = computed(() => poker.tableState?.sessions || []);
const mySession = computed(() =>
  activePlayers.value.find((s) => s.username === me.value),
);
const myPlayer = computed(() =>
  hand.value?.players?.find((p) => p.username === me.value),
);
const boardCards = computed(() => hand.value?.board || lastHand.value?.board || []);
const pot = computed(() => hand.value?.pot ?? lastHand.value?.pot ?? 0);
const canStartHand = computed(() => !!poker.tableState?.can_start_hand);
const startHandReason = computed(() => poker.tableState?.start_hand_reason || "");

// ─── Helpers pour le panneau de résultat ────────────────
const settlement = computed(() => lastHand.value?.settlement || null);

// Liste plate des seats vainqueurs (toutes les sides pots confondues)
const winnerSeats = computed(() => {
  const s = new Set();
  for (const pot of settlement.value?.pots || []) {
    for (const w of pot.winners || []) s.add(w.seat);
  }
  return s;
});

// Showdown – les non-gagnants qui ont quand même montré leurs cartes
const nonWinnerShowdown = computed(() => {
  const shown = settlement.value?.shown_holes || [];
  return shown.filter((sh) => !winnerSeats.value.has(sh.seat));
});

// Tous les joueurs et leur net P&L sur cette main, triés gagnants → folded
const finalPlayers = computed(() => {
  const fps = (settlement.value?.final_players || []).slice();
  fps.sort((a, b) => (b.net || 0) - (a.net || 0));
  return fps;
});

// Indexé par username → net (pour le rendu rapide à côté des shown_holes)
const netByUsername = computed(() => {
  const m = {};
  for (const fp of settlement.value?.final_players || []) {
    m[fp.username] = fp.net;
  }
  return m;
});

function initial(name) {
  return (name || "?").charAt(0).toUpperCase();
}

function formatNet(n) {
  if (n === undefined || n === null) return "";
  if (n > 0) return `+${n} CAMP`;
  if (n < 0) return `${n} CAMP`;
  return "0 CAMP";
}
const isMyTurn = computed(
  () =>
    !!hand.value &&
    !!myPlayer.value &&
    hand.value.to_act_seat === myPlayer.value.seat &&
    !myPlayer.value.folded &&
    !myPlayer.value.all_in,
);
const toCall = computed(() => {
  if (!hand.value || !myPlayer.value) return 0;
  return Math.max(0, hand.value.current_bet - myPlayer.value.bet);
});
const canRaise = computed(() => {
  if (!hand.value || !myPlayer.value) return false;
  const min = hand.value.current_bet + hand.value.min_raise;
  const maxTotal = myPlayer.value.bet + myPlayer.value.stack;
  // All-in raise tolere meme si en dessous du min
  return raiseAmount.value >= min && raiseAmount.value <= maxTotal
      || raiseAmount.value === maxTotal;
});

const streetLabel = computed(() => {
  const map = {
    preflop: "Pré-flop",
    flop: "Flop",
    turn: "Turn",
    river: "River",
    showdown: "Showdown",
    done: "Terminée",
  };
  return map[hand.value?.street] || "";
});

// Disposition des sieges autour de la table : on cherche le seat du user
// pour le mettre en bas et tourner les autres autour.
const seatSlots = computed(() => {
  if (!table.value) return [];
  const max = table.value.max_players;
  const filled = activePlayers.value;
  const handPlayers = hand.value?.players || [];
  // Mappe seat -> player (state de la main si dispo, sinon session)
  const byseat = {};
  for (const s of filled) {
    byseat[s.seat] = { ...s };
  }
  for (const p of handPlayers) {
    byseat[p.seat] = { ...byseat[p.seat], ...p };
  }
  return Array.from({ length: max }, (_, idx) => ({
    idx,
    player: byseat[idx] || null,
  }));
});

// Calcule la position angulaire de chaque siège autour de la table
function seatStyle(seatIdx) {
  if (!table.value) return {};
  const max = table.value.max_players;

  // Mon siège est forcement en bas (ou siège 0 si je ne suis pas assis)
  const offset = mySession.value ? mySession.value.seat : 0;
  // Sieges "logiques" : 0 = bas, 1 = bas-gauche, ... rotation horaire
  const logical = (seatIdx - offset + max) % max;
  // angle 0 = top, on veut logical 0 = bottom -> +180°
  const angle = 180 + (logical * 360) / max;
  const rad = (angle * Math.PI) / 180;
  const rx = 44;            // % horizontal
  const ry = 38;            // % vertical
  const x = 50 + rx * Math.sin(rad);
  const y = 50 - ry * Math.cos(rad);
  return {
    left: `${x}%`,
    top: `${y}%`,
    transform: "translate(-50%, -50%)",
  };
}

// Lookup des hole cards de la derniere main (shown_holes + winners),
// pour pouvoir afficher 2 cartes greyed sur chaque siege apres la main.
const lastHandHoles = computed(() => {
  const m = new Map();
  const settle = lastHand.value?.settlement;
  if (!settle) return m;
  for (const sh of settle.shown_holes || []) {
    if (sh.username && sh.hole_cards?.length) {
      m.set(sh.username, sh.hole_cards);
    }
  }
  for (const pot of settle.pots || []) {
    for (const w of pot.winners || []) {
      if (w.username && w.hole_cards?.length) {
        m.set(w.username, w.hole_cards);
      }
    }
  }
  return m;
});

function seatHoleCards(player) {
  // Main en cours
  if (hand.value?.players) {
    if (player.username === me.value && hand.value?.my_hole_cards) {
      return hand.value.my_hole_cards.map((card) => ({
        card, hidden: false, faded: false,
      }));
    }
    if (player.folded) return [];
    return [
      { card: "", hidden: true, faded: false },
      { card: "", hidden: true, faded: false },
    ];
  }
  // Main finie : on montre les 2 hole cards greyed pour tout le monde
  const lh = lastHandHoles.value.get(player.username);
  if (lh?.length) {
    return lh.map((card) => ({ card, hidden: false, faded: true }));
  }
  return [];
}

// ─── Actions ─────────────────────────────────────────────
async function onSit() {
  error.value = null;
  try {
    await poker.sit(tableId.value, sitBuyin.value);
  } catch (e) {
    error.value = e.message;
  }
}

async function onLeave() {
  error.value = null;
  try {
    await poker.leave(tableId.value);
  } catch (e) {
    error.value = e.message;
  }
}

async function onStartHand() {
  error.value = null;
  try {
    await poker.startHand(tableId.value);
  } catch (e) {
    error.value = e.message;
  }
}

async function onAct(move, amount = 0) {
  error.value = null;
  try {
    await poker.act(tableId.value, move, amount);
    // Reset raise amount au minimum suivant
    if (hand.value) {
      raiseAmount.value = (hand.value.current_bet || 0) + (hand.value.min_raise || 1);
    }
  } catch (e) {
    error.value = e.message;
  }
}

// ─── Lifecycle ───────────────────────────────────────────
let stopPolling = null;

onMounted(async () => {
  // S'assure que wallet.me est chargé pour `me.value`
  if (!wallet.me) await wallet.refresh().catch(() => {});
  stopPolling = poker.startPolling(tableId.value);
});

onBeforeUnmount(() => {
  if (stopPolling) stopPolling();
});

// Quand la config de table arrive, init le buyin par defaut au min
watch(
  () => table.value,
  (t) => {
    if (t && !sitBuyin.value) {
      sitBuyin.value = t.min_buyin;
    }
  },
);

// Synchronise raiseAmount avec le min courant a chaque changement de hand
watch(
  () => hand.value?.current_bet,
  () => {
    if (!hand.value) return;
    const min = (hand.value.current_bet || 0) + (hand.value.min_raise || 1);
    if (raiseAmount.value < min) raiseAmount.value = min;
  },
);
</script>

<style scoped>
.header {
  display: flex;
  align-items: center;
  gap: 1em;
  margin-bottom: 1em;
}
.header h2 {
  margin: 0;
  font-size: 1.4em;
}
.blinds {
  color: var(--text-2);
  font-size: 0.85em;
}
.back {
  color: var(--text-2);
  text-decoration: none;
  font-size: 0.9em;
}
.back:hover {
  color: var(--camp);
}

.sit-card {
  margin-bottom: 1em;
}
.sit-card h3 {
  margin: 0 0 0.3em 0;
}
.form-row {
  display: flex;
  gap: 0.5em;
  margin-top: 0.6em;
  align-items: center;
}
.input {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0.5em 0.7em;
  color: var(--text-0);
  font-size: 0.95em;
}
.input.num {
  width: 110px;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

/* ─── Table ovale ─── */
.board-wrap {
  margin-bottom: 1em;
}
.board-frame {
  position: relative;
  width: 100%;
  max-width: 760px;
  aspect-ratio: 16 / 9;
  margin: 0 auto;
  background:
    radial-gradient(
      ellipse at 50% 40%,
      rgba(46, 134, 70, 0.45) 0%,
      rgba(14, 50, 30, 0.85) 60%,
      rgba(7, 16, 11, 1) 100%
    );
  border: 6px solid #2a1810;
  border-radius: 50% / 25%;
  box-shadow:
    inset 0 4px 30px rgba(0, 0, 0, 0.6),
    0 12px 40px rgba(0, 0, 0, 0.45);
}
.centre {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.6em;
}
.board-cards {
  display: flex;
  gap: 0.3em;
}
.pot {
  display: flex;
  flex-direction: column;
  align-items: center;
  color: var(--gold, #f5c842);
  font-weight: 700;
}
.pot .lbl {
  font-size: 0.7em;
  letter-spacing: 0.1em;
  opacity: 0.75;
}
.pot .val {
  font-size: 1.15em;
}
.street-tag {
  font-size: 0.75em;
  color: rgba(255, 255, 255, 0.5);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

/* ─── Sieges ─── */
.seat {
  position: absolute;
  width: 120px;
  background: rgba(14, 18, 26, 0.85);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0.4em 0.5em;
  text-align: center;
  font-size: 0.78em;
  transition: border-color 0.18s, box-shadow 0.18s, transform 0.18s;
}
.seat.filled.me {
  border-color: var(--camp);
  box-shadow: 0 0 0 1px var(--camp), 0 6px 16px -8px var(--camp-glow);
}
.seat.to_act {
  border-color: var(--gold, #f5c842);
  box-shadow: 0 0 0 1px var(--gold, #f5c842), 0 6px 16px -8px rgba(245, 200, 66, 0.5);
  animation: pulse 1.4s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 1px var(--gold, #f5c842), 0 0 16px rgba(245,200,66,0.3); }
  50%      { box-shadow: 0 0 0 2px var(--gold, #f5c842), 0 0 24px rgba(245,200,66,0.55); }
}
.seat.folded {
  opacity: 0.45;
}
.seat-head {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.1em;
  margin-bottom: 0.25em;
}
.seat-name {
  font-weight: 700;
  color: var(--text-0);
}
.seat-stack {
  color: var(--gold, #f5c842);
  font-size: 0.95em;
}
.seat-hole {
  display: flex;
  justify-content: center;
  gap: 2px;
  min-height: 44px;
}
.seat-bet {
  margin-top: 0.25em;
  font-size: 0.95em;
  color: var(--gold, #f5c842);
}
.seat-tags {
  display: flex;
  justify-content: center;
  gap: 0.25em;
  margin-top: 0.2em;
}
.tag {
  display: inline-block;
  font-size: 0.62em;
  padding: 0.1em 0.4em;
  background: var(--bg-3);
  border-radius: 3px;
  color: var(--text-2);
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.dealer-tag {
  background: #d8d8d8;
  color: #111;
}
.fold-tag {
  background: var(--red-soft);
  color: var(--red);
}
.allin-tag {
  background: var(--gold-soft, rgba(245, 200, 66, 0.18));
  color: var(--gold, #f5c842);
}
.empty-seat {
  color: var(--text-3);
  padding: 1.2em 0;
}

/* ─── Actions bar ─── */
.actions-bar {
  display: flex;
  flex-direction: column;
  gap: 0.6em;
  margin: 1em 0;
  position: sticky;
  bottom: 0.6em;
  z-index: 10;
  box-shadow: 0 8px 24px -8px rgba(0, 0, 0, 0.4);
}
.actions-info {
  display: flex;
  gap: 0.4em 0.5em;
  align-items: center;
  flex-wrap: wrap;
  font-size: 0.88em;
}
.actions-info .lbl {
  color: var(--gold, #f5c842);
  font-weight: 700;
  font-size: 1em;
  text-transform: none;
  letter-spacing: 0;
}
.actions-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4em;
  align-items: stretch;
}
.btn.danger {
  color: var(--red);
}
.btn.gold {
  background: var(--gold, #f5c842);
  color: #1a1a1a;
}

/* ─── Bouton Nouvelle main ─── */
.new-hand-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.7em;
  margin-bottom: 0.9em;
  border: 1px dashed var(--border-strong);
}
.new-hand-bar.ready {
  border-style: solid;
  border-color: rgba(245, 200, 66, 0.55);
  background:
    linear-gradient(135deg, rgba(245, 200, 66, 0.08), rgba(255, 122, 0, 0.04));
}
.new-hand-info {
  display: flex;
  flex-direction: column;
  gap: 0.15em;
  min-width: 0;
}
.btn.big {
  min-height: 46px;
  padding: 0.7em 1.2em;
  font-size: 1em;
  font-weight: 700;
  white-space: nowrap;
}

/* ─── Resultat (mobile-first) ─── */
.result {
  display: flex;
  flex-direction: column;
  gap: 0.9em;
}
.result-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.6em;
}
.result-head h3 {
  margin: 0;
  font-size: 1.1em;
}
.next-pill {
  background: var(--bg-2);
  border: 1px solid var(--border);
  color: var(--text-2);
  font-size: 0.72em;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 0.25em 0.6em;
  border-radius: 999px;
}
.result-board {
  display: flex;
  align-items: center;
  gap: 0.5em;
  flex-wrap: wrap;
  background: var(--bg-2);
  padding: 0.5em 0.7em;
  border-radius: var(--radius-sm);
}
.result-board-cards {
  display: flex;
  gap: 0.25em;
  flex-wrap: wrap;
}
.lbl {
  color: var(--text-3);
  font-size: 0.72em;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.pot-block {
  display: flex;
  flex-direction: column;
  gap: 0.5em;
}
.pot-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.6em;
  padding: 0 0.1em;
}
.pot-tag {
  color: var(--text-2);
  font-size: 0.78em;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.pot-total {
  color: var(--gold, #f5c842);
  font-size: 1.05em;
  font-weight: 700;
}

.winner-card {
  background:
    linear-gradient(135deg, rgba(245, 200, 66, 0.12), rgba(255, 122, 0, 0.06));
  border: 1px solid rgba(245, 200, 66, 0.45);
  border-radius: var(--radius-sm);
  padding: 0.8em 0.85em;
  display: flex;
  flex-direction: column;
  gap: 0.55em;
}
.winner-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.6em;
}
.winner-id {
  display: flex;
  align-items: center;
  gap: 0.6em;
  min-width: 0;
}
.avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 0.95em;
  background: linear-gradient(135deg, #f5c842, #ff9700);
  color: #1a1a1a;
  flex-shrink: 0;
}
.avatar.small {
  width: 28px;
  height: 28px;
  font-size: 0.85em;
  background: var(--bg-3);
  color: var(--text-0);
}
.winner-name {
  display: flex;
  align-items: center;
  gap: 0.35em;
  font-size: 1em;
  overflow: hidden;
  text-overflow: ellipsis;
}
.trophy {
  font-size: 0.9em;
}
.winner-label {
  color: var(--text-2);
  font-size: 0.85em;
}
.winner-amount {
  color: var(--green);
  font-weight: 800;
  font-size: 1.05em;
  background: var(--green-soft);
  padding: 0.25em 0.6em;
  border-radius: 999px;
  white-space: nowrap;
  flex-shrink: 0;
}
/* Rangee de cartes (winner + loser). Wrap si besoin sur mobile. */
.card-row {
  display: flex;
  gap: 0.25em;
  flex-wrap: wrap;
}
:deep(.card.card-faded) {
  opacity: 0.4;
  filter: grayscale(60%);
}

.losers {
  display: flex;
  flex-direction: column;
  gap: 0.5em;
  border-top: 1px solid var(--border);
  padding-top: 0.7em;
}
.losers-title {
  margin: 0;
  font-size: 0.78em;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-2);
}
.loser-row {
  display: flex;
  flex-direction: column;
  gap: 0.45em;
  padding: 0.6em 0.7em;
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}
.loser-row.folded {
  opacity: 0.85;
  background: var(--bg-1);
}
.loser-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.6em;
}
.loser-id {
  display: flex;
  align-items: center;
  gap: 0.55em;
  flex: 1;
  min-width: 0;
}
.loser-meta {
  min-width: 0;
}
.loser-name {
  display: flex;
  align-items: center;
  gap: 0.4em;
  font-size: 0.95em;
}
.loser-amount {
  color: var(--red);
  font-variant-numeric: tabular-nums;
  font-weight: 700;
  font-size: 0.92em;
  white-space: nowrap;
  background: var(--red-soft);
  padding: 0.18em 0.55em;
  border-radius: 999px;
}
.loser-amount.pos {
  color: var(--green);
  background: var(--green-soft);
}

.scoreboard {
  border-top: 1px solid var(--border);
  padding-top: 0.7em;
}
.score-rows {
  display: flex;
  flex-direction: column;
  gap: 0.2em;
  margin-top: 0.4em;
}
.score-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.4em 0.6em;
  border-radius: var(--radius-sm);
  font-size: 0.92em;
  background: var(--bg-2);
}
.score-row.winner {
  background: var(--green-soft);
  color: var(--green);
}
.score-row.loser .score-net {
  color: var(--red);
}
.score-row.me {
  outline: 1px solid var(--camp);
}
.score-name {
  display: inline-flex;
  align-items: center;
  gap: 0.4em;
  font-weight: 600;
}
.me-tag {
  font-size: 0.7em;
  background: var(--camp);
  color: white;
  padding: 0.1em 0.4em;
  border-radius: 4px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.fold-mark {
  font-size: 0.72em;
  color: var(--text-3);
  padding: 0.1em 0.35em;
  background: var(--bg-3);
  border-radius: 3px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.score-net {
  font-weight: 700;
}

.leave-row {
  margin-top: 1em;
  text-align: center;
}
.alert.err {
  background: var(--red-soft);
  color: var(--red);
  border: 1px solid var(--red);
  padding: 0.6em 0.8em;
  border-radius: var(--radius-sm);
  margin-bottom: 0.8em;
}
.dim {
  color: var(--text-2);
}
.small {
  font-size: 0.85em;
}
.mono {
  font-variant-numeric: tabular-nums;
}

/* ─── Action bar : layout mobile clair ─── */
@media (max-width: 640px) {
  .board-frame {
    aspect-ratio: 6 / 5;
    border-width: 4px;
  }
  .seat {
    width: 88px;
    padding: 0.3em 0.35em;
    font-size: 0.7em;
  }
  .seat-hole {
    min-height: 36px;
  }
  .board-cards :deep(.card.large) {
    width: 38px;
    height: 56px;
    padding: 3px 4px;
  }
  .board-cards :deep(.card.large .suit) {
    font-size: 1.15em;
  }
  .actions-buttons {
    gap: 0.35em;
  }
  .actions-buttons .btn {
    min-height: 44px;
    padding: 0.55em 0.9em;
    flex: 1 1 auto;
  }
  .actions-buttons .input.num {
    flex: 1 1 90px;
    min-width: 90px;
    min-height: 44px;
  }
  .form-row {
    flex-wrap: wrap;
  }
  .form-row .input {
    flex: 1 1 120px;
    min-height: 44px;
  }
  .form-row .btn {
    flex: 1 1 100%;
    min-height: 44px;
  }
  .header h2 {
    font-size: 1.15em;
  }
  .header {
    flex-wrap: wrap;
    row-gap: 0.3em;
  }
  .leave-row .btn {
    width: 100%;
    min-height: 44px;
  }
  .new-hand-bar {
    flex-wrap: wrap;
    gap: 0.5em;
  }
  .new-hand-bar .btn {
    width: 100%;
  }
  /* Result panel : un peu plus compact */
  .winner-row {
    align-items: flex-start;
  }
  .winner-amount {
    font-size: 0.95em;
    padding: 0.2em 0.55em;
  }
  .pot-total {
    font-size: 0.98em;
  }
}

@media (max-width: 380px) {
  .seat {
    width: 78px;
    font-size: 0.66em;
  }
  .seat-hole {
    min-height: 32px;
  }
  .board-cards :deep(.card.large) {
    width: 32px;
    height: 48px;
    padding: 2px 3px;
  }
  .board-cards :deep(.card.large .rank) {
    font-size: 0.72em;
  }
  .board-cards :deep(.card.large .suit) {
    font-size: 0.95em;
  }
}
</style>
