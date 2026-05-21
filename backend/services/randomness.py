"""
services/randomness.py - Tirages aleatoires provably fair (commit-reveal).

Pour chaque tirage :
  1. commit()  : on genere un secret (32 bytes hex), on publie son sha256
                 dans la table rng_seeds. Retourne (seed_hash, seed_id).
  2. reveal()  : on lit le secret, on combine avec le client_seed fourni
                 par le user, on calcule combined_hash = sha256(secret || client_seed).
                 Marque la ligne comme revealed=True.
  3. derive_int(combined, modulo) : retourne un int dans [0, modulo[.

Le user peut verifier a posteriori :
  - sha256(server_seed) == seed_hash   (le backend n'a pas change le secret)
  - sha256(server_seed + client_seed) donne bien combined_hash
  - L'outcome se deduit de combined_hash et du modulo.

Note : on commit + reveal dans la meme requete HTTP pour la simplicite UX
(le user ne voit pas le hash AVANT de miser). C'est ce que font la plupart
des casinos provably fair en ligne.
"""
import datetime
import hashlib
import secrets
from typing import Optional

from sqlalchemy.orm import Session

from models import RngSeed


def commit(db: Session, purpose: str) -> tuple[str, int]:
    """
    Cree une ligne rng_seeds avec un secret aleatoire. Retourne
    (seed_hash, seed_id). Le caller flushera la session.
    """
    secret = secrets.token_hex(32)              # 64 hex chars = 32 bytes
    seed_hash = hashlib.sha256(secret.encode()).hexdigest()
    row = RngSeed(
        purpose=purpose,
        seed_hash=seed_hash,
        seed_secret=secret,
        revealed=False,
    )
    db.add(row)
    db.flush()
    return seed_hash, row.id


def reveal(
    db: Session,
    seed_id: int,
    client_seed: str,
    ref_id: Optional[int] = None,
) -> tuple[str, str]:
    """
    Marque le secret comme revele, retourne (server_seed, combined_hash).
    combined_hash = sha256(server_seed || ':' || client_seed).
    """
    row = db.get(RngSeed, seed_id)
    if row is None:
        raise ValueError(f"rng_seed id={seed_id} introuvable")

    row.revealed = True
    row.revealed_at = datetime.datetime.utcnow()
    row.client_seed = client_seed
    if ref_id is not None:
        row.ref_id = ref_id

    combined = hashlib.sha256(
        f"{row.seed_secret}:{client_seed}".encode()
    ).hexdigest()
    return row.seed_secret, combined


def derive_int(combined_hash: str, modulo: int) -> int:
    """
    Convertit les 8 premiers chars hex (32 bits) en int, puis modulo.
    32 bits = ~4 milliards, biais modulo negligeable pour modulo petit.
    """
    if modulo <= 0:
        raise ValueError("modulo doit etre > 0")
    value = int(combined_hash[:8], 16)
    return value % modulo
