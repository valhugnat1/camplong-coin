import datetime
import bcrypt
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query
from sqlalchemy.orm import Session
from eth_account import Account
from jose import jwt

from database import get_db
from models import User, Transaction, MarketOrder, Bet
from schemas import AdminLoginIn, CreateUserIn, AmountIn, UpdateOrderIn, ResolveBetIn
from security import require_admin, fernet
from blockchain import admin_transfer, get_balance_camp, get_balance_eth, treasury
from email_service import send_user_order_done, send_bet_resolved
from config import ADMIN_PASSWORD, JWT_SECRET
from services import escrow
from routers.bets import _bet_dict, _settle_resolved, BETS_ESCROW_ROLE, _user_email

router = APIRouter(prefix="/admin", tags=["admin"])

# ─── Auth ──────────────────────────────────────────────

@router.post("/login")
def admin_login(body: AdminLoginIn):
    if body.password != ADMIN_PASSWORD:
        raise HTTPException(401, "Mot de passe incorrect")
    exp = datetime.datetime.utcnow() + datetime.timedelta(days=1)
    token = jwt.encode({"sub": "admin", "role": "admin", "exp": exp},
                       JWT_SECRET, algorithm="HS256")
    return {"token": token}


# ─── Treasury ──────────────────────────────────────────

@router.get("/treasury")
def get_treasury(_: bool = Depends(require_admin)):
    return {
        "address": treasury.address,
        "balance_eth": get_balance_eth(treasury.address),
        "balance_camp": get_balance_camp(treasury.address),
    }


# ─── Users ─────────────────────────────────────────────

@router.get("/users")
def list_all_users(_: bool = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.query(User).order_by(User.created_at).all()
    return [
        {
            "username": u.username,
            "address": u.address,
            "email": u.email,
            "created_at": u.created_at.isoformat() + "Z" if u.created_at else None,
            "balance_camp": get_balance_camp(u.address),
        }
        for u in rows
    ]


@router.post("/users")
def create_user(
    body: CreateUserIn,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if db.get(User, body.username):
        raise HTTPException(400, f"Username '{body.username}' deja pris")

    acct = Account.create()
    enc_pk = fernet.encrypt(acct.key.hex().encode()).decode()
    pwd_hash = bcrypt.hashpw(body.user_password.encode(), bcrypt.gensalt()).decode()

    new_user = User(
        username=body.username,
        password_hash=pwd_hash,
        address=acct.address,
        encrypted_private_key=enc_pk,
        email=body.email,
    )
    db.add(new_user)
    db.commit()

    camp_tx = None
    if body.initial_camp > 0:
        treasury_bal = get_balance_camp(treasury.address)
        if body.initial_camp > treasury_bal:
            raise HTTPException(400, f"Treasury insuffisante ({treasury_bal} CAMP)")
        camp_tx = admin_transfer(db, treasury.address, acct.address, body.initial_camp)
        db.add(Transaction(
            ts=datetime.datetime.utcnow(),
            from_username="__treasury__",
            to_username=body.username,
            amount=body.initial_camp,
            note="onboarding",
            tx_hash=camp_tx,
        ))
        db.commit()

    return {
        "username": body.username,
        "address": acct.address,
        "email": body.email,
        "camp_tx": camp_tx,
        "initial_camp": body.initial_camp,
    }


@router.delete("/users/{username}")
def delete_user(
    username: str,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Supprime un user. Refuse si le user a encore du CAMD on-chain
    (l'admin doit d'abord debiter manuellement via /admin/debit pour
    eviter de laisser des CAMP orphelins).
    Les transactions liees au user sont conservees (audit), seules
    les market_orders sont supprimees en cascade.
    """
    user = db.get(User, username)
    if not user:
        raise HTTPException(404, f"User '{username}' introuvable")

    balance = get_balance_camp(user.address)
    if balance > 0:
        raise HTTPException(
            400,
            f"User a encore {balance} CAMP. Debite-le d'abord via Debiter "
            f"avant suppression."
        )

    # Cascade : on supprime les orders associes (audit transactions reste)
    db.query(MarketOrder).filter(MarketOrder.username == username).delete()
    db.delete(user)
    db.commit()

    return {"status": "deleted", "username": username}


# ─── Credit / Debit ────────────────────────────────────

@router.post("/credit")
def credit_user(
    body: AmountIn,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, body.username)
    if not user:
        raise HTTPException(404, f"User '{body.username}' introuvable")

    treasury_bal = get_balance_camp(treasury.address)
    if body.amount > treasury_bal:
        raise HTTPException(400, f"Treasury insuffisante ({treasury_bal} CAMP)")

    tx_hash = admin_transfer(db, treasury.address, user.address, body.amount)

    db.add(Transaction(
        ts=datetime.datetime.utcnow(),
        from_username="__treasury__",
        to_username=user.username,
        amount=body.amount,
        note=body.note or "credit admin",
        tx_hash=tx_hash,
    ))
    db.commit()

    return {
        "tx_hash": tx_hash,
        "username": user.username,
        "new_balance_camp": get_balance_camp(user.address),
    }


@router.post("/debit")
def debit_user(
    body: AmountIn,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, body.username)
    if not user:
        raise HTTPException(404, f"User '{body.username}' introuvable")

    user_bal = get_balance_camp(user.address)
    if body.amount > user_bal:
        raise HTTPException(400, f"User n'a que {user_bal} CAMP")

    tx_hash = admin_transfer(db, user.address, treasury.address, body.amount)

    db.add(Transaction(
        ts=datetime.datetime.utcnow(),
        from_username=user.username,
        to_username="__treasury__",
        amount=body.amount,
        note=body.note or "debit admin",
        tx_hash=tx_hash,
    ))
    db.commit()

    return {
        "tx_hash": tx_hash,
        "username": user.username,
        "new_balance_camp": get_balance_camp(user.address),
    }


# ─── Market Orders ─────────────────────────────────────

def _order_dict(o: MarketOrder, user_email: str | None) -> dict:
    return {
        "id": o.id,
        "ts": o.ts.isoformat() + "Z" if o.ts else None,
        "username": o.username,
        "user_email": user_email,
        "type": o.type,
        "amount_camp": o.amount_camp,
        "amount_eur": o.amount_eur,
        "handle": o.handle or "",
        "note": o.note or "",
        "status": o.status,
        "admin_note": o.admin_note or "",
        "done_at": o.done_at.isoformat() + "Z" if o.done_at else None,
        "tx_hash": o.tx_hash,
    }


@router.get("/orders")
def list_orders(
    status: str = Query("all", pattern="^(all|pending|done|cancelled)$"),
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Liste les demandes d'achat/vente, jointes avec l'email du user."""
    q = (
        db.query(MarketOrder, User.email)
          .outerjoin(User, User.username == MarketOrder.username)
          .order_by(MarketOrder.ts.desc())
    )
    if status != "all":
        q = q.filter(MarketOrder.status == status)

    return [_order_dict(o, em) for o, em in q.all()]


@router.patch("/orders/{order_id}")
def update_order(
    order_id: int,
    body: UpdateOrderIn,
    background_tasks: BackgroundTasks,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Met a jour le statut et/ou la note admin d'une demande.

    Quand on bascule en 'done' depuis un autre statut :
      1. On execute le mouvement on-chain (atomique : si la tx echoue,
         le statut n'est pas mis a jour) :
         - BUY  -> adminTransfer(treasury -> user)  : user recoit ses CAMP
         - SELL -> adminTransfer(user -> treasury) : user envoie ses CAMP
      2. On log la tx dans la table transactions (pour l'historique user)
      3. On stocke le tx_hash sur l'order
      4. On envoie un email de confirmation au user (en background)

    Si on repasse en 'pending' ou 'cancelled' apres avoir ete 'done',
    le tx_hash et done_at sont conserves (audit, le mouvement on-chain
    est irreversible de toute facon).
    """
    order = db.get(MarketOrder, order_id)
    if not order:
        raise HTTPException(404, f"Order #{order_id} introuvable")

    previous_status = order.status
    becoming_done = body.status == "done" and previous_status != "done"

    # ─── Etape 1 : si on passe en done, on fait le mouvement on-chain
    # AVANT de toucher au statut. Si ca rate, l'order reste en pending.
    if becoming_done:
        user = db.get(User, order.username)
        if not user:
            raise HTTPException(
                400,
                f"Impossible de finaliser : user '{order.username}' n'existe plus"
            )

        if order.tx_hash:
            # Garde-fou : si l'order a deja un tx_hash, c'est qu'elle a deja
            # ete done une fois et qu'on l'a re-repassee en pending. On ne refait
            # PAS le transfert (le mouvement on-chain est irreversible).
            # On accepte juste de re-marquer le statut sans nouveau transfert.
            pass
        else:
            if order.type == "buy":
                # Treasury envoie les CAMP au user (le user a paye en EUR)
                treasury_bal = get_balance_camp(treasury.address)
                if order.amount_camp > treasury_bal:
                    raise HTTPException(
                        400,
                        f"Treasury insuffisante : {treasury_bal} CAMP disponibles, "
                        f"il en faut {order.amount_camp}. Refund ta treasury d'abord."
                    )
                from_addr, to_addr = treasury.address, user.address
                tx_from_user = "__treasury__"
                tx_to_user = order.username
                tx_note = f"order #{order.id} buy"
            else:
                # SELL : on debite le user (Hugo lui a envoye les EUR)
                user_bal = get_balance_camp(user.address)
                if order.amount_camp > user_bal:
                    raise HTTPException(
                        400,
                        f"Le user n'a que {user_bal} CAMP, impossible de debiter "
                        f"{order.amount_camp}. Il a peut-etre transfere depuis sa "
                        f"demande."
                    )
                from_addr, to_addr = user.address, treasury.address
                tx_from_user = order.username
                tx_to_user = "__treasury__"
                tx_note = f"order #{order.id} sell"

            # Execute la tx on-chain. Si ca raise, FastAPI rollback la transaction DB
            # et renvoie le detail en HTTP 500. L'order reste en pending.
            try:
                tx_hash = admin_transfer(db, from_addr, to_addr, order.amount_camp)
            except Exception as e:
                db.rollback()
                raise HTTPException(
                    500,
                    f"Echec du transfert on-chain : {e}. L'order reste en pending."
                )

            # Log dans la table transactions (pour l'historique du user)
            db.add(Transaction(
                ts=datetime.datetime.utcnow(),
                from_username=tx_from_user,
                to_username=tx_to_user,
                amount=order.amount_camp,
                note=tx_note,
                tx_hash=tx_hash,
            ))

            order.tx_hash = tx_hash

        # done_at se met a jour meme si on saute le transfert (re-done)
        order.done_at = datetime.datetime.utcnow()

    # ─── Etape 2 : update du statut et/ou note
    if body.status is not None:
        order.status = body.status

    if body.admin_note is not None:
        order.admin_note = body.admin_note

    db.commit()
    db.refresh(order)

    # ─── Etape 3 : email user (background, ne bloque pas)
    if becoming_done:
        user = db.get(User, order.username)
        if user and user.email:
            background_tasks.add_task(
                send_user_order_done,
                _order_dict(order, user.email),
                user.email,
            )

    user_email = db.query(User.email).filter(User.username == order.username).scalar()
    return _order_dict(order, user_email)


@router.delete("/orders/{order_id}")
def delete_order(
    order_id: int,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Supprime definitivement une demande (utile si test/erreur)."""
    order = db.get(MarketOrder, order_id)
    if not order:
        raise HTTPException(404, f"Order #{order_id} introuvable")
    db.delete(order)
    db.commit()
    return {"status": "deleted", "id": order_id}


# ─── Bets (admin) ──────────────────────────────────────

ADMIN_RESOLVED_BY = "__admin__"


@router.get("/bets")
def admin_list_bets(
    status: str = Query("all", pattern="^(all|open|matched|resolved|cancelled|expired)$"),
    category: str | None = Query(None),
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    q = db.query(Bet).order_by(Bet.created_at.desc())
    if status != "all":
        q = q.filter(Bet.status == status)
    if category:
        q = q.filter(Bet.category == category)
    return [_bet_dict(b) for b in q.all()]


@router.post("/bets/{bet_id}/resolve")
def admin_resolve_bet(
    bet_id: int,
    body: ResolveBetIn,
    background_tasks: BackgroundTasks,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Override de resolution : meme logique que /bets/{id}/resolve mais sans la
    contrainte arbitre. Sert pour les paris sans arbitre designe ou les overrides.
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
        raise HTTPException(400, f"Pari non resolvable (statut: {bet.status})")

    try:
        _settle_resolved(db, bet, body.resolution, resolved_by=ADMIN_RESOLVED_BY)
    except escrow.EscrowError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Echec du settlement on-chain : {e}")

    db.commit()
    db.refresh(bet)

    for u_name in (bet.creator_username, bet.opponent_username):
        em = _user_email(db, u_name)
        if em:
            background_tasks.add_task(
                send_bet_resolved, _bet_dict(bet), em, u_name,
            )

    return _bet_dict(bet)


@router.post("/bets/{bet_id}/cancel")
def admin_cancel_bet(
    bet_id: int,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Force-cancel : refund creator (et opponent si matched).
    Refus sur 'resolved' (les fonds sont deja distribues, irreversibles).
    Sur 'cancelled' ou 'expired' : no-op.
    """
    bet = (
        db.query(Bet)
          .filter(Bet.id == bet_id)
          .with_for_update()
          .first()
    )
    if not bet:
        raise HTTPException(404, "Pari introuvable")
    if bet.status == "resolved":
        raise HTTPException(400, "Pari deja resolu, fonds distribues - impossible d'annuler")
    if bet.status in ("cancelled", "expired"):
        return _bet_dict(bet)

    creator = db.get(User, bet.creator_username)
    opponent = db.get(User, bet.opponent_username) if bet.opponent_username else None

    try:
        if creator:
            escrow.release(
                db, BETS_ESCROW_ROLE, creator, bet.stake_creator,
                f"bet #{bet.id} admin cancel refund (creator)",
            )
        if bet.status == "matched" and opponent:
            escrow.release(
                db, BETS_ESCROW_ROLE, opponent, bet.stake_opponent,
                f"bet #{bet.id} admin cancel refund (opponent)",
            )
    except escrow.EscrowError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Echec du refund on-chain : {e}")

    bet.status = "cancelled"
    bet.resolved_at = datetime.datetime.utcnow()
    bet.resolved_by = ADMIN_RESOLVED_BY
    db.commit()
    db.refresh(bet)
    return _bet_dict(bet)


@router.delete("/bets/{bet_id}")
def admin_delete_bet(
    bet_id: int,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Suppression DB definitive. N'annule PAS les mouvements on-chain.
    Refus sur 'matched' / 'resolved' (fonds escrowes ou distribues -
    compromettrait l'audit). Force-cancel d'abord.
    """
    bet = db.get(Bet, bet_id)
    if not bet:
        raise HTTPException(404, "Pari introuvable")
    if bet.status in ("matched", "resolved"):
        raise HTTPException(
            400,
            f"Pari en statut '{bet.status}' : force-cancel d'abord (POST /admin/bets/{bet_id}/cancel)"
        )
    db.delete(bet)
    db.commit()
    return {"status": "deleted", "id": bet_id}
