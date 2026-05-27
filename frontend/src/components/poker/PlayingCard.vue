<template>
  <div
    class="card"
    :class="{
      hidden: hidden || !card,
      red: !hidden && (suit === 'h' || suit === 'd'),
      highlight: highlight,
      small: size === 'sm',
      large: size === 'lg',
    }"
  >
    <template v-if="!hidden && card">
      <div class="rank top">{{ displayRank }}</div>
      <div class="suit">{{ suitSymbol }}</div>
      <div class="rank bottom">{{ displayRank }}</div>
    </template>
    <template v-else>
      <div class="back">🂠</div>
    </template>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  card: { type: String, default: "" },
  hidden: { type: Boolean, default: false },
  highlight: { type: Boolean, default: false },
  size: { type: String, default: "md" },
});

const rank = computed(() => (props.card ? props.card[0] : ""));
const suit = computed(() => (props.card ? props.card[1] : ""));
const displayRank = computed(() => (rank.value === "T" ? "10" : rank.value));
const suitSymbol = computed(() => {
  return {
    h: "♥",
    d: "♦",
    c: "♣",
    s: "♠",
  }[suit.value] || "";
});
</script>

<style scoped>
.card {
  width: 44px;
  height: 64px;
  background: #fafafa;
  border-radius: 6px;
  border: 1px solid #d0d0d0;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 4px 5px;
  color: #1a1a1a;
  font-weight: 700;
  box-shadow:
    0 2px 8px rgba(0, 0, 0, 0.35),
    inset 0 1px 0 rgba(255, 255, 255, 0.6);
  font-family:
    -apple-system, "Segoe UI", system-ui, sans-serif;
  user-select: none;
  position: relative;
  transition: transform 0.18s, box-shadow 0.18s;
}
.card.small {
  width: 30px;
  height: 44px;
  padding: 2px 3px;
}
.card.large {
  width: 56px;
  height: 80px;
  padding: 5px 6px;
}
.card.red {
  color: #d92043;
}
.card.hidden {
  background: linear-gradient(135deg, #1a3a5c 0%, #0f2240 100%);
  color: #6a8fc0;
  border-color: #0a1830;
  align-items: center;
  justify-content: center;
}
.card.hidden .back {
  font-size: 1.8em;
  opacity: 0.7;
}
.card.highlight {
  box-shadow:
    0 0 0 2px var(--gold, #f5c842),
    0 4px 14px rgba(245, 200, 66, 0.4);
  transform: translateY(-2px);
}
.rank {
  font-size: 0.85em;
  line-height: 1;
}
.rank.top {
  text-align: left;
}
.rank.bottom {
  text-align: right;
  transform: rotate(180deg);
}
.suit {
  text-align: center;
  font-size: 1.4em;
  line-height: 1;
}
.card.small .suit {
  font-size: 1em;
}
.card.large .suit {
  font-size: 1.7em;
}
</style>
