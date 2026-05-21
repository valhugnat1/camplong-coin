"""
services/coinflip.py - Logique metier du jeu pile/face.

Reutilise les primitives existantes :
  - services.escrow.lock/release vers le compte systeme 'casino_bank'
  - services.randomness.commit/reveal pour le tirage provably fair
  - services.settings pour lire l'edge maison a chaud (modifie par l'admin)

Le router HTTP (routers/casino.py) appelle play() et serialise le resultat.
"""
import datetime
from dataclasses import dataclass, asdict
from typing import Optional

from sqlalchemy.orm import Session

from models import User, CoinflipRound, RngSeed
from services import escrow, randomness, settings
from blockchain import get_balance_camp


CASINO_BANK_ROLE = "casino_bank"


class CoinflipError(Exception):
    """Erreur metier (mise hors limites, solde insuffisant, ...)."""


@dataclass
class PlayResult:
    id: int
    bet_amount: int
    choice: str
    outcome: str
    win: bool
    payout: int
    edge_pct: float
    seed_hash: str
    server_seed: str
    client_seed: str
    combined_hash: str
    tx_hash_lock: str
    tx_hash_payout: Optional[str]
    new_balance: int
    ts: str

    def to_dict(self) -> dict:
        return asdict(self)


def play(db: Session, user: User, bet: int, choice: str, client_seed: str) -> PlayResult:
    """
    Joue une partie de pile/face. Lock la mise, tire au sort, paie en cas
    de victoire. Tout en une seule requete HTTP.

    En cas d'erreur metier (mise hors limites, solde, ...) : raise CoinflipError.
    En cas d'echec on-chain : raise escrow.EscrowError ou Exception, le caller
    rollback. Si le lock a reussi mais que le payout echoue, on raise sans
    rollback (l'admin doit regler a la main) - le casino_bank a recu la mise.
    """
    # ─── Validation
    if choice not in ("heads", "tails"):
        raise CoinflipError("Choix doit etre 'heads' ou 'tails'")
    if not isinstance(bet, int) or bet <= 0:
        raise CoinflipError("Mise doit etre un entier positif")
    if not client_seed or len(client_seed) > 128:
        raise CoinflipError("client_seed manquant ou trop long (max 128 chars)")

    min_bet = settings.get_int(db, "coinflip_min_bet", 1)
    max_bet = settings.get_int(db, "coinflip_max_bet", 200)
    edge_pct = settings.get_float(db, "coinflip_edge_pct", 2.0)

    if bet < min_bet or bet > max_bet:
        raise CoinflipError(
            f"Mise hors limites ({min_bet}-{max_bet} CAMP)"
        )

    # Edge sanity check (l'admin pourrait avoir mis une valeur folle).
    # On clamp 0-50% par securite : au-dela, le jeu n'a plus de sens.
    if edge_pct < 0 or edge_pct >= 50:
        raise CoinflipError(
            f"Edge maison hors limites ({edge_pct}%), contacte l'admin"
        )

    # ─── Commit RNG (publie un hash, garde le secret)
    seed_hash, seed_id = randomness.commit(db, "coinflip")

    # ─── Lock de la mise vers casino_bank
    try:
        tx_lock = escrow.lock(
            db, user, CASINO_BANK_ROLE, bet,
            f"coinflip seed_id={seed_id}",
        )
    except escrow.EscrowError:
        # Solde insuffisant ou compte systeme manquant : on remonte tel quel,
        # le caller rollback et expose en 400.
        raise

    # ─── Reveal + resolution
    server_seed, combined = randomness.reveal(db, seed_id, client_seed)
    outcome = "heads" if randomness.derive_int(combined, 2) == 0 else "tails"
    win = outcome == choice

    # Payout : 2x la mise * (1 - edge/100). Arrondi a l'entier inferieur
    # (un peu plus avantageux pour le casino sur le centieme de CAMP).
    payout = int(bet * 2 * (1 - edge_pct / 100)) if win else 0

    tx_payout: Optional[str] = None
    if win and payout > 0:
        # Si ca rate, on NE rollback PAS : la mise est partie au casino,
        # le user merite son payout. L'admin verra l'erreur et reglera
        # a la main. C'est le pattern documente dans EXTENSIONS.md.
        tx_payout = escrow.release(
            db, CASINO_BANK_ROLE, user, payout,
            f"coinflip seed_id={seed_id} win",
        )

    # ─── Persiste la round
    round_ = CoinflipRound(
        username=user.username,
        bet_amount=bet,
        choice=choice,
        outcome=outcome,
        win=win,
        payout=payout,
        client_seed=client_seed,
        rng_seed_id=seed_id,
        status="settled",
        settled_at=datetime.datetime.utcnow(),
        tx_hash_lock=tx_lock,
        tx_hash_payout=tx_payout,
    )
    db.add(round_)
    db.flush()

    # Lie le seed a la round (pour audit a posteriori)
    seed_row = db.get(RngSeed, seed_id)
    if seed_row is not None:
        seed_row.ref_id = round_.id

    db.commit()
    db.refresh(round_)

    return PlayResult(
        id=round_.id,
        bet_amount=bet,
        choice=choice,
        outcome=outcome,
        win=win,
        payout=payout,
        edge_pct=edge_pct,
        seed_hash=seed_hash,
        server_seed=server_seed,
        client_seed=client_seed,
        combined_hash=combined,
        tx_hash_lock=tx_lock,
        tx_hash_payout=tx_payout,
        new_balance=get_balance_camp(user.address),
        ts=round_.ts.isoformat() + "Z" if round_.ts else "",
    )


def history_dict(r: CoinflipRound) -> dict:
    """Serialise une round pour l'API (user history + admin)."""
    return {
        "id": r.id,
        "username": r.username,
        "bet_amount": r.bet_amount,
        "choice": r.choice,
        "outcome": r.outcome,
        "win": r.win,
        "payout": r.payout,
        "status": r.status,
        "ts": r.ts.isoformat() + "Z" if r.ts else None,
        "tx_hash_lock": r.tx_hash_lock,
        "tx_hash_payout": r.tx_hash_payout,
    }
