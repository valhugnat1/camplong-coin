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
            <BetStatusBadge :status="bet.status" />
            <span class="bet-type mono">
              {{ bet.type === "yes_no" ? "Oui / Non" : `${bet.options.length} choix` }}
            </span>
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

        <!-- ─── Pot summary ────────────────────────────── -->
        <section class="pot-card">
          <div class="pot-block">
            <span class="pot-label">Mise unique</span>
            <span class="pot-value mono">{{ formatNum(bet.stake) }} CAMP</span>
          </div>
          <div class="pot-block">
            <span class="pot-label">Participants</span>
            <span class="pot-value mono">{{ bet.participants_count }}</span>
          </div>
          <div class="pot-block big">
            <span class="pot-label">Pot total</span>
            <span class="pot-value gold mono"
              >{{ formatNum(bet.pot_total) }} CAMP</span
            >
          </div>
        </section>

        <!-- ─── Options + barres ───────────────────────── -->
        <section class="card opts-section">
          <h3 class="card-title">Options</h3>
          <div
            v-for="o in bet.options"
            :key="o.id"
            class="opt"
            :class="{
              mine: o.id === bet.my_option_id,
              winner:
                bet.status === 'resolved' &&
                !bet.resolution_void &&
                o.id === bet.resolution_option_id,
            }"
          >
            <div class="opt-bar-wrap">
              <div
                class="opt-bar"
                :style="{ width: optionWidth(o) + '%' }"
              />
            </div>
            <div class="opt-content">
              <div class="opt-head">
                <span class="opt-label">{{ o.label }}</span>
                <span v-if="o.id === bet.my_option_id" class="opt-tag mine-tag">★ Ma mise</span>
                <span
                  v-if="
                    bet.status === 'resolved' &&
                    !bet.resolution_void &&
                    o.id === bet.resolution_option_id
                  "
                  class="opt-tag win-tag"
                  >🏆 Gagnante</span
                >
              </div>
              <div class="opt-stats mono">
                {{ o.participants_count }} mise{{
                  o.participants_count > 1 ? "s" : ""
                }}
                · {{ formatNum(o.total_staked) }} CAMP
              </div>
            </div>
          </div>
        </section>

        <!-- ─── Arbitre ────────────────────────────────── -->
        <section v-if="bet.arbiter_username" class="card arbiter-card">
          <div class="arbiter-icon">⚖️</div>
          <div class="arbiter-info">
            <div class="arbiter-label">Arbitre désigné</div>
            <div class="arbiter-name">{{ bet.arbiter_username }}</div>
          </div>
        </section>
        <section v-else class="card vote-info-card">
          <div class="arbiter-icon">🗳️</div>
          <div class="arbiter-info">
            <div class="arbiter-label">Résolution communautaire</div>
            <div class="arbiter-name">
              {{ bet.votes_count }} vote{{ bet.votes_count > 1 ? "s" : "" }} ·
              2 voix concordantes = résolution auto
            </div>
          </div>
        </section>

        <!-- ─── Résolution ─────────────────────────────── -->
        <section v-if="bet.status === 'resolved'" class="resolved-card">
          <div class="resolved-icon">
            {{ bet.resolution_void ? "○" : "🏆" }}
          </div>
          <div>
            <div class="resolved-title">
              <template v-if="bet.resolution_void"
                >Pari annulé (refund)</template
              >
              <template v-else>
                Verdict : <b>{{ bet.winning_label }}</b>
              </template>
            </div>
            <div class="resolved-sub mono">
              Résolu par {{ resolvedByLabel }} ·
              {{ formatFullDate(bet.resolved_at) }}
            </div>
            <div v-if="myPayout > 0" class="resolved-mine">
              💰 Tu touches <b>{{ formatNum(myPayout) }} CAMP</b>
            </div>
          </div>
        </section>

        <!-- ─── Action : rejoindre ─────────────────────── -->
        <section v-if="canJoin" class="actions-card join-card">
          <h3 class="card-title">Choisis ton option</h3>
          <p class="action-prompt">
            Mise <b class="mono">{{ formatNum(bet.stake) }} CAMP</b> sur
            l'option de ton choix.
            <span v-if="isCreator" class="dim">
              Tu es le créateur — tu peux aussi rejoindre ton propre pari.
            </span>
          </p>
          <p v-if="!enoughBalance" class="action-warning">
            ⚠️ Solde insuffisant : tu as
            {{ formatNum(walletBalance) }} CAMP.
          </p>
          <div class="join-buttons">
            <button
              v-for="o in bet.options"
              :key="o.id"
              class="btn-join"
              :disabled="!enoughBalance || acting"
              @click="confirmJoin(o)"
            >
              <span class="join-label">{{ o.label }}</span>
              <span class="join-sub mono">
                {{ o.participants_count }} mise{{
                  o.participants_count > 1 ? "s" : ""
                }}
              </span>
            </button>
          </div>
        </section>

        <!-- ─── Action : arbitrer (arbitre) ────────────── -->
        <section v-if="canResolve" class="actions-card resolve-card">
          <h3 class="card-title">Tu es l'arbitre — c'est à toi</h3>
          <p class="action-prompt">
            Choisis l'option gagnante, ou annule si impossible à trancher.
          </p>
          <div class="resolve-buttons">
            <button
              v-for="o in bet.options"
              :key="o.id"
              class="btn-resolve"
              :disabled="acting"
              @click="confirmResolve(o)"
            >
              <span class="big">{{ o.label }}</span>
              <span class="dim mono">
                {{ o.participants_count }} mise{{
                  o.participants_count > 1 ? "s" : ""
                }}
              </span>
            </button>
            <button
              class="btn-resolve void"
              :disabled="acting"
              @click="confirmResolve(null)"
            >
              <span class="big">○ Nul</span>
              <span class="dim mono">Refund tous</span>
            </button>
          </div>
        </section>

        <!-- ─── Action : vote communautaire ────────────── -->
        <section v-if="canVote" class="vote-section">
          <button
            v-if="!voteExpanded"
            class="btn-toggle-vote"
            @click="voteExpanded = true"
          >
            <span class="toggle-icon">🗳️</span>
            <span class="toggle-text">
              <template v-if="bet.my_has_voted">
                Modifier mon vote (actuel : <b>{{ myVoteOptionLabel }}</b>)
              </template>
              <template v-else>Voter pour résoudre le pari</template>
            </span>
            <span class="toggle-chevron">›</span>
          </button>

          <div v-else class="actions-card vote-card">
            <div class="vote-header">
              <h3 class="card-title">Vote sur la résolution</h3>
              <button
                class="btn-close"
                @click="voteExpanded = false"
                aria-label="Replier"
              >
                ✕
              </button>
            </div>
            <p class="action-prompt">
              <template v-if="!bet.my_has_voted">
                Tu peux voter pour décider du verdict. 2 votes concordants
                déclenchent la résolution.
              </template>
              <template v-else>
                Ton vote actuel : <b>{{ myVoteOptionLabel }}</b>. Tu peux le
                changer tant que le pari n'est pas résolu.
              </template>
            </p>
            <div class="resolve-buttons">
              <button
                v-for="o in bet.options"
                :key="o.id"
                class="btn-resolve"
                :class="{ selected: bet.my_vote_option_id === o.id }"
                :disabled="acting"
                @click="confirmVote(o)"
              >
                <span class="big">{{ o.label }}</span>
                <span class="dim mono">
                  {{ voteCountFor(o.id) }} voix
                </span>
              </button>
              <button
                class="btn-resolve void"
                :class="{
                  selected:
                    bet.my_has_voted && bet.my_vote_option_id === null,
                }"
                :disabled="acting"
                @click="confirmVote(null)"
              >
                <span class="big">○ Nul</span>
                <span class="dim mono">{{ voidVoteCount }} voix</span>
              </button>
            </div>
          </div>
        </section>

        <!-- ─── Action : annuler (créateur) ────────────── -->
        <section v-if="canCancel" class="actions-card cancel-card">
          <h3 class="card-title">Tu es le créateur</h3>
          <p class="action-prompt">
            <template v-if="bet.participants_count === 0">
              Personne n'a encore rejoint, tu peux annuler sans impact.
            </template>
            <template v-else>
              {{ bet.participants_count }} personne(s) ont déjà misé. Annuler
              = refund de tout le monde (toi compris si tu as misé).
            </template>
          </p>
          <button
            class="btn-ghost danger"
            :disabled="acting"
            @click="confirmCancel"
          >
            {{ acting ? "Annulation..." : "Annuler le pari" }}
          </button>
        </section>

        <!-- ─── Erreur d'action ────────────────────────── -->
        <div v-if="actionError" class="alert error">{{ actionError }}</div>

        <!-- ─── Participants ───────────────────────────── -->
        <section v-if="bet.participants.length" class="card">
          <h3 class="card-title">Participants</h3>
          <div class="participants-list">
            <div
              v-for="p in bet.participants"
              :key="p.username"
              class="participant"
            >
              <span class="part-name">{{ p.username }}</span>
              <span class="part-option dim">
                → {{ labelForOption(p.option_id) }}
              </span>
              <span class="part-amount mono">
                {{ formatNum(p.amount) }} CAMP
              </span>
            </div>
          </div>
        </section>

        <!-- ─── Métadonnées ────────────────────────────── -->
        <section class="meta-card">
          <h3 class="card-title">Détails</h3>
          <div class="meta-row mono">
            <span>Créé par</span>
            <span>{{ bet.creator_username }}</span>
          </div>
          <div class="meta-row mono">
            <span>Créé le</span>
            <span>{{ formatFullDate(bet.created_at) }}</span>
          </div>
          <div class="meta-row mono">
            <span>ID</span>
            <span>#{{ bet.id }}</span>
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
import { useWalletStore } from "@/stores/wallet";
import { useBetsStore } from "@/stores/bets";
import { formatNum } from "@/config";

const route = useRoute();
const router = useRouter();
const wallet = useWalletStore();
const betsStore = useBetsStore();
const { detail: bet, loading, error } = storeToRefs(betsStore);

const walletBalance = computed(() => Number(wallet.me?.balance ?? 0));

const acting = ref(false);
const actionError = ref("");
const voteExpanded = ref(false);

// ─── Rôles & permissions ─────────────────────────────────
const me = computed(() => wallet.me?.username);
const isCreator = computed(() => bet.value?.creator_username === me.value);
const isArbiter = computed(() => bet.value?.arbiter_username === me.value);
const isParticipant = computed(() => bet.value?.my_option_id != null);

const isPastDeadline = computed(
  () => bet.value && new Date(bet.value.deadline) < new Date(),
);

const canJoin = computed(
  () =>
    bet.value?.status === "open" &&
    !isPastDeadline.value &&
    !isParticipant.value &&
    !isArbiter.value,
);

const canCancel = computed(
  () => bet.value?.status === "open" && isCreator.value,
);

const canResolve = computed(
  () => bet.value?.status === "open" && isArbiter.value,
);

const canVote = computed(
  () =>
    bet.value?.status === "open" &&
    !bet.value?.arbiter_username &&
    !isArbiter.value,
);

// ─── Vote computed ───────────────────────────────────────
const myVoteOptionLabel = computed(() => {
  if (!bet.value?.my_has_voted) return null;
  const oid = bet.value.my_vote_option_id;
  if (oid == null) return "Nul";
  const o = bet.value.options.find((x) => x.id === oid);
  return o?.label || null;
});

function voteCountFor(optId) {
  if (!bet.value) return 0;
  return bet.value.votes.filter((v) => v.option_id === optId).length;
}

const voidVoteCount = computed(() => {
  if (!bet.value) return 0;
  return bet.value.votes.filter((v) => v.option_id === null).length;
});

// ─── Pot & odds ──────────────────────────────────────────
const enoughBalance = computed(
  () => (walletBalance.value || 0) >= (bet.value?.stake || 0),
);

const myPayout = computed(() => {
  if (!bet.value || bet.value.status !== "resolved" || !isParticipant.value)
    return 0;
  if (bet.value.resolution_void) return bet.value.stake;
  if (bet.value.my_option_id !== bet.value.resolution_option_id) return 0;
  const winningOpt = bet.value.options.find(
    (o) => o.id === bet.value.resolution_option_id,
  );
  if (!winningOpt || winningOpt.participants_count === 0) return 0;
  return Math.floor(bet.value.pot_total / winningOpt.participants_count);
});

function optionWidth(o) {
  const max = Math.max(
    1,
    ...(bet.value?.options || []).map((x) => x.participants_count),
  );
  return Math.round((o.participants_count / max) * 100);
}

function labelForOption(optId) {
  return bet.value?.options.find((o) => o.id === optId)?.label || "—";
}

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

const resolvedByLabel = computed(() => {
  const r = bet.value?.resolved_by;
  if (!r) return "";
  if (r === "__community__") return "accord communautaire (2 voix)";
  if (r === "__admin__") return "admin";
  if (r === "__expired__") return "expiration";
  return r;
});

// ─── Actions ─────────────────────────────────────────────
async function confirmJoin(opt) {
  if (
    !confirm(
      `Miser ${formatNum(bet.value.stake)} CAMP sur "${opt.label}" ?\n\nTu ne pourras plus changer.`,
    )
  )
    return;
  acting.value = true;
  actionError.value = "";
  try {
    await betsStore.join(bet.value.id, opt.id);
  } catch (e) {
    actionError.value = e.message;
  } finally {
    acting.value = false;
  }
}

async function confirmCancel() {
  const msg =
    bet.value.participants_count > 0
      ? `Annuler le pari ? Refund de ${bet.value.participants_count} participant(s).`
      : "Annuler le pari ?";
  if (!confirm(msg)) return;
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

async function confirmResolve(opt) {
  const label = opt ? `"${opt.label}"` : "NUL (refund tous)";
  if (
    !confirm(`Résoudre ce pari → ${label} ?\n\nIrréversible.`)
  )
    return;
  acting.value = true;
  actionError.value = "";
  try {
    await betsStore.resolve(bet.value.id, opt ? opt.id : null);
  } catch (e) {
    actionError.value = e.message;
  } finally {
    acting.value = false;
  }
}

async function confirmVote(opt) {
  const optId = opt ? opt.id : null;
  const label = opt ? `"${opt.label}"` : "NUL";
  const currentCount = optId == null ? voidVoteCount.value : voteCountFor(optId);
  const willSettle = currentCount >= 1; // ce vote en fera 2 si non doublonné par moi
  const msg = willSettle
    ? `Voter ${label} ? Quelqu'un a déjà voté pareil → le pari va se résoudre maintenant et déclencher les payouts.`
    : `Voter ${label} ? Tu pourras changer tant que le pari n'est pas résolu.`;
  if (!confirm(msg)) return;
  acting.value = true;
  actionError.value = "";
  try {
    await betsStore.vote(bet.value.id, optId);
  } catch (e) {
    actionError.value = e.message;
  } finally {
    acting.value = false;
  }
}

// ─── Helpers ─────────────────────────────────────────────
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

// ─── Init ────────────────────────────────────────────────
onMounted(async () => {
  await betsStore.fetchDetail(route.params.id);
  try {
    if (typeof wallet.refresh === "function") await wallet.refresh();
  } catch (e) {
    /* silent */
  }
});
</script>

<style scoped>
.narrow {
  max-width: 760px;
  margin: 0 auto;
  padding-bottom: 2em;
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
  margin-bottom: 1.2em;
}
.bet-head-top {
  display: flex;
  gap: 0.6em;
  margin-bottom: 0.7em;
  align-items: center;
}
.bet-type {
  font-size: 0.68em;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--text-3);
  font-weight: 700;
}
.bet-statement {
  font-size: 1.55em;
  line-height: 1.3;
  letter-spacing: -0.02em;
  margin: 0 0 0.6em;
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

/* ─── Pot card ───────────────────────────────────────── */
.pot-card {
  display: grid;
  grid-template-columns: 1fr 1fr 1.5fr;
  gap: 0.6em;
  background: var(--bg-1);
  border: 1px solid var(--violet);
  border-radius: var(--radius);
  padding: 1em;
  margin-bottom: 1em;
  box-shadow: 0 0 0 3px rgba(154, 78, 255, 0.08);
}
.pot-block {
  display: flex;
  flex-direction: column;
  gap: 0.1em;
  padding: 0.3em 0.5em;
}
.pot-block.big {
  border-left: 1px solid var(--border);
  padding-left: 0.9em;
}
.pot-label {
  font-size: 0.7em;
  color: var(--text-3);
  letter-spacing: 0.1em;
  text-transform: uppercase;
}
.pot-value {
  font-size: 1.1em;
  font-weight: 700;
  color: var(--text-0);
}
.pot-value.gold {
  color: var(--gold);
  font-size: 1.3em;
}

/* ─── Generic cards ──────────────────────────────────── */
.card {
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.1em 1.2em;
  margin-bottom: 1em;
}
.card-title {
  font-size: 0.78em;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--text-2);
  margin: 0 0 0.9em;
}

/* ─── Options section (detail) ───────────────────────── */
.opts-section {
  display: flex;
  flex-direction: column;
}
.opt {
  position: relative;
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0.7em 0.9em;
  overflow: hidden;
  margin-bottom: 0.5em;
}
.opt:last-child {
  margin-bottom: 0;
}
.opt.mine {
  border-color: var(--violet);
}
.opt.winner {
  border-color: var(--gold);
  background: linear-gradient(
    135deg,
    rgba(245, 200, 66, 0.1),
    rgba(245, 200, 66, 0.02)
  );
}
.opt-bar-wrap {
  position: absolute;
  inset: 0;
}
.opt-bar {
  height: 100%;
  background: linear-gradient(
    90deg,
    rgba(154, 78, 255, 0.18),
    rgba(154, 78, 255, 0.04)
  );
  transition: width 0.3s ease;
}
.opt.winner .opt-bar {
  background: linear-gradient(
    90deg,
    rgba(245, 200, 66, 0.25),
    rgba(245, 200, 66, 0.05)
  );
}
.opt-content {
  position: relative;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.6em;
  flex-wrap: wrap;
}
.opt-head {
  display: flex;
  align-items: center;
  gap: 0.5em;
  flex-wrap: wrap;
}
.opt-label {
  font-weight: 700;
  font-size: 1em;
  color: var(--text-0);
}
.opt-tag {
  font-size: 0.7em;
  padding: 0.15em 0.55em;
  border-radius: 999px;
  font-weight: 700;
  letter-spacing: 0.05em;
}
.mine-tag {
  background: rgba(154, 78, 255, 0.15);
  color: var(--violet);
}
.win-tag {
  background: rgba(245, 200, 66, 0.15);
  color: var(--gold);
}
.opt-stats {
  font-size: 0.82em;
  color: var(--text-2);
}

/* ─── Arbiter / vote info ────────────────────────────── */
.arbiter-card,
.vote-info-card {
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
  font-size: 1em;
  font-weight: 600;
}

/* ─── Resolved card ─────────────────────────────────── */
.resolved-card {
  background: linear-gradient(
    135deg,
    rgba(154, 78, 255, 0.05),
    rgba(245, 200, 66, 0.05)
  );
  border: 1px solid var(--gold);
  border-radius: var(--radius);
  padding: 1.2em 1.3em;
  margin-bottom: 1em;
  display: flex;
  gap: 1em;
  align-items: center;
}
.resolved-icon {
  font-size: 2em;
  line-height: 1;
}
.resolved-title {
  font-size: 1.15em;
  font-weight: 700;
  margin-bottom: 0.3em;
}
.resolved-sub {
  font-size: 0.78em;
  color: var(--text-3);
}
.resolved-mine {
  margin-top: 0.5em;
  font-size: 0.95em;
  color: var(--gold);
}

/* ─── Actions card ──────────────────────────────────── */
.actions-card {
  background: var(--bg-1);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius);
  padding: 1.2em 1.3em;
  margin-bottom: 1em;
}
.actions-card.join-card {
  border-color: var(--violet);
  box-shadow: 0 0 0 3px rgba(154, 78, 255, 0.08);
}
.actions-card.resolve-card {
  border-color: var(--gold);
  box-shadow: 0 0 0 3px rgba(245, 200, 66, 0.08);
}
.actions-card.vote-card {
  border-color: var(--violet);
}

/* ─── Vote toggle (collapsed state) ─────────────────── */
.vote-section {
  margin-bottom: 1em;
}
.btn-toggle-vote {
  width: 100%;
  background: var(--bg-1);
  border: 1px dashed var(--border-strong);
  border-radius: var(--radius);
  padding: 0.9em 1.1em;
  display: flex;
  align-items: center;
  gap: 0.7em;
  cursor: pointer;
  color: var(--text-1);
  font-size: 0.95em;
  text-align: left;
  transition: all 0.15s;
}
.btn-toggle-vote:hover {
  border-color: var(--violet);
  border-style: solid;
  color: var(--text-0);
  background: rgba(154, 78, 255, 0.04);
}
.toggle-icon {
  font-size: 1.3em;
}
.toggle-text {
  flex: 1;
}
.toggle-text b {
  color: var(--violet);
}
.toggle-chevron {
  font-size: 1.5em;
  color: var(--text-3);
  line-height: 1;
}
.btn-toggle-vote:hover .toggle-chevron {
  color: var(--violet);
  transform: translateX(2px);
}

.vote-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5em;
  margin-bottom: 0.6em;
}
.vote-header .card-title {
  margin: 0;
}
.btn-close {
  background: none;
  border: none;
  color: var(--text-3);
  cursor: pointer;
  font-size: 1em;
  padding: 0.3em 0.5em;
  border-radius: var(--radius-sm);
  line-height: 1;
}
.btn-close:hover {
  color: var(--text-0);
  background: var(--bg-2);
}
.actions-card.cancel-card {
  border-color: var(--border);
}
.action-prompt {
  margin: 0 0 1em;
  color: var(--text-1);
  font-size: 0.95em;
}
.action-warning {
  color: var(--red);
  font-size: 0.9em;
  margin-bottom: 0.7em;
}

.join-buttons,
.resolve-buttons {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 0.6em;
}
.btn-join,
.btn-resolve {
  background: var(--bg-2);
  border: 2px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 1em 0.7em;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.3em;
  transition: all 0.15s;
  min-height: 70px;
  text-align: center;
}
.btn-join:hover:not(:disabled),
.btn-resolve:hover:not(:disabled) {
  border-color: var(--violet);
  transform: translateY(-2px);
}
.btn-join:disabled,
.btn-resolve:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.join-label,
.btn-resolve .big {
  font-weight: 700;
  font-size: 1em;
  color: var(--text-0);
}
.join-sub,
.btn-resolve .dim {
  font-size: 0.78em;
  color: var(--text-2);
}
.btn-resolve.void {
  border-style: dashed;
}
.btn-resolve.selected {
  border-color: var(--gold);
  background: rgba(245, 200, 66, 0.06);
}

.btn-ghost.danger {
  color: var(--red);
  border-color: var(--red);
}
.btn-ghost.danger:hover {
  background: rgba(255, 69, 102, 0.08);
}

/* ─── Participants ──────────────────────────────────── */
.participants-list {
  display: flex;
  flex-direction: column;
  gap: 0.45em;
}
.participant {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5em;
  padding: 0.45em 0;
  border-bottom: 1px dashed var(--border);
  font-size: 0.9em;
  flex-wrap: wrap;
}
.participant:last-child {
  border-bottom: none;
}
.part-name {
  font-weight: 600;
}
.part-option {
  font-size: 0.85em;
  flex: 1;
}
.part-amount {
  font-weight: 600;
  color: var(--gold);
}

/* ─── Meta ──────────────────────────────────────────── */
.meta-card {
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1em 1.2em;
}
.meta-row {
  display: flex;
  justify-content: space-between;
  padding: 0.4em 0;
  border-bottom: 1px dashed var(--border);
  font-size: 0.85em;
  color: var(--text-1);
  gap: 1em;
}
.meta-row:last-child {
  border-bottom: none;
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
  .pot-card {
    grid-template-columns: 1fr 1fr;
  }
  .pot-block.big {
    grid-column: span 2;
    border-left: none;
    border-top: 1px solid var(--border);
    padding-top: 0.6em;
    padding-left: 0.5em;
  }
  .bet-statement {
    font-size: 1.25em;
  }
  .join-buttons,
  .resolve-buttons {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 400px) {
  .join-buttons,
  .resolve-buttons {
    grid-template-columns: 1fr;
  }
}
</style>
