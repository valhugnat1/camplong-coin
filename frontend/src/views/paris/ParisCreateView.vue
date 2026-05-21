<template>
  <AppLayout>
    <main class="page fade-in narrow">
      <div class="page-header">
        <div>
          <h1 class="page-title">Nouveau pari</h1>
          <p class="page-sub">
            Énonce-le. Mise. Trouve quelqu'un d'assez bête pour matcher.
          </p>
        </div>
      </div>

      <form class="bet-form" @submit.prevent="submit">
        <!-- ─── Affirmation ────────────────────────────── -->
        <section class="card">
          <label class="field">
            <span class="field-label">Affirmation</span>
            <textarea
              v-model="form.statement"
              rows="2"
              placeholder='Ex : "Emile va dire la phrase secrète avant samedi"'
              maxlength="512"
              required
            />
            <span class="field-hint mono">{{ form.statement.length }}/512</span>
          </label>

          <div class="field-row">
            <label class="field">
              <span class="field-label">Catégorie</span>
              <select v-model="form.category">
                <option value="">— Aucune —</option>
                <option v-for="c in CATEGORIES" :key="c" :value="c">
                  {{ c }}
                </option>
              </select>
            </label>

            <label class="field">
              <span class="field-label">Deadline</span>
              <input
                type="datetime-local"
                v-model="form.deadline"
                :min="minDeadline"
                required
              />
              <div class="quick-deadlines mono">
                <button type="button" @click="setDeadline(1)">+1h</button>
                <button type="button" @click="setDeadline(24)">+1j</button>
                <button type="button" @click="setDeadline(24 * 7)">
                  +1sem
                </button>
                <button type="button" @click="setDeadline(24 * 30)">
                  +1mois
                </button>
              </div>
            </label>
          </div>
        </section>

        <!-- ─── Ma position ────────────────────────────── -->
        <section class="card">
          <div class="section-title">Ma position</div>

          <div class="side-toggle">
            <button
              type="button"
              class="side-opt yes"
              :class="{ active: form.creator_side === 'yes' }"
              @click="form.creator_side = 'yes'"
            >
              <span class="side-opt-label">Je parie que c'est</span>
              <span class="side-opt-value">VRAI</span>
            </button>
            <button
              type="button"
              class="side-opt no"
              :class="{ active: form.creator_side === 'no' }"
              @click="form.creator_side = 'no'"
            >
              <span class="side-opt-label">Je parie que c'est</span>
              <span class="side-opt-value">FAUX</span>
            </button>
          </div>

          <label class="field">
            <span class="field-label">Ma mise (CAMP)</span>
            <input
              type="number"
              v-model.number="form.stake_creator"
              :min="MIN_STAKE"
              :max="MAX_STAKE"
              step="1"
              required
            />
            <div class="quick-amounts mono">
              <button
                type="button"
                v-for="a in QUICK_AMOUNTS"
                :key="a"
                @click="form.stake_creator = a"
              >
                {{ a }}
              </button>
              <button type="button" @click="form.stake_creator = maxAffordable">
                Max ({{ formatNum(maxAffordable) }})
              </button>
            </div>
            <span v-if="walletBalance != null" class="field-hint mono">
              Solde : {{ formatNum(walletBalance) }} CAMP
            </span>
          </label>
        </section>

        <!-- ─── Cote ────────────────────────────────────── -->
        <section class="card">
          <div class="section-title">Cote</div>
          <p class="hint">
            Pour 1 CAMP que tu mises, l'adversaire doit miser
            <b class="mono">{{ ratioStr }}</b> CAMP.
          </p>

          <div class="cote-presets mono">
            <button
              type="button"
              v-for="p in PRESETS"
              :key="p.label"
              class="preset"
              :class="{
                active: form.odds_num === p.num && form.odds_den === p.den,
              }"
              @click="setOdds(p.num, p.den)"
            >
              {{ p.label }}
            </button>
            <button
              type="button"
              class="preset"
              :class="{ active: customMode }"
              @click="customMode = !customMode"
            >
              Custom
            </button>
          </div>

          <div v-if="customMode" class="custom-cote">
            <label class="field">
              <span class="field-label">Toi (num)</span>
              <input
                type="number"
                v-model.number="form.odds_num"
                min="1"
                max="100"
              />
            </label>
            <span class="cote-sep">:</span>
            <label class="field">
              <span class="field-label">Adversaire (den)</span>
              <input
                type="number"
                v-model.number="form.odds_den"
                min="1"
                max="100"
              />
            </label>
          </div>
        </section>

        <!-- ─── Arbitre (optionnel) ─────────────────────── -->
        <section class="card">
          <div class="section-title">
            Arbitre
            <span class="optional">optionnel</span>
          </div>
          <p class="hint">
            Désigne un pote pour trancher si le résultat est ambigu. Sinon,
            c'est moi (Hugo) qui tranche.
          </p>

          <div class="field-row">
            <label class="field">
              <span class="field-label">Qui</span>
              <select v-model="form.arbiter_username">
                <option :value="null">— Personne (admin tranche) —</option>
                <option
                  v-for="u in eligibleArbiters"
                  :key="u.username"
                  :value="u.username"
                >
                  {{ u.username }}
                </option>
              </select>
            </label>

            <label class="field" v-if="form.arbiter_username">
              <span class="field-label">Commission</span>
              <div class="fee-input">
                <input
                  type="number"
                  v-model.number="form.arbiter_fee_pct"
                  min="0"
                  max="50"
                  step="1"
                />
                <span class="mono">%</span>
              </div>
            </label>
          </div>
        </section>

        <!-- ─── Récap ──────────────────────────────────── -->
        <section class="recap" :class="{ invalid: !isValid }">
          <h3>En clair</h3>
          <div class="recap-grid">
            <div class="recap-row">
              <span>Ta mise</span>
              <b class="mono">{{ formatNum(form.stake_creator) }} CAMP</b>
            </div>
            <div class="recap-row">
              <span>Mise adverse requise</span>
              <b class="mono">{{ formatNum(opponentStake) }} CAMP</b>
            </div>
            <div class="recap-row">
              <span>Pot total</span>
              <b class="mono">{{ formatNum(pot) }} CAMP</b>
            </div>
            <div class="recap-row gain">
              <span>Si tu gagnes</span>
              <b class="mono">+{{ formatNum(winnerGain) }} CAMP</b>
            </div>
            <div
              v-if="form.arbiter_username && form.arbiter_fee_pct > 0"
              class="recap-row"
            >
              <span>Commission arbitre</span>
              <b class="mono">{{ formatNum(arbiterFee) }} CAMP</b>
            </div>
          </div>
        </section>

        <!-- ─── Erreurs ─────────────────────────────────── -->
        <div v-if="validationErrors.length" class="alert error">
          <ul>
            <li v-for="(e, i) in validationErrors" :key="i">{{ e }}</li>
          </ul>
        </div>

        <div v-if="apiError" class="alert error">{{ apiError }}</div>

        <!-- ─── Actions ─────────────────────────────────── -->
        <div class="actions">
          <button
            type="button"
            class="btn-ghost"
            @click="router.push({ name: 'paris-list' })"
          >
            Annuler
          </button>
          <button
            type="submit"
            class="btn-primary"
            :disabled="!isValid || submitting"
          >
            {{
              submitting ? "Création..." : "Créer le pari & bloquer mes CAMP"
            }}
          </button>
        </div>
      </form>
    </main>
  </AppLayout>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { storeToRefs } from "pinia";
import AppLayout from "@/components/layout/AppLayout.vue";
import { useAuthStore } from "@/stores/auth";
import { useWalletStore } from "@/stores/wallet";
import { useBetsStore } from "@/stores/bets";
import { apiCall } from "@/api/client";
import { formatNum } from "@/config";

const router = useRouter();
const auth = useAuthStore();
const wallet = useWalletStore();
const betsStore = useBetsStore();

// Acces tolerant au solde wallet : on essaie plusieurs noms de champ
// possibles selon comment le store wallet est implemente. A remplacer
// par un acces direct si tu connais le bon nom.
const walletBalance = computed(() => {
  const w = wallet;
  return Number(w?.balance ?? w?.campBalance ?? w?.balance_camp ?? 0);
});

// ─── Constantes UI ──────────────────────────────────────
const MIN_STAKE = 1;
const MAX_STAKE = 1000;

const CATEGORIES = [
  "Sport",
  "Pro",
  "Crypto",
  "Lifestyle",
  "Tech",
  "Météo",
  "Politique",
  "Bullshit",
  "Autre",
];

const QUICK_AMOUNTS = [10, 25, 50, 100, 250];

const PRESETS = [
  { label: "1:1", num: 1, den: 1 }, // 50/50
  { label: "1:2", num: 1, den: 2 }, // toi favori 2x
  { label: "1:3", num: 1, den: 3 }, // toi favori 3x
  { label: "1:5", num: 1, den: 5 }, // toi favori 5x
  { label: "2:1", num: 2, den: 1 }, // adversaire favori 2x
  { label: "3:1", num: 3, den: 1 }, // adversaire favori 3x
];

// ─── État du formulaire ────────────────────────────────
const form = reactive({
  statement: "",
  category: "",
  deadline: "",
  creator_side: "yes",
  stake_creator: 20,
  odds_num: 1,
  odds_den: 1,
  arbiter_username: null,
  arbiter_fee_pct: 5,
});

const customMode = ref(false);
const submitting = ref(false);
const apiError = ref("");
const eligibleArbiters = ref([]);

// ─── Calculs dérivés ───────────────────────────────────
const opponentStake = computed(() => {
  if (!form.stake_creator || !form.odds_num || !form.odds_den) return 0;
  return (form.stake_creator * form.odds_den) / form.odds_num;
});

const pot = computed(() => form.stake_creator + opponentStake.value);

const arbiterFee = computed(() => {
  if (!form.arbiter_username || !form.arbiter_fee_pct) return 0;
  return Math.floor((pot.value * form.arbiter_fee_pct) / 100);
});

const winnerGain = computed(() => opponentStake.value - arbiterFee.value);

const ratioStr = computed(() => {
  if (form.odds_num === 1) return form.odds_den.toString();
  return (form.odds_den / form.odds_num).toFixed(2);
});

const maxAffordable = computed(() =>
  Math.min(MAX_STAKE, Math.floor(walletBalance.value || 0)),
);

const minDeadline = computed(() => {
  const d = new Date(Date.now() + 5 * 60 * 1000);
  return d.toISOString().slice(0, 16);
});

// ─── Validation ────────────────────────────────────────
const validationErrors = computed(() => {
  const errs = [];
  if (!form.statement.trim()) errs.push("L'affirmation est obligatoire");
  if (form.statement.length > 512) errs.push("Trop long, max 512 caractères");
  if (!form.deadline) errs.push("Deadline obligatoire");
  else if (new Date(form.deadline) < new Date())
    errs.push("La deadline est déjà passée");

  if (!form.stake_creator || form.stake_creator < MIN_STAKE)
    errs.push(`Mise minimum : ${MIN_STAKE} CAMP`);
  if (form.stake_creator > MAX_STAKE)
    errs.push(`Mise maximum : ${MAX_STAKE} CAMP`);
  if (form.stake_creator > (walletBalance.value || 0))
    errs.push(`Solde insuffisant (${formatNum(walletBalance.value)} CAMP)`);

  if (
    !form.odds_num ||
    !form.odds_den ||
    form.odds_num < 1 ||
    form.odds_den < 1
  )
    errs.push("Cote invalide");
  else if (!Number.isInteger(opponentStake.value))
    errs.push(
      `Cette cote produit une mise fractionnaire (${opponentStake.value} CAMP). Ajuste.`,
    );

  if (form.arbiter_fee_pct < 0 || form.arbiter_fee_pct > 50)
    errs.push("Commission arbitre entre 0 et 50%");

  return errs;
});

const isValid = computed(() => validationErrors.value.length === 0);

// ─── Helpers ───────────────────────────────────────────
function setOdds(num, den) {
  form.odds_num = num;
  form.odds_den = den;
  customMode.value = false;
}

function setDeadline(hoursFromNow) {
  const d = new Date(Date.now() + hoursFromNow * 60 * 60 * 1000);
  // Format pour datetime-local : YYYY-MM-DDTHH:mm
  const pad = (n) => n.toString().padStart(2, "0");
  form.deadline = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

// ─── Submit ────────────────────────────────────────────
async function submit() {
  if (!isValid.value) return;
  submitting.value = true;
  apiError.value = "";
  try {
    const payload = {
      statement: form.statement.trim(),
      category: form.category || null,
      deadline: new Date(form.deadline).toISOString(),
      creator_side: form.creator_side,
      stake_creator: form.stake_creator,
      odds_num: form.odds_num,
      odds_den: form.odds_den,
      arbiter_username: form.arbiter_username,
      arbiter_fee_pct: form.arbiter_username ? form.arbiter_fee_pct : 0,
    };
    const bet = await betsStore.create(payload);
    router.push({ name: "paris-detail", params: { id: bet.id } });
  } catch (e) {
    apiError.value = e.message;
  } finally {
    submitting.value = false;
  }
}

// ─── Init ──────────────────────────────────────────────
onMounted(async () => {
  setDeadline(24 * 7); // défaut : dans 1 semaine
  // Annuaire pour le select arbitre
  try {
    const users = await apiCall("/users", { token: auth.userToken });
    eligibleArbiters.value = users.filter((u) => u.username !== auth.username);
  } catch (e) {
    // pas bloquant
  }
  // Rafraîchir le solde affiché (best-effort, on essaie plusieurs methodes possibles)
  try {
    if (typeof wallet.refresh === "function") await wallet.refresh();
    else if (typeof wallet.load === "function") await wallet.load();
    else if (typeof wallet.fetch === "function") await wallet.fetch();
  } catch (e) {
    // pas bloquant
  }
});
</script>

<style scoped>
.narrow {
  max-width: 720px;
  margin: 0 auto;
}

.bet-form {
  display: flex;
  flex-direction: column;
  gap: 1em;
}

.card {
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.3em;
}

.section-title {
  font-size: 0.78em;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--text-2);
  margin-bottom: 0.9em;
  display: flex;
  align-items: center;
  gap: 0.8em;
}
.optional {
  font-size: 0.85em;
  font-weight: 500;
  text-transform: none;
  letter-spacing: 0;
  color: var(--text-3);
  font-style: italic;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.4em;
  margin-bottom: 0.9em;
}
.field:last-child {
  margin-bottom: 0;
}
.field-label {
  font-size: 0.82em;
  font-weight: 600;
  color: var(--text-1);
}
.field-hint {
  font-size: 0.72em;
  color: var(--text-3);
  align-self: flex-end;
}

.field-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.9em;
}

textarea,
input[type="number"],
input[type="datetime-local"],
select {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0.65em 0.8em;
  font-size: 0.95em;
  color: var(--text-0);
  font-family: inherit;
}
textarea {
  resize: vertical;
  min-height: 3.5em;
}
input:focus,
textarea:focus,
select:focus {
  outline: none;
  border-color: var(--violet);
}

.quick-amounts,
.quick-deadlines {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3em;
  margin-top: 0.3em;
}
.quick-amounts button,
.quick-deadlines button {
  background: var(--bg-2);
  border: 1px solid var(--border);
  padding: 0.3em 0.7em;
  border-radius: var(--radius-sm);
  font-size: 0.78em;
  color: var(--text-1);
  cursor: pointer;
  transition: all 0.15s;
}
.quick-amounts button:hover,
.quick-deadlines button:hover {
  border-color: var(--violet);
  color: var(--text-0);
}

.side-toggle {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.5em;
  margin-bottom: 1em;
}
.side-opt {
  background: var(--bg-2);
  border: 2px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 1em;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.3em;
  transition: all 0.15s;
}
.side-opt-label {
  font-size: 0.75em;
  color: var(--text-2);
}
.side-opt-value {
  font-size: 1.4em;
  font-weight: 800;
  letter-spacing: 0.05em;
}
.side-opt.yes:hover,
.side-opt.yes.active {
  border-color: var(--green);
  background: rgba(20, 224, 142, 0.08);
}
.side-opt.yes.active .side-opt-value {
  color: var(--green);
}

.side-opt.no:hover,
.side-opt.no.active {
  border-color: var(--red);
  background: rgba(255, 69, 102, 0.08);
}
.side-opt.no.active .side-opt-value {
  color: var(--red);
}

.cote-presets {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4em;
  margin-bottom: 0.9em;
}
.preset {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0.5em 1em;
  font-weight: 700;
  font-size: 0.9em;
  color: var(--text-1);
  cursor: pointer;
  min-width: 4em;
  transition: all 0.15s;
}
.preset:hover {
  border-color: var(--border-strong);
  color: var(--text-0);
}
.preset.active {
  background: var(--violet);
  border-color: var(--violet);
  color: white;
}

.custom-cote {
  display: flex;
  align-items: flex-end;
  gap: 0.7em;
}
.custom-cote .field {
  flex: 1;
  margin-bottom: 0;
}
.cote-sep {
  font-size: 1.5em;
  font-weight: 700;
  color: var(--text-2);
  padding-bottom: 0.5em;
}

.fee-input {
  display: flex;
  align-items: center;
  gap: 0.3em;
}
.fee-input input {
  flex: 1;
}

.hint {
  color: var(--text-2);
  font-size: 0.88em;
  margin-bottom: 0.8em;
}

.recap {
  background: var(--bg-1);
  border: 1px solid var(--violet);
  border-radius: var(--radius);
  padding: 1.2em 1.3em;
  box-shadow: 0 0 0 3px rgba(154, 78, 255, 0.08);
}
.recap.invalid {
  border-color: var(--border);
  box-shadow: none;
  opacity: 0.6;
}
.recap h3 {
  font-size: 0.78em;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--violet);
  margin-bottom: 0.8em;
}
.recap-grid {
  display: flex;
  flex-direction: column;
  gap: 0.45em;
}
.recap-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.3em 0;
  border-bottom: 1px dashed var(--border);
}
.recap-row:last-child {
  border-bottom: none;
}
.recap-row.gain {
  color: var(--green);
  font-size: 1.05em;
  padding-top: 0.6em;
  border-top: 1px solid var(--border);
}

.alert.error {
  background: rgba(255, 69, 102, 0.1);
  border: 1px solid var(--red);
  border-radius: var(--radius-sm);
  padding: 0.8em 1em;
  color: var(--red);
  font-size: 0.9em;
}
.alert.error ul {
  margin: 0;
  padding-left: 1.2em;
}

.actions {
  display: flex;
  gap: 0.6em;
  justify-content: flex-end;
}

@media (max-width: 640px) {
  .field-row {
    grid-template-columns: 1fr;
  }
  .side-toggle {
    grid-template-columns: 1fr 1fr;
  }
  .actions {
    flex-direction: column-reverse;
  }
  .actions button {
    width: 100%;
  }
}
</style>
