<template>
  <AdminTopBar :pending-count="ordersStore.pendingCount" />
  <main class="page fade-in">

    <div class="page-header">
      <h1 class="page-title">📊 Backoffice <span class="dot">·</span> Qui a fait quoi</h1>
      <p class="page-sub">
        P&amp;L <b>borné à la période</b> et <b>net des recharges</b> : ce que
        chacun a fait depuis la date choisie, sans que son passé ni ses
        rechargements ne le fassent monter.
      </p>
    </div>

    <div v-if="error" class="alert error">{{ error }}</div>

    <div class="page-toolbar">
      <label class="since-field">
        <span class="field-label">Activité depuis</span>
        <input type="datetime-local" v-model="sinceLocal" @change="load" />
      </label>
      <button class="btn-ghost btn-sm" @click="load" :disabled="loading">
        {{ loading ? '…' : '↻ Rafraîchir' }}
      </button>
      <p class="card-explain dim">
        Tout est compté à partir de cette date. La référence n'est pas « 1000
        CAMP pour tous » mais la <b>valeur réelle de chacun à cette date</b>,
        reconstruite depuis le ledger — sinon les parties jouées avant, ou un
        reset admin, seraient attribués à la période.
      </p>
    </div>

    <div v-if="!report && loading" class="empty-state">
      <div class="emoji">⏳</div>
      Calcul en cours…
    </div>

    <template v-if="report">
      <!-- ─── Chiffres globaux ───────────────────────────── -->
      <section class="kpi-row">
        <article class="kpi">
          <div class="k-label">Valeur détenue par les joueurs</div>
          <div class="k-value mono">{{ fmt(report.totals.total_value_camp) }}</div>
          <div class="k-sub dim">
            wallet {{ fmt(report.totals.wallet_camp) }} ·
            lait {{ fmt(report.totals.milk_value_camp) }} ·
            paris {{ fmt(report.totals.bets_locked_camp) }} ·
            poker {{ fmt(report.totals.poker_stack_camp) }}
          </div>
        </article>

        <article class="kpi">
          <div class="k-label">Base de mesure</div>
          <div class="k-value mono">{{ fmt(report.totals.net_deposited_camp) }}</div>
          <div class="k-sub dim">
            valeur au départ {{ fmt(report.totals.opening_value_camp) }} ·
            dont <b>{{ fmt(report.totals.topups_camp) }}</b> rechargés depuis
          </div>
        </article>

        <article class="kpi">
          <div class="k-label">P&amp;L global des joueurs</div>
          <div class="k-value mono" :class="signClass(report.totals.pnl_camp)">
            {{ signed(report.totals.pnl_camp) }}
          </div>
          <div class="k-sub dim">
            ce que les joueurs ont pris à la maison (casino, lait, paris)
          </div>
        </article>

        <article class="kpi">
          <div class="k-label">Investi en bourse du lait</div>
          <div class="k-value mono">{{ fmt(report.totals.milk_value_camp) }}</div>
          <div class="k-sub dim">
            {{ report.pools.reduce((a, p) => a + p.holders, 0) }} position(s) ·
            valeur réalisable
          </div>
        </article>

        <article class="kpi">
          <div class="k-label">Volume misé au casino</div>
          <div class="k-value mono">{{ fmt(report.totals.casino_volume_camp) }}</div>
          <div class="k-sub dim">
            {{ fmt(report.totals.casino_plays) }} parties ·
            joueurs
            <span :class="signClass(report.totals.casino_pnl_players_camp)">
              {{ signed(report.totals.casino_pnl_players_camp) }}
            </span>
          </div>
        </article>

        <article class="kpi">
          <div class="k-label">Actions totales</div>
          <div class="k-value mono">{{ fmt(report.totals.actions) }}</div>
          <div class="k-sub dim">
            parties + trades + paris rejoints
          </div>
        </article>
      </section>

      <!-- ─── Podiums ────────────────────────────────────── -->
      <section class="card">
        <div class="card-header">
          <h3 class="card-title">🏆 Podiums</h3>
        </div>
        <div class="podium-grid">
          <article v-for="p in podiums" :key="p.key" class="podium"
                   :class="{ expanded: openPodium === p.key }">
            <div class="p-title">{{ p.icon }} {{ p.title }}</div>
            <p class="p-desc dim">{{ p.desc }}</p>

            <ol v-if="ranking(p).length" class="p-list">
              <li v-for="(row, i) in visibleRanking(p)" :key="row.username">
                <span class="medal">{{ ['🥇', '🥈', '🥉'][i] || '#' + (i + 1) }}</span>
                <span class="p-name">{{ row.username }}</span>
                <span class="p-val mono" :class="p.signed ? signClass(row.value) : ''">
                  {{ p.signed ? signed(row.value) : fmt(row.value) }}{{ p.unit || '' }}
                </span>
              </li>
            </ol>
            <p v-else class="dim p-empty">Personne pour l'instant.</p>

            <button
              v-if="ranking(p).length > 3"
              class="p-more"
              @click="openPodium = openPodium === p.key ? null : p.key"
            >
              {{ openPodium === p.key
                  ? '− Replier'
                  : `+ Voir les ${ranking(p).length} joueurs` }}
            </button>
          </article>
        </div>
      </section>

      <!-- ─── Classement ─────────────────────────────────── -->
      <section class="card">
        <div class="card-header">
          <h3 class="card-title">Classement ({{ report.users.length }} joueurs)</h3>
          <span class="hint dim">Clique une colonne pour trier · une ligne pour le détail</span>
        </div>

        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th class="rank-col">#</th>
                <th @click="sortBy('username')" class="sortable">Joueur {{ arrow('username') }}</th>
                <th @click="sortBy('wallet_camp')" class="sortable num">Wallet {{ arrow('wallet_camp') }}</th>
                <th @click="sortBy('milk_value_camp')" class="sortable num">Lait {{ arrow('milk_value_camp') }}</th>
                <th @click="sortBy('bets_locked_camp')" class="sortable num">Paris {{ arrow('bets_locked_camp') }}</th>
                <th @click="sortBy('poker_stack_camp')" class="sortable num">Poker {{ arrow('poker_stack_camp') }}</th>
                <th @click="sortBy('total_value_camp')" class="sortable num">Total {{ arrow('total_value_camp') }}</th>
                <th @click="sortBy('opening_value_camp')" class="sortable num" title="Valeur au début de la période, reconstruite depuis le ledger">Départ {{ arrow('opening_value_camp') }}</th>
                <th @click="sortBy('net_deposited_camp')" class="sortable num" title="Valeur de départ + dépôts − retraits de la période">Base {{ arrow('net_deposited_camp') }}</th>
                <th @click="sortBy('pnl_camp')" class="sortable num">P&amp;L {{ arrow('pnl_camp') }}</th>
                <th @click="sortBy('actions')" class="sortable num">Actions {{ arrow('actions') }}</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="(u, i) in sortedUsers" :key="u.username">
                <tr class="row" :class="{ open: expanded === u.username }" @click="toggle(u.username)">
                  <td class="rank-col dim">{{ i + 1 }}</td>
                  <td>
                    <b>{{ u.username }}</b>
                    <span v-if="u.has_topped_up" class="tag-topup" title="A rechargé du CAMP">
                      +{{ fmt(u.topups_camp) }} rechargé
                    </span>
                  </td>
                  <td class="num mono">{{ fmt(u.wallet_camp) }}</td>
                  <td class="num mono" :class="{ dim: !u.milk_value_camp }">{{ fmt(u.milk_value_camp) }}</td>
                  <td class="num mono" :class="{ dim: !u.bets_locked_camp }">{{ fmt(u.bets_locked_camp) }}</td>
                  <td class="num mono" :class="{ dim: !u.poker_stack_camp }">{{ fmt(u.poker_stack_camp) }}</td>
                  <td class="num mono strong">{{ fmt(u.total_value_camp) }}</td>
                  <td class="num mono dim">{{ fmt(u.opening_value_camp) }}</td>
                  <td class="num mono dim">{{ fmt(u.net_deposited_camp) }}</td>
                  <td class="num mono strong" :class="signClass(u.pnl_camp)">
                    {{ signed(u.pnl_camp) }}
                    <span v-if="u.pnl_pct !== null" class="pct">({{ signedPct(u.pnl_pct) }})</span>
                  </td>
                  <td class="num mono">{{ fmt(u.actions) }}</td>
                </tr>

                <tr v-if="expanded === u.username" :key="u.username + '-d'" class="detail-row">
                  <td colspan="11">
                    <div class="detail">
                      <!-- Casino -->
                      <article class="d-block">
                        <h4>🪙 Casino</h4>
                        <div class="d-line">
                          <span>Total</span>
                          <b class="mono" :class="signClass(u.casino.pnl_camp)">{{ signed(u.casino.pnl_camp) }}</b>
                        </div>
                        <div class="d-line dim">
                          <span>{{ u.casino.plays }} parties · {{ fmt(u.casino.volume_camp) }} misés</span>
                        </div>
                        <div v-for="g in ['coinflip', 'roulette', 'slots']" :key="g" class="d-sub">
                          <span class="dim">{{ gameLabel[g] }}</span>
                          <span class="mono dim">{{ u.casino[g].plays }} pt</span>
                          <span class="mono" :class="signClass(u.casino[g].pnl_camp)">
                            {{ signed(u.casino[g].pnl_camp) }}
                          </span>
                        </div>
                      </article>

                      <!-- Lait -->
                      <article class="d-block">
                        <h4>🥛 Bourse du lait</h4>
                        <div class="d-line">
                          <span>P&amp;L total</span>
                          <b class="mono" :class="signClass(u.milk.pnl_camp)">{{ signed(u.milk.pnl_camp) }}</b>
                        </div>
                        <div class="d-line dim">
                          <span>{{ u.milk.trades }} trades ({{ u.milk.buys }} achats / {{ u.milk.sells }} ventes)</span>
                        </div>
                        <div class="d-line dim">
                          <span>Flux net réalisé</span>
                          <span class="mono">{{ signed(u.milk.realized_camp) }}</span>
                        </div>
                        <div class="d-line dim">
                          <span>Frais payés</span>
                          <span class="mono">{{ fmt(u.milk.fees_camp) }}</span>
                        </div>
                        <div v-if="u.milk.positions.length" class="d-positions">
                          <div v-for="p in u.milk.positions" :key="p.pool_id" class="d-pos">
                            <span class="pos-sym">{{ p.symbol }}</span>
                            <span class="mono dim">{{ fmt(p.bottles) }} bt</span>
                            <span class="mono">{{ fmt(p.value_camp) }}</span>
                            <span class="mono" :class="signClass(p.unrealized_pnl_camp)">
                              {{ signed(p.unrealized_pnl_camp) }}
                            </span>
                          </div>
                        </div>
                        <p v-else class="dim d-empty">Aucune position ouverte.</p>
                      </article>

                      <!-- Paris + poker -->
                      <article class="d-block">
                        <h4>🎲 Paris &amp; 🃏 Poker</h4>
                        <div class="d-line">
                          <span>Paris</span>
                          <b class="mono" :class="signClass(u.bets.pnl)">{{ signed(u.bets.pnl) }}</b>
                        </div>
                        <div class="d-line dim">
                          <span>{{ u.bets.joined }} rejoints · {{ fmt(u.bets.staked) }} misés</span>
                        </div>
                        <div v-if="u.bets_locked_camp" class="d-line dim">
                          <span>Bloqué (paris en cours)</span>
                          <span class="mono">{{ fmt(u.bets_locked_camp) }}</span>
                        </div>
                        <div class="d-line" style="margin-top: 0.6em">
                          <span>Poker</span>
                          <b class="mono" :class="signClass(u.poker.pnl)">{{ signed(u.poker.pnl) }}</b>
                        </div>
                        <div v-if="u.poker.stack_camp" class="d-line dim">
                          <span>Stack en cours</span>
                          <span class="mono">{{ fmt(u.poker.stack_camp) }}</span>
                        </div>
                      </article>

                      <!-- Argent injecté -->
                      <article class="d-block">
                        <h4>💸 D'où vient son argent</h4>
                        <div v-if="u.onboarding_camp" class="d-line">
                          <span>Dotation reçue dans la période</span>
                          <span class="mono">{{ fmt(u.onboarding_camp) }}</span>
                        </div>
                        <div class="d-line">
                          <span>Recharges</span>
                          <span class="mono" :class="{ warn: u.topups_camp > 0 }">{{ fmt(u.topups_camp) }}</span>
                        </div>
                        <div class="d-line">
                          <span>Retiré</span>
                          <span class="mono">{{ fmt(u.withdrawals_camp) }}</span>
                        </div>
                        <div class="d-line dim">
                          <span title="Reconstruit depuis le ledger : solde actuel moins les mouvements de la période">
                            Valeur au départ
                          </span>
                          <span class="mono">{{ fmt(u.opening_value_camp) }}</span>
                        </div>
                        <div class="d-line strong">
                          <span>Net injecté</span>
                          <b class="mono">{{ fmt(u.net_deposited_camp) }}</b>
                        </div>
                        <div class="d-line strong">
                          <span>Valeur actuelle</span>
                          <b class="mono">{{ fmt(u.total_value_camp) }}</b>
                        </div>
                      </article>
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </section>

      <!-- ─── Ajustement des dépôts ─────────────────────── -->
      <section class="card">
        <div class="card-header">
          <h3 class="card-title">🛠️ Ajuster les dépôts</h3>
          <button class="btn-ghost btn-sm" @click="toggleFlows">
            {{ showFlows ? 'Masquer' : 'Afficher' }} ({{ flows?.movements?.length ?? '…' }})
          </button>
        </div>

        <p class="card-explain dim">
          Chaque mouvement entre un joueur et la trésorerie est classé
          automatiquement d'après sa note. Corrige ici les cas où la déduction
          est fausse — typiquement une <b>mise de départ versée à la main
          après coup</b>, qui compte à tort comme une recharge.
          <br />
          Ça n'écrit que dans une table d'étiquettes :
          <b>la transaction d'origine n'est jamais modifiée</b>.
        </p>

        <div v-if="showFlows">
          <div v-if="flowsError" class="alert error">{{ flowsError }}</div>

          <div v-if="flows" class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Joueur</th>
                  <th class="num">Montant</th>
                  <th>Note d'origine</th>
                  <th>Compté comme</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="mv in flows.movements" :key="mv.tx_id"
                    :class="{ 'out-period': !mv.in_period }">
                  <td class="mono nowrap">
                    {{ new Date(mv.ts).toLocaleString('fr-FR', dateOpts) }}
                    <span v-if="!mv.in_period" class="tag-out" title="Hors période analysée">
                      hors période
                    </span>
                  </td>
                  <td><b>{{ mv.username }}</b></td>
                  <td class="num mono" :class="mv.direction === 'in' ? 'pos' : 'neg'">
                    {{ mv.direction === 'in' ? '+' : '−' }}{{ fmt(mv.amount_camp) }}
                  </td>
                  <td class="dim note-cell">{{ mv.note || '—' }}</td>
                  <td>
                    <select
                      class="label-select"
                      :value="mv.source === 'manual' ? mv.label : ''"
                      :disabled="savingTx === mv.tx_id"
                      @change="onLabelChange(mv, $event.target.value)"
                    >
                      <option value="">Auto → {{ labelText[mv.label] }}</option>
                      <option value="onboarding">Capital de départ</option>
                      <option value="topup">Recharge</option>
                      <option value="withdrawal">Retrait</option>
                      <option value="ignore">Ignorer</option>
                    </select>
                  </td>
                  <td>
                    <span v-if="savingTx === mv.tx_id" class="dim">…</span>
                    <span v-else-if="mv.source === 'manual'" class="tag-manual">corrigé</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div v-else class="empty-state">
            <div class="emoji">⏳</div>
            Chargement des mouvements…
          </div>
        </div>
      </section>

      <!-- ─── Positions par bourse ───────────────────────── -->
      <section class="card">
        <div class="card-header">
          <h3 class="card-title">🥛 Positions par bourse</h3>
          <span class="hint mono">
            total investi : {{ fmt(report.totals.milk_value_camp) }} CAMP
          </span>
        </div>

        <div v-if="!report.pools.length" class="empty-state">
          <div class="emoji">🫙</div>
          Aucun pool.
        </div>

        <div v-else class="pool-grid">
          <article v-for="p in report.pools" :key="p.pool_id" class="pool">
            <div class="pool-head">
              <div>
                <div class="pool-name">{{ p.name }}</div>
                <div class="pool-sym mono dim">{{ p.symbol }}</div>
              </div>
              <div class="pool-price mono">
                {{ p.price_camp_per_bottle.toFixed(2) }}
                <span class="dim">CAMP/bt</span>
              </div>
            </div>

            <div class="pool-stats">
              <div>
                <div class="ps-label dim">Détenu par</div>
                <div class="ps-value mono">{{ p.holders }} joueur{{ p.holders > 1 ? 's' : '' }}</div>
              </div>
              <div>
                <div class="ps-label dim">Bouteilles détenues</div>
                <div class="ps-value mono">{{ fmt(p.bottles_held) }}</div>
              </div>
              <div>
                <div class="ps-label dim">Valeur réalisable</div>
                <div class="ps-value mono strong">{{ fmt(p.value_camp) }}</div>
              </div>
              <div>
                <div class="ps-label dim">P&amp;L latent</div>
                <div class="ps-value mono" :class="signClass(p.unrealized_pnl_camp)">
                  {{ signed(p.unrealized_pnl_camp) }}
                </div>
              </div>
            </div>

            <div class="pool-holders" v-if="holdersOf(p.pool_id).length">
              <div v-for="h in holdersOf(p.pool_id)" :key="h.username" class="ph">
                <span class="ph-name">{{ h.username }}</span>
                <span class="ph-bar">
                  <span class="ph-fill" :style="{ width: share(h.value_camp, p.value_camp) }"></span>
                </span>
                <span class="ph-val mono">{{ fmt(h.value_camp) }}</span>
              </div>
            </div>
          </article>
        </div>
      </section>

      <p class="footnote dim">
        {{ report.note }}
        <br />
        Calculé le {{ new Date(report.generated_at).toLocaleString('fr-FR') }}.
      </p>
    </template>
  </main>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import AdminTopBar from '@/components/admin/AdminTopBar.vue'
import { useAuthStore } from '@/stores/auth'
import { useOrdersStore } from '@/stores/orders'
import { adminAnalyticsApi } from '@/api/analytics'
import { formatNum } from '@/config'

const auth = useAuthStore()
const ordersStore = useOrdersStore()

const report = ref(null)
const loading = ref(false)
const error = ref('')
const expanded = ref(null)

// Lancement de l'app : 22/08/2026 22h heure de Paris. L'input est en heure
// locale, on convertit en UTC a l'envoi (le backend stocke en UTC).
const sinceLocal = ref('2026-08-22T22:00')

const sortKey = ref('pnl_camp')
const sortAsc = ref(false)

// Panneau d'ajustement des dépôts
const flows = ref(null)
const flowsError = ref('')
const showFlows = ref(false)
const savingTx = ref(null)

const dateOpts = { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }
const labelText = {
  onboarding: 'capital de départ',
  topup: 'recharge',
  withdrawal: 'retrait',
  ignore: 'ignoré',
}

const gameLabel = { coinflip: 'Pile ou face', roulette: 'Roulette', slots: 'Machine à sous' }

const podiums = [
  { key: 'best_pnl', icon: '📈', title: 'Meilleur P&L', signed: true,
    desc: 'Net des recharges : le vrai classement.' },
  { key: 'worst_pnl', icon: '📉', title: 'Pire P&L', signed: true, reverse: true,
    desc: 'Ceux qui ont le plus fondu.' },
  { key: 'best_casino', icon: '🍀', title: 'A plumé le casino', signed: true,
    desc: 'Gains nets sur coinflip + roulette + slots.' },
  { key: 'worst_casino', icon: '🔥', title: 'A nourri le casino', signed: true, reverse: true,
    desc: 'Pertes nettes au casino.' },
  { key: 'most_active', icon: '⚡', title: 'Le plus actif', signed: false, unit: ' actions',
    desc: 'Parties + trades + paris rejoints.' },
  { key: 'biggest_gambler', icon: '🎰', title: 'Plus gros volume misé', signed: false,
    desc: 'Total misé au casino, gagné ou perdu.' },
  { key: 'best_milk_trader', icon: '🥛', title: 'Meilleur tradeur de lait', signed: true,
    desc: 'Flux réalisé + valeur du stock encore détenu.' },
  { key: 'biggest_milk_position', icon: '🏦', title: 'Plus grosse position lait', signed: false,
    desc: 'Valeur réalisable du portefeuille actuel.' },
]

const openPodium = ref(null)

/**
 * Classement complet pour un podium donne.
 *
 * Le backend ne renvoie que le top 3 dans `report.podiums`, mais il renvoie
 * aussi TOUS les joueurs : on rejoue donc le tri ici plutot que de rappeler
 * l'API pour "voir plus". Les joueurs a zero sont ecartes, comme cote backend
 * (etre 12e ex aequo avec 0 partie jouee n'apprend rien).
 */
function ranking(p) {
  if (!report.value) return []
  return report.value.users
    .map(u => ({ username: u.username, value: podiumValue(p.key, u) }))
    .filter(r => r.value !== 0)
    .sort((a, b) => (p.reverse ? a.value - b.value : b.value - a.value))
}

function visibleRanking(p) {
  const all = ranking(p)
  return openPodium.value === p.key ? all : all.slice(0, 3)
}

function podiumValue(key, u) {
  switch (key) {
    case 'best_pnl':
    case 'worst_pnl': return u.pnl_camp
    case 'best_casino':
    case 'worst_casino': return u.casino.pnl_camp
    case 'most_active': return u.actions
    case 'biggest_gambler': return u.casino.volume_camp
    case 'best_milk_trader': return u.milk.pnl_camp
    case 'biggest_milk_position': return u.milk_value_camp
    default: return 0
  }
}

const sortedUsers = computed(() => {
  if (!report.value) return []
  const rows = [...report.value.users]
  const k = sortKey.value
  rows.sort((a, b) => {
    const va = a[k], vb = b[k]
    const cmp = typeof va === 'string' ? va.localeCompare(vb) : (va - vb)
    return sortAsc.value ? cmp : -cmp
  })
  return rows
})

function sortBy(key) {
  if (sortKey.value === key) {
    sortAsc.value = !sortAsc.value
  } else {
    sortKey.value = key
    // Un nom se lit A→Z, un montant se lit du plus gros au plus petit.
    sortAsc.value = key === 'username'
  }
}

function arrow(key) {
  if (sortKey.value !== key) return ''
  return sortAsc.value ? '↑' : '↓'
}

function toggle(username) {
  expanded.value = expanded.value === username ? null : username
}

/** Détenteurs d'un pool, du plus gros au plus petit. */
function holdersOf(poolId) {
  if (!report.value) return []
  return report.value.users
    .map(u => {
      const pos = u.milk.positions.find(p => p.pool_id === poolId)
      return pos ? { username: u.username, value_camp: pos.value_camp } : null
    })
    .filter(Boolean)
    .sort((a, b) => b.value_camp - a.value_camp)
}

/** Largeur de barre, en gardant 0% plutot que NaN si le pool vaut 0. */
function share(value, total) {
  const t = Number(total || 0)
  return t > 0 ? (100 * Number(value || 0)) / t + '%' : '0%'
}

const fmt = (n) => formatNum(Math.round(Number(n || 0)))
const signed = (n) => (Number(n) > 0 ? '+' : '') + fmt(n)
const signedPct = (n) => (Number(n) > 0 ? '+' : '') + Number(n).toFixed(1) + '%'
const signClass = (n) => (Number(n) > 0 ? 'pos' : Number(n) < 0 ? 'neg' : 'dim')

/** datetime-local est en heure locale : toISOString() la ramene en UTC. */
function sinceIso() {
  return sinceLocal.value ? new Date(sinceLocal.value).toISOString() : undefined
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    report.value = await adminAnalyticsApi.overview(auth.adminToken, sinceIso())
    // Le panneau d'ajustement affiche un flag "hors periode" : il doit suivre
    // la meme date que le rapport.
    if (showFlows.value) await loadFlows()
  } catch (e) {
    error.value = e.message || 'Impossible de charger les stats'
  } finally {
    loading.value = false
  }
}

async function loadFlows() {
  flowsError.value = ''
  try {
    flows.value = await adminAnalyticsApi.flows(auth.adminToken, sinceIso())
  } catch (e) {
    flowsError.value = e.message || 'Impossible de charger les mouvements'
  }
}

function toggleFlows() {
  showFlows.value = !showFlows.value
  if (showFlows.value && !flows.value) loadFlows()
}

/**
 * Applique une reclassification. La valeur vide du <select> signifie
 * "revenir a la deduction automatique" -> label null cote API.
 */
async function onLabelChange(mv, value) {
  savingTx.value = mv.tx_id
  flowsError.value = ''
  try {
    await adminAnalyticsApi.setLabel(auth.adminToken, mv.tx_id, value || null)
    // Le PnL de tout le monde peut bouger : on recharge les deux.
    await Promise.all([load(), loadFlows()])
  } catch (e) {
    flowsError.value = e.message || 'Impossible de reclasser ce mouvement'
    await loadFlows()   // resynchronise le <select> avec l'etat serveur
  } finally {
    savingTx.value = null
  }
}

onMounted(() => {
  load()
  // Alimente le badge "demandes en attente" de la topbar, comme les autres
  // vues admin. Silencieux si ca echoue : ce n'est pas le sujet de la page.
  ordersStore.load('all').catch(() => {})
})
</script>

<style scoped>
.dot { color: var(--text-3); }
.dim { color: var(--text-2); }
.pos { color: var(--green); }
.neg { color: var(--red); }
.strong { color: var(--text-0); font-weight: 700; }
.warn { color: var(--gold); }
.num { text-align: right; }
.mono { font-variant-numeric: tabular-nums; }

.page-toolbar {
  display: flex;
  align-items: flex-end;
  gap: 1em;
  flex-wrap: wrap;
  margin-bottom: 1.2em;
}
.since-field { display: flex; flex-direction: column; gap: 0.3em; }
.since-field input {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-0);
  padding: 0.5em 0.7em;
  font-size: 0.9em;
}
.card-explain { flex: 1; min-width: 260px; font-size: 0.82em; margin: 0; }

/* ─── KPI ─── */
.kpi-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(215px, 1fr));
  gap: 0.9em;
  margin-bottom: 1.3em;
}
.kpi {
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1em 1.1em;
}
.k-label {
  font-size: 0.75em;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-2);
  font-weight: 700;
}
.k-value { font-size: 1.65em; font-weight: 700; margin: 0.18em 0 0.25em; }
.k-sub { font-size: 0.78em; line-height: 1.45; }

/* ─── Podiums ─── */
.podium-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(255px, 1fr));
  gap: 0.9em;
  padding: 0.2em 0 0.4em;
}
.podium {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0.9em 1em;
}
.p-title { font-weight: 700; font-size: 0.95em; }
.p-desc { font-size: 0.76em; margin: 0.25em 0 0.7em; line-height: 1.4; }
.p-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.35em; }
.p-list li { display: flex; align-items: center; gap: 0.5em; font-size: 0.9em; }
.medal { width: 1.3em; }
.p-name { flex: 1; font-weight: 600; }
.p-val { font-weight: 700; }
.p-empty { font-size: 0.82em; margin: 0; }
.p-more {
  margin-top: 0.6em;
  background: none;
  border: none;
  color: var(--text-2);
  font-size: 0.78em;
  font-weight: 700;
  cursor: pointer;
  padding: 0.2em 0;
}
.p-more:hover { color: var(--camp); }
.podium.expanded { background: var(--bg-3); }
.podium.expanded .p-list { max-height: 19em; overflow-y: auto; }

/* ─── Table ─── */
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 0.9em; }
th {
  text-align: left;
  padding: 0.6em 0.7em;
  color: var(--text-2);
  font-size: 0.82em;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
th.sortable { cursor: pointer; user-select: none; }
th.sortable:hover { color: var(--text-0); }
td { padding: 0.62em 0.7em; border-bottom: 1px solid var(--border); }
.rank-col { width: 2.2em; text-align: center; }
tr.row { cursor: pointer; }
tr.row:hover td { background: var(--bg-2); }
tr.row.open td { background: var(--bg-2); border-bottom-color: transparent; }
.pct { font-size: 0.82em; opacity: 0.75; margin-left: 0.25em; }

.tag-topup {
  margin-left: 0.5em;
  background: rgba(245, 200, 66, 0.12);
  color: var(--gold);
  border-radius: 999px;
  padding: 0.1em 0.55em;
  font-size: 0.7em;
  font-weight: 700;
  white-space: nowrap;
}

/* ─── Détail ─── */
.detail-row td { background: var(--bg-2); padding: 0 0.7em 1em; }
.detail {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
  gap: 1em;
}
.d-block {
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0.8em 0.9em;
}
.d-block h4 { margin: 0 0 0.6em; font-size: 0.88em; }
.d-line {
  display: flex;
  justify-content: space-between;
  gap: 0.6em;
  font-size: 0.85em;
  padding: 0.15em 0;
}
.d-sub {
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: 0.6em;
  font-size: 0.8em;
  padding: 0.12em 0;
}
.d-positions { margin-top: 0.55em; display: grid; gap: 0.3em; }
.d-pos {
  display: grid;
  grid-template-columns: 1fr auto auto auto;
  gap: 0.55em;
  font-size: 0.8em;
}
.pos-sym { color: var(--text-1); }
.d-empty { font-size: 0.8em; margin: 0.4em 0 0; }

/* ─── Pools ─── */
.pool-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(290px, 1fr));
  gap: 0.9em;
  padding-bottom: 0.3em;
}
.pool {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0.95em 1em;
}
.pool-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 0.6em; }
.pool-name { font-weight: 700; }
.pool-sym { font-size: 0.76em; }
.pool-price { font-size: 0.9em; font-weight: 700; }
.pool-price .dim { font-size: 0.8em; font-weight: 400; }
.pool-stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.55em 0.9em;
  margin: 0.85em 0;
}
.ps-label { font-size: 0.72em; text-transform: uppercase; letter-spacing: 0.04em; }
.ps-value { font-size: 0.95em; }
.pool-holders { display: grid; gap: 0.35em; border-top: 1px solid var(--border); padding-top: 0.7em; }
.ph { display: grid; grid-template-columns: 5.5em 1fr auto; gap: 0.55em; align-items: center; font-size: 0.8em; }
.ph-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ph-bar { height: 6px; background: var(--bg-3); border-radius: 999px; overflow: hidden; }
.ph-fill { display: block; height: 100%; background: var(--camp); border-radius: 999px; }

/* ─── Ajustement des dépôts ─── */
.nowrap { white-space: nowrap; }
.note-cell { max-width: 16em; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
tr.out-period td { opacity: 0.55; }
.label-select {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-0);
  padding: 0.32em 0.5em;
  font-size: 0.85em;
  max-width: 15em;
}
.label-select:hover { border-color: var(--border-strong); }
.tag-out, .tag-manual {
  border-radius: 999px;
  padding: 0.1em 0.5em;
  font-size: 0.7em;
  font-weight: 700;
  white-space: nowrap;
}
.tag-out { background: var(--bg-3); color: var(--text-2); margin-left: 0.4em; }
.tag-manual { background: rgba(164, 132, 255, 0.14); color: var(--violet); }

.footnote { font-size: 0.78em; line-height: 1.5; margin: 1.4em 0 2em; }

@media (max-width: 760px) {
  .k-value { font-size: 1.35em; }
  .pool-stats { grid-template-columns: 1fr; }
}
</style>
