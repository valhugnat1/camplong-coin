import datetime
import bcrypt
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import or_
from jose import jwt

from database import get_db, DB_SCHEMA
from models import User, Transaction
from schemas import LoginIn, TransferIn
from security import current_user
from blockchain import admin_transfer, get_balance_camp, treasury, reserve_next_nonce
from config import JWT_SECRET

router = APIRouter(tags=["users"])

@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.get(User, body.username)
    if not u or not bcrypt.checkpw(body.password.encode(), u.password_hash.encode()):
        raise HTTPException(401, "Identifiants invalides")
    exp = datetime.datetime.utcnow() + datetime.timedelta(days=7)
    token = jwt.encode({"sub": u.username, "exp": exp}, JWT_SECRET, algorithm="HS256")
    return {"token": token, "address": u.address, "username": u.username}

@router.get("/me")
def me(user: User = Depends(current_user)):
    return {
        "username": user.username,
        "address": user.address,
        "balance": get_balance_camp(user.address),
    }


@router.get("/users")
def list_users(user: User = Depends(current_user), db: Session = Depends(get_db)):
    others = db.query(User).filter(User.username != user.username).all()
    return [{"username": u.username} for u in others]


@router.post("/transfer")
def transfer(
    body: TransferIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    # 1. Validation
    dest = db.get(User, body.to_username)
    if not dest:
        raise HTTPException(404, "Destinataire inconnu")
    if body.amount <= 0:
        raise HTTPException(400, "Montant doit etre positif")

    current_balance = get_balance_camp(user.address)
    if body.amount > current_balance:
        raise HTTPException(400, f"Solde insuffisant ({current_balance} CAMP)")

    # 2 & 3. Appel à la blockchain via notre fonction helper !
    # Plus besoin de w3, contract, gas, reserve_next_nonce ici.
    tx_hash = admin_transfer(db, user.address, dest.address, body.amount)

    # 4. Log DB
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

@router.get("/history")
def history(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Historique des tx ou le user est expediteur ou destinataire."""
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