import datetime
import bcrypt
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query
from sqlalchemy.orm import Session
from eth_account import Account
from jose import jwt

from database import get_db
from models import User, Transaction, MarketOrder
from schemas import AdminLoginIn, CreateUserIn, AmountIn, UpdateOrderIn
from security import require_admin, fernet
from blockchain import admin_transfer, get_balance_camp, get_balance_eth, treasury
from email_service import send_user_order_done
from config import ADMIN_PASSWORD, JWT_SECRET

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
    Si on passe le statut a 'done' (et qu'il n'y etait pas deja), on envoie
    un email de confirmation au user (en background, ne bloque pas la requete).
    """
    order = db.get(MarketOrder, order_id)
    if not order:
        raise HTTPException(404, f"Order #{order_id} introuvable")

    previous_status = order.status

    if body.status is not None:
        order.status = body.status
        if body.status == "done" and previous_status != "done":
            order.done_at = datetime.datetime.utcnow()
        elif body.status != "done":
            # Si on repasse en pending/cancelled, on enleve la date "done"
            order.done_at = None

    if body.admin_note is not None:
        order.admin_note = body.admin_note

    db.commit()
    db.refresh(order)

    # Notif user uniquement quand on bascule en "done" depuis autre chose
    if body.status == "done" and previous_status != "done":
        user = db.get(User, order.username)
        if user and user.email:
            background_tasks.add_task(
                send_user_order_done,
                _order_dict(order, user.email),
                user.email,
            )

    # On renvoie l'order complet
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
