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

## Structure

```
camplong-front/
├── index.html              # entry point (charge les fonts)
├── package.json
├── vite.config.js          # alias @ = ./src
├── .env.example            # VITE_API_URL
│
└── src/
    ├── main.js
    ├── App.vue             # shell minimal (router-view)
    │
    ├── api/
    │   └── client.js       # wrapper fetch + gestion erreurs
    │
    ├── router/
    │   └── index.js        # routes + guards (needsUser, needsAdmin)
    │
    ├── stores/
    │   ├── auth.js         # JWT user + JWT admin, localStorage sync
    │   └── wallet.js       # me, users, history (refresh centralisé)
    │
    ├── assets/styles/
    │   └── main.css        # variables, primitives, atmosphère
    │
    ├── components/
    │   ├── layout/
    │   │   ├── AppLayout.vue   # topbar + ticker + tabs (user)
    │   │   ├── TopBar.vue
    │   │   ├── Ticker.vue
    │   │   └── TabNav.vue
    │   ├── wallet/
    │   │   ├── BalanceCard.vue
    │   │   ├── SendForm.vue
    │   │   └── HistoryList.vue
    │   └── admin/
    │       ├── AdminTopBar.vue
    │       ├── TreasuryBox.vue
    │       ├── CreateUserForm.vue
    │       └── UsersTable.vue   # + modal credit/debit
    │
    └── views/
        ├── LoginView.vue
        ├── WalletView.vue
        ├── ParisView.vue    # placeholder (markets mockés)
        ├── CasinoView.vue   # placeholder (jeux mockés)
        ├── MilkView.vue     # placeholder (chart SVG + top movers)
        └── admin/
            ├── AdminLoginView.vue
            └── AdminView.vue
```

## Init (à faire 1 fois)

```bash
cd camplong-front
cp .env.example .env
# édite .env si ton back tourne ailleurs que http://localhost:8000

npm install
```

## Dev

```bash
npm run dev
```

- App user : <http://localhost:8080/login>
- Backoffice : <http://localhost:8080/admin/login>

Le dev server reload à chaud (HMR) à chaque modif.

## Build prod

```bash
npm run build      # génère dist/
npm run preview    # sert dist/ localement pour tester
```

`dist/` contient un SPA statique. Tu peux le servir avec n'importe quoi : nginx, Caddy, Scaleway Object Storage + CDN, Vercel, Netlify…

## Routes

| Path           | Auth         | Vue                |
|----------------|--------------|--------------------|
| `/`            | redirect     | → `/wallet`        |
| `/login`       | public       | LoginView          |
| `/wallet`      | user JWT     | WalletView         |
| `/paris`       | user JWT     | ParisView (mock)   |
| `/casino`      | user JWT     | CasinoView (mock)  |
| `/milk`        | user JWT     | MilkView (mock)    |
| `/admin/login` | public       | AdminLoginView     |
| `/admin`       | admin JWT    | AdminView          |

Les routes `*` (404) redirigent vers `/wallet`.

## Endpoints back consommés

User (token JWT user, header `Authorization: Bearer …`) :
- `POST /login`
- `GET /me`
- `GET /users`
- `GET /history`
- `POST /transfer`

Admin (token JWT admin) :
- `POST /admin/login`
- `GET /admin/treasury`
- `GET /admin/users`
- `POST /admin/users`
- `POST /admin/credit`
- `POST /admin/debit`

L'URL du back est lue dans `VITE_API_URL` (`.env`).

## Branchement des features "soon"

Les vues `paris`, `casino`, `milk` ont des données statiques (dans `<script setup>`).
Quand tu auras les endpoints back, remplace les `const markets = [...]`, `const games = [...]`, etc. par des `onMounted(async () => { ... = await apiCall(...) })`.

Tu peux aussi extraire dans des stores Pinia (`stores/paris.js`, etc.) si tu veux partager l'état entre composants.
