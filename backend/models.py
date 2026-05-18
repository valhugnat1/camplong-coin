"""
models.py - Schemas SQL (3 tables : users, transactions, nonces).

Chaque table est explicitement associee au schema DB_SCHEMA via __table_args__.
Du coup les requetes ORM produisent du SQL comme :
    SELECT ... FROM test.users WHERE ...
au lieu de simplement :
    SELECT ... FROM users
(qui depend du search_path et peut taper le mauvais schema).
"""
from sqlalchemy import Column, String, Integer, BigInteger, DateTime, Text, func
from database import Base, DB_SCHEMA


class User(Base):
    """Remplace users.json. Le username est directement le pseudo (ex: 'Hugo')."""
    __tablename__ = "users"
    __table_args__ = {"schema": DB_SCHEMA}

    username = Column(String(64), primary_key=True)
    password_hash = Column(String(128), nullable=False)
    address = Column(String(42), nullable=False, unique=True)   # 0x + 40 hex
    encrypted_private_key = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class Transaction(Base):
    """Remplace transactions.log."""
    __tablename__ = "transactions"
    __table_args__ = {"schema": DB_SCHEMA}

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime, server_default=func.now(), nullable=False)
    from_username = Column(String(64), nullable=False, index=True)
    to_username = Column(String(64), nullable=False, index=True)
    amount = Column(BigInteger, nullable=False)         # en CAMP entiers (pas wei)
    note = Column(String(256), default="")
    tx_hash = Column(String(66), nullable=False, unique=True)   # 0x + 64 hex


class Nonce(Base):
    """
    Compteur de tx par adresse, mis a jour avec un verrou ligne (FOR UPDATE)
    pour eviter les collisions en cas de tx concurrentes.
    """
    __tablename__ = "nonces"
    __table_args__ = {"schema": DB_SCHEMA}

    address = Column(String(42), primary_key=True)
    next_nonce = Column(Integer, nullable=False)
    updated_at = Column(DateTime, server_default=func.now(),
                        onupdate=func.now(), nullable=False)