<template>
  <AppLayout>
    <main class="page fade-in">
      <div class="page-header">
        <div>
          <h1 class="page-title">
            Paris <span class="dot">·</span> Pronostics
          </h1>
          <p class="page-sub">
            Mise sur tes potes. Si t'es plus malin que les autres, tu vas en
            vivre.
          </p>
        </div>
        <button
          class="btn-primary"
          @click="router.push({ name: 'paris-create' })"
        >
          + Créer un pari
        </button>
      </div>

      <!-- Tabs -->
      <div class="tabs">
        <button
          class="tab"
          :class="{ active: tab === 'open' }"
          @click="setTab('open')"
        >
          Disponibles
          <span v-if="openBets.length" class="tab-count">{{
            openBets.length
          }}</span>
        </button>
        <button
          class="tab"
          :class="{ active: tab === 'mine' }"
          @click="setTab('mine')"
        >
          Mes paris
          <span v-if="myBets.length" class="tab-count">{{
            myBets.length
          }}</span>
        </button>
      </div>

      <!-- Filtres -->
      <div v-if="tab === 'open' && categories.length" class="filters">
        <button
          class="chip"
          :class="{ active: !filter.category }"
          @click="filter.category = ''"
        >
          Tous
        </button>
        <button
          v-for="c in categories"
          :key="c"
          class="chip"
          :class="{ active: filter.category === c }"
          @click="filter.category = c"
        >
          {{ c }}
        </button>
      </div>

      <div v-if="tab === 'mine'" class="filters">
        <button
          v-for="s in MINE_STATUSES"
          :key="s.value"
          class="chip"
          :class="{ active: mineStatusFilter === s.value }"
          @click="mineStatusFilter = s.value"
        >
          {{ s.label }}
        </button>
      </div>

      <!-- Erreur -->
      <div v-if="error" class="alert error" style="margin-top: 1em">
        {{ error }}
      </div>

      <!-- Loading -->
      <div v-if="loading && !displayed.length" class="empty">
        <span class="dim">Chargement...</span>
      </div>

      <!-- Liste vide -->
      <div v-else-if="!displayed.length" class="empty">
        <div v-if="tab === 'open'">
          <p>Pas encore de pari ouvert.</p>
          <button
            class="btn-primary"
            @click="router.push({ name: 'paris-create' })"
          >
            Crée le premier
          </button>
        </div>
        <div v-else>
          <p>
            Tu n'as encore aucun pari{{
              mineStatusFilter !== "all" ? " dans ce statut" : ""
            }}.
          </p>
        </div>
      </div>

      <!-- Grille de cartes -->
      <div v-else class="bets-grid">
        <BetCard v-for="b in displayed" :key="b.id" :bet="b" />
      </div>
    </main>
  </AppLayout>
</template>

<script setup>
import { ref, computed, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { storeToRefs } from "pinia";
import AppLayout from "@/components/layout/AppLayout.vue";
import BetCard from "@/components/bets/BetCard.vue";
import { useBetsStore } from "@/stores/bets";

const router = useRouter();
const betsStore = useBetsStore();
const { openBets, myBets, loading, error } = storeToRefs(betsStore);

const tab = ref("open");
const filter = ref({ category: "" });
const mineStatusFilter = ref("all");

const MINE_STATUSES = [
  { value: "all", label: "Tous" },
  { value: "open", label: "Ouverts" },
  { value: "matched", label: "En cours" },
  { value: "resolved", label: "Résolus" },
  { value: "cancelled", label: "Annulés" },
];

// Catégories vues parmi les paris ouverts (dédoublonnées)
const categories = computed(() => {
  const set = new Set();
  for (const b of openBets.value) if (b.category) set.add(b.category);
  return [...set].sort();
});

const displayed = computed(() => {
  if (tab.value === "open") {
    if (!filter.value.category) return openBets.value;
    return openBets.value.filter((b) => b.category === filter.value.category);
  }
  // mine
  if (mineStatusFilter.value === "all") return myBets.value;
  return myBets.value.filter((b) => b.status === mineStatusFilter.value);
});

function setTab(t) {
  tab.value = t;
  refresh();
}

async function refresh() {
  if (tab.value === "open") await betsStore.fetchOpen();
  else await betsStore.fetchMine();
}

onMounted(refresh);
</script>

<style scoped>
.dot {
  color: var(--violet);
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1em;
  margin-bottom: 1.5em;
}
.page-header .btn-primary {
  white-space: nowrap;
  flex-shrink: 0;
}

.tabs {
  display: flex;
  gap: 0.3em;
  border-bottom: 1px solid var(--border);
  margin-bottom: 1em;
}
.tab {
  background: transparent;
  border: none;
  padding: 0.7em 1.2em;
  color: var(--text-2);
  font-weight: 600;
  font-size: 0.95em;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  display: flex;
  align-items: center;
  gap: 0.5em;
  transition:
    color 0.15s,
    border-color 0.15s;
}
.tab:hover {
  color: var(--text-0);
}
.tab.active {
  color: var(--text-0);
  border-bottom-color: var(--violet);
}
.tab-count {
  background: var(--bg-2);
  padding: 0.1em 0.55em;
  border-radius: 999px;
  font-size: 0.75em;
  color: var(--text-1);
}
.tab.active .tab-count {
  background: var(--violet);
  color: white;
}

.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4em;
  margin-bottom: 1em;
}
.chip {
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 0.35em 0.95em;
  font-size: 0.82em;
  color: var(--text-1);
  cursor: pointer;
  transition: all 0.15s;
}
.chip:hover {
  border-color: var(--border-strong);
  color: var(--text-0);
}
.chip.active {
  background: var(--violet);
  border-color: var(--violet);
  color: white;
}

.bets-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 1em;
}

.empty {
  text-align: center;
  padding: 3em 1em;
  color: var(--text-2);
}
.empty p {
  margin-bottom: 1em;
}
.dim {
  color: var(--text-3);
}

.alert.error {
  background: rgba(255, 69, 102, 0.1);
  border: 1px solid var(--red);
  border-radius: var(--radius-sm);
  padding: 0.8em 1em;
  color: var(--red);
}

@media (max-width: 640px) {
  .page-header {
    flex-direction: column;
  }
  .page-header .btn-primary {
    width: 100%;
  }
}
</style>
