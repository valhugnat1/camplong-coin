"""
analytics.py — Agregations transverses pour le dashboard admin "Qui a fait quoi".

Principe central : la table `transactions` journalise TOUS les mouvements CAMP
avec des usernames sentinelles (`__treasury__`, `__bets_escrow__`, `__casino_bank__`,
`__milk_pool_<symbol>__`, `__poker_bank__`). On s'en sert pour separer proprement :

  - l'argent VRAIMENT injecte de l'exterieur    -> `__treasury__` -> user
    (onboarding 1000 CAMP, credits admin, orders 'buy' passes en done)
  - l'argent VRAIMENT retire                    -> user -> `__treasury__`
    (debits admin, orders 'sell' passes en done)
  - les mouvements internes de jeu              -> user <-> `__<role>__`

D'ou la definition du PnL "sans recharger", celle qui interesse l'admin :

    pnl = valeur_totale_actuelle - (solde_d_ouverture + depots - retraits)

avec, des deux cotes, la meme definition de la valeur :

    valeur = solde on-chain du wallet
           + valeur realisable des positions lait
           + CAMP bloques dans les paris en cours
           + stacks de poker en cours

Le solde on-chain seul ne suffit pas : quand un user achete du lait, ses CAMP
partent sur le compte systeme du pool, donc son wallet baisse alors qu'il n'a
rien perdu. Sans ce rattrapage, tout trader lait apparaitrait en perte.

`solde_d_ouverture` est RECONSTRUIT au cutoff depuis le ledger (voir
`_wallet_flows_since`), et non suppose egal au capital de depart : les joueurs
avaient deja une histoire au moment ou la periode commence (parties d'avant,
reset admin, recharges anterieures). Supposer 1000 CAMP a tous au depart
attribuait a la periode des gains et des pertes qui lui sont anterieurs.

La classification d'un mouvement de tresorerie est deduite de sa note, et
l'admin peut la corriger via `analytics_tx_labels` (table purement additive,
voir `classify` et `set_label`) : typiquement quand une mise de depart a ete
versee a la main apres coup et serait presentee a tort comme une recharge.
"""
import datetime
from typing import Optional

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from models import (
    User, Transaction, MilkPool, MilkPosition, MilkTrade,
    CoinflipRound, RouletteSpin, SlotsSpin, PokerSession,
    AnalyticsTxLabel,
)
from services import amm
from services.milk import MILK_UNIT
from services.coinflip import CASINO_BANK_ROLE
from services.poker import POKER_BANK_ROLE

# Debut de l'aventure : 22 aout 2026, 22h heure de Paris = 20h UTC.
# Les timestamps sont stockes en UTC (datetime.utcnow() / func.now()).
DEFAULT_SINCE = datetime.datetime(2026, 8, 22, 20, 0, 0)

TREASURY = "__treasury__"

# Les sentinelles sont construites par escrow.lock/release : `__<role>__`.
# On repart des constantes de role plutot que de reecrire les chaines, sinon un
# renommage cote service ferait silencieusement tomber ces agregations a zero.
# `bets_escrow` vit dans routers/bets.py (pas de service dedie) : on le duplique
# ici a dessein pour ne pas importer un router depuis un service.
BETS_ESCROW_ROLE = "bets_escrow"
BETS_ESCROW = f"__{BETS_ESCROW_ROLE}__"
POKER_BANK = f"__{POKER_BANK_ROLE}__"
CASINO_BANK = f"__{CASINO_BANK_ROLE}__"


def _sentinel(username: str) -> bool:
    """True pour les pseudo-comptes du ledger (`__treasury__`, `__casino_bank__`...)."""
    return username.startswith("__") and username.endswith("__")


def _sum_map(rows) -> dict:
    """[(cle, valeur), ...] -> {cle: int(valeur)}, en ignorant les None."""
    return {r[0]: int(r[1] or 0) for r in rows}


# ─── Flux externes (depots / retraits) ─────────────────

def _labels(db: Session) -> dict:
    """
    {tx_id: label} — les reclassifications manuelles de l'admin.

    Tolere que la table n'existe pas encore : si le backend est deploye avant
    d'avoir joue migrate_v11, on retombe simplement sur la classification
    automatique au lieu de renvoyer une 500. Le rollback est indispensable,
    sinon la session Postgres reste en erreur pour les requetes suivantes.
    """
    try:
        return {r[0]: r[1] for r in db.query(AnalyticsTxLabel.tx_id,
                                             AnalyticsTxLabel.label).all()}
    except SQLAlchemyError:
        db.rollback()
        return {}


def classify(tx: Transaction, labels: dict) -> tuple:
    """
    (label, source) pour un mouvement de tresorerie.

    Par defaut on se fie a la note posee par le backend a l'ecriture
    (`onboarding` pour la dotation initiale) ; l'admin peut corriger, typiquement
    quand une mise de depart a ete donnee a la main plus tard via /admin/credit
    et compte donc a tort comme une recharge.
    """
    manual = labels.get(tx.id)
    if manual:
        return manual, "manual"
    if tx.from_username == TREASURY:
        return ("onboarding" if (tx.note or "") == "onboarding" else "topup"), "auto"
    return "withdrawal", "auto"


def treasury_movements(db: Session):
    """Tous les mouvements user <-> tresorerie, du plus recent au plus ancien."""
    return (
        db.query(Transaction)
          .filter((Transaction.from_username == TREASURY)
                  | (Transaction.to_username == TREASURY))
          .order_by(Transaction.ts.desc())
          .all()
    )


def _external_flows(db: Session, since: datetime.datetime) -> dict:
    """
    Par user : capital de depart, recharges, retraits.

    Seuls les mouvements DANS la periode comptent : ceux d'avant sont deja
    absorbes par le solde d'ouverture reconstruit (`_wallet_flows_since`), les
    compter en plus les ferait compter deux fois.

    La distinction onboarding/topup n'influe plus sur le PnL (un CAMP recu est
    un CAMP recu, quel que soit son motif) : elle sert a repondre "qui a
    recharge", donc a ne pas presenter comme rechargeur celui dont la mise de
    depart a ete versee en retard.

    Les lignes etiquetees `ignore` sont exclues de tout.
    """
    labels = _labels(db)
    out: dict = {}

    def bucket(username: str) -> dict:
        return out.setdefault(username, {
            "starting_capital": 0, "topups": 0, "withdrawals": 0,
            "deposits": 0,
        })

    for tx in treasury_movements(db):
        label, _ = classify(tx, labels)
        if label == "ignore":
            continue
        if tx.ts is None or tx.ts < since:
            continue

        username = tx.to_username if tx.from_username == TREASURY else tx.from_username
        if _sentinel(username):
            continue  # mouvement tresorerie <-> compte systeme, pas un joueur

        b = bucket(username)
        amount = int(tx.amount or 0)

        if label == "onboarding":
            b["starting_capital"] += amount
            b["deposits"] += amount
        elif label == "topup":
            b["topups"] += amount
            b["deposits"] += amount
        elif label == "withdrawal":
            b["withdrawals"] += amount

    return out


def _escrow_net(db: Session, role_sentinel: str,
                before: Optional[datetime.datetime] = None) -> dict:
    """
    Par user : CAMP nets bloques chez un compte systeme donne
    (= somme des locks - somme des releases).

    `before` borne le calcul dans le passe, pour reconstituer ce qui etait
    bloque a un instant donne.
    """
    q_lock = db.query(Transaction.from_username, func.sum(Transaction.amount)) \
               .filter(Transaction.to_username == role_sentinel)
    q_rel = db.query(Transaction.to_username, func.sum(Transaction.amount)) \
              .filter(Transaction.from_username == role_sentinel)
    if before is not None:
        q_lock = q_lock.filter(Transaction.ts < before)
        q_rel = q_rel.filter(Transaction.ts < before)

    locked = _sum_map(q_lock.group_by(Transaction.from_username).all())
    released = _sum_map(q_rel.group_by(Transaction.to_username).all())
    return {u: locked.get(u, 0) - released.get(u, 0)
            for u in set(locked) | set(released)}


# ─── Solde d'ouverture (reconstruction au cutoff) ──────

def _wallet_flows_since(db: Session, since: datetime.datetime) -> dict:
    """
    Par user : CAMP entres et sortis du wallet depuis `since`.

    Exact : chaque mouvement on-chain passe par `admin_transfer` et est
    journalise dans `transactions` (tresorerie, escrows casino/paris/lait/poker,
    virements entre users). D'ou la reconstruction du solde d'ouverture :

        solde_au_cutoff = solde_actuel - entrees_depuis + sorties_depuis
    """
    ins = _sum_map(
        db.query(Transaction.to_username, func.sum(Transaction.amount))
          .filter(Transaction.ts >= since)
          .group_by(Transaction.to_username).all()
    )
    outs = _sum_map(
        db.query(Transaction.from_username, func.sum(Transaction.amount))
          .filter(Transaction.ts >= since)
          .group_by(Transaction.from_username).all()
    )
    return {u: {"in": ins.get(u, 0), "out": outs.get(u, 0)}
            for u in set(ins) | set(outs) if not _sentinel(u)}


def _pool_price_at(db: Session, pool: MilkPool,
                   since: datetime.datetime) -> float:
    """
    Prix d'une bouteille au moment du cutoff.

    Approximation assumee : on prend le prix du dernier trade avant `since`
    (`price_after`), a defaut celui du premier trade apres. Les evenements chaos
    survenus entre-deux ne sont pas rejoues — il faudrait un historique des
    reserves, que la base ne garde pas.
    """
    last = (db.query(MilkTrade)
              .filter(MilkTrade.pool_id == pool.id, MilkTrade.ts < since)
              .order_by(MilkTrade.ts.desc()).first())
    if last is not None:
        return float(last.price_after)
    first = (db.query(MilkTrade)
               .filter(MilkTrade.pool_id == pool.id, MilkTrade.ts >= since)
               .order_by(MilkTrade.ts.asc()).first())
    if first is not None:
        return float(first.price_before)
    return amm.current_price(pool.reserve_camp, pool.reserve_milk)


def _milk_opening(db: Session, since: datetime.datetime) -> dict:
    """
    Par user : valeur du stock de lait detenu au cutoff.

    Stock au cutoff = stock actuel - lait achete depuis + lait vendu depuis.
    """
    pools = {p.id: p for p in db.query(MilkPool).all()}
    prices = {pid: _pool_price_at(db, p, since) for pid, p in pools.items()}

    # Lait entre/sorti par les trades de la periode, par (user, pool).
    moves: dict = {}
    rows = (
        db.query(MilkTrade.username, MilkTrade.pool_id, MilkTrade.side,
                 func.coalesce(func.sum(MilkTrade.amount_milk_out), 0),
                 func.coalesce(func.sum(MilkTrade.amount_milk_in), 0))
          .filter(MilkTrade.ts >= since)
          .group_by(MilkTrade.username, MilkTrade.pool_id, MilkTrade.side)
          .all()
    )
    for username, pool_id, side, milk_out, milk_in in rows:
        d = moves.setdefault((username, pool_id), 0)
        # buy  : le user recoit du lait  -> il en avait moins avant
        # sell : le user en donne        -> il en avait plus avant
        moves[(username, pool_id)] = d + (int(milk_out or 0) if side == "buy"
                                          else -int(milk_in or 0))

    out: dict = {}
    for pos in db.query(MilkPosition).all():
        pool = pools.get(pos.pool_id)
        if pool is None:
            continue
        opening_milk = int(pos.balance_milk) - moves.get((pos.username, pos.pool_id), 0)
        if opening_milk <= 0:
            continue
        value = int(opening_milk * prices[pos.pool_id] / MILK_UNIT)
        out[pos.username] = out.get(pos.username, 0) + value
    return out


def _poker_opening(db: Session, since: datetime.datetime) -> dict:
    """
    Par user : CAMP assis a une table au cutoff.

    Approximation : on prend le buy-in (`initial_stack`), le stack exact a cet
    instant n'etant pas historise. Marginal en pratique — il faut etre assis a
    cheval sur le cutoff pour etre concerne.
    """
    rows = (
        db.query(PokerSession.username, func.sum(PokerSession.initial_stack))
          .filter(PokerSession.joined_at < since)
          .filter((PokerSession.left_at.is_(None)) | (PokerSession.left_at >= since))
          .group_by(PokerSession.username)
          .all()
    )
    return _sum_map(rows)


def _escrow_entries(db: Session, role_sentinel: str,
                    since: datetime.datetime) -> dict:
    """Par user : nombre de mises envoyees vers un compte systeme, sur la periode."""
    rows = (
        db.query(Transaction.from_username, func.count(Transaction.id))
          .filter(Transaction.to_username == role_sentinel, Transaction.ts >= since)
          .group_by(Transaction.from_username)
          .all()
    )
    return {r[0]: int(r[1] or 0) for r in rows}


def _escrow_pnl(db: Session, role_sentinel: str, since: datetime.datetime) -> dict:
    """Par user : recu - mise sur un compte systeme, sur la periode."""
    staked = _sum_map(
        db.query(Transaction.from_username, func.sum(Transaction.amount))
          .filter(Transaction.to_username == role_sentinel, Transaction.ts >= since)
          .group_by(Transaction.from_username).all()
    )
    won = _sum_map(
        db.query(Transaction.to_username, func.sum(Transaction.amount))
          .filter(Transaction.from_username == role_sentinel, Transaction.ts >= since)
          .group_by(Transaction.to_username).all()
    )
    return {
        u: {"staked": staked.get(u, 0),
            "won": won.get(u, 0),
            "pnl": won.get(u, 0) - staked.get(u, 0)}
        for u in set(staked) | set(won)
    }


# ─── Casino ────────────────────────────────────────────

def _casino_stats(db: Session, since: datetime.datetime) -> dict:
    """
    Par user : nombre de parties, volume mise, gains, PnL joueur.
    PnL joueur = payout - mise (positif = le joueur a battu la banque).
    """
    out: dict = {}

    def bucket(username: str) -> dict:
        return out.setdefault(username, {
            "plays": 0, "volume_camp": 0, "payout_camp": 0, "pnl_camp": 0,
            "coinflip": {"plays": 0, "volume_camp": 0, "pnl_camp": 0},
            "roulette": {"plays": 0, "volume_camp": 0, "pnl_camp": 0},
            "slots": {"plays": 0, "volume_camp": 0, "pnl_camp": 0},
        })

    games = [
        ("coinflip", CoinflipRound, CoinflipRound.bet_amount, CoinflipRound.payout),
        ("roulette", RouletteSpin, RouletteSpin.total_bet, RouletteSpin.total_payout),
        ("slots", SlotsSpin, SlotsSpin.bet_amount, SlotsSpin.payout),
    ]
    for name, model, bet_col, payout_col in games:
        rows = (
            db.query(
                model.username,
                func.count(model.id),
                func.coalesce(func.sum(bet_col), 0),
                func.coalesce(func.sum(payout_col), 0),
            )
            .filter(model.ts >= since)
            .group_by(model.username)
            .all()
        )
        for username, plays, volume, payout in rows:
            plays, volume, payout = int(plays), int(volume or 0), int(payout or 0)
            b = bucket(username)
            b[name] = {"plays": plays, "volume_camp": volume,
                       "pnl_camp": payout - volume}
            b["plays"] += plays
            b["volume_camp"] += volume
            b["payout_camp"] += payout
            b["pnl_camp"] += payout - volume

    return out


# ─── Bourse du lait ────────────────────────────────────

def _milk_trade_stats(db: Session, since: datetime.datetime) -> dict:
    """
    Par user : activite de trading sur la periode.

    `realized_camp` = CAMP encaisses sur les ventes - CAMP depenses sur les
    achats. C'est un flux net, donc negatif tant que le user est investi ;
    il devient le vrai PnL une fois additionne a la valeur du stock restant.
    """
    rows = (
        db.query(
            MilkTrade.username,
            MilkTrade.side,
            func.count(MilkTrade.id),
            func.coalesce(func.sum(MilkTrade.amount_camp_in), 0),
            func.coalesce(func.sum(MilkTrade.amount_camp_out), 0),
            func.coalesce(func.sum(MilkTrade.fee), 0),
        )
        .filter(MilkTrade.ts >= since)
        .group_by(MilkTrade.username, MilkTrade.side)
        .all()
    )

    out: dict = {}
    for username, side, n, camp_in, camp_out, fee in rows:
        b = out.setdefault(username, {
            "trades": 0, "buys": 0, "sells": 0,
            "bought_camp": 0, "sold_camp": 0, "fees_camp": 0,
        })
        b["trades"] += int(n)
        b["fees_camp"] += int(fee or 0)
        if side == "buy":
            b["buys"] += int(n)
            b["bought_camp"] += int(camp_in or 0)
        else:
            b["sells"] += int(n)
            b["sold_camp"] += int(camp_out or 0)

    for b in out.values():
        b["volume_camp"] = b["bought_camp"] + b["sold_camp"]
        b["realized_camp"] = b["sold_camp"] - b["bought_camp"]
    return out


def _milk_positions(db: Session) -> tuple:
    """
    Positions courantes valorisees.

    Retourne (par_user, par_pool). La valeur retenue est la valeur REALISABLE
    (`sell_quote` sur tout le stock), pas le mark-to-market : sur un AMM, une
    grosse position ne se debouclerait pas au prix spot.
    """
    pools = {p.id: p for p in db.query(MilkPool).all()}
    positions = db.query(MilkPosition).filter(MilkPosition.balance_milk > 0).all()

    by_user: dict = {}
    by_pool: dict = {
        p.id: {
            "pool_id": p.id,
            "symbol": p.symbol,
            "name": p.name,
            "status": p.status,
            "price_camp_per_bottle": amm.current_price(p.reserve_camp, p.reserve_milk),
            "reserve_camp": int(p.reserve_camp),
            "bottles_in_pool": int(p.reserve_milk) // MILK_UNIT,
            "holders": 0,
            "bottles_held": 0,
            "value_camp": 0,
            "cost_basis_camp": 0,
        }
        for p in pools.values()
    }

    for pos in positions:
        pool = pools.get(pos.pool_id)
        if pool is None:
            continue

        cost_basis = int(pos.avg_cost * pos.balance_milk / MILK_UNIT)
        try:
            value = int(amm.sell_quote(
                pool.reserve_camp, pool.reserve_milk,
                float(pool.fee_pct or 0), pos.balance_milk,
            )["amount_out"])
        except Exception:
            # Pool vide / reserves incoherentes : on retombe sur le spot.
            price = amm.current_price(pool.reserve_camp, pool.reserve_milk)
            value = int(pos.balance_milk * price / MILK_UNIT)

        entry = {
            "pool_id": pool.id,
            "symbol": pool.symbol,
            "name": pool.name,
            "bottles": int(pos.balance_milk) // MILK_UNIT,
            "balance_milk": int(pos.balance_milk),
            "avg_cost": float(pos.avg_cost or 0),
            "cost_basis_camp": cost_basis,
            "value_camp": value,
            "unrealized_pnl_camp": value - cost_basis,
        }
        u = by_user.setdefault(pos.username, {"positions": [], "value_camp": 0,
                                              "cost_basis_camp": 0})
        u["positions"].append(entry)
        u["value_camp"] += value
        u["cost_basis_camp"] += cost_basis

        agg = by_pool[pool.id]
        agg["holders"] += 1
        agg["bottles_held"] += entry["bottles"]
        agg["value_camp"] += value
        agg["cost_basis_camp"] += cost_basis

    for agg in by_pool.values():
        agg["unrealized_pnl_camp"] = agg["value_camp"] - agg["cost_basis_camp"]

    return by_user, by_pool


# ─── Poker ─────────────────────────────────────────────

def _poker_stacks(db: Session) -> dict:
    """Par user : CAMP actuellement assis a une table (sessions non quittees)."""
    rows = (
        db.query(PokerSession.username, func.sum(PokerSession.stack))
          .filter(PokerSession.left_at.is_(None))
          .group_by(PokerSession.username)
          .all()
    )
    return _sum_map(rows)


# ─── Vue d'ensemble ────────────────────────────────────

def overview(db: Session, since: Optional[datetime.datetime],
             balance_fn, only: Optional[list] = None) -> dict:
    """
    Construit le rapport complet.

    `balance_fn(address) -> int` est injectee (blockchain.get_balance_camp) pour
    garder ce module testable sans RPC.

    `only` restreint aux joueurs nommes — utilise par /me/stats pour ne faire
    qu'UN appel RPC au lieu d'un par joueur. Attention : `totals` et `podiums`
    ne portent alors que sur ces joueurs-la, donc ne les exposez pas comme des
    chiffres globaux. `pools` reste une agregation de marche, toujours complete.
    """
    since = since or DEFAULT_SINCE

    # Meme filtre que /users et /leaderboard : on ne classe que les vrais
    # joueurs, pas les comptes systeme (casino_bank, milk_pool_*, ...).
    q = db.query(User).filter(User.account_type == "user")
    if only is not None:
        q = q.filter(User.username.in_(only))
    users = q.order_by(User.created_at).all()

    flows = _external_flows(db, since)
    casino = _casino_stats(db, since)
    milk_trades = _milk_trade_stats(db, since)
    milk_by_user, milk_by_pool = _milk_positions(db)
    poker_stacks = _poker_stacks(db)
    bets_locked = _escrow_net(db, BETS_ESCROW)
    bets_pnl = _escrow_pnl(db, BETS_ESCROW, since)
    bets_joined = _escrow_entries(db, BETS_ESCROW, since)
    poker_pnl = _escrow_pnl(db, POKER_BANK, since)

    # Reconstruction de la situation de chacun au cutoff.
    wallet_flows = _wallet_flows_since(db, since)
    milk_opening = _milk_opening(db, since)
    bets_opening = _escrow_net(db, BETS_ESCROW, before=since)
    poker_opening = _poker_opening(db, since)

    rows = []
    for u in users:
        name = u.username
        wallet = int(balance_fn(u.address) or 0)

        milk_pos = milk_by_user.get(name, {"positions": [], "value_camp": 0,
                                           "cost_basis_camp": 0})
        milk_act = milk_trades.get(name, {
            "trades": 0, "buys": 0, "sells": 0, "bought_camp": 0,
            "sold_camp": 0, "fees_camp": 0, "volume_camp": 0, "realized_camp": 0,
        })
        cas = casino.get(name, {
            "plays": 0, "volume_camp": 0, "payout_camp": 0, "pnl_camp": 0,
            "coinflip": {"plays": 0, "volume_camp": 0, "pnl_camp": 0},
            "roulette": {"plays": 0, "volume_camp": 0, "pnl_camp": 0},
            "slots": {"plays": 0, "volume_camp": 0, "pnl_camp": 0},
        })
        bet = bets_pnl.get(name, {"staked": 0, "won": 0, "pnl": 0})
        pok = poker_pnl.get(name, {"staked": 0, "won": 0, "pnl": 0})

        # Les paris en cours immobilisent des CAMP : sans ca le joueur qui a un
        # pari ouvert apparaitrait en perte du montant de sa mise.
        bets_open = max(0, bets_locked.get(name, 0))
        poker_stack = poker_stacks.get(name, 0)
        milk_value = milk_pos["value_camp"]

        total_value = wallet + milk_value + bets_open + poker_stack

        f = flows.get(name, {"starting_capital": 0, "topups": 0,
                             "withdrawals": 0, "deposits": 0})
        onboarding = f["starting_capital"]
        topups = f["topups"]
        withdrawals = f["withdrawals"]

        # Situation au cutoff, reconstruite plutot que supposee : le solde
        # d'alors n'etait pas forcement le capital de depart (parties jouees
        # avant, reset admin, recharges anterieures...).
        wf = wallet_flows.get(name, {"in": 0, "out": 0})
        opening_wallet = wallet - wf["in"] + wf["out"]
        opening_value = (opening_wallet
                         + milk_opening.get(name, 0)
                         + max(0, bets_opening.get(name, 0))
                         + poker_opening.get(name, 0))

        # Base de mesure : ce qu'il avait au depart de la periode, plus ce qui
        # a ete injecte pendant, moins ce qui a ete retire pendant.
        net_in = opening_value + f["deposits"] - withdrawals

        pnl = total_value - net_in

        rows.append({
            "username": name,
            "created_at": u.created_at.isoformat() + "Z" if u.created_at else None,

            # Ou est son argent, maintenant
            "wallet_camp": wallet,
            "milk_value_camp": milk_value,
            "bets_locked_camp": bets_open,
            "poker_stack_camp": poker_stack,
            "total_value_camp": total_value,

            # Situation au debut de la periode (reconstruite depuis le ledger)
            "opening_value_camp": opening_value,
            "opening_wallet_camp": opening_wallet,

            # Ce qu'il a mis / repris PENDANT la periode
            "onboarding_camp": onboarding,
            "topups_camp": topups,
            "withdrawals_camp": withdrawals,
            "net_deposited_camp": net_in,
            "has_topped_up": topups > 0,

            # La colonne qui compte
            "pnl_camp": pnl,
            "pnl_pct": round(100 * pnl / net_in, 1) if net_in else None,

            "casino": cas,
            "milk": {
                **milk_act,
                "positions_value_camp": milk_value,
                "cost_basis_camp": milk_pos["cost_basis_camp"],
                "unrealized_pnl_camp": milk_value - milk_pos["cost_basis_camp"],
                # PnL complet : flux net encaisse + valeur du stock encore detenu
                "pnl_camp": milk_act["realized_camp"] + milk_value,
                "positions": sorted(milk_pos["positions"],
                                    key=lambda p: -p["value_camp"]),
            },
            # `pnl` = gagne - mise + ce qui est ENCORE engage. Sans ce dernier
            # terme, un pari en cours ou un stack encore sur la table
            # s'afficherait comme une perte seche du montant mise.
            "bets": {**bet, "joined": bets_joined.get(name, 0),
                     "pnl": bet["pnl"] + bets_open},
            "poker": {**pok, "stack_camp": poker_stack,
                      "pnl": pok["pnl"] + poker_stack},

            # Activite tous jeux confondus, pour "qui a le plus joue"
            "actions": (cas["plays"] + milk_act["trades"]
                        + bets_joined.get(name, 0)),
        })

    totals = {
        "users": len(rows),
        "wallet_camp": sum(r["wallet_camp"] for r in rows),
        "milk_value_camp": sum(r["milk_value_camp"] for r in rows),
        "bets_locked_camp": sum(r["bets_locked_camp"] for r in rows),
        "poker_stack_camp": sum(r["poker_stack_camp"] for r in rows),
        "total_value_camp": sum(r["total_value_camp"] for r in rows),
        "opening_value_camp": sum(r["opening_value_camp"] for r in rows),
        "net_deposited_camp": sum(r["net_deposited_camp"] for r in rows),
        "topups_camp": sum(r["topups_camp"] for r in rows),
        "pnl_camp": sum(r["pnl_camp"] for r in rows),
        "casino_volume_camp": sum(r["casino"]["volume_camp"] for r in rows),
        "casino_pnl_players_camp": sum(r["casino"]["pnl_camp"] for r in rows),
        "casino_plays": sum(r["casino"]["plays"] for r in rows),
        "milk_volume_camp": sum(r["milk"]["volume_camp"] for r in rows),
        "milk_trades": sum(r["milk"]["trades"] for r in rows),
        "milk_fees_camp": sum(r["milk"]["fees_camp"] for r in rows),
        "actions": sum(r["actions"] for r in rows),
    }

    def top(key_fn, reverse=True, keep=3, nonzero=True):
        ranked = sorted(rows, key=key_fn, reverse=reverse)
        if nonzero:
            ranked = [r for r in ranked if key_fn(r) != 0]
        return [{"username": r["username"], "value": key_fn(r)} for r in ranked[:keep]]

    podiums = {
        "best_pnl": top(lambda r: r["pnl_camp"]),
        "worst_pnl": top(lambda r: r["pnl_camp"], reverse=False),
        "best_casino": top(lambda r: r["casino"]["pnl_camp"]),
        "worst_casino": top(lambda r: r["casino"]["pnl_camp"], reverse=False),
        "most_active": top(lambda r: r["actions"]),
        "biggest_gambler": top(lambda r: r["casino"]["volume_camp"]),
        "best_milk_trader": top(lambda r: r["milk"]["pnl_camp"]),
        "biggest_milk_position": top(lambda r: r["milk_value_camp"]),
    }

    return {
        "since": since.isoformat() + "Z",
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "note": (
            "PnL borne a la periode : la base de mesure est le solde d'ouverture "
            "reconstruit depuis le ledger (solde actuel moins les mouvements de la "
            "periode), pas le capital de depart suppose. L'activite d'avant `since` "
            "n'influence donc plus le classement. Les positions lait sont valorisees "
            "en valeur realisable (sell_quote sur tout le stock), pas au prix spot ; "
            "leur valeur au cutoff utilise le dernier prix connu avant `since`."
        ),
        "totals": totals,
        "podiums": podiums,
        "users": sorted(rows, key=lambda r: -r["pnl_camp"]),
        "pools": sorted(milk_by_pool.values(), key=lambda p: -p["value_camp"]),
    }


def flows_detail(db: Session, since: Optional[datetime.datetime] = None) -> dict:
    """
    Liste des mouvements de tresorerie avec leur classification courante, pour
    l'ecran d'ajustement admin.

    `source` vaut 'auto' (deduit de la note) ou 'manual' (l'admin a tranche).
    """
    since = since or DEFAULT_SINCE
    labels = _labels(db)

    rows = []
    for tx in treasury_movements(db):
        label, source = classify(tx, labels)
        username = tx.to_username if tx.from_username == TREASURY else tx.from_username
        if _sentinel(username):
            continue
        rows.append({
            "tx_id": tx.id,
            "ts": tx.ts.isoformat() + "Z" if tx.ts else None,
            "username": username,
            "direction": "in" if tx.from_username == TREASURY else "out",
            "amount_camp": int(tx.amount or 0),
            "note": tx.note or "",
            "tx_hash": tx.tx_hash,
            "label": label,
            "source": source,
            "in_period": bool(tx.ts and tx.ts >= since),
        })

    return {
        "since": since.isoformat() + "Z",
        "labels_available": ["onboarding", "topup", "withdrawal", "ignore"],
        "movements": rows,
    }


def set_label(db: Session, tx_id: int, label: Optional[str],
              note: str = "") -> dict:
    """
    Pose (ou retire, si `label` est None) une reclassification manuelle.

    Ne touche jamais la ligne `transactions` d'origine : on ecrit uniquement
    dans `analytics_tx_labels`.
    """
    tx = db.get(Transaction, tx_id)
    if tx is None:
        raise ValueError(f"Transaction #{tx_id} introuvable")
    if tx.from_username != TREASURY and tx.to_username != TREASURY:
        raise ValueError(
            f"Transaction #{tx_id} n'est pas un mouvement de tresorerie "
            "(seuls les depots/retraits se reclassent)"
        )

    existing = db.get(AnalyticsTxLabel, tx_id)

    if label is None:
        if existing:
            db.delete(existing)
            db.commit()
        return {"tx_id": tx_id, "label": classify(tx, {})[0], "source": "auto"}

    if label not in ("onboarding", "topup", "withdrawal", "ignore"):
        raise ValueError(f"Label invalide : {label!r}")

    if existing:
        existing.label = label
        existing.note = note
    else:
        db.add(AnalyticsTxLabel(tx_id=tx_id, label=label, note=note))
    db.commit()

    return {"tx_id": tx_id, "label": label, "source": "manual", "note": note}
