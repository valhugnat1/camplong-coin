// ═══════════════════════════════════════════════════════════
// CamplongCoin — Configuration partagée
// Taux de change · réseau · token · handles de paiement
// ═══════════════════════════════════════════════════════════

// Base Sepolia testnet (Chain ID 84532)
export const CHAIN = {
  chainId: '0x14a34',
  chainIdDecimal: 84532,
  chainName: 'Base Sepolia',
  nativeCurrency: { name: 'Sepolia ETH', symbol: 'ETH', decimals: 18 },
  rpcUrls: ['https://base-sepolia-rpc.publicnode.com'],
  blockExplorerUrls: ['https://sepolia.basescan.org']
}

// Token CAMP
export const TOKEN = {
  symbol: 'CAMP',
  name: 'CamplongCoin',
  decimals: 18,
  // ⚠️ à remplir dans .env (VITE_CONTRACT_ADDRESS=0x...) sinon vide
  address: import.meta.env.VITE_CONTRACT_ADDRESS || ''
}

// ─── Conversion EUR ↔ CAMP
// Base rate (sans frais) : 1 € = 100 CAMP, donc 1 CAMP = 0,01 €
// Frais 5 % prélevés sur chaque transaction (serveurs + gas Ethereum)
// Donc en pratique : 10 € → 950 CAMP (1000 brut − 5 % = 950 net)
export const RATES = {
  campPerEur: 100,
  feePct: 5
}

// Handles de paiement — Hugo Philipp
// ⚠️ Remplace ces valeurs par tes vraies coordonnées
export const PAYMENT = {
  recipient: 'Hugo Philipp',
  wero: '+33 6 XX XX XX XX',   // ← à remplacer
  revolut: '@hugophilipp'      // ← à remplacer
}

// ─── Helpers de calcul

export function campToEur(camp) {
  return Number(camp || 0) / RATES.campPerEur
}

/** EUR → CAMP net reçus par l'acheteur (après frais 5 %) */
export function eurToCampNet(eur) {
  const gross = Number(eur || 0) * RATES.campPerEur
  return Math.floor(gross * (1 - RATES.feePct / 100))
}

/** CAMP → EUR nets reçus par le vendeur (après frais 5 %) */
export function campToEurNet(camp) {
  const gross = Number(camp || 0) / RATES.campPerEur
  return gross * (1 - RATES.feePct / 100)
}

/** Formate un nombre en EUR (1234.5 → "1 234,50 €") */
export function formatEur(n) {
  return Number(n || 0).toLocaleString('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })
}

export function formatNum(n) {
  if (n == null) return '0'
  return Number(n).toLocaleString('fr-FR')
}
