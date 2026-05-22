<template>
  <AppLayout>
    <main class="page fade-in narrow">
      <div class="page-header">
        <button class="back-link" @click="router.push({ name: 'paris-list' })">
          ← Paris
        </button>
        <h1 class="page-title">Nouveau pari</h1>
        <p class="page-sub">
          Pose ton affirmation, fixe la mise, laisse les potes choisir leur camp.
        </p>
      </div>

      <form class="bet-form" @submit.prevent="submit">
        <!-- ─── Affirmation + deadline ──────────────────── -->
        <section class="card">
          <label class="field">
            <span class="field-label">Affirmation</span>
            <textarea
              v-model="form.statement"
              rows="2"
              placeholder='Ex: "Emile sera en retard à la raclette de samedi"'
              maxlength="512"
              required
            />
            <span class="field-hint mono">{{ form.statement.length }}/512</span>
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
              <button type="button" @click="setDeadline(24 * 7)">+1sem</button>
              <button type="button" @click="setDeadline(24 * 30)">+1mois</button>
            </div>
          </label>
        </section>

        <!-- ─── Format (yes/no ou multi) ────────────────── -->
        <section class="card">
          <div class="section-title">Format</div>
          <div class="format-toggle">
            <button
              type="button"
              class="format-opt"
              :class="{ active: form.type === 'yes_no' }"
              @click="setType('yes_no')"
            >
              <span class="format-label">Oui / Non</span>
              <span class="format-sub">2 options classiques</span>
            </button>
            <button
              type="button"
              class="format-opt"
              :class="{ active: form.type === 'multi_choice' }"
              @click="setType('multi_choice')"
            >
              <span class="format-label">Choix multiples</span>
              <span class="format-sub">2 à 6 options custom</span>
            </button>
          </div>

          <div v-if="form.type === 'multi_choice'" class="options-builder">
            <span class="field-label">Tes options</span>
            <div
              v-for="(opt, i) in form.options"
              :key="i"
              class="option-row"
            >
              <span class="opt-num mono">{{ i + 1 }}.</span>
              <input
                type="text"
                v-model="form.options[i]"
                maxlength="64"
                :placeholder="`Option ${i + 1}`"
              />
              <button
                v-if="form.options.length > 2"
                type="button"
                class="opt-remove"
                @click="removeOption(i)"
                aria-label="Retirer"
              >
                ✕
              </button>
            </div>
            <button
              type="button"
              class="btn-ghost btn-add-opt"
              v-if="form.options.length < BETS.maxOptions"
              @click="addOption"
            >
              + Ajouter une option ({{ form.options.length }}/{{
                BETS.maxOptions
              }})
            </button>
          </div>
        </section>

        <!-- ─── Mise unique ─────────────────────────────── -->
        <section class="card">
          <div class="section-title">Mise unique</div>
          <p class="hint">
            Tout le monde mise pareil pour participer. Le pot total est partagé
            entre les gagnants à la fin. Tu pourras toi aussi rejoindre une
            option après création.
          </p>
          <label class="field">
            <input
              type="number"
              v-model.number="form.stake"
              :min="BETS.minStake"
              :max="BETS.maxStake"
              step="1"
              required
            />
            <div class="quick-amounts mono">
              <button
                type="button"
                v-for="a in QUICK_AMOUNTS"
                :key="a"
                @click="form.stake = a"
              >
                {{ a }}
              </button>
            </div>
            <span v-if="walletBalance != null" class="field-hint mono">
              Solde : {{ formatNum(walletBalance) }} CAMP
            </span>
          </label>
        </section>

        <!-- ─── Arbitre (optionnel) ─────────────────────── -->
        <section class="card">
          <div class="section-title">
            Arbitre
            <span class="optional">optionnel</span>
          </div>
          <p class="hint">
            Sans arbitre : 2 votes communautaires concordants résolvent le
            pari. Avec arbitre : il tranche tout seul (et ne peut pas
            participer).
          </p>
          <label class="field">
            <select v-model="form.arbiter_username">
              <option :value="null">— Personne (vote communautaire) —</option>
              <option
                v-for="u in eligibleArbiters"
                :key="u.username"
                :value="u.username"
              >
                {{ u.username }}
              </option>
            </select>
          </label>
        </section>

        <!-- ─── Récap ──────────────────────────────────── -->
        <section class="recap" :class="{ invalid: !isValid }">
          <h3>En clair</h3>
          <div class="recap-grid">
            <div class="recap-row">
              <span>Mise par participant</span>
              <b class="mono">{{ formatNum(form.stake) }} CAMP</b>
            </div>
            <div class="recap-row">
              <span>Options</span>
              <b>{{ optionLabels.join(" · ") }}</b>
            </div>
            <div class="recap-row">
              <span>Résolution</span>
              <b>
                {{
                  form.arbiter_username
                    ? `Arbitre: ${form.arbiter_username}`
                    : "Vote communautaire (2 voix)"
                }}
              </b>
            </div>
            <div class="recap-row hint-row">
              <span class="dim">Étape suivante</span>
              <b class="hint-text">Tu pourras y miser après création</b>
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

        <!-- ─── Actions (sticky bottom on mobile) ───────── -->
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
            {{ submitting ? "Création..." : "Créer le pari" }}
          </button>
        </div>
      </form>
    </main>
  </AppLayout>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import AppLayout from "@/components/layout/AppLayout.vue";
import { useAuthStore } from "@/stores/auth";
import { useWalletStore } from "@/stores/wallet";
import { useBetsStore } from "@/stores/bets";
import { apiCall } from "@/api/client";
import { formatNum, BETS } from "@/config";

const router = useRouter();
const auth = useAuthStore();
const wallet = useWalletStore();
const betsStore = useBetsStore();

const walletBalance = computed(() => Number(wallet.me?.balance ?? 0));

const QUICK_AMOUNTS = [10, 25, 50, 100, 250];

const form = reactive({
  statement: "",
  deadline: "",
  type: "yes_no",
  stake: 20,
  options: ["Oui", "Non"],
  arbiter_username: null,
});

const submitting = ref(false);
const apiError = ref("");
const eligibleArbiters = ref([]);

// ─── Computed ────────────────────────────────────────────
const optionLabels = computed(() => {
  if (form.type === "yes_no") return ["Oui", "Non"];
  return form.options.map((o) => (o || "").trim());
});

const minDeadline = computed(() => {
  const d = new Date(Date.now() + 5 * 60 * 1000);
  return d.toISOString().slice(0, 16);
});

const validationErrors = computed(() => {
  const errs = [];
  if (!form.statement.trim()) errs.push("L'affirmation est obligatoire");
  if (!form.deadline) errs.push("Deadline obligatoire");
  else if (new Date(form.deadline) < new Date())
    errs.push("La deadline est déjà passée");

  if (!form.stake || form.stake < BETS.minStake)
    errs.push(`Mise minimum : ${BETS.minStake} CAMP`);
  if (form.stake > BETS.maxStake)
    errs.push(`Mise maximum : ${BETS.maxStake} CAMP`);

  if (form.type === "multi_choice") {
    const cleaned = optionLabels.value.filter(Boolean);
    if (cleaned.length < BETS.minOptions)
      errs.push(`Au moins ${BETS.minOptions} options non vides`);
    if (cleaned.length > BETS.maxOptions)
      errs.push(`Maximum ${BETS.maxOptions} options`);
    // Doublons
    const lower = cleaned.map((s) => s.toLowerCase());
    if (new Set(lower).size !== lower.length)
      errs.push("Pas de doublons dans les options");
  }

  return errs;
});

const isValid = computed(() => validationErrors.value.length === 0);

// ─── Helpers ─────────────────────────────────────────────
function setType(t) {
  form.type = t;
  if (t === "yes_no") {
    form.options = ["Oui", "Non"];
  } else if (form.options.length < 2) {
    form.options = ["", ""];
  }
}

function addOption() {
  if (form.options.length < BETS.maxOptions) form.options.push("");
}

function removeOption(i) {
  if (form.options.length <= 2) return;
  form.options.splice(i, 1);
}

function setDeadline(hoursFromNow) {
  const d = new Date(Date.now() + hoursFromNow * 60 * 60 * 1000);
  const pad = (n) => n.toString().padStart(2, "0");
  form.deadline = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

// Si l'arbitre devient le user, on le retire (impossible techniquement
// puisque eligibleArbiters exclut déjà me). Pas de logique supplémentaire.

// ─── Submit ──────────────────────────────────────────────
async function submit() {
  if (!isValid.value) return;
  submitting.value = true;
  apiError.value = "";
  try {
    const payload = {
      statement: form.statement.trim(),
      deadline: new Date(form.deadline).toISOString(),
      type: form.type,
      stake: form.stake,
      arbiter_username: form.arbiter_username,
    };
    if (form.type === "multi_choice") {
      payload.options = optionLabels.value.filter(Boolean);
    }
    // Pas de creator_option_index : le créateur rejoint après création
    // depuis la vue détail, comme n'importe quel autre user.
    const bet = await betsStore.create(payload);
    router.push({ name: "paris-detail", params: { id: bet.id } });
  } catch (e) {
    apiError.value = e.message;
  } finally {
    submitting.value = false;
  }
}

// ─── Init ────────────────────────────────────────────────
onMounted(async () => {
  setDeadline(24 * 7);
  try {
    const users = await apiCall("/users", { token: auth.userToken });
    eligibleArbiters.value = users.filter(
      (u) => u.username !== wallet.me?.username,
    );
  } catch (e) {
    /* silent */
  }
  try {
    if (typeof wallet.refresh === "function") await wallet.refresh();
  } catch (e) {
    /* silent */
  }
});
</script>

<style scoped>
.narrow {
  max-width: 720px;
  margin: 0 auto;
  padding-bottom: 6em;
}

.page-header {
  margin-bottom: 1.5em;
}
.back-link {
  background: none;
  border: none;
  color: var(--text-2);
  font-size: 0.9em;
  cursor: pointer;
  margin-bottom: 0.4em;
  padding: 0;
}
.back-link:hover {
  color: var(--text-0);
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
  padding: 1.2em 1.3em;
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
  margin-bottom: 0.5em;
}
.field-hint {
  font-size: 0.72em;
  color: var(--text-3);
  align-self: flex-end;
}

textarea,
input[type="number"],
input[type="text"],
input[type="datetime-local"],
select {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0.7em 0.85em;
  font-size: 1em;
  color: var(--text-0);
  font-family: inherit;
  width: 100%;
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
  padding: 0.35em 0.8em;
  border-radius: var(--radius-sm);
  font-size: 0.82em;
  color: var(--text-1);
  cursor: pointer;
  transition: all 0.15s;
  min-height: 38px;
}
.quick-amounts button:hover,
.quick-deadlines button:hover {
  border-color: var(--violet);
  color: var(--text-0);
}

/* ─── Format toggle ─────────────────────────────────── */
.format-toggle {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.6em;
  margin-bottom: 1em;
}
.format-opt {
  background: var(--bg-2);
  border: 2px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 1em 0.8em;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.3em;
  transition: all 0.15s;
  min-height: 60px;
}
.format-opt:hover {
  border-color: var(--border-strong);
}
.format-opt.active {
  border-color: var(--violet);
  background: rgba(154, 78, 255, 0.08);
}
.format-label {
  font-weight: 700;
  font-size: 1em;
  color: var(--text-0);
}
.format-sub {
  font-size: 0.78em;
  color: var(--text-2);
}

/* ─── Options builder ─────────────────────────────────── */
.options-builder {
  display: flex;
  flex-direction: column;
  gap: 0.5em;
}
.option-row {
  display: flex;
  align-items: center;
  gap: 0.5em;
}
.opt-num {
  font-size: 0.85em;
  color: var(--text-3);
  width: 1.5em;
  text-align: right;
}
.option-row input {
  flex: 1;
}
.opt-remove {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0.45em 0.7em;
  cursor: pointer;
  color: var(--text-2);
  min-width: 40px;
  min-height: 40px;
}
.opt-remove:hover {
  color: var(--red);
  border-color: var(--red);
}
.btn-add-opt {
  margin-top: 0.3em;
  width: 100%;
}

.dim {
  color: var(--text-3);
}

.hint {
  color: var(--text-2);
  font-size: 0.88em;
  margin-bottom: 0.8em;
}

/* ─── Récap ───────────────────────────────────────────── */
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
  gap: 1em;
  flex-wrap: wrap;
}
.recap-row b {
  text-align: right;
}
.recap-row:last-child {
  border-bottom: none;
}
.recap-row.gain {
  color: var(--gold);
  font-size: 1.02em;
  padding-top: 0.6em;
  border-top: 1px solid var(--border);
}
.recap-row.hint-row {
  padding-top: 0.6em;
  border-top: 1px solid var(--border);
  font-size: 0.85em;
}
.hint-text {
  color: var(--violet);
  font-weight: 600;
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
  .format-toggle {
    grid-template-columns: 1fr;
  }
  /* Sticky CTA on mobile */
  .actions {
    position: sticky;
    bottom: 0;
    background: linear-gradient(
      to top,
      var(--bg-0) 65%,
      transparent
    );
    padding: 1em 0 0.6em;
    margin: 0 -1em;
    padding-left: 1em;
    padding-right: 1em;
    z-index: 5;
    flex-direction: column-reverse;
  }
  .actions button {
    width: 100%;
    min-height: 48px;
  }
}
</style>
