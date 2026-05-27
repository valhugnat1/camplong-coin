<template>
  <div class="admin-shell">
    <AdminTopBar />
    <main class="page admin-page fade-in">
      <header class="page-head">
        <div>
          <h2>🃏 Poker — tables</h2>
          <p class="dim">
            Crée, ouvre ou ferme les tables. Les stacks sont off-chain :
            chaque buy-in lock du CAMP sur le wallet <code>poker_bank</code>,
            chaque cashout le release.
          </p>
        </div>
      </header>

      <div v-if="error" class="alert err">{{ error }}</div>

      <!-- ─── Creation d'une table ─── -->
      <section class="card">
        <h3>Créer une table</h3>
        <div class="form-grid">
          <label>
            <span class="lbl">Nom</span>
            <input v-model="form.name" class="input" placeholder="ex: Table du salon" />
          </label>
          <label>
            <span class="lbl">Small blind</span>
            <input v-model.number="form.blind_small" type="number" class="input" min="1" />
          </label>
          <label>
            <span class="lbl">Big blind</span>
            <input v-model.number="form.blind_big" type="number" class="input" min="1" />
          </label>
          <label>
            <span class="lbl">Min buy-in</span>
            <input v-model.number="form.min_buyin" type="number" class="input" min="1" />
          </label>
          <label>
            <span class="lbl">Max buy-in</span>
            <input v-model.number="form.max_buyin" type="number" class="input" min="1" />
          </label>
          <label>
            <span class="lbl">Sièges max</span>
            <input v-model.number="form.max_players" type="number" class="input" min="2" max="10" />
          </label>
        </div>
        <button
          class="btn primary"
          :disabled="!canCreate || creating"
          @click="onCreate"
        >
          {{ creating ? "Création…" : "Créer la table" }}
        </button>
      </section>

      <!-- ─── Liste tables ─── -->
      <section class="tables">
        <h3 class="section-title">Tables existantes</h3>
        <div v-if="loading && !tables.length" class="card dim">Chargement…</div>
        <div v-else-if="!tables.length" class="card dim">
          Aucune table pour le moment.
        </div>
        <article v-for="t in tables" :key="t.id" class="card table-row">
          <header class="t-head">
            <div>
              <h4>{{ t.name }} <span class="dim">#{{ t.id }}</span></h4>
              <div class="mono dim small">
                blinds {{ t.blind_small }} / {{ t.blind_big }} ·
                buy-in {{ t.min_buyin }}–{{ t.max_buyin }} ·
                {{ t.n_players }} / {{ t.max_players }} sièges
              </div>
              <div class="dim small">
                créateur :
                <b v-if="t.creator_username">{{ t.creator_username }}</b>
                <span v-else>admin</span>
              </div>
            </div>
            <span class="status" :class="t.status">{{ t.status }}</span>
          </header>

          <div v-if="t.players?.length" class="players-list">
            <span
              v-for="p in t.players"
              :key="p.username"
              class="player-chip"
            >
              <b>{{ p.username }}</b>
              <span class="mono dim">· stack {{ p.stack }}</span>
              <span class="dim">· siège {{ p.seat + 1 }}</span>
            </span>
          </div>

          <div class="stats">
            <div>
              <span class="lbl">Mains jouées</span>
              <span class="val mono">{{ t.n_hands_played }}</span>
            </div>
            <div v-if="t.hand_in_progress">
              <span class="lbl">Main en cours</span>
              <span class="val mono">#{{ t.hand_in_progress }}</span>
            </div>
          </div>

          <div class="actions">
            <button
              class="btn"
              :disabled="busy === t.id"
              @click="onToggle(t)"
            >
              {{ t.status === "open" ? "Fermer" : "Rouvrir" }}
            </button>
            <button
              v-if="t.hand_in_progress"
              class="btn ghost danger"
              :disabled="busy === t.id"
              @click="onForceEnd(t)"
            >
              Annuler la main en cours
            </button>
            <button
              class="btn ghost danger"
              :disabled="busy === t.id || t.n_players > 0"
              @click="onDelete(t)"
              :title="t.n_players > 0 ? 'Vide la table d\'abord' : ''"
            >
              Supprimer
            </button>
          </div>
        </article>
      </section>
    </main>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, computed } from "vue";
import AdminTopBar from "@/components/admin/AdminTopBar.vue";
import { adminPokerApi } from "@/api/poker";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const tables = ref([]);
const loading = ref(false);
const error = ref(null);
const busy = ref(null);
const creating = ref(false);

const form = ref({
  name: "",
  blind_small: 1,
  blind_big: 2,
  min_buyin: 40,
  max_buyin: 200,
  max_players: 6,
});

const canCreate = computed(() => {
  const f = form.value;
  return (
    f.name?.length > 0 &&
    f.blind_small > 0 &&
    f.blind_big >= f.blind_small &&
    f.min_buyin >= f.blind_big &&
    f.max_buyin >= f.min_buyin &&
    f.max_players >= 2 &&
    f.max_players <= 10
  );
});

async function load() {
  loading.value = true;
  error.value = null;
  try {
    tables.value = await adminPokerApi.listTables(auth.adminToken);
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}

async function onCreate() {
  if (!canCreate.value) return;
  creating.value = true;
  error.value = null;
  try {
    await adminPokerApi.createTable(auth.adminToken, form.value);
    form.value.name = "";
    await load();
  } catch (e) {
    error.value = e.message;
  } finally {
    creating.value = false;
  }
}

async function onToggle(t) {
  busy.value = t.id;
  error.value = null;
  try {
    await adminPokerApi.updateTable(auth.adminToken, t.id, {
      status: t.status === "open" ? "closed" : "open",
    });
    await load();
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = null;
  }
}

async function onForceEnd(t) {
  if (!confirm(`Annuler la main en cours sur "${t.name}" ? Les mises sont rendues aux joueurs.`))
    return;
  busy.value = t.id;
  error.value = null;
  try {
    await adminPokerApi.forceEndHand(auth.adminToken, t.id);
    await load();
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = null;
  }
}

async function onDelete(t) {
  if (!confirm(`Supprimer définitivement la table "${t.name}" ?`))
    return;
  busy.value = t.id;
  error.value = null;
  try {
    await adminPokerApi.deleteTable(auth.adminToken, t.id);
    await load();
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = null;
  }
}

let refreshTimer = null;
onMounted(() => {
  load();
  refreshTimer = setInterval(load, 6000);
});
onBeforeUnmount(() => {
  if (refreshTimer) clearInterval(refreshTimer);
});
</script>

<style scoped>
.page-head {
  margin-bottom: 1em;
}
.page-head h2 {
  margin: 0 0 0.2em 0;
}
.page-head p {
  margin: 0;
  max-width: 70ch;
}
.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 0.6em;
  margin-bottom: 0.8em;
}
.form-grid label {
  display: flex;
  flex-direction: column;
  gap: 0.2em;
}
.lbl {
  color: var(--text-3);
  font-size: 0.78em;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.input {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0.5em 0.7em;
  color: var(--text-0);
  font-size: 0.95em;
}
.section-title {
  margin: 1.5em 0 0.7em 0;
}
.tables {
  display: flex;
  flex-direction: column;
  gap: 0.7em;
}
.table-row {
  display: flex;
  flex-direction: column;
  gap: 0.7em;
}
.t-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}
.t-head h4 {
  margin: 0;
  font-size: 1.05em;
}
.status {
  font-size: 0.7em;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 0.2em 0.55em;
  border-radius: 999px;
}
.status.open {
  background: var(--green-soft);
  color: var(--green);
}
.status.closed {
  background: var(--bg-3);
  color: var(--text-2);
}
.players-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4em;
}
.player-chip {
  font-size: 0.82em;
  background: var(--bg-2);
  border: 1px solid var(--border);
  padding: 0.25em 0.6em;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  gap: 0.35em;
}
.stats {
  display: flex;
  gap: 1em;
  font-size: 0.85em;
}
.stats .val {
  color: var(--text-0);
  font-weight: 700;
  margin-left: 0.3em;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4em;
}
.btn.danger {
  color: var(--red);
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
.admin-shell {
  min-height: 100vh;
  background: var(--bg-0);
}
.admin-page {
  max-width: var(--max);
  margin: 0 auto;
  padding: 1.6em 1.25em;
}
</style>
