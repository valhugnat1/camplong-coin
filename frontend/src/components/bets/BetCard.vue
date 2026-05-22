<template>
  <article class="bet-card" @click="onClick">
    <header class="bet-card-head">
      <BetStatusBadge :status="bet.status" />
      <span class="bet-type-tag mono">
        {{ bet.type === "yes_no" ? "Oui / Non" : `${bet.options.length} choix` }}
      </span>
    </header>

    <h3 class="bet-statement">{{ bet.statement }}</h3>

    <!-- Options avec barres de participation -->
    <div class="opts">
      <div
        v-for="o in bet.options"
        :key="o.id"
        class="opt-row"
        :class="{ mine: o.id === bet.my_option_id }"
      >
        <div class="opt-bar-wrap">
          <div
            class="opt-bar"
            :style="{ width: barWidth(o) + '%' }"
          />
        </div>
        <div class="opt-meta">
          <span class="opt-label">
            {{ o.label }}
            <span v-if="o.id === bet.my_option_id" class="opt-mine-tag">★</span>
          </span>
          <span class="opt-count mono">{{ o.participants_count }}</span>
        </div>
      </div>
    </div>

    <footer class="bet-meta mono">
      <span>💰 {{ formatNum(bet.stake) }} CAMP/mise</span>
      <span class="pot">Pot {{ formatNum(bet.pot_total) }}</span>
      <span>{{ formatDeadline(bet.deadline) }}</span>
    </footer>

    <div v-if="bet.arbiter_username" class="bet-arbiter">
      ⚖️ arbitre : {{ bet.arbiter_username }}
    </div>
    <div v-else class="bet-arbiter">
      🗳️ vote communautaire (2 voix concordantes)
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

const maxCount = computed(() =>
  Math.max(1, ...(props.bet.options || []).map((o) => o.participants_count)),
);

function barWidth(opt) {
  if (!maxCount.value) return 0;
  return Math.round((opt.participants_count / maxCount.value) * 100);
}

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
  padding: 1.1em 1.2em;
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
.bet-card:active {
  transform: translateY(0);
}

.bet-card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5em;
}

.bet-type-tag {
  font-size: 0.68em;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--text-3);
  font-weight: 700;
}

.bet-statement {
  font-size: 1.05em;
  line-height: 1.35;
  letter-spacing: -0.01em;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.opts {
  display: flex;
  flex-direction: column;
  gap: 0.4em;
}
.opt-row {
  position: relative;
  padding: 0.5em 0.7em;
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
}
.opt-row.mine {
  border-color: var(--violet);
  box-shadow: 0 0 0 1px var(--violet);
}
.opt-bar-wrap {
  position: absolute;
  inset: 0;
  background: transparent;
}
.opt-bar {
  height: 100%;
  background: linear-gradient(
    90deg,
    rgba(154, 78, 255, 0.18),
    rgba(154, 78, 255, 0.06)
  );
  transition: width 0.3s ease;
}
.opt-row.mine .opt-bar {
  background: linear-gradient(
    90deg,
    rgba(154, 78, 255, 0.35),
    rgba(154, 78, 255, 0.1)
  );
}
.opt-meta {
  position: relative;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5em;
  font-size: 0.88em;
}
.opt-label {
  font-weight: 600;
  color: var(--text-0);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.opt-mine-tag {
  color: var(--gold);
  margin-left: 0.3em;
}
.opt-count {
  font-weight: 700;
  color: var(--text-1);
  flex-shrink: 0;
}

.bet-meta {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 0.5em;
  font-size: 0.78em;
  color: var(--text-2);
}
.bet-meta .pot {
  color: var(--gold);
  font-weight: 700;
}

.bet-arbiter {
  font-size: 0.75em;
  color: var(--text-2);
  padding-top: 0.4em;
  border-top: 1px dashed var(--border);
}

@media (max-width: 480px) {
  .bet-card {
    padding: 1em;
  }
  .bet-statement {
    font-size: 1em;
  }
}
</style>
