"""
services/escrow.py - Lock/release de CAMP entre un user et un compte systeme.

Module commun reutilise par les paris (et a terme : casino, lait, poker).
Tous les mouvements passent par admin_transfer (signe par la treasury),
et sont journalises dans la table transactions avec une convention claire :
  - lock   : from_username = user.username, to_username = '__<role>__'
  - release: from_username = '__<role>__',  to_username = user.username

Si la tx on-chain rate, on raise EscrowError sans toucher la DB.
La caller decide du rollback de session.
"""
import datetime
from sqlalchemy.orm import Session

from models import User, Transaction
from blockchain import admin_transfer, get_balance_camp


class EscrowError(Exception):
    """Erreur metier d'escrow (solde insuffisant, role inconnu, ...)."""


def get_system_account(db: Session, role: str) -> User:
    acc = (
        db.query(User)
          .filter(User.account_type == "system", User.system_role == role)
          .first()
    )
    if not acc:
        raise EscrowError(
            f"Compte systeme '{role}' introuvable. "
            "Lance scripts/seed_system_accounts.py."
        )
    return acc


def lock(db: Session, user: User, role: str, amount: int, note: str) -> str:
    """Bloque des fonds : user -> compte systeme. Retourne tx_hash."""
    if amount <= 0:
        raise EscrowError("Montant doit etre strictement positif")
    bal = get_balance_camp(user.address)
    if amount > bal:
        raise EscrowError(f"Solde insuffisant ({bal} CAMP, il en faut {amount})")
    sys_acc = get_system_account(db, role)
    tx_hash = admin_transfer(db, user.address, sys_acc.address, amount)
    db.add(Transaction(
        ts=datetime.datetime.utcnow(),
        from_username=user.username,
        to_username=f"__{role}__",
        amount=amount,
        note=note,
        tx_hash=tx_hash,
    ))
    return tx_hash


def release(db: Session, role: str, user: User, amount: int, note: str) -> str:
    """Libere des fonds : compte systeme -> user. Retourne tx_hash."""
    if amount <= 0:
        raise EscrowError("Montant doit etre strictement positif")
    sys_acc = get_system_account(db, role)
    bal = get_balance_camp(sys_acc.address)
    if amount > bal:
        raise EscrowError(
            f"Compte '{role}' insuffisant ({bal} CAMP, il en faut {amount}). "
            "Recharge depuis la treasury."
        )
    tx_hash = admin_transfer(db, sys_acc.address, user.address, amount)
    db.add(Transaction(
        ts=datetime.datetime.utcnow(),
        from_username=f"__{role}__",
        to_username=user.username,
        amount=amount,
        note=note,
        tx_hash=tx_hash,
    ))
    return tx_hash
