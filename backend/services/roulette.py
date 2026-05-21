"""
services/roulette.py - Logique metier de la roulette europeenne (37 cases).

Reutilise les memes primitives que coinflip :
  - escrow.lock/release vers 'casino_bank'
  - randomness.commit/reveal/derive_int pour le tirage provably fair
  - settings pour les limites de mise (min/max), pas d'edge configurable
    (l'edge maison est mecanique : 1/37 = ~2.7%)

Optimisation gas : un spin = N mises sur le tapis = 1 lock total + 1 payout
net. Sans ca, 10 spots misés = 11 tx on-chain, ce qui sature le nonce
treasury pour rien.
"""
import datetime
import json
from dataclasses import dataclass, asdict
from typing import Optional

from sqlalchemy.orm import Session

from models import User, RouletteSpin, RngSeed
from services import escrow, randomness, settings
from blockchain import get_balance_camp


CASINO_BANK_ROLE = "casino_bank"

# Numeros rouges d'une roulette europeenne standard.
RED_NUMBERS = {
    1, 3, 5, 7, 9, 12, 14, 16, 18,
    19, 21, 23, 25, 27, 30, 32, 34, 36,
}

# Spots autorises en V1. (Splits/streets/corners viendront en V2 si besoin.)
# Format compact : spot string parse cote evaluate_bet.
ALLOWED_SIMPLE_SPOTS = {
    "red", "black", "even", "odd", "low", "high",
    "dozen=1", "dozen=2", "dozen=3",
    "col=1", "col=2", "col=3",
}


class RouletteError(Exception):
    """Erreur metier (mise hors limites, spot invalide, ...)."""


@dataclass
class SpinResult:
    id: int
    total_bet: int
    total_payout: int
    net_pnl: int
    bets: list[dict]
    outcome_number: int
    outcome_color: str
    winning_spots: list[str]
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


def number_color(n: int) -> str:
    if n == 0:
        return "green"
    return "red" if n in RED_NUMBERS else "black"


def validate_spot(spot: str) -> None:
    """Raise RouletteError si le spot n'est pas un format reconnu."""
    if spot in ALLOWED_SIMPLE_SPOTS:
        return
    if spot.startswith("n="):
        try:
            n = int(spot[2:])
        except ValueError:
            raise RouletteError(f"Spot invalide : {spot}")
        if n < 0 or n > 36:
            raise RouletteError(f"Numero hors plage [0,36] : {n}")
        return
    raise RouletteError(f"Spot inconnu : {spot}")


def evaluate_bet(bet: dict, outcome: int) -> int:
    """
    Retourne le payout TOTAL (mise incluse) si gagnant, 0 sinon.
    Convention : "amount * 2" pour une mise even-money payee 1:1 (= mise
    rendue + 1x). "amount * 36" pour un numero plein paye 35:1.
    """
    spot = bet["spot"]
    amount = int(bet["amount"])
    color = number_color(outcome)

    if spot.startswith("n="):
        n = int(spot[2:])
        return amount * 36 if n == outcome else 0
    if spot == "red":
        return amount * 2 if color == "red" else 0
    if spot == "black":
        return amount * 2 if color == "black" else 0
    if spot == "even":
        return amount * 2 if outcome != 0 and outcome % 2 == 0 else 0
    if spot == "odd":
        return amount * 2 if outcome != 0 and outcome % 2 == 1 else 0
    if spot == "low":
        return amount * 2 if 1 <= outcome <= 18 else 0
    if spot == "high":
        return amount * 2 if 19 <= outcome <= 36 else 0
    if spot.startswith("dozen="):
        d = int(spot.split("=")[1])
        return amount * 3 if outcome != 0 and (outcome - 1) // 12 == d - 1 else 0
    if spot.startswith("col="):
        c = int(spot.split("=")[1])
        return amount * 3 if outcome != 0 and (outcome - 1) % 3 == c - 1 else 0
    return 0


def spin(db: Session, user: User, bets: list[dict], client_seed: str) -> SpinResult:
    """
    Joue un spin avec N mises agregees.
    Lock 1 = somme des mises, payout net = somme des gains.
    """
    # ─── Validation entree
    if not isinstance(bets, list) or not bets:
        raise RouletteError("Au moins une mise est requise")
    if len(bets) > 50:
        raise RouletteError("Trop de mises sur un spin (max 50)")

    total_bet = 0
    for b in bets:
        if not isinstance(b, dict) or "spot" not in b or "amount" not in b:
            raise RouletteError("Chaque mise doit avoir { spot, amount }")
        spot = str(b["spot"]).strip()
        try:
            amount = int(b["amount"])
        except (TypeError, ValueError):
            raise RouletteError(f"Montant invalide pour {spot}")
        if amount <= 0:
            raise RouletteError(f"Montant non positif pour {spot}")
        validate_spot(spot)
        b["spot"] = spot
        b["amount"] = amount
        total_bet += amount

    if not client_seed or len(client_seed) > 128:
        raise RouletteError("client_seed manquant ou trop long (max 128 chars)")

    # ─── Limites en DB (modifiables par l'admin)
    min_bet = settings.get_int(db, "roulette_min_bet", 1)
    max_bet = settings.get_int(db, "roulette_max_bet", 200)
    if total_bet < min_bet:
        raise RouletteError(
            f"Mise totale {total_bet} < min {min_bet} CAMP"
        )
    if total_bet > max_bet:
        raise RouletteError(
            f"Mise totale {total_bet} > max {max_bet} CAMP"
        )

    # ─── Commit RNG (publie le hash, garde le secret)
    seed_hash, seed_id = randomness.commit(db, "roulette")

    # ─── Lock unique (somme des mises) vers casino_bank
    tx_lock = escrow.lock(
        db, user, CASINO_BANK_ROLE, total_bet,
        f"roulette seed_id={seed_id}",
    )

    # ─── Reveal + tirage 0..36
    server_seed, combined = randomness.reveal(db, seed_id, client_seed)
    outcome = randomness.derive_int(combined, 37)
    color = number_color(outcome)

    # ─── Evaluation
    total_payout = 0
    winning_spots: list[str] = []
    for b in bets:
        gain = evaluate_bet(b, outcome)
        if gain > 0:
            total_payout += gain
            winning_spots.append(b["spot"])

    # ─── Payout unique si gain. Si ca rate apres le lock, l'admin
    # regle a la main (pattern documente dans EXTENSIONS.md - on raise
    # SANS rollback pour que la trace du lock reste).
    tx_payout: Optional[str] = None
    if total_payout > 0:
        tx_payout = escrow.release(
            db, CASINO_BANK_ROLE, user, total_payout,
            f"roulette seed_id={seed_id} payout",
        )

    # ─── Persiste le spin
    spin_row = RouletteSpin(
        username=user.username,
        total_bet=total_bet,
        total_payout=total_payout,
        net_pnl=total_payout - total_bet,
        bets_json=json.dumps(bets),
        outcome_number=outcome,
        outcome_color=color,
        client_seed=client_seed,
        rng_seed_id=seed_id,
        status="settled",
        tx_hash_lock=tx_lock,
        tx_hash_payout=tx_payout,
    )
    db.add(spin_row)
    db.flush()

    # Lie le seed a la ligne spin pour l'audit
    seed_row = db.get(RngSeed, seed_id)
    if seed_row is not None:
        seed_row.ref_id = spin_row.id

    db.commit()
    db.refresh(spin_row)

    return SpinResult(
        id=spin_row.id,
        total_bet=total_bet,
        total_payout=total_payout,
        net_pnl=total_payout - total_bet,
        bets=bets,
        outcome_number=outcome,
        outcome_color=color,
        winning_spots=winning_spots,
        seed_hash=seed_hash,
        server_seed=server_seed,
        client_seed=client_seed,
        combined_hash=combined,
        tx_hash_lock=tx_lock,
        tx_hash_payout=tx_payout,
        new_balance=get_balance_camp(user.address),
        ts=spin_row.ts.isoformat() + "Z" if spin_row.ts else "",
    )


def history_dict(r: RouletteSpin) -> dict:
    """Serialise un spin pour l'API (user history + admin)."""
    try:
        bets = json.loads(r.bets_json) if r.bets_json else []
    except json.JSONDecodeError:
        bets = []
    return {
        "id": r.id,
        "username": r.username,
        "total_bet": r.total_bet,
        "total_payout": r.total_payout,
        "net_pnl": r.net_pnl,
        "bets": bets,
        "outcome_number": r.outcome_number,
        "outcome_color": r.outcome_color,
        "status": r.status,
        "ts": r.ts.isoformat() + "Z" if r.ts else None,
        "tx_hash_lock": r.tx_hash_lock,
        "tx_hash_payout": r.tx_hash_payout,
    }
