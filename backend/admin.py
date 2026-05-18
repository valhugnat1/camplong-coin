"""
admin.py - Backoffice CamplongCoin

Endpoints (tous prefixes /admin) :
  POST /admin/login           -> {token}
  GET  /admin/users           -> liste de tous les users avec leurs soldes
  POST /admin/users           -> cree un nouveau user (genere wallet, fund ETH+CAMP)
  POST /admin/credit          -> envoie CAMP depuis treasury vers un user
  POST /admin/debit           -> retire CAMP d'un user vers treasury
  GET  /admin/treasury        -> infos treasury (adresse, solde ETH, solde CAMP)

Auth : un seul admin, mot de passe dans ADMIN_PASSWORD (.env).
"""
import os
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
# Config (importee depuis main.py via les memes env vars)
# ---------------------------------------------------------------------------
JWT_SECRET = os.environ["JWT_SECRET"]
MASTER_KEY = os.environ["MASTER_KEY"].encode()
RPC_URL = os.environ["RPC_URL"]
CONTRACT_ADDRESS = Web3.to_checksum_address(os.environ["CONTRACT_ADDRESS"])

# Specifique au backoffice
TREASURY_PRIVATE_KEY = os.environ["TREASURY_PRIVATE_KEY"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
CHAIN_ID = 84532

# ETH a envoyer aux nouveaux users pour qu'ils puissent payer leur gas
DEFAULT_ETH_FUND = 0.005   # ~5000 tx de transfer chacune sur Base Sepolia

w3 = Web3(Web3.HTTPProvider(RPC_URL))
fernet = Fernet(MASTER_KEY)
treasury = Account.from_key(TREASURY_PRIVATE_KEY)

import json as _json
ERC20_ABI = _json.loads("""[
  {"constant":true,"inputs":[{"name":"_owner","type":"address"}],
   "name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"},
  {"constant":false,"inputs":[{"name":"_to","type":"address"},{"name":"_value","type":"uint256"}],
   "name":"transfer","outputs":[{"name":"","type":"bool"}],"type":"function"},
  {"constant":false,"inputs":[{"name":"_from","type":"address"},{"name":"_to","type":"address"},{"name":"_value","type":"uint256"}],
   "name":"transferFrom","outputs":[{"name":"","type":"bool"}],"type":"function"}
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
    initial_camp: int = Field(0, ge=0)   # CAMP a envoyer immediatement (0 = aucun)


class AmountIn(BaseModel):
    username: str
    amount: int = Field(..., gt=0)   # CAMP entiers
    note: str = ""


# ---------------------------------------------------------------------------
# Auth admin
# ---------------------------------------------------------------------------
def require_admin(authorization: Optional[str] = Header(None)):
    """Verifie qu'on a un JWT admin valide en header."""
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
# Helpers blockchain (treasury sign)
# ---------------------------------------------------------------------------
def _next_treasury_nonce(db: Session) -> int:
    """
    Pareil que pour les users : reserve_next_nonce avec verrou DB.
    On reutilise la table 'nonces' pour la treasury aussi.
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


def _send_eth_from_treasury(db: Session, to_addr: str, amount_eth: float) -> str:
    """Envoie de l'ETH (gas) depuis la treasury. Retourne tx_hash."""
    nonce = _next_treasury_nonce(db)
    tx = {
        "from": treasury.address,
        "to": Web3.to_checksum_address(to_addr),
        "value": w3.to_wei(amount_eth, "ether"),
        "nonce": nonce,
        "chainId": CHAIN_ID,
        "gas": 21000,
        "maxFeePerGas": w3.to_wei(0.1, "gwei"),
        "maxPriorityFeePerGas": w3.to_wei(0.01, "gwei"),
    }
    signed = treasury.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction).hex()
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
    if receipt.status != 1:
        raise HTTPException(500, "Tx ETH (treasury->user) a echoue on-chain")
    return tx_hash


def _send_camp_from_treasury(db: Session, to_addr: str, amount_camp: int) -> str:
    """Envoie des CAMP depuis la treasury. Retourne tx_hash."""
    nonce = _next_treasury_nonce(db)
    tx = contract.functions.transfer(
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
        raise HTTPException(500, "Tx CAMP (treasury->user) a echoue on-chain")
    return tx_hash


def _send_camp_from_user_to_treasury(db: Session, user: User, amount_camp: int) -> str:
    """
    Retire des CAMP du user vers la treasury (signe par le user).
    On dechiffre la cle privee du user et on signe une tx transfer().
    """
    pk = fernet.decrypt(user.encrypted_private_key.encode()).decode()
    user_acct = Account.from_key(pk)

    # Verifier que le user a assez d'ETH pour payer le gas
    # (sinon on lui en envoie un petit peu d'abord)
    eth_balance = w3.eth.get_balance(user.address)
    min_gas = w3.to_wei(0.0005, "ether")
    if eth_balance < min_gas:
        _send_eth_from_treasury(db, user.address, 0.005)

    # Reserver un nonce user
    row = (
        db.query(Nonce)
          .filter_by(address=user.address)
          .with_for_update()
          .first()
    )
    chain_nonce = w3.eth.get_transaction_count(user.address, "pending")
    if row is None:
        nonce = chain_nonce
        db.add(Nonce(address=user.address, next_nonce=nonce + 1))
        db.flush()
    else:
        nonce = max(row.next_nonce, chain_nonce)
        row.next_nonce = nonce + 1
    db.commit()

    tx = contract.functions.transfer(
        treasury.address,
        amount_camp * 10**18,
    ).build_transaction({
        "from": user_acct.address,
        "nonce": nonce,
        "chainId": CHAIN_ID,
        "gas": 100_000,
        "maxFeePerGas": w3.to_wei(0.1, "gwei"),
        "maxPriorityFeePerGas": w3.to_wei(0.01, "gwei"),
    })
    signed = user_acct.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction).hex()
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
    if receipt.status != 1:
        raise HTTPException(500, "Tx CAMP (user->treasury) a echoue on-chain")
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
    """Liste tous les users avec leurs soldes on-chain."""
    rows = db.query(User).order_by(User.created_at).all()
    return [
        {
            "username": u.username,
            "address": u.address,
            "created_at": u.created_at.isoformat() + "Z" if u.created_at else None,
            "balance_camp": _balance_camp(u.address),
            "balance_eth": _balance_eth(u.address),
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
      1. Genere wallet + chiffre la cle privee
      2. Hash le password
      3. Insere en DB
      4. Fund ETH (gas) depuis treasury
      5. Si initial_camp > 0 : envoie aussi des CAMP depuis treasury
    """
    if db.get(User, body.username):
        raise HTTPException(400, f"Username '{body.username}' deja pris")

    # 1. Wallet
    acct = Account.create()
    enc_pk = fernet.encrypt(acct.key.hex().encode()).decode()

    # 2. Password
    pwd_hash = bcrypt.hashpw(body.user_password.encode(), bcrypt.gensalt()).decode()

    # 3. DB
    new_user = User(
        username=body.username,
        password_hash=pwd_hash,
        address=acct.address,
        encrypted_private_key=enc_pk,
    )
    db.add(new_user)
    db.commit()

    # 4. Fund ETH (toujours, pour qu'il puisse payer son gas plus tard)
    eth_tx = _send_eth_from_treasury(db, acct.address, DEFAULT_ETH_FUND)

    # 5. Optionnel : envoyer des CAMP initiaux
    camp_tx = None
    if body.initial_camp > 0:
        camp_tx = _send_camp_from_treasury(db, acct.address, body.initial_camp)
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
        "eth_tx": eth_tx,
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

    tx_hash = _send_camp_from_treasury(db, user.address, body.amount)

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
    Custodial = on a la cle privee du user, donc on peut signer pour lui.
    """
    user = db.get(User, body.username)
    if not user:
        raise HTTPException(404, f"User '{body.username}' introuvable")

    user_bal = _balance_camp(user.address)
    if body.amount > user_bal:
        raise HTTPException(400, f"User n'a que {user_bal} CAMP")

    tx_hash = _send_camp_from_user_to_treasury(db, user, body.amount)

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