# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Reference documents

- `README.md` — what the app does and how to launch it locally (in French).
- `AGENTS.md` — full technical spec: contract, DB schema, backend modules, frontend layout, **modules Paris (community bets), Casino (coinflip + roulette + slots), Bourse du Lait (AMM)**, security model, gotchas. Read this before non-trivial changes.
- `EXTENSIONS.md` — spec for the not-yet-implemented Poker module + cross-cutting future ideas. All other modules (Paris, Casino, Bourse du Lait) have moved into `AGENTS.md` now that they're shipped.
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
- **Orders are not the only place a state change drives an on-chain tx outside a direct user action.** `PATCH /admin/orders/{id}` flipping to `done` triggers `adminTransfer` + email. There's a guard against double-transfer: if `tx_hash` is already set, re-flipping done→pending→done does *not* re-execute on-chain. Bets resolution (vote agreement, arbiter call, admin override) likewise drives on-chain payouts via the escrow service.
- **Escrow service** (`backend/services/escrow.py`) is the generic primitive for "user → system account → user" flows. Reused by bets (`bets_escrow`), coinflip + roulette + slots (`casino_bank`), milk AMM (`milk_pool_<symbol>`); will be reused by the planned poker module. Pattern: do the on-chain `lock`/`release` *before* changing DB status; on failure, `db.rollback()` so status stays consistent. The casino's special case: if the lock succeeded but the release fails (bank insufficient), we *don't* rollback — the lock stays, the round is logged, the admin reconciles by hand.
- **Milk AMM** (`backend/services/{amm,milk}.py`). x·y=k pool per product; `reserve_camp` in entire CAMP, `reserve_milk` in milli-bouteilles (`MILK_UNIT=1000`). Swaps `SELECT FOR UPDATE` the pool row (front-running guard). Chaos bot (`main.py::_chaos_loop`) modifies `reserve_milk` only — never `reserve_camp` — so CAMP conservation holds. Templates are pondered in DB (`milk_chaos_templates`); tick/proba/cap-volatilité are hot-reloadable via `app_settings`. `chaos_analysis` applies the volatility cap and exposes drift expectation (E[sqrt(milk_after/milk_before)] − 1) — note this assumes holders rebalance, otherwise the bank just keeps its CAMP unchanged.
- **Position valuation**. `position_dict` exposes both `current_value_camp` (mark-to-market = `balance × prix_spot`, theoretical) and `realisable_value_camp` (= `sell_quote(balance_milk)`, what you actually get). UI uses the realisable one by default — the spot version overstates large positions because it ignores their own price impact.
- **Provably-fair RNG** (`backend/services/randomness.py`) — commit-reveal sha256 pattern used by casino plays. The seed_hash is published BEFORE the play, the server_seed AFTER, and combined with a client_seed for the final outcome. `derive_int(combined, modulo)` gives the tirage (modulo 2 for coinflip, 37 for roulette, 3 weighted picks for slots with different offsets).
- **Commit-after-anim pattern** in casino views: the store's `{play, slotsSpin, rouletteSpin}` action returns the result *without* touching the wallet or history. The view runs the animation, then calls `commit{Slots,Roulette}Result()` (or inlines `wallet.refresh()` for coinflip) only after the anim finishes — otherwise the TopBar balance and history list spoil the result before the reels/wheel stop.
- **System accounts.** `users.account_type` distinguishes `'user'` from `'system'` (e.g. `bets_escrow`, `casino_bank`). System accounts have a wallet + encrypted key but no `password_hash` / `email`. `/users` filters them out so they don't appear in user-facing dropdowns.
- **Email is best-effort.** `backend/email_service.py` never raises; SMTP failures only log. Always dispatched via FastAPI `BackgroundTasks`.

## Backend layout (`backend/`)

Flat module structure, five routers:
- `main.py` mounts `routers/users.py` (user-facing, JWT user-auth), `routers/admin.py` (backoffice, JWT admin-auth), `routers/bets.py` (community bets, user-auth), `routers/casino.py` (coinflip + roulette + slots, user-auth), `routers/milk.py` (AMM lait, user-auth). Also runs `_chaos_loop` async task for the milk bot.
- `security.py` — `current_user` / `require_admin` deps, Fernet for private-key encryption.
- `blockchain.py` — singleton `w3` + `contract`, `admin_transfer`, balance helpers, treasury nonce reservation.
- `services/escrow.py` — `lock`/`release` between users and system accounts. Journalises every move in `transactions` with sentinel usernames like `__bets_escrow__`, `__milk_pool_lait_entier__`.
- `services/amm.py` + `services/milk.py` — pure AMM math (x·y=k) + swap orchestration + chaos templates + `chaos_analysis` (drift estimation with volatility cap applied).
- `models.py` — tables: `users` (with `account_type`/`system_role`), `transactions`, `nonces`, `market_orders`, `bets` + `bet_options` + `bet_participations` + `bet_votes`, `coinflip_rounds` + `roulette_spins` + `slots_spins`, `milk_pools` + `milk_positions` + `milk_trades` + `milk_chaos_events` + `milk_chaos_templates`, `app_settings`, `rng_seeds`. Treasury/system operations logged in `transactions` with `from_username`/`to_username = "__treasury__"` / `"__<role>__"`.
- `config.py` — env loading; `DB_SCHEMA` defaults to `test`; `BETS` dict mirrors `frontend/src/config.js`.

Two JWT flavors share `JWT_SECRET` (HS256): user tokens (7d, `sub=<username>`), admin tokens (24h, `sub="admin"`, `role="admin"`).

## Frontend layout (`frontend/src/`)

- `config.js` — **all business constants live here**: `RATES.campPerEur`, `RATES.feePctBuy` (5% fee applies only to *buys*; sells are free, and the displayed `CAMP · €` value uses `campToEur` without fees because that's the resale value), `PAYMENT` handles, `CHAIN`, `TOKEN`. Helpers `campToEur`, `eurToCampNet`, `formatEur`, `formatNum` are exported from here — use them instead of inline math.
- `api/client.js` — fetch wrapper with Bearer auto-injection and **global 401 handling**: any 401 logs out the appropriate session (user vs admin) and redirects to login with `?redirect=<current path>`. Don't handle 401 in stores/views.
- `stores/` — Pinia: `auth` (tokens persisted to localStorage — **only tokens, no username; the current username lives in `wallet.me.username`**), `wallet` (me/users/history), `orders` (admin orders, shared between `AdminView` and `AdminOrdersView` so the pending badge stays in sync), `bets` (open/mine/detail + actions create/join/cancel/resolve/vote), `casino` (config + history + lock/play/spin for coinflip/roulette/slots), `milk` (pools, pool detail, chart, trades, chaos, positions, myTrades).
- `router/index.js` — meta flags `guest: 'user' | 'admin'`, `needsUser`, `needsAdmin` drive the global `beforeEach` guard. Login views auto-bypass to `/wallet` or `/admin` if already authenticated.

Stack: Vue 3 Composition API with `<script setup>`, Vite 6, Vue Router 4, Pinia. No UI framework — scoped SFC styles plus primitives in `assets/styles/main.css`. Vite alias `@` → `./src`. Mobile-first, responsive down to 360px.

## Gotchas worth remembering

- The `adminTransfer` shortcut (skipping ERC-20 `approve`/`transferFrom`) is intentional and central — don't "fix" it back to the standard pattern.
- The treasury owns the contract on Base Sepolia (Chain ID 84532). Owner compromise = full control of all balances. Acceptable on testnet; would need multi-sig + rate limits + 2FA before mainnet.
- `__treasury__` is a sentinel username in `transactions.from_username` / `to_username`, not a real row in `users`. Similarly `__bets_escrow__` for escrow moves, and `__admin__` / `__community__` / `__expired__` appear in `bets.resolved_by`.
- In `/admin/*` routes the `wallet` store is intentionally not loaded — admins don't need a user account, so `wallet.me` being empty there is expected.
- **Username lookup in Vue views**: use `wallet.me?.username`, never `auth.username` (the auth store only holds tokens). This bit Paris views early; do not repeat.
- **Migrations**: run each migration script once per schema (`test`, then `prod`). Latest are `migrate_v4_extensions.py` (tables for paris/casino/lait + `account_type` on users), `migrate_v5_bet_votes.py` (legacy bet vote columns, obsoleted by v8), `migrate_v6_app_settings.py` (`app_settings` table for admin-tweakable params, e.g. `coinflip_edge_pct`), `migrate_v7_slots.py` (table `slots_spins` + slots min/max bet seeds), `migrate_v8_bets_v2.py` (**bets refonte** — drops old single-pair bet table and creates new community-bet schema: `bets` + `bet_options` + `bet_participations` + `bet_votes`; refund manually first), and `migrate_v9_milk_chaos_templates.py` (table `milk_chaos_templates` + ~33 seed templates + chaos `app_settings` seeds: tick_seconds, proba_pct, max_volatility_pct), `migrate_v10_poker_creator.py` (poker), and `migrate_v11_analytics_labels.py` (table `analytics_tx_labels` pour le dashboard `/admin/stats` — purement additive, et le backend tourne sans elle). Follow with `seed_system_accounts.py` after v4.
- **⚠️ Le container de prod tourne sur le schema `test`**, pas `prod` (verifie le 23/08/2026). Les donnees live des users sont donc dans `test` : c'est ce schema-la qu'il faut migrer en priorite, et `DB_SCHEMA=test` en local pointe sur la prod.
- **Dynamic settings**: `app_settings` (key/value VARCHAR table) holds parameters the admin can change from `/admin/casino` and `/admin/milk` without redeploying. Currently: coinflip edge + min/max bet, roulette min/max bet, slots min/max bet (slots edge is mechanical, hardcoded in `services/slots.py::SYMBOLS`), and milk chaos params (`milk_chaos_tick_seconds`, `milk_chaos_proba_pct`, `milk_chaos_max_volatility_pct`). Read via `services/settings.py::get_int/get_float`; whitelist of writable keys is in the same module. Static deploy-time constants (`BETS`, `RATES`, `MILK.milkUnit`) stay in `backend/config.py` / `frontend/src/config.js`.
- BaseScan tx link format: `https://sepolia.basescan.org/tx/<hash>`.
