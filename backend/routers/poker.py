"""
routers/poker.py - Endpoints user et admin pour le poker Texas Hold'em.

User :
  - GET    /casino/poker/tables                liste des tables ouvertes
  - GET    /casino/poker/tables/{id}/state     snapshot (poll)
  - POST   /casino/poker/tables/{id}/sit       sit-in (lock buyin)
  - POST   /casino/poker/tables/{id}/leave     sit-out (release stack)
  - POST   /casino/poker/tables/{id}/act       fold/check/call/bet/raise
  - GET    /me/poker/history                   mes mains passees

Admin :
  - GET    /admin/poker/tables                 toutes les tables + stats
  - POST   /admin/poker/tables                 creer
  - PATCH  /admin/poker/tables/{id}            update statut
  - DELETE /admin/poker/tables/{id}            supprime (refuse si sessions actives)
  - POST   /admin/poker/tables/{id}/force-end  annule la main en cours
                                                (refund de chaque mise au joueur)
"""
import datetime
import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from models import User, PokerTable, PokerSession, PokerHand
from schemas import (
    PokerSitIn, PokerActIn,
    PokerCreateTableIn,
    AdminPokerCreateTableIn, AdminPokerUpdateTableIn,
)
from security import current_user, require_admin
from services import escrow, poker as poker_svc
from blockchain import get_balance_camp


router = APIRouter(tags=["poker"])


# ═══════════════════════════════════════════════════════════════════
#  USER
# ═══════════════════════════════════════════════════════════════════

def _cascade_delete_table(db: Session, t: PokerTable) -> None:
    """
    Supprime une table + ses donnees liees (sessions historiques, mains,
    hole cards). Les FK pointent sur table_id ; tant qu'on n'a pas de
    ON DELETE CASCADE en DDL, on nettoie explicitement.
    PokerHandHole a deja un ON DELETE CASCADE -> poker_hands (cf. v4),
    donc DELETE FROM poker_hands suffit pour ses cartes privees.
    """
    db.query(PokerHand).filter(PokerHand.table_id == t.id).delete(
        synchronize_session=False,
    )
    db.query(PokerSession).filter(PokerSession.table_id == t.id).delete(
        synchronize_session=False,
    )
    db.delete(t)


def _validate_create_payload(body: PokerCreateTableIn) -> None:
    if body.blind_big < body.blind_small:
        raise HTTPException(400, "Big blind doit etre >= small blind")
    if body.min_buyin < body.blind_big:
        raise HTTPException(400, "Min buy-in doit etre >= big blind")
    if body.max_buyin < body.min_buyin:
        raise HTTPException(400, "Max buy-in doit etre >= min buy-in")


@router.get("/casino/poker/tables")
def list_tables(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Tables ouvertes + nb de joueurs assis."""
    rows = (
        db.query(PokerTable)
          .order_by(PokerTable.id.asc())
          .all()
    )
    out = []
    for t in rows:
        sessions = (
            db.query(PokerSession)
              .filter(PokerSession.table_id == t.id,
                      PokerSession.left_at.is_(None))
              .all()
        )
        out.append({
            **poker_svc.table_dict(t),
            "n_players": len(sessions),
            "players": [
                {"username": s.username, "seat": s.seat, "stack": int(s.stack)}
                for s in sessions
            ],
            "im_in": any(s.username == user.username for s in sessions),
            "im_creator": t.creator_username == user.username,
        })
    return out


@router.post("/casino/poker/tables")
def create_table(
    body: PokerCreateTableIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """
    N'importe quel user authentifie peut creer une table. Il en devient
    le createur (`creator_username`) et pourra la supprimer si elle est
    vide. L'admin garde le pouvoir d'administrer toutes les tables.
    """
    _validate_create_payload(body)
    t = PokerTable(
        name=body.name,
        blind_small=body.blind_small,
        blind_big=body.blind_big,
        min_buyin=body.min_buyin,
        max_buyin=body.max_buyin,
        max_players=body.max_players,
        status="open",
        creator_username=user.username,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return poker_svc.table_dict(t)


@router.delete("/casino/poker/tables/{table_id}")
def delete_table(
    table_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """
    Le createur peut supprimer sa propre table, a condition qu'il n'y
    ait plus de joueurs assis. Si une main est en cours, refus.
    """
    t = db.get(PokerTable, table_id)
    if t is None:
        raise HTTPException(404, "Table introuvable")
    if t.creator_username != user.username:
        raise HTTPException(
            403,
            "Seul le createur peut supprimer cette table (sinon demande a l'admin)"
        )
    active = (
        db.query(PokerSession)
          .filter(PokerSession.table_id == table_id,
                  PokerSession.left_at.is_(None))
          .count()
    )
    if active > 0:
        raise HTTPException(
            400,
            f"{active} joueur(s) encore assis : ils doivent partir d'abord"
        )
    cur = poker_svc._current_hand(db, table_id)
    if cur is not None:
        raise HTTPException(400, "Une main est encore en cours")
    _cascade_delete_table(db, t)
    db.commit()
    return {"ok": True}


@router.get("/casino/poker/tables/{table_id}/state")
def get_table_state(
    table_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """
    Snapshot d'une table (poll par le front toutes les ~2s).
    Le deal d'une nouvelle main est explicite : appelle POST /start-hand.
    """
    table = (
        db.query(PokerTable)
          .filter(PokerTable.id == table_id)
          .first()
    )
    if table is None:
        raise HTTPException(404, "Table introuvable")

    return poker_svc.state_dict(db, table, user)


@router.post("/casino/poker/tables/{table_id}/start-hand")
def start_hand(
    table_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """
    Demarre explicitement une nouvelle main. N'importe quel joueur
    assis a la table peut declencher. Le verrou SELECT FOR UPDATE
    serialise les clics concurrents.
    """
    table = (
        db.query(PokerTable)
          .filter(PokerTable.id == table_id)
          .with_for_update()
          .first()
    )
    if table is None:
        raise HTTPException(404, "Table introuvable")

    # Doit etre assis pour demarrer une main
    seated = (
        db.query(PokerSession)
          .filter(PokerSession.table_id == table_id,
                  PokerSession.username == user.username,
                  PokerSession.left_at.is_(None))
          .first()
    )
    if seated is None:
        raise HTTPException(403, "Tu dois etre assis a la table")

    cs = poker_svc.can_start_hand(db, table)
    if not cs["can_start"]:
        raise HTTPException(400, cs["reason"] or "Impossible de demarrer")

    try:
        hand = poker_svc.start_hand(db, table)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Echec demarrage main : {e}")

    if hand is None:
        raise HTTPException(400, "Pas assez de joueurs eligibles")
    return {"ok": True, "hand_id": hand.id, "hand_number": hand.hand_number}


@router.post("/casino/poker/tables/{table_id}/sit")
def sit_in_table(
    table_id: int,
    body: PokerSitIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    table = (
        db.query(PokerTable)
          .filter(PokerTable.id == table_id)
          .with_for_update()
          .first()
    )
    if table is None:
        raise HTTPException(404, "Table introuvable")

    try:
        sess = poker_svc.sit_in(db, table, user, body.buyin)
        db.commit()
    except poker_svc.PokerError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    except escrow.EscrowError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Echec sit-in : {e}")

    return {
        "ok": True,
        "session_id": sess.id,
        "seat": sess.seat,
        "stack": int(sess.stack),
        "tx_hash_buyin": sess.tx_hash_buyin,
        "new_balance": get_balance_camp(user.address),
    }


@router.post("/casino/poker/tables/{table_id}/leave")
def leave_table(
    table_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    table = (
        db.query(PokerTable)
          .filter(PokerTable.id == table_id)
          .with_for_update()
          .first()
    )
    if table is None:
        raise HTTPException(404, "Table introuvable")

    try:
        out = poker_svc.sit_out(db, table, user)
        db.commit()
    except poker_svc.PokerError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    except escrow.EscrowError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Echec sit-out : {e}")

    return {
        "ok": True,
        **out,
        "new_balance": get_balance_camp(user.address),
    }


@router.post("/casino/poker/tables/{table_id}/act")
def act_table(
    table_id: int,
    body: PokerActIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Fold/check/call/bet/raise sur la main en cours."""
    table = (
        db.query(PokerTable)
          .filter(PokerTable.id == table_id)
          .with_for_update()
          .first()
    )
    if table is None:
        raise HTTPException(404, "Table introuvable")

    hand = poker_svc._current_hand(db, table_id)
    if hand is None:
        raise HTTPException(400, "Aucune main en cours")

    try:
        result = poker_svc.act(db, table, hand, user, body.move, body.amount)
        db.commit()
    except poker_svc.PokerError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Echec action : {e}")

    return result


@router.get("/me/poker/history")
def my_poker_history(
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """
    Liste les mains finies ou j'ai participe. On filtre cote DB sur
    la presence du username dans le hand_log (LIKE). Suffisant pour
    une vingtaine de mains. Si volume important : passer par
    poker_hand_holes (un row par participation).
    """
    rows = (
        db.query(PokerHand)
          .filter(PokerHand.ended_at.isnot(None))
          .order_by(PokerHand.id.desc())
          .limit(limit * 4)   # filter cote Python ensuite
          .all()
    )
    out = []
    for h in rows:
        try:
            log = json.loads(h.hand_log)
            usernames = {p["username"] for p in log.get("players", [])}
        except Exception:
            usernames = set()
        if user.username in usernames:
            out.append(poker_svc.hand_history_dict(h))
            if len(out) >= limit:
                break
    return out


# ═══════════════════════════════════════════════════════════════════
#  ADMIN
# ═══════════════════════════════════════════════════════════════════

@router.get("/admin/poker/tables")
def admin_list_tables(
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(PokerTable)
          .order_by(PokerTable.id.asc())
          .all()
    )
    out = []
    for t in rows:
        sessions = (
            db.query(PokerSession)
              .filter(PokerSession.table_id == t.id,
                      PokerSession.left_at.is_(None))
              .all()
        )
        cur = poker_svc._current_hand(db, t.id)
        hand_n_played = (
            db.query(PokerHand)
              .filter(PokerHand.table_id == t.id,
                      PokerHand.ended_at.isnot(None))
              .count()
        )
        out.append({
            **poker_svc.table_dict(t),
            "n_players": len(sessions),
            "players": [
                {"username": s.username, "seat": s.seat, "stack": int(s.stack)}
                for s in sessions
            ],
            "n_hands_played": hand_n_played,
            "hand_in_progress": cur.id if cur else None,
        })
    return out


@router.post("/admin/poker/tables")
def admin_create_table(
    body: AdminPokerCreateTableIn,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    _validate_create_payload(body)
    t = PokerTable(
        name=body.name,
        blind_small=body.blind_small,
        blind_big=body.blind_big,
        min_buyin=body.min_buyin,
        max_buyin=body.max_buyin,
        max_players=body.max_players,
        status="open",
        creator_username=None,  # cree par l'admin
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return poker_svc.table_dict(t)


@router.patch("/admin/poker/tables/{table_id}")
def admin_update_table(
    table_id: int,
    body: AdminPokerUpdateTableIn,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    t = db.get(PokerTable, table_id)
    if t is None:
        raise HTTPException(404, "Table introuvable")
    if body.status is not None:
        t.status = body.status
    db.commit()
    db.refresh(t)
    return poker_svc.table_dict(t)


@router.delete("/admin/poker/tables/{table_id}")
def admin_delete_table(
    table_id: int,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    t = db.get(PokerTable, table_id)
    if t is None:
        raise HTTPException(404, "Table introuvable")
    active = (
        db.query(PokerSession)
          .filter(PokerSession.table_id == table_id,
                  PokerSession.left_at.is_(None))
          .count()
    )
    if active > 0:
        raise HTTPException(
            400,
            f"{active} joueur(s) encore assis : faut leur dire de partir d'abord"
        )
    _cascade_delete_table(db, t)
    db.commit()
    return {"ok": True}


@router.post("/admin/poker/tables/{table_id}/force-end")
def admin_force_end_hand(
    table_id: int,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Annule la main en cours et rend a chacun sa mise totale. Utile si une
    main bloque (joueur AFK qui doit agir). N'effectue PAS de tx on-chain
    (les stacks restent off-chain, le pot etant juste redistribue dans les
    sessions).
    """
    table = (
        db.query(PokerTable)
          .filter(PokerTable.id == table_id)
          .with_for_update()
          .first()
    )
    if table is None:
        raise HTTPException(404, "Table introuvable")

    hand = poker_svc._current_hand(db, table_id)
    if hand is None:
        raise HTTPException(400, "Aucune main en cours")

    state = json.loads(hand.hand_log)
    # Refund de chaque mise au joueur (stack += total_bet)
    sessions = poker_svc._active_sessions(db, table_id)
    by_seat = {s.seat: s for s in sessions}
    for p in state.get("players", []):
        sess = by_seat.get(p["seat"])
        if sess is not None:
            sess.stack = int(sess.stack) + int(p.get("total_bet", 0))

    state["street"] = "done"
    state["to_act_seat"] = None
    state["deck"] = []
    hand.hand_log = json.dumps(state)
    hand.ended_at = datetime.datetime.utcnow()
    hand.winners_json = json.dumps({
        "pots": [],
        "final_players": [],
        "board": state.get("board", []),
        "shown_holes": [],
        "voided": True,
        "void_reason": "admin_force_end",
    })
    db.commit()
    return {"ok": True}
