"""
main.py - Backend CamplongCoin (v2 : Postgres + schema test/prod + nonces en DB)

Endpoints :
  POST /login       -> {token, address, username}
  GET  /me          -> {username, address, balance}
  GET  /users       -> autres users (pour le dropdown destinataire)
  POST /transfer    -> {tx_hash, new_balance}
  GET  /history     -> historique des transferts (depuis la DB)

Lancement :  uvicorn main:app --reload
"""
import os
import json
import datetime

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_
from web3 import Web3
from eth_account import Account
from cryptography.fernet import Fernet
from jose import jwt, JWTError
import bcrypt
from dotenv import load_dotenv

from database import get_db, DB_SCHEMA
from models import User, Transaction, Nonce


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
load_dotenv()

MASTER_KEY = os.environ["MASTER_KEY"].encode()
RPC_URL = os.environ["RPC_URL"]
CONTRACT_ADDRESS = Web3.to_checksum_address(os.environ["CONTRACT_ADDRESS"])
JWT_SECRET = os.environ["JWT_SECRET"]
CHAIN_ID = 84532  # Base Sepolia

fernet = Fernet(MASTER_KEY)
w3 = Web3(Web3.HTTPProvider(RPC_URL))

ERC20_ABI = json.loads("""[
  {"constant":true,"inputs":[{"name":"_owner","type":"address"}],
   "name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"},
  {"constant":false,"inputs":[{"name":"_to","type":"address"},{"name":"_value","type":"uint256"}],
   "name":"transfer","outputs":[{"name":"","type":"bool"}],"type":"function"}
]""")

contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=ERC20_ABI)


# ---------------------------------------------------------------------------
# App + CORS
# ---------------------------------------------------------------------------
app = FastAPI(title="CamplongCoin API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2 = OAuth2PasswordBearer(tokenUrl="login")


# ---------------------------------------------------------------------------
# Modeles Pydantic
# ---------------------------------------------------------------------------
class LoginIn(BaseModel):
    username: str
    password: str


class TransferIn(BaseModel):
    to_username: str
    amount: int       # en CAMP entiers (pas en wei)
    note: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def current_user(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> User:
    """Decode le JWT, retourne le User depuis la DB."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        username = payload["sub"]
    except (JWTError, KeyError):
        raise HTTPException(401, "Token invalide")
    u = db.get(User, username)
    if not u:
        raise HTTPException(401, "User inconnu")
    return u


def get_balance_camp(address: str) -> int:
    """Lit le solde on-chain et le convertit en CAMP entiers."""
    bal_wei = contract.functions.balanceOf(address).call()
    return bal_wei // 10**18


def reserve_next_nonce(db: Session, address: str) -> int:
    """
    Retourne le prochain nonce a utiliser pour cette adresse et l'incremente.
    Utilise SELECT ... FOR UPDATE pour serialiser les acces concurrents.

    Si la ligne nonce n'existe pas encore en DB, on initialise depuis la
    blockchain (eth_getTransactionCount en 'pending' inclut les tx en mempool).
    """
    row = (
        db.query(Nonce)
          .filter_by(address=address)
          .with_for_update()
          .first()
    )

    chain_nonce = w3.eth.get_transaction_count(address, "pending")

    if row is None:
        nonce_to_use = chain_nonce
        row = Nonce(address=address, next_nonce=nonce_to_use + 1)
        db.add(row)
        db.flush()
    else:
        # max(DB, chain) pour resync si une tx est passee hors backend
        nonce_to_use = max(row.next_nonce, chain_nonce)
        row.next_nonce = nonce_to_use + 1

    db.commit()
    return nonce_to_use


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/")
def root():
    return {
        "status": "ok",
        "chain": "Base Sepolia",
        "contract": CONTRACT_ADDRESS,
        "schema": DB_SCHEMA,
    }


@app.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.get(User, body.username)
    if not u or not bcrypt.checkpw(body.password.encode(), u.password_hash.encode()):
        raise HTTPException(401, "Identifiants invalides")
    exp = datetime.datetime.utcnow() + datetime.timedelta(days=7)
    token = jwt.encode(
        {"sub": u.username, "exp": exp},
        JWT_SECRET, algorithm="HS256",
    )
    return {
        "token": token,
        "address": u.address,
        "username": u.username,
    }


@app.get("/me")
def me(user: User = Depends(current_user)):
    return {
        "username": user.username,
        "address": user.address,
        "balance": get_balance_camp(user.address),
    }


@app.get("/users")
def list_users(user: User = Depends(current_user), db: Session = Depends(get_db)):
    others = db.query(User).filter(User.username != user.username).all()
    return [{"username": u.username} for u in others]


@app.post("/transfer")
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

    # 2. Dechiffrer la cle privee
    pk = fernet.decrypt(user.encrypted_private_key.encode()).decode()
    acct = Account.from_key(pk)
    to_addr = Web3.to_checksum_address(dest.address)
    amount_wei = body.amount * 10**18

    # 3. Reserver un nonce en DB (avec verrou)
    nonce = reserve_next_nonce(db, user.address)

    # 4. Construire, signer, envoyer
    tx = contract.functions.transfer(to_addr, amount_wei).build_transaction({
        "from": acct.address,
        "nonce": nonce,
        "chainId": CHAIN_ID,
        "gas": 100_000,
        "maxFeePerGas": w3.to_wei(0.1, "gwei"),
        "maxPriorityFeePerGas": w3.to_wei(0.01, "gwei"),
    })
    signed = acct.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction).hex()

    # 5. Attendre la confirmation
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
    if receipt.status != 1:
        raise HTTPException(500, "La tx a echoue on-chain")

    # 6. Enregistrer la tx en DB
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


@app.get("/history")
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