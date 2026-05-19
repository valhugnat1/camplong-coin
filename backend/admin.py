"""
admin.py - Backoffice CamplongCoin (v2 : treasury paie tout le gas)

Le contrat expose maintenant adminTransfer(from, to, amount), reserve a
l'owner du contrat (= treasury). Le backoffice signe TOUTES les transactions,
donc :
  - Les users n'ont jamais besoin d'ETH
  - Plus de funding ETH a la creation d'un user
  - Le debit n'a plus besoin de dechiffrer la cle privee du user

Endpoints (tous prefixes /admin) :
  POST /admin/login        -> {token}
  GET  /admin/treasury     -> infos treasury (adresse, solde ETH, solde CAMP)
  GET  /admin/users        -> liste de tous les users avec leur solde CAMP
  POST /admin/users        -> cree un user (wallet + CAMP initiaux optionnels)
  POST /admin/credit       -> envoie CAMP treasury -> user (adminTransfer)
  POST /admin/debit        -> retire CAMP user -> treasury (adminTransfer)
"""
import os
import json
import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from web3 import Web3
from eth_account import Account
from cryptography.fernet import Fernet
from jose import jwt, JWTError
import bcrypt

from database import get_db
from models import User, Transaction, Nonce


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
JWT_SECRET = os.environ["JWT_SECRET"]
MASTER_KEY = os.environ["MASTER_KEY"].encode()
RPC_URL = os.environ["RPC_URL"]
CONTRACT_ADDRESS = Web3.to_checksum_address(os.environ["CONTRACT_ADDRESS"])

TREASURY_PRIVATE_KEY = os.environ["TREASURY_PRIVATE_KEY"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
CHAIN_ID = 84532  # Base Sepolia

w3 = Web3(Web3.HTTPProvider(RPC_URL))
fernet = Fernet(MASTER_KEY)
treasury = Account.from_key(TREASURY_PRIVATE_KEY)

ERC20_ABI = json.loads("""[
  {"constant":true,"inputs":[{"name":"_owner","type":"address"}],
   "name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"},
  {"constant":false,"inputs":[{"name":"_to","type":"address"},{"name":"_value","type":"uint256"}],
   "name":"transfer","outputs":[{"name":"","type":"bool"}],"type":"function"},
  {"constant":false,"inputs":[
     {"name":"from","type":"address"},
     {"name":"to","type":"address"},
     {"name":"amount","type":"uint256"}],
   "name":"adminTransfer","outputs":[],"type":"function"}
]""")
contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=ERC20_ABI)


router = APIRouter(prefix="/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Modeles Pydantic
# ---------------------------------------------------------------------------
class AdminLoginIn(BaseModel):
    password: str


class CreateUserIn(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    user_password: str = Field(..., min_length=1)
    initial_camp: int = Field(0, ge=0)


class AmountIn(BaseModel):
    username: str
    amount: int = Field(..., gt=0)
    note: str = ""


# ---------------------------------------------------------------------------
# Auth admin
# ---------------------------------------------------------------------------
def require_admin(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Token manquant")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        if payload.get("role") != "admin":
            raise HTTPException(403, "Reserve admin")
    except (JWTError, KeyError):
        raise HTTPException(401, "Token invalide")
    return True


# ---------------------------------------------------------------------------
# Helpers blockchain
# ---------------------------------------------------------------------------
def _next_treasury_nonce(db: Session) -> int:
    """
    Reserve un nonce pour la treasury (verrou pessimiste sur la ligne DB).
    Comme la treasury signe TOUT, c'est le seul nonce qu'on gere desormais.
    """
    row = (
        db.query(Nonce)
          .filter_by(address=treasury.address)
          .with_for_update()
          .first()
    )
    chain_nonce = w3.eth.get_transaction_count(treasury.address, "pending")

    if row is None:
        nonce_to_use = chain_nonce
        db.add(Nonce(address=treasury.address, next_nonce=nonce_to_use + 1))
        db.flush()
    else:
        nonce_to_use = max(row.next_nonce, chain_nonce)
        row.next_nonce = nonce_to_use + 1

    db.commit()
    return nonce_to_use


def _admin_transfer(db: Session, from_addr: str, to_addr: str, amount_camp: int) -> str:
    """
    Treasury appelle adminTransfer(from, to, amount) sur le contrat.
    Sert pour :
      - credit (treasury -> user)
      - debit  (user -> treasury)
      - transfert user -> user (declenche depuis /transfer dans main.py)
    """
    nonce = _next_treasury_nonce(db)
    tx = contract.functions.adminTransfer(
        Web3.to_checksum_address(from_addr),
        Web3.to_checksum_address(to_addr),
        amount_camp * 10**18,
    ).build_transaction({
        "from": treasury.address,
        "nonce": nonce,
        "chainId": CHAIN_ID,
        "gas": 100_000,
        "maxFeePerGas": w3.to_wei(0.1, "gwei"),
        "maxPriorityFeePerGas": w3.to_wei(0.01, "gwei"),
    })
    signed = treasury.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction).hex()
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
    if receipt.status != 1:
        raise HTTPException(500, "adminTransfer a echoue on-chain")
    return tx_hash


def _balance_camp(addr: str) -> int:
    return contract.functions.balanceOf(addr).call() // 10**18


def _balance_eth(addr: str) -> float:
    return float(w3.from_wei(w3.eth.get_balance(addr), "ether"))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post("/login")
def admin_login(body: AdminLoginIn):
    if body.password != ADMIN_PASSWORD:
        raise HTTPException(401, "Mot de passe incorrect")
    exp = datetime.datetime.utcnow() + datetime.timedelta(days=1)
    token = jwt.encode(
        {"sub": "admin", "role": "admin", "exp": exp},
        JWT_SECRET, algorithm="HS256",
    )
    return {"token": token}


@router.get("/treasury")
def get_treasury(_: bool = Depends(require_admin)):
    return {
        "address": treasury.address,
        "balance_eth": _balance_eth(treasury.address),
        "balance_camp": _balance_camp(treasury.address),
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
            "balance_camp": _balance_camp(u.address),
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
        treasury_bal = _balance_camp(treasury.address)
        if body.initial_camp > treasury_bal:
            raise HTTPException(400, f"Treasury insuffisante ({treasury_bal} CAMP)")
        camp_tx = _admin_transfer(db, treasury.address, acct.address, body.initial_camp)
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

    treasury_bal = _balance_camp(treasury.address)
    if body.amount > treasury_bal:
        raise HTTPException(400, f"Treasury insuffisante ({treasury_bal} CAMP)")

    tx_hash = _admin_transfer(db, treasury.address, user.address, body.amount)

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
        "new_balance_camp": _balance_camp(user.address),
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

    user_bal = _balance_camp(user.address)
    if body.amount > user_bal:
        raise HTTPException(400, f"User n'a que {user_bal} CAMP")

    tx_hash = _admin_transfer(db, user.address, treasury.address, body.amount)

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
        "new_balance_camp": _balance_camp(user.address),
    }