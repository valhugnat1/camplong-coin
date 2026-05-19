import datetime
import bcrypt
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from eth_account import Account
from jose import jwt

from database import get_db
from models import User, Transaction
from schemas import AdminLoginIn, CreateUserIn, AmountIn
from security import require_admin, fernet
from blockchain import admin_transfer, get_balance_camp, get_balance_eth, treasury
from config import ADMIN_PASSWORD, JWT_SECRET

router = APIRouter(prefix="/admin", tags=["admin"])

@router.post("/login")
def admin_login(body: AdminLoginIn):
    if body.password != ADMIN_PASSWORD:
        raise HTTPException(401, "Mot de passe incorrect")
    exp = datetime.datetime.utcnow() + datetime.timedelta(days=1)
    token = jwt.encode({"sub": "admin", "role": "admin", "exp": exp}, JWT_SECRET, algorithm="HS256")
    return {"token": token}

@router.get("/treasury")
def get_treasury(_: bool = Depends(require_admin)):
    return {
        "address": treasury.address,
        "balance_eth": get_balance_eth(treasury.address),
        "balance_camp": get_balance_camp(treasury.address),
    }

@router.get("/users")
def list_all_users(_: bool = Depends(require_admin), db: Session = Depends(get_db)):
    """Liste tous les users avec leur solde CAMP on-chain."""
    rows = db.query(User).order_by(User.created_at).all()
    return [
        {
            "username": u.username,
            "address": u.address,
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
    """
    Cree un nouveau user :
      1. Genere wallet + chiffre la cle privee (gardee pour un eventuel
         export self-custody plus tard, sinon jamais utilisee)
      2. Hash le password
      3. Insere en DB
      4. Si initial_camp > 0 : adminTransfer treasury -> user
    Plus de funding ETH, le user n'en a pas besoin.
    """
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
        "camp_tx": camp_tx,
        "initial_camp": body.initial_camp,
    }


@router.post("/credit")
def credit_user(
    body: AmountIn,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Envoie {amount} CAMP depuis treasury vers le user."""
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
        "newbalance_camp": get_balance_camp(user.address),
    }


@router.post("/debit")
def debit_user(
    body: AmountIn,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Retire {amount} CAMP du user vers la treasury.
    Plus besoin de dechiffrer la cle privee du user : la treasury (= owner
    du contrat) peut deplacer n'importe quel solde via adminTransfer.
    """
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
        "newbalance_camp": get_balance_camp(user.address),
    }