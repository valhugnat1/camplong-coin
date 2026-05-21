"""
models.py - Schemas SQL (users, transactions, nonces, market_orders, bets).

Chaque table est explicitement associee au schema DB_SCHEMA via __table_args__.
"""
from sqlalchemy import Column, String, Integer, BigInteger, DateTime, Text, Float, func
from database import Base, DB_SCHEMA


class User(Base):
    """
    Compte user OU compte systeme (account_type='system', ex: bets_escrow).
    Les comptes systeme n'ont pas de password_hash ni d'email.
    """
    __tablename__ = "users"
    __table_args__ = {"schema": DB_SCHEMA}

    username = Column(String(64), primary_key=True)
    password_hash = Column(String(128), nullable=True)
    address = Column(String(42), nullable=False, unique=True)   # 0x + 40 hex
    encrypted_private_key = Column(Text, nullable=False)
    email = Column(String(256), nullable=True)                  # pour les notifs
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    account_type = Column(String(16), nullable=False, default="user")  # 'user' | 'system'
    system_role = Column(String(64), nullable=True)             # ex: 'bets_escrow'


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
    via le backoffice, ce qui declenche :
      - le transfert on-chain (treasury -> user pour buy, user -> treasury pour sell)
      - un email de confirmation au user
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
    tx_hash = Column(String(66), nullable=True)          # tx du mouvement on-chain (si done)


class Bet(Base):
    """
    Pari P2P avec arbitre optionnel. Creator pose la mise + la cote ;
    un autre user (opponent) prend le pari en face. Resolution par l'arbitre
    designe ou l'admin. Fonds escrowes dans le compte systeme 'bets_escrow'.
    """
    __tablename__ = "bets"
    __table_args__ = {"schema": DB_SCHEMA}

    id = Column(Integer, primary_key=True, autoincrement=True)
    creator_username = Column(String(64), nullable=False, index=True)
    statement = Column(String(512), nullable=False)
    category = Column(String(32), nullable=True)
    deadline = Column(DateTime, nullable=False)

    stake_creator = Column(BigInteger, nullable=False)
    stake_opponent = Column(BigInteger, nullable=False)
    odds_num = Column(Integer, nullable=False)
    odds_den = Column(Integer, nullable=False)
    creator_side = Column(String(8), nullable=False)            # 'yes' | 'no'

    opponent_username = Column(String(64), nullable=True, index=True)
    arbiter_username = Column(String(64), nullable=True, index=True)
    arbiter_fee_pct = Column(Integer, nullable=False, default=0)

    # 'open' | 'matched' | 'resolved' | 'cancelled' | 'expired'
    status = Column(String(16), nullable=False, default="open", index=True)
    resolution = Column(String(8), nullable=True)               # 'yes' | 'no' | 'void'
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String(64), nullable=True)

    # Resolution amiable : si les deux votes coincident, le pari se resout
    # sans arbitre ni admin. resolved_by = '__both_players__'.
    creator_vote = Column(String(8), nullable=True)             # 'yes' | 'no' | 'void'
    opponent_vote = Column(String(8), nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    matched_at = Column(DateTime, nullable=True)

    tx_hash_lock_creator = Column(String(66), nullable=True)
    tx_hash_lock_opponent = Column(String(66), nullable=True)
    tx_hash_payout_winner = Column(String(66), nullable=True)
    tx_hash_payout_arbiter = Column(String(66), nullable=True)
