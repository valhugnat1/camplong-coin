<template>
  <AdminTopBar :pending-count="ordersStore.pendingCount" />
  <main class="page fade-in">

    <div class="page-header">
      <h1 class="page-title">🪙 Backoffice <span class="dot">·</span> Casino</h1>
      <p class="page-sub">
        Règle l'edge maison comme tu veux. Le front lit la config à chaque
        partie, pas besoin de redéployer.
      </p>
    </div>

    <div v-if="error" class="alert error">{{ error }}</div>
    <div v-if="successMsg" class="alert success">{{ successMsg }}</div>

    <div class="page-toolbar">
      <button class="btn-ghost btn-sm" @click="loadAll" :disabled="loading">
        {{ loading ? '…' : '↻ Rafraîchir' }}
      </button>
      <p class="card-explain dim">
        Les changements sont actifs <b>immédiatement</b> pour toutes les
        prochaines parties. Aucun redémarrage ni redéploiement nécessaire.
      </p>
    </div>

    <!-- ─── Settings Coinflip ──────────────────────────── -->
    <section class="card settings-card">
      <div class="card-header">
        <h3 class="card-title">🪙 Paramètres du coinflip</h3>
      </div>

      <div class="settings-grid">
        <!-- Edge maison -->
        <article class="setting-tile">
          <div class="setting-head">
            <div class="s-key">Edge maison</div>
            <div class="s-current mono">{{ stats?.coinflip?.edge_configured_pct ?? '—' }}%</div>
          </div>
          <p class="s-desc">
            Pourcentage que la maison garde sur chaque gain.
            Payout d'une victoire = <span class="mono">mise × 2 × (1 − edge/100)</span>.
            <br />
            Avec <b>2%</b> → multiplicateur <span class="mono">×1.96</span>.
            Avec <b>5%</b> → <span class="mono">×1.90</span>. Mets <b>0</b> pour
            un jeu équitable (la variance fera quand même mal au casino_bank).
          </p>
          <div class="s-edit">
            <input
              type="number"
              step="0.1"
              min="0"
              max="49.9"
              v-model.number="edit.coinflip_edge_pct"
              :disabled="saving.coinflip_edge_pct"
              placeholder="ex: 2 ou 2.5"
            />
            <button
              class="btn-primary btn-sm"
              :disabled="!canSave('coinflip_edge_pct') || saving.coinflip_edge_pct"
              @click="save('coinflip_edge_pct')"
            >
              {{ saving.coinflip_edge_pct ? '…' : 'Sauver' }}
            </button>
          </div>
          <div v-if="previewMultiplier !== null" class="s-preview">
            → Nouveau multiplicateur : <b class="mono">x{{ previewMultiplier }}</b>
            <span class="dim">
              ({{ previewExpected }} CAMP attendus pour 100 misés / partie sur 1000)
            </span>
          </div>
        </article>

        <!-- Min bet -->
        <article class="setting-tile">
          <div class="setting-head">
            <div class="s-key">Mise minimale</div>
            <div class="s-current mono">{{ stats?.coinflip?.min_bet ?? '—' }} CAMP</div>
          </div>
          <p class="s-desc">
            En dessous, le jeu refuse. Utile pour limiter le spam de
            micro-parties qui flood l'historique.
          </p>
          <div class="s-edit">
            <input
              type="number"
              step="1"
              min="1"
              v-model.number="edit.coinflip_min_bet"
              :disabled="saving.coinflip_min_bet"
            />
            <button
              class="btn-primary btn-sm"
              :disabled="!canSave('coinflip_min_bet') || saving.coinflip_min_bet"
              @click="save('coinflip_min_bet')"
            >
              {{ saving.coinflip_min_bet ? '…' : 'Sauver' }}
            </button>
          </div>
        </article>

        <!-- Max bet -->
        <article class="setting-tile">
          <div class="setting-head">
            <div class="s-key">Mise maximale</div>
            <div class="s-current mono">{{ stats?.coinflip?.max_bet ?? '—' }} CAMP</div>
          </div>
          <p class="s-desc">
            Plafond par partie. Conseil : <b>10×</b> moins que le solde du
            casino_bank pour ne pas se faire vider en une mauvaise série.
          </p>
          <div class="s-edit">
            <input
              type="number"
              step="1"
              min="1"
              v-model.number="edit.coinflip_max_bet"
              :disabled="saving.coinflip_max_bet"
            />
            <button
              class="btn-primary btn-sm"
              :disabled="!canSave('coinflip_max_bet') || saving.coinflip_max_bet"
              @click="save('coinflip_max_bet')"
            >
              {{ saving.coinflip_max_bet ? '…' : 'Sauver' }}
            </button>
          </div>
        </article>
      </div>
    </section>

    <!-- ─── Settings Roulette ──────────────────────────── -->
    <section class="card settings-card">
      <div class="card-header">
        <h3 class="card-title">🎡 Paramètres de la roulette</h3>
      </div>
      <p class="card-explain dim">
        L'edge maison de la roulette est <b>mécanique</b> (1/37 ≈ <b>2.70%</b>) et
        ne se configure pas — il est verrouillé par les règles du jeu européen.
        Tu peux ajuster les limites de mise <b>totale</b> par spin.
      </p>

      <div class="settings-grid">
        <article class="setting-tile">
          <div class="setting-head">
            <div class="s-key">Mise totale minimale</div>
            <div class="s-current mono">{{ stats?.roulette?.min_bet ?? '—' }} CAMP</div>
          </div>
          <p class="s-desc">
            Plancher pour la somme de toutes les mises d'un spin. Évite les
            spins à 1 CAMP qui floodent l'historique.
          </p>
          <div class="s-edit">
            <input
              type="number"
              step="1"
              min="1"
              v-model.number="edit.roulette_min_bet"
              :disabled="saving.roulette_min_bet"
            />
            <button
              class="btn-primary btn-sm"
              :disabled="!canSave('roulette_min_bet') || saving.roulette_min_bet"
              @click="save('roulette_min_bet')"
            >
              {{ saving.roulette_min_bet ? '…' : 'Sauver' }}
            </button>
          </div>
        </article>

        <article class="setting-tile">
          <div class="setting-head">
            <div class="s-key">Mise totale maximale</div>
            <div class="s-current mono">{{ stats?.roulette?.max_bet ?? '—' }} CAMP</div>
          </div>
          <p class="s-desc">
            Plafond agrégé. Un numéro plein gagnant à 35:1 paye <b>36×</b> la
            mise — calcule en conséquence vs le solde de casino_bank.
          </p>
          <div class="s-edit">
            <input
              type="number"
              step="1"
              min="1"
              v-model.number="edit.roulette_max_bet"
              :disabled="saving.roulette_max_bet"
            />
            <button
              class="btn-primary btn-sm"
              :disabled="!canSave('roulette_max_bet') || saving.roulette_max_bet"
              @click="save('roulette_max_bet')"
            >
              {{ saving.roulette_max_bet ? '…' : 'Sauver' }}
            </button>
          </div>
        </article>
      </div>
    </section>

    <!-- ─── Stats globales casino ──────────────────────── -->
    <h3 class="section-h">🪙 Coinflip — stats</h3>
    <section class="stats-grid" v-if="stats">
      <div class="stat-card">
        <div class="stat-k">Banque casino</div>
        <div class="stat-v mono">{{ formatNum(stats.bank.balance_camp) }}</div>
        <div class="stat-sub">CAMP en réserve</div>
        <div v-if="stats.bank.address" class="stat-foot mono dim">
          {{ shortAddr(stats.bank.address) }}
        </div>
        <div v-if="bankLow" class="alert error stat-warn">
          ⚠ Solde sous {{ maxBetSafe }} CAMP. Recharge depuis la treasury
          (Vue d'ensemble → Créditer __casino_bank__).
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-k">PnL casino</div>
        <div class="stat-v mono" :class="{ positive: stats.coinflip.pnl_camp >= 0, negative: stats.coinflip.pnl_camp < 0 }">
          {{ stats.coinflip.pnl_camp >= 0 ? '+' : '' }}{{ formatNum(stats.coinflip.pnl_camp) }}
        </div>
        <div class="stat-sub">CAMP cumulés</div>
        <div class="stat-foot mono dim">
          Volume misé : {{ formatNum(stats.coinflip.volume_bet) }}
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-k">RTP observé</div>
        <div class="stat-v mono">
          {{ stats.coinflip.rtp_observed_pct ?? '—' }}<span v-if="stats.coinflip.rtp_observed_pct !== null">%</span>
        </div>
        <div class="stat-sub">
          attendu : {{ (100 - stats.coinflip.edge_configured_pct).toFixed(2) }}%
        </div>
        <div class="stat-foot mono dim">
          {{ stats.coinflip.rounds_total }} partie{{ stats.coinflip.rounds_total > 1 ? 's' : '' }}
        </div>
      </div>
    </section>

    <!-- ─── Historique rounds Coinflip ─────────────────── -->
    <section v-if="stats?.recent_rounds?.length" class="recent-section">
      <h4 class="recent-title">📜 20 dernières parties coinflip</h4>
      <div class="table-wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th>#</th>
              <th>User</th>
              <th>Choix</th>
              <th>Tirage</th>
              <th class="ralign">Mise</th>
              <th class="ralign">Payout</th>
              <th>Quand</th>
              <th>Tx</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in stats.recent_rounds" :key="r.id" :class="{ won: r.win, lost: !r.win }">
              <td class="mono">#{{ r.id }}</td>
              <td>{{ r.username }}</td>
              <td>
                <b>{{ r.choice === 'heads' ? 'PILE' : 'FACE' }}</b>
              </td>
              <td>
                <span class="outcome-pill" :class="{ won: r.win, lost: !r.win }">
                  {{ r.outcome === 'heads' ? 'PILE' : 'FACE' }}
                </span>
              </td>
              <td class="ralign mono">{{ formatNum(r.bet_amount) }}</td>
              <td class="ralign mono">
                <span :class="{ accent: r.payout > 0, dim: !r.payout }">
                  {{ r.payout ? '+' + formatNum(r.payout) : '0' }}
                </span>
              </td>
              <td class="mono dim">{{ formatShort(r.ts) }}</td>
              <td class="mono">
                <a v-if="r.tx_hash_payout" :href="basescan(r.tx_hash_payout)" target="_blank" rel="noreferrer">
                  payout↗
                </a>
                <a v-else-if="r.tx_hash_lock" :href="basescan(r.tx_hash_lock)" target="_blank" rel="noreferrer">
                  lock↗
                </a>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- ─── Stats Roulette ─────────────────────────────── -->
    <h3 class="section-h">🎡 Roulette — stats</h3>
    <section class="stats-grid" v-if="stats?.roulette">
      <div class="stat-card">
        <div class="stat-k">PnL roulette</div>
        <div class="stat-v mono" :class="{ positive: stats.roulette.pnl_camp >= 0, negative: stats.roulette.pnl_camp < 0 }">
          {{ stats.roulette.pnl_camp >= 0 ? '+' : '' }}{{ formatNum(stats.roulette.pnl_camp) }}
        </div>
        <div class="stat-sub">CAMP cumulés</div>
        <div class="stat-foot mono dim">
          Volume misé : {{ formatNum(stats.roulette.volume_bet) }}
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-k">RTP observé</div>
        <div class="stat-v mono">
          {{ stats.roulette.rtp_observed_pct ?? '—' }}<span v-if="stats.roulette.rtp_observed_pct !== null">%</span>
        </div>
        <div class="stat-sub">
          attendu : {{ (100 - stats.roulette.edge_mechanical_pct).toFixed(2) }}%
        </div>
        <div class="stat-foot mono dim">
          {{ stats.roulette.spins_total }} spin{{ stats.roulette.spins_total > 1 ? 's' : '' }}
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-k">Edge mécanique</div>
        <div class="stat-v mono">{{ stats.roulette.edge_mechanical_pct }}%</div>
        <div class="stat-sub">1 / 37 cases</div>
        <div class="stat-foot mono dim">verrouillé par les règles</div>
      </div>
    </section>

    <!-- ─── Historique spins Roulette ──────────────────── -->
    <section v-if="stats?.recent_spins?.length" class="recent-section">
      <h4 class="recent-title">📜 20 derniers spins roulette</h4>
      <div class="table-wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th>#</th>
              <th>User</th>
              <th>Mises</th>
              <th>Tirage</th>
              <th class="ralign">Total misé</th>
              <th class="ralign">Payout</th>
              <th class="ralign">Net</th>
              <th>Quand</th>
              <th>Tx</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in stats.recent_spins" :key="r.id" :class="{ won: r.net_pnl > 0, lost: r.net_pnl < 0 }">
              <td class="mono">#{{ r.id }}</td>
              <td>{{ r.username }}</td>
              <td class="mono dim">{{ r.bets?.length || 0 }} spot{{ (r.bets?.length || 0) > 1 ? 's' : '' }}</td>
              <td>
                <span class="num-pill" :class="r.outcome_color">{{ r.outcome_number }}</span>
              </td>
              <td class="ralign mono">{{ formatNum(r.total_bet) }}</td>
              <td class="ralign mono">
                <span :class="{ accent: r.total_payout > 0, dim: !r.total_payout }">
                  {{ r.total_payout ? '+' + formatNum(r.total_payout) : '0' }}
                </span>
              </td>
              <td class="ralign mono" :class="{ positive: r.net_pnl > 0, negative: r.net_pnl < 0 }">
                {{ r.net_pnl > 0 ? '+' : '' }}{{ formatNum(r.net_pnl) }}
              </td>
              <td class="mono dim">{{ formatShort(r.ts) }}</td>
              <td class="mono">
                <a v-if="r.tx_hash_payout" :href="basescan(r.tx_hash_payout)" target="_blank" rel="noreferrer">
                  payout↗
                </a>
                <a v-else-if="r.tx_hash_lock" :href="basescan(r.tx_hash_lock)" target="_blank" rel="noreferrer">
                  lock↗
                </a>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </main>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import AdminTopBar from '@/components/admin/AdminTopBar.vue'
import { useAuthStore } from '@/stores/auth'
import { useOrdersStore } from '@/stores/orders'
import { adminCasinoApi, adminSettingsApi } from '@/api/casino'
import { formatNum } from '@/config'

const auth = useAuthStore()
const ordersStore = useOrdersStore()

const stats = ref(null)
const settings = ref([])
const loading = ref(false)
const error = ref('')
const successMsg = ref('')

// Edit buffers : initialisés depuis stats.coinflip.* au load.
const edit = reactive({
  coinflip_edge_pct: 2,
  coinflip_min_bet: 1,
  coinflip_max_bet: 200,
  roulette_min_bet: 1,
  roulette_max_bet: 200,
})
const saving = reactive({
  coinflip_edge_pct: false,
  coinflip_min_bet: false,
  coinflip_max_bet: false,
  roulette_min_bet: false,
  roulette_max_bet: false,
})

const bankLow = computed(() => {
  if (!stats.value) return false
  const balance = Number(stats.value.bank.balance_camp || 0)
  const maxBet = Number(stats.value.coinflip.max_bet || 0)
  // Seuil "safe" : 10x la mise max (recommandation seed_system_accounts)
  return balance < maxBet * 10
})

const maxBetSafe = computed(() => {
  return Number(stats.value?.coinflip?.max_bet || 0) * 10
})

// Preview du nouveau multiplicateur en fonction du buffer d'edit
const previewMultiplier = computed(() => {
  const v = Number(edit.coinflip_edge_pct)
  if (Number.isNaN(v) || v < 0 || v >= 50) return null
  return (2 * (1 - v / 100)).toFixed(3)
})

// Expected return par 100 CAMP misés sur 1000 parties (espérance)
const previewExpected = computed(() => {
  const v = Number(edit.coinflip_edge_pct)
  if (Number.isNaN(v)) return '—'
  // 50% chance de gagner, payout = 100 * 2 * (1 - v/100) - 100
  // E(par partie) = 0.5 * (100 * 2 * (1 - v/100)) + 0.5 * 0 - 100 = -v
  // Sur 1000 parties à 100 CAMP misés : casino gagne 1000 * v CAMP
  const houseGainPer100 = (v).toFixed(2)
  return `casino gagne ~${houseGainPer100} CAMP par 100 misés`
})

function canSave(key) {
  if (!stats.value) return false
  const current = currentValue(key)
  const next = edit[key]
  if (next === '' || next === null || next === undefined) return false
  if (Number.isNaN(Number(next))) return false
  return Number(next) !== Number(current)
}

function currentValue(key) {
  if (!stats.value) return null
  if (key === 'coinflip_edge_pct') return stats.value.coinflip.edge_configured_pct
  if (key === 'coinflip_min_bet') return stats.value.coinflip.min_bet
  if (key === 'coinflip_max_bet') return stats.value.coinflip.max_bet
  if (key === 'roulette_min_bet') return stats.value.roulette?.min_bet
  if (key === 'roulette_max_bet') return stats.value.roulette?.max_bet
  return null
}

async function loadAll() {
  loading.value = true
  error.value = ''
  try {
    const [s, sett] = await Promise.all([
      adminCasinoApi.stats(auth.adminToken),
      adminSettingsApi.list(auth.adminToken),
    ])
    stats.value = s
    settings.value = sett
    // Sync les buffers d'edit sur les valeurs courantes
    edit.coinflip_edge_pct = Number(s.coinflip.edge_configured_pct)
    edit.coinflip_min_bet = Number(s.coinflip.min_bet)
    edit.coinflip_max_bet = Number(s.coinflip.max_bet)
    if (s.roulette) {
      edit.roulette_min_bet = Number(s.roulette.min_bet)
      edit.roulette_max_bet = Number(s.roulette.max_bet)
    }
    ordersStore.load('all').catch(() => {})
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function save(key) {
  if (!canSave(key)) return
  saving[key] = true
  error.value = ''
  successMsg.value = ''
  try {
    await adminSettingsApi.update(auth.adminToken, key, edit[key])
    successMsg.value = `${labelOf(key)} mise à jour : ${edit[key]}`
    setTimeout(() => (successMsg.value = ''), 4000)
    await loadAll()
  } catch (e) {
    error.value = e.message
  } finally {
    saving[key] = false
  }
}

function labelOf(key) {
  return {
    coinflip_edge_pct: 'Edge maison (coinflip)',
    coinflip_min_bet: 'Mise minimale (coinflip)',
    coinflip_max_bet: 'Mise maximale (coinflip)',
    roulette_min_bet: 'Mise totale minimale (roulette)',
    roulette_max_bet: 'Mise totale maximale (roulette)',
  }[key] || key
}

function shortAddr(addr) {
  if (!addr) return ''
  return `${addr.slice(0, 6)}…${addr.slice(-4)}`
}
function basescan(hash) {
  return `https://sepolia.basescan.org/tx/${hash}`
}
function formatShort(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(d.getDate())}/${pad(d.getMonth() + 1)} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

onMounted(loadAll)
</script>

<style scoped>
.dot { color: var(--camp); }
.dim { color: var(--text-3); }
.accent { color: var(--camp); }
.positive { color: var(--green); }
.negative { color: var(--red); }
.ralign { text-align: right; }

/* ─── Settings card ───────────────────────────────────── */
.settings-card {
  background:
    radial-gradient(circle at 90% 10%, rgba(245, 200, 66, 0.06), transparent 60%),
    var(--bg-1);
  margin-bottom: 1.5em;
}
.card-explain {
  font-size: 0.9em;
  margin: 0 0 1.2em 0;
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1em;
}

.setting-tile {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 1.1em 1em;
}
.setting-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 0.5em;
  flex-wrap: wrap;
  gap: 0.4em;
}
.s-key {
  font-size: 0.78em;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-1);
}
.s-current {
  font-size: 1.4em;
  font-weight: 700;
  color: var(--camp);
}
.s-desc {
  color: var(--text-2);
  font-size: 0.85em;
  line-height: 1.55;
  margin: 0 0 0.85em 0;
}
.s-edit {
  display: flex;
  gap: 0.5em;
  align-items: stretch;
}
.s-edit input {
  flex: 1;
  font-family: 'JetBrains Mono', monospace;
}
.s-preview {
  margin-top: 0.7em;
  padding: 0.5em 0.7em;
  background: var(--camp-soft);
  border: 1px solid rgba(255, 122, 0, 0.2);
  border-radius: var(--radius-sm);
  color: var(--camp);
  font-size: 0.85em;
}
.s-preview .dim { font-size: 0.88em; }

/* ─── Stats grid ──────────────────────────────────────── */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 1em;
  margin-bottom: 1.5em;
}
.stat-card {
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.2em 1.3em;
}
.stat-k {
  font-size: 0.78em;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-2);
  font-weight: 600;
  margin-bottom: 0.4em;
}
.stat-v {
  font-size: 2em;
  font-weight: 700;
  font-family: 'Bricolage Grotesque', sans-serif;
  letter-spacing: -0.02em;
  line-height: 1;
}
.stat-sub {
  color: var(--text-2);
  font-size: 0.82em;
  margin-top: 0.3em;
}
.stat-foot {
  font-size: 0.8em;
  margin-top: 0.7em;
}
.stat-warn {
  margin: 0.7em 0 0;
  font-size: 0.82em;
}

/* ─── Recent rounds table ─────────────────────────────── */
.recent-section { margin-top: 0.5em; }
.recent-title {
  font-size: 1.1em;
  margin-bottom: 0.7em;
}
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
}
.admin-table thead th {
  background: var(--bg-2);
  font-weight: 600;
  font-size: 0.78em;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-2);
  border-bottom: 1px solid var(--border);
}
.admin-table tbody tr { border-bottom: 1px solid var(--border); }
.admin-table tbody tr:last-child { border-bottom: none; }
.admin-table tbody tr:hover { background: var(--bg-2); }
.admin-table tbody tr.won { border-left: 3px solid var(--green); }
.admin-table tbody tr.lost { border-left: 3px solid var(--red); opacity: 0.85; }

.outcome-pill {
  font-size: 0.72em;
  font-weight: 700;
  letter-spacing: 0.06em;
  padding: 0.2em 0.6em;
  border-radius: 999px;
}
.outcome-pill.won { background: var(--green-soft); color: var(--green); }
.outcome-pill.lost { background: var(--red-soft); color: var(--red); }

.num-pill {
  display: inline-grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
  font-size: 0.85em;
  color: white;
}
.num-pill.red { background: #c4302b; }
.num-pill.black { background: #1a1a1a; border: 1px solid #2a2a2a; }
.num-pill.green { background: #0d8050; }

.page-toolbar {
  display: flex;
  align-items: center;
  gap: 1em;
  margin-bottom: 1em;
}
.page-toolbar .card-explain { margin: 0; }

.section-h {
  margin: 2em 0 0.8em 0;
  font-size: 1.05em;
  color: var(--text-1);
  padding-top: 1em;
  border-top: 1px dashed var(--border);
}

@media (max-width: 760px) {
  .settings-grid { grid-template-columns: 1fr; }
  .admin-table { font-size: 0.78em; }
}
</style>
