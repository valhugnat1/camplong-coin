"""
services/slots.py - Logique metier de la machine a sous.

3 rouleaux, single payline. Le payout est sur 3-of-a-kind uniquement
(la combinaison la plus lisible pour les joueurs : 3 fois le meme symbole).

Edge maison : MECANIQUE, baked dans les poids des symboles et la table
de payouts. ~2.3% theorique avec les valeurs ci-dessous. Pas d'edge_pct
configurable cote admin (comme la roulette).

Calcul theorique :
  p(symbol_i) = weight_i / sum(weights)
  p(3 of symbol_i) = p(symbol_i)^3
  RTP = sum(p^3 * payout_multiplier_i)

Avec les valeurs actuelles (poids 5/4/3/2/1/1 → total 16, payouts
6/14/25/60/200/1000), RTP ≈ 97.7%, donc edge ≈ 2.3%.
"""
import datetime
import json
from dataclasses import dataclass, asdict
from typing import Optional

from sqlalchemy.orm import Session

from models import User, SlotsSpin, RngSeed
from services import escrow, randomness, settings
from blockchain import get_balance_camp


CASINO_BANK_ROLE = "casino_bank"


# ─── Table des symboles ─────────────────────────────────
# Ordre fixe (utilise par derive_int pour mapper l'index sur le symbole).
# (code, emoji, weight, payout_multiplier_3x)
#
# Note : on stocke un "code" stable (ascii) en plus de l'emoji pour eviter
# d'avoir a parser/comparer des chaines emoji en DB.
#
# Design : on vise P(gain) ≈ 14% (1 sur 7), avec un max payout × 250
# (gain max = 250 × max_bet). RTP theorique ≈ 90%, edge ≈ 10%.
#
# Decomposition de la frequence des gains :
#   - cherry  (12.50% des spins) : petit gain ×4  → "ca crepite"
#   - lemon   ( 1.56% des spins) : moyen ×14
#   - orange  ( 0.20% des spins) : gros ×50
#   - bell    ( 0.02% des spins) : tres gros ×100
#   - star    ( 0.02% des spins) : jackpot ×250
SYMBOLS = [
    # code      emoji   weight  payout_3x
    ("cherry",  "🍒",   8,      4),
    ("lemon",   "🍋",   4,      14),
    ("orange",  "🍊",   2,      50),
    ("bell",    "🔔",   1,      100),
    ("star",    "⭐",   1,      250),
]

TOTAL_WEIGHT = sum(w for _, _, w, _ in SYMBOLS)   # = 16


def theoretical_rtp_pct() -> float:
    """RTP theorique (en %) calcule a partir des poids et payouts."""
    rtp = 0.0
    for _, _, w, payout in SYMBOLS:
        p = w / TOTAL_WEIGHT
        rtp += (p ** 3) * payout
    return round(rtp * 100, 2)


class SlotsError(Exception):
    """Erreur metier (mise hors limites, solde insuffisant, ...)."""


@dataclass
class SpinResult:
    id: int
    bet_amount: int
    payout: int
    win: bool
    reels: list[dict]              # [{'code': 'cherry', 'emoji': '🍒'}, ...]
    combo: str                     # '3xcherry' / 'no_match'
    multiplier: int                # 0 si perdu
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


def weighted_pick_index(combined_hash: str, offset: int) -> int:
    """
    Tire un index dans [0, len(SYMBOLS)) ponderé par les `weight` des symboles.
    Provably fair : meme combined_hash + meme offset → meme resultat.
    """
    # On utilise un sous-hash dependant de l'offset pour avoir 3 tirages
    # independants a partir du meme combined_hash.
    # randomness.derive_int hash deja avec :offset, donc on s'appuie dessus.
    r = randomness.derive_int(combined_hash, TOTAL_WEIGHT * 1_000)  # haute granularite
    # On rescale dans [0, TOTAL_WEIGHT)
    # Note : derive_int prend deja en compte l'offset via son propre hash interne ?
    # Non, randomness.derive_int ne prend pas d'offset : on doit composer
    # le hash combined+offset nous-meme. Sinon les 3 rouleaux donneraient
    # le meme symbole a chaque spin (catastrophe).
    return _weighted_pick(combined_hash, offset)


def _weighted_pick(combined_hash: str, offset: int) -> int:
    """Helper : compose combined+offset puis hash + modulo + lookup poids."""
    import hashlib
    composite = hashlib.sha256(f"{combined_hash}:{offset}".encode()).hexdigest()
    r = int(composite[:8], 16) % TOTAL_WEIGHT
    cumul = 0
    for i, (_, _, w, _) in enumerate(SYMBOLS):
        cumul += w
        if r < cumul:
            return i
    return len(SYMBOLS) - 1  # safety, ne devrait jamais arriver


def evaluate(reel_indices: list[int]) -> tuple[str, int, int]:
    """
    Retourne (combo, multiplier, payout_amount) — mais on a pas la mise ici.
    Donc on retourne juste (combo, multiplier) ; le caller calcule
    payout = bet * multiplier.
    """
    a, b, c = reel_indices
    if a == b == c:
        code, _emoji, _w, multiplier = SYMBOLS[a]
        return f"3x{code}", multiplier
    return "no_match", 0


def spin(db: Session, user: User, bet: int, client_seed: str) -> SpinResult:
    """
    Joue un spin : commit RNG, lock mise, tire 3 symboles, paie si gain.

    Pattern atomique identique a coinflip/roulette : on lock AVANT le tirage.
    Si la release du payout echoue alors que le lock a marche, on raise
    SANS rollback (la trace du lock reste, l'admin regle a la main).
    """
    # ─── Validation
    if not isinstance(bet, int) or bet <= 0:
        raise SlotsError("Mise doit etre un entier positif")
    if not client_seed or len(client_seed) > 128:
        raise SlotsError("client_seed manquant ou trop long (max 128 chars)")

    min_bet = settings.get_int(db, "slots_min_bet", 1)
    max_bet = settings.get_int(db, "slots_max_bet", 100)
    if bet < min_bet or bet > max_bet:
        raise SlotsError(f"Mise hors limites ({min_bet}-{max_bet} CAMP)")

    # ─── Commit RNG
    seed_hash, seed_id = randomness.commit(db, "slots")

    # ─── Lock
    tx_lock = escrow.lock(
        db, user, CASINO_BANK_ROLE, bet,
        f"slots seed_id={seed_id}",
    )

    # ─── Reveal + tirage 3 rouleaux
    server_seed, combined = randomness.reveal(db, seed_id, client_seed)
    reel_indices = [_weighted_pick(combined, offset=i) for i in range(3)]
    reels = [
        {"code": SYMBOLS[idx][0], "emoji": SYMBOLS[idx][1]}
        for idx in reel_indices
    ]

    combo, multiplier = evaluate(reel_indices)
    payout = bet * multiplier
    win = payout > 0

    # ─── Payout net si gain
    tx_payout: Optional[str] = None
    if win:
        tx_payout = escrow.release(
            db, CASINO_BANK_ROLE, user, payout,
            f"slots seed_id={seed_id} {combo}",
        )

    # ─── Persiste
    spin_row = SlotsSpin(
        username=user.username,
        bet_amount=bet,
        payout=payout,
        win=win,
        reels="|".join(r["emoji"] for r in reels),
        combo=combo,
        multiplier=multiplier,
        client_seed=client_seed,
        rng_seed_id=seed_id,
        status="settled",
        tx_hash_lock=tx_lock,
        tx_hash_payout=tx_payout,
    )
    db.add(spin_row)
    db.flush()

    # Lie le seed pour audit
    seed_row = db.get(RngSeed, seed_id)
    if seed_row is not None:
        seed_row.ref_id = spin_row.id

    db.commit()
    db.refresh(spin_row)

    return SpinResult(
        id=spin_row.id,
        bet_amount=bet,
        payout=payout,
        win=win,
        reels=reels,
        combo=combo,
        multiplier=multiplier,
        seed_hash=seed_hash,
        server_seed=server_seed,
        client_seed=client_seed,
        combined_hash=combined,
        tx_hash_lock=tx_lock,
        tx_hash_payout=tx_payout,
        new_balance=get_balance_camp(user.address),
        ts=spin_row.ts.isoformat() + "Z" if spin_row.ts else "",
    )


def history_dict(r: SlotsSpin) -> dict:
    """Serialise un spin pour l'API (user history + admin)."""
    reels = []
    if r.reels:
        for emoji in r.reels.split("|"):
            reels.append({"emoji": emoji})
    return {
        "id": r.id,
        "username": r.username,
        "bet_amount": r.bet_amount,
        "payout": r.payout,
        "win": r.win,
        "reels": reels,
        "combo": r.combo,
        "multiplier": r.multiplier,
        "status": r.status,
        "ts": r.ts.isoformat() + "Z" if r.ts else None,
        "tx_hash_lock": r.tx_hash_lock,
        "tx_hash_payout": r.tx_hash_payout,
    }


def paytable() -> list[dict]:
    """Table publique des payouts, exposee au front pour affichage."""
    return [
        {
            "code": code,
            "emoji": emoji,
            "combo": f"3x{code}",
            "label": f"{emoji}{emoji}{emoji}",
            "multiplier": payout,
            "weight": w,
            "probability": round((w / TOTAL_WEIGHT) ** 3, 6),
        }
        for code, emoji, w, payout in SYMBOLS
    ]
