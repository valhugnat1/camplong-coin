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
  // Définie dans .env (VITE_CONTRACT_ADDRESS=0x...)
  // Doit être la même adresse que CONTRACT_ADDRESS côté backend.
  address: import.meta.env.VITE_CONTRACT_ADDRESS || ''
}

// ─── Conversion EUR ↔ CAMP
//
// Taux affiché (= taux de vente, sans frais) : 1 CAMP = 0,01 € → 1 € = 100 CAMP
// → La valeur affichée à l'écran correspond exactement à ce que tu récupères en vendant.
//
// Frais (5 %) : prélevés uniquement à l'ACHAT pour couvrir serveurs et gas Ethereum.
// → 10 € → 950 CAMP (1000 brut − 5 % = 950 net)
// → Ces 950 CAMP s'afficheront comme valant 9,50 € (= leur vraie valeur de revente).
//
export const RATES = {
  campPerEur: 100,
  feePctBuy: 5    // frais à l'achat uniquement
}

// Handles de paiement — Hugo Philipp
// ⚠️ Remplace ces valeurs par tes vraies coordonnées
export const PAYMENT = {
  recipient: 'Hugo Philipp',
  wero: '+33 6 XX XX XX XX',
  revolut: '@hugophilipp'
}

// ─── Helpers de calcul

/** Valeur d'un solde CAMP en euros (= ce que tu récupères si tu vends) */
export function campToEur(camp) {
  return Number(camp || 0) / RATES.campPerEur
}

/** EUR → CAMP nets reçus par l'acheteur (après frais 5 % à l'achat) */
export function eurToCampNet(eur) {
  const gross = Number(eur || 0) * RATES.campPerEur
  return Math.floor(gross * (1 - RATES.feePctBuy / 100))
}

/** CAMP → EUR à la vente : pas de frais, c'est la valeur de marché */
export function campToEurNet(camp) {
  return campToEur(camp)
}

/** Formate un nombre en EUR */
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
