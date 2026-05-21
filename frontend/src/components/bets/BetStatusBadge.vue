<template>
  <span class="status-badge" :class="`status-${status}`">
    {{ label }}
  </span>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  status: {
    type: String,
    required: true,
    validator: (v) =>
      ["open", "matched", "resolved", "cancelled", "expired"].includes(v),
  },
});

const LABELS = {
  open: "Ouvert",
  matched: "En cours",
  resolved: "Résolu",
  cancelled: "Annulé",
  expired: "Expiré",
};

const label = computed(() => LABELS[props.status] || props.status);
</script>

<style scoped>
.status-badge {
  display: inline-block;
  padding: 0.2em 0.7em;
  font-size: 0.72em;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--bg-2);
}

.status-open {
  color: var(--green);
  border-color: rgba(20, 224, 142, 0.3);
}
.status-matched {
  color: var(--gold);
  border-color: rgba(245, 200, 66, 0.3);
}
.status-resolved {
  color: var(--text-2);
}
.status-cancelled {
  color: var(--text-3);
}
.status-expired {
  color: var(--red);
  border-color: rgba(255, 69, 102, 0.3);
}
</style>
