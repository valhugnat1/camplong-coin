<template>
  <AppLayout>
    <main class="page fade-in narrow">
      <button class="back-link" @click="router.push({ name: 'paris-list' })">
        ← Retour
      </button>

      <div v-if="loading && !bet" class="empty">Chargement...</div>

      <div v-else-if="error && !bet" class="alert error">
        {{ error }}
      </div>

      <template v-else-if="bet">
        <!-- ─── En-tête ────────────────────────────────── -->
        <header class="bet-head">
          <div class="bet-head-top">
            <span v-if="bet.category" class="bet-cat">{{ bet.category }}</span>
            <BetStatusBadge :status="bet.status" />
          </div>
          <h1 class="bet-statement">{{ bet.statement }}</h1>
          <div class="bet-deadline mono">
            ⏱ Deadline : {{ formatFullDate(bet.deadline) }}
            <span v-if="!isPastDeadline" class="dim">
              · {{ relativeDeadline }}</span
            >
            <span v-else class="warn"> · ÉCHUE</span>
          </div>
        </header>

        <!-- ─── Pari : creator vs opponent ─────────────── -->
        <section class="vs-block">
          <article
            class="party"
            :class="bet.creator_side === 'yes' ? 'side-yes' : 'side-no'"
          >
            <div class="party-head">
              <span class="party-pos">{{
                bet.creator_side === "yes" ? "VRAI" : "FAUX"
              }}</span>
              <span class="party-role mono">CRÉATEUR</span>
            </div>
            <div class="party-name">{{ bet.creator_username }}</div>
            <div class="party-stake mono">
              {{ formatNum(bet.stake_creator) }} CAMP
            </div>
          </article>

          <div class="vs-divider">
            <span class="vs-circle">VS</span>
            <div class="pot mono">
              <span class="pot-label">POT</span>
              <span class="pot-value">{{ formatNum(pot) }}</span>
            </div>
          </div>

          <article
            class="party"
            :class="bet.creator_side === 'yes' ? 'side-no' : 'side-yes'"
          >
            <div class="party-head">
              <span class="party-pos">{{
                bet.creator_side === "yes" ? "FAUX" : "VRAI"
              }}</span>
              <span class="party-role mono">OPPOSANT</span>
            </div>
            <div v-if="bet.opponent_username" class="party-name">
              {{ bet.opponent_username }}
            </div>
            <div v-else class="party-name empty">À prendre</div>
            <div class="party-stake mono">
              {{ formatNum(bet.stake_opponent) }} CAMP
            </div>
          </article>
        </section>

        <!-- ─── Arbitre ────────────────────────────────── -->
        <section v-if="bet.arbiter_username" class="card arbiter-card">
          <div class="arbiter-icon">⚖️</div>
          <div class="arbiter-info">
            <div class="arbiter-label">Arbitre désigné</div>
            <div class="arbiter-name">{{ bet.arbiter_username }}</div>
          </div>
          <div v-if="bet.arbiter_fee_pct > 0" class="arbiter-fee mono">
            {{ bet.arbiter_fee_pct }}% commission
            <span class="dim">({{ formatNum(arbiterFee) }} CAMP)</span>
          </div>
        </section>

        <!-- ─── Résolution (si résolu) ─────────────────── -->
        <section v-if="bet.status === 'resolved'" class="resolved-card">
          <div class="resolved-icon">
            {{
              bet.resolution === "yes"
                ? "✓"
                : bet.resolution === "no"
                  ? "✗"
                  : "○"
            }}
          </div>
          <div>
            <div class="resolved-title">
              <template v-if="bet.resolution === 'void'"
                >Pari annulé (nul)</template
              >
              <template v-else>
                Verdict :
                <b>{{ bet.resolution === "yes" ? "VRAI" : "FAUX" }}</b>
              </template>
            </div>
            <div class="resolved-sub mono">
              Résolu par {{ bet.resolved_by }} ·
              {{ formatFullDate(bet.resolved_at) }}
            </div>
            <div
              v-if="winnerName && bet.resolution !== 'void'"
              class="resolved-winner"
            >
              🏆 Gagnant : <b>{{ winnerName }}</b> (gain net :
              {{ formatNum(winnerGain) }} CAMP)
            </div>
          </div>
        </section>

        <!-- ─── Actions contextuelles ──────────────────── -->
        <section v-if="hasActions" class="actions-card">
          <!-- Cas 1 : open, je peux matcher -->
          <div v-if="canMatch">
            <p class="action-prompt">
              Tu veux prendre ce pari côté
              <b :class="opponentSideClass">{{ opponentSide.toUpperCase() }}</b>
              ? Tu vas bloquer
              <b class="mono">{{ formatNum(bet.stake_opponent) }} CAMP</b>.
            </p>
            <p v-if="!enoughBalance" class="action-warning">
              ⚠️ Solde insuffisant : tu as {{ formatNum(walletBalance) }} CAMP.
            </p>
            <button
              class="btn-primary big"
              :disabled="!enoughBalance || acting"
              @click="doMatch"
            >
              {{
                acting
                  ? "Validation..."
                  : `Prendre ce pari (${formatNum(bet.stake_opponent)} CAMP)`
              }}
            </button>
          </div>

          <!-- Cas 2 : open, je suis le creator → je peux annuler -->
          <div v-else-if="canCancel">
            <p class="action-prompt">
              Tu peux annuler ce pari tant que personne ne l'a pris. Tes
              <b class="mono">{{ formatNum(bet.stake_creator) }} CAMP</b> te
              seront rendus.
            </p>
            <button
              class="btn-ghost danger"
              :disabled="acting"
              @click="confirmCancel"
            >
              {{ acting ? "Annulation..." : "Annuler mon pari" }}
            </button>
          </div>

          <!-- Cas 3 : matched, je suis l'arbitre → je peux résoudre -->
          <div v-else-if="canResolve">
            <p class="action-prompt">
              Tu es l'arbitre désigné. C'est à toi de trancher.
            </p>
            <div class="resolve-buttons">
              <button
                class="btn-resolve yes"
                :disabled="acting"
                @click="confirmResolve('yes')"
              >
                <span class="big">✓</span>
                <span>L'affirmation est VRAIE</span>
                <span class="dim mono"
                  >{{ formatNum(yesWinnerGain) }} CAMP →
                  {{ yesWinnerName }}</span
                >
              </button>
              <button
                class="btn-resolve no"
                :disabled="acting"
                @click="confirmResolve('no')"
              >
                <span class="big">✗</span>
                <span>L'affirmation est FAUSSE</span>
                <span class="dim mono"
                  >{{ formatNum(noWinnerGain) }} CAMP → {{ noWinnerName }}</span
                >
              </button>
              <button
                class="btn-resolve void"
                :disabled="acting"
                @click="confirmResolve('void')"
              >
                <span class="big">○</span>
                <span>Impossible de trancher (nul)</span>
                <span class="dim mono">Refund des deux côtés</span>
              </button>
            </div>
          </div>
        </section>

        <!-- ─── Erreur d'action ────────────────────────── -->
        <div v-if="actionError" class="alert error">{{ actionError }}</div>

        <!-- ─── Métadonnées ────────────────────────────── -->
        <section class="meta-card">
          <h3>Détails</h3>
          <div class="meta-row mono">
            <span>Créé le</span>
            <span>{{ formatFullDate(bet.created_at) }}</span>
          </div>
          <div v-if="bet.matched_at" class="meta-row mono">
            <span>Matché le</span>
            <span>{{ formatFullDate(bet.matched_at) }}</span>
          </div>
          <div class="meta-row mono">
            <span>Cote</span>
            <span>{{ bet.odds_num }} : {{ bet.odds_den }}</span>
          </div>
          <div class="meta-row mono">
            <span>ID</span>
            <span>#{{ bet.id }}</span>
          </div>
          <div v-if="bet.tx_hash_lock_creator" class="meta-row mono">
            <span>Lock créateur</span>
            <a
              :href="`https://sepolia.basescan.org/tx/${bet.tx_hash_lock_creator}`"
              target="_blank"
              class="tx-link"
            >
              {{ shortHash(bet.tx_hash_lock_creator) }} ↗
            </a>
          </div>
          <div v-if="bet.tx_hash_lock_opponent" class="meta-row mono">
            <span>Lock opposant</span>
            <a
              :href="`https://sepolia.basescan.org/tx/${bet.tx_hash_lock_opponent}`"
              target="_blank"
              class="tx-link"
            >
              {{ shortHash(bet.tx_hash_lock_opponent) }} ↗
            </a>
          </div>
          <div v-if="bet.tx_hash_payout_winner" class="meta-row mono">
            <span>Payout gagnant</span>
            <a
              :href="`https://sepolia.basescan.org/tx/${bet.tx_hash_payout_winner}`"
              target="_blank"
              class="tx-link"
            >
              {{ shortHash(bet.tx_hash_payout_winner) }} ↗
            </a>
          </div>
        </section>
      </template>
    </main>
  </AppLayout>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { storeToRefs } from "pinia";
import AppLayout from "@/components/layout/AppLayout.vue";
import BetStatusBadge from "@/components/bets/BetStatusBadge.vue";
import { useAuthStore } from "@/stores/auth";
import { useWalletStore } from "@/stores/wallet";
import { useBetsStore } from "@/stores/bets";
import { formatNum } from "@/config";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const wallet = useWalletStore();
const betsStore = useBetsStore();
const { detail: bet, loading, error } = storeToRefs(betsStore);

const walletBalance = computed(() => Number(wallet.me?.balance ?? 0));

const acting = ref(false);
const actionError = ref("");

// ─── Computed : rôles + permissions ─────────────────────
const isCreator = computed(() => bet.value?.creator_username === auth.username);
const isOpponent = computed(
  () => bet.value?.opponent_username === auth.username,
);
const isArbiter = computed(() => bet.value?.arbiter_username === auth.username);

const isPastDeadline = computed(
  () => bet.value && new Date(bet.value.deadline) < new Date(),
);

const canMatch = computed(
  () =>
    bet.value?.status === "open" && !isCreator.value && !isPastDeadline.value,
);

const canCancel = computed(
  () => bet.value?.status === "open" && isCreator.value,
);

const canResolve = computed(
  () => bet.value?.status === "matched" && isArbiter.value,
);

const hasActions = computed(
  () => canMatch.value || canCancel.value || canResolve.value,
);

const enoughBalance = computed(
  () => (walletBalance.value || 0) >= (bet.value?.stake_opponent || 0),
);

// ─── Computed : calculs ─────────────────────────────────
const pot = computed(
  () => (bet.value?.stake_creator || 0) + (bet.value?.stake_opponent || 0),
);

const arbiterFee = computed(() => {
  if (!bet.value?.arbiter_fee_pct) return 0;
  return Math.floor((pot.value * bet.value.arbiter_fee_pct) / 100);
});

const winnerGain = computed(() => pot.value - arbiterFee.value);

const opponentSide = computed(() =>
  bet.value?.creator_side === "yes" ? "faux" : "vrai",
);
const opponentSideClass = computed(() =>
  bet.value?.creator_side === "yes" ? "side-no-text" : "side-yes-text",
);

const winnerName = computed(() => {
  if (
    !bet.value ||
    bet.value.status !== "resolved" ||
    bet.value.resolution === "void"
  )
    return null;
  return bet.value.resolution === bet.value.creator_side
    ? bet.value.creator_username
    : bet.value.opponent_username;
});

// Pour les boutons de résolution (preview du gagnant selon l'option)
const yesWinnerName = computed(() =>
  bet.value?.creator_side === "yes"
    ? bet.value.creator_username
    : bet.value?.opponent_username,
);
const noWinnerName = computed(() =>
  bet.value?.creator_side === "no"
    ? bet.value.creator_username
    : bet.value?.opponent_username,
);
const yesWinnerGain = computed(() => winnerGain.value);
const noWinnerGain = computed(() => winnerGain.value);

const relativeDeadline = computed(() => {
  if (!bet.value?.deadline) return "";
  const d = new Date(bet.value.deadline) - new Date();
  if (d < 0) return "";
  const days = Math.floor(d / (1000 * 60 * 60 * 24));
  const hours = Math.floor(d / (1000 * 60 * 60));
  if (hours < 1) return `dans ${Math.floor(d / 60000)} min`;
  if (hours < 24) return `dans ${hours}h`;
  return `dans ${days}j`;
});

// ─── Actions ────────────────────────────────────────────
async function doMatch() {
  if (
    !confirm(
      `Confirmer la prise du pari pour ${formatNum(bet.value.stake_opponent)} CAMP ?`,
    )
  )
    return;
  acting.value = true;
  actionError.value = "";
  try {
    await betsStore.match(bet.value.id);
  } catch (e) {
    actionError.value = e.message;
  } finally {
    acting.value = false;
  }
}

async function confirmCancel() {
  if (!confirm("Annuler ce pari ? Tes CAMP te seront rendus on-chain.")) return;
  acting.value = true;
  actionError.value = "";
  try {
    await betsStore.cancel(bet.value.id);
  } catch (e) {
    actionError.value = e.message;
  } finally {
    acting.value = false;
  }
}

async function confirmResolve(resolution) {
  const labels = { yes: "VRAI", no: "FAUX", void: "NUL (annulation)" };
  if (
    !confirm(
      `Résoudre ce pari : ${labels[resolution]} ?\n\nCette action est irréversible.`,
    )
  )
    return;
  acting.value = true;
  actionError.value = "";
  try {
    await betsStore.resolve(bet.value.id, resolution);
  } catch (e) {
    actionError.value = e.message;
  } finally {
    acting.value = false;
  }
}

// ─── Helpers ────────────────────────────────────────────
function formatFullDate(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleString("fr-FR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function shortHash(h) {
  if (!h) return "";
  return `${h.slice(0, 8)}...${h.slice(-6)}`;
}

// ─── Init ───────────────────────────────────────────────
onMounted(async () => {
  await betsStore.fetchDetail(route.params.id);
  // Best-effort refresh wallet
  try {
    if (typeof wallet.refresh === "function") await wallet.refresh();
    else if (typeof wallet.load === "function") await wallet.load();
    else if (typeof wallet.fetch === "function") await wallet.fetch();
  } catch (e) {
    /* silent */
  }
});
</script>

<style scoped>
.narrow {
  max-width: 760px;
  margin: 0 auto;
}

.back-link {
  background: none;
  border: none;
  color: var(--text-2);
  font-size: 0.9em;
  cursor: pointer;
  margin-bottom: 1em;
  padding: 0;
}
.back-link:hover {
  color: var(--text-0);
}

.bet-head {
  margin-bottom: 1.5em;
}
.bet-head-top {
  display: flex;
  gap: 0.6em;
  margin-bottom: 0.7em;
  align-items: center;
}
.bet-cat {
  font-size: 0.7em;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--violet);
  font-weight: 700;
}
.bet-statement {
  font-size: 1.7em;
  line-height: 1.25;
  letter-spacing: -0.02em;
  margin-bottom: 0.5em;
}
.bet-deadline {
  font-size: 0.85em;
  color: var(--text-2);
}
.dim {
  color: var(--text-3);
}
.warn {
  color: var(--red);
  font-weight: 700;
}

/* ─── VS Block ────────────────────────────────────── */
.vs-block {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 1em;
  align-items: stretch;
  margin-bottom: 1.5em;
}

.party {
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.3em;
  display: flex;
  flex-direction: column;
  gap: 0.5em;
}
.party.side-yes {
  border-left: 4px solid var(--green);
}
.party.side-no {
  border-left: 4px solid var(--red);
}

.party-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.party-pos {
  font-size: 1.4em;
  font-weight: 800;
  letter-spacing: 0.05em;
}
.party.side-yes .party-pos {
  color: var(--green);
}
.party.side-no .party-pos {
  color: var(--red);
}

.party-role {
  font-size: 0.7em;
  color: var(--text-3);
  letter-spacing: 0.1em;
}

.party-name {
  font-size: 1.1em;
  font-weight: 600;
}
.party-name.empty {
  color: var(--text-3);
  font-style: italic;
  font-weight: 400;
}

.party-stake {
  font-size: 1.05em;
  font-weight: 700;
  color: var(--text-0);
  margin-top: auto;
}

.vs-divider {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.7em;
}
.vs-circle {
  width: 3em;
  height: 3em;
  border-radius: 50%;
  background: var(--bg-2);
  border: 1px solid var(--border-strong);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 0.85em;
  color: var(--text-2);
  letter-spacing: 0.05em;
}
.pot {
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: 0.1em;
}
.pot-label {
  font-size: 0.65em;
  color: var(--text-3);
  letter-spacing: 0.15em;
}
.pot-value {
  font-size: 1.1em;
  font-weight: 700;
  color: var(--gold);
}

/* ─── Cards génériques ─────────────────────────────── */
.card {
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.2em 1.3em;
  margin-bottom: 1em;
}

.arbiter-card {
  display: flex;
  align-items: center;
  gap: 1em;
}
.arbiter-icon {
  font-size: 1.6em;
}
.arbiter-info {
  flex: 1;
}
.arbiter-label {
  font-size: 0.78em;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--text-2);
}
.arbiter-name {
  font-size: 1.1em;
  font-weight: 600;
}
.arbiter-fee {
  font-size: 0.85em;
  color: var(--text-1);
}

/* ─── Résolu ───────────────────────────────────────── */
.resolved-card {
  background: linear-gradient(
    135deg,
    rgba(154, 78, 255, 0.05),
    rgba(20, 224, 142, 0.05)
  );
  border: 1px solid var(--violet);
  border-radius: var(--radius);
  padding: 1.3em;
  margin-bottom: 1em;
  display: flex;
  gap: 1em;
  align-items: center;
}
.resolved-icon {
  font-size: 2.5em;
  font-weight: 800;
  color: var(--violet);
  line-height: 1;
}
.resolved-title {
  font-size: 1.2em;
  font-weight: 700;
  margin-bottom: 0.3em;
}
.resolved-sub {
  font-size: 0.8em;
  color: var(--text-3);
}
.resolved-winner {
  margin-top: 0.7em;
  font-size: 0.95em;
  color: var(--green);
}

/* ─── Actions ──────────────────────────────────────── */
.actions-card {
  background: var(--bg-1);
  border: 1px solid var(--violet);
  border-radius: var(--radius);
  padding: 1.5em;
  margin-bottom: 1em;
  box-shadow: 0 0 0 3px rgba(154, 78, 255, 0.08);
}
.action-prompt {
  margin-bottom: 1em;
  color: var(--text-1);
}
.action-warning {
  color: var(--red);
  font-size: 0.9em;
  margin-bottom: 1em;
}
.side-yes-text {
  color: var(--green);
}
.side-no-text {
  color: var(--red);
}

.btn-primary.big {
  width: 100%;
  padding: 1em;
  font-size: 1.05em;
}
.btn-ghost.danger {
  color: var(--red);
  border-color: var(--red);
}
.btn-ghost.danger:hover {
  background: rgba(255, 69, 102, 0.08);
}

.resolve-buttons {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 0.6em;
}
.btn-resolve {
  background: var(--bg-2);
  border: 2px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 1em 0.6em;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.3em;
  cursor: pointer;
  transition: all 0.15s;
  font-size: 0.85em;
  text-align: center;
}
.btn-resolve:hover:not(:disabled) {
  transform: translateY(-2px);
}
.btn-resolve:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.btn-resolve .big {
  font-size: 2em;
  font-weight: 800;
  line-height: 1;
}
.btn-resolve.yes:hover {
  border-color: var(--green);
  background: rgba(20, 224, 142, 0.08);
}
.btn-resolve.no:hover {
  border-color: var(--red);
  background: rgba(255, 69, 102, 0.08);
}
.btn-resolve.void:hover {
  border-color: var(--text-2);
}
.btn-resolve.yes .big {
  color: var(--green);
}
.btn-resolve.no .big {
  color: var(--red);
}
.btn-resolve.void .big {
  color: var(--text-2);
}

/* ─── Meta ─────────────────────────────────────────── */
.meta-card {
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.2em 1.3em;
}
.meta-card h3 {
  font-size: 0.78em;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--text-2);
  margin-bottom: 0.9em;
}
.meta-row {
  display: flex;
  justify-content: space-between;
  padding: 0.4em 0;
  border-bottom: 1px dashed var(--border);
  font-size: 0.85em;
  color: var(--text-1);
}
.meta-row:last-child {
  border-bottom: none;
}
.tx-link {
  color: var(--violet);
  text-decoration: none;
}
.tx-link:hover {
  text-decoration: underline;
}

.alert.error {
  background: rgba(255, 69, 102, 0.1);
  border: 1px solid var(--red);
  border-radius: var(--radius-sm);
  padding: 0.8em 1em;
  color: var(--red);
  margin-bottom: 1em;
}

.empty {
  text-align: center;
  padding: 3em 1em;
  color: var(--text-2);
}

@media (max-width: 640px) {
  .vs-block {
    grid-template-columns: 1fr;
    gap: 0.6em;
  }
  .vs-divider {
    flex-direction: row;
  }
  .resolve-buttons {
    grid-template-columns: 1fr;
  }
  .bet-statement {
    font-size: 1.3em;
  }
}
</style>
