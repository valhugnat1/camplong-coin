"""
routers/milk.py - Endpoints user pour la Bourse du Lait.

Toutes les routes exigent un JWT user.
La logique metier vit dans services/milk.py + services/amm.py.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from models import MilkChaosEvent, MilkPool, MilkPosition, MilkTrade, User
from schemas import MilkSwapIn
from security import current_user
from services import amm, escrow, milk
from blockchain import get_balance_camp


router = APIRouter(tags=["milk"])


# ─── Lecture pools ─────────────────────────────────────


def _pool_with_24h(db: Session, p: MilkPool) -> dict:
    """Sertialise un pool + change 24h calcule a partir des trades."""
    d = milk.pool_dict(p)
    # Variation 24h : 1er trade > now-24h vs prix courant.
    # Pour rester leger en V1, on regarde le dernier trade et le 1er trade
    # des dernieres 24h.
    import datetime as _dt
    since = _dt.datetime.utcnow() - _dt.timedelta(hours=24)
    oldest = (
        db.query(MilkTrade)
          .filter(MilkTrade.pool_id == p.id, MilkTrade.ts >= since)
          .order_by(MilkTrade.ts.asc())
          .first()
    )
    if oldest:
        price_24h_ago = oldest.price_before
        if price_24h_ago > 0:
            d["change_24h_pct"] = round(100 * (d["price"] - price_24h_ago) / price_24h_ago, 2)
        else:
            d["change_24h_pct"] = None
    else:
        d["change_24h_pct"] = None
    return d


@router.get("/milk/pools")
def list_pools(
    _user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Liste tous les pools (active + paused) avec prix courant + variation 24h."""
    pools = db.query(MilkPool).order_by(MilkPool.created_at.asc()).all()
    return [_pool_with_24h(db, p) for p in pools]


@router.get("/milk/pools/{symbol}")
def get_pool(
    symbol: str,
    _user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    p = db.query(MilkPool).filter(MilkPool.symbol == symbol).first()
    if not p:
        raise HTTPException(404, f"Pool {symbol} introuvable")
    d = _pool_with_24h(db, p)
    # Inclut le solde CAMP du wallet pool (debug / transparence)
    try:
        sys_acc = escrow.get_system_account(db, p.system_role)
        d["pool_wallet_balance_camp"] = get_balance_camp(sys_acc.address)
        d["pool_wallet_address"] = sys_acc.address
    except escrow.EscrowError:
        d["pool_wallet_balance_camp"] = None
        d["pool_wallet_address"] = None
    return d


@router.get("/milk/pools/{symbol}/chart")
def get_chart(
    symbol: str,
    minutes: int = Query(24 * 60, ge=1, le=24 * 60 * 30),
    _user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """
    Renvoie une serie temporelle pour le chart. Approche legere V1 :
    on utilise les trades + events chaos comme points.

    `minutes` : fenetre temporelle (de 1 min a 30 jours). Le front fournit
    en minutes pour pouvoir demander des plages courtes (ex: 15 min) qu'on
    n'arrivait pas a exprimer en heures entieres.
    """
    import datetime as _dt
    p = db.query(MilkPool).filter(MilkPool.symbol == symbol).first()
    if not p:
        raise HTTPException(404, f"Pool {symbol} introuvable")

    since = _dt.datetime.utcnow() - _dt.timedelta(minutes=minutes)

    trades = (
        db.query(MilkTrade)
          .filter(MilkTrade.pool_id == p.id, MilkTrade.ts >= since)
          .order_by(MilkTrade.ts.asc())
          .all()
    )
    chaos = (
        db.query(MilkChaosEvent)
          .filter(MilkChaosEvent.pool_id == p.id, MilkChaosEvent.ts >= since)
          .order_by(MilkChaosEvent.ts.asc())
          .all()
    )

    # Merge chronologique : (ts, price). Les trades portent assez d'infos
    # pour que le front filtre ses trades a lui et affiche un tooltip.
    # Les events chaos restent dans la serie pour que la ligne de prix
    # reflete les mouvements, mais le front ne les rend pas en markers.
    points = []
    for t in trades:
        points.append({
            "ts": t.ts.isoformat() + "Z",
            "price": t.price_after,
            "source": "trade",
            "username": t.username,
            "side": t.side,
            "amount_camp_in": t.amount_camp_in,
            "amount_milk_in": t.amount_milk_in,
            "amount_camp_out": t.amount_camp_out,
            "amount_milk_out": t.amount_milk_out,
        })
    for e in chaos:
        points.append({
            "ts": e.ts.isoformat() + "Z",
            "price": e.price_after,
            "source": "chaos",
        })
    points.sort(key=lambda p: p["ts"])

    # Ajoute le point courant (prix maintenant) pour eviter une ligne plate
    current = amm.current_price(p.reserve_camp, p.reserve_milk)
    points.append({
        "ts": _dt.datetime.utcnow().isoformat() + "Z",
        "price": current,
        "source": "current",
    })

    return {
        "symbol": symbol,
        "minutes": minutes,
        "current_price": current,
        "points": points,
    }


@router.get("/milk/pools/{symbol}/quote")
def get_quote(
    symbol: str,
    side: str = Query(..., pattern="^(buy|sell)$"),
    amount: int = Query(..., gt=0),
    _user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """
    Preview d'un swap. amount = CAMP (buy) ou milli-bouteilles (sell).
    """
    p = db.query(MilkPool).filter(MilkPool.symbol == symbol).first()
    if not p:
        raise HTTPException(404, f"Pool {symbol} introuvable")
    try:
        q = milk.quote(p, side, amount)
    except milk.MilkError as e:
        raise HTTPException(400, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return q


# ─── Swap ─────────────────────────────────────────────


@router.post("/milk/pools/{symbol}/swap")
def swap(
    symbol: str,
    body: MilkSwapIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """
    Execute un swap. Le pool est verrouille (SELECT FOR UPDATE) pour
    serializer les acces concurrents.
    """
    pool = (
        db.query(MilkPool)
          .filter(MilkPool.symbol == symbol)
          .with_for_update()
          .first()
    )
    if not pool:
        raise HTTPException(404, f"Pool {symbol} introuvable")

    try:
        result = milk.swap(
            db, user, pool,
            side=body.side,
            amount=body.amount,
            expected_price=body.expected_price,
            max_slippage_pct=body.max_slippage_pct,
        )
    except milk.MilkError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    except escrow.EscrowError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    except ValueError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Echec swap milk : {e}")

    db.commit()
    return result.to_dict()


# ─── Positions / trades du user ───────────────────────


@router.get("/me/milk/positions")
def my_positions(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Toutes mes positions (balance milk + valorisation courante + P&L)."""
    rows = (
        db.query(MilkPosition, MilkPool)
          .join(MilkPool, MilkPool.id == MilkPosition.pool_id)
          .filter(MilkPosition.username == user.username)
          .all()
    )
    return [milk.position_dict(pos, pool) for pos, pool in rows]


@router.get("/me/milk/trades")
def my_trades(
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(MilkTrade)
          .filter(MilkTrade.username == user.username)
          .order_by(MilkTrade.ts.desc())
          .limit(limit)
          .all()
    )
    return [milk.trade_dict(t) for t in rows]


@router.get("/milk/pools/{symbol}/trades")
def pool_trades(
    symbol: str,
    limit: int = Query(20, ge=1, le=100),
    _user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Derniers trades du pool (pour le 'tape' cote front)."""
    p = db.query(MilkPool).filter(MilkPool.symbol == symbol).first()
    if not p:
        raise HTTPException(404, f"Pool {symbol} introuvable")
    rows = (
        db.query(MilkTrade)
          .filter(MilkTrade.pool_id == p.id)
          .order_by(MilkTrade.ts.desc())
          .limit(limit)
          .all()
    )
    return [milk.trade_dict(t) for t in rows]


@router.get("/milk/pools/{symbol}/chaos")
def pool_chaos(
    symbol: str,
    limit: int = Query(20, ge=1, le=100),
    _user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Derniers evenements chaos du pool (pour le storytelling cote front)."""
    p = db.query(MilkPool).filter(MilkPool.symbol == symbol).first()
    if not p:
        raise HTTPException(404, f"Pool {symbol} introuvable")
    rows = (
        db.query(MilkChaosEvent)
          .filter(MilkChaosEvent.pool_id == p.id)
          .order_by(MilkChaosEvent.ts.desc())
          .limit(limit)
          .all()
    )
    return [milk.chaos_dict(e) for e in rows]
