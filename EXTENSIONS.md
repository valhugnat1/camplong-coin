# EXTENSIONS.md — Pistes d'évolutions transverses

Toutes les modules métier de CamplongCoin sont **livrés** et documentés dans `AGENTS.md`. Ce fichier liste ce qu'il reste à creuser : points d'attention cross-cutting (sécurité, audit comptable, tests, scalabilité) et idées d'évolutions / nouveaux jeux à ajouter.

> Modules livrés (spec dans `AGENTS.md`) :
> - **Paris** (P2P bets — refonte mai 2026)
> - **Casino — Pile ou Face** (coinflip, edge configurable à chaud)
> - **Casino — Roulette** (européenne, 37 cases)
> - **Casino — Slots** (3 rouleaux, single payline, RTP ~90%)
> - **Casino — Poker** (Texas Hold'em No-Limit, état off-chain, polling 2 s, RNG vérifiable)
> - **Bourse du Lait** (AMM x·y=k, bot chaos, templates éditables, cap volatilité)
>
> Les patterns transverses (comptes système, escrow, RNG vérifiable,
> `app_settings`, tables `poker_*` & cascade delete) sont documentés dans `AGENTS.md`.

> Lecture conseillée : `AGENTS.md` d'abord (architecture custodial, contrat, blockchain.py, schémas test/prod, tous les modules livrés).

---

## Table des matières

1. [Vue d'ensemble & audit comptable](#1-vue-densemble--audit-comptable)
2. [Points d'attention](#7-points-dattention)
3. [Améliorations & autres jeux possibles](#8-améliorations--autres-jeux-possibles)

> Les ancres des sections gardent leur numérotation d'origine (7, 8) ;
> seule la TOC a été renumérotée. Les sections 5 (Poker) et 6 (Bourse du
> Lait) ont été supprimées puisque les modules sont livrés.

---

## 1. Vue d'ensemble & audit comptable

### 1.1 Récap des patterns on-chain

Tous les modules métier sont livrés. Récap rapide des coûts on-chain par cycle de jeu (utile à garder en tête avant d'ajouter un nouveau jeu) :

| Module | Pattern | Tx on-chain par cycle |
|---|---|---|
| Paris | Escrow on-chain immédiat | 3 (mise creator + mise matcher + settlement) |
| Pile ou Face | On-chain par flip | 2 (mise + payout) — 1 seule si perte (pas de release) |
| Roulette | On-chain par spin | 2 (mises agrégées + payout net) — 1 seule si perte |
| Slots | On-chain par spin | 2 (mise + payout) — 1 seule si perte |
| Bourse du Lait | On-chain par swap | 2 (lock CAMP + release lait→CAMP) |
| Poker | Sit-in / sit-out only | 2 par session (deposit + withdraw), peu importe le nombre de mains jouées |

**Patterns transverses utilisables pour les futurs jeux** :
- `users.account_type='system'` + `system_role` (treasury, casino_bank, bets_escrow, poker_bank, milk_pool_*) — déjà créés par `seed_system_accounts.py`.
- `services/escrow.py::lock/release` — la primitive pour faire bouger des CAMP user ↔ compte système.
- `services/randomness.py` (commit-reveal sha256 + `derive_int`) — RNG vérifiable, réutilisable.
- `app_settings` + `services/settings.py` pour les paramètres tweakables à chaud sans redéploiement.

Côté refactoring (split en sous-modules, migrations Alembic), on est resté sur la convention plate + `migrate_v*.py` (16+ tables, 10 migrations à ce jour). À envisager si on attaque un module aussi gros que le poker ; pas un bloqueur aujourd'hui.

### 1.2 Audit comptable (non implémenté)

Avec 6 modules qui bougent du CAMP (paris, coinflip, roulette, slots, lait, poker), la question "où sont passés mes 1 000 000 CAMP" devient non triviale. Endpoint admin `/admin/audit` souhaitable :

```
treasury balance + system_account balances + sum(user balances) == total_supply ?
```

Si ça ne matche pas, il y a un bug. Cron 1×/jour + alerte email à l'admin si écart > 0.01 CAMP. Le poker rajoute un compte système (`poker_bank`) qu'il faut inclure dans la somme.

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

Tous les modules métier sont livrés (cf. `AGENTS.md`) : **Paris** (v2), **Pile ou face**, **Roulette**, **Slots**, **Poker** (Texas Hold'em No-Limit), **Bourse du Lait** (AMM + chaos bot).

Pistes ordonnées par impact / coût décroissant :

1. **Audit comptable** (§1.2) : cron quotidien + alerte si l'invariant `treasury + system_accounts + users == 1 000 000` casse. Faible coût, indispensable maintenant que 6 modules bougent du CAMP.
2. **Tests automatisés** (§7.7) : la combinatoire grandit, AMM + paris + casino + poker = beaucoup de chemins. Quelques jours de pytest sur la math (`amm`, `eval_5`, side-pots poker, `chaos_analysis`) déjà très rentables.
3. **Timeout auto-fold poker** : un joueur AFK bloque la table actuellement (mitigation = force-end admin). Background task qui auto-fold après N minutes ; aligner sur le pattern `_chaos_loop` côté `main.py`.
4. **Nouveaux jeux additionnels** (§8.1) : dés / crash / plinko / mines — tous reposent sur les primitives en place, ~quelques jours par jeu.
5. **Migration Alembic** : confort plus que nécessité ; 10 scripts `migrate_v*.py` à ce jour tiennent encore. À envisager si on dépasse 20.