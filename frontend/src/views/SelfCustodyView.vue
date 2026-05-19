<template>
  <AppLayout>
    <main class="page fade-in">
      <div class="page-header">
        <h1 class="page-title">
          <span style="color: var(--camp)">🦊</span> Récupérer ton wallet
        </h1>
        <p class="page-sub">
          Self-custody mode : tu reprends le contrôle. Plus de Hugo entre toi et tes CAMP.
        </p>
      </div>

      <!-- ─── Étape 1 : ajouter le réseau & le token à MetaMask ─── -->
      <div class="card step-card">
        <div class="card-header">
          <div class="card-title"><span class="step-num">1</span> Configurer MetaMask</div>
        </div>
        <p class="explain">
          MetaMask doit connaître <b>Base Sepolia</b> et le token <b>CAMP</b> pour t'afficher tes coins.
          Si tu n'as pas MetaMask, <a href="https://metamask.io/download" target="_blank" rel="noreferrer">installe-le d'abord</a>.
        </p>

        <div class="actions-grid">
          <button class="btn-primary" @click="addNetwork" :disabled="busyNet">
            {{ busyNet ? '…' : '+ Ajouter Base Sepolia' }}
          </button>
          <button class="btn-ghost" @click="addToken" :disabled="busyTok">
            {{ busyTok ? '…' : '+ Ajouter le token CAMP' }}
          </button>
        </div>

        <div v-if="metaMsg" class="alert success">{{ metaMsg }}</div>
        <div v-if="metaErr" class="alert error">{{ metaErr }}</div>

        <details class="manual">
          <summary>Faire ça à la main</summary>
          <div class="info-row"><span class="k">Réseau</span><span class="v">{{ chain.chainName }}</span></div>
          <div class="info-row"><span class="k">Chain ID</span><span class="v mono">{{ chain.chainIdDecimal }}</span></div>
          <div class="info-row"><span class="k">RPC URL</span><span class="v mono small">{{ chain.rpcUrls[0] }}</span></div>
          <div class="info-row"><span class="k">Explorer</span><span class="v mono small">{{ chain.blockExplorerUrls[0] }}</span></div>
          <div class="info-row"><span class="k">Token CAMP</span><span class="v mono small">{{ token.address || '⚠ VITE_CONTRACT_ADDRESS non défini' }}</span></div>
        </details>
      </div>

      <!-- ─── Étape 2 : récupérer la clé privée ─── -->
      <div class="card step-card">
        <div class="card-header">
          <div class="card-title"><span class="step-num">2</span> Récupérer ta clé privée</div>
        </div>

        <div class="warning-box">
          <span class="warn-ico">⚠</span>
          <div>
            <b>La clé privée donne le contrôle total de ton wallet.</b>
            Ne la partage avec personne. Note-la dans un gestionnaire de mots de passe.
            Une fois exportée, Hugo n'aura plus aucun pouvoir sur ces CAMP (c'est le but).
          </div>
        </div>

        <div v-if="!revealed">
          <p class="explain">
            Confirme ton mot de passe pour révéler la clé privée associée à ton wallet on-chain.
          </p>
          <div class="field">
            <label class="field-label">Mot de passe</label>
            <input
              v-model="revealPwd"
              type="password"
              placeholder="••••••••"
              autocomplete="current-password"
              @keyup.enter="reveal"
            />
          </div>
          <button class="btn-danger btn-block" @click="reveal" :disabled="revealing || !revealPwd">
            {{ revealing ? 'Déchiffrement…' : '🔓 Révéler ma clé privée' }}
          </button>
          <div v-if="revealErr" class="alert error">{{ revealErr }}</div>
        </div>

        <div v-else>
          <label class="field-label">Ta clé privée (format hex)</label>
          <div class="key-box">
            <code class="key">{{ shownKey }}</code>
            <button class="btn-ghost btn-sm" @click="toggleHide">
              {{ hidden ? '👁 Voir' : '🙈 Cacher' }}
            </button>
            <button class="btn-ghost btn-sm" @click="copyKey">
              {{ copied ? '✓ Copié' : '📋 Copier' }}
            </button>
          </div>
          <p class="hint">
            Une fois sauvegardée en lieu sûr, importe-la dans MetaMask :
            <b>MetaMask → Hamburger → Comptes → Ajouter un compte → Importer compte → Clé privée</b>.
          </p>
        </div>
      </div>

      <!-- ─── Étape 3 : récap ─── -->
      <div class="card step-card recap">
        <div class="card-header">
          <div class="card-title"><span class="step-num">3</span> Et après ?</div>
        </div>
        <p class="explain">
          Une fois ta clé importée dans MetaMask, tu vois tes CAMP directement dans ton wallet perso.
          Tu peux les envoyer où tu veux, mais <b>attention : Hugo paie le gas via le système custodial</b>.
          Si tu envoies depuis MetaMask, tu paies le gas en ETH Sepolia (gratuit sur testnet, mais réel sur mainnet).
        </p>
        <p class="explain dim">
          Pour récupérer de l'ETH Sepolia : <a href="https://portal.cdp.coinbase.com/products/faucet" target="_blank" rel="noreferrer">faucet Coinbase</a>.
        </p>
      </div>
    </main>
  </AppLayout>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import AppLayout from '@/components/layout/AppLayout.vue'
import { apiCall } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useWalletStore } from '@/stores/wallet'
import { CHAIN, TOKEN } from '@/config'

const auth = useAuthStore()
const wallet = useWalletStore()

const chain = CHAIN
const token = TOKEN

// MetaMask network/token
const busyNet = ref(false)
const busyTok = ref(false)
const metaMsg = ref('')
const metaErr = ref('')

async function addNetwork() {
  metaMsg.value = ''
  metaErr.value = ''
  if (!window.ethereum) {
    metaErr.value = "MetaMask non détecté. Installe l'extension d'abord."
    return
  }
  busyNet.value = true
  try {
    await window.ethereum.request({
      method: 'wallet_addEthereumChain',
      params: [{
        chainId: CHAIN.chainId,
        chainName: CHAIN.chainName,
        nativeCurrency: CHAIN.nativeCurrency,
        rpcUrls: CHAIN.rpcUrls,
        blockExplorerUrls: CHAIN.blockExplorerUrls
      }]
    })
    metaMsg.value = 'Réseau Base Sepolia ajouté à MetaMask.'
  } catch (e) {
    metaErr.value = e.message || 'Annulé.'
  } finally {
    busyNet.value = false
  }
}

async function addToken() {
  metaMsg.value = ''
  metaErr.value = ''
  if (!window.ethereum) {
    metaErr.value = "MetaMask non détecté."
    return
  }
  if (!TOKEN.address || /^0x0+$/i.test(TOKEN.address)) {
    metaErr.value = "Adresse du contrat manquante (variable VITE_CONTRACT_ADDRESS dans .env)."
    return
  }
  busyTok.value = true
  try {
    await window.ethereum.request({
      method: 'wallet_watchAsset',
      params: {
        type: 'ERC20',
        options: {
          address: TOKEN.address,
          symbol: TOKEN.symbol,
          decimals: TOKEN.decimals
        }
      }
    })
    metaMsg.value = 'Token CAMP ajouté à MetaMask.'
  } catch (e) {
    metaErr.value = e.message || 'Annulé.'
  } finally {
    busyTok.value = false
  }
}

// Reveal private key
const revealPwd = ref('')
const revealing = ref(false)
const revealErr = ref('')
const revealed = ref(false)
const privateKey = ref('')
const hidden = ref(false)
const copied = ref(false)

const shownKey = computed(() => {
  if (hidden.value) return '•'.repeat(64)
  return privateKey.value
})

async function reveal() {
  revealErr.value = ''
  revealing.value = true
  try {
    // Endpoint à implémenter côté back : POST /me/reveal-key
    // Payload : { password }
    // Réponse : { private_key }
    const d = await apiCall('/me/reveal-key', {
      method: 'POST',
      token: auth.userToken,
      body: JSON.stringify({ password: revealPwd.value })
    })
    privateKey.value = d.private_key
    revealed.value = true
    revealPwd.value = ''
  } catch (e) {
    if (/404|Not Found/i.test(e.message)) {
      revealErr.value =
        "L'endpoint /me/reveal-key n'existe pas encore côté back. À implémenter (POST avec { password } → { private_key })."
    } else {
      revealErr.value = e.message
    }
  } finally {
    revealing.value = false
  }
}

function toggleHide() {
  hidden.value = !hidden.value
}

async function copyKey() {
  try {
    await navigator.clipboard.writeText(privateKey.value)
    copied.value = true
    setTimeout(() => (copied.value = false), 1500)
  } catch (e) {
    // silencieux
  }
}

onMounted(() => {
  if (!wallet.me.username) wallet.refresh()
})
</script>

<style scoped>
.step-card {
  margin-bottom: 1em;
}
.step-num {
  display: inline-grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--camp);
  color: white;
  font-weight: 700;
  font-size: 0.85em;
  margin-right: 0.4em;
}

.explain {
  color: var(--text-1);
  font-size: 0.95em;
  margin: 0.4em 0 1em;
}
.explain.dim {
  color: var(--text-2);
  font-size: 0.88em;
}

.actions-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.6em;
}
@media (max-width: 540px) {
  .actions-grid { grid-template-columns: 1fr; }
}

.manual {
  margin-top: 1em;
  padding: 0.8em 1em;
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 0.9em;
}
.manual summary {
  cursor: pointer;
  color: var(--text-2);
  font-weight: 600;
}
.manual summary:hover { color: var(--text-0); }

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 0.5em 0;
  border-bottom: 1px solid var(--border);
  gap: 1em;
}
.info-row:last-child {
  border-bottom: none;
}
.info-row .k {
  color: var(--text-2);
  font-size: 0.82em;
  flex-shrink: 0;
}
.info-row .v {
  text-align: right;
  word-break: break-all;
  color: var(--text-0);
  min-width: 0;
}
.info-row .v.small {
  font-size: 0.8em;
}

.warning-box {
  display: flex;
  gap: 0.8em;
  align-items: flex-start;
  background: rgba(255, 69, 102, 0.06);
  border: 1px solid rgba(255, 69, 102, 0.2);
  border-radius: var(--radius-sm);
  padding: 0.9em 1em;
  color: var(--text-1);
  font-size: 0.92em;
  margin-bottom: 1em;
}
.warn-ico {
  color: var(--red);
  font-size: 1.4em;
  line-height: 1;
  flex-shrink: 0;
}

.key-box {
  display: flex;
  gap: 0.5em;
  align-items: center;
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0.8em;
  margin-top: 0.4em;
  flex-wrap: wrap;
}
.key {
  flex: 1;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.82em;
  word-break: break-all;
  color: var(--green);
  min-width: 200px;
}

.hint {
  color: var(--text-3);
  font-size: 0.85em;
  margin-top: 0.8em;
  font-style: italic;
}
</style>
