<template>
  <AppLayout>
    <main class="page fade-in">
      <div class="poker-hero">
        <div>
          <h2>Poker <span class="gold">Texas Hold'em</span></h2>
          <p>
            No-Limit, blinds fixes, 2 à 6 joueurs par table. Achète-toi
            une place, joue tes mains, ramasse les jetons des potes.
          </p>
        </div>
        <router-link to="/casino" class="back">← Casino</router-link>
      </div>

      <!-- ─── Crée ta table ─── -->
      <section class="create-card card" :class="{ expanded: showCreate }">
        <header class="create-head">
          <div>
            <h3>Créer une table</h3>
            <p class="dim small">
              Tu deviens le créateur — tu pourras la supprimer quand elle
              sera vide. L'admin peut aussi l'administrer.
            </p>
          </div>
          <button class="btn ghost" @click="showCreate = !showCreate">
            {{ showCreate ? "Fermer" : "+ Nouvelle table" }}
          </button>
        </header>

        <div v-if="showCreate" class="create-form">
          <div class="form-grid">
            <label>
              <span class="lbl">Nom</span>
              <input v-model="form.name" class="input" placeholder="ex: Table du salon" maxlength="64" />
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
          <div v-if="createError" class="alert err">{{ createError }}</div>
          <button class="btn primary" :disabled="!canCreate || poker.acting" @click="onCreate">
            {{ poker.acting ? "Création…" : "Créer la table" }}
          </button>
        </div>
      </section>

      <div v-if="poker.loading && !poker.tables.length" class="card dim">
        Chargement des tables…
      </div>

      <div v-else-if="!poker.tables.length" class="card dim empty">
        Aucune table ouverte pour le moment.<br />
        <small>Crée la première en cliquant sur "Nouvelle table" ci-dessus.</small>
      </div>

      <div v-else class="tables-grid">
        <article
          v-for="t in poker.tables"
          :key="t.id"
          class="table-tile"
          :class="{ closed: t.status !== 'open' }"
        >
          <header>
            <div class="title-wrap">
              <h3>{{ t.name }}</h3>
              <div class="creator dim small" v-if="t.creator_username">
                par <b>{{ t.creator_username }}</b>
                <span v-if="t.im_creator" class="me-tag">toi</span>
              </div>
              <div class="creator dim small" v-else>
                table admin
              </div>
            </div>
            <span class="status" :class="t.status">{{
              t.status === "open" ? "ouverte" : "fermée"
            }}</span>
          </header>
          <div class="meta">
            <div>
              <span class="lbl">Blinds</span>
              <span class="val mono">{{ t.blind_small }} / {{ t.blind_big }}</span>
            </div>
            <div>
              <span class="lbl">Buy-in</span>
              <span class="val mono">{{ t.min_buyin }} — {{ t.max_buyin }}</span>
            </div>
            <div>
              <span class="lbl">Sièges</span>
              <span class="val mono">{{ t.n_players }} / {{ t.max_players }}</span>
            </div>
          </div>

          <div class="players" v-if="t.players?.length">
            <span v-for="p in t.players" :key="p.username" class="player-pill">
              {{ p.username }} · {{ p.stack }}
            </span>
          </div>

          <div class="actions">
            <button
              v-if="t.im_creator"
              class="btn ghost danger"
              :disabled="poker.acting || t.n_players > 0"
              :title="t.n_players > 0 ? 'Vide la table avant de la supprimer' : ''"
              @click.stop="onDelete(t)"
            >
              Supprimer
            </button>
            <router-link
              v-if="t.im_in || t.status === 'open'"
              :to="`/casino/poker/${t.id}`"
              class="btn primary"
            >
              {{ t.im_in ? "Reprendre" : "Rejoindre" }}
            </router-link>
            <span v-else class="dim small">Table fermée</span>
          </div>
        </article>
      </div>
    </main>
  </AppLayout>
</template>

<script setup>
import { onMounted, onBeforeUnmount, ref, computed } from "vue";
import AppLayout from "@/components/layout/AppLayout.vue";
import { usePokerStore } from "@/stores/poker";

const poker = usePokerStore();

const showCreate = ref(false);
const createError = ref(null);
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
    f.name?.trim().length > 0 &&
    f.blind_small > 0 &&
    f.blind_big >= f.blind_small &&
    f.min_buyin >= f.blind_big &&
    f.max_buyin >= f.min_buyin &&
    f.max_players >= 2 &&
    f.max_players <= 10
  );
});

async function onCreate() {
  if (!canCreate.value) return;
  createError.value = null;
  try {
    await poker.createTable({ ...form.value, name: form.value.name.trim() });
    form.value.name = "";
    showCreate.value = false;
  } catch (e) {
    createError.value = e.message;
  }
}

async function onDelete(t) {
  if (!confirm(`Supprimer la table "${t.name}" ?`)) return;
  try {
    await poker.deleteTable(t.id);
  } catch (e) {
    alert(e.message);
  }
}

let refreshTimer = null;

onMounted(() => {
  poker.loadTables();
  // Refresh doux toutes les 5s pour voir les sit-in / sit-out arriver
  refreshTimer = setInterval(() => poker.loadTables(), 5000);
});

onBeforeUnmount(() => {
  if (refreshTimer) clearInterval(refreshTimer);
});
</script>

<style scoped>
.poker-hero {
  background:
    radial-gradient(
      circle at 75% 50%,
      rgba(46, 134, 70, 0.18),
      transparent 65%
    ),
    linear-gradient(135deg, #0d1a13 0%, #0a0e0f 100%);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius);
  padding: 1.8em 1.6em;
  margin-bottom: 1.4em;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1em;
}
.poker-hero h2 {
  font-size: 1.8em;
  margin: 0 0 0.2em 0;
}
.poker-hero .gold {
  background: linear-gradient(90deg, var(--gold), #f5c842);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
.poker-hero p {
  color: var(--text-2);
  margin: 0;
  max-width: 50ch;
}
.back {
  color: var(--text-2);
  text-decoration: none;
  font-size: 0.9em;
  white-space: nowrap;
}
.back:hover {
  color: var(--camp);
}
.create-card {
  margin-bottom: 1em;
  transition: background 0.18s;
}
.create-card.expanded {
  background: linear-gradient(135deg, rgba(245, 200, 66, 0.05), transparent);
  border-color: rgba(245, 200, 66, 0.35);
}
.create-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.8em;
}
.create-head h3 {
  margin: 0 0 0.15em 0;
  font-size: 1.05em;
}
.create-head p {
  margin: 0;
  max-width: 50ch;
}
.create-form {
  margin-top: 0.9em;
  display: flex;
  flex-direction: column;
  gap: 0.7em;
}
.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 0.6em;
}
.form-grid label {
  display: flex;
  flex-direction: column;
  gap: 0.2em;
}
.form-grid .lbl {
  color: var(--text-3);
  font-size: 0.74em;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.input {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0.55em 0.7em;
  color: var(--text-0);
  font-size: 0.95em;
  min-height: 40px;
}
.alert.err {
  background: var(--red-soft);
  color: var(--red);
  border: 1px solid var(--red);
  padding: 0.55em 0.8em;
  border-radius: var(--radius-sm);
  font-size: 0.9em;
}

.tables-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1em;
}
.title-wrap {
  display: flex;
  flex-direction: column;
  gap: 0.1em;
  min-width: 0;
}
.creator {
  display: inline-flex;
  align-items: center;
  gap: 0.35em;
}
.me-tag {
  font-size: 0.65em;
  background: var(--camp);
  color: white;
  padding: 0.1em 0.4em;
  border-radius: 4px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.btn.danger {
  color: var(--red);
}
.actions {
  gap: 0.4em;
}
.table-tile {
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.2em 1.1em;
  display: flex;
  flex-direction: column;
  gap: 0.7em;
  transition: border-color 0.18s, transform 0.18s;
}
.table-tile:hover {
  border-color: var(--border-strong);
  transform: translateY(-2px);
}
.table-tile.closed {
  opacity: 0.7;
}
.table-tile header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.table-tile h3 {
  font-size: 1.1em;
  margin: 0;
}
.status {
  font-size: 0.7em;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 0.2em 0.5em;
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
.meta {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 0.5em;
  font-size: 0.85em;
}
.meta .lbl {
  display: block;
  color: var(--text-3);
  font-size: 0.78em;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.15em;
}
.meta .val {
  color: var(--text-0);
  font-weight: 700;
}
.players {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3em;
}
.player-pill {
  font-size: 0.78em;
  background: var(--bg-2);
  border: 1px solid var(--border);
  padding: 0.2em 0.6em;
  border-radius: 999px;
  color: var(--text-1);
}
.actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 0.3em;
}
.empty {
  text-align: center;
  padding: 2em 1em;
}
.dim {
  color: var(--text-2);
}
.small {
  font-size: 0.85em;
}

@media (max-width: 520px) {
  .poker-hero {
    flex-direction: column;
    align-items: flex-start;
    padding: 1.4em 1.1em;
  }
  .meta {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
