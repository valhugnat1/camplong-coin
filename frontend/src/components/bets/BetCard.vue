<template>
  <article class="bet-card" @click="onClick">
    <header class="bet-card-head">
      <span v-if="bet.category" class="bet-cat">{{ bet.category }}</span>
      <BetStatusBadge :status="bet.status" />
    </header>

    <h3 class="bet-statement">{{ bet.statement }}</h3>

    <div class="bet-sides">
      <div
        class="side"
        :class="bet.creator_side === 'yes' ? 'side-yes' : 'side-no'"
      >
        <div class="side-label">
          {{ bet.creator_username }}
          <span class="side-pos">{{
            bet.creator_side === "yes" ? "VRAI" : "FAUX"
          }}</span>
        </div>
        <div class="side-stake mono">
          {{ formatNum(bet.stake_creator) }} CAMP
        </div>
      </div>

      <div class="vs">VS</div>

      <div
        class="side"
        :class="bet.creator_side === 'yes' ? 'side-no' : 'side-yes'"
      >
        <div class="side-label">
          <template v-if="bet.opponent_username">
            {{ bet.opponent_username }}
            <span class="side-pos">{{
              bet.creator_side === "yes" ? "FAUX" : "VRAI"
            }}</span>
          </template>
          <template v-else>
            <span class="side-empty">À prendre</span>
          </template>
        </div>
        <div class="side-stake mono">
          {{ formatNum(bet.stake_opponent) }} CAMP
        </div>
      </div>
    </div>

    <footer class="bet-meta mono">
      <span>💰 {{ formatNum(pot) }} CAMP</span>
      <span>{{ formatDeadline(bet.deadline) }}</span>
    </footer>

    <div v-if="bet.arbiter_username" class="bet-arbiter">
      ⚖️ arbitre : {{ bet.arbiter_username }}
      <span v-if="bet.arbiter_fee_pct > 0" class="dim"
        >({{ bet.arbiter_fee_pct }}%)</span
      >
    </div>
  </article>
</template>

<script setup>
import { computed } from "vue";
import { useRouter } from "vue-router";
import { formatNum } from "@/config";
import BetStatusBadge from "./BetStatusBadge.vue";

const props = defineProps({
  bet: { type: Object, required: true },
  clickable: { type: Boolean, default: true },
});

const emit = defineEmits(["click"]);
const router = useRouter();

const pot = computed(
  () => (props.bet.stake_creator || 0) + (props.bet.stake_opponent || 0),
);

function onClick() {
  if (!props.clickable) return;
  emit("click", props.bet);
  router.push({ name: "paris-detail", params: { id: props.bet.id } });
}

function formatDeadline(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const now = new Date();
  const diffMs = d - now;
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));

  if (diffMs < 0) return "Expiré";
  if (diffHours < 1) {
    const m = Math.max(1, Math.floor(diffMs / (1000 * 60)));
    return `Dans ${m} min`;
  }
  if (diffHours < 24) return `Dans ${diffHours}h`;
  if (diffDays < 7) return `Dans ${diffDays}j`;
  return d.toLocaleDateString("fr-FR", { day: "2-digit", month: "short" });
}
</script>

<style scoped>
.bet-card {
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.2em 1.3em;
  cursor: pointer;
  transition:
    transform 0.15s,
    border-color 0.15s;
  display: flex;
  flex-direction: column;
  gap: 0.9em;
}
.bet-card:hover {
  transform: translateY(-2px);
  border-color: var(--border-strong);
}

.bet-card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5em;
}

.bet-cat {
  font-size: 0.68em;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--violet);
  font-weight: 700;
}

.bet-statement {
  font-size: 1.05em;
  line-height: 1.35;
  letter-spacing: -0.01em;
  min-height: 2.7em;
  margin: 0;
}

.bet-sides {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 0.5em;
  align-items: center;
}

.side {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0.6em 0.7em;
  display: flex;
  flex-direction: column;
  gap: 0.25em;
}
.side-yes {
  border-left: 3px solid var(--green);
}
.side-no {
  border-left: 3px solid var(--red);
}

.side-label {
  font-size: 0.78em;
  color: var(--text-1);
  display: flex;
  flex-direction: column;
  gap: 0.15em;
}
.side-pos {
  font-size: 0.7em;
  font-weight: 700;
  letter-spacing: 0.05em;
}
.side-yes .side-pos {
  color: var(--green);
}
.side-no .side-pos {
  color: var(--red);
}

.side-empty {
  font-style: italic;
  color: var(--text-3);
}

.side-stake {
  font-size: 0.9em;
  font-weight: 700;
  color: var(--text-0);
}

.vs {
  font-size: 0.7em;
  font-weight: 700;
  color: var(--text-3);
  letter-spacing: 0.1em;
}

.bet-meta {
  display: flex;
  justify-content: space-between;
  font-size: 0.78em;
  color: var(--text-2);
}

.bet-arbiter {
  font-size: 0.75em;
  color: var(--text-2);
  padding-top: 0.4em;
  border-top: 1px dashed var(--border);
}
.dim {
  color: var(--text-3);
}
</style>
