<template>
  <nav class="tabs">
    <router-link
      v-for="t in tabs"
      :key="t.to"
      :to="t.to"
      custom
      v-slot="{ isActive, navigate }"
    >
      <button class="tab" :class="{ active: isActive }" @click="navigate">
        <span>{{ t.icon }}</span> {{ t.label }}
        <span v-if="t.badge" class="tab-badge">{{ t.badge }}</span>
      </button>
    </router-link>
  </nav>
</template>

<script setup>
const tabs = [
  { to: "/wallet", icon: "💼", label: "Wallet" },
  { to: "/paris", icon: "🎯", label: "Paris" },
  { to: "/casino", icon: "🎰", label: "Casino" },
  { to: "/milk", icon: "🥛", label: "Bourse du Lait", badge: "soon" },
];
</script>

<style scoped>
.tabs {
  max-width: var(--max);
  margin: 0 auto;
  padding: 0 1.25em;
  display: flex;
  gap: 0.25em;
  border-bottom: 1px solid var(--border);
  overflow-x: auto;
  scrollbar-width: none;
}
.tabs::-webkit-scrollbar {
  display: none;
}

.tab {
  padding: 1em 1.1em;
  background: none;
  border: none;
  color: var(--text-2);
  font-weight: 600;
  font-size: 0.95em;
  cursor: pointer;
  position: relative;
  white-space: nowrap;
  display: flex;
  align-items: center;
  gap: 0.5em;
  border-radius: 0;
}
.tab:hover {
  color: var(--text-0);
}
.tab.active {
  color: var(--text-0);
}
.tab.active::after {
  content: "";
  position: absolute;
  bottom: -1px;
  left: 1.1em;
  right: 1.1em;
  height: 2px;
  background: var(--camp);
  border-radius: 2px;
  box-shadow: 0 0 8px var(--camp-glow);
}

.tab-badge {
  background: var(--bg-3);
  color: var(--text-2);
  font-size: 0.65em;
  font-weight: 700;
  padding: 0.15em 0.45em;
  border-radius: 4px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.tab.active .tab-badge {
  background: var(--camp-soft);
  color: var(--camp);
}

@media (max-width: 640px) {
  .tabs {
    padding: 0 0.5em;
  }
  .tab {
    padding: 0.9em 0.8em;
    font-size: 0.88em;
  }
}
</style>
