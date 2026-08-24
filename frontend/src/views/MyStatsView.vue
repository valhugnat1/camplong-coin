<template>
  <AppLayout>
    <main class="page fade-in">
      <div class="page-header">
        <h1 class="page-title">
          📊 Mes stats
          <span v-if="myName" class="whoami">{{ myName }}</span>
        </h1>
        <p class="page-sub">
          Ce que tu as fait depuis le lancement. Recharger du CAMP ne compte pas
          comme un gain — seul ce que tu gagnes en jouant fait bouger ce chiffre.
        </p>
      </div>

      <div v-if="error" class="alert error">{{ error }}</div>

      <div v-if="!me && loading" class="empty-state">
        <div class="emoji">⏳</div>
        On compte…
      </div>

      <template v-if="me">
        <!-- ─── Résultat ────────────────────────────────── -->
        <section class="hero">
          <div class="hero-main">
            <div class="hero-label">Mon résultat</div>
            <div class="hero-value mono" :class="signClass(me.pnl_camp)">
              {{ signed(me.pnl_camp) }}
              <span class="hero-unit">CAMP</span>
            </div>
            <div class="hero-sub dim">
              <span v-if="me.pnl_pct !== null">{{ signedPct(me.pnl_pct) }} · </span>
              {{ verdict }}
            </div>
          </div>

          <div class="hero-split">
            <div class="hs-row">
              <span class="dim">Dans mon wallet</span>
              <span class="mono">{{ fmt(me.wallet_camp) }}</span>
            </div>
            <div class="hs-row" v-if="me.milk_value_camp">
              <span class="dim">En bouteilles de lait</span>
              <span class="mono">{{ fmt(me.milk_value_camp) }}</span>
            </div>
            <div class="hs-row" v-if="me.bets_locked_camp">
              <span class="dim">Bloqué dans des paris</span>
              <span class="mono">{{ fmt(me.bets_locked_camp) }}</span>
            </div>
            <div class="hs-row" v-if="me.poker_stack_camp">
              <span class="dim">Sur une table de poker</span>
              <span class="mono">{{ fmt(me.poker_stack_camp) }}</span>
            </div>
            <div class="hs-row total">
              <span>Ma fortune totale</span>
              <span class="mono">{{ fmt(me.total_value_camp) }}</span>
            </div>
            <div class="hs-row dim small">
              <span title="Tout le monde est reparti de 1000 CAMP au lancement, le 22 août.">
                Ma mise de départ
              </span>
              <span class="mono">{{ fmt(STARTING_CAMP) }}</span>
            </div>
            <div class="hs-row dim small" v-if="me.topups_camp">
              <span>Rechargé depuis</span>
              <span class="mono">{{ fmt(me.topups_camp) }}</span>
            </div>
          </div>
        </section>

        <!-- ─── Par activité ────────────────────────────── -->
        <section class="act-grid">
          <article class="act">
            <div class="act-head">
              <h3>🎰 Casino</h3>
              <span class="mono act-pnl" :class="signClass(me.casino.pnl_camp)">
                {{ signed(me.casino.pnl_camp) }}
              </span>
            </div>
            <p class="act-sub dim">
              {{ fmt(me.casino.plays) }} parties · {{ fmt(me.casino.volume_camp) }} CAMP misés
            </p>
            <div v-for="g in games" :key="g.key" class="act-line">
              <span class="dim">{{ g.icon }} {{ g.label }}</span>
              <span class="mono dim">{{ me.casino[g.key].plays }}</span>
              <span class="mono" :class="signClass(me.casino[g.key].pnl_camp)">
                {{ signed(me.casino[g.key].pnl_camp) }}
              </span>
            </div>
          </article>

          <article class="act">
            <div class="act-head">
              <h3>🥛 Bourse du lait</h3>
              <span class="mono act-pnl" :class="signClass(me.milk.pnl_camp)">
                {{ signed(me.milk.pnl_camp) }}
              </span>
            </div>
            <p class="act-sub dim">
              {{ me.milk.trades }} trades · {{ me.milk.buys }} achats /
              {{ me.milk.sells }} ventes · {{ fmt(me.milk.fees_camp) }} de frais
            </p>
            <div v-if="me.milk.positions.length" class="pos-list">
              <div v-for="p in me.milk.positions" :key="p.pool_id" class="pos">
                <span class="pos-name">{{ p.name }}</span>
                <span class="mono dim">{{ fmt(p.bottles) }} bt</span>
                <span class="mono">{{ fmt(p.value_camp) }}</span>
                <span class="mono" :class="signClass(p.unrealized_pnl_camp)">
                  {{ signed(p.unrealized_pnl_camp) }}
                </span>
              </div>
              <p class="dim tiny">
                Valeur si tu vendais tout maintenant, price impact compris.
              </p>
            </div>
            <p v-else class="dim tiny">Aucune bouteille en stock.</p>
          </article>

          <article class="act">
            <div class="act-head">
              <h3>🎯 Paris</h3>
              <span class="mono act-pnl" :class="signClass(me.bets.pnl)">
                {{ signed(me.bets.pnl) }}
              </span>
            </div>
            <p class="act-sub dim">
              {{ me.bets.joined }} paris rejoints · {{ fmt(me.bets.staked) }} misés
            </p>
            <div v-if="me.bets_locked_camp" class="act-line">
              <span class="dim">En cours</span>
              <span></span>
              <span class="mono">{{ fmt(me.bets_locked_camp) }}</span>
            </div>
          </article>

          <article class="act">
            <div class="act-head">
              <h3>🃏 Poker</h3>
              <span class="mono act-pnl" :class="signClass(me.poker.pnl)">
                {{ signed(me.poker.pnl) }}
              </span>
            </div>
            <p class="act-sub dim">
              <span v-if="me.poker.stack_camp">
                {{ fmt(me.poker.stack_camp) }} CAMP encore sur la table
              </span>
              <span v-else>Pas assis en ce moment.</span>
            </p>
          </article>
        </section>

        <p class="actions-line dim">
          <b class="mono">{{ fmt(me.actions) }}</b> actions au total (parties,
          trades et paris confondus) depuis le
          {{ new Date(since).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' }) }}.
        </p>

        <!-- ─── Classement de tout le monde ─────────────── -->
        <section class="card">
          <div class="card-header">
            <h3 class="card-title">🏆 Le classement</h3>
            <span class="hint dim">Le même que le bandeau, en plus lisible</span>
          </div>

          <div v-if="!leaderboard.length" class="empty-state">
            <div class="emoji">⏳</div>
            Chargement…
          </div>

          <ol v-else class="board">
            <li
              v-for="p in leaderboard"
              :key="p.username"
              class="board-row"
              :class="[medal(p.rank), { me: p.username === myName }]"
            >
              <span class="b-rank mono">{{ medalIcon(p.rank) || '#' + p.rank }}</span>
              <span class="b-name">
                {{ p.username }}
                <span v-if="p.username === myName" class="b-you">toi</span>
              </span>
              <span class="b-bar">
                <span class="b-fill" :style="{ width: share(p.balance) }"></span>
              </span>
              <span class="b-val mono">{{ fmt(p.balance) }}</span>
            </li>
          </ol>

          <p class="dim tiny board-note">
            Classement par CAMP dans le wallet. Ce n'est pas la même chose que
            mon résultat ci-dessus : ce que tu as investi en lait ou misé dans un
            pari en cours n'est plus dans ton wallet, donc n'apparaît pas ici.
          </p>
        </section>
      </template>
    </main>
  </AppLayout>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import AppLayout from '@/components/layout/AppLayout.vue'
import { useAuthStore } from '@/stores/auth'
import { useWalletStore } from '@/stores/wallet'
import { myStatsApi } from '@/api/analytics'
import { formatNum, STARTING_CAMP } from '@/config'

const auth = useAuthStore()
const wallet = useWalletStore()

const me = ref(null)
const since = ref(null)
const leaderboard = ref([])
const loading = ref(false)
const error = ref('')

// Le username vit dans le store wallet, jamais dans le store auth.
const myName = computed(() => wallet.me?.username)

const games = [
  { key: 'coinflip', icon: '🪙', label: 'Pile ou face' },
  { key: 'roulette', icon: '🎡', label: 'Roulette' },
  { key: 'slots', icon: '🍒', label: 'Machine à sous' },
]

const verdict = computed(() => {
  if (!me.value) return ''
  const p = me.value.pnl_camp
  if (p > 500) return 'Tu écrases le marché.'
  if (p > 0) return 'Dans le vert, tranquille.'
  if (p === 0) return 'Pile à l\'équilibre.'
  if (p > -500) return 'Ça va, ça se rattrape.'
  return 'La maison te remercie.'
})

const maxBalance = computed(
  () => Math.max(1, ...leaderboard.value.map(p => Number(p.balance || 0)))
)
const share = (v) => (100 * Number(v || 0)) / maxBalance.value + '%'

const fmt = (n) => formatNum(Math.round(Number(n || 0)))
const signed = (n) => (Number(n) > 0 ? '+' : '') + fmt(n)
const signedPct = (n) => (Number(n) > 0 ? '+' : '') + Number(n).toFixed(1) + '%'
const signClass = (n) => (Number(n) > 0 ? 'pos' : Number(n) < 0 ? 'neg' : 'dim')

const medal = (rank) => ({ 1: 'gold', 2: 'silver', 3: 'bronze' })[rank] || ''
const medalIcon = (rank) => ({ 1: '🥇', 2: '🥈', 3: '🥉' })[rank] || ''

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [stats, board] = await Promise.all([
      myStatsApi.get(auth.userToken),
      myStatsApi.leaderboard(auth.userToken),
    ])
    me.value = stats.me
    since.value = stats.since
    leaderboard.value = board
  } catch (e) {
    error.value = e.message || 'Impossible de charger tes stats'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  if (!wallet.me?.username) wallet.refresh?.()
  load()
})
</script>

<style scoped>
.whoami {
  background: var(--camp-soft);
  color: var(--camp);
  border-radius: 999px;
  padding: 0.12em 0.6em;
  font-size: 0.5em;
  font-weight: 700;
  vertical-align: middle;
  margin-left: 0.4em;
}
.dim { color: var(--text-2); }
.pos { color: var(--green); }
.neg { color: var(--red); }
.mono { font-variant-numeric: tabular-nums; }
.tiny { font-size: 0.78em; line-height: 1.5; }

/* ─── Hero ─── */
.hero {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.2em;
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.4em 1.5em;
  margin-bottom: 1.2em;
}
.hero-label {
  font-size: 0.78em;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-2);
  font-weight: 700;
}
.hero-value { font-size: 2.6em; font-weight: 800; line-height: 1.1; margin: 0.1em 0; }
.hero-unit { font-size: 0.42em; font-weight: 600; opacity: 0.6; margin-left: 0.2em; }
.hero-sub { font-size: 0.88em; }
.hero-split { display: flex; flex-direction: column; justify-content: center; gap: 0.32em; }
.hs-row { display: flex; justify-content: space-between; gap: 1em; font-size: 0.9em; }
.hs-row.total {
  border-top: 1px solid var(--border);
  padding-top: 0.4em;
  margin-top: 0.2em;
  font-weight: 700;
  color: var(--text-0);
}
.hs-row.small { font-size: 0.8em; }

/* ─── Activités ─── */
.act-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(255px, 1fr));
  gap: 0.9em;
  margin-bottom: 1em;
}
.act {
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1em 1.1em;
}
.act-head { display: flex; justify-content: space-between; align-items: baseline; gap: 0.6em; }
.act-head h3 { margin: 0; font-size: 1em; }
.act-pnl { font-weight: 800; font-size: 1.05em; }
.act-sub { font-size: 0.8em; margin: 0.35em 0 0.7em; line-height: 1.45; }
.act-line {
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: 0.7em;
  font-size: 0.84em;
  padding: 0.16em 0;
}
.pos-list { display: grid; gap: 0.3em; }
.pos {
  display: grid;
  grid-template-columns: 1fr auto auto auto;
  gap: 0.55em;
  font-size: 0.84em;
}
.pos-name { color: var(--text-1); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.actions-line { font-size: 0.88em; margin: 0 0 1.4em; }

/* ─── Classement ─── */
.board { list-style: none; margin: 0; padding: 0.2em 0 0; display: grid; gap: 0.3em; }
.board-row {
  display: grid;
  grid-template-columns: 2.6em minmax(5em, 1fr) 2fr auto;
  gap: 0.7em;
  align-items: center;
  padding: 0.42em 0.5em;
  border-radius: var(--radius-sm);
  font-size: 0.92em;
}
.board-row.me {
  background: var(--camp-soft);
  box-shadow: inset 0 0 0 1px rgba(255, 122, 0, 0.3);
}
.b-rank { text-align: center; color: var(--text-2); font-size: 0.9em; }
.board-row.gold .b-rank,
.board-row.silver .b-rank,
.board-row.bronze .b-rank { font-size: 1.05em; }
.b-name { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.b-you {
  background: var(--camp);
  color: white;
  border-radius: 999px;
  padding: 0.05em 0.45em;
  font-size: 0.68em;
  font-weight: 700;
  margin-left: 0.4em;
  vertical-align: middle;
}
.b-bar { height: 7px; background: var(--bg-2); border-radius: 999px; overflow: hidden; }
.b-fill { display: block; height: 100%; background: var(--camp); border-radius: 999px; }
.board-row.gold .b-fill { background: var(--gold); }
.b-val { font-weight: 700; }
.board-note { margin: 0.9em 0 0; }

@media (max-width: 700px) {
  .hero { grid-template-columns: 1fr; }
  .hero-value { font-size: 2.1em; }
  .board-row { grid-template-columns: 2.2em 1fr auto; }
  .b-bar { display: none; }
}
</style>
