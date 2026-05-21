"""
routers/bets.py - Endpoints user pour les paris P2P.

Cycle de vie :
  open ─ (creator DELETE) ─→ cancelled
  open ─ (matcher POST /match) ─→ matched ─ (arbiter POST /resolve) ─→ resolved
  open|matched + cron deadline ─→ expired (refund)

Toutes les routes exigent un JWT user.
Pattern atomique : la tx on-chain (lock/release) se fait AVANT de toucher
au statut DB. Si elle echoue, on rollback et le statut reste coherent.
"""
import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc

from database import get_db
from models import User, Bet
from schemas import CreateBetIn, ResolveBetIn
from security import current_user
from services import escrow
from email_service import (
    send_bet_arbiter_assigned, send_bet_matched, send_bet_resolved,
)
from config import BETS

router = APIRouter(tags=["bets"])

BETS_ESCROW_ROLE = "bets_escrow"
BOTH_PLAYERS_RESOLVED_BY = "__both_players__"


# ─── Serialisation ─────────────────────────────────────

def _bet_dict(b: Bet, my_role: Optional[str] = None) -> dict:
    out = {
        "id": b.id,
        "creator_username": b.creator_username,
        "statement": b.statement,
        "category": b.category,
        "deadline": b.deadline.isoformat() + "Z" if b.deadline else None,

        "stake_creator": b.stake_creator,
        "stake_opponent": b.stake_opponent,
        "odds_num": b.odds_num,
        "odds_den": b.odds_den,
        "creator_side": b.creator_side,

        "opponent_username": b.opponent_username,
        "arbiter_username": b.arbiter_username,
        "arbiter_fee_pct": b.arbiter_fee_pct,

        "status": b.status,
        "resolution": b.resolution,
        "resolved_at": b.resolved_at.isoformat() + "Z" if b.resolved_at else None,
        "resolved_by": b.resolved_by,

        "creator_vote": b.creator_vote,
        "opponent_vote": b.opponent_vote,

        "created_at": b.created_at.isoformat() + "Z" if b.created_at else None,
        "matched_at": b.matched_at.isoformat() + "Z" if b.matched_at else None,

        "tx_hash_lock_creator": b.tx_hash_lock_creator,
        "tx_hash_lock_opponent": b.tx_hash_lock_opponent,
        "tx_hash_payout_winner": b.tx_hash_payout_winner,
        "tx_hash_payout_arbiter": b.tx_hash_payout_arbiter,
    }
    if my_role is not None:
        out["my_role"] = my_role
    return out


# ─── Helpers email ─────────────────────────────────────

def _user_email(db: Session, username: Optional[str]) -> Optional[str]:
    if not username:
        return None
    row = db.query(User.email).filter(User.username == username).scalar()
    return row


# ─── Create ────────────────────────────────────────────

@router.post("/bets")
def create_bet(
    body: CreateBetIn,
    background_tasks: BackgroundTasks,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    # ─── Validations metier
    if body.stake_creator < BETS["min_stake"] or body.stake_creator > BETS["max_stake"]:
        raise HTTPException(
            400,
            f"Mise hors limites ({BETS['min_stake']}-{BETS['max_stake']} CAMP)"
        )

    # Deadline future. Comparaison naive UTC.
    deadline = body.deadline.replace(tzinfo=None) if body.deadline.tzinfo else body.deadline
    if deadline <= datetime.datetime.utcnow():
        raise HTTPException(400, "Deadline doit etre dans le futur")

    # Mise opposee derivee de la cote. On refuse les arrondis pour eviter
    # de payer en fractions de CAMP (la DB stocke en entiers).
    if (body.stake_creator * body.odds_den) % body.odds_num != 0:
        raise HTTPException(
            400, "Cote/mise produit un montant fractionnaire (stake * den % num != 0)"
        )
    stake_opponent = body.stake_creator * body.odds_den // body.odds_num
    if stake_opponent <= 0:
        raise HTTPException(400, "Mise opposee invalide")

    # Arbitre : doit exister, etre un vrai user, et != creator
    if body.arbiter_username:
        if body.arbiter_username == user.username:
            raise HTTPException(400, "Tu ne peux pas etre ton propre arbitre")
        arb = db.get(User, body.arbiter_username)
        if not arb or arb.account_type != "user":
            raise HTTPException(400, f"Arbitre '{body.arbiter_username}' introuvable")
    elif body.arbiter_fee_pct and body.arbiter_fee_pct > 0:
        raise HTTPException(400, "Une commission arbitre suppose un arbitre designe")

    # Anti-spam : limite de paris ouverts par user
    open_count = (
        db.query(Bet)
          .filter(Bet.creator_username == user.username, Bet.status == "open")
          .count()
    )
    if open_count >= BETS["max_open_bets_per_user"]:
        raise HTTPException(
            400,
            f"Tu as deja {open_count} paris ouverts (max "
            f"{BETS['max_open_bets_per_user']}). Annule-en un avant d'en creer un autre."
        )

    # ─── Creation DB (status open, sans tx_hash)
    bet = Bet(
        creator_username=user.username,
        statement=body.statement,
        category=body.category,
        deadline=deadline,
        stake_creator=body.stake_creator,
        stake_opponent=stake_opponent,
        odds_num=body.odds_num,
        odds_den=body.odds_den,
        creator_side=body.creator_side,
        arbiter_username=body.arbiter_username,
        arbiter_fee_pct=body.arbiter_fee_pct or 0,
        status="open",
    )
    db.add(bet)
    db.flush()  # pour avoir bet.id avant le lock

    # ─── Lock on-chain (tx_hash recupere avant le commit DB)
    try:
        tx = escrow.lock(
            db, user, BETS_ESCROW_ROLE, body.stake_creator,
            f"bet #{bet.id} stake creator",
        )
    except escrow.EscrowError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Echec du lock on-chain : {e}")

    bet.tx_hash_lock_creator = tx
    db.commit()
    db.refresh(bet)

    # ─── Notif arbitre (background, non bloquant)
    if bet.arbiter_username:
        arb_email = _user_email(db, bet.arbiter_username)
        if arb_email:
            background_tasks.add_task(
                send_bet_arbiter_assigned, _bet_dict(bet), arb_email,
            )

    return _bet_dict(bet)


# ─── List ──────────────────────────────────────────────

@router.get("/bets")
def list_bets(
    status: str = Query("all", pattern="^(all|open|matched|resolved|cancelled|expired)$"),
    category: Optional[str] = Query(None),
    _user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Bet).order_by(desc(Bet.created_at))
    if status != "all":
        q = q.filter(Bet.status == status)
    if category:
        q = q.filter(Bet.category == category)
    return [_bet_dict(b) for b in q.all()]


@router.get("/bets/{bet_id}")
def get_bet(
    bet_id: int,
    _user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    bet = db.get(Bet, bet_id)
    if not bet:
        raise HTTPException(404, "Pari introuvable")
    return _bet_dict(bet)


# ─── Match ─────────────────────────────────────────────

@router.post("/bets/{bet_id}/match")
def match_bet(
    bet_id: int,
    background_tasks: BackgroundTasks,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    # Verrou pessimiste : deux users qui tentent de matcher simultanement,
    # le second voit status != 'open' et recoit une erreur claire.
    bet = (
        db.query(Bet)
          .filter(Bet.id == bet_id)
          .with_for_update()
          .first()
    )
    if not bet:
        raise HTTPException(404, "Pari introuvable")
    if bet.status != "open":
        raise HTTPException(400, f"Pari non disponible (statut: {bet.status})")
    if bet.creator_username == user.username:
        raise HTTPException(400, "Tu ne peux pas matcher ton propre pari")
    if bet.arbiter_username == user.username:
        raise HTTPException(400, "L'arbitre ne peut pas etre le matcher")
    if bet.deadline <= datetime.datetime.utcnow():
        raise HTTPException(400, "Deadline deja passee")

    try:
        tx = escrow.lock(
            db, user, BETS_ESCROW_ROLE, bet.stake_opponent,
            f"bet #{bet.id} stake opponent",
        )
    except escrow.EscrowError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Echec du lock on-chain : {e}")

    bet.opponent_username = user.username
    bet.tx_hash_lock_opponent = tx
    bet.status = "matched"
    bet.matched_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(bet)

    # Notif creator
    creator_email = _user_email(db, bet.creator_username)
    if creator_email:
        background_tasks.add_task(
            send_bet_matched, _bet_dict(bet), creator_email, user.username,
        )

    return _bet_dict(bet)


# ─── Cancel (creator only, only if open) ───────────────

@router.delete("/bets/{bet_id}")
def cancel_bet(
    bet_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    bet = (
        db.query(Bet)
          .filter(Bet.id == bet_id)
          .with_for_update()
          .first()
    )
    if not bet:
        raise HTTPException(404, "Pari introuvable")
    if bet.creator_username != user.username:
        raise HTTPException(403, "Seul le createur peut annuler son pari")
    if bet.status != "open":
        raise HTTPException(400, f"Pari non annulable (statut: {bet.status})")

    creator = db.get(User, bet.creator_username)
    try:
        escrow.release(
            db, BETS_ESCROW_ROLE, creator, bet.stake_creator,
            f"bet #{bet.id} refund cancel",
        )
    except escrow.EscrowError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Echec du refund on-chain : {e}")

    bet.status = "cancelled"
    db.commit()
    db.refresh(bet)
    return _bet_dict(bet)


# ─── Resolve (arbiter only) ────────────────────────────

def _settle_resolved(db: Session, bet: Bet, resolution: str, resolved_by: str) -> None:
    """
    Execute les mouvements on-chain associes a une resolution puis met a jour
    le statut DB. Utilise par /bets/{id}/resolve ET /admin/bets/{id}/resolve.

    Tous les release() font db.add() de Transaction lignes ; le commit final
    se fait par le caller.
    """
    creator = db.get(User, bet.creator_username)
    opponent = db.get(User, bet.opponent_username) if bet.opponent_username else None

    if resolution == "void":
        # Refund integral des deux cotes
        escrow.release(
            db, BETS_ESCROW_ROLE, creator, bet.stake_creator,
            f"bet #{bet.id} refund (void)",
        )
        if opponent:
            escrow.release(
                db, BETS_ESCROW_ROLE, opponent, bet.stake_opponent,
                f"bet #{bet.id} refund (void)",
            )
    else:
        if not opponent:
            raise escrow.EscrowError("Pas d'opponent, resolution impossible (utilise void)")

        pot = bet.stake_creator + bet.stake_opponent
        arbiter_fee = (pot * bet.arbiter_fee_pct) // 100 if bet.arbiter_username else 0
        winner_payout = pot - arbiter_fee

        winner = creator if bet.creator_side == resolution else opponent
        tx_w = escrow.release(
            db, BETS_ESCROW_ROLE, winner, winner_payout,
            f"bet #{bet.id} winner payout",
        )
        bet.tx_hash_payout_winner = tx_w

        if arbiter_fee > 0 and bet.arbiter_username:
            arbiter = db.get(User, bet.arbiter_username)
            if arbiter:
                tx_a = escrow.release(
                    db, BETS_ESCROW_ROLE, arbiter, arbiter_fee,
                    f"bet #{bet.id} arbiter fee",
                )
                bet.tx_hash_payout_arbiter = tx_a

    bet.status = "resolved"
    bet.resolution = resolution
    bet.resolved_at = datetime.datetime.utcnow()
    bet.resolved_by = resolved_by


@router.post("/bets/{bet_id}/resolve")
def resolve_bet(
    bet_id: int,
    body: ResolveBetIn,
    background_tasks: BackgroundTasks,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    bet = (
        db.query(Bet)
          .filter(Bet.id == bet_id)
          .with_for_update()
          .first()
    )
    if not bet:
        raise HTTPException(404, "Pari introuvable")
    if bet.status != "matched":
        raise HTTPException(400, f"Pari non resolvable (statut: {bet.status})")
    if not bet.arbiter_username:
        raise HTTPException(403, "Aucun arbitre designe, resolution admin requise")
    if bet.arbiter_username != user.username:
        raise HTTPException(403, "Tu n'es pas l'arbitre designe")

    try:
        _settle_resolved(db, bet, body.resolution, resolved_by=user.username)
    except escrow.EscrowError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Echec du settlement on-chain : {e}")

    db.commit()
    db.refresh(bet)

    # Notifs : les deux parties
    for u_name in (bet.creator_username, bet.opponent_username):
        em = _user_email(db, u_name)
        if em:
            background_tasks.add_task(
                send_bet_resolved, _bet_dict(bet), em, u_name,
            )

    return _bet_dict(bet)


# ─── Vote (resolution amiable) ─────────────────────────

@router.post("/bets/{bet_id}/vote")
def vote_bet(
    bet_id: int,
    body: ResolveBetIn,
    background_tasks: BackgroundTasks,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """
    Vote du creator ou de l'opponent sur la resolution. Quand les deux votes
    coincident, le pari est resolu automatiquement (resolved_by =
    '__both_players__'), sans arbitre ni admin.

    Un vote peut etre change tant que les deux votes ne coincident pas
    (on ecrase le precedent). Si l'autre joueur a deja vote pareil, l'appel
    declenche le settlement immediat dans la meme transaction.
    """
    bet = (
        db.query(Bet)
          .filter(Bet.id == bet_id)
          .with_for_update()
          .first()
    )
    if not bet:
        raise HTTPException(404, "Pari introuvable")
    if bet.status != "matched":
        raise HTTPException(400, f"Pari non votable (statut: {bet.status})")
    if user.username not in (bet.creator_username, bet.opponent_username):
        raise HTTPException(403, "Seuls le createur et l'opposant peuvent voter")

    is_creator = user.username == bet.creator_username
    if is_creator:
        bet.creator_vote = body.resolution
    else:
        bet.opponent_vote = body.resolution

    # Si l'autre cote n'a pas encore vote OU vote different, on enregistre
    # juste le vote et on attend / on signale le desaccord.
    other_vote = bet.opponent_vote if is_creator else bet.creator_vote
    if other_vote is None or other_vote != body.resolution:
        db.commit()
        db.refresh(bet)
        return _bet_dict(bet)

    # Accord → settlement immediat
    try:
        _settle_resolved(db, bet, body.resolution, resolved_by=BOTH_PLAYERS_RESOLVED_BY)
    except escrow.EscrowError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Echec du settlement on-chain : {e}")

    db.commit()
    db.refresh(bet)

    # Notifs : les deux parties
    for u_name in (bet.creator_username, bet.opponent_username):
        em = _user_email(db, u_name)
        if em:
            background_tasks.add_task(
                send_bet_resolved, _bet_dict(bet), em, u_name,
            )

    return _bet_dict(bet)


# ─── /me/bets ──────────────────────────────────────────

@router.get("/me/bets")
def list_my_bets(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """
    Tous les paris ou le user est creator / opponent / arbitre.
    Dedup avec role prioritaire : creator > opponent > arbiter.
    """
    rows = (
        db.query(Bet)
          .filter(or_(
              Bet.creator_username == user.username,
              Bet.opponent_username == user.username,
              Bet.arbiter_username == user.username,
          ))
          .order_by(desc(Bet.created_at))
          .all()
    )

    def role_of(b: Bet) -> str:
        if b.creator_username == user.username:
            return "creator"
        if b.opponent_username == user.username:
            return "opponent"
        return "arbiter"

    return [_bet_dict(b, my_role=role_of(b)) for b in rows]
