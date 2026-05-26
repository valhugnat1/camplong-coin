"""
services/settings.py - Lecture/ecriture des parametres dynamiques.

Les parametres modifiables a chaud (edge maison du coinflip, limites de
mise, ...) sont stockes dans la table app_settings (key/value).
Ce module expose des helpers typés (get_float, get_int) avec defaults
de secours, et un setter qui upsert.

Aucun cache : la table est petite et les lectures sont peu frequentes
(une fois par play coinflip, une fois par chargement admin). Un cache
ferait diverger les instances en cas de scale horizontal.
"""
from typing import Optional
import datetime

from sqlalchemy.orm import Session

from models import AppSetting


# Defauts de secours si la cle n'est pas en DB (cas d'un setup incomplet).
# Ces valeurs doivent correspondre au seed initial de migrate_v6_app_settings.py.
DEFAULTS = {
    # Coinflip
    "coinflip_edge_pct": "2",
    "coinflip_min_bet": "1",
    "coinflip_max_bet": "200",
    # Roulette (edge mecanique 2.7%, donc pas d'edge_pct configurable)
    "roulette_min_bet": "1",
    "roulette_max_bet": "200",
    # Slots (edge mecanique ~2.3% via weights+payouts hardcoded)
    "slots_min_bet": "1",
    "slots_max_bet": "100",
    # Bourse du lait : frequence du bot chaos (lue par main.py::_chaos_loop)
    "milk_chaos_tick_seconds": "900",   # 15 minutes
    "milk_chaos_proba_pct": "25",       # 25% par tick par pool actif
    # Cap de volatilite par event bot (en % de variation de prix MAX).
    # 0 = bot mute, 100 = pas de cap. 20 = price_after/price_before <= 1.20
    # (donc delta_milk negatif clamp a -16.67% de reserve).
    "milk_chaos_max_volatility_pct": "20",
}

# Cles autorisees pour PATCH /admin/settings. Toute autre cle est refusee
# pour eviter qu'un admin n'introduise des cles fantaisistes.
WRITABLE_KEYS = set(DEFAULTS.keys())


def get_raw(db: Session, key: str) -> Optional[str]:
    """Retourne la valeur brute (string) ou None si absente."""
    row = db.get(AppSetting, key)
    if row is not None:
        return row.value
    return DEFAULTS.get(key)


def get_float(db: Session, key: str, default: float = 0.0) -> float:
    raw = get_raw(db, key)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def get_int(db: Session, key: str, default: int = 0) -> int:
    raw = get_raw(db, key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def list_all(db: Session) -> list[dict]:
    """Liste toutes les settings (avec leurs descriptions) pour le backoffice."""
    rows = db.query(AppSetting).order_by(AppSetting.key).all()
    return [
        {
            "key": r.key,
            "value": r.value,
            "description": r.description,
            "updated_at": r.updated_at.isoformat() + "Z" if r.updated_at else None,
        }
        for r in rows
    ]


def set_value(db: Session, key: str, value: str) -> AppSetting:
    """Upsert. Le caller commit la session."""
    row = db.get(AppSetting, key)
    if row is None:
        row = AppSetting(key=key, value=value)
        db.add(row)
    else:
        row.value = value
        row.updated_at = datetime.datetime.utcnow()
    return row
