# EXTENSIONS.md — Modules casino, bourse du lait

Spec technique des modules **Casino** (Pile ou Face, Roulette, Poker) et **Bourse du Lait** (AMM x·y=k) — pas encore implémentés. Ce document complète `AGENTS.md` et ne le remplace pas.

> Le module **Paris** a été déplacé dans `AGENTS.md` une fois livré — il n'est plus listé ici.

> Lecture conseillée : `AGENTS.md` d'abord (architecture custodial, contrat, blockchain.py, schémas test/prod).

---

## Table des matières

1. [Vue d'ensemble & refactoring global](#1-vue-densemble--refactoring-global)
2. [Module Casino — Pile ou Face](#3-module-casino--pile-ou-face)
3. [Module Casino — Roulette](#4-module-casino--roulette)
4. [Module Casino — Poker](#5-module-casino--poker)
5. [Module Bourse du Lait](#6-module-bourse-du-lait)
6. [Points d'attention](#7-points-dattention)
7. [Améliorations & autres jeux possibles](#8-améliorations--autres-jeux-possibles)

> Les ancres des sections ci-dessous gardent leur numérotation d'origine (3 → 8) ;
> seule la TOC a été renumérotée après le départ du module Paris.

---

## 1. Vue d'ensemble & refactoring global

### 1.1 Principes directeurs

Le projet passe d'un seul concept simple (transfer P2P + market orders manuels) à une plateforme de jeu avec 5+ produits. Trois principes à acter avant de coder.

**On-chain vs off-chain.** Le projet actuel fait un `adminTransfer` on-chain pour chaque mouvement de CAMP. C'est OK pour les transferts P2P (volume faible, latence ~2s acceptable). C'est intenable pour le poker (multiples mises par main) et limite pour le trading rapide (bourse du lait). On adopte le pattern **escrow on-chain + livre off-chain** : les fonds bougent on-chain au début et à la fin d'une "session de jeu", mais les actions de jeu intermédiaires se font dans la DB.

| Module | Pattern | Tx on-chain par cycle |
|---|---|---|
| Paris | Escrow on-chain immédiat | 3 (mise creator + mise matcher + settlement) |
| Pile ou Face | On-chain par flip | 2 (mise + payout) — peut être nettés en 1 en cas de perte |
| Roulette | On-chain par spin | 2 (mises agrégées + payout net) |
| Poker | Sit-in / sit-out only | 2 par session (deposit + withdraw), peu importe le nombre de mains |
| Bourse du Lait | On-chain par swap | 2 (mise + payout) ou 1 si on aggrège |

**Comptes système.** Tu as déjà la treasury. On ajoute des comptes "système" pour isoler les fonds par produit, ce que tu as demandé pour la banque casino. Tracking comptable bien plus propre, et limite le rayon d'explosion en cas de bug.

**RNG vérifiable.** Pour tout ce qui est tirage aléatoire (coinflip, roulette, deck de poker, événements bot lait), on utilise un schéma **commit-reveal**. Le backend annonce `hash(seed)` avant le tirage, exécute le tirage, puis publie `seed`. Les users peuvent vérifier qu'on n'a pas triché a posteriori. C'est ce que font Stake, Bustabit, etc. Très peu coûteux à implémenter et ça désamorce immédiatement les accusations de triche entre potes.

### 1.2 Concept clé : comptes système

Aujourd'hui un compte = un user (login, mdp, clé privée chiffrée, email). On introduit un second type : compte système.

```
users (avec nouvelle colonne account_type)
├── 'user'        : Hugo, Alice, Emile, ...   (login + clé chiffrée)
└── 'system'      :                              (pas de login, clé chiffrée, géré par admin)
     ├── treasury           (déjà existant — flag rétroactif)
     ├── casino_bank        (banque jeux maison : coinflip, roulette)
     ├── bets_escrow        (escrow paris)
     ├── poker_bank         (stacks des joueurs en cours de partie)
     └── milk_pool_<symbol> (un par produit lait : LAIT-ENTIER, BEURRE, ...)
```

Caractéristiques d'un compte système :
- Adresse Ethereum + clé privée chiffrée (comme un user normal, pour pouvoir faire des `adminTransfer` dans les deux sens)
- Pas de `password_hash`, pas d'email
- Filtré dans la liste users côté annuaire user (`/users` ne les renvoie pas)
- Visible et créable dans le backoffice (`/admin/system-accounts`)
- Impossible de leur envoyer un CAMP depuis l'UI user de façon arbitraire — uniquement via les flows métier (mise sur un pari, swap dans un pool, sit-in poker)

Migration : ajouter `account_type VARCHAR(16) NOT NULL DEFAULT 'user'` à `users`, et back-fill la treasury à `'system'` + `system_role = 'treasury'`.

```sql
ALTER TABLE users ADD COLUMN account_type VARCHAR(16) NOT NULL DEFAULT 'user';
ALTER TABLE users ADD COLUMN system_role VARCHAR(32) NULL;
-- Index pour filtrer rapidement
CREATE INDEX idx_users_account_type ON users(account_type);
```

À noter : tu peux choisir de **ne pas** stocker la treasury dans `users` (elle vient déjà de `.env`), pour ne pas avoir à dupliquer la source de vérité. Choix par défaut dans ce doc : la treasury reste en `.env`, et les autres comptes système sont en DB.

### 1.3 Service d'escrow réutilisable

Un module commun pour bloquer/libérer des fonds vers un compte système. Évite de dupliquer la logique entre paris, casino, lait.

```python
# backend/services/escrow.py
from sqlalchemy.orm import Session
from models import User, Transaction
from blockchain import admin_transfer, get_balance_camp
import datetime

class EscrowError(Exception): pass

def get_system_account(db: Session, role: str) -> User:
    acc = db.query(User).filter(
        User.account_type == "system", User.system_role == role
    ).first()
    if not acc:
        raise EscrowError(f"Compte système '{role}' introuvable, à créer dans le backoffice")
    return acc

def lock(db: Session, user: User, role: str, amount: int, note: str) -> str:
    """Bloque des fonds : user -> compte système. Retourne tx_hash."""
    if amount <= 0:
        raise EscrowError("Montant doit être strictement positif")
    bal = get_balance_camp(user.address)
    if amount > bal:
        raise EscrowError(f"Solde insuffisant ({bal} CAMP)")
    sys_acc = get_system_account(db, role)
    tx_hash = admin_transfer(db, user.address, sys_acc.address, amount)
    db.add(Transaction(
        ts=datetime.datetime.utcnow(),
        from_username=user.username,
        to_username=f"__{role}__",
        amount=amount, note=note, tx_hash=tx_hash,
    ))
    return tx_hash

def release(db: Session, role: str, user: User, amount: int, note: str) -> str:
    """Libère des fonds : compte système -> user. Retourne tx_hash."""
    if amount <= 0:
        raise EscrowError("Montant doit être strictement positif")
    sys_acc = get_system_account(db, role)
    bal = get_balance_camp(sys_acc.address)
    if amount > bal:
        raise EscrowError(
            f"Compte '{role}' insuffisant ({bal} CAMP), il en faut {amount}. "
            f"Recharge depuis la treasury."
        )
    tx_hash = admin_transfer(db, sys_acc.address, user.address, amount)
    db.add(Transaction(
        ts=datetime.datetime.utcnow(),
        from_username=f"__{role}__",
        to_username=user.username,
        amount=amount, note=note, tx_hash=tx_hash,
    ))
    return tx_hash
```

Toutes les opérations de jeu passent par `lock()` et `release()`. La table `transactions` continue d'être le journal unique de tous les mouvements CAMP — l'audit reste trivial.

### 1.4 Service de randomness vérifiable

```python
# backend/services/randomness.py
import secrets, hashlib
from models import RngSeed  # nouvelle table, voir §1.7

def commit(db, purpose: str, ref_id: int | None = None) -> tuple[str, int]:
    """Génère un seed secret, retourne son hash public + l'id DB du seed."""
    seed = secrets.token_hex(32)
    seed_hash = hashlib.sha256(seed.encode()).hexdigest()
    row = RngSeed(
        purpose=purpose, ref_id=ref_id,
        seed_hash=seed_hash, seed_secret=seed,
        revealed=False,
    )
    db.add(row); db.flush()
    return seed_hash, row.id

def reveal(db, seed_id: int, client_seed: str = "") -> tuple[str, str]:
    """Marque le seed comme révélé, retourne (server_seed, combined_hash)."""
    row = db.get(RngSeed, seed_id)
    if row is None: raise ValueError("seed inconnu")
    row.revealed = True
    combined = hashlib.sha256((row.seed_secret + ":" + client_seed).encode()).hexdigest()
    return row.seed_secret, combined

def derive_int(combined_hash: str, modulus: int, offset: int = 0) -> int:
    """Tire un int dans [0, modulus) à partir du hash combiné."""
    h = hashlib.sha256(f"{combined_hash}:{offset}".encode()).hexdigest()
    return int(h, 16) % modulus
```

L'utilisateur peut, après chaque tirage, recalculer le résultat et le vérifier. La page de chaque jeu affiche `hash` avant pari et `seed` après pari, avec un lien "vérifier le résultat" qui détaille la formule.

### 1.5 Refactoring de la structure de fichiers

`users.py` et `admin.py` vont exploser si on continue à tout y mettre. On split par domaine.

```
backend/
├── main.py
├── config.py
├── database.py
├── blockchain.py
├── security.py
├── email_service.py
├── models/
│   ├── __init__.py            # re-exports pour compat (import models)
│   ├── core.py                # User (avec account_type), Transaction, Nonce
│   ├── market.py              # MarketOrder
│   ├── bets.py                # Bet
│   ├── casino.py              # CoinflipRound, RouletteSpin
│   ├── poker.py               # PokerTable, PokerSession, PokerHand
│   ├── milk.py                # MilkPool, MilkTrade, MilkChaosEvent
│   └── rng.py                 # RngSeed
├── schemas/                   # idem, un .py par domaine
├── routers/
│   ├── auth.py                # /login, /me, /me/password, ...
│   ├── wallet.py              # /transfer, /history, /users
│   ├── market.py              # /orders, /me/orders   (déplacé de users.py)
│   ├── bets.py                # /bets/*
│   ├── coinflip.py            # /casino/coinflip/*
│   ├── roulette.py            # /casino/roulette/*
│   ├── poker.py               # /casino/poker/* + WebSocket
│   ├── milk.py                # /milk/*
│   ├── admin_users.py         # /admin/users, /admin/system-accounts
│   ├── admin_market.py        # /admin/orders/*
│   ├── admin_bets.py          # /admin/bets/*
│   ├── admin_casino.py        # /admin/casino/*
│   └── admin_milk.py          # /admin/milk/pools/*
└── services/
    ├── escrow.py
    ├── randomness.py
    ├── amm.py                 # math x·y=k
    ├── poker_engine.py        # wrapper autour de treys
    └── chaos_bot.py           # scheduler pour la bourse du lait
```

Côté frontend, même découpage :

```
frontend/src/
├── views/
│   ├── WalletView.vue
│   ├── ProfileView.vue
│   ├── paris/
│   │   ├── ParisListView.vue
│   │   ├── ParisCreateView.vue
│   │   └── ParisDetailView.vue
│   ├── casino/
│   │   ├── CasinoHomeView.vue     # hub
│   │   ├── CoinflipView.vue
│   │   ├── RouletteView.vue
│   │   └── PokerView.vue
│   ├── lait/
│   │   ├── MilkHomeView.vue
│   │   └── MilkTradeView.vue
│   └── admin/
│       ├── ...
│       ├── AdminBetsView.vue
│       ├── AdminCasinoView.vue
│       ├── AdminMilkView.vue
│       └── AdminSystemAccountsView.vue
├── api/
│   ├── client.js
│   ├── bets.js
│   ├── casino.js
│   ├── poker.js   (utilise WebSocket aussi)
│   └── milk.js
└── stores/
    ├── auth.js  wallet.js   (existants)
    ├── bets.js
    ├── casino.js
    └── milk.js
```

### 1.6 Configuration partagée

Les paramètres métier des nouveaux modules vont dans `config.js` (front) et `config.py` (back). Un seul endroit, partagé symboliquement entre les deux (les valeurs sont dupliquées mais documentées comme devant rester en sync).

```js
// frontend/config.js — ajouts
export const BETS = {
  minStake: 1,
  maxStake: 1000,
  arbiterDefaultFeePct: 5,
  maxOpenBetsPerUser: 10,
}

export const CASINO = {
  coinflip: { minBet: 1, maxBet: 200, edgePct: 2 },     // edge maison
  roulette: { minBet: 1, maxBet: 200, edgePct: 2.7 },   // 1/37 = ~2.7%
  poker:    { minBuyIn: 50, maxBuyIn: 1000 },
}

export const MILK = {
  feePct: 0.5,
  maxSlippagePctDefault: 1,
}
```

### 1.7 Nouvelles tables transverses

```sql
-- RNG vérifiable (utilisé par coinflip, roulette, poker, chaos bot)
CREATE TABLE rng_seeds (
  id           SERIAL PRIMARY KEY,
  purpose      VARCHAR(32) NOT NULL,   -- 'coinflip' | 'roulette' | 'poker' | 'chaos'
  ref_id       INT NULL,               -- id de la round / spin / hand / event
  seed_hash    VARCHAR(64) NOT NULL,   -- sha256 du secret, publié avant
  seed_secret  VARCHAR(64) NOT NULL,   -- secret, publié après
  revealed     BOOLEAN NOT NULL DEFAULT FALSE,
  created_at   TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_rng_purpose_ref ON rng_seeds(purpose, ref_id);
```

### 1.8 Migrations

Le pattern actuel (`scripts/init_db.py` + migrate_v*.py) tient sur un projet à 4 tables. Avec 15+ tables on a vraiment besoin d'**Alembic**. Ajout :

```bash
cd backend
pip install alembic
alembic init alembic
# configurer alembic/env.py pour utiliser DATABASE_URL et DB_SCHEMA
alembic revision --autogenerate -m "add account_type + extension tables"
alembic upgrade head
```

Migration v4 typique :
- Ajouter `account_type` + `system_role` à `users`
- Créer toutes les nouvelles tables (paris, casino, poker, milk, rng_seeds)
- Seed des comptes système initiaux (casino_bank, bets_escrow, etc.) via script `scripts/seed_system_accounts.py`

À faire dans les deux schémas (`test` et `prod`) — Alembic permet de paramétrer le schema via la config.

### 1.9 Audit comptable

Avec 5+ produits qui bougent du CAMP, la question "où sont passés mes 1 000 000 CAMP" devient non triviale. Ajouter un endpoint admin `/admin/audit` qui calcule :

```
treasury balance + system_account balances + sum(user balances) == total_supply ?
```

Si ça ne matche pas, il y a un bug quelque part. Ce check tourne aussi via un cron 1×/jour et alerte par email à l'admin si écart > 0.01 CAMP.

---

## 3. Module Casino — Pile ou Face

### 3.1 Concept

Le user mise, choisit pile ou face, le backend tire au sort, paye 2× la mise si gagné (ou plutôt `2 × (1 - edge_pct/100)`, soit ~1.96× pour 2% d'edge).

C'est le plus simple des trois jeux casino, à implémenter en premier comme prototype du pattern "joueur vs banque".

### 3.2 Schéma DB

```sql
CREATE TABLE coinflip_rounds (
  id            SERIAL PRIMARY KEY,
  username      VARCHAR(64) NOT NULL REFERENCES users(username),
  bet_amount    BIGINT NOT NULL,
  choice        VARCHAR(8) NOT NULL,    -- 'heads' | 'tails'
  outcome       VARCHAR(8) NULL,        -- 'heads' | 'tails' (null avant settlement)
  win           BOOLEAN NULL,
  payout        BIGINT NOT NULL DEFAULT 0,   -- 0 si perdu, sinon 2 * bet * (1 - edge)

  client_seed   VARCHAR(64) NOT NULL,   -- contribution user (random côté front)
  rng_seed_id   INT NOT NULL REFERENCES rng_seeds(id),

  status        VARCHAR(16) NOT NULL DEFAULT 'open',
  -- 'open'       : seed commit envoyé, en attente de la mise (rare, peut être skip)
  -- 'committed'  : mise locked, hash publié, en attente du flip
  -- 'settled'    : résolu, payout fait

  ts                    TIMESTAMP DEFAULT NOW(),
  settled_at            TIMESTAMP NULL,
  tx_hash_lock          VARCHAR(66) NULL,
  tx_hash_payout        VARCHAR(66) NULL
);
CREATE INDEX idx_coinflip_user ON coinflip_rounds(username, ts DESC);
```

### 3.3 Flow

```
[user] POST /casino/coinflip/play  { bet, choice, client_seed }
   │
   ├─ Backend valide bet (min/max, balance suffisante)
   ├─ Backend appelle randomness.commit('coinflip')  → seed_id + seed_hash
   ├─ Backend lock bet via escrow → casino_bank (tx_hash_lock)
   ├─ Backend appelle randomness.reveal(seed_id, client_seed) → seed + combined_hash
   ├─ Backend calcule outcome = 'heads' if derive_int(combined, 2) == 0 else 'tails'
   ├─ Si win: payout = bet * 2 * (1 - edge/100), release de casino_bank → user
   ├─ Si lose: rien (les fonds restent dans casino_bank)
   └─ Persiste tout (round + seed)

Response: { id, outcome, win, payout, seed_hash, seed, client_seed, combined_hash, tx_hash_lock, tx_hash_payout }
```

Note : on commit *et* reveal dans la même requête HTTP. C'est moins pur cryptographiquement (l'utilisateur ne voit jamais `seed_hash` *avant* de miser), mais c'est ce que font la plupart des casinos provably fair en ligne pour la simplicité UX. Le user peut quand même vérifier a posteriori que `sha256(seed) == seed_hash`. Pour une version plus rigoureuse : 2 endpoints séparés (commit puis play), mais ça alourdit l'UX.

### 3.4 Code

```python
# routers/coinflip.py
@router.post("/casino/coinflip/play")
def play_coinflip(body: CoinflipIn, user=Depends(current_user), db=Depends(get_db)):
    if body.bet < CASINO["coinflip"]["min_bet"] or body.bet > CASINO["coinflip"]["max_bet"]:
        raise HTTPException(400, "Mise hors limites")
    if body.choice not in ("heads", "tails"):
        raise HTTPException(400, "Choice doit être 'heads' ou 'tails'")

    # Commit RNG seed
    seed_hash, seed_id = randomness.commit(db, "coinflip")

    # Lock
    try:
        tx_lock = escrow.lock(db, user, "casino_bank", body.bet,
                              f"coinflip seed_id={seed_id}")
    except EscrowError as e:
        db.rollback(); raise HTTPException(400, str(e))

    # Reveal + résolution
    server_seed, combined = randomness.reveal(db, seed_id, body.client_seed)
    outcome = "heads" if randomness.derive_int(combined, 2) == 0 else "tails"
    win = (outcome == body.choice)

    edge = CASINO["coinflip"]["edge_pct"] / 100
    payout = int(body.bet * 2 * (1 - edge)) if win else 0
    tx_payout = None
    if win:
        try:
            tx_payout = escrow.release(db, "casino_bank", user, payout,
                                       f"coinflip seed_id={seed_id} win")
        except EscrowError as e:
            # Catastrophe : on a pris la mise mais on peut pas payer le gain.
            # On lève sans rollback pour que le lock reste, l'admin règle à la main.
            raise HTTPException(500, f"Casino bank insuffisant pour payout: {e}")

    round_ = CoinflipRound(
        username=user.username, bet_amount=body.bet, choice=body.choice,
        outcome=outcome, win=win, payout=payout,
        client_seed=body.client_seed, rng_seed_id=seed_id,
        status="settled", settled_at=datetime.utcnow(),
        tx_hash_lock=tx_lock, tx_hash_payout=tx_payout,
    )
    db.add(round_); db.commit(); db.refresh(round_)

    return {
        "id": round_.id, "outcome": outcome, "win": win, "payout": payout,
        "seed_hash": seed_hash, "server_seed": server_seed,
        "client_seed": body.client_seed, "combined_hash": combined,
        "tx_hash_lock": tx_lock, "tx_hash_payout": tx_payout,
        "new_balance": get_balance_camp(user.address),
    }
```

### 3.5 Front

`CoinflipView.vue` : 
- Bouton avec animation de pièce qui tourne (CSS 3D transform sur un div, 1.5s d'animation)
- Slider/inputs pour la mise + raccourcis (10, 50, max)
- Toggle pile/face
- Bouton "Flip!" → POST → afficher résultat avec confettis si gain
- Historique des 20 derniers flips en dessous (mini-table)
- Accordéon "Vérifier le tirage" qui montre `seed_hash`, `server_seed`, formule

Pas de framework nécessaire. ~250 lignes de Vue + CSS, faisable en un soir.

### 3.6 Banque casino & monitoring

Le `casino_bank` doit avoir un solde positif et géré. Ajouter :
- Dashboard admin `/admin/casino` : solde casino_bank, P&L cumulé (par jeu), nombre de rounds par jour, RTP réel observé vs théorique
- Alerte email si solde casino_bank < seuil (configurable, ex: 1000 CAMP)
- Bouton "Recharger depuis treasury" qui fait `adminTransfer(treasury, casino_bank, X)`

---

## 4. Module Casino — Roulette

### 4.1 Concept

Roulette européenne (1 zéro, 37 cases : 0, 1-36). Le user place une ou plusieurs mises sur des "spots" (numéro, rouge/noir, pair/impair, douzaines, etc.), un seul spin résout l'ensemble.

L'edge est mécanique : payout d'un numéro plein = 35:1, mais probabilité de 1/37 → edge maison = 1/37 ≈ 2.7%. Pas besoin de configurer un edge artificiel comme pour le coinflip.

### 4.2 Schéma DB

Un spin = N mises agrégées, payout net.

```sql
CREATE TABLE roulette_spins (
  id              SERIAL PRIMARY KEY,
  username        VARCHAR(64) NOT NULL REFERENCES users(username),
  total_bet       BIGINT NOT NULL,         -- somme des mises
  total_payout    BIGINT NOT NULL DEFAULT 0,
  net_pnl         BIGINT NOT NULL DEFAULT 0,  -- = total_payout - total_bet

  bets_json       TEXT NOT NULL,           -- [{ "spot": "red", "amount": 10 }, ...]
  outcome_number  INT NULL,                -- 0..36
  outcome_color   VARCHAR(8) NULL,         -- 'red' | 'black' | 'green'

  client_seed     VARCHAR(64) NOT NULL,
  rng_seed_id     INT NOT NULL REFERENCES rng_seeds(id),

  status          VARCHAR(16) NOT NULL DEFAULT 'settled',
  ts              TIMESTAMP DEFAULT NOW(),
  tx_hash_lock    VARCHAR(66) NULL,
  tx_hash_payout  VARCHAR(66) NULL
);
CREATE INDEX idx_roulette_user ON roulette_spins(username, ts DESC);
```

### 4.3 Types de mises supportés (V1)

| Spot | Format | Payout | Proba | Edge |
|---|---|---|---|---|
| Numéro plein | `"n=17"` | 35:1 | 1/37 | 2.7% |
| Rouge / Noir | `"red"`, `"black"` | 1:1 | 18/37 | 2.7% |
| Pair / Impair | `"even"`, `"odd"` | 1:1 | 18/37 | 2.7% |
| Manque / Passe | `"low"` (1-18), `"high"` (19-36) | 1:1 | 18/37 | 2.7% |
| Douzaines | `"dozen=1"` (1-12), `"dozen=2"`, `"dozen=3"` | 2:1 | 12/37 | 2.7% |
| Colonnes | `"col=1"`, `"col=2"`, `"col=3"` | 2:1 | 12/37 | 2.7% |

Tu peux ajouter splits/streets/corners en V2 si besoin.

### 4.4 Logique de résolution

```python
# services/roulette.py
RED_NUMBERS = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}

def number_color(n: int) -> str:
    if n == 0: return "green"
    return "red" if n in RED_NUMBERS else "black"

def evaluate_bet(bet: dict, outcome: int) -> int:
    """Retourne le payout (mise incluse) si gagnant, 0 sinon."""
    spot, amount = bet["spot"], bet["amount"]
    color = number_color(outcome)

    if spot.startswith("n="):
        return amount * 36 if int(spot[2:]) == outcome else 0
    if spot == "red":  return amount * 2 if color == "red" else 0
    if spot == "black": return amount * 2 if color == "black" else 0
    if spot == "even": return amount * 2 if outcome != 0 and outcome % 2 == 0 else 0
    if spot == "odd":  return amount * 2 if outcome % 2 == 1 else 0
    if spot == "low":  return amount * 2 if 1 <= outcome <= 18 else 0
    if spot == "high": return amount * 2 if 19 <= outcome <= 36 else 0
    if spot.startswith("dozen="):
        d = int(spot.split("=")[1])
        return amount * 3 if outcome != 0 and (outcome - 1) // 12 == d - 1 else 0
    if spot.startswith("col="):
        c = int(spot.split("=")[1])
        return amount * 3 if outcome != 0 and (outcome - 1) % 3 == c - 1 else 0
    return 0
```

### 4.5 Flow on-chain : 1 mise + 1 payout net

Pour éviter 1 tx par spot misé, on agrège : 1 lock = somme des mises, 1 release = payout total (ou 0).

```python
# routers/roulette.py
@router.post("/casino/roulette/spin")
def spin(body: RouletteIn, user=Depends(current_user), db=Depends(get_db)):
    total_bet = sum(b["amount"] for b in body.bets)
    if total_bet < CASINO["roulette"]["min_bet"]:
        raise HTTPException(400, "Mise totale trop faible")
    # ... validations spots ...

    seed_hash, seed_id = randomness.commit(db, "roulette")
    tx_lock = escrow.lock(db, user, "casino_bank", total_bet,
                          f"roulette seed_id={seed_id}")

    server_seed, combined = randomness.reveal(db, seed_id, body.client_seed)
    outcome = randomness.derive_int(combined, 37)   # 0..36

    total_payout = sum(evaluate_bet(b, outcome) for b in body.bets)

    tx_payout = None
    if total_payout > 0:
        tx_payout = escrow.release(db, "casino_bank", user, total_payout,
                                    f"roulette seed_id={seed_id}")

    spin_ = RouletteSpin(
        username=user.username, total_bet=total_bet, total_payout=total_payout,
        net_pnl=total_payout - total_bet,
        bets_json=json.dumps(body.bets),
        outcome_number=outcome, outcome_color=number_color(outcome),
        client_seed=body.client_seed, rng_seed_id=seed_id,
        tx_hash_lock=tx_lock, tx_hash_payout=tx_payout,
    )
    db.add(spin_); db.commit(); db.refresh(spin_)
    return {...}
```

### 4.6 Front : tapis + animation roue

**Pas de framework Vue pour roulette mature aujourd'hui.** Options :

1. **Composant maison** (recommandé) :
   - Tapis = grille HTML/CSS classique (~100 lignes CSS pour reproduire le layout standard)
   - Animation roue = SVG ou CSS keyframes (rotation avec `cubic-bezier`)
   - Phaser/PixiJS overkill pour ça

2. **`react-casino-roulette`** existe mais c'est React, ne convient pas.

3. **HTML5 vanilla + wrapper Vue** : tu peux importer une lib JS comme [winwheel.js](https://github.com/zarocknz/javascript-winwheel) pour la roue et la wrapper dans un composant Vue. ~50 lignes de glue.

Mon conseil : composant maison. Pour un casino "entre potes" avec 7 types de mises basiques, tu auras plus vite fini en codant à la main qu'en intégrant une lib. Animation roue avec CSS :

```vue
<div class="wheel" :style="{ transform: `rotate(${rotation}deg)`, transition: 'transform 4s cubic-bezier(.2,.8,.3,1)' }">
  <!-- 37 spans positionnés en cercle, ou juste un SVG -->
</div>
```

Mise à jour de `rotation` lorsque la réponse arrive : calculer l'angle final qui pointe vers `outcome_number`.

### 4.7 Limites V1

- 1 spin = 1 joueur (pas de multi-table avec plusieurs joueurs autour). Si tu veux du multi-joueur sur la même roue, c'est un mode "live" qui nécessite WebSockets + agenda fixe pour le spin (ex: spin toutes les 30s). À cibler en V2.

---

## 5. Module Casino — Poker

### 5.1 Pourquoi ce module est spécifique

Le poker casse toutes les hypothèses du projet :
- **Multi-joueurs synchrones** (3 à 8 à une table) → WebSockets obligatoires
- **Nombreuses actions par main** (check, call, raise, fold, all-in) → impossible de faire on-chain par action
- **Tours en temps réel** avec timer → état serveur complexe
- **Cartes cachées** par joueur → pas de "vue partagée" simple

Décision claire : **état du jeu off-chain (en DB + en mémoire serveur), mouvements on-chain uniquement au sit-in (deposit) et sit-out (withdraw)**.

### 5.2 Bibliothèques recommandées

**Backend :**
- [`treys`](https://github.com/ihendley/treys) (Python) — évaluation de mains 5/7 cartes ultra-rapide, MIT. *Indispensable*, ne réimplémente pas le hand evaluator toi-même (sujet horrible : straight wheels, kickers, équivalences).
- [`pokerengine`](https://github.com/Ishinoshita/pokerengine) ou [`pypokerengine`](https://github.com/ishikota/PyPokerEngine) — moteur de tour de jeu complet (street progression, side pots, etc.) pour Texas Hold'em. Apporte beaucoup mais pas testé récemment, attention au fork.
- Alternative : coder l'engine toi-même (~800 lignes Python) en utilisant `treys` juste pour l'évaluation. Plus de contrôle, faisable.

**Frontend :**
- **Pas de framework "poker en Vue" mature.** Repo `vue-poker` GitHub est mort.
- Composants Vue maison : table (canvas ou SVG), cartes (composant `<PlayingCard suit="h" rank="A"/>`), joueurs (avatars + stack + bouton actuel), actions (call/raise/fold + slider).
- Sprite des cartes : [`svg-cards`](https://github.com/htdebeer/SVG-cards) (sprites SVG MIT, 52 cartes prêtes), ou utilise Unicode (♠♥♦♣) avec du CSS.
- ~600-800 lignes de Vue pour un client poker propre.

### 5.3 Schéma DB

```sql
-- Une table de poker, persistante. Plusieurs tables en parallèle.
CREATE TABLE poker_tables (
  id             SERIAL PRIMARY KEY,
  name           VARCHAR(64) NOT NULL,
  blind_small    INT NOT NULL,            -- en CAMP
  blind_big      INT NOT NULL,
  min_buyin      INT NOT NULL,
  max_buyin      INT NOT NULL,
  max_players    INT NOT NULL DEFAULT 6,
  status         VARCHAR(16) NOT NULL DEFAULT 'open',
  -- 'open' | 'closed' (close = ne plus accepter de sit-in, mais finir les mains en cours)
  created_at     TIMESTAMP DEFAULT NOW()
);

-- Un siège occupé par un joueur. stack = CAMP devant lui à table (off-chain).
CREATE TABLE poker_sessions (
  id             SERIAL PRIMARY KEY,
  table_id       INT NOT NULL REFERENCES poker_tables(id),
  username       VARCHAR(64) NOT NULL REFERENCES users(username),
  seat           INT NOT NULL,            -- 0..max_players-1
  stack          BIGINT NOT NULL,         -- stack actuel
  initial_stack  BIGINT NOT NULL,         -- buy-in initial
  joined_at      TIMESTAMP DEFAULT NOW(),
  left_at        TIMESTAMP NULL,
  tx_hash_buyin     VARCHAR(66) NULL,
  tx_hash_cashout   VARCHAR(66) NULL,
  UNIQUE(table_id, seat, left_at)        -- un siège libre quand left_at IS NOT NULL
);
CREATE INDEX idx_poker_sessions_active ON poker_sessions(table_id, left_at);

-- Chaque main complète jouée.
CREATE TABLE poker_hands (
  id            SERIAL PRIMARY KEY,
  table_id      INT NOT NULL REFERENCES poker_tables(id),
  hand_number   INT NOT NULL,            -- séquentiel par table
  dealer_seat   INT NOT NULL,
  board_cards   VARCHAR(20),             -- ex: 'Ah Kd 7s 2c Th' (post-river)
  pot           BIGINT NOT NULL DEFAULT 0,
  winners_json  TEXT NULL,               -- [{"username": "Hugo", "amount": 120, "hand": "two pair"}]
  hand_log      TEXT NOT NULL,           -- JSON de toutes les actions (street/action/amount)
  rng_seed_id   INT NOT NULL REFERENCES rng_seeds(id),  -- pour le deck
  started_at    TIMESTAMP DEFAULT NOW(),
  ended_at      TIMESTAMP NULL,
  UNIQUE(table_id, hand_number)
);

-- État volatile en cours de partie : qui a quelle main, etc.
-- Ces données sont sensibles (révèlent les cartes). À garder server-side uniquement.
CREATE TABLE poker_hand_holes (
  hand_id      INT NOT NULL REFERENCES poker_hands(id),
  username     VARCHAR(64) NOT NULL,
  hole_cards   VARCHAR(8) NOT NULL,      -- ex: 'Ah Kd'
  PRIMARY KEY (hand_id, username)
);
```

### 5.4 Architecture runtime

```
┌──────────────────┐  WebSocket  ┌────────────────────────┐
│   Vue Client     │ ◄─────────► │  FastAPI WebSocket     │
│ - subscribe/play │             │  /ws/poker/{table_id}  │
└──────────────────┘             └───────────┬────────────┘
                                             │
                                             ▼
                              ┌────────────────────────────┐
                              │ TableManager (in-memory)   │
                              │  - state machine par table │
                              │  - action queue            │
                              │  - timer par tour          │
                              └───────────┬────────────────┘
                                          │
                                          ▼
                                  ┌───────────────┐
                                  │  Postgres     │
                                  │  (persist)    │
                                  └───────────────┘
```

Le serveur FastAPI tient en mémoire une instance `TableManager` par table active. Lors des arrêts/redéploiements, l'état est reconstruit depuis la DB (`poker_sessions` actifs, dernière main en cours), ou la main en cours est annulée avec refund (selon politique).

**Caveat critique** : si le backend tourne en plusieurs instances (scale horizontal), le state in-memory ne fonctionne plus. Soit on garde 1 instance (suffisant pour 7 potes), soit on passe par Redis pour le state partagé. Pour CamplongCoin v1, 1 instance suffit largement, mais documenter cette limite.

### 5.5 Endpoints HTTP + WebSocket

```
# HTTP — gestion lobby & sit-in
POST   /casino/poker/tables               créer une table (admin only)
GET    /casino/poker/tables               liste des tables (avec joueurs courants)
POST   /casino/poker/tables/{id}/sit      sit-in (buy-in, lock fonds vers poker_bank)
POST   /casino/poker/tables/{id}/leave    sit-out (cashout stack actuel)
GET    /casino/poker/tables/{id}/state    snapshot state (utile au reload, hors mains en cours)
GET    /me/poker/history                  mes mains jouées

# WebSocket — gameplay
WS     /ws/poker/{table_id}
       client → server :
         {"action": "subscribe"}
         {"action": "play", "move": "fold" | "check" | "call" | "raise", "amount": int}
       server → client :
         {"type": "state", ...}              # snapshot complet (au connect)
         {"type": "deal_hole", "cards": "Ah Kd"}    # privé, à toi seulement
         {"type": "action", "username": "Alice", "move": "raise", "amount": 20}
         {"type": "deal_board", "cards": "..."}    # flop/turn/river
         {"type": "hand_end", "winners": [...], "showdown": {...}}
         {"type": "timer", "username": "Hugo", "remaining_ms": 28000}
```

### 5.6 Cycle d'une main

```
1. État de table : N joueurs sit-in avec stack ≥ blind_big
2. Allocate next dealer button (rotation).
3. Commit RNG seed pour le deck.
4. Shuffle deck déterministe depuis seed.
5. Post small blind & big blind (déduits des stacks).
6. Distribute hole cards (privées via WS).
7. Pre-flop betting round (chaque joueur agit en ordre).
8. Flop (3 cartes board) → betting round.
9. Turn (1 carte) → betting round.
10. River (1 carte) → betting round.
11. Showdown : eval treys, distribute pot (gérer side pots si all-in).
12. Update stacks, persiste hand + holes.
13. Reveal RNG seed → vérifiabilité du deck.
14. Goto 2 (sauf si <2 joueurs avec stack > 0).
```

Si un joueur déconnecte / timeout : auto-fold à son tour. Si tout le monde sauf un fold, gagne le pot direct (pas de showdown).

### 5.7 Sit-in / Sit-out on-chain

```python
@router.post("/casino/poker/tables/{table_id}/sit")
def sit_in(table_id: int, body: SitInIn, user=Depends(current_user), db=Depends(get_db)):
    table = db.get(PokerTable, table_id)
    if not table or table.status != "open":
        raise HTTPException(400, "Table non disponible")
    if body.buyin < table.min_buyin or body.buyin > table.max_buyin:
        raise HTTPException(400, "Buy-in hors limites")
    # Vérifier siège libre
    active = db.query(PokerSession).filter(
        PokerSession.table_id == table_id, PokerSession.left_at.is_(None)
    ).all()
    if len(active) >= table.max_players:
        raise HTTPException(400, "Table pleine")
    if any(s.username == user.username for s in active):
        raise HTTPException(400, "Déjà à cette table")
    seat = next_free_seat(active, table.max_players)

    # Lock
    tx = escrow.lock(db, user, "poker_bank", body.buyin,
                     f"poker table={table_id} buyin")
    sess = PokerSession(
        table_id=table_id, username=user.username, seat=seat,
        stack=body.buyin, initial_stack=body.buyin,
        tx_hash_buyin=tx,
    )
    db.add(sess); db.commit()
    # Notifier les autres joueurs via WS (broadcast)
    TableManager.get(table_id).broadcast({"type": "sit_in", "seat": seat, "username": user.username, "stack": body.buyin})
    return _session_dict(sess)


@router.post("/casino/poker/tables/{table_id}/leave")
def sit_out(table_id: int, user=Depends(current_user), db=Depends(get_db)):
    sess = db.query(PokerSession).filter(
        PokerSession.table_id == table_id,
        PokerSession.username == user.username,
        PokerSession.left_at.is_(None),
    ).first()
    if not sess: raise HTTPException(404, "Pas à cette table")

    mgr = TableManager.get(table_id)
    if mgr.is_user_in_current_hand(user.username):
        raise HTTPException(400, "Termine ta main en cours d'abord")

    final_stack = sess.stack
    if final_stack > 0:
        tx = escrow.release(db, "poker_bank", user, final_stack,
                            f"poker table={table_id} cashout")
        sess.tx_hash_cashout = tx
    sess.left_at = datetime.utcnow()
    db.commit()
    mgr.broadcast({"type": "sit_out", "username": user.username})
    return _session_dict(sess)
```

### 5.8 Front

Vues :
- **`PokerView.vue`** (lobby) : liste tables avec nb joueurs, blinds, bouton "rejoindre"
- **`PokerTableView.vue`** : la table elle-même
  - Vue circulaire de la table (SVG ou CSS positions absolues)
  - 6 sièges avec avatar / stack / cartes (dos ou face si showdown)
  - Board cards au centre
  - Pot affiché
  - Toi en bas avec tes hole cards visibles + actions
  - Slider pour raise
  - Chat optionnel (sympa entre potes, ~50 lignes WS supplémentaires)

Composants réutilisables :
- `<PlayingCard suit="h" rank="A" :hidden="true" />` 
- `<PlayerSeat :session="..." :is_current="..." :is_dealer="..." />`
- `<ActionBar :legal_actions="..." @action="onAction" />`

Effort estimé : ~1 semaine de dev frontend dédié si tu pars de zéro. C'est de loin le module le plus lourd.

### 5.9 Provably fair pour le deck

Le seed RNG permet de reproduire le shuffle du deck (Fisher-Yates seedé). Quand la main se termine, le serveur publie le seed → un joueur peut vérifier que le deck initial était bien `[As, 2h, ...]` etc. Si quelqu'un cheat en regardant la DB côté admin : la DB enregistre les `hole_cards` clairement, donc en interne c'est non-confidentiel — mais aucun joueur ne peut voir les cartes des autres pendant la partie via le client.

---

## 6. Module Bourse du Lait

### 6.1 Concept (récap)

AMM type Uniswap v1 : pool (`reserve_camp`, `reserve_milk`) avec `reserve_camp × reserve_milk = k` (constante). Prix marginal = `reserve_camp / reserve_milk`. Frais sur swap = 0.5% (ajustable), restant dans le pool donc augmente lentement `k`. Plusieurs pools possibles, un par "produit" laitier (LAIT-ENTIER, BEURRE, EMMENTAL...).

Pour amorcer : admin crée un pool avec une réserve initiale (X CAMP + Y unités de lait, prix initial = X/Y). Les "unités de lait" sont des bouteilles virtuelles trackées en DB — pas un token ERC-20 séparé (gain en simplicité).

**Bot dieu (chaos)** : process périodique qui modifie aléatoirement la réserve de lait du pool (jamais la réserve CAMP) → crée des chocs de prix sans casser la conservation des CAMP du système.

### 6.2 Schéma DB

```sql
CREATE TABLE milk_pools (
  id              SERIAL PRIMARY KEY,
  symbol          VARCHAR(32) NOT NULL UNIQUE,    -- 'LAIT-ENTIER'
  name            VARCHAR(64) NOT NULL,
  reserve_camp    BIGINT NOT NULL,                -- en CAMP entiers
  reserve_milk    BIGINT NOT NULL,                -- en milliunités (pour éviter floats : 1 bouteille = 1000)
  fee_pct         FLOAT NOT NULL DEFAULT 0.5,
  status          VARCHAR(16) NOT NULL DEFAULT 'active',  -- 'active' | 'paused'
  initial_camp    BIGINT NOT NULL,
  initial_milk    BIGINT NOT NULL,
  chaos_enabled   BOOLEAN NOT NULL DEFAULT TRUE,
  created_at      TIMESTAMP DEFAULT NOW(),
  system_role     VARCHAR(64) NOT NULL    -- ex 'milk_pool_lait_entier', sur users.system_role
);

-- Positions des users (stock de lait détenu)
CREATE TABLE milk_positions (
  username      VARCHAR(64) NOT NULL REFERENCES users(username),
  pool_id       INT NOT NULL REFERENCES milk_pools(id),
  balance_milk  BIGINT NOT NULL DEFAULT 0,    -- milliunités
  avg_cost      FLOAT NOT NULL DEFAULT 0,     -- prix moyen d'achat (pour P&L UI)
  PRIMARY KEY (username, pool_id)
);

CREATE TABLE milk_trades (
  id              SERIAL PRIMARY KEY,
  pool_id         INT NOT NULL REFERENCES milk_pools(id),
  username        VARCHAR(64) NOT NULL,
  side            VARCHAR(4) NOT NULL,           -- 'buy' | 'sell'
  amount_camp_in  BIGINT NOT NULL DEFAULT 0,     -- buy: CAMP misés, sell: 0
  amount_milk_in  BIGINT NOT NULL DEFAULT 0,     -- buy: 0, sell: milk vendu
  amount_camp_out BIGINT NOT NULL DEFAULT 0,     -- buy: 0, sell: CAMP reçus
  amount_milk_out BIGINT NOT NULL DEFAULT 0,     -- buy: milk reçu, sell: 0
  fee             BIGINT NOT NULL DEFAULT 0,
  price_before    FLOAT NOT NULL,
  price_after     FLOAT NOT NULL,
  ts              TIMESTAMP DEFAULT NOW(),
  tx_hash         VARCHAR(66) NULL               -- pour les buys (lock) ou sells (release)
);
CREATE INDEX idx_milk_trades_pool_ts ON milk_trades(pool_id, ts DESC);

CREATE TABLE milk_chaos_events (
  id             SERIAL PRIMARY KEY,
  pool_id        INT NOT NULL REFERENCES milk_pools(id),
  kind           VARCHAR(32) NOT NULL,        -- 'famine' | 'overstock' | 'spoil' | 'import'
  delta_milk     BIGINT NOT NULL,             -- signé (négatif = retrait)
  reserve_milk_before  BIGINT NOT NULL,
  reserve_milk_after   BIGINT NOT NULL,
  price_before   FLOAT NOT NULL,
  price_after    FLOAT NOT NULL,
  narrative      VARCHAR(256),                -- "Maladie de Lyon, -300 bouteilles"
  triggered_by   VARCHAR(16) NOT NULL,        -- 'bot' | 'admin'
  ts             TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_milk_chaos_pool_ts ON milk_chaos_events(pool_id, ts DESC);
```

### 6.3 Math AMM

```python
# services/amm.py
def buy_quote(pool, camp_in: int) -> dict:
    """Combien de milk je reçois en mettant `camp_in` CAMP."""
    fee = int(camp_in * pool.fee_pct / 100)
    camp_in_net = camp_in - fee
    new_reserve_camp = pool.reserve_camp + camp_in_net
    new_reserve_milk = pool.reserve_camp * pool.reserve_milk // new_reserve_camp  # k préservé
    milk_out = pool.reserve_milk - new_reserve_milk
    return {
        "milk_out": milk_out,
        "fee": fee,
        "price_before": pool.reserve_camp / pool.reserve_milk,
        "price_after":  new_reserve_camp / new_reserve_milk,
        "new_reserve_camp": new_reserve_camp,
        "new_reserve_milk": new_reserve_milk,
    }

def sell_quote(pool, milk_in: int) -> dict:
    new_reserve_milk = pool.reserve_milk + milk_in
    new_reserve_camp = pool.reserve_camp * pool.reserve_milk // new_reserve_milk
    camp_out_gross = pool.reserve_camp - new_reserve_camp
    fee = int(camp_out_gross * pool.fee_pct / 100)
    camp_out = camp_out_gross - fee
    return {
        "camp_out": camp_out,
        "fee": fee,
        "price_before": pool.reserve_camp / pool.reserve_milk,
        "price_after":  new_reserve_camp / new_reserve_milk,
        "new_reserve_camp": new_reserve_camp,
        "new_reserve_milk": new_reserve_milk,
    }
```

Attention overflows : avec des `BIGINT` Postgres et `int` Python ça tient, mais bien tester.

### 6.4 Endpoints

```
GET    /milk/pools                       liste pools actifs + prix courant + 24h change
GET    /milk/pools/{symbol}/chart?range  données pour graphique (snapshots horaires)
GET    /milk/pools/{symbol}/quote?side=buy|sell&amount=X     preview du swap
POST   /milk/pools/{symbol}/swap         exécute le swap (avec max_slippage_pct)
GET    /me/milk/positions                mes positions
GET    /me/milk/trades                   mon historique de trades

# Admin
POST   /admin/milk/pools                 créer un pool (admin uniquement)
PATCH  /admin/milk/pools/{id}            update fee_pct, chaos_enabled, status
POST   /admin/milk/pools/{id}/inject     injecter manuellement du lait (chaos manuel)
GET    /admin/milk/chaos                 historique des events chaos
```

### 6.5 Code swap

```python
@router.post("/milk/pools/{symbol}/swap")
def swap(symbol: str, body: SwapIn, user=Depends(current_user), db=Depends(get_db)):
    # Verrouiller le pool en SELECT FOR UPDATE pour éviter race conditions
    pool = db.query(MilkPool).filter(MilkPool.symbol == symbol)\
              .with_for_update().first()
    if not pool or pool.status != "active":
        raise HTTPException(404, "Pool indisponible")

    if body.side == "buy":
        q = buy_quote(pool, body.amount_camp_in)
        # Protection slippage
        expected_price = body.expected_price
        if expected_price and abs(q["price_after"] - expected_price) / expected_price \
                              > body.max_slippage_pct / 100:
            raise HTTPException(400, "Slippage trop élevé, retente")
        # Vérifier solde
        bal = get_balance_camp(user.address)
        if body.amount_camp_in > bal:
            raise HTTPException(400, f"Solde insuffisant ({bal} CAMP)")
        # Lock CAMP vers le pool
        tx = escrow.lock(db, user, pool.system_role, body.amount_camp_in,
                         f"milk swap buy {symbol}")
        # Mettre à jour réserves + position user
        pool.reserve_camp = q["new_reserve_camp"]
        pool.reserve_milk = q["new_reserve_milk"]
        pos = db.query(MilkPosition).filter_by(
            username=user.username, pool_id=pool.id
        ).with_for_update().first()
        if not pos:
            pos = MilkPosition(username=user.username, pool_id=pool.id,
                                balance_milk=0, avg_cost=0)
            db.add(pos); db.flush()
        # Update avg_cost pondéré
        old_value = pos.balance_milk * pos.avg_cost
        new_value = old_value + body.amount_camp_in
        pos.balance_milk += q["milk_out"]
        pos.avg_cost = new_value / pos.balance_milk if pos.balance_milk > 0 else 0
        # Trade log
        trade = MilkTrade(
            pool_id=pool.id, username=user.username, side="buy",
            amount_camp_in=body.amount_camp_in,
            amount_milk_out=q["milk_out"], fee=q["fee"],
            price_before=q["price_before"], price_after=q["price_after"],
            tx_hash=tx,
        )
        db.add(trade)
        db.commit()
        return _trade_dict(trade)

    elif body.side == "sell":
        # Vérifier que le user a assez de milk
        pos = db.query(MilkPosition).filter_by(
            username=user.username, pool_id=pool.id
        ).with_for_update().first()
        if not pos or pos.balance_milk < body.amount_milk_in:
            raise HTTPException(400, "Pas assez de lait à vendre")
        q = sell_quote(pool, body.amount_milk_in)
        # Vérifier que le pool a assez de CAMP
        pool_bal = get_balance_camp_for_role(db, pool.system_role)
        if q["camp_out"] > pool_bal:
            raise HTTPException(500, "Pool insuffisant — incohérence, alerte admin")
        # Mettre à jour positions + réserves
        pos.balance_milk -= body.amount_milk_in
        pool.reserve_camp = q["new_reserve_camp"]
        pool.reserve_milk = q["new_reserve_milk"]
        # Release CAMP du pool vers user
        tx = escrow.release(db, pool.system_role,
                             db.get(User, user.username),
                             q["camp_out"],
                             f"milk swap sell {symbol}")
        trade = MilkTrade(
            pool_id=pool.id, username=user.username, side="sell",
            amount_milk_in=body.amount_milk_in,
            amount_camp_out=q["camp_out"], fee=q["fee"],
            price_before=q["price_before"], price_after=q["price_after"],
            tx_hash=tx,
        )
        db.add(trade)
        db.commit()
        return _trade_dict(trade)
```

`SELECT FOR UPDATE` sur le pool est crucial pour éviter qu'Alice et Hugo qui swappent en même temps voient le même `reserve_*` et créent des incohérences (front-running / TOCTOU classique sur AMM).

### 6.6 Bot chaos

```python
# services/chaos_bot.py
import random
from apscheduler.schedulers.background import BackgroundScheduler

NARRATIVES = {
    "famine":    ("famine_negative", "Sécheresse en Normandie, -{pct}% du stock"),
    "spoil":     ("famine_negative", "Lot du 14 contaminé, retrait sanitaire de {n} bouteilles"),
    "overstock": ("famine_positive", "Surproduction en Bretagne, +{n} bouteilles offertes"),
    "import":    ("famine_positive", "Import suisse exceptionnel, +{pct}% du stock"),
}

def tick():
    """Appelé périodiquement par scheduler. Décide ou pas d'agir."""
    with SessionLocal() as db:
        for pool in db.query(MilkPool).filter(
            MilkPool.status == "active", MilkPool.chaos_enabled == True
        ).all():
            # Petite chance par tick
            if random.random() > 0.05:   # 5% par tick
                continue
            apply_chaos(db, pool)

def apply_chaos(db, pool):
    kind = random.choices(
        ["famine", "spoil", "overstock", "import"],
        weights=[2, 3, 2, 3], k=1
    )[0]
    if kind in ("famine", "import"):
        # variation par pourcentage du stock
        pct = random.uniform(5, 25)
        delta = int(pool.reserve_milk * pct / 100)
        if kind == "famine": delta = -delta
        narrative = NARRATIVES[kind][1].format(pct=round(pct, 1))
    else:
        # variation absolue
        n = random.randint(50, 500)
        delta = -n if kind == "spoil" else n
        narrative = NARRATIVES[kind][1].format(n=n)

    # Bornes : ne jamais vider complètement (sinon prix = ∞)
    new_milk = pool.reserve_milk + delta
    if new_milk < 1000:    # garde-fou
        return

    price_before = pool.reserve_camp / pool.reserve_milk
    pool.reserve_milk = new_milk
    price_after = pool.reserve_camp / pool.reserve_milk

    db.add(MilkChaosEvent(
        pool_id=pool.id, kind=kind, delta_milk=delta,
        reserve_milk_before=pool.reserve_milk - delta,
        reserve_milk_after=pool.reserve_milk,
        price_before=price_before, price_after=price_after,
        narrative=narrative, triggered_by="bot",
    ))
    db.commit()
    # Optionnel : push notification temps réel via WS si user connecté

# Au démarrage de FastAPI :
scheduler = BackgroundScheduler()
scheduler.add_job(tick, "interval", minutes=15, id="milk_chaos")
scheduler.start()
```

Note importante : **le bot ne touche que `reserve_milk`, jamais `reserve_camp`**. C'est ce qui préserve la propriété "somme nulle des CAMP dans le système". Quand la famine retire 300 bouteilles, le prix monte parce que `k` reste virtuellement inchangé (en pratique, k = reserve_camp × nouvelle reserve_milk, donc k bouge aussi, mais la quantité totale de CAMP dans tout le système reste fixe).

### 6.7 Snapshot pour graphique

Pour le chart, on log un snapshot toutes les heures (cron):

```sql
CREATE TABLE milk_price_history (
  pool_id      INT NOT NULL REFERENCES milk_pools(id),
  ts           TIMESTAMP NOT NULL,
  price        FLOAT NOT NULL,
  reserve_camp BIGINT NOT NULL,
  reserve_milk BIGINT NOT NULL,
  PRIMARY KEY (pool_id, ts)
);
```

Le placeholder `MilkView.vue` actuel a déjà un graphique SVG sympa — le brancher dessus. Récupérer `/milk/pools/{symbol}/chart?range=24h` → array de `{ts, price}`, renderer en SVG path.

### 6.8 Front

- **`MilkHomeView.vue`** : grid des pools avec prix courant + variation 24h + sparkline
- **`MilkTradeView.vue`** : un pool sélectionné
  - Big graph (chart.js, ou ton SVG actuel adapté)
  - Buy/sell tabs
  - Input avec preview quote en live (debounced GET `/quote`)
  - Slider de slippage tolérance
  - Bouton "Swap" → POST
  - Tape de trades récents
  - Tape d'événements chaos avec narrative (sympa pour la lore)
  - Position personnelle : balance + P&L (valeur courante - avg_cost * balance)

---

## 7. Points d'attention

### 7.1 Sécurité : escrow et comptes système

**Risque** : si la clé privée de la treasury (`TREASURY_PRIVATE_KEY`) fuit, tout est compromis — y compris les fonds dans `casino_bank`, `bets_escrow`, etc. (puisque l'admin peut tout bouger via `adminTransfer`).

**Mitigations** :
- Garder les clés privées des comptes système chiffrées avec une MASTER_KEY différente de celle des users si possible (compartimenter).
- Logger tous les `adminTransfer` qui ne suivent pas un flow métier connu (audit manuel).
- En mainnet (pas testnet) : multi-sig sur le contract owner. Avec un Gnosis Safe par exemple.

### 7.2 RNG vérifiable : limites

Le commit-reveal protège contre un admin qui changerait le résultat après-coup. Il **ne protège pas** contre un admin qui :
1. Tire `seed`, calcule l'outcome.
2. Si l'outcome est défavorable pour la banque, ne commit pas et redémarre.

Pour éviter ça : le `commit` doit être atomique avec une étape antérieure visible (ex: l'utilisateur a déjà envoyé sa mise). Si l'admin "annule" un round déjà commité, ça doit apparaître dans `rng_seeds` comme un seed `unrevealed`. Donc l'admin doit pouvoir prouver pour chaque seed commit : soit il est revealed (et le résultat matche), soit la mise n'a pas été prise (annulation visible).

Pour l'admin lui-même (toi), c'est OK puisque tu joues entre potes et tu as zéro intérêt à tricher. Pour un produit ouvert, il faudrait un VRF on-chain (Chainlink) ou un commit-reveal en deux étapes vraiment séparées.

### 7.3 Goulot d'étranglement on-chain

Base Sepolia confirme en ~2s, OK pour un volume modeste. Mais :
- **Roulette en mode live multi-joueur** : si 5 personnes lancent un spin chacune en 10s, c'est 10 tx en 10s sur le même nonce treasury. Le code actuel gère via `SELECT FOR UPDATE` sur le nonce, donc les tx sont sérialisées. À 1 tx/2s tu peux faire ~30 spins/min max sur l'ensemble du système. C'est le plafond.
- **Bourse du lait** : si tout le monde swap en panique pendant un chaos event, même problème.

**Mitigations** :
- Throttling côté API (rate limit par user, ex: 1 action/2s par user)
- En cas de pic : batcher les tx (1 tx multi-call ou plusieurs `adminTransfer` dans la même tx via un contrat batcher — engineering effort)
- Mode dégradé : afficher "transaction en file d'attente, position X"

### 7.4 Cohérence DB ↔ blockchain

Le pattern actuel commit la tx on-chain puis la ligne `transactions` en DB. Si le backend crash entre les deux, la tx est faite mais pas enregistrée. Avec 5 modules en plus, ce risque se multiplie.

**Mitigation** :
- `admin_transfer()` doit insérer la ligne `transactions` dans la même transaction DB que la mise à jour métier (bet status, milk reserves, etc.), et ne commiter qu'à la fin.
- Si la tx on-chain réussit mais le commit DB échoue → la tx on-chain est "perdue" (le user n'a pas son objet métier mais a perdu son CAMP). Solution : un job de réconciliation qui scanne les tx_hash absents en DB depuis le bloc N → log et re-rejouer ou alerter.

### 7.5 Audit comptable de bout en bout

Avec 5 modules + 6 comptes système + N users, un cron quotidien :

```python
# scripts/audit.py
total_supply = 1_000_000
sum_all = (
    get_balance_camp(treasury.address)
    + sum(get_balance_camp(s.address) for s in system_accounts(db))
    + sum(get_balance_camp(u.address) for u in regular_users(db))
)
if abs(total_supply - sum_all) > 1:
    alert_admin(f"INCOHERENCE: total_supply={total_supply}, observed={sum_all}")
```

À lancer 1×/jour. Si écart : enquête immédiate.

### 7.6 Gestion des dépendances aux comptes système

Plusieurs modules dépendent de comptes système nominés. Si l'admin supprime accidentellement le `casino_bank` du backoffice, tous les coinflips échouent.

**Mitigation** :
- Empêcher la suppression d'un compte système référencé par une table active (poker_sessions ouvertes, bets matchés, milk_pools actifs).
- Au démarrage du backend, check que tous les comptes système requis existent. Si non, log critical et refuser de servir les routes concernées.

### 7.7 Tests

Les modules monétaires demandent des tests automatisés sérieux, plus que ce qu'il y a aujourd'hui (rien d'automatisé visible). Suggéré :
- Tests unitaires des math (AMM, evaluation roulette, treys poker eval) — `pytest`
- Tests d'intégration des flows métier avec une chaîne mockée — `web3.py` a un provider de test (`EthereumTester`)
- Snapshots de la table `transactions` pour vérifier qu'une séquence d'actions produit le bon état comptable

Sans ces tests, dans 2 mois tu n'oseras plus toucher au code de la bourse du lait. Investir 2-3 jours dans une suite de base est rentabilisé tôt.

### 7.8 WebSockets et état multi-instance

Si tu scale le backend en plusieurs containers Scaleway, le `TableManager` in-memory devient un problème : un client peut se connecter à l'instance A, et le joueur d'à côté à l'instance B, et personne ne se voit. Pour 7 potes ça n'arrive jamais (1 instance suffit), mais à documenter.

Si besoin un jour : Redis pub/sub + state Redis pour le poker. Sinon "sticky session" sur l'instance qui héberge la table, à condition que ton load balancer supporte (Scaleway Serverless Containers : à vérifier).

### 7.9 Limites de l'edge maison

Tu as 2-2.7% d'edge sur le casino. Avec 7 potes qui jouent peu, **la variance domine largement l'edge**. Tu peux te retrouver avec une banque casino qui perd 5000 CAMP en une soirée même si statistiquement elle devrait gagner. Solutions :
- Banque casino bien capitalisée (ex: 10× la mise max permise) au lancement
- Cap par session/jour côté user (max bet quotidien)
- Affichage du "P&L casino" en transparence dans l'app (les gens savent à quoi ils jouent)

### 7.10 Spam / abus

Pour les paris : un user peut spammer des paris ridicules pour bloquer son propre CAMP en escrow et frustrer ses fonds. Limit du nb de paris ouverts par user (`maxOpenBetsPerUser` dans config). Pour le poker : limiter le nombre de tables qu'un user peut être assis simultanément.

---

## 8. Améliorations & autres jeux possibles

### 8.1 Jeux additionnels faciles à ajouter une fois le pattern établi

| Jeu | Effort | Pattern réutilisable |
|---|---|---|
| **Dés** (mise sur un nombre 1-6) | 1-2j | Identique au coinflip, juste `derive_int(combined, 6)` |
| **Crash** (mise + cashout dynamique) | 4-5j | Multiplicateur qui croît, joueur clique cashout avant explosion. Nécessite WS et un round commun. Provably fair via seed. |
| **Slots** (3 rouleaux d'emojis) | 2-3j | Pur RNG. Définir une table de payouts par combinaison. |
| **Plinko** | 3-4j | Bille qui rebondit sur des pegs, payouts en cases. Anim Phaser ou SVG. |
| **Mines** (style Stake) | 2-3j | Grille N×N, M mines cachées. Mise + révèle cases progressivement. Payout multiplicateur monte à chaque case sûre. |
| **Tour de Hanoï misé**, etc. | — | Aucune limite à l'imagination quand le pattern escrow est en place. |

### 8.2 Évolutions du module Casino

- **Tournois poker** : MTT avec elimination, classement final → prize pool.
- **Casino "live"** : roulette commune où plusieurs joueurs misent sur le même spin (à intervalle fixe). Plus social.
- **Programme de fidélité** : XP par CAMP misé, niveaux qui donnent des bonus (réduction d'edge, freebets).

### 8.3 Évolutions de la bourse du lait

- **Plusieurs pools = paniers d'arbitrage** : si tu as LAIT-ENTIER et LAIT-DEMI, un user peut arb entre les deux. Lore : "fais ton fromage avec du lait entier".
- **Liquidity providers** : actuellement seul l'admin amorce le pool. On peut autoriser les users à provisionner du CAMP+lait dans le pool (mint LP tokens) et toucher une part des fees. Très Uniswap.
- **Événements scriptés** : pas juste un bot random, mais une "saison" avec une narrative (été = surproduction = prix bas, hiver = pénurie). Plus de gameplay, moins d'arbitraire.
- **Marchés "futures"** : pari sur le prix du lait à T+30j. Recombine paris + bourse du lait, joli.

### 8.4 Évolutions cross-module

- **Leaderboards** : classement global (P&L total) + par module. Vue dédiée. Compétitif.
- **Achievements / badges** : "Premier sit-out positif au poker", "Plus de 1000 CAMP de fees lait payés", etc. Ne touche pas le CAMP mais ajoute du jeu.
- **Stats personnelles** : page "mon casino" / "mes paris" avec graphes, win rate, biggest hand, etc. Réutilise les tables existantes.
- **Notifs push** : web push pour "ton pari a été matché", "tu es invité à une partie de poker", "famine en cours, vends ton lait !"
- **Référent / parrainage** : si tu invites un pote, tu touches X% de ses fees pendant les 30 premiers jours.

### 8.5 Priorisation conseillée

Ordre suggéré pour les modules restants (le module **Paris** est déjà livré, cf. `AGENTS.md`) :

1. **Pile ou face** (§3) : permet de valider le pattern casino avec un jeu trivial. ~1-2 jours.
2. **Bourse du lait** (§6) : le plus original conceptuellement, gameplay fort. ~5-7 jours.
3. **Roulette** (§4) : techniquement proche du coinflip mais animation/UI plus lourdes. ~3-5 jours.
4. **Poker** (§5) : très gros chantier, à attaquer en dernier et en bloc dédié. ~10-15 jours minimum si bien fait.

Le pattern escrow + comptes système + RNG vérifiable (§1) reste un pré-requis transverse à mettre en place côté infra (en partie déjà fait pour Paris : `bets_escrow` créé, `services/escrow.py` réutilisable, migrations v4/v5 appliquées).