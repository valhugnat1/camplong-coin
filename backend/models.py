"""
models.py - Schemas SQL (users, transactions, nonces, market_orders,
bets + bet_options + bet_participations + bet_votes,
app_settings, rng_seeds, coinflip_rounds, roulette_spins, slots_spins).

Chaque table est explicitement associee au schema DB_SCHEMA via __table_args__.
"""
from sqlalchemy import (
    Column, String, Integer, BigInteger, DateTime, Text, Float, Boolean, func,
)
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
    Pari communautaire. Le createur pose une mise unique fixe + 2 a 6 options
    (yes/no ou choix multiples). N'importe qui peut rejoindre une option pour
    le montant defini. Resolution par arbitre, 2 votes communautaires
    concordants, ou admin. Pot total reparti entre les gagnants au prorata
    (egal puisque toutes les mises sont identiques).
    """
    __tablename__ = "bets"
    __table_args__ = {"schema": DB_SCHEMA}

    id = Column(Integer, primary_key=True, autoincrement=True)
    creator_username = Column(String(64), nullable=False, index=True)
    statement = Column(String(512), nullable=False)
    deadline = Column(DateTime, nullable=False)

    # 'yes_no' (2 options Oui/Non) | 'multi_choice' (2 a 6 options custom)
    type = Column(String(16), nullable=False, default="yes_no")
    # Mise unique pour tous les participants (le createur inclus s'il joue).
    stake = Column(BigInteger, nullable=False)

    arbiter_username = Column(String(64), nullable=True, index=True)

    # 'open' | 'resolved' | 'cancelled' | 'expired'
    status = Column(String(16), nullable=False, default="open", index=True)
    # Option gagnante (FK bet_options.id). NULL si void (refund) ou pas encore resolu.
    resolution_option_id = Column(Integer, nullable=True)
    # True si resolu en "void" (refund de tous les participants).
    resolution_void = Column(Boolean, nullable=False, default=False)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String(64), nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class BetOption(Base):
    """
    Une option de pari (Oui/Non pour yes_no, A/B/C/... pour multi_choice).
    """
    __tablename__ = "bet_options"
    __table_args__ = {"schema": DB_SCHEMA}

    id = Column(Integer, primary_key=True, autoincrement=True)
    bet_id = Column(Integer, nullable=False, index=True)
    label = Column(String(64), nullable=False)
    position = Column(Integer, nullable=False, default=0)


class BetParticipation(Base):
    """
    Une mise d'un user sur une option d'un pari. UNIQUE (bet_id, username) :
    un user ne peut miser qu'une seule fois par pari (sur une seule option).
    Le montant est toujours egal a bet.stake (denormalise pour faciliter les
    refunds en cas de void).
    """
    __tablename__ = "bet_participations"
    __table_args__ = {"schema": DB_SCHEMA}

    id = Column(Integer, primary_key=True, autoincrement=True)
    bet_id = Column(Integer, nullable=False, index=True)
    option_id = Column(Integer, nullable=False, index=True)
    username = Column(String(64), nullable=False, index=True)
    amount = Column(BigInteger, nullable=False)
    tx_hash_lock = Column(String(66), nullable=True)
    tx_hash_payout = Column(String(66), nullable=True)
    joined_at = Column(DateTime, server_default=func.now(), nullable=False)


class BetVote(Base):
    """
    Un vote communautaire sur la resolution d'un pari. N'importe quel user
    (participant ou non) peut voter. UNIQUE (bet_id, voter_username) : un
    user n'a qu'un vote par pari (modifiable tant que le pari n'est pas
    resolu).

    option_id = NULL signifie un vote pour "void" (refund de tous).
    Quand 2 votes pointent vers la meme option_id (ou tous les deux vers NULL),
    le pari est resolu automatiquement.
    """
    __tablename__ = "bet_votes"
    __table_args__ = {"schema": DB_SCHEMA}

    id = Column(Integer, primary_key=True, autoincrement=True)
    bet_id = Column(Integer, nullable=False, index=True)
    voter_username = Column(String(64), nullable=False, index=True)
    option_id = Column(Integer, nullable=True)   # NULL = vote pour "void"
    voted_at = Column(DateTime, server_default=func.now(),
                      onupdate=func.now(), nullable=False)


class AppSetting(Base):
    """
    Parametres dynamiques modifiables depuis le backoffice (edge maison,
    limites de mise, etc.). Key/value en VARCHAR : on parse cote service
    selon le besoin (int, float, bool).
    """
    __tablename__ = "app_settings"
    __table_args__ = {"schema": DB_SCHEMA}

    key = Column(String(64), primary_key=True)
    value = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(),
                        onupdate=func.now(), nullable=False)


class RngSeed(Base):
    """
    Commit-reveal pour les tirages aleatoires (coinflip, roulette, ...).
    Le backend genere un secret + hash, publie le hash AVANT le tirage,
    puis revele le secret APRES. Le user peut verifier sha256(secret) == hash.
    """
    __tablename__ = "rng_seeds"
    __table_args__ = {"schema": DB_SCHEMA}

    id = Column(Integer, primary_key=True, autoincrement=True)
    purpose = Column(String(32), nullable=False)         # 'coinflip', 'roulette', ...
    ref_id = Column(Integer, nullable=True)              # id de la round associee
    seed_hash = Column(String(64), nullable=False)       # publie avant
    seed_secret = Column(String(64), nullable=False)     # revele apres
    revealed = Column(Boolean, nullable=False, default=False)
    client_seed = Column(String(128), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    revealed_at = Column(DateTime, nullable=True)


class RouletteSpin(Base):
    """
    Un spin de roulette europeenne (1 zero, 37 cases). Le user place
    plusieurs mises sur des "spots" (numero, rouge/noir, douzaine...),
    un seul tirage les resout toutes. On agrege en 1 lock + 1 payout
    net pour ne pas exploser le nombre de tx on-chain.

    L'edge est mecanique (2.7%) : payout numero plein = 35:1 mais proba
    1/37. Pas de parametre 'edge_pct' a configurer.
    """
    __tablename__ = "roulette_spins"
    __table_args__ = {"schema": DB_SCHEMA}

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), nullable=False, index=True)
    total_bet = Column(BigInteger, nullable=False)
    total_payout = Column(BigInteger, nullable=False, default=0)
    net_pnl = Column(BigInteger, nullable=False, default=0)

    bets_json = Column(Text, nullable=False)        # JSON [{spot, amount}, ...]
    outcome_number = Column(Integer, nullable=True)  # 0..36
    outcome_color = Column(String(8), nullable=True)  # 'red' | 'black' | 'green'

    client_seed = Column(String(128), nullable=False)
    rng_seed_id = Column(Integer, nullable=False)

    status = Column(String(16), nullable=False, default="settled")
    ts = Column(DateTime, server_default=func.now(), nullable=False)
    tx_hash_lock = Column(String(66), nullable=True)
    tx_hash_payout = Column(String(66), nullable=True)


class CoinflipRound(Base):
    """
    Une partie de pile/face. Settle dans la meme requete HTTP que le
    play (commit + reveal en une seule fois pour simplifier l'UX).
    """
    __tablename__ = "coinflip_rounds"
    __table_args__ = {"schema": DB_SCHEMA}

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), nullable=False, index=True)
    bet_amount = Column(BigInteger, nullable=False)
    choice = Column(String(8), nullable=False)           # 'heads' | 'tails'
    outcome = Column(String(8), nullable=True)
    win = Column(Boolean, nullable=True)
    payout = Column(BigInteger, nullable=False, default=0)

    client_seed = Column(String(128), nullable=False)
    rng_seed_id = Column(Integer, nullable=False)

    # Edge applique sur cette round (snapshot au moment du tirage, en %),
    # stocke comme float dans la note de transaction et utilise pour
    # l'audit. La colonne n'existe pas dans la table v4 : on garde l'edge
    # uniquement en memoire du compute. (Pas besoin de l'archiver, c'est
    # deductible : payout / (2 * bet_amount) = 1 - edge/100.)

    status = Column(String(16), nullable=False, default="committed")
    ts = Column(DateTime, server_default=func.now(), nullable=False)
    settled_at = Column(DateTime, nullable=True)
    tx_hash_lock = Column(String(66), nullable=True)
    tx_hash_payout = Column(String(66), nullable=True)


class MilkPool(Base):
    """
    Pool AMM (Uniswap v1) pour un produit laitier.
    reserve_camp * reserve_milk = k (conserve sauf chaos qui touche reserve_milk).
    reserve_milk est en milli-bouteilles (1 bouteille = 1000) pour la granularite.
    system_role pointe sur users.system_role (compte custodial du pool).
    """
    __tablename__ = "milk_pools"
    __table_args__ = {"schema": DB_SCHEMA}

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(32), nullable=False, unique=True)
    name = Column(String(64), nullable=False)
    system_role = Column(String(64), nullable=False)
    reserve_camp = Column(BigInteger, nullable=False)
    reserve_milk = Column(BigInteger, nullable=False)
    fee_pct = Column(Float, nullable=False, default=0.5)
    status = Column(String(16), nullable=False, default="active")  # 'active'|'paused'
    initial_camp = Column(BigInteger, nullable=False)
    initial_milk = Column(BigInteger, nullable=False)
    chaos_enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class MilkPosition(Base):
    """Stock de lait detenu par un user sur un pool."""
    __tablename__ = "milk_positions"
    __table_args__ = {"schema": DB_SCHEMA}

    username = Column(String(64), primary_key=True)
    pool_id = Column(Integer, primary_key=True)
    balance_milk = Column(BigInteger, nullable=False, default=0)
    avg_cost = Column(Float, nullable=False, default=0)
    updated_at = Column(DateTime, server_default=func.now(),
                        onupdate=func.now(), nullable=False)


class MilkTrade(Base):
    """Un swap (buy ou sell) execute sur un pool."""
    __tablename__ = "milk_trades"
    __table_args__ = {"schema": DB_SCHEMA}

    id = Column(Integer, primary_key=True, autoincrement=True)
    pool_id = Column(Integer, nullable=False, index=True)
    username = Column(String(64), nullable=False, index=True)
    side = Column(String(4), nullable=False)  # 'buy' | 'sell'
    amount_camp_in = Column(BigInteger, nullable=False, default=0)
    amount_milk_in = Column(BigInteger, nullable=False, default=0)
    amount_camp_out = Column(BigInteger, nullable=False, default=0)
    amount_milk_out = Column(BigInteger, nullable=False, default=0)
    fee = Column(BigInteger, nullable=False, default=0)
    price_before = Column(Float, nullable=False)
    price_after = Column(Float, nullable=False)
    ts = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    tx_hash = Column(String(66), nullable=True)


class MilkChaosTemplate(Base):
    """
    Modele d'evenement chaos editable depuis le backoffice. Le bot dieu
    tire au sort un template (ponderation `weight`, `enabled=True`) puis
    genere un delta dans [delta_min, delta_max] et formate la narrative.

    delta_type :
      - 'pct'     : delta en pourcent de reserve_milk courante (float)
      - 'bottles' : delta en bouteilles absolues (multiplie x1000 pour milli)

    Convention de signe : si delta_min/max negatifs -> evenement baissier
    pour la reserve (donc prix qui MONTE). Inversement.

    Placeholders dans `narrative` :
      {pct}     -> delta_pct signe (ex: '-5.3')
      {abs_pct} -> abs(delta_pct) (ex: '5.3')
      {n}       -> delta_bottles signe (ex: '-120')
      {abs_n}   -> abs(delta_bottles) (ex: '120')
    """
    __tablename__ = "milk_chaos_templates"
    __table_args__ = {"schema": DB_SCHEMA}

    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String(64), nullable=False, unique=True)
    kind = Column(String(32), nullable=False)  # 'famine'|'spoil'|'overstock'|'import'
    delta_type = Column(String(16), nullable=False)  # 'pct'|'bottles'
    delta_min = Column(Float, nullable=False)
    delta_max = Column(Float, nullable=False)
    narrative = Column(String(512), nullable=False)
    weight = Column(Integer, nullable=False, default=1)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(),
                        onupdate=func.now(), nullable=False)


class MilkChaosEvent(Base):
    """
    Evenement chaos (bot ou admin) qui modifie reserve_milk d'un pool.
    Ne touche jamais reserve_camp (preservation de la masse CAMP du systeme).
    """
    __tablename__ = "milk_chaos_events"
    __table_args__ = {"schema": DB_SCHEMA}

    id = Column(Integer, primary_key=True, autoincrement=True)
    pool_id = Column(Integer, nullable=False, index=True)
    kind = Column(String(32), nullable=False)  # 'famine'|'spoil'|'overstock'|'import'
    delta_milk = Column(BigInteger, nullable=False)
    reserve_milk_before = Column(BigInteger, nullable=False)
    reserve_milk_after = Column(BigInteger, nullable=False)
    price_before = Column(Float, nullable=False)
    price_after = Column(Float, nullable=False)
    narrative = Column(String(256), nullable=True)
    triggered_by = Column(String(16), nullable=False)  # 'bot'|'admin'
    ts = Column(DateTime, server_default=func.now(), nullable=False, index=True)


class PokerTable(Base):
    """
    Table de poker Texas Hold'em No-Limit. Plusieurs tables en parallele.
    Status 'open' : accepte les sit-in. 'closed' : on finit les mains
    en cours mais on n'accepte plus personne.
    """
    __tablename__ = "poker_tables"
    __table_args__ = {"schema": DB_SCHEMA}

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=False)
    blind_small = Column(Integer, nullable=False)
    blind_big = Column(Integer, nullable=False)
    min_buyin = Column(Integer, nullable=False)
    max_buyin = Column(Integer, nullable=False)
    max_players = Column(Integer, nullable=False, default=6)
    status = Column(String(16), nullable=False, default="open")
    # NULL = table cree par l'admin. Sinon = pseudo du joueur createur,
    # qui peut la supprimer lui-meme.
    creator_username = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class PokerSession(Base):
    """
    Un siege occupe par un joueur. left_at IS NULL => actif.
    `stack` est le stack off-chain devant le joueur. Les CAMP correspondants
    sont sur le wallet 'poker_bank' (system_role) — escrow lock au sit-in,
    release au sit-out.
    """
    __tablename__ = "poker_sessions"
    __table_args__ = {"schema": DB_SCHEMA}

    id = Column(Integer, primary_key=True, autoincrement=True)
    table_id = Column(Integer, nullable=False, index=True)
    username = Column(String(64), nullable=False, index=True)
    seat = Column(Integer, nullable=False)
    stack = Column(BigInteger, nullable=False)
    initial_stack = Column(BigInteger, nullable=False)
    joined_at = Column(DateTime, server_default=func.now(), nullable=False)
    left_at = Column(DateTime, nullable=True)
    tx_hash_buyin = Column(String(66), nullable=True)
    tx_hash_cashout = Column(String(66), nullable=True)


class PokerHand(Base):
    """
    Une main jouee a une table. `hand_log` contient un blob JSON avec
    l'etat complet de la main (deck restant, joueurs, street, pot, etc.)
    et la sequence d'actions. ended_at IS NULL => main en cours.
    """
    __tablename__ = "poker_hands"
    __table_args__ = {"schema": DB_SCHEMA}

    id = Column(Integer, primary_key=True, autoincrement=True)
    table_id = Column(Integer, nullable=False, index=True)
    hand_number = Column(Integer, nullable=False)
    dealer_seat = Column(Integer, nullable=False)
    board_cards = Column(String(20), nullable=True)
    pot = Column(BigInteger, nullable=False, default=0)
    winners_json = Column(Text, nullable=True)
    hand_log = Column(Text, nullable=False, default="{}")
    rng_seed_id = Column(Integer, nullable=False)
    started_at = Column(DateTime, server_default=func.now(), nullable=False)
    ended_at = Column(DateTime, nullable=True)


class PokerHandHole(Base):
    """Cartes privees par joueur pour une main donnee."""
    __tablename__ = "poker_hand_holes"
    __table_args__ = {"schema": DB_SCHEMA}

    hand_id = Column(Integer, primary_key=True)
    username = Column(String(64), primary_key=True)
    hole_cards = Column(String(8), nullable=False)


class SlotsSpin(Base):
    """
    Un spin de machine a sous (3 rouleaux, single payline, paye sur
    3-of-a-kind seulement).
    Provably fair : un commit-reveal RNG par spin, 3 picks ponderes
    sur le meme combined_hash avec des offsets differents.
    """
    __tablename__ = "slots_spins"
    __table_args__ = {"schema": DB_SCHEMA}

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), nullable=False, index=True)
    bet_amount = Column(BigInteger, nullable=False)
    payout = Column(BigInteger, nullable=False, default=0)
    win = Column(Boolean, nullable=False, default=False)

    # Symboles sortis, separes par '|' (ex '🍒|🍋|🍒').
    reels = Column(String(32), nullable=False)
    # Code combo (ex '3xcherry' ou 'no_match').
    combo = Column(String(32), nullable=False)
    # Multiplicateur applique (0 si perdu, 6/14/25/... sinon).
    multiplier = Column(Integer, nullable=False, default=0)

    client_seed = Column(String(128), nullable=False)
    rng_seed_id = Column(Integer, nullable=False)

    status = Column(String(16), nullable=False, default="settled")
    ts = Column(DateTime, server_default=func.now(), nullable=False)
    tx_hash_lock = Column(String(66), nullable=True)
    tx_hash_payout = Column(String(66), nullable=True)


class AnalyticsTxLabel(Base):
    """
    Reclassification manuelle d'un mouvement de tresorerie, pour le dashboard
    analytics uniquement.

    Table PUREMENT ADDITIVE : elle ne modifie jamais `transactions`, qui reste
    le journal immuable des mouvements on-chain. On se contente de dire
    COMMENT compter une ligne existante. Supprimer cette table ne fait perdre
    que les ajustements, jamais des donnees financieres.

    Cas d'usage : un credit admin qui etait en realite la mise de depart d'un
    joueur (oubliee a l'onboarding) doit compter comme capital initial et non
    comme recharge, sinon il apparait comme quelqu'un qui a recharge.

    label :
      - 'onboarding' : capital de depart (compte hors periode, c'est la base)
      - 'topup'      : vraie recharge
      - 'withdrawal' : vrai retrait
      - 'ignore'     : exclu de tout calcul (erreur, test, correction interne)
    """
    __tablename__ = "analytics_tx_labels"
    __table_args__ = {"schema": DB_SCHEMA}

    tx_id = Column(Integer, primary_key=True)      # -> transactions.id
    label = Column(String(16), nullable=False)
    note = Column(String(256), default="")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(),
                        onupdate=func.now(), nullable=False)
