"""
routers/bets.py - Endpoints user pour les paris communautaires.

Cycle de vie :
  open  ──(creator DELETE, si 0 participation)─→ cancelled
  open  ──(arbiter POST /resolve | community POST /vote x2 concordants
           | admin)                              ─→ resolved
  open  + deadline passee + cron                ─→ expired

Modele : mise unique fixe, 2 a 6 options, N participants. Chaque user mise
au plus une fois (sur une seule option) par pari. Resolution = repartition
egale du pot total entre les participants de l'option gagnante (le reste de
division reste dans bets_escrow).

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
from models import User, Bet, BetOption, BetParticipation, BetVote
from schemas import CreateBetIn, JoinBetIn, VoteBetIn, ResolveBetIn
from security import current_user
from services import escrow
from email_service import (
    send_bet_arbiter_assigned, send_bet_joined, send_bet_resolved,
)
from config import BETS

router = APIRouter(tags=["bets"])

BETS_ESCROW_ROLE = "bets_escrow"
COMMUNITY_RESOLVED_BY = "__community__"
ADMIN_RESOLVED_BY = "__admin__"
EXPIRED_RESOLVED_BY = "__expired__"


# ─── Serialisation ─────────────────────────────────────

def _options_for(db: Session, bet_id: int) -> list[BetOption]:
    return (
        db.query(BetOption)
          .filter(BetOption.bet_id == bet_id)
          .order_by(BetOption.position, BetOption.id)
          .all()
    )


def _participations_for(db: Session, bet_id: int) -> list[BetParticipation]:
    return (
        db.query(BetParticipation)
          .filter(BetParticipation.bet_id == bet_id)
          .order_by(BetParticipation.joined_at, BetParticipation.id)
          .all()
    )


def _votes_for(db: Session, bet_id: int) -> list[BetVote]:
    return (
        db.query(BetVote)
          .filter(BetVote.bet_id == bet_id)
          .order_by(BetVote.voted_at, BetVote.id)
          .all()
    )


def _bet_dict(
    db: Session,
    b: Bet,
    *,
    me: Optional[str] = None,
    options: Optional[list[BetOption]] = None,
    parts: Optional[list[BetParticipation]] = None,
    votes: Optional[list[BetVote]] = None,
) -> dict:
    """
    Serialise un pari avec ses options + participants + votes. Si me est
    fourni, on ajoute mes infos contextuelles (my_role, my_option_id, my_vote).
    """
    if options is None:
        options = _options_for(db, b.id)
    if parts is None:
        parts = _participations_for(db, b.id)
    if votes is None:
        votes = _votes_for(db, b.id)

    # ─── Agregats par option (compte + montant total)
    counts = {o.id: 0 for o in options}
    sums = {o.id: 0 for o in options}
    for p in parts:
        if p.option_id in counts:
            counts[p.option_id] += 1
            sums[p.option_id] += p.amount

    options_out = [
        {
            "id": o.id,
            "label": o.label,
            "position": o.position,
            "participants_count": counts[o.id],
            "total_staked": sums[o.id],
        }
        for o in options
    ]

    pot_total = sum(p.amount for p in parts)

    # ─── Winning label (si resolu et pas void)
    winning_label = None
    if b.status == "resolved" and not b.resolution_void and b.resolution_option_id:
        wo = next((o for o in options if o.id == b.resolution_option_id), None)
        if wo:
            winning_label = wo.label

    out = {
        "id": b.id,
        "creator_username": b.creator_username,
        "statement": b.statement,
        "deadline": b.deadline.isoformat() + "Z" if b.deadline else None,
        "type": b.type,
        "stake": b.stake,
        "arbiter_username": b.arbiter_username,
        "status": b.status,
        "resolution_option_id": b.resolution_option_id,
        "resolution_void": b.resolution_void,
        "resolved_at": b.resolved_at.isoformat() + "Z" if b.resolved_at else None,
        "resolved_by": b.resolved_by,
        "winning_label": winning_label,
        "created_at": b.created_at.isoformat() + "Z" if b.created_at else None,
        "options": options_out,
        "participants_count": len(parts),
        "pot_total": pot_total,
        "participants": [
            {
                "username": p.username,
                "option_id": p.option_id,
                "amount": p.amount,
                "joined_at": p.joined_at.isoformat() + "Z" if p.joined_at else None,
                "tx_hash_lock": p.tx_hash_lock,
                "tx_hash_payout": p.tx_hash_payout,
            }
            for p in parts
        ],
        "votes_count": len(votes),
        "votes": [
            {
                "voter_username": v.voter_username,
                "option_id": v.option_id,   # NULL = void
                "voted_at": v.voted_at.isoformat() + "Z" if v.voted_at else None,
            }
            for v in votes
        ],
    }

    if me is not None:
        my_part = next((p for p in parts if p.username == me), None)
        my_vote = next((v for v in votes if v.voter_username == me), None)
        if me == b.creator_username:
            my_role = "creator"
        elif me == b.arbiter_username:
            my_role = "arbiter"
        elif my_part:
            my_role = "participant"
        else:
            my_role = "observer"
        out["my_role"] = my_role
        out["my_option_id"] = my_part.option_id if my_part else None
        out["my_vote_option_id"] = my_vote.option_id if my_vote else None
        out["my_has_voted"] = my_vote is not None

    return out


# ─── Helpers email ─────────────────────────────────────

def _user_email(db: Session, username: Optional[str]) -> Optional[str]:
    if not username:
        return None
    row = db.query(User.email).filter(User.username == username).scalar()
    return row


# ─── Helpers metier ────────────────────────────────────

def _ensure_user_exists(db: Session, username: str, label: str) -> User:
    u = db.get(User, username)
    if not u or u.account_type != "user":
        raise HTTPException(400, f"{label} '{username}' introuvable")
    return u


def _try_community_settlement(
    db: Session, bet: Bet, votes: list[BetVote], background_tasks: BackgroundTasks
) -> bool:
    """
    Si 2 votes au moins pointent vers la meme option_id (ou tous les 2 vers
    NULL=void), declenche le settlement. Retourne True si settle a eu lieu.

    Le caller doit avoir verrouille la ligne bet (with_for_update). Le commit
    final reste a sa charge.
    """
    # Regroupe les votes par cible : option_id ou 'void' (None)
    targets: dict = {}
    for v in votes:
        k = v.option_id if v.option_id is not None else "void"
        targets[k] = targets.get(k, 0) + 1

    winner_key = next((k for k, c in targets.items() if c >= 2), None)
    if winner_key is None:
        return False

    resolution_option_id = None if winner_key == "void" else winner_key
    _settle_resolved(
        db, bet,
        resolution_option_id=resolution_option_id,
        resolved_by=COMMUNITY_RESOLVED_BY,
        background_tasks=background_tasks,
    )
    return True


def _settle_resolved(
    db: Session,
    bet: Bet,
    *,
    resolution_option_id: Optional[int],
    resolved_by: str,
    background_tasks: Optional[BackgroundTasks] = None,
) -> None:
    """
    Execute les mouvements on-chain et met a jour le statut.

    - resolution_option_id None : void, refund de tous les participants.
    - resolution_option_id : tous les CAMP du pot vont aux participants de
      cette option, repartis a part egale (floor). Le reste eventuel reste
      dans bets_escrow.

    Cas particulier "solo bet" : si l'option gagnante n'a aucun participant
    OU si une seule option a des participants au moment de la resolution
    (toutes les mises sont du meme cote), on force le void.

    Le caller commit + notifie. Cette fonction n'appelle pas db.commit().
    """
    parts = _participations_for(db, bet.id)
    options = _options_for(db, bet.id)

    options_with_parts = {p.option_id for p in parts}

    # Force void si solo bet
    if not bet.resolution_void:
        if len(options_with_parts) <= 1 and resolution_option_id is not None:
            # Une seule option a des participants : on void
            resolution_option_id = None
        elif resolution_option_id is not None and not any(
            p.option_id == resolution_option_id for p in parts
        ):
            # L'option gagnante n'a pas de participants : void aussi (cas pathologique)
            resolution_option_id = None

    is_void = resolution_option_id is None
    bet.resolution_void = is_void
    bet.resolution_option_id = resolution_option_id
    bet.status = "resolved"
    bet.resolved_at = datetime.datetime.utcnow()
    bet.resolved_by = resolved_by

    # ─── Mouvements on-chain
    if is_void:
        # Refund chaque participant
        for p in parts:
            u = db.get(User, p.username)
            if not u:
                continue
            tx = escrow.release(
                db, BETS_ESCROW_ROLE, u, p.amount,
                f"bet #{bet.id} void refund",
            )
            p.tx_hash_payout = tx
    else:
        winners = [p for p in parts if p.option_id == resolution_option_id]
        if not winners:
            # Garde-fou (deja gere ci-dessus). Pas de payout.
            return

        pot = sum(p.amount for p in parts)
        share = pot // len(winners)   # floor, le reste reste en escrow
        if share <= 0:
            # Pari microscopique, pas de payout possible (ne devrait pas
            # arriver avec stake >= 1 CAMP).
            return

        for p in winners:
            u = db.get(User, p.username)
            if not u:
                continue
            tx = escrow.release(
                db, BETS_ESCROW_ROLE, u, share,
                f"bet #{bet.id} payout (option #{resolution_option_id})",
            )
            p.tx_hash_payout = tx

    # ─── Notifs (best-effort, en background)
    if background_tasks is not None:
        # On serialise avec les infos a chaud pour le mail (winning_label,
        # bet.resolution_void deja a jour).
        snap = _bet_dict(db, bet, options=options, parts=parts)
        for p in parts:
            em = _user_email(db, p.username)
            if not em:
                continue
            user_won = (not is_void) and p.option_id == resolution_option_id
            payout = 0
            if is_void:
                payout = p.amount
            elif user_won:
                pot = snap["pot_total"]
                winners_count = sum(
                    1 for pp in parts if pp.option_id == resolution_option_id
                )
                payout = pot // winners_count if winners_count else 0
            background_tasks.add_task(
                send_bet_resolved, snap, em, p.username, user_won, payout,
            )


# ─── Create ────────────────────────────────────────────

@router.post("/bets")
def create_bet(
    body: CreateBetIn,
    background_tasks: BackgroundTasks,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    # ─── Validations metier ───────────────────────────────
    if body.stake < BETS["min_stake"] or body.stake > BETS["max_stake"]:
        raise HTTPException(
            400,
            f"Mise hors limites ({BETS['min_stake']}-{BETS['max_stake']} CAMP)"
        )

    deadline = body.deadline.replace(tzinfo=None) if body.deadline.tzinfo else body.deadline
    if deadline <= datetime.datetime.utcnow():
        raise HTTPException(400, "Deadline doit etre dans le futur")

    # Determine la liste finale des options selon le type
    if body.type == "yes_no":
        labels = ["Oui", "Non"]
    else:
        if not body.options:
            raise HTTPException(400, "Options requises pour un pari multi-choix")
        # Normalisation : strip, dedup, garde l'ordre
        cleaned = []
        seen = set()
        for raw in body.options:
            s = (raw or "").strip()
            if not s:
                continue
            if s.lower() in seen:
                continue
            if len(s) > 64:
                raise HTTPException(400, f"Option trop longue (max 64 char): {s}")
            seen.add(s.lower())
            cleaned.append(s)
        if len(cleaned) < BETS["min_options"] or len(cleaned) > BETS["max_options"]:
            raise HTTPException(
                400,
                f"Entre {BETS['min_options']} et {BETS['max_options']} options "
                f"distinctes (recu {len(cleaned)})"
            )
        labels = cleaned

    if body.creator_option_index is not None:
        if body.creator_option_index < 0 or body.creator_option_index >= len(labels):
            raise HTTPException(400, "creator_option_index hors limites")

    # Arbitre : doit exister, etre un vrai user, et != creator
    if body.arbiter_username:
        if body.arbiter_username == user.username:
            raise HTTPException(400, "Tu ne peux pas etre ton propre arbitre")
        _ensure_user_exists(db, body.arbiter_username, "Arbitre")

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

    # ─── Creation DB
    bet = Bet(
        creator_username=user.username,
        statement=body.statement,
        deadline=deadline,
        type=body.type,
        stake=body.stake,
        arbiter_username=body.arbiter_username,
        status="open",
    )
    db.add(bet)
    db.flush()

    # Options dans l'ordre
    created_options: list[BetOption] = []
    for i, lbl in enumerate(labels):
        opt = BetOption(bet_id=bet.id, label=lbl, position=i)
        db.add(opt)
        created_options.append(opt)
    db.flush()  # pour avoir les ids

    # Participation eventuelle du createur
    if body.creator_option_index is not None:
        chosen = created_options[body.creator_option_index]
        # Lock on-chain (avant le commit DB)
        try:
            tx = escrow.lock(
                db, user, BETS_ESCROW_ROLE, body.stake,
                f"bet #{bet.id} creator stake (option \"{chosen.label}\")",
            )
        except escrow.EscrowError as e:
            db.rollback()
            raise HTTPException(400, str(e))
        except Exception as e:
            db.rollback()
            raise HTTPException(500, f"Echec du lock on-chain : {e}")

        part = BetParticipation(
            bet_id=bet.id,
            option_id=chosen.id,
            username=user.username,
            amount=body.stake,
            tx_hash_lock=tx,
        )
        db.add(part)

    db.commit()
    db.refresh(bet)

    # ─── Notif arbitre (background, non bloquant)
    if bet.arbiter_username:
        arb_email = _user_email(db, bet.arbiter_username)
        if arb_email:
            background_tasks.add_task(
                send_bet_arbiter_assigned,
                _bet_dict(db, bet, options=created_options),
                arb_email,
            )

    return _bet_dict(db, bet, me=user.username)


# ─── List ──────────────────────────────────────────────

@router.get("/bets")
def list_bets(
    status: str = Query("all", pattern="^(all|open|resolved|cancelled|expired)$"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Bet).order_by(desc(Bet.created_at))
    if status != "all":
        q = q.filter(Bet.status == status)
    bets = q.all()
    # Optimisation : on pourrait batch les options/parts/votes, mais le
    # volume reste petit pour un site entre potes.
    return [_bet_dict(db, b, me=user.username) for b in bets]


@router.get("/bets/{bet_id}")
def get_bet(
    bet_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    bet = db.get(Bet, bet_id)
    if not bet:
        raise HTTPException(404, "Pari introuvable")
    return _bet_dict(db, bet, me=user.username)


# ─── Join (anyone qui n'a pas deja mise) ───────────────

@router.post("/bets/{bet_id}/join")
def join_bet(
    bet_id: int,
    body: JoinBetIn,
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
    if bet.status != "open":
        raise HTTPException(400, f"Pari non disponible (statut: {bet.status})")
    if bet.deadline <= datetime.datetime.utcnow():
        raise HTTPException(400, "Deadline deja passee")

    # L'arbitre ne peut pas jouer (conflit d'interet)
    if bet.arbiter_username == user.username:
        raise HTTPException(400, "L'arbitre ne peut pas participer a son propre pari")

    # Une participation max par user
    existing = (
        db.query(BetParticipation)
          .filter(
              BetParticipation.bet_id == bet_id,
              BetParticipation.username == user.username,
          )
          .first()
    )
    if existing:
        raise HTTPException(
            400,
            "Tu as deja une mise sur ce pari (1 mise max par user). "
            "Il faut annuler avant de changer d'option (pas encore supporte)."
        )

    # Verifie que l'option existe et appartient au pari
    opt = (
        db.query(BetOption)
          .filter(BetOption.id == body.option_id, BetOption.bet_id == bet_id)
          .first()
    )
    if not opt:
        raise HTTPException(400, "Option invalide pour ce pari")

    # Lock on-chain
    try:
        tx = escrow.lock(
            db, user, BETS_ESCROW_ROLE, bet.stake,
            f"bet #{bet.id} stake (option \"{opt.label}\")",
        )
    except escrow.EscrowError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Echec du lock on-chain : {e}")

    part = BetParticipation(
        bet_id=bet.id,
        option_id=opt.id,
        username=user.username,
        amount=bet.stake,
        tx_hash_lock=tx,
    )
    db.add(part)
    db.commit()
    db.refresh(bet)

    # Notif createur si != joiner
    if bet.creator_username != user.username:
        creator_email = _user_email(db, bet.creator_username)
        if creator_email:
            background_tasks.add_task(
                send_bet_joined,
                _bet_dict(db, bet),
                creator_email,
                user.username,
                opt.label,
            )

    return _bet_dict(db, bet, me=user.username)


# ─── Cancel ────────────────────────────────────────────

@router.delete("/bets/{bet_id}")
def cancel_bet(
    bet_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """
    Annulation par le createur.
    - Si zero participation : annulation simple (status -> cancelled).
    - Si participations : on void (refund tous), comme un settlement void.
      Le createur garde la main pour eviter d'avoir besoin de l'admin pour
      un pari ou personne n'a engage.
    """
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

    parts = _participations_for(db, bet.id)

    if not parts:
        # Pas de mise, pas de mouvement
        bet.status = "cancelled"
        bet.resolved_at = datetime.datetime.utcnow()
        bet.resolved_by = user.username
        db.commit()
        db.refresh(bet)
        return _bet_dict(db, bet, me=user.username)

    # Sinon, void refund
    try:
        for p in parts:
            u = db.get(User, p.username)
            if not u:
                continue
            tx = escrow.release(
                db, BETS_ESCROW_ROLE, u, p.amount,
                f"bet #{bet.id} cancel refund",
            )
            p.tx_hash_payout = tx
    except escrow.EscrowError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Echec du refund on-chain : {e}")

    bet.status = "cancelled"
    bet.resolution_void = True
    bet.resolved_at = datetime.datetime.utcnow()
    bet.resolved_by = user.username
    db.commit()
    db.refresh(bet)
    return _bet_dict(db, bet, me=user.username)


# ─── Resolve (arbiter only) ────────────────────────────

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
    if bet.status != "open":
        raise HTTPException(400, f"Pari non resolvable (statut: {bet.status})")
    if not bet.arbiter_username:
        raise HTTPException(403, "Aucun arbitre designe, resolution communautaire ou admin")
    if bet.arbiter_username != user.username:
        raise HTTPException(403, "Tu n'es pas l'arbitre designe")

    if body.option_id is not None:
        opt = (
            db.query(BetOption)
              .filter(BetOption.id == body.option_id, BetOption.bet_id == bet_id)
              .first()
        )
        if not opt:
            raise HTTPException(400, "Option invalide pour ce pari")

    try:
        _settle_resolved(
            db, bet,
            resolution_option_id=body.option_id,
            resolved_by=user.username,
            background_tasks=background_tasks,
        )
    except escrow.EscrowError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Echec du settlement on-chain : {e}")

    db.commit()
    db.refresh(bet)
    return _bet_dict(db, bet, me=user.username)


# ─── Vote (communautaire) ──────────────────────────────

@router.post("/bets/{bet_id}/vote")
def vote_bet(
    bet_id: int,
    body: VoteBetIn,
    background_tasks: BackgroundTasks,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """
    Vote communautaire (n'importe quel user). 1 vote par pari par user
    (modifiable tant que le pari n'est pas resolu). option_id = NULL = void.
    Quand 2 votes pointent vers la meme cible, le pari est resolu auto
    (resolved_by = '__community__').
    """
    bet = (
        db.query(Bet)
          .filter(Bet.id == bet_id)
          .with_for_update()
          .first()
    )
    if not bet:
        raise HTTPException(404, "Pari introuvable")
    if bet.status != "open":
        raise HTTPException(400, f"Pari non votable (statut: {bet.status})")
    if bet.arbiter_username:
        raise HTTPException(
            400,
            f"Pari avec arbitre designe ({bet.arbiter_username}), vote communautaire desactive"
        )

    # Validation option_id (None autorise = vote void)
    if body.option_id is not None:
        opt = (
            db.query(BetOption)
              .filter(BetOption.id == body.option_id, BetOption.bet_id == bet_id)
              .first()
        )
        if not opt:
            raise HTTPException(400, "Option invalide pour ce pari")

    # Upsert du vote
    existing = (
        db.query(BetVote)
          .filter(BetVote.bet_id == bet_id, BetVote.voter_username == user.username)
          .first()
    )
    if existing:
        existing.option_id = body.option_id
        existing.voted_at = datetime.datetime.utcnow()
    else:
        db.add(BetVote(
            bet_id=bet.id,
            voter_username=user.username,
            option_id=body.option_id,
        ))
    db.flush()

    # Recharge les votes a jour
    votes = _votes_for(db, bet.id)

    # Tente settlement si accord
    try:
        settled = _try_community_settlement(db, bet, votes, background_tasks)
    except escrow.EscrowError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Echec du settlement on-chain : {e}")

    db.commit()
    db.refresh(bet)
    return _bet_dict(db, bet, me=user.username)


# ─── /me/bets ──────────────────────────────────────────

@router.get("/me/bets")
def list_my_bets(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """
    Tous les paris ou le user est creator, arbitre ou participant.
    """
    creator_ids = db.query(Bet.id).filter(Bet.creator_username == user.username)
    arbiter_ids = db.query(Bet.id).filter(Bet.arbiter_username == user.username)
    part_ids = (
        db.query(BetParticipation.bet_id)
          .filter(BetParticipation.username == user.username)
    )

    rows = (
        db.query(Bet)
          .filter(or_(
              Bet.id.in_(creator_ids),
              Bet.id.in_(arbiter_ids),
              Bet.id.in_(part_ids),
          ))
          .order_by(desc(Bet.created_at))
          .all()
    )

    return [_bet_dict(db, b, me=user.username) for b in rows]
