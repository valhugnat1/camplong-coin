"""
routers/casino.py - Endpoints user pour le casino (coinflip + futurs jeux).

Toutes les routes exigent un JWT user.
La logique metier vit dans services/coinflip.py ; ce router ne fait que la
validation HTTP et la conversion d'erreurs en codes HTTP.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from models import User, CoinflipRound, RouletteSpin
from schemas import CoinflipPlayIn, RouletteSpinIn
from security import current_user
from services import escrow, coinflip, roulette, settings as settings_svc


router = APIRouter(tags=["casino"])


# ─── Settings publics ─────────────────────────────────

@router.get("/casino/coinflip/config")
def get_coinflip_config(
    _user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """
    Retourne les parametres courants pour que le front affiche les bonnes
    limites et le bon multiplicateur de gain. Lit la table app_settings :
    si l'admin change l'edge, le front le voit au prochain refresh.
    """
    edge = settings_svc.get_float(db, "coinflip_edge_pct", 2.0)
    return {
        "min_bet": settings_svc.get_int(db, "coinflip_min_bet", 1),
        "max_bet": settings_svc.get_int(db, "coinflip_max_bet", 200),
        "edge_pct": edge,
        # Pour l'affichage : "x1.96" si edge = 2%
        "win_multiplier": 2 * (1 - edge / 100),
    }


# ─── Play ─────────────────────────────────────────────

@router.post("/casino/coinflip/play")
def play_coinflip(
    body: CoinflipPlayIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """
    Joue une partie. Lock, tirage, payout - tout en une requete.

    En cas d'erreur metier (mise hors limites, solde insuffisant,
    casino_bank manquant) → 400.
    En cas d'echec on-chain inattendu → 500 et l'admin doit regler.
    """
    try:
        result = coinflip.play(
            db, user,
            bet=body.bet,
            choice=body.choice,
            client_seed=body.client_seed,
        )
    except coinflip.CoinflipError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    except escrow.EscrowError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    except Exception as e:
        # Si le lock a deja reussi, le rollback annule la ligne
        # CoinflipRound mais PAS la tx on-chain. C'est rare ; le
        # journal des transactions garde la trace pour l'admin.
        db.rollback()
        raise HTTPException(500, f"Echec coinflip : {e}")

    return result.to_dict()


# ─── Historique user ──────────────────────────────────

@router.get("/me/coinflip")
def my_coinflip_history(
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(CoinflipRound)
          .filter(CoinflipRound.username == user.username)
          .order_by(CoinflipRound.ts.desc())
          .limit(limit)
          .all()
    )
    return [coinflip.history_dict(r) for r in rows]


# ═══════════════════════════════════════════════════════
#  Roulette europeenne (37 cases)
# ═══════════════════════════════════════════════════════

@router.get("/casino/roulette/config")
def get_roulette_config(
    _user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """
    Limites de mise (lues en DB pour suivre les changements admin a chaud).
    Pas d'edge_pct configurable : l'edge est mecanique (1/37 = 2.70%).
    """
    return {
        "min_bet": settings_svc.get_int(db, "roulette_min_bet", 1),
        "max_bet": settings_svc.get_int(db, "roulette_max_bet", 200),
        "house_edge_pct": round(100 / 37, 2),  # constant ~2.70
    }


@router.post("/casino/roulette/spin")
def spin_roulette(
    body: RouletteSpinIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """
    Joue un spin : N mises agregees → 1 lock total, 1 payout net.
    En cas d'erreur metier (mise hors limites, spot invalide, solde) → 400.
    """
    try:
        bets_list = [b.model_dump() for b in body.bets]
        result = roulette.spin(
            db, user,
            bets=bets_list,
            client_seed=body.client_seed,
        )
    except roulette.RouletteError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    except escrow.EscrowError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Echec spin roulette : {e}")

    return result.to_dict()


@router.get("/me/roulette")
def my_roulette_history(
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(RouletteSpin)
          .filter(RouletteSpin.username == user.username)
          .order_by(RouletteSpin.ts.desc())
          .limit(limit)
          .all()
    )
    return [roulette.history_dict(r) for r in rows]
