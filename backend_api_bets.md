# API Bets — Spec attendue par le front

Le front fait ces appels. Implémenter côté backend conformément.

---

## 1. Conventions

- Authentification : `Authorization: Bearer <jwt>` sur **toutes** les routes
- Routes `/admin/*` : JWT admin obligatoire
- Routes `/bets/*`, `/me/bets` : JWT user obligatoire
- Erreurs : `{ "detail": "message lisible" }` avec status HTTP cohérent
- Dates : ISO 8601 UTC avec suffixe `Z` (ex : `"2026-05-28T18:00:00Z"`)
- Montants CAMP : entiers (BIGINT côté DB, `number` côté JSON)

---

## 2. Schéma JSON d'un Bet

Objet renvoyé par toutes les routes qui retournent un pari :

```json
{
  "id": 42,
  "creator_username": "hugo",
  "statement": "Emile va dire la phrase secrète avant samedi",
  "category": "Lifestyle",
  "deadline": "2026-05-28T18:00:00Z",

  "stake_creator": 20,
  "stake_opponent": 60,
  "odds_num": 1,
  "odds_den": 3,
  "creator_side": "yes",

  "opponent_username": null,
  "arbiter_username": "alice",
  "arbiter_fee_pct": 5,

  "status": "open",
  "resolution": null,
  "resolved_at": null,
  "resolved_by": null,

  "created_at": "2026-05-21T10:00:00Z",
  "matched_at": null,

  "tx_hash_lock_creator": "0xab12...",
  "tx_hash_lock_opponent": null,
  "tx_hash_payout_winner": null,
  "tx_hash_payout_arbiter": null
}
```

Valeurs autorisées :
- `status` : `"open" | "matched" | "resolved" | "cancelled" | "expired"`
- `creator_side` : `"yes" | "no"`
- `resolution` : `"yes" | "no" | "void" | null`

Pour `/me/bets` uniquement, chaque objet a un champ supplémentaire :
- `my_role` : `"creator" | "opponent" | "arbiter"`

---

## 3. Endpoints user

### `POST /bets` — Créer un pari

**Body :**
```json
{
  "statement": "Emile va dire la phrase...",
  "category": "Lifestyle",                  // ou null
  "deadline": "2026-05-28T18:00:00Z",
  "creator_side": "yes",                    // "yes" | "no"
  "stake_creator": 20,
  "odds_num": 1,
  "odds_den": 3,
  "arbiter_username": "alice",              // ou null
  "arbiter_fee_pct": 5                      // 0-50, ou 0 si pas d'arbitre
}
```

**Réponse :** objet Bet (status `"open"`, `tx_hash_lock_creator` populated)

**Validations backend :**
- `stake_creator` entre 1 et 1000 (config BETS)
- `(stake_creator * odds_den) % odds_num == 0` (pas de mise fractionnaire)
- `deadline` dans le futur
- Solde user >= `stake_creator`
- `arbiter_username` existe (si fourni) et != `creator_username`
- `arbiter_fee_pct` entre 0 et 50
- Nombre de paris ouverts du user < `BETS.maxOpenBetsPerUser` (anti-spam)

**Side-effect :** `escrow.lock(user, "bets_escrow", stake_creator, "bet #N stake creator")`

---

### `GET /bets?status=open&category=Sport` — Lister les paris

**Query params :**
- `status` (optionnel) : `"open" | "matched" | "resolved" | "cancelled" | "expired" | "all"` (défaut `"all"`)
- `category` (optionnel) : filtre par catégorie exacte

**Réponse :** `Bet[]` triés par `created_at DESC`

Note : pour la page liste publique, le front filtre `status=open`.

---

### `GET /bets/{id}` — Détail d'un pari

**Réponse :** objet Bet

**404** si introuvable.

---

### `POST /bets/{id}/match` — Prendre un pari

**Pas de body.**

**Réponse :** Bet mis à jour (status `"matched"`, `opponent_username` = user courant, `matched_at` set, `tx_hash_lock_opponent` populated)

**Validations backend :**
- Bet existe et `status == "open"`
- `user.username != bet.creator_username`
- `deadline > now()`
- Solde user >= `stake_opponent`

**Side-effect :** `escrow.lock(user, "bets_escrow", stake_opponent, "bet #N stake opponent")`

---

### `DELETE /bets/{id}` — Annuler son pari

**Pas de body.**

**Réponse :** `{ "status": "cancelled", "id": 42 }` ou objet Bet à jour (au choix, le front gère les deux).

**Validations backend :**
- Bet existe et `status == "open"`
- `user.username == bet.creator_username`

**Side-effect :** `escrow.release("bets_escrow", creator, stake_creator, "bet #N refund cancel")`

---

### `POST /bets/{id}/resolve` — Résoudre (arbitre désigné)

**Body :**
```json
{ "resolution": "yes" }
```
(ou `"no"`, ou `"void"`)

**Réponse :** Bet mis à jour (status `"resolved"`, `resolution` set, `resolved_at` set, `resolved_by` = user courant, tx hashes payout populés)

**Validations backend :**
- Bet existe et `status == "matched"`
- `user.username == bet.arbiter_username` (si pas d'arbitre désigné, retourner 403 avec message "Aucun arbitre, résolution admin requise")

**Side-effects :**
- Si `resolution == "void"` : refund deux côtés
- Sinon :
  - Calcul `pot = stake_creator + stake_opponent`
  - `arbiter_fee = pot * arbiter_fee_pct // 100`
  - `winner_payout = pot - arbiter_fee`
  - Détermine gagnant : `bet.creator_side == resolution ? creator : opponent`
  - `escrow.release("bets_escrow", winner, winner_payout, "bet #N winner")`
  - Si arbitre fee > 0 : `escrow.release("bets_escrow", arbiter, arbiter_fee, "bet #N arbiter fee")`

---

### `GET /me/bets` — Mes paris

**Réponse :** `Bet[]` enrichis d'un champ `my_role` :
```json
[
  { ...bet, "my_role": "creator" },
  { ...bet, "my_role": "opponent" },
  { ...bet, "my_role": "arbiter" }
]
```

Inclut tous les paris où le user est creator OU opponent OU arbiter, tous statuts confondus. Triés `created_at DESC`. Un même pari peut potentiellement apparaître plusieurs fois si le user a plusieurs rôles dessus (creator + arbiter — bien que ce cas soit interdit côté create). Si tu préfères dédupliquer, retourner le rôle prioritaire dans l'ordre creator > opponent > arbiter.

---

## 4. Endpoints admin

### `GET /admin/bets?status=...` — Tous les paris

Comme `/bets`, mais sans restriction de visibilité (admin voit tous statuts par défaut). Pas besoin de `my_role`.

---

### `POST /admin/bets/{id}/resolve` — Force-resolve

**Body :** `{ "resolution": "yes" | "no" | "void" }`

Comme `/bets/{id}/resolve` mais **sans** la contrainte sur l'arbitre désigné. Utilisé pour :
- Résoudre un pari sans arbitre désigné
- Override d'un arbitre absent ou en désaccord
- Cas tordus

Le champ `resolved_by` doit être set à `"__admin__"` ou similaire pour traçabilité.

---

### `POST /admin/bets/{id}/cancel` — Force-cancel

**Pas de body.**

Annule un pari quel que soit son statut courant (sauf `resolved`, qui est irréversible — retourner 400 si tentative).

Si `status == "open"` : refund creator.
Si `status == "matched"` : refund creator ET opponent.

---

### `DELETE /admin/bets/{id}` — Suppression définitive

Supprime la ligne en DB. **N'annule pas** les mouvements on-chain déjà faits — ce n'est qu'un nettoyage de la table. À réserver aux tests / paris erronés.

Refuser si `status == "matched"` ou `"resolved"` (les fonds sont escrowés ou ont été distribués, ça compromettrait l'audit). Force-cancel d'abord.

---

## 5. Endpoint annexe utilisé par le front

### `GET /users` — Annuaire

Déjà existant. Utilisé par `ParisCreateView` pour peupler le select "arbitre". Le front filtre côté client pour exclure `current_user` de la liste.

---

## 6. Notes d'implémentation

### Concurrence

Plusieurs users peuvent essayer de matcher le même pari simultanément. Le premier doit gagner, les autres reçoivent une erreur claire. Solution : `SELECT ... FOR UPDATE` sur la ligne `bets` dans la transaction du match.

### Cron jobs (rappel EXTENSIONS.md §2.8)

- Toutes les 10 min : refund les paris `open` dont la `deadline` est passée → status `expired`.
- Toutes les 6h : alerte email admin pour les paris `matched` dont la `deadline + 24h` est passée sans résolution.

Ces jobs sont indépendants des endpoints, mais leur absence laisse des fonds escrowés indéfiniment.

### Email notifications (cohérent avec le module market existant)

- Création d'un pari avec arbitre désigné → email à l'arbitre ("On t'a désigné comme juge pour : ...")
- Match d'un pari → email au créateur ("X a pris ton pari")
- Résolution → email aux deux parties (gagnant et perdant)

Ces notifications sont nice-to-have, pas bloquantes pour la v1.

### Atomicité escrow + DB

Le pattern actuel (cf. `users.py`/`admin.py` MarketOrder) : exécuter le `admin_transfer` on-chain **avant** de toucher au statut DB. Si la tx on-chain échoue, le statut reste cohérent. Garder ce pattern partout dans le bets router.