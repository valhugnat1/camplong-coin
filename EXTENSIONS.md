# EXTENSIONS.md — Module Poker (à venir)

Spec technique du seul module **non encore implémenté** : le **Poker**. Ce document complète `AGENTS.md` et ne le remplace pas.

> Modules **déjà livrés** (spec déplacée dans `AGENTS.md`) :
> - **Paris** (P2P bets — refonte mai 2026)
> - **Casino — Pile ou Face** (coinflip, edge configurable à chaud)
> - **Casino — Roulette** (européenne, 37 cases)
> - **Casino — Slots** (3 rouleaux, single payline, RTP ~90%)
> - **Bourse du Lait** (AMM x·y=k, bot chaos, templates éditables, cap volatilité)
>
> Les patterns transverses (comptes système, escrow, RNG vérifiable,
> `app_settings`) sont également documentés dans `AGENTS.md`.

> Lecture conseillée : `AGENTS.md` d'abord (architecture custodial, contrat, blockchain.py, schémas test/prod, tous les modules livrés).

---

## Table des matières

1. [Vue d'ensemble & points encore valables](#1-vue-densemble--points-encore-valables)
2. [Module Casino — Poker](#5-module-casino--poker)
3. [Points d'attention](#7-points-dattention)
4. [Améliorations & autres jeux possibles](#8-améliorations--autres-jeux-possibles)

> Les ancres des sections gardent leur numérotation d'origine (5, 7, 8) ;
> seule la TOC a été renumérotée. La section 6 (Bourse du Lait) a été
> supprimée puisque le module est livré.

---

## 1. Vue d'ensemble & points encore valables

### 1.1 Principes directeurs

Le projet est passé d'un seul concept simple (transfer P2P + market orders manuels) à une plateforme de jeu avec 5 produits livrés. Pour le poker, qui reste à faire, ces principes s'appliquent toujours.

**On-chain vs off-chain.** L'`adminTransfer` on-chain pour chaque mouvement est OK pour les transferts P2P (volume faible, latence ~2s). C'est intenable pour le poker (multiples mises par main). On adopte le pattern **escrow on-chain + livre off-chain** : les fonds bougent on-chain au sit-in et au sit-out, les actions de jeu intermédiaires (check/raise/fold) restent en DB.

| Module | Pattern | Tx on-chain par cycle | Statut |
|---|---|---|---|
| Paris | Escrow on-chain immédiat | 3 (mise creator + mise matcher + settlement) | ✅ livré |
| Pile ou Face | On-chain par flip | 2 (mise + payout) — 1 seule si perte (pas de release) | ✅ livré |
| Roulette | On-chain par spin | 2 (mises agrégées + payout net) — 1 seule si perte | ✅ livré |
| Slots | On-chain par spin | 2 (mise + payout) — 1 seule si perte | ✅ livré |
| Bourse du Lait | On-chain par swap | 2 (lock CAMP + release lait→CAMP) | ✅ livré |
| Poker | Sit-in / sit-out only | 2 par session (deposit + withdraw), peu importe le nombre de mains | à faire |

**Comptes système, escrow, RNG vérifiable.** Tous ces patterns sont en place et documentés dans `AGENTS.md` :
- `users.account_type='system'` + `system_role` (treasury, casino_bank, bets_escrow, milk_pool_*) — déjà créés par `seed_system_accounts.py`.
- `services/escrow.py::lock/release` — réutilisable tel quel pour le `poker_bank` (sit-in/sit-out).
- `services/randomness.py` (commit-reveal sha256 + `derive_int`) — réutilisable pour le shuffle du deck poker.

Côté refactoring de structure (split en sous-modules `routers/casino/poker.py` etc.) et migrations Alembic, ce n'est toujours pas fait — on est resté sur la convention plate + `migrate_v*.py` qui a tenu jusqu'à 15+ tables. C'est probablement le bon moment pour basculer si on attaque le poker, mais ce n'est pas un bloqueur.

### 1.2 Audit comptable (non implémenté)

Avec 5 modules qui bougent du CAMP, la question "où sont passés mes 1 000 000 CAMP" devient non triviale. Endpoint admin `/admin/audit` souhaitable :

```
treasury balance + system_account balances + sum(user balances) == total_supply ?
```

Si ça ne matche pas, il y a un bug. Cron 1×/jour + alerte email à l'admin si écart > 0.01 CAMP. Pas encore en place — à ajouter quand le poker arrive (multiplie les chemins).

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

### 8.3 Évolutions de la bourse du lait (module livré)

Le module est en place avec : multi-pools, bot chaos avec ~33 templates pondérés, cap de volatilité, analyse d'espérance banque (voir `services/milk.py::chaos_analysis`), valeur réalisable (sell-quote sur tout le stock) côté UI. Pistes d'évolution :

- **Plusieurs pools = paniers d'arbitrage** : créer `LAIT-DEMI`, `BEURRE`, `EMMENTAL` et laisser les users arb entre eux. Lore : "fais ton fromage avec du lait entier".
- **Liquidity providers** : actuellement seul l'admin amorce le pool. On peut autoriser les users à provisionner du CAMP+lait dans le pool (mint LP tokens) et toucher une part des fees. Très Uniswap. Nécessiterait une refonte du modèle de position (passer de `balance_milk` simple à un système de parts).
- **Événements scriptés / saisons** : à la place du bot random, séquencer une saison narrative (été = surproduction = prix bas, hiver = pénurie). Plus de gameplay, moins d'arbitraire. Les `MilkChaosTemplate` existants pourraient être groupés en "saisons" enableables.
- **Marchés "futures"** : pari sur le prix du lait à T+30j. Recombine module Paris + Bourse du Lait. Joli mais demande une infrastructure de settlement périodique.

### 8.4 Évolutions cross-module

- **Leaderboards** : classement global (P&L total) + par module. Vue dédiée. Compétitif.
- **Achievements / badges** : "Premier sit-out positif au poker", "Plus de 1000 CAMP de fees lait payés", etc. Ne touche pas le CAMP mais ajoute du jeu.
- **Stats personnelles** : page "mon casino" / "mes paris" avec graphes, win rate, biggest hand, etc. Réutilise les tables existantes.
- **Notifs push** : web push pour "ton pari a été matché", "tu es invité à une partie de poker", "famine en cours, vends ton lait !"
- **Référent / parrainage** : si tu invites un pote, tu touches X% de ses fees pendant les 30 premiers jours.

### 8.5 Priorisation conseillée

Modules déjà livrés (cf. `AGENTS.md`) : **Paris** (v2), **Pile ou face**, **Roulette**, **Slots**, **Bourse du Lait** (avec bot chaos + templates).

Reste :

1. **Poker** (§5) : très gros chantier, à attaquer en bloc dédié. ~10-15 jours minimum si bien fait. Demande WebSockets, state machine en mémoire, sprites de cartes, et un client Vue dédié.

Pré-requis déjà en place : `services/escrow.py` (réutilisable pour `poker_bank`), `services/randomness.py` (commit-reveal pour le shuffle deck), comptes système, `app_settings` pour les paramètres tweakables à chaud. À envisager avant le poker : migrer vers Alembic et brancher l'audit comptable §1.2.