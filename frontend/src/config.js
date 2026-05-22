// ═══════════════════════════════════════════════════════════
// CamplongCoin — Configuration partagée
// ═══════════════════════════════════════════════════════════

export const CHAIN = {
  chainId: '0x14a34',
  chainIdDecimal: 84532,
  chainName: 'Base Sepolia',
  nativeCurrency: { name: 'Sepolia ETH', symbol: 'ETH', decimals: 18 },
  rpcUrls: ['https://base-sepolia-rpc.publicnode.com'],
  blockExplorerUrls: ['https://sepolia.basescan.org']
}

export const TOKEN = {
  symbol: 'CAMP',
  name: 'CamplongCoin',
  decimals: 18,
  address: import.meta.env.VITE_CONTRACT_ADDRESS || ''
}

// Taux : 1 CAMP = 0,01 € (sans frais à la vente)
// À l'achat : frais 5 % → 10 € donnent 950 CAMP nets
export const RATES = {
  campPerEur: 100,
  feePctBuy: 5
}

// Handles de paiement Hugo Philipp
export const PAYMENT = {
  recipient: 'Hugo Philipp',
  wero: '+33 7 77 93 22 15',
  revolut: '@hugo1weu7'
}

// Paris communautaires (doit rester en sync avec backend/config.py BETS)
export const BETS = {
  minStake: 1,
  maxStake: 1000,
  maxOpenBetsPerUser: 10,
  minOptions: 2,
  maxOptions: 6,
}

// ─── Helpers ───────────────────────────────────────────

export function campToEur(camp) {
  return Number(camp || 0) / RATES.campPerEur
}

export function eurToCampNet(eur) {
  const gross = Number(eur || 0) * RATES.campPerEur
  return Math.floor(gross * (1 - RATES.feePctBuy / 100))
}

export function campToEurNet(camp) {
  return campToEur(camp)
}

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
