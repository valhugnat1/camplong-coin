<template>
  <AdminTopBar :pending-count="ordersStore.pendingCount" />
  <main class="page fade-in">
    <div class="page-header">
      <h1 class="page-title">Backoffice <span class="dot">·</span> Paris</h1>
      <p class="page-sub">
        Tous les paris du système, override admin pour les cas tordus.
      </p>
    </div>

    <!-- Bandeau demandes en attente : pattern reutilise depuis AdminView -->
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

    <!-- Etats vides / erreurs -->
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

    <!-- Table principale -->
    <div v-else class="table-wrap">
      <table class="admin-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Statut</th>
            <th>Affirmation</th>
            <th>Créateur</th>
            <th>Opposant</th>
            <th>Arbitre</th>
            <th class="ralign">Pot</th>
            <th>Deadline</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="b in bets" :key="b.id">
            <td class="mono">#{{ b.id }}</td>
            <td>
              <span class="status-pill" :class="b.status">{{
                statusLabel(b.status)
              }}</span>
            </td>
            <td class="statement-cell">
              <div class="statement-text">{{ b.statement }}</div>
              <div v-if="b.category" class="statement-cat mono">
                {{ b.category }}
              </div>
            </td>
            <td>
              <div class="user-side">
                <span>{{ b.creator_username }}</span>
                <span class="side-tag" :class="`side-${b.creator_side}`">
                  {{ b.creator_side === "yes" ? "VRAI" : "FAUX" }}
                </span>
              </div>
              <div class="dim mono">{{ formatNum(b.stake_creator) }} CAMP</div>
            </td>
            <td>
              <template v-if="b.opponent_username">
                <div class="user-side">
                  <span>{{ b.opponent_username }}</span>
                  <span
                    class="side-tag"
                    :class="`side-${b.creator_side === 'yes' ? 'no' : 'yes'}`"
                  >
                    {{ b.creator_side === "yes" ? "FAUX" : "VRAI" }}
                  </span>
                </div>
                <div class="dim mono">
                  {{ formatNum(b.stake_opponent) }} CAMP
                </div>
              </template>
              <template v-else>
                <span class="dim">—</span>
              </template>
            </td>
            <td>
              <span v-if="b.arbiter_username">
                {{ b.arbiter_username }}
                <span v-if="b.arbiter_fee_pct" class="dim mono"
                  >({{ b.arbiter_fee_pct }}%)</span
                >
              </span>
              <span v-else class="dim">—</span>
            </td>
            <td class="ralign mono">
              {{ formatNum(b.stake_creator + b.stake_opponent) }}
            </td>
            <td class="mono">{{ formatShort(b.deadline) }}</td>
            <td class="actions-cell">
              <div class="action-row">
                <template v-if="b.status === 'matched'">
                  <button
                    class="btn-mini yes"
                    :disabled="acting[b.id]"
                    @click="forceResolve(b, 'yes')"
                    title="Résoudre VRAI"
                  >
                    ✓
                  </button>
                  <button
                    class="btn-mini no"
                    :disabled="acting[b.id]"
                    @click="forceResolve(b, 'no')"
                    title="Résoudre FAUX"
                  >
                    ✗
                  </button>
                  <button
                    class="btn-mini void"
                    :disabled="acting[b.id]"
                    @click="forceResolve(b, 'void')"
                    title="Annuler (refund)"
                  >
                    ○
                  </button>
                </template>
                <button
                  v-if="b.status === 'open' || b.status === 'matched'"
                  class="btn-mini cancel"
                  :disabled="acting[b.id]"
                  @click="forceCancel(b)"
                  title="Force-cancel + refund"
                >
                  ⊘
                </button>
                <button
                  v-if="b.status !== 'matched' && b.status !== 'resolved'"
                  class="btn-mini delete"
                  :disabled="acting[b.id]"
                  @click="deleteRow(b)"
                  title="Supprimer définitivement"
                >
                  🗑
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Notif globale (pattern AdminView) -->
    <div v-if="globalSuccess" class="alert success" style="margin-top: 1em">
      {{ globalSuccess }}
      <div v-if="globalTx" style="margin-top: 0.4em; font-size: 0.85em">
        <a
          :href="'https://sepolia.basescan.org/tx/' + globalTx"
          target="_blank"
          rel="noreferrer"
        >
          Voir la tx sur BaseScan →
        </a>
      </div>
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
  { value: "matched", label: "En cours" },
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
const globalTx = ref("");

const totalPot = computed(() =>
  bets.value.reduce(
    (s, b) => s + Number(b.stake_creator || 0) + Number(b.stake_opponent || 0),
    0,
  ),
);

async function loadAll() {
  loading.value = true;
  error.value = null;
  try {
    bets.value = await adminBetsApi.list(
      auth.adminToken,
      filterStatus.value === "all" ? {} : { status: filterStatus.value },
    );
    // Si on filtre, on recompte que pour le bucket courant
    // sinon on fait le full count
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
    // Recharge le compteur de demandes en attente (silencieux si erreur)
    ordersStore.load("all").catch(() => {});
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}

function notifyTx({ message, tx_hash }) {
  globalSuccess.value = message;
  globalTx.value = tx_hash || "";
  setTimeout(() => {
    globalSuccess.value = "";
    globalTx.value = "";
  }, 8000);
}

async function forceResolve(bet, resolution) {
  const labels = { yes: "VRAI", no: "FAUX", void: "NUL" };
  if (!confirm(`Force-resolve pari #${bet.id} → ${labels[resolution]} ?`))
    return;
  acting[bet.id] = true;
  error.value = null;
  try {
    const updated = await adminBetsApi.resolve(
      auth.adminToken,
      bet.id,
      resolution,
    );
    const i = bets.value.findIndex((b) => b.id === bet.id);
    if (i >= 0) bets.value[i] = updated;
    notifyTx({
      message: `Pari #${bet.id} résolu (${labels[resolution]})`,
      tx_hash: updated.tx_hash_payout_winner,
    });
  } catch (e) {
    error.value = e.message;
  } finally {
    acting[bet.id] = false;
  }
}

async function forceCancel(bet) {
  if (
    !confirm(
      `Force-cancel pari #${bet.id} ? Les fonds bloqués seront refundés.`,
    )
  )
    return;
  acting[bet.id] = true;
  error.value = null;
  try {
    const updated = await adminBetsApi.cancel(auth.adminToken, bet.id);
    const i = bets.value.findIndex((b) => b.id === bet.id);
    if (i >= 0) bets.value[i] = updated;
    notifyTx({ message: `Pari #${bet.id} annulé, fonds refundés.` });
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
        `Cette opération n'annule PAS les mouvements on-chain déjà faits, ` +
        `seulement la ligne en DB. À réserver aux tests / erreurs.`,
    )
  )
    return;
  acting[bet.id] = true;
  error.value = null;
  try {
    await adminBetsApi.delete(auth.adminToken, bet.id);
    bets.value = bets.value.filter((b) => b.id !== bet.id);
    notifyTx({ message: `Pari #${bet.id} supprimé.` });
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
      matched: "En cours",
      resolved: "Résolu",
      cancelled: "Annulé",
      expired: "Expiré",
    }[s] || s
  );
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

/* ─── Bandeau pending — copie 1:1 d'AdminView ─────────── */
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

/* ─── Toolbar (pattern OrdersView) ────────────────────── */
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

/* ─── Filtres (chip pattern) ──────────────────────────── */
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

/* ─── Status pills (pattern OrdersView) ───────────────── */
.status-pill {
  font-size: 0.72em;
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
.status-pill.matched {
  background: var(--camp-soft);
  color: var(--camp);
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

/* ─── Empty state (pattern OrdersView) ────────────────── */
.empty-state {
  text-align: center;
  padding: 2.5em 1em;
  color: var(--text-2);
}
.empty-state .emoji {
  font-size: 2em;
  margin-bottom: 0.5em;
}

/* ─── Table ──────────────────────────────────────────── */
.table-wrap {
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow-x: auto;
}
.admin-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.88em;
}
.admin-table th,
.admin-table td {
  padding: 0.7em 0.8em;
  text-align: left;
  vertical-align: top;
}
.admin-table thead th {
  background: var(--bg-2);
  font-weight: 600;
  font-size: 0.78em;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-2);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
}
.admin-table tbody tr {
  border-bottom: 1px solid var(--border);
}
.admin-table tbody tr:last-child {
  border-bottom: none;
}
.admin-table tbody tr:hover {
  background: var(--bg-2);
}

.statement-cell {
  max-width: 30ch;
}
.statement-text {
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.statement-cat {
  font-size: 0.7em;
  color: var(--camp);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-top: 0.2em;
}

.user-side {
  display: flex;
  align-items: center;
  gap: 0.4em;
  font-weight: 600;
}
.side-tag {
  font-size: 0.62em;
  padding: 0.1em 0.45em;
  border-radius: 999px;
  letter-spacing: 0.05em;
  font-weight: 700;
}
.side-yes {
  background: var(--green-soft);
  color: var(--green);
}
.side-no {
  background: var(--red-soft);
  color: var(--red);
}

.ralign {
  text-align: right;
}
.actions-cell {
  white-space: nowrap;
}

.action-row {
  display: flex;
  gap: 0.3em;
}
.btn-mini {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0.35em 0.6em;
  font-size: 1em;
  cursor: pointer;
  font-weight: 700;
  color: var(--text-1);
  transition: all 0.15s;
  line-height: 1;
}
.btn-mini:hover:not(:disabled) {
  border-color: var(--border-strong);
  color: var(--text-0);
}
.btn-mini:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.btn-mini.yes:hover {
  border-color: var(--green);
  color: var(--green);
}
.btn-mini.no:hover {
  border-color: var(--red);
  color: var(--red);
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

@media (max-width: 900px) {
  .admin-table {
    font-size: 0.75em;
  }
  .statement-cell {
    max-width: 18ch;
  }
}
</style>
