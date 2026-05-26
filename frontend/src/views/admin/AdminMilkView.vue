<template>
  <AdminTopBar :pending-count="ordersStore.pendingCount" />
  <main class="page fade-in">
    <div class="page-header">
      <h1 class="page-title">🥛 Backoffice <span class="dot">·</span> Bourse du Lait</h1>
      <p class="page-sub">
        Crée des pools, ajuste les frais, balance des événements chaos. Le bot
        dieu tourne en background (1 chance sur 4 toutes les 15 min par pool).
      </p>
    </div>

    <div v-if="error" class="alert error">{{ error }}</div>
    <div v-if="successMsg" class="alert success">{{ successMsg }}</div>

    <!-- ─── Toolbar + Create pool ─────────────────────── -->
    <div class="toolbar">
      <button class="btn-ghost btn-sm" @click="loadAll" :disabled="loading">
        {{ loading ? '…' : '↻ Rafraîchir' }}
      </button>
      <button class="btn-primary btn-sm" @click="openCreate = true">
        + Créer un pool
      </button>
    </div>

    <!-- ─── Bot chaos : frequence ─────────────────────── -->
    <section class="card chaos-freq-card">
      <div class="card-header">
        <h3 class="card-title">🤖 Bot chaos · fréquence</h3>
        <span class="dim small">
          modifs prises en compte au prochain tick (pas besoin de redémarrer)
        </span>
      </div>
      <div class="freq-grid">
        <div class="freq-tile">
          <div class="freq-head">
            <span class="freq-k">Période entre ticks</span>
            <span class="freq-v mono">{{ freq.milk_chaos_tick_seconds || '—' }}s
              <span class="dim small">({{ tickHuman }})</span>
            </span>
          </div>
          <p class="freq-desc">
            Toutes les <b>{{ tickHuman }}</b>, le bot regarde chaque pool actif
            et tire au sort si un événement doit tomber. Plus c'est court, plus
            le marché est nerveux.
          </p>
          <div class="freq-edit">
            <input
              type="number"
              min="60"
              max="86400"
              step="60"
              v-model.number="editFreq.milk_chaos_tick_seconds"
            />
            <button
              class="btn-primary btn-sm"
              :disabled="!canSaveFreq('milk_chaos_tick_seconds') || savingFreq.milk_chaos_tick_seconds"
              @click="saveFreq('milk_chaos_tick_seconds')"
            >
              {{ savingFreq.milk_chaos_tick_seconds ? '…' : 'Sauver' }}
            </button>
          </div>
        </div>

        <div class="freq-tile">
          <div class="freq-head">
            <span class="freq-k">Probabilité par tick</span>
            <span class="freq-v mono">{{ freq.milk_chaos_proba_pct ?? '—' }}%</span>
          </div>
          <p class="freq-desc">
            Sur chaque pool actif, à chaque tick, <b>{{ freq.milk_chaos_proba_pct ?? 0 }}%</b>
            de chance qu'un event soit tiré. <b>0</b> = bot éteint.
            <b>100</b> = un event à chaque tick.
          </p>
          <div class="freq-edit">
            <input
              type="number"
              min="0"
              max="100"
              step="1"
              v-model.number="editFreq.milk_chaos_proba_pct"
            />
            <button
              class="btn-primary btn-sm"
              :disabled="!canSaveFreq('milk_chaos_proba_pct') || savingFreq.milk_chaos_proba_pct"
              @click="saveFreq('milk_chaos_proba_pct')"
            >
              {{ savingFreq.milk_chaos_proba_pct ? '…' : 'Sauver' }}
            </button>
          </div>
        </div>

        <div class="freq-tile">
          <div class="freq-head">
            <span class="freq-k">Volatilité max</span>
            <span class="freq-v mono">{{ freq.milk_chaos_max_volatility_pct ?? '—' }}%</span>
          </div>
          <p class="freq-desc">
            Plafond de variation de prix par event du bot. À <b>20%</b>, un event
            ne peut pas faire bouger le prix de plus de <b>±20%</b> même si le
            template tirait « famine -25% ». Évite les chocs trop violents qui
            drainent la banque quand les holders revendent au pic.
            <br />
            <span class="dim">
              <b>0</b> = bot muet · <b>100</b> = pas de cap.
            </span>
          </p>
          <div class="freq-edit">
            <input
              type="number"
              min="0"
              max="100"
              step="1"
              v-model.number="editFreq.milk_chaos_max_volatility_pct"
            />
            <button
              class="btn-primary btn-sm"
              :disabled="!canSaveFreq('milk_chaos_max_volatility_pct') || savingFreq.milk_chaos_max_volatility_pct"
              @click="saveFreq('milk_chaos_max_volatility_pct')"
            >
              {{ savingFreq.milk_chaos_max_volatility_pct ? '…' : 'Sauver' }}
            </button>
          </div>
        </div>

        <div class="freq-tile stats-tile">
          <div class="freq-head">
            <span class="freq-k">Cadence estimée</span>
            <span class="freq-v mono">{{ estimatedRate }}</span>
          </div>
          <p class="freq-desc">
            Avec <b>{{ pools.filter(p => p.status === 'active' && p.chaos_enabled).length }}</b>
            pool{{ pools.filter(p => p.status === 'active' && p.chaos_enabled).length > 1 ? 's' : '' }}
            actif{{ pools.filter(p => p.status === 'active' && p.chaos_enabled).length > 1 ? 's' : '' }} ·
            <b>{{ enabledTemplatesCount }}</b> template{{ enabledTemplatesCount > 1 ? 's' : '' }} activé{{ enabledTemplatesCount > 1 ? 's' : '' }}.
          </p>
        </div>
      </div>
    </section>

    <!-- ─── Espérance banque ──────────────────────────── -->
    <section v-if="analysis" class="card analysis-card">
      <div class="card-header">
        <h3 class="card-title">💰 Espérance banque · catalogue chaos</h3>
        <span class="dim small">
          Cap de volatilité appliqué
          <span v-if="analysis.max_vol_pct != null">
            ({{ analysis.max_vol_pct }}% prix · lait dans
            [{{ formatSigned(analysis.milk_cap_lo_pct) }}%,
            {{ analysis.milk_cap_hi_pct != null ? '+' + analysis.milk_cap_hi_pct + '%' : '∞' }}])
          </span>
          · suppose un rééquilibrage des holders
        </span>
      </div>

      <div class="analysis-grid">
        <div class="analysis-tile" :class="biasClass">
          <div class="a-k">Drift moyen / event</div>
          <div class="a-v mono">
            {{ formatSigned(analysis.weighted_avg_bank_drift_pct) }}%
          </div>
          <div class="a-sub dim">
            {{ biasLabel }} · banque
            {{ analysis.weighted_avg_bank_drift_pct >= 0 ? 'capte' : 'lâche' }}
            ~{{ formatSigned(Math.abs(analysis.weighted_avg_bank_drift_pct)) }}% du pool par event
          </div>
        </div>

        <div class="analysis-tile">
          <div class="a-k">Bias stock (Δ milk)</div>
          <div class="a-v mono">
            {{ formatSigned(analysis.weighted_avg_delta_milk_pct) }}%
          </div>
          <div class="a-sub dim">
            Volatilité moyenne ±{{ analysis.weighted_avg_abs_delta_pct }}%
          </div>
        </div>

        <div class="analysis-tile">
          <div class="a-k">Projection / jour</div>
          <div class="a-v mono" :class="biasClass">
            {{ formatSigned(projectedDailyDriftPct) }}%
          </div>
          <div class="a-sub dim">
            ≈ {{ formatSigned(projectedHourlyDriftPct) }}% / h
            · {{ analysis.total_templates }} templates · weight {{ analysis.total_weight }}
          </div>
        </div>
      </div>

      <div class="analysis-foot">
        <details>
          <summary class="dim small">
            <span>📊 Détail par template (top drainage en haut)</span>
          </summary>
          <div class="table-wrap" style="margin-top: 0.6em">
            <table class="admin-table tpl-table">
              <thead>
                <tr>
                  <th>Slug</th>
                  <th>Kind</th>
                  <th class="ralign">Poids</th>
                  <th class="ralign">Part du tirage</th>
                  <th class="ralign">Δ moyen milk</th>
                  <th class="ralign">E[banque]</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="t in analysis.per_template" :key="t.id">
                  <td class="mono">{{ t.slug }}</td>
                  <td><span class="kind-pill" :class="t.kind">{{ t.kind }}</span></td>
                  <td class="ralign mono">{{ t.weight }}</td>
                  <td class="ralign mono dim">{{ t.weight_share_pct }}%</td>
                  <td class="ralign mono" :class="signClass(t.avg_delta_milk_pct)">
                    {{ formatSigned(t.avg_delta_milk_pct) }}%
                  </td>
                  <td class="ralign mono" :class="signClass(t.bank_drift_pct)">
                    {{ formatSigned(t.bank_drift_pct) }}%
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </details>
        <p class="dim small explain">
          <b>E[banque]</b> = espérance de <code>sqrt(milk_after/milk_before) - 1</code> :
          combien la banque <em>capterait</em> en CAMP <b>si</b> les holders
          rééquilibraient au prix d'avant le choc (vente après famine, achat
          après overstock). Négatif = drainage.
          <br><br>
          ⚠️ <b>Hypothèse forte</b> : sans volume de trade organique, la
          banque garde exactement son CAMP même après 100 chaos events — les
          réserves ne bougent que sur trade. Ce chiffre est donc un <em>upper
          bound</em> conditionnel au rééquilibrage, pas une rente garantie.
          <br><br>
          Le cap de volatilité (param « Volatilité max » ci-dessus) est
          maintenant pris en compte dans le calcul : un template avec
          un gros range (ex. <code>milking_record [+100, +400 btl]</code>)
          tape en pratique le cap supérieur, pas son centre brut.
          La concavité de sqrt fait que même un catalogue symétrique perd
          légèrement (effet Jensen). Référence pour les templates en
          bouteilles : 200 btl.
        </p>
      </div>
    </section>

    <!-- ─── Pools ─────────────────────────────────────── -->
    <section class="pools-grid">
      <article
        v-for="p in pools"
        :key="p.id"
        class="pool-card"
        :class="p.status"
      >
        <header class="pool-header">
          <div>
            <h3>{{ p.name }} <span class="ticker mono">${{ p.symbol }}</span></h3>
            <div class="meta mono dim">id={{ p.id }} · role={{ p.system_role }}</div>
          </div>
          <span class="status-badge" :class="p.status">{{ p.status }}</span>
        </header>

        <div class="pool-stats">
          <div class="stat">
            <div class="k">Prix</div>
            <div class="v mono">{{ p.price.toFixed(2) }}</div>
            <div class="sub dim">CAMP/btl</div>
          </div>
          <div class="stat">
            <div class="k">Réserve CAMP</div>
            <div class="v mono">{{ formatNum(p.reserve_camp) }}</div>
            <div class="sub dim">x · y = k</div>
          </div>
          <div class="stat">
            <div class="k">Réserve lait</div>
            <div class="v mono">{{ formatNum(p.bottles) }}</div>
            <div class="sub dim">bouteilles</div>
          </div>
          <div class="stat">
            <div class="k">Wallet pool</div>
            <div class="v mono">{{ p.pool_wallet_balance_camp != null ? formatNum(p.pool_wallet_balance_camp) : '—' }}</div>
            <div class="sub dim" v-if="p.pool_wallet_username">{{ p.pool_wallet_username }}</div>
          </div>
        </div>

        <div v-if="walletShortfall(p)" class="alert error small">
          ⚠ Wallet pool ({{ p.pool_wallet_balance_camp }} CAMP) &lt; réserve
          ({{ p.reserve_camp }}). Recharge avant d'activer/laisser tourner.
        </div>

        <div class="pool-actions">
          <label class="inline">
            <span>Frais %</span>
            <input
              type="number"
              step="0.1"
              min="0"
              max="10"
              :value="p.fee_pct"
              @change="updatePool(p, { fee_pct: parseFloat($event.target.value) })"
            />
          </label>

          <label class="inline-toggle">
            <input
              type="checkbox"
              :checked="p.chaos_enabled"
              @change="updatePool(p, { chaos_enabled: $event.target.checked })"
            />
            chaos
          </label>

          <button
            v-if="p.status === 'paused'"
            class="btn-primary btn-sm"
            @click="updatePool(p, { status: 'active' })"
          >
            ▶ Activer
          </button>
          <button
            v-else
            class="btn-ghost btn-sm"
            @click="updatePool(p, { status: 'paused' })"
          >
            ⏸ Pause
          </button>

          <button class="btn-ghost btn-sm" @click="openInjectFor(p)">
            🌪️ Injecter chaos
          </button>
        </div>

        <div class="pool-foot mono dim small">
          📊 {{ p.trades_count }} trades · 🌪️ {{ p.chaos_count }} events chaos
        </div>
      </article>

      <p v-if="!pools.length" class="empty dim">
        Aucun pool. Clique "Créer un pool" pour commencer.
      </p>
    </section>

    <!-- ─── Historique chaos global ───────────────────── -->
    <section v-if="chaosEvents.length" class="recent-section">
      <div class="section-row">
        <h3 class="section-h">🌪️ Derniers événements chaos (tous pools)</h3>
        <span class="dim small">
          {{ chaosEvents.length }} event{{ chaosEvents.length > 1 ? 's' : '' }}
          · page {{ chaosPage }}/{{ chaosTotalPages }}
        </span>
      </div>
      <div class="table-wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Pool</th>
              <th>Type</th>
              <th>Δ bouteilles</th>
              <th>Prix avant → après</th>
              <th>Trigger</th>
              <th>Narrative</th>
              <th>Quand</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in pagedChaosEvents" :key="c.id" :class="c.kind">
              <td class="mono">#{{ c.id }}</td>
              <td class="mono">{{ poolNameById(c.pool_id) }}</td>
              <td>{{ c.kind }}</td>
              <td class="mono" :class="c.delta_milk >= 0 ? 'positive' : 'negative'">
                {{ c.delta_milk >= 0 ? '+' : '' }}{{ formatNum(c.delta_milk / 1000) }}
              </td>
              <td class="mono">
                {{ c.price_before.toFixed(2) }} → {{ c.price_after.toFixed(2) }}
              </td>
              <td>
                <span class="trigger-pill" :class="c.triggered_by">{{ c.triggered_by }}</span>
              </td>
              <td class="narrative-cell">{{ c.narrative }}</td>
              <td class="mono dim">{{ formatShort(c.ts) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="chaosTotalPages > 1" class="pager">
        <button
          class="pager-btn"
          :disabled="chaosPage <= 1"
          @click="chaosPage = Math.max(1, chaosPage - 1)"
        >
          ← Préc.
        </button>
        <span class="pager-info mono dim">
          {{ chaosPage }} / {{ chaosTotalPages }}
        </span>
        <button
          class="pager-btn"
          :disabled="chaosPage >= chaosTotalPages"
          @click="chaosPage = Math.min(chaosTotalPages, chaosPage + 1)"
        >
          Suiv. →
        </button>
      </div>
    </section>

    <!-- ─── Templates chaos ────────────────────────────── -->
    <section class="templates-section">
      <div class="section-head">
        <h3 class="section-h">🎲 Templates d'événements chaos</h3>
        <button class="btn-primary btn-sm" @click="openNewTpl">
          + Nouveau template
        </button>
      </div>
      <p class="dim small section-explain">
        Catalogue tiré au sort par le bot. <b class="mono">weight</b> = poids
        de tirage (plus c'est haut, plus le template revient souvent).
        Placeholders dans la narrative :
        <span class="mono">{pct}</span>, <span class="mono">{abs_pct}</span>,
        <span class="mono">{n}</span>, <span class="mono">{abs_n}</span>.
      </p>

      <div v-if="!templates.length" class="empty dim">
        Aucun template. Lance <span class="mono">migrate_v9_milk_chaos_templates.py</span>
        ou crée-en un manuellement.
      </div>

      <div v-else class="table-wrap">
        <table class="admin-table tpl-table">
          <thead>
            <tr>
              <th>Slug</th>
              <th>Kind</th>
              <th>Δ</th>
              <th>Narrative</th>
              <th class="ralign">Poids</th>
              <th>Actif</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in templates" :key="t.id" :class="{ disabled: !t.enabled }">
              <td class="mono">{{ t.slug }}</td>
              <td>
                <span class="kind-pill" :class="t.kind">{{ t.kind }}</span>
              </td>
              <td class="mono dim small">
                {{ formatRange(t) }}
              </td>
              <td class="narr-cell">
                <em>{{ t.narrative }}</em>
                <div v-if="previewById[t.id]" class="preview-line mono dim small">
                  → {{ previewById[t.id].rendered_narrative }}
                </div>
              </td>
              <td class="ralign mono">{{ t.weight }}</td>
              <td>
                <label class="switch">
                  <input
                    type="checkbox"
                    :checked="t.enabled"
                    @change="toggleTpl(t, $event.target.checked)"
                  />
                  <span></span>
                </label>
              </td>
              <td class="ralign nowrap">
                <button class="btn-ghost btn-xs" @click="previewTpl(t)" title="Aperçu">
                  👁
                </button>
                <button class="btn-ghost btn-xs" @click="openEditTpl(t)">
                  ✎
                </button>
                <button class="btn-ghost btn-xs danger" @click="deleteTpl(t)" title="Supprimer">
                  ✕
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- ─── Modal : Edit/Create template ──────────────── -->
    <div v-if="tplModalOpen" class="modal-backdrop" @click.self="closeTplModal">
      <div class="modal">
        <h3>{{ editingTpl?.id ? 'Modifier' : 'Nouveau' }} template</h3>
        <form @submit.prevent="submitTpl">
          <label class="field">
            <span>Slug <span class="dim">(a-z, 0-9, _)</span></span>
            <input
              v-model="tplForm.slug"
              required
              maxlength="64"
              pattern="^[a-z0-9_]+$"
              :disabled="!!editingTpl?.id"
            />
          </label>
          <div class="row-2">
            <label class="field">
              <span>Type</span>
              <select v-model="tplForm.kind" required>
                <option value="famine">famine (baissier)</option>
                <option value="spoil">spoil (baissier)</option>
                <option value="overstock">overstock (haussier)</option>
                <option value="import">import (haussier)</option>
              </select>
            </label>
            <label class="field">
              <span>Delta unité</span>
              <select v-model="tplForm.delta_type" required>
                <option value="pct">% de la réserve</option>
                <option value="bottles">bouteilles abs.</option>
              </select>
            </label>
          </div>
          <div class="row-2">
            <label class="field">
              <span>Delta min</span>
              <input type="number" step="0.1" v-model.number="tplForm.delta_min" required />
            </label>
            <label class="field">
              <span>Delta max</span>
              <input type="number" step="0.1" v-model.number="tplForm.delta_max" required />
            </label>
          </div>
          <label class="field">
            <span>Narrative (placeholders : {pct}, {abs_pct}, {n}, {abs_n})</span>
            <input v-model="tplForm.narrative" required maxlength="512" />
          </label>
          <div class="row-2">
            <label class="field">
              <span>Poids (tirage)</span>
              <input type="number" min="1" max="100" v-model.number="tplForm.weight" />
            </label>
            <label class="field inline-toggle-field">
              <span>Actif</span>
              <label class="switch">
                <input type="checkbox" v-model="tplForm.enabled" />
                <span></span>
              </label>
            </label>
          </div>

          <div class="info-box dim small">
            Convention de signe : negatif → baisse de stock (prix monte).
            Positif → hausse de stock (prix baisse). Le bot tire un nombre
            aléatoire dans <span class="mono">[min, max]</span> à chaque event.
          </div>

          <div class="modal-actions">
            <button type="button" class="btn-ghost" @click="closeTplModal">Annuler</button>
            <button type="submit" class="btn-primary" :disabled="tplSaving">
              {{ tplSaving ? '…' : (editingTpl?.id ? 'Sauver' : 'Créer') }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- ─── Modal : Create pool ───────────────────────── -->
    <div v-if="openCreate" class="modal-backdrop" @click.self="openCreate = false">
      <div class="modal">
        <h3>Créer un pool laitier</h3>
        <form @submit.prevent="createPool">
          <label class="field">
            <span>Symbole <span class="dim">(ex: LAIT-DEMI)</span></span>
            <input v-model="newPool.symbol" required maxlength="32" />
          </label>
          <label class="field">
            <span>Nom complet</span>
            <input v-model="newPool.name" required maxlength="64" />
          </label>
          <label class="field">
            <span>Bouteilles initiales</span>
            <input v-model.number="newPool.initial_bottles" type="number" min="1" required />
          </label>
          <label class="field">
            <span>Prix initial (CAMP / bouteille)</span>
            <input v-model.number="newPool.price_per_bottle" type="number" min="1" required />
          </label>
          <label class="field">
            <span>Frais (%)</span>
            <input v-model.number="newPool.fee_pct" type="number" step="0.1" min="0" max="10" />
          </label>

          <div class="info-box dim small">
            Le wallet system du pool sera créé automatiquement avec
            <b class="mono">{{ formatNum((newPool.initial_bottles || 0) * (newPool.price_per_bottle || 0)) }}</b>
            CAMP de réserve à amorcer depuis la treasury. Le pool naît en
            <b>pause</b> ; passe-le en active après crédit.
          </div>

          <div class="modal-actions">
            <button type="button" class="btn-ghost" @click="openCreate = false">
              Annuler
            </button>
            <button type="submit" class="btn-primary" :disabled="creating">
              {{ creating ? '…' : 'Créer' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- ─── Modal : Inject chaos ──────────────────────── -->
    <div v-if="injectPool" class="modal-backdrop" @click.self="injectPool = null">
      <div class="modal">
        <h3>Injecter chaos — {{ injectPool.symbol }}</h3>
        <form @submit.prevent="submitInject">
          <label class="field">
            <span>Type</span>
            <select v-model="inject.kind" required>
              <option value="famine">famine (- bouteilles, prix monte)</option>
              <option value="spoil">spoil (- bouteilles, prix monte)</option>
              <option value="overstock">overstock (+ bouteilles, prix baisse)</option>
              <option value="import">import (+ bouteilles, prix baisse)</option>
            </select>
          </label>
          <label class="field">
            <span>Bouteilles <span class="dim">(signé : +50 / -50)</span></span>
            <input v-model.number="inject.bottles" type="number" required />
          </label>
          <label class="field">
            <span>Narrative <span class="dim">(optionnel)</span></span>
            <input v-model="inject.narrative" maxlength="256" placeholder="ex: tempête sur la Beauce…" />
          </label>

          <div class="info-box dim small">
            Cet event sera tagué <b class="mono">triggered_by=admin</b>.
            Aucun mouvement on-chain : on touche uniquement
            <span class="mono">reserve_milk</span>, ce qui crée un choc de prix.
          </div>

          <div class="modal-actions">
            <button type="button" class="btn-ghost" @click="injectPool = null">
              Annuler
            </button>
            <button type="submit" class="btn-primary" :disabled="injecting">
              {{ injecting ? '…' : 'Injecter' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </main>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import AdminTopBar from '@/components/admin/AdminTopBar.vue'
import { useAuthStore } from '@/stores/auth'
import { useOrdersStore } from '@/stores/orders'
import { adminMilkApi } from '@/api/milk'
import { adminSettingsApi } from '@/api/casino'   // wrapper unifie /admin/settings
import { formatNum } from '@/config'

const auth = useAuthStore()
const ordersStore = useOrdersStore()

const pools = ref([])
const chaosEvents = ref([])
const templates = ref([])
const previewById = reactive({})
const freq = reactive({
  milk_chaos_tick_seconds: 900,
  milk_chaos_proba_pct: 25,
  milk_chaos_max_volatility_pct: 20,
})
const editFreq = reactive({
  milk_chaos_tick_seconds: 900,
  milk_chaos_proba_pct: 25,
  milk_chaos_max_volatility_pct: 20,
})
const savingFreq = reactive({
  milk_chaos_tick_seconds: false,
  milk_chaos_proba_pct: false,
  milk_chaos_max_volatility_pct: false,
})

const analysis = ref(null)

// Pagination de l'historique chaos global (10 events/page)
const CHAOS_PAGE_SIZE = 10
const chaosPage = ref(1)
const chaosTotalPages = computed(() =>
  Math.max(1, Math.ceil(chaosEvents.value.length / CHAOS_PAGE_SIZE)),
)
const pagedChaosEvents = computed(() => {
  const start = (chaosPage.value - 1) * CHAOS_PAGE_SIZE
  return chaosEvents.value.slice(start, start + CHAOS_PAGE_SIZE)
})

const loading = ref(false)
const error = ref('')
const successMsg = ref('')

const openCreate = ref(false)
const creating = ref(false)
const newPool = reactive({
  symbol: '',
  name: '',
  initial_bottles: 200,
  price_per_bottle: 50,
  fee_pct: 0.5,
})

const injectPool = ref(null)
const injecting = ref(false)
const inject = reactive({
  kind: 'famine',
  bottles: -100,
  narrative: '',
})

function walletShortfall(p) {
  if (p.pool_wallet_balance_camp == null) return false
  return p.pool_wallet_balance_camp < p.reserve_camp
}

function poolNameById(id) {
  const p = pools.value.find((x) => x.id === id)
  return p ? p.symbol : `pool #${id}`
}

function flash(msg) {
  successMsg.value = msg
  setTimeout(() => { successMsg.value = '' }, 4000)
}

async function loadAll() {
  loading.value = true
  error.value = ''
  try {
    const [pp, cc, tt, settings, ana] = await Promise.all([
      adminMilkApi.pools(auth.adminToken),
      adminMilkApi.chaosHistory(auth.adminToken, { limit: 100 }),
      adminMilkApi.listTemplates(auth.adminToken),
      adminSettingsApi.list(auth.adminToken),
      adminMilkApi.chaosAnalysis(auth.adminToken, 200).catch(() => null),
    ])
    pools.value = pp
    chaosEvents.value = cc
    templates.value = tt
    analysis.value = ana
    // Resync la page courante : si la nouvelle liste est plus courte que
    // l'ancienne (suppression bulk ou refresh), on revient sur une page valide.
    if (chaosPage.value > chaosTotalPages.value) {
      chaosPage.value = chaosTotalPages.value
    }
    // Lit les settings de frequence
    const freqKeys = [
      'milk_chaos_tick_seconds',
      'milk_chaos_proba_pct',
      'milk_chaos_max_volatility_pct',
    ]
    for (const s of settings) {
      if (freqKeys.includes(s.key)) {
        freq[s.key] = Number(s.value)
        editFreq[s.key] = Number(s.value)
      }
    }
    ordersStore.load('all').catch(() => {})
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

// ─── Frequency settings ───────────────────────────────
function canSaveFreq(key) {
  const next = editFreq[key]
  if (next === '' || next == null || Number.isNaN(Number(next))) return false
  return Number(next) !== Number(freq[key])
}

async function saveFreq(key) {
  if (!canSaveFreq(key)) return
  savingFreq[key] = true
  error.value = ''
  try {
    await adminSettingsApi.update(auth.adminToken, key, editFreq[key])
    freq[key] = Number(editFreq[key])
    flash(`Setting ${key} mis à jour`)
  } catch (e) {
    error.value = e.message
  } finally {
    savingFreq[key] = false
  }
}

const tickHuman = computed(() => {
  const s = Number(freq.milk_chaos_tick_seconds) || 0
  if (s < 60) return `${s}s`
  if (s < 3600) return `${Math.round(s / 60)} min`
  return `${(s / 3600).toFixed(1)} h`
})

const enabledTemplatesCount = computed(() =>
  templates.value.filter((t) => t.enabled).length,
)

const estimatedRate = computed(() => {
  const tick = Number(freq.milk_chaos_tick_seconds) || 900
  const proba = Number(freq.milk_chaos_proba_pct) || 0
  const activePools = pools.value.filter(
    (p) => p.status === 'active' && p.chaos_enabled,
  ).length
  if (proba === 0 || activePools === 0) return 'bot désactivé'
  // events / heure attendus = activePools * proba/100 * (3600 / tick)
  const perHour = activePools * (proba / 100) * (3600 / tick)
  if (perHour < 1) {
    const perDay = perHour * 24
    return `~${perDay.toFixed(1)} events/jour`
  }
  return `~${perHour.toFixed(1)} events/h`
})

// ─── Espérance banque ────────────────────────────────
// L'analyse renvoie un drift moyen en % par event. On extrapole sur
// l'heure et la journée en multipliant par events/h estimes.
// NB : un drift de -0.1% par event × 100 events/jour = ~-10% / jour. Avec
// le clamp de volatilite a 20%, les events extremes sont coupes, donc le
// drift par event sera plus faible (~quelques % au pire).
const eventsPerHour = computed(() => {
  const tick = Number(freq.milk_chaos_tick_seconds) || 900
  const proba = Number(freq.milk_chaos_proba_pct) || 0
  const activePools = pools.value.filter(
    (p) => p.status === 'active' && p.chaos_enabled,
  ).length
  if (proba === 0 || activePools === 0) return 0
  return activePools * (proba / 100) * (3600 / tick)
})

const projectedHourlyDriftPct = computed(() => {
  if (!analysis.value) return 0
  return analysis.value.weighted_avg_bank_drift_pct * eventsPerHour.value
})

const projectedDailyDriftPct = computed(() => {
  return projectedHourlyDriftPct.value * 24
})

const biasClass = computed(() => {
  if (!analysis.value) return ''
  const d = analysis.value.weighted_avg_bank_drift_pct
  if (d <= -0.5) return 'drain'
  if (d >= 0.5) return 'gain'
  return 'neutral'
})

const biasLabel = computed(() => {
  if (!analysis.value) return ''
  const d = analysis.value.weighted_avg_bank_drift_pct
  if (d <= -0.5) return 'Drainage'
  if (d >= 0.5) return 'Gain'
  return 'Équilibré'
})

function formatSigned(n) {
  if (n == null || Number.isNaN(Number(n))) return '—'
  const v = Number(n)
  const sign = v > 0 ? '+' : ''
  return `${sign}${v.toFixed(2)}`
}

function signClass(n) {
  if (n == null) return ''
  const v = Number(n)
  if (v < 0) return 'negative'
  if (v > 0) return 'positive'
  return ''
}

// ─── Templates CRUD ───────────────────────────────────
const tplModalOpen = ref(false)
const editingTpl = ref(null)
const tplSaving = ref(false)
const tplForm = reactive({
  slug: '',
  kind: 'famine',
  delta_type: 'pct',
  delta_min: -10,
  delta_max: -3,
  narrative: '',
  weight: 5,
  enabled: true,
})

function openNewTpl() {
  editingTpl.value = null
  tplForm.slug = ''
  tplForm.kind = 'famine'
  tplForm.delta_type = 'pct'
  tplForm.delta_min = -10
  tplForm.delta_max = -3
  tplForm.narrative = 'Petite secheresse, -{abs_pct}% du stock'
  tplForm.weight = 5
  tplForm.enabled = true
  tplModalOpen.value = true
}

function openEditTpl(t) {
  editingTpl.value = t
  tplForm.slug = t.slug
  tplForm.kind = t.kind
  tplForm.delta_type = t.delta_type
  tplForm.delta_min = t.delta_min
  tplForm.delta_max = t.delta_max
  tplForm.narrative = t.narrative
  tplForm.weight = t.weight
  tplForm.enabled = t.enabled
  tplModalOpen.value = true
}

function closeTplModal() {
  tplModalOpen.value = false
  editingTpl.value = null
}

async function submitTpl() {
  tplSaving.value = true
  error.value = ''
  try {
    if (editingTpl.value?.id) {
      // PATCH (slug non modifiable)
      const { slug, ...payload } = tplForm
      await adminMilkApi.updateTemplate(auth.adminToken, editingTpl.value.id, payload)
      flash(`Template ${slug} mis à jour`)
    } else {
      await adminMilkApi.createTemplate(auth.adminToken, { ...tplForm })
      flash(`Template ${tplForm.slug} créé`)
    }
    closeTplModal()
    await loadAll()
  } catch (e) {
    error.value = e.message
  } finally {
    tplSaving.value = false
  }
}

async function toggleTpl(t, enabled) {
  try {
    await adminMilkApi.updateTemplate(auth.adminToken, t.id, { enabled })
    t.enabled = enabled
    flash(`Template ${t.slug} ${enabled ? 'activé' : 'désactivé'}`)
  } catch (e) {
    error.value = e.message
  }
}

async function deleteTpl(t) {
  if (!confirm(`Supprimer le template "${t.slug}" ?`)) return
  try {
    await adminMilkApi.deleteTemplate(auth.adminToken, t.id)
    flash(`Template ${t.slug} supprimé`)
    await loadAll()
  } catch (e) {
    error.value = e.message
  }
}

async function previewTpl(t) {
  try {
    const out = await adminMilkApi.previewTemplate(auth.adminToken, t.id)
    previewById[t.id] = out
    setTimeout(() => { delete previewById[t.id] }, 8000)
  } catch (e) {
    error.value = e.message
  }
}

function formatRange(t) {
  const min = Number(t.delta_min)
  const max = Number(t.delta_max)
  const unit = t.delta_type === 'pct' ? '%' : ' btl'
  return `[${min}${unit}, ${max}${unit}]`
}

async function updatePool(p, payload) {
  try {
    const out = await adminMilkApi.updatePool(auth.adminToken, p.id, payload)
    Object.assign(p, out)
    flash(`Pool ${p.symbol} mis à jour`)
    await loadAll()
  } catch (e) {
    error.value = e.message
  }
}

async function createPool() {
  creating.value = true
  error.value = ''
  try {
    const out = await adminMilkApi.createPool(auth.adminToken, { ...newPool })
    flash(`Pool ${out.symbol} créé. ${out.next_step || ''}`)
    openCreate.value = false
    newPool.symbol = ''
    newPool.name = ''
    newPool.initial_bottles = 200
    newPool.price_per_bottle = 50
    newPool.fee_pct = 0.5
    await loadAll()
  } catch (e) {
    error.value = e.message
  } finally {
    creating.value = false
  }
}

function openInjectFor(p) {
  injectPool.value = p
  inject.kind = 'famine'
  inject.bottles = -100
  inject.narrative = ''
}

async function submitInject() {
  if (!injectPool.value) return
  injecting.value = true
  error.value = ''
  try {
    await adminMilkApi.injectChaos(auth.adminToken, injectPool.value.id, {
      kind: inject.kind,
      bottles: inject.bottles,
      narrative: inject.narrative || null,
    })
    flash(`Chaos ${inject.kind} injecté sur ${injectPool.value.symbol}`)
    injectPool.value = null
    await loadAll()
  } catch (e) {
    error.value = e.message
  } finally {
    injecting.value = false
  }
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
.small { font-size: 0.82em; }
.positive { color: var(--green, #14e08e); }
.negative { color: var(--red); }

.toolbar {
  display: flex;
  gap: 0.6em;
  margin-bottom: 1.2em;
  align-items: center;
}

/* ─── Pool cards ──────────────────────── */
.pools-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 1em;
  margin-bottom: 2em;
}
.pool-card {
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.2em 1.3em;
  display: flex;
  flex-direction: column;
  gap: 0.8em;
}
.pool-card.paused { opacity: 0.85; }

.pool-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}
.pool-header h3 {
  font-size: 1.05em;
  margin: 0;
}
.pool-header .ticker {
  color: var(--text-3);
  font-size: 0.85em;
  margin-left: 0.4em;
}
.pool-header .meta {
  font-size: 0.75em;
  margin-top: 0.15em;
}
.status-badge {
  font-size: 0.7em;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 0.2em 0.55em;
  border-radius: 999px;
}
.status-badge.active { background: rgba(20, 224, 142, 0.15); color: #14e08e; }
.status-badge.paused { background: var(--bg-3); color: var(--text-3); }

.pool-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.5em;
  background: var(--bg-2);
  border-radius: var(--radius-sm);
  padding: 0.7em 0.6em;
}
.pool-stats .stat {
  text-align: center;
}
.pool-stats .k {
  font-size: 0.7em;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-3);
}
.pool-stats .v {
  font-size: 0.95em;
  font-weight: 700;
  margin-top: 0.2em;
}
.pool-stats .sub {
  font-size: 0.72em;
  margin-top: 0.1em;
}

.alert.small { font-size: 0.82em; padding: 0.5em 0.7em; margin: 0; }

.pool-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5em;
  align-items: center;
}
.inline {
  display: flex;
  align-items: center;
  gap: 0.4em;
  font-size: 0.85em;
  color: var(--text-2);
}
.inline input {
  width: 80px;
  padding: 0.35em 0.5em;
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-0);
  font-family: 'JetBrains Mono', monospace;
}
.inline-toggle {
  display: flex;
  align-items: center;
  gap: 0.3em;
  font-size: 0.85em;
  color: var(--text-2);
  cursor: pointer;
}

.pool-foot { margin-top: auto; }

.empty {
  text-align: center;
  padding: 2em;
  grid-column: 1 / -1;
}

/* ─── Chaos history ───────────────────── */
.section-h {
  margin: 1.5em 0 0.8em;
  font-size: 1.05em;
  padding-top: 1em;
  border-top: 1px dashed var(--border);
}
.section-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 0.5em;
}
.section-row .section-h {
  margin: 1.5em 0 0.5em;
}

/* Pagination */
.pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.8em;
  margin-top: 0.8em;
}
.pager-btn {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-1);
  padding: 0.45em 0.9em;
  font-size: 0.85em;
  cursor: pointer;
  min-width: 88px;
}
.pager-btn:hover:not(:disabled) {
  border-color: var(--border-strong);
  color: var(--text-0);
}
.pager-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.pager-info {
  min-width: 60px;
  text-align: center;
  font-size: 0.85em;
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
.narrative-cell { font-style: italic; color: var(--text-1); }

.trigger-pill {
  display: inline-block;
  font-size: 0.72em;
  font-weight: 700;
  letter-spacing: 0.04em;
  padding: 0.18em 0.55em;
  border-radius: 999px;
  text-transform: uppercase;
}
.trigger-pill.admin { background: var(--camp-soft); color: var(--camp); }
.trigger-pill.bot { background: var(--bg-3); color: var(--text-2); }

/* ─── Modal ───────────────────────────── */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(6px);
  display: grid;
  place-items: center;
  z-index: 60;
  padding: 1em;
}
.modal {
  background: var(--bg-1);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius);
  padding: 1.4em;
  width: 100%;
  max-width: 420px;
  box-shadow: 0 20px 60px -20px rgba(0, 0, 0, 0.8);
}
.modal h3 { font-size: 1.1em; margin-bottom: 1em; }
.field {
  display: flex;
  flex-direction: column;
  gap: 0.3em;
  margin-bottom: 0.9em;
  font-size: 0.88em;
  color: var(--text-2);
}
.field input,
.field select {
  padding: 0.55em 0.7em;
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-0);
  font-family: 'JetBrains Mono', monospace;
}
.info-box {
  background: var(--bg-2);
  border: 1px dashed var(--border);
  border-radius: var(--radius-sm);
  padding: 0.7em 0.9em;
  margin: 0.5em 0 0.8em;
  line-height: 1.5;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.6em;
}

/* ─── Chaos frequency card ────────────────── */
.chaos-freq-card {
  background:
    radial-gradient(circle at 90% 10%, rgba(255, 69, 102, 0.06), transparent 60%),
    var(--bg-1);
  margin-bottom: 1.5em;
  padding: 1.2em 1.3em;
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 0.5em;
  margin-bottom: 1em;
}
.card-title { font-size: 1.05em; margin: 0; }

.freq-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 1em;
}
.freq-tile {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 1em 1.05em;
}
.freq-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 0.5em;
}
.freq-k {
  font-size: 0.75em;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-2);
}
.freq-v {
  font-size: 1.2em;
  font-weight: 700;
  color: var(--camp);
}
.freq-desc {
  color: var(--text-2);
  font-size: 0.82em;
  line-height: 1.5;
  margin: 0 0 0.7em 0;
}
.freq-edit {
  display: flex;
  gap: 0.4em;
}
.freq-edit input {
  flex: 1;
  padding: 0.4em 0.6em;
  background: var(--bg-3);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-0);
  font-family: 'JetBrains Mono', monospace;
}
.stats-tile { background: var(--bg-1); border-style: dashed; }
.stats-tile .freq-v { color: var(--text-0); font-size: 1.05em; }

/* ─── Espérance banque ───────────────────── */
.analysis-card {
  background:
    radial-gradient(circle at 10% 10%, rgba(20, 224, 142, 0.05), transparent 60%),
    var(--bg-1);
  margin-bottom: 1.5em;
  padding: 1.2em 1.3em;
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.analysis-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0.8em;
  margin-bottom: 0.9em;
}
.analysis-tile {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0.9em 1em;
}
.analysis-tile .a-k {
  font-size: 0.72em;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-2);
  font-weight: 700;
  margin-bottom: 0.3em;
}
.analysis-tile .a-v {
  font-size: 1.6em;
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1;
}
.analysis-tile .a-sub {
  font-size: 0.78em;
  margin-top: 0.4em;
  line-height: 1.4;
}
.analysis-tile.drain { border-color: rgba(255, 69, 102, 0.4); }
.analysis-tile.drain .a-v { color: #ff4566; }
.analysis-tile.gain { border-color: rgba(20, 224, 142, 0.4); }
.analysis-tile.gain .a-v { color: #14e08e; }
.analysis-tile.neutral .a-v { color: var(--text-0); }
.analysis-foot details > summary {
  list-style: none;
  cursor: pointer;
  padding: 0.5em 0;
  user-select: none;
  font-size: 0.85em;
}
.analysis-foot details > summary::-webkit-details-marker { display: none; }
.analysis-foot details > summary:hover { color: var(--text-0); }
.analysis-foot .explain {
  margin: 0.7em 0 0 0;
  line-height: 1.5;
}
.analysis-foot .explain code {
  background: var(--bg-2);
  padding: 0.1em 0.3em;
  border-radius: 3px;
  font-size: 0.92em;
}

/* ─── Templates table ─────────────────────── */
.templates-section { margin-top: 0.5em; }
.section-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 0.5em;
}
.section-explain { margin: 0 0 0.9em 0; line-height: 1.5; }

.tpl-table { font-size: 0.85em; }
.tpl-table tbody tr.disabled { opacity: 0.55; }
.tpl-table .narr-cell {
  max-width: 320px;
  font-style: italic;
  color: var(--text-1);
}
.tpl-table .nowrap { white-space: nowrap; }
.tpl-table .preview-line {
  margin-top: 0.3em;
  padding: 0.3em 0.5em;
  background: var(--bg-2);
  border-left: 2px solid var(--camp);
  border-radius: 3px;
  font-style: normal;
}

.kind-pill {
  display: inline-block;
  font-size: 0.7em;
  font-weight: 700;
  letter-spacing: 0.04em;
  padding: 0.2em 0.55em;
  border-radius: 999px;
  text-transform: uppercase;
}
.kind-pill.famine,
.kind-pill.spoil { background: rgba(255, 69, 102, 0.15); color: #ff4566; }
.kind-pill.overstock,
.kind-pill.import { background: rgba(20, 224, 142, 0.15); color: #14e08e; }

.btn-xs {
  padding: 0.25em 0.5em;
  font-size: 0.9em;
  margin-left: 0.15em;
}
.btn-xs.danger:hover { color: var(--red); }

.switch {
  display: inline-block;
  position: relative;
  width: 36px;
  height: 20px;
  cursor: pointer;
}
.switch input { opacity: 0; width: 0; height: 0; position: absolute; }
.switch span {
  position: absolute;
  inset: 0;
  background: var(--bg-3);
  border-radius: 999px;
  border: 1px solid var(--border);
  transition: background 0.15s;
}
.switch span::before {
  content: '';
  position: absolute;
  width: 14px;
  height: 14px;
  left: 2px;
  top: 2px;
  background: var(--text-2);
  border-radius: 50%;
  transition: transform 0.15s, background 0.15s;
}
.switch input:checked + span { background: rgba(20, 224, 142, 0.2); border-color: #14e08e; }
.switch input:checked + span::before { transform: translateX(16px); background: #14e08e; }

.inline-toggle-field {
  flex-direction: row;
  align-items: center;
  gap: 0.6em;
}
.inline-toggle-field span:first-child { flex: 1; }

.row-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.6em;
}

@media (max-width: 640px) {
  .pool-stats { grid-template-columns: repeat(2, 1fr); }
  .tpl-table { font-size: 0.78em; }
  .row-2 { grid-template-columns: 1fr; }
}
</style>
