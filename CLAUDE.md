# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Reference documents

- `README.md` — what the app does and how to launch it locally (in French).
- `AGENTS.md` — full technical spec: contract, DB schema, backend modules, frontend layout, security model, gotchas. Read this before non-trivial changes.
- `EXTENSIONS.md` — feature/extension notes.
- `backend/SETUP_EMAIL.md` — SMTP/Gmail App Password setup.

## Common commands

### Backend (FastAPI, Python 3.11+)
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload          # http://localhost:8000, OpenAPI at /docs
```

### Frontend (Vue 3 + Vite)
```bash
cd frontend
npm install
npm run dev                        # http://localhost:8080 (port hardcoded in vite.config.js)
npm run build                      # produces dist/ for the nginx image
```

User app entry: `/login` · Admin backoffice entry: `/admin/login`.

### Deploy (Scaleway Serverless Containers)
Run from the repo root, with a root `.env` containing `BACKEND_URL`, `CONTRACT_ADDRESS`, `SCW_SECRET_KEY`, `BACKEND_CONTAINER_ID`, `FRONT_CONTAINER_ID`:
```bash
./scripts/push_images.sh           # docker buildx build & push (linux/amd64)
./scripts/redeploy.sh              # POST /redeploy to Scaleway for both containers
```
`VITE_API_URL` and `VITE_CONTRACT_ADDRESS` are injected as build args into the frontend image — they are baked in at build time, not read at runtime.

There is no test runner or linter wired up in either project.

## Architecture — what's load-bearing

This is a **custodial** ERC-20 wallet app on Base Sepolia. The architectural pivot is:

**Every on-chain transfer is signed by a single treasury key**, never by users. The backend calls `contract.adminTransfer(from, to, amount)` (an owner-only function on the custom ERC-20) for *all* movements: user→user, admin credit/debit, and confirmed buy/sell orders. Users never need ETH; their encrypted private keys exist in the DB only for optional self-custody export.

Consequences that matter when editing code:

- **Single nonce sequence.** All tx come from the treasury address, so nonce management lives in `backend/blockchain.py::_next_treasury_nonce()` using a Postgres `SELECT ... FOR UPDATE` row on the `nonces` table, reconciled against `eth_getTransactionCount(treasury, "pending")`. Don't introduce parallel signers without rethinking this lock.
- **CAMP vs wei.** API + DB store amounts as integer CAMP. The ×10¹⁸ conversion happens *only* in `backend/blockchain.py`. Anywhere else in the codebase, reason in CAMP.
- **Two DB schemas in one Postgres database.** `test` and `prod`, selected via the `DB_SCHEMA` env var. The code both sets `search_path` per connection *and* declares `__table_args__ = {"schema": DB_SCHEMA}` on every model. Migrations must be run twice (once per schema).
- **Orders are the only place a state change drives an on-chain tx outside a direct user action.** `PATCH /admin/orders/{id}` flipping to `done` triggers `adminTransfer` + email. There's a guard against double-transfer: if `tx_hash` is already set, re-flipping done→pending→done does *not* re-execute on-chain.
- **Email is best-effort.** `backend/email_service.py` never raises; SMTP failures only log. Always dispatched via FastAPI `BackgroundTasks`.

## Backend layout (`backend/`)

Flat module structure, two routers:
- `main.py` mounts `routers/users.py` (user-facing endpoints, JWT user-auth) and `routers/admin.py` (backoffice, JWT admin-auth).
- `security.py` — `current_user` / `require_admin` deps, Fernet for private-key encryption.
- `blockchain.py` — singleton `w3` + `contract`, `admin_transfer`, balance helpers, treasury nonce reservation.
- `models.py` — 4 tables: `users`, `transactions`, `nonces`, `market_orders`. Treasury operations are logged in `transactions` with `from_username`/`to_username = "__treasury__"`.
- `config.py` — env loading; `DB_SCHEMA` defaults to `test`.

Two JWT flavors share `JWT_SECRET` (HS256): user tokens (7d, `sub=<username>`), admin tokens (24h, `sub="admin"`, `role="admin"`).

## Frontend layout (`frontend/src/`)

- `config.js` — **all business constants live here**: `RATES.campPerEur`, `RATES.feePctBuy` (5% fee applies only to *buys*; sells are free, and the displayed `CAMP · €` value uses `campToEur` without fees because that's the resale value), `PAYMENT` handles, `CHAIN`, `TOKEN`. Helpers `campToEur`, `eurToCampNet`, `formatEur`, `formatNum` are exported from here — use them instead of inline math.
- `api/client.js` — fetch wrapper with Bearer auto-injection and **global 401 handling**: any 401 logs out the appropriate session (user vs admin) and redirects to login with `?redirect=<current path>`. Don't handle 401 in stores/views.
- `stores/` — Pinia: `auth` (tokens persisted to localStorage), `wallet` (me/users/history), `orders` (admin orders, shared between `AdminView` and `AdminOrdersView` so the pending badge stays in sync).
- `router/index.js` — meta flags `guest: 'user' | 'admin'`, `needsUser`, `needsAdmin` drive the global `beforeEach` guard. Login views auto-bypass to `/wallet` or `/admin` if already authenticated.

Stack: Vue 3 Composition API with `<script setup>`, Vite 6, Vue Router 4, Pinia. No UI framework — scoped SFC styles plus primitives in `assets/styles/main.css`. Vite alias `@` → `./src`. Mobile-first, responsive down to 360px.

## Gotchas worth remembering

- The `adminTransfer` shortcut (skipping ERC-20 `approve`/`transferFrom`) is intentional and central — don't "fix" it back to the standard pattern.
- The treasury owns the contract on Base Sepolia (Chain ID 84532). Owner compromise = full control of all balances. Acceptable on testnet; would need multi-sig + rate limits + 2FA before mainnet.
- `__treasury__` is a sentinel username in `transactions.from_username` / `to_username`, not a real row in `users`.
- In `/admin/*` routes the `wallet` store is intentionally not loaded — admins don't need a user account, so `wallet.me` being empty there is expected.
- BaseScan tx link format: `https://sepolia.basescan.org/tx/<hash>`.
