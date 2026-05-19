# CamplongCoin — Frontend

App Vue 3 + Vite + Vue Router + Pinia.
Single repo pour le front user **et** le backoffice admin.

## Stack

- **Vue 3** (Composition API, `<script setup>`)
- **Vite 6** (dev server + bundler)
- **Vue Router 4** (SPA routing avec lazy loading)
- **Pinia** (state management : auth + wallet)
- Single-file components, scoped CSS
- Responsive (mobile-first), tout marche jusqu'à 360px

## Init

```bash
cd camplong-front
cp .env.example .env
# édite .env : VITE_API_URL + VITE_CONTRACT_ADDRESS

npm install
npm run dev      # http://localhost:8080
```

Pour la prod : `npm run build` → `dist/` (statique, à servir avec nginx, Caddy, Object Storage…).

## Routes

| Path             | Auth         | Vue                  | Description                        |
|------------------|--------------|----------------------|------------------------------------|
| `/`              | redirect     | → `/wallet`          | Home                               |
| `/login`         | public       | LoginView            |                                    |
| `/wallet`        | user JWT     | WalletView           | Balance, envoi, historique         |
| `/paris`         | user JWT     | ParisView            | Placeholder Polymarket-like        |
| `/casino`        | user JWT     | CasinoView           | Placeholder slots/roulette         |
| `/milk`          | user JWT     | MilkView             | Placeholder Bourse du Lait         |
| `/profile`       | user JWT     | ProfileView          | Change mot de passe                |
| `/self-custody`  | user JWT     | SelfCustodyView      | Export clé + ajout MetaMask        |
| `/buy`           | user JWT     | BuyCampView          | Acheter / Vendre CAMP en EUR       |
| `/admin/login`   | public       | AdminLoginView       |                                    |
| `/admin`         | admin JWT    | AdminView            | Backoffice                         |

Routes inconnues → redirect `/wallet`.

## Conversion EUR ↔ CAMP

Centralisée dans `src/config.js`.

- **Taux de base** : 1 € = 100 CAMP (1 CAMP = 0,01 €)
- **Frais** : 5 % sur chaque opération (serveurs + gas Ethereum)
- **Résultat pratique** : 10 € → 950 CAMP nets

Pour changer le taux ou les frais : édite `RATES` dans `config.js`.

## Handles de paiement (Hugo)

Dans `src/config.js`, objet `PAYMENT` :

```js
export const PAYMENT = {
  recipient: 'Hugo Philipp',
  wero: '+33 6 XX XX XX XX',
  revolut: '@hugophilipp'
}
```

**⚠️ Pense à remplacer ces valeurs par tes vrais handles avant de partager le lien.**

## Endpoints back consommés

User (header `Authorization: Bearer <user_jwt>`) :
- `POST /login`
- `GET /me`
- `GET /users`
- `GET /history`
- `POST /transfer`
- `POST /me/password`     ← **À implémenter** (pour ProfileView)
- `POST /me/reveal-key`   ← **À implémenter** (pour SelfCustodyView)

Admin (header `Authorization: Bearer <admin_jwt>`) :
- `POST /admin/login`
- `GET /admin/treasury`
- `GET /admin/users`
- `POST /admin/users`
- `POST /admin/credit`
- `POST /admin/debit`

### Spec des 2 nouveaux endpoints user

**`POST /me/password`**
```json
// Request
{ "current_password": "...", "new_password": "..." }
// Response: 204 No Content (ou {"ok": true})
```

**`POST /me/reveal-key`**
```json
// Request
{ "password": "..." }
// Response
{ "private_key": "0x..." }
```
Le back doit re-vérifier le password, déchiffrer la clé Fernet, et la renvoyer. Le front ne stocke jamais la clé, il l'affiche juste à l'écran.

## Structure

```
camplong-front/
├── index.html              # entry point (charge les fonts)
├── package.json
├── vite.config.js          # alias @ = ./src
├── .env.example
│
└── src/
    ├── main.js
    ├── App.vue
    ├── config.js           # taux EUR↔CAMP, handles paiement, chain, token
    │
    ├── api/
    │   └── client.js
    │
    ├── router/
    │   └── index.js
    │
    ├── stores/
    │   ├── auth.js
    │   └── wallet.js
    │
    ├── assets/styles/
    │   └── main.css
    │
    ├── components/
    │   ├── layout/
    │   │   ├── AppLayout.vue
    │   │   ├── TopBar.vue
    │   │   ├── ProfileMenu.vue   ← dropdown user (mon profil, metamask, etc.)
    │   │   ├── Ticker.vue
    │   │   └── TabNav.vue
    │   ├── wallet/
    │   │   ├── BalanceCard.vue   ← affiche aussi le solde en EUR
    │   │   ├── SendForm.vue
    │   │   └── HistoryList.vue
    │   └── admin/
    │       ├── AdminTopBar.vue
    │       ├── TreasuryBox.vue
    │       ├── CreateUserForm.vue
    │       └── UsersTable.vue
    │
    └── views/
        ├── LoginView.vue
        ├── WalletView.vue
        ├── ParisView.vue
        ├── CasinoView.vue
        ├── MilkView.vue
        ├── ProfileView.vue       ← change mot de passe
        ├── SelfCustodyView.vue   ← export clé + MetaMask
        ├── BuyCampView.vue       ← acheter/vendre CAMP en EUR
        └── admin/
            ├── AdminLoginView.vue
            └── AdminView.vue
```
