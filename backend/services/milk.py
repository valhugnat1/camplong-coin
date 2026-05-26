"""
services/milk.py - Logique metier de la Bourse du Lait (AMM x*y=k).

Trois fonctions principales :
  - quote(pool, side, amount)         : preview du swap sans le faire
  - swap(db, user, pool, ...)         : execute le swap (lock/release on-chain)
  - apply_chaos(db, pool, kind=None)  : modifie reserve_milk (jamais reserve_camp)

Convention CAMP <-> milk :
  - reserve_camp / amount_camp : en CAMP entiers
  - reserve_milk / amount_milk : en milli-bouteilles (1 bouteille = 1000)
  - prix = CAMP par bouteille  = reserve_camp * 1000 / reserve_milk
"""
import datetime
import json
import math
import random
from dataclasses import asdict, dataclass
from typing import Optional

from sqlalchemy.orm import Session

from blockchain import get_balance_camp
from models import MilkChaosEvent, MilkChaosTemplate, MilkPool, MilkPosition, MilkTrade, User
from services import amm, escrow
from services import settings as settings_svc


# 1 bouteille = 1000 milli-bouteilles (granularite pour swaps)
MILK_UNIT = 1000

# Garde-fou : on ne vide jamais completement la reserve_milk (prix -> inf)
MIN_RESERVE_MILK = 1000   # = 1 bouteille minimum


class MilkError(Exception):
    """Erreur metier (pool inactif, slippage, solde, ...)."""


# ─── Chaos templates : fallbacks codes en dur ────────────────────────
#
# Utilises uniquement si la table milk_chaos_templates est vide ou inaccessible.
# Le catalogue par defaut riche est seed via migrate_v9_milk_chaos_templates.py.

FALLBACK_NARRATIVES = {
    "famine":    "Petite secheresse, -{abs_pct}% du stock",
    "spoil":     "Lot contamine, retrait de {abs_n} bouteilles",
    "overstock": "Surproduction, +{pct}% offertes au marche",
    "import":    "Import exceptionnel, +{pct}% du stock",
}
FALLBACK_KIND_WEIGHTS = [("famine", 2), ("spoil", 3), ("overstock", 2), ("import", 3)]


# ─── Helpers templates ────────────────────────────────────────────────

def pick_template(db: Session) -> Optional[MilkChaosTemplate]:
    """
    Tire un template enabled de maniere ponderee. Retourne None si la
    table est vide (le caller bascule sur le fallback hardcoded).
    """
    rows = (
        db.query(MilkChaosTemplate)
          .filter(MilkChaosTemplate.enabled == True)
          .all()
    )
    if not rows:
        return None
    weights = [max(1, r.weight) for r in rows]
    return random.choices(rows, weights=weights, k=1)[0]


def _safe_format(narrative: str, **kw) -> str:
    """
    Format tolerant : si la narrative ne contient pas le placeholder
    attendu (ex: {pct} mais l'utilisateur a ecrit que {abs_n}), on
    n'echoue pas. Cle absente -> remplace par chaine vide.
    """
    class _D(dict):
        def __missing__(self, key):  # noqa: D401
            return ""
    try:
        return narrative.format_map(_D(**kw))
    except Exception:
        return narrative


def render_narrative(template_narrative: str, delta_milk: int,
                     reserve_milk_before: int) -> str:
    """
    Substitue les placeholders {pct} {abs_pct} {n} {abs_n} dans la narrative.

    - {pct} / {abs_pct} : delta en % de la reserve AVANT, arrondi 1 decimale
    - {n}   / {abs_n}   : delta en BOUTEILLES (delta_milk / MILK_UNIT), entier
    """
    if reserve_milk_before > 0:
        pct = round(delta_milk * 100.0 / reserve_milk_before, 1)
    else:
        pct = 0.0
    n_bottles = int(delta_milk / MILK_UNIT)
    return _safe_format(
        template_narrative,
        pct=pct,
        abs_pct=abs(pct),
        n=n_bottles,
        abs_n=abs(n_bottles),
    )


def _delta_from_template(tpl: MilkChaosTemplate, reserve_milk: int) -> int:
    """
    Tire un delta dans [delta_min, delta_max] selon delta_type.
    Retourne le delta en milli-bouteilles (signe).
    """
    value = random.uniform(tpl.delta_min, tpl.delta_max)
    if tpl.delta_type == "pct":
        return int(reserve_milk * value / 100)
    # 'bottles' : value est en bouteilles entieres -> milli
    return int(value) * MILK_UNIT


def clamp_to_volatility(delta_milk: int, reserve_milk: int,
                         max_vol_pct: float) -> int:
    """
    Borne un delta_milk pour respecter une volatilite max (% de variation
    de prix). Sans cap, les templates 'famine_severe' peuvent doubler le
    prix en une seule fois -- ce qui draine la banque trop vite quand les
    holders revendent juste apres.

    Formule (prix = camp / milk * 1000) :
      - delta < 0 (price up) :
          price_after/price_before = old_milk / new_milk ≤ 1 + cap/100
          → delta ≥ -old_milk * cap / (100 + cap)
      - delta > 0 (price down) :
          price_after/price_before ≥ 1 - cap/100
          → delta ≤ old_milk * cap / (100 - cap)

    cap = 0 → aucune variation autorisee (delta = 0).
    cap ≥ 100 → pas de cap (delta inchange).
    """
    if max_vol_pct <= 0:
        return 0
    if max_vol_pct >= 100:
        return delta_milk
    if delta_milk < 0:
        max_drop = -reserve_milk * max_vol_pct / (100 + max_vol_pct)
        return int(max(delta_milk, max_drop))
    if delta_milk > 0:
        max_rise = reserve_milk * max_vol_pct / (100 - max_vol_pct)
        return int(min(delta_milk, max_rise))
    return 0


# ─── Serialization ────────────────────────────────────────────────────

def pool_dict(p: MilkPool) -> dict:
    return {
        "id": p.id,
        "symbol": p.symbol,
        "name": p.name,
        "system_role": p.system_role,
        "reserve_camp": p.reserve_camp,
        "reserve_milk": p.reserve_milk,
        "fee_pct": p.fee_pct,
        "status": p.status,
        "initial_camp": p.initial_camp,
        "initial_milk": p.initial_milk,
        "chaos_enabled": p.chaos_enabled,
        "price": amm.current_price(p.reserve_camp, p.reserve_milk),
        "milk_unit": MILK_UNIT,
        "bottles": p.reserve_milk // MILK_UNIT,
        "created_at": p.created_at.isoformat() + "Z" if p.created_at else None,
    }


def trade_dict(t: MilkTrade) -> dict:
    return {
        "id": t.id,
        "pool_id": t.pool_id,
        "username": t.username,
        "side": t.side,
        "amount_camp_in": t.amount_camp_in,
        "amount_milk_in": t.amount_milk_in,
        "amount_camp_out": t.amount_camp_out,
        "amount_milk_out": t.amount_milk_out,
        "fee": t.fee,
        "price_before": t.price_before,
        "price_after": t.price_after,
        "ts": t.ts.isoformat() + "Z" if t.ts else None,
        "tx_hash": t.tx_hash,
    }


def position_dict(pos: MilkPosition, pool: Optional[MilkPool] = None) -> dict:
    d = {
        "username": pos.username,
        "pool_id": pos.pool_id,
        "balance_milk": pos.balance_milk,
        "bottles": pos.balance_milk // MILK_UNIT,
        "avg_cost": pos.avg_cost,
    }
    if pool is not None:
        price = amm.current_price(pool.reserve_camp, pool.reserve_milk)
        # Valeur mark-to-market : balance * prix spot. Theorique, surestime
        # pour les grosses positions (ne prend pas en compte le price impact
        # qu'elles subiraient en se debouclant).
        mtm_value = int(pos.balance_milk * price / MILK_UNIT) if pos.balance_milk else 0
        cost_basis = int(pos.avg_cost * pos.balance_milk / MILK_UNIT)

        # Valeur realisable : CAMP qu'on toucherait vraiment en vendant tout
        # le stock au pool maintenant (sell_quote sur balance_milk, donc
        # walk down the curve). C'est la valeur "honnete" du portefeuille.
        if pos.balance_milk > 0 and pool.reserve_camp > 0 and pool.reserve_milk > 0:
            try:
                sell_q = amm.sell_quote(
                    pool.reserve_camp, pool.reserve_milk,
                    float(pool.fee_pct or 0),
                    pos.balance_milk,
                )
                realisable_value = int(sell_q["amount_out"])
                realisable_price_after = sell_q["price_after"]
            except Exception:
                realisable_value = mtm_value
                realisable_price_after = price
        else:
            realisable_value = 0
            realisable_price_after = price

        d["current_value_camp"] = mtm_value          # legacy: mark-to-market
        d["realisable_value_camp"] = realisable_value  # ce qu'on toucherait vraiment
        d["cost_basis_camp"] = cost_basis
        d["pnl_camp"] = mtm_value - cost_basis                # PnL mark-to-market
        d["realisable_pnl_camp"] = realisable_value - cost_basis  # PnL realiste
        d["price_impact_sell_all_pct"] = (
            (realisable_price_after - price) / price * 100.0 if price > 0 else 0.0
        )
        d["pool_symbol"] = pool.symbol
        d["pool_name"] = pool.name
        d["current_price"] = price
    return d


def chaos_dict(e: MilkChaosEvent) -> dict:
    return {
        "id": e.id,
        "pool_id": e.pool_id,
        "kind": e.kind,
        "delta_milk": e.delta_milk,
        "reserve_milk_before": e.reserve_milk_before,
        "reserve_milk_after": e.reserve_milk_after,
        "price_before": e.price_before,
        "price_after": e.price_after,
        "narrative": e.narrative,
        "triggered_by": e.triggered_by,
        "ts": e.ts.isoformat() + "Z" if e.ts else None,
    }


# ─── Quote ────────────────────────────────────────────────────────────

def quote(pool: MilkPool, side: str, amount: int) -> dict:
    """
    Calcule un preview de swap sans le faire. amount est :
      - le CAMP entrant si side == 'buy'
      - le milk (en milli-bouteilles) entrant si side == 'sell'
    """
    if pool.status != "active":
        raise MilkError(f"Pool {pool.symbol} non actif (statut: {pool.status})")
    if side == "buy":
        return amm.buy_quote(pool.reserve_camp, pool.reserve_milk,
                             pool.fee_pct, amount)
    elif side == "sell":
        return amm.sell_quote(pool.reserve_camp, pool.reserve_milk,
                              pool.fee_pct, amount)
    raise MilkError(f"side inconnu : {side!r} (attendu 'buy' ou 'sell')")


# ─── Swap ─────────────────────────────────────────────────────────────

@dataclass
class SwapResult:
    trade_id: int
    side: str
    amount_camp_in: int
    amount_milk_in: int
    amount_camp_out: int
    amount_milk_out: int
    fee: int
    price_before: float
    price_after: float
    new_reserve_camp: int
    new_reserve_milk: int
    new_balance_camp: int
    new_balance_milk: int
    tx_hash: Optional[str]
    ts: str

    def to_dict(self) -> dict:
        return asdict(self)


def _check_slippage(q: dict, expected_price: Optional[float],
                    max_slippage_pct: Optional[float]) -> None:
    """
    Si le user a passe un prix attendu + tolerance, on verifie que le prix
    apres swap ne s'eloigne pas trop. Sinon (params None) on ne fait rien.
    """
    if expected_price is None or max_slippage_pct is None:
        return
    if expected_price <= 0:
        return
    drift = abs(q["price_after"] - expected_price) / expected_price * 100
    if drift > max_slippage_pct:
        raise MilkError(
            f"Slippage trop eleve ({drift:.2f}% > {max_slippage_pct}%). "
            "Le prix a bouge avant ton swap, retente."
        )


def swap(
    db: Session,
    user: User,
    pool: MilkPool,
    side: str,
    amount: int,
    expected_price: Optional[float] = None,
    max_slippage_pct: Optional[float] = None,
) -> SwapResult:
    """
    Execute un swap. Pattern atomique (cf. EXTENSIONS.md, services/coinflip.py) :
      1. Calcul de la quote.
      2. Slippage check.
      3. Mouvement on-chain (lock pour buy, release pour sell).
      4. Update DB : reserves, position user, ligne trade.
      5. Commit.

    Verrou pessimiste sur la ligne pool en amont (caller doit avoir fait
    le with_for_update()) pour serialiser les swaps concurrents.

    En cas d'erreur metier : raise MilkError (caller -> 400, rollback).
    En cas d'echec on-chain : la tx peut etre passee ou pas. Le caller fait
    db.rollback() ; si la tx est passee mais que la DB n'a pas commit, l'admin
    doit reconcilier via /admin/milk + transactions.
    """
    if pool.status != "active":
        raise MilkError(f"Pool {pool.symbol} non actif")
    if amount <= 0:
        raise MilkError("Montant doit etre > 0")
    if side not in ("buy", "sell"):
        raise MilkError(f"side invalide : {side!r}")

    q = quote(pool, side, amount)
    _check_slippage(q, expected_price, max_slippage_pct)

    if side == "buy":
        if q["amount_out"] <= 0:
            raise MilkError("Montant trop faible : 0 bouteille en sortie")

        # Lock CAMP utilisateur -> pool system account
        tx = escrow.lock(
            db, user, pool.system_role, amount,
            f"milk swap buy {pool.symbol}",
        )

        # Met a jour les reserves
        pool.reserve_camp = q["new_reserve_camp"]
        pool.reserve_milk = q["new_reserve_milk"]

        # Position user (upsert + pondere avg_cost)
        pos = (
            db.query(MilkPosition)
              .filter_by(username=user.username, pool_id=pool.id)
              .with_for_update()
              .first()
        )
        if not pos:
            pos = MilkPosition(
                username=user.username, pool_id=pool.id,
                balance_milk=0, avg_cost=0,
            )
            db.add(pos)
            db.flush()

        # avg_cost en CAMP par bouteille (milli-bouteille agnostic)
        # cost_total_before = avg_cost * balance_milk / MILK_UNIT
        # cost_total_after = cost_total_before + amount (CAMP qu'on vient de
        # mettre, fees inclus - c'est ce que ca a vraiment coute au user)
        old_value = pos.avg_cost * pos.balance_milk / MILK_UNIT
        new_value = old_value + amount
        pos.balance_milk += q["amount_out"]
        if pos.balance_milk > 0:
            # avg_cost = cost_camp_total / bouteilles
            #          = new_value / (balance_milk / MILK_UNIT)
            pos.avg_cost = new_value * MILK_UNIT / pos.balance_milk
        else:
            pos.avg_cost = 0

        trade = MilkTrade(
            pool_id=pool.id,
            username=user.username,
            side="buy",
            amount_camp_in=amount,
            amount_milk_in=0,
            amount_camp_out=0,
            amount_milk_out=q["amount_out"],
            fee=q["fee"],
            price_before=q["price_before"],
            price_after=q["price_after"],
            tx_hash=tx,
        )
        db.add(trade)
        db.flush()

        return SwapResult(
            trade_id=trade.id,
            side="buy",
            amount_camp_in=amount,
            amount_milk_in=0,
            amount_camp_out=0,
            amount_milk_out=q["amount_out"],
            fee=q["fee"],
            price_before=q["price_before"],
            price_after=q["price_after"],
            new_reserve_camp=pool.reserve_camp,
            new_reserve_milk=pool.reserve_milk,
            new_balance_camp=get_balance_camp(user.address),
            new_balance_milk=pos.balance_milk,
            tx_hash=tx,
            ts=trade.ts.isoformat() + "Z" if trade.ts else datetime.datetime.utcnow().isoformat() + "Z",
        )

    # ─── SELL
    pos = (
        db.query(MilkPosition)
          .filter_by(username=user.username, pool_id=pool.id)
          .with_for_update()
          .first()
    )
    if not pos or pos.balance_milk < amount:
        raise MilkError(
            f"Pas assez de bouteilles a vendre "
            f"({(pos.balance_milk if pos else 0) // MILK_UNIT} dispo)"
        )

    if q["amount_out"] <= 0:
        raise MilkError("Sortie nulle : montant trop faible apres frais")

    # On enleve le milk avant la tx on-chain : si la tx rate, le caller
    # rollback et la position est restauree.
    pos.balance_milk -= amount

    # Met a jour les reserves AVANT la tx (preserve l'invariance si rollback)
    pool.reserve_camp = q["new_reserve_camp"]
    pool.reserve_milk = q["new_reserve_milk"]

    # Release CAMP du pool vers l'utilisateur
    tx = escrow.release(
        db, pool.system_role, user, q["amount_out"],
        f"milk swap sell {pool.symbol}",
    )

    trade = MilkTrade(
        pool_id=pool.id,
        username=user.username,
        side="sell",
        amount_camp_in=0,
        amount_milk_in=amount,
        amount_camp_out=q["amount_out"],
        amount_milk_out=0,
        fee=q["fee"],
        price_before=q["price_before"],
        price_after=q["price_after"],
        tx_hash=tx,
    )
    db.add(trade)
    db.flush()

    return SwapResult(
        trade_id=trade.id,
        side="sell",
        amount_camp_in=0,
        amount_milk_in=amount,
        amount_camp_out=q["amount_out"],
        amount_milk_out=0,
        fee=q["fee"],
        price_before=q["price_before"],
        price_after=q["price_after"],
        new_reserve_camp=pool.reserve_camp,
        new_reserve_milk=pool.reserve_milk,
        new_balance_camp=get_balance_camp(user.address),
        new_balance_milk=pos.balance_milk,
        tx_hash=tx,
        ts=trade.ts.isoformat() + "Z" if trade.ts else datetime.datetime.utcnow().isoformat() + "Z",
    )


# ─── Chaos ────────────────────────────────────────────────────────────

def _commit_chaos(
    db: Session,
    pool: MilkPool,
    kind: str,
    delta_milk: int,
    narrative: str,
    triggered_by: str,
) -> Optional[MilkChaosEvent]:
    """Applique le delta sur pool.reserve_milk + log l'event. Garde-fou inclus."""
    new_milk = pool.reserve_milk + delta_milk
    if new_milk < MIN_RESERVE_MILK:
        return None

    price_before = pool.reserve_camp * 1000.0 / pool.reserve_milk
    reserve_milk_before = pool.reserve_milk
    pool.reserve_milk = new_milk
    price_after = pool.reserve_camp * 1000.0 / pool.reserve_milk

    event = MilkChaosEvent(
        pool_id=pool.id,
        kind=kind,
        delta_milk=delta_milk,
        reserve_milk_before=reserve_milk_before,
        reserve_milk_after=new_milk,
        price_before=price_before,
        price_after=price_after,
        narrative=narrative,
        triggered_by=triggered_by,
    )
    db.add(event)
    db.flush()
    return event


def apply_chaos(
    db: Session,
    pool: MilkPool,
    kind: Optional[str] = None,
    delta_milk: Optional[int] = None,
    narrative: Optional[str] = None,
    triggered_by: str = "bot",
) -> Optional[MilkChaosEvent]:
    """
    Applique un evenement chaos sur un pool.

    - kind=None & delta_milk=None : tirage d'un template DB (ou fallback
      hardcoded si la table est vide). Cas du bot dieu.
    - kind+delta_milk explicites : injection manuelle (admin). narrative
      optionnelle (sinon on rend depuis le fallback du kind).

    Modifie pool.reserve_milk SEULEMENT (jamais reserve_camp).
    Retourne l'event cree, ou None si garde-fou (drain < 1 bouteille).
    """
    if pool.status != "active":
        return None

    # ─── Cas 1 : injection manuelle (admin) ────────────────────────
    if kind is not None or delta_milk is not None:
        if kind is None:
            kind = "spoil" if (delta_milk or 0) < 0 else "overstock"
        if delta_milk is None:
            # delta_milk manquant : fallback random sur un range neutre
            delta_milk = -50 * MILK_UNIT if kind in ("famine", "spoil") else 50 * MILK_UNIT
        if narrative is None:
            narrative = render_narrative(
                FALLBACK_NARRATIVES.get(kind, "Choc sur le stock ({n} btl)"),
                delta_milk, pool.reserve_milk,
            )
        return _commit_chaos(db, pool, kind, delta_milk, narrative, triggered_by)

    # ─── Cas 2 : auto (bot), tirage de template ────────────────────
    # Lit le cap de volatilite a chaque firing (modifiable a chaud).
    max_vol_pct = settings_svc.get_float(db, "milk_chaos_max_volatility_pct", 20.0)

    tpl = pick_template(db)
    if tpl is not None:
        delta_milk = _delta_from_template(tpl, pool.reserve_milk)
        delta_milk = clamp_to_volatility(delta_milk, pool.reserve_milk, max_vol_pct)
        narrative_str = render_narrative(tpl.narrative, delta_milk, pool.reserve_milk)
        return _commit_chaos(db, pool, tpl.kind, delta_milk, narrative_str, triggered_by)

    # ─── Fallback : pas de template en DB ──────────────────────────
    kinds, weights = zip(*FALLBACK_KIND_WEIGHTS)
    kind = random.choices(kinds, weights=weights, k=1)[0]
    if kind in ("famine", "import"):
        pct = random.uniform(5, 25)
        delta_milk = int(pool.reserve_milk * pct / 100)
        if kind == "famine":
            delta_milk = -delta_milk
    else:
        n = random.randint(50, 500)
        delta_milk = -n * MILK_UNIT if kind == "spoil" else n * MILK_UNIT
    delta_milk = clamp_to_volatility(delta_milk, pool.reserve_milk, max_vol_pct)
    narrative_str = render_narrative(
        FALLBACK_NARRATIVES[kind], delta_milk, pool.reserve_milk
    )
    return _commit_chaos(db, pool, kind, delta_milk, narrative_str, triggered_by)


# ─── Template serialization ────────────────────────────────────────

def template_dict(t: MilkChaosTemplate) -> dict:
    return {
        "id": t.id,
        "slug": t.slug,
        "kind": t.kind,
        "delta_type": t.delta_type,
        "delta_min": t.delta_min,
        "delta_max": t.delta_max,
        "narrative": t.narrative,
        "weight": t.weight,
        "enabled": t.enabled,
        "created_at": t.created_at.isoformat() + "Z" if t.created_at else None,
        "updated_at": t.updated_at.isoformat() + "Z" if t.updated_at else None,
    }


def template_preview(t: MilkChaosTemplate, reserve_milk: int = 200_000) -> dict:
    """
    Genere un exemple de narrative pour previsualiser un template
    sans le tirer reellement. reserve_milk par defaut = 200 btl.
    """
    delta_milk = _delta_from_template(t, reserve_milk)
    return {
        "delta_milk": delta_milk,
        "delta_bottles": delta_milk / MILK_UNIT,
        "rendered_narrative": render_narrative(t.narrative, delta_milk, reserve_milk),
    }


# ─── Chaos analysis (esperance d'impact banque) ──────────────────────

def _expected_bank_drift_factor(delta_pct_min: float, delta_pct_max: float) -> float:
    """
    Esperance de (sqrt(milk_after/milk_before) - 1) pour X uniforme dans
    [delta_pct_min, delta_pct_max] (deltas exprimes en pourcent de reserve_milk).

    Interpretation : si les holders reequilibrent au prix avant chaos (sell
    apres famine, buy apres overstock), la banque finit avec
    reserve_camp * sqrt(milk_after/milk_before) en CAMP. Le ratio - 1 est
    l'esperance de gain (positif) ou de drainage (negatif) pour la banque,
    en proportion de reserve_camp.

    Formule fermee (integrale de sqrt(1+x) - 1 sur [a, b] uniforme) :
        E = (2/3 * ((1+b)^1.5 - (1+a)^1.5)) / (b - a) - 1
    """
    a = delta_pct_min / 100.0
    b = delta_pct_max / 100.0
    # Garde-fou : delta ≤ -100% n'a pas de sens physique (vide complet).
    a = max(a, -0.999)
    b = max(b, -0.999)
    if abs(b - a) < 1e-9:
        return math.sqrt(1.0 + a) - 1.0
    integral = (2.0 / 3.0) * ((1.0 + b) ** 1.5 - (1.0 + a) ** 1.5)
    return integral / (b - a) - 1.0


def _milk_pct_bounds_for_cap(max_vol_pct: float) -> tuple[float, float]:
    """
    Bornes en % du lait imposees par le cap de volatilite prix (max_vol_pct).
    Cap c% => delta_milk dans [-100c/(100+c), +100c/(100-c)] (en % de la reserve).
    """
    if max_vol_pct <= 0:
        return (0.0, 0.0)
    if max_vol_pct >= 100:
        return (-100.0, float("inf"))
    return (
        -100.0 * max_vol_pct / (100.0 + max_vol_pct),
        +100.0 * max_vol_pct / (100.0 - max_vol_pct),
    )


def chaos_analysis(
    db: Session,
    reference_reserve_milk: int = 200_000,
    max_vol_pct: float | None = None,
) -> dict:
    """
    Calcule, pour chaque template enabled, l'esperance de mouvement
    de prix et l'esperance d'impact sur la banque (en % de reserve_camp).

    Globalement : moyenne ponderee par weight. Permet a l'admin de
    detecter un catalogue biaise qui draine systematiquement la liquidite.

    reference_reserve_milk sert UNIQUEMENT pour les templates en
    delta_type='bottles' (qui dependent du size du pool). Par defaut on
    prend 200 btl = 200_000 milli (= reserve d'amorcage par defaut).

    max_vol_pct : si fourni, on applique le cap (clamp uniforme sur la
    distribution du template) avant d'integrer. Sans ca on sur-estime
    sauvagement les templates a gros range (milking_record, famine_severe,
    etc.). Pass None => pas de cap (anciens chiffres bruts).
    """
    templates = (
        db.query(MilkChaosTemplate)
          .filter(MilkChaosTemplate.enabled == True)
          .all()
    )
    total_weight = sum(t.weight for t in templates) or 1

    cap_lo, cap_hi = _milk_pct_bounds_for_cap(max_vol_pct) if max_vol_pct is not None else (-100.0, float("inf"))

    per_template = []
    weighted_delta_pct = 0.0
    weighted_bank_drift_pct = 0.0
    weighted_abs_delta_pct = 0.0  # volatilite moyenne (abs value)

    for t in templates:
        # Convertit delta_min/delta_max en pourcent de reserve_milk
        if t.delta_type == "pct":
            raw_min_pct = t.delta_min
            raw_max_pct = t.delta_max
        else:
            # 'bottles' : delta en bouteilles, on rapporte au reference reserve
            ref_bottles = reference_reserve_milk / MILK_UNIT
            raw_min_pct = (t.delta_min / ref_bottles) * 100 if ref_bottles else 0
            raw_max_pct = (t.delta_max / ref_bottles) * 100 if ref_bottles else 0

        # Applique le cap de volatilite (meme regle que clamp_to_volatility).
        # On clip simplement les bornes : un template tirant uniformement dans
        # [raw_min, raw_max] verra ses tirages clampes a [cap_lo, cap_hi].
        # Approximation : la masse en dehors du cap est rabattue sur la borne,
        # mais on traite la sous-plage clampee comme uniforme (E sur la zone
        # encore libre, et tirages au cap pour le reste).
        d_min_pct = max(raw_min_pct, cap_lo)
        d_max_pct = min(raw_max_pct, cap_hi)
        if d_min_pct > d_max_pct:
            # cap a tout ecrase d'un cote -> distribution dégénérée sur la borne
            d_min_pct = d_max_pct = max(min(raw_max_pct, cap_hi), cap_lo) if raw_max_pct > 0 else max(min(raw_min_pct, cap_hi), cap_lo)

        # Esperance "vraie" avec clip : on combine la zone uniforme avec les
        # masses concentrees sur chaque borne.
        raw_range = raw_max_pct - raw_min_pct
        if raw_range <= 1e-9:
            avg_delta_pct = (d_min_pct + d_max_pct) / 2.0
            avg_abs_delta_pct = (abs(d_min_pct) + abs(d_max_pct)) / 2.0
            bank_drift_pct = _expected_bank_drift_factor(d_min_pct, d_max_pct) * 100.0
        else:
            # Probabilites de la masse clippee sur chaque cote
            p_low = max(0.0, (cap_lo - raw_min_pct)) / raw_range
            p_high = max(0.0, (raw_max_pct - cap_hi)) / raw_range
            p_mid = max(0.0, 1.0 - p_low - p_high)

            mid_lo = max(raw_min_pct, cap_lo)
            mid_hi = min(raw_max_pct, cap_hi)
            if mid_hi < mid_lo:
                mid_lo = mid_hi

            avg_delta_pct = (
                p_low * cap_lo
                + p_high * cap_hi
                + p_mid * (mid_lo + mid_hi) / 2.0
            )
            avg_abs_delta_pct = (
                p_low * abs(cap_lo)
                + p_high * abs(cap_hi)
                + p_mid * (abs(mid_lo) + abs(mid_hi)) / 2.0
            )
            drift_low = math.sqrt(1.0 + max(cap_lo, -0.999) / 100.0) - 1.0
            drift_high = math.sqrt(1.0 + cap_hi / 100.0) - 1.0
            drift_mid = _expected_bank_drift_factor(mid_lo, mid_hi)
            bank_drift_pct = (
                p_low * drift_low
                + p_high * drift_high
                + p_mid * drift_mid
            ) * 100.0

        share = t.weight / total_weight
        weighted_delta_pct += share * avg_delta_pct
        weighted_bank_drift_pct += share * bank_drift_pct
        weighted_abs_delta_pct += share * avg_abs_delta_pct

        per_template.append({
            "id": t.id,
            "slug": t.slug,
            "kind": t.kind,
            "weight": t.weight,
            "weight_share_pct": round(share * 100, 2),
            "delta_type": t.delta_type,
            "delta_min": t.delta_min,
            "delta_max": t.delta_max,
            "avg_delta_milk_pct": round(avg_delta_pct, 3),
            "bank_drift_pct": round(bank_drift_pct, 4),
        })

    per_template.sort(
        key=lambda x: x["bank_drift_pct"]
    )  # plus drainant en haut

    return {
        "total_templates": len(templates),
        "total_weight": total_weight,
        "reference_reserve_milk": reference_reserve_milk,
        "max_vol_pct": max_vol_pct,
        "milk_cap_lo_pct": round(cap_lo, 3) if max_vol_pct is not None else None,
        "milk_cap_hi_pct": round(cap_hi, 3) if (max_vol_pct is not None and cap_hi != float("inf")) else None,
        "weighted_avg_delta_milk_pct": round(weighted_delta_pct, 3),
        "weighted_avg_abs_delta_pct": round(weighted_abs_delta_pct, 3),
        "weighted_avg_bank_drift_pct": round(weighted_bank_drift_pct, 4),
        "per_template": per_template,
    }
