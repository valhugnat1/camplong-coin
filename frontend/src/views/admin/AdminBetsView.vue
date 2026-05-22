<template>
  <AdminTopBar :pending-count="ordersStore.pendingCount" />
  <main class="page fade-in">
    <div class="page-header">
      <h1 class="page-title">Backoffice <span class="dot">·</span> Paris</h1>
      <p class="page-sub">
        Tous les paris du système, override admin pour les cas tordus.
      </p>
    </div>

    <router-link
      v-if="ordersStore.pendingCount > 0"
      to="/admin/orders"
      class="pending-banner"
    >
      <span class="dot-anim"></span>
      <span class="t">
        <b
          >{{ ordersStore.pendingCount }} demande{{
            ordersStore.pendingCount > 1 ? "s" : ""
          }}
          en attente</b
        >
        — Hugo, t'as du taf.
      </span>
      <span class="arrow">→</span>
    </router-link>

    <!-- Toolbar -->
    <div class="toolbar">
      <button class="btn-ghost btn-sm" @click="loadAll" :disabled="loading">
        {{ loading ? "…" : "↻ Rafraîchir" }}
      </button>
      <div class="counts mono" v-if="!loading">
        {{ bets.length }} pari{{ bets.length > 1 ? "s" : "" }}
        <span class="dim">·</span>
        Pot total : {{ formatNum(totalPot) }} CAMP
      </div>
    </div>

    <!-- Filtres statut -->
    <div class="filters">
      <button
        v-for="s in STATUSES"
        :key="s.value"
        class="chip"
        :class="{ active: filterStatus === s.value }"
        @click="
          filterStatus = s.value;
          loadAll();
        "
      >
        {{ s.label }}
        <span v-if="counts[s.value]" class="count mono">{{
          counts[s.value]
        }}</span>
      </button>
    </div>

    <div v-if="error" class="alert error">{{ error }}</div>

    <div v-if="loading && !bets.length" class="empty-state">
      <div class="emoji">⌛</div>
      Chargement...
    </div>

    <div v-else-if="!bets.length" class="card empty-state">
      <div class="emoji">📭</div>
      <div>
        Aucun pari{{ filterStatus !== "all" ? " dans ce statut" : "" }}.
      </div>
    </div>

    <!-- Liste en cartes admin -->
    <div v-else class="bets-list">
      <article v-for="b in bets" :key="b.id" class="admin-bet-card">
        <header class="bet-row-top">
          <span class="status-pill" :class="b.status">{{
            statusLabel(b.status)
          }}</span>
          <span class="bet-type mono">
            {{ b.type === "yes_no" ? "Oui / Non" : `${b.options.length} choix` }}
          </span>
          <span class="bet-id mono">#{{ b.id }}</span>
        </header>

        <h3 class="bet-row-statement">{{ b.statement }}</h3>

        <!-- Options et participants -->
        <div class="bet-options">
          <div
            v-for="o in b.options"
            :key="o.id"
            class="opt-pill"
            :class="{
              winner:
                b.status === 'resolved' &&
                !b.resolution_void &&
                o.id === b.resolution_option_id,
            }"
          >
            <span class="opt-label">{{ o.label }}</span>
            <span class="opt-count mono">{{ o.participants_count }}</span>
          </div>
          <div v-if="b.resolution_void" class="opt-pill void">○ Void</div>
        </div>

        <div class="bet-info-row mono">
          <span>👤 {{ b.creator_username }}</span>
          <span v-if="b.arbiter_username">⚖️ {{ b.arbiter_username }}</span>
          <span v-else>🗳️ {{ b.votes_count }} voix</span>
          <span>💰 {{ formatNum(b.stake) }} CAMP/mise</span>
          <span class="pot-info">Pot {{ formatNum(b.pot_total) }}</span>
          <span>⏱ {{ formatShort(b.deadline) }}</span>
        </div>

        <!-- Actions admin -->
        <div v-if="b.status === 'open'" class="admin-actions">
          <div class="resolve-bar">
            <span class="action-label">Force-resolve →</span>
            <button
              v-for="o in b.options"
              :key="o.id"
              class="btn-mini resolve"
              :disabled="acting[b.id]"
              @click="forceResolve(b, o)"
              :title="`Résoudre vers ${o.label}`"
            >
              {{ o.label }}
              <span class="count-tag mono">{{ o.participants_count }}</span>
            </button>
            <button
              class="btn-mini void"
              :disabled="acting[b.id]"
              @click="forceResolve(b, null)"
              title="Résoudre void (refund tous)"
            >
              ○ Nul
            </button>
            <button
              class="btn-mini cancel"
              :disabled="acting[b.id]"
              @click="forceCancel(b)"
              title="Cancel + refund tous"
            >
              ⊘ Cancel
            </button>
          </div>
        </div>
        <div v-else class="admin-actions">
          <button
            v-if="b.status !== 'resolved'"
            class="btn-mini delete"
            :disabled="acting[b.id]"
            @click="deleteRow(b)"
            title="Supprimer définitivement"
          >
            🗑 Supprimer
          </button>
          <span v-if="b.resolved_by" class="resolved-by mono">
            résolu par {{ formatResolvedBy(b.resolved_by) }}
            <template v-if="b.resolved_at">
              · {{ formatShort(b.resolved_at) }}
            </template>
          </span>
        </div>
      </article>
    </div>

    <div v-if="globalSuccess" class="alert success" style="margin-top: 1em">
      {{ globalSuccess }}
    </div>
  </main>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from "vue";
import AdminTopBar from "@/components/admin/AdminTopBar.vue";
import { useAuthStore } from "@/stores/auth";
import { useOrdersStore } from "@/stores/orders";
import { adminBetsApi } from "@/api/bets";
import { formatNum } from "@/config";

const auth = useAuthStore();
const ordersStore = useOrdersStore();

const STATUSES = [
  { value: "all", label: "Tous" },
  { value: "open", label: "Ouverts" },
  { value: "resolved", label: "Résolus" },
  { value: "cancelled", label: "Annulés" },
  { value: "expired", label: "Expirés" },
];

const bets = ref([]);
const counts = ref({});
const loading = ref(false);
const error = ref(null);
const filterStatus = ref("all");
const acting = reactive({});
const globalSuccess = ref("");

const totalPot = computed(() =>
  bets.value.reduce((s, b) => s + Number(b.pot_total || 0), 0),
);

async function loadAll() {
  loading.value = true;
  error.value = null;
  try {
    bets.value = await adminBetsApi.list(
      auth.adminToken,
      filterStatus.value === "all" ? {} : { status: filterStatus.value },
    );
    if (filterStatus.value === "all") {
      const c = {};
      for (const b of bets.value) c[b.status] = (c[b.status] || 0) + 1;
      c.all = bets.value.length;
      counts.value = c;
    } else {
      counts.value = {
        ...counts.value,
        [filterStatus.value]: bets.value.length,
      };
    }
    ordersStore.load("all").catch(() => {});
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}

function notify(message) {
  globalSuccess.value = message;
  setTimeout(() => {
    globalSuccess.value = "";
  }, 6000);
}

async function forceResolve(bet, option) {
  const label = option ? `"${option.label}"` : "NUL (refund tous)";
  if (!confirm(`Force-resolve pari #${bet.id} → ${label} ?`)) return;
  acting[bet.id] = true;
  error.value = null;
  try {
    const updated = await adminBetsApi.resolve(
      auth.adminToken,
      bet.id,
      option ? option.id : null,
    );
    const i = bets.value.findIndex((b) => b.id === bet.id);
    if (i >= 0) bets.value[i] = updated;
    notify(`Pari #${bet.id} résolu (${label}).`);
  } catch (e) {
    error.value = e.message;
  } finally {
    acting[bet.id] = false;
  }
}

async function forceCancel(bet) {
  if (
    !confirm(
      `Force-cancel pari #${bet.id} ? Refund de ${bet.participants_count} participant(s).`,
    )
  )
    return;
  acting[bet.id] = true;
  error.value = null;
  try {
    const updated = await adminBetsApi.cancel(auth.adminToken, bet.id);
    const i = bets.value.findIndex((b) => b.id === bet.id);
    if (i >= 0) bets.value[i] = updated;
    notify(`Pari #${bet.id} annulé.`);
  } catch (e) {
    error.value = e.message;
  } finally {
    acting[bet.id] = false;
  }
}

async function deleteRow(bet) {
  if (
    !confirm(
      `SUPPRIMER définitivement pari #${bet.id} ?\n\n` +
        `N'annule PAS les mouvements on-chain. Réservé aux tests/erreurs.`,
    )
  )
    return;
  acting[bet.id] = true;
  error.value = null;
  try {
    await adminBetsApi.delete(auth.adminToken, bet.id);
    bets.value = bets.value.filter((b) => b.id !== bet.id);
    notify(`Pari #${bet.id} supprimé.`);
  } catch (e) {
    error.value = e.message;
  } finally {
    acting[bet.id] = false;
  }
}

function statusLabel(s) {
  return (
    {
      open: "Ouvert",
      resolved: "Résolu",
      cancelled: "Annulé",
      expired: "Expiré",
    }[s] || s
  );
}

function formatResolvedBy(r) {
  if (r === "__community__") return "communauté";
  if (r === "__admin__") return "admin";
  if (r === "__expired__") return "expiration";
  return r;
}

function formatShort(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n) => String(n).padStart(2, "0");
  return `${pad(d.getDate())}/${pad(d.getMonth() + 1)} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

onMounted(loadAll);
</script>

<style scoped>
.dot {
  color: var(--camp);
}

.pending-banner {
  display: flex;
  align-items: center;
  gap: 0.7em;
  padding: 0.9em 1.2em;
  background: linear-gradient(
    135deg,
    rgba(255, 122, 0, 0.15),
    rgba(255, 122, 0, 0.05)
  );
  border: 1px solid rgba(255, 122, 0, 0.3);
  border-radius: var(--radius);
  margin-bottom: 1.25em;
  text-decoration: none;
  color: var(--text-0);
  transition:
    transform 0.15s,
    border-color 0.15s;
}
.pending-banner:hover {
  border-color: var(--camp);
  text-decoration: none;
  transform: translateX(2px);
}
.pending-banner .dot-anim {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--camp);
  box-shadow: 0 0 10px var(--camp);
  animation: pulse 1.4s infinite;
}
.pending-banner .t {
  flex: 1;
}
.pending-banner .t b {
  color: var(--camp);
}
.pending-banner .arrow {
  font-size: 1.2em;
  color: var(--camp);
}

.toolbar {
  display: flex;
  gap: 0.8em;
  margin-bottom: 1em;
  flex-wrap: wrap;
  align-items: center;
}
.counts {
  color: var(--text-2);
  font-size: 0.88em;
}
.dim {
  color: var(--text-3);
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
  font-size: 0.85em;
  cursor: pointer;
  color: var(--text-1);
  display: inline-flex;
  align-items: center;
  gap: 0.5em;
  transition: all 0.15s;
}
.chip:hover {
  border-color: var(--border-strong);
  color: var(--text-0);
}
.chip.active {
  background: var(--camp);
  border-color: var(--camp);
  color: var(--bg-0);
}
.chip .count {
  background: var(--bg-2);
  padding: 0.05em 0.45em;
  border-radius: 999px;
  font-size: 0.75em;
}
.chip.active .count {
  background: rgba(0, 0, 0, 0.2);
  color: var(--bg-0);
}

.empty-state {
  text-align: center;
  padding: 2.5em 1em;
  color: var(--text-2);
}
.empty-state .emoji {
  font-size: 2em;
  margin-bottom: 0.5em;
}

/* ─── Cards liste admin ──────────────────────────────── */
.bets-list {
  display: flex;
  flex-direction: column;
  gap: 0.8em;
}
.admin-bet-card {
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1em 1.1em;
  display: flex;
  flex-direction: column;
  gap: 0.7em;
}
.bet-row-top {
  display: flex;
  align-items: center;
  gap: 0.7em;
  flex-wrap: wrap;
}
.bet-id {
  margin-left: auto;
  color: var(--text-3);
  font-size: 0.85em;
}
.bet-type {
  font-size: 0.7em;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--text-3);
}
.bet-row-statement {
  font-size: 1em;
  margin: 0;
  line-height: 1.35;
}

.bet-options {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4em;
}
.opt-pill {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 0.25em 0.7em 0.25em 0.85em;
  font-size: 0.82em;
  display: inline-flex;
  align-items: center;
  gap: 0.4em;
}
.opt-pill.winner {
  border-color: var(--gold);
  background: rgba(245, 200, 66, 0.1);
  color: var(--gold);
  font-weight: 700;
}
.opt-pill.void {
  border-style: dashed;
  color: var(--text-3);
}
.opt-label {
  font-weight: 600;
}
.opt-count {
  background: var(--bg-3);
  padding: 0.05em 0.5em;
  border-radius: 999px;
  font-size: 0.78em;
  color: var(--text-1);
  font-weight: 700;
}
.opt-pill.winner .opt-count {
  background: rgba(245, 200, 66, 0.2);
  color: var(--gold);
}

.bet-info-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.9em;
  font-size: 0.78em;
  color: var(--text-2);
  padding-top: 0.5em;
  border-top: 1px dashed var(--border);
}
.pot-info {
  color: var(--gold);
  font-weight: 700;
}

.status-pill {
  font-size: 0.7em;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 0.25em 0.7em;
  border-radius: 999px;
  display: inline-block;
}
.status-pill.open {
  background: var(--green-soft);
  color: var(--green);
}
.status-pill.resolved {
  background: var(--bg-3);
  color: var(--text-1);
}
.status-pill.cancelled {
  background: var(--bg-3);
  color: var(--text-3);
}
.status-pill.expired {
  background: var(--red-soft);
  color: var(--red);
}

/* ─── Admin actions row ──────────────────────────────── */
.admin-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4em;
  align-items: center;
  padding-top: 0.5em;
  border-top: 1px dashed var(--border);
}
.resolve-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4em;
  align-items: center;
  width: 100%;
}
.action-label {
  font-size: 0.78em;
  color: var(--text-2);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-right: 0.3em;
}

.btn-mini {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0.4em 0.7em;
  font-size: 0.82em;
  cursor: pointer;
  font-weight: 600;
  color: var(--text-1);
  display: inline-flex;
  align-items: center;
  gap: 0.4em;
  transition: all 0.15s;
}
.btn-mini:hover:not(:disabled) {
  border-color: var(--border-strong);
  color: var(--text-0);
}
.btn-mini:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.btn-mini.resolve:hover {
  border-color: var(--gold);
  color: var(--gold);
}
.btn-mini.void:hover {
  border-color: var(--text-2);
}
.btn-mini.cancel:hover {
  border-color: var(--camp);
  color: var(--camp);
}
.btn-mini.delete:hover {
  border-color: var(--red);
  color: var(--red);
}
.count-tag {
  background: var(--bg-3);
  padding: 0.05em 0.4em;
  border-radius: 999px;
  font-size: 0.7em;
  color: var(--text-2);
}

.resolved-by {
  font-size: 0.78em;
  color: var(--text-3);
}

.alert.error {
  background: rgba(255, 69, 102, 0.1);
  border: 1px solid var(--red);
  border-radius: var(--radius-sm);
  padding: 0.8em 1em;
  color: var(--red);
}
.alert.success {
  background: var(--green-soft);
  border: 1px solid var(--green);
  border-radius: var(--radius-sm);
  padding: 0.8em 1em;
  color: var(--green);
}

@media (max-width: 600px) {
  .bet-info-row {
    flex-direction: column;
    gap: 0.3em;
  }
  .admin-bet-card {
    padding: 0.9em;
  }
}
</style>
