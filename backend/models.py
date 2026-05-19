"""
models.py - Schemas SQL (4 tables : users, transactions, nonces, market_orders).

Chaque table est explicitement associee au schema DB_SCHEMA via __table_args__.
"""
from sqlalchemy import Column, String, Integer, BigInteger, DateTime, Text, Float, func
from database import Base, DB_SCHEMA


class User(Base):
    """Compte user. username = pseudo (ex: 'Hugo'). email = facultatif."""
    __tablename__ = "users"
    __table_args__ = {"schema": DB_SCHEMA}

    username = Column(String(64), primary_key=True)
    password_hash = Column(String(128), nullable=False)
    address = Column(String(42), nullable=False, unique=True)   # 0x + 40 hex
    encrypted_private_key = Column(Text, nullable=False)
    email = Column(String(256), nullable=True)                  # pour les notifs
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class Transaction(Base):
    """Log des transferts CAMP."""
    __tablename__ = "transactions"
    __table_args__ = {"schema": DB_SCHEMA}

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime, server_default=func.now(), nullable=False)
    from_username = Column(String(64), nullable=False, index=True)
    to_username = Column(String(64), nullable=False, index=True)
    amount = Column(BigInteger, nullable=False)
    note = Column(String(256), default="")
    tx_hash = Column(String(66), nullable=False, unique=True)


class Nonce(Base):
    """Compteur de tx par adresse, verrouille en SELECT FOR UPDATE."""
    __tablename__ = "nonces"
    __table_args__ = {"schema": DB_SCHEMA}

    address = Column(String(42), primary_key=True)
    next_nonce = Column(Integer, nullable=False)
    updated_at = Column(DateTime, server_default=func.now(),
                        onupdate=func.now(), nullable=False)


class MarketOrder(Base):
    """
    Demande d'achat ou de vente de CAMP.
    L'admin la traite manuellement (paiement Wero/Revolut) puis marque "done"
    via le backoffice, ce qui declenche un email de confirmation au user.
    """
    __tablename__ = "market_orders"
    __table_args__ = {"schema": DB_SCHEMA}

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    username = Column(String(64), nullable=False, index=True)
    type = Column(String(8), nullable=False)             # 'buy' ou 'sell'
    amount_camp = Column(BigInteger, nullable=False)
    amount_eur = Column(Float, nullable=False)
    handle = Column(String(128), default="")             # Wero/Revolut handle (sell)
    note = Column(String(512), default="")               # note du user
    status = Column(String(16), default="pending", index=True)  # pending|done|cancelled
    admin_note = Column(String(512), default="")        # note admin
    done_at = Column(DateTime, nullable=True)
