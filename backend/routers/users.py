import datetime
import bcrypt
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import or_
from jose import jwt

from database import get_db
from models import User, Transaction, MarketOrder
from schemas import (
    LoginIn, TransferIn,
    ChangePasswordIn, RevealKeyIn, UpdateEmailIn, CreateOrderIn,
)
from security import current_user, fernet
from blockchain import admin_transfer, get_balance_camp, treasury
from email_service import send_admin_new_order
from config import JWT_SECRET

router = APIRouter(tags=["users"])

# ─── Auth ──────────────────────────────────────────────

@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.get(User, body.username)
    if not u or not bcrypt.checkpw(body.password.encode(), u.password_hash.encode()):
        raise HTTPException(401, "Identifiants invalides")
    exp = datetime.datetime.utcnow() + datetime.timedelta(days=7)
    token = jwt.encode({"sub": u.username, "exp": exp}, JWT_SECRET, algorithm="HS256")
    return {"token": token, "address": u.address, "username": u.username}


# ─── Profil ────────────────────────────────────────────

@router.get("/me")
def me(user: User = Depends(current_user)):
    return {
        "username": user.username,
        "address": user.address,
        "email": user.email,
        "balance": get_balance_camp(user.address),
    }


@router.post("/me/password")
def change_password(
    body: ChangePasswordIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Change le mot de passe. Verifie l'ancien d'abord."""
    if not bcrypt.checkpw(body.current_password.encode(), user.password_hash.encode()):
        raise HTTPException(401, "Mot de passe actuel incorrect")
    user.password_hash = bcrypt.hashpw(
        body.new_password.encode(), bcrypt.gensalt()
    ).decode()
    db.commit()
    return {"ok": True}


@router.post("/me/email")
def update_email(
    body: UpdateEmailIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Met a jour l'email du user (pour recevoir les confirmations de demande)."""
    user.email = body.email
    db.commit()
    return {"ok": True, "email": user.email}


@router.post("/me/reveal-key")
def reveal_key(
    body: RevealKeyIn,
    user: User = Depends(current_user),
):
    """
    Renvoie la cle privee dechiffree pour permettre au user d'importer son
    wallet dans MetaMask. Requiert le mot de passe en plus du JWT (double verif).
    """
    if not bcrypt.checkpw(body.password.encode(), user.password_hash.encode()):
        raise HTTPException(401, "Mot de passe incorrect")
    try:
        private_key = fernet.decrypt(user.encrypted_private_key.encode()).decode()
    except Exception:
        raise HTTPException(500, "Impossible de dechiffrer la cle (MASTER_KEY ?)")
    # Format 0x... attendu par MetaMask
    if not private_key.startswith("0x"):
        private_key = "0x" + private_key
    return {"private_key": private_key}


# ─── Annuaire ──────────────────────────────────────────

@router.get("/users")
def list_users(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Annuaire des autres users humains. Exclut les comptes systeme (escrow, banque, ...)."""
    others = (
        db.query(User)
          .filter(User.username != user.username)
          .filter(User.account_type == "user")
          .all()
    )
    return [{"username": u.username} for u in others]


@router.get("/leaderboard")
def leaderboard(_: User = Depends(current_user), db: Session = Depends(get_db)):
    """Classement des users par solde CAMP (desc). Inclut tous les users humains."""
    users = (
        db.query(User)
          .filter(User.account_type == "user")
          .all()
    )
    ranked = [
        {"username": u.username, "balance": get_balance_camp(u.address)}
        for u in users
    ]
    ranked.sort(key=lambda x: x["balance"], reverse=True)
    return [{"rank": i + 1, **r} for i, r in enumerate(ranked)]


# ─── Transferts entre users ────────────────────────────

@router.post("/transfer")
def transfer(
    body: TransferIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    dest = db.get(User, body.to_username)
    if not dest:
        raise HTTPException(404, "Destinataire inconnu")
    if body.amount <= 0:
        raise HTTPException(400, "Montant doit etre positif")

    current_balance = get_balance_camp(user.address)
    if body.amount > current_balance:
        raise HTTPException(400, f"Solde insuffisant ({current_balance} CAMP)")

    tx_hash = admin_transfer(db, user.address, dest.address, body.amount)

    db.add(Transaction(
        ts=datetime.datetime.utcnow(),
        from_username=user.username,
        to_username=body.to_username,
        amount=body.amount,
        note=body.note,
        tx_hash=tx_hash,
    ))
    db.commit()

    return {
        "tx_hash": tx_hash,
        "new_balance": get_balance_camp(user.address),
    }


@router.get("/balance-history")
def balance_history(
    window: str = "1d",
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """
    Reconstruit l'evolution du solde CAMP sur une fenetre temporelle.

    Strategie : on lit le solde actuel on-chain, puis on rejoue les transactions
    qui touchent l'user a l'envers. Le solde a t = solde_actuel - somme des deltas
    survenus apres t.
    """
    windows = {
        "15m": datetime.timedelta(minutes=15),
        "1h":  datetime.timedelta(hours=1),
        "6h":  datetime.timedelta(hours=6),
        "1d":  datetime.timedelta(days=1),
        "7d":  datetime.timedelta(days=7),
    }
    if window not in windows:
        raise HTTPException(400, "window doit etre 15m, 1h, 6h, 1d ou 7d")

    now = datetime.datetime.utcnow()
    duration = windows[window]
    start = now - duration
    current = get_balance_camp(user.address)

    txs = (
        db.query(Transaction)
          .filter(or_(
              Transaction.from_username == user.username,
              Transaction.to_username == user.username,
          ))
          .filter(Transaction.ts >= start)
          .order_by(Transaction.ts.asc())
          .all()
    )
    # delta signe : +amount si recu, -amount si envoye
    deltas = [
        (t.ts, t.amount if t.to_username == user.username else -t.amount)
        for t in txs
    ]

    n = 60
    points = []
    for i in range(n + 1):
        ti = start + (duration * i / n)
        # solde a ti = solde_actuel - somme des deltas posterieurs a ti
        delta_after = sum(d for (ts, d) in deltas if ts > ti)
        points.append({
            "ts": ti.isoformat() + "Z",
            "balance": current - delta_after,
        })

    return {"current": current, "points": points}


@router.get("/history")
def history(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(Transaction)
          .filter(or_(
              Transaction.from_username == user.username,
              Transaction.to_username == user.username,
          ))
          .order_by(Transaction.ts.desc())
          .limit(100)
          .all()
    )
    return [
        {
            "ts": r.ts.isoformat() + "Z",
            "from": r.from_username,
            "to": r.to_username,
            "amount": r.amount,
            "note": r.note,
            "tx_hash": r.tx_hash,
        }
        for r in rows
    ]


# ─── Market Orders (achat/vente CAMP avec Hugo) ────────

def _order_dict(o: MarketOrder) -> dict:
    return {
        "id": o.id,
        "ts": o.ts.isoformat() + "Z" if o.ts else None,
        "type": o.type,
        "amount_camp": o.amount_camp,
        "amount_eur": o.amount_eur,
        "handle": o.handle or "",
        "note": o.note or "",
        "status": o.status,
        "admin_note": o.admin_note or "",
        "done_at": o.done_at.isoformat() + "Z" if o.done_at else None,
    }


@router.post("/orders")
def create_order(
    body: CreateOrderIn,
    background_tasks: BackgroundTasks,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """
    Cree une demande d'achat ou de vente. Statut initial : pending.
    Envoie un email a l'admin en background.
    """
    if body.type == "sell":
        if not body.handle.strip():
            raise HTTPException(
                400, "Pour vendre, indique ton handle Wero ou Revolut"
            )
        balance = get_balance_camp(user.address)
        if body.amount_camp > balance:
            raise HTTPException(400, f"Solde insuffisant ({balance} CAMP)")

    order = MarketOrder(
        username=user.username,
        type=body.type,
        amount_camp=body.amount_camp,
        amount_eur=body.amount_eur,
        handle=body.handle.strip(),
        note=body.note,
        status="pending",
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    # Notif admin en background (n'echoue jamais la requete)
    background_tasks.add_task(
        send_admin_new_order,
        {
            "id": order.id,
            "ts": order.ts.isoformat() + "Z" if order.ts else "",
            "username": user.username,
            "type": order.type,
            "amount_camp": order.amount_camp,
            "amount_eur": order.amount_eur,
            "handle": order.handle,
            "note": order.note,
        },
        user.email,
    )

    return _order_dict(order)


@router.get("/me/orders")
def list_my_orders(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(MarketOrder)
          .filter(MarketOrder.username == user.username)
          .order_by(MarketOrder.ts.desc())
          .limit(100)
          .all()
    )
    return [_order_dict(r) for r in rows]
