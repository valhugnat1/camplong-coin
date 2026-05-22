import datetime
from typing import Literal, Optional
from pydantic import BaseModel, EmailStr, Field

# ─── Admin ─────────────────────────────────────────────

class AdminLoginIn(BaseModel):
    password: str

class CreateUserIn(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    user_password: str = Field(..., min_length=1)
    email: Optional[EmailStr] = None
    initial_camp: int = Field(0, ge=0)

class AmountIn(BaseModel):
    username: str
    amount: int = Field(..., gt=0)
    note: str = ""

class UpdateOrderIn(BaseModel):
    """PATCH /admin/orders/{id} — l'admin peut mettre à jour le statut et/ou la note."""
    status: Optional[Literal["pending", "done", "cancelled"]] = None
    admin_note: Optional[str] = None

# ─── Users ─────────────────────────────────────────────

class LoginIn(BaseModel):
    username: str
    password: str

class TransferIn(BaseModel):
    to_username: str
    amount: int                    # en CAMP entiers
    note: str = ""

class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=4)

class RevealKeyIn(BaseModel):
    password: str

class UpdateEmailIn(BaseModel):
    email: EmailStr

class CreateOrderIn(BaseModel):
    type: Literal["buy", "sell"]
    amount_camp: int = Field(..., gt=0)
    amount_eur: float = Field(..., gt=0)
    handle: str = ""               # obligatoire pour 'sell' (validé côté route)
    note: str = ""


# ─── Bets ──────────────────────────────────────────────

class CreateBetIn(BaseModel):
    """
    Creation d'un pari :
      - type 'yes_no' : on cree automatiquement 2 options Oui / Non.
        Le champ 'options' est ignore.
      - type 'multi_choice' : 'options' doit contenir 2 a 6 labels distincts.

    'creator_option_index' : index dans la liste finale d'options (0..n-1) sur
    laquelle le createur souhaite parier. None s'il ne participe pas.
    """
    statement: str = Field(..., min_length=1, max_length=512)
    deadline: datetime.datetime
    type: Literal["yes_no", "multi_choice"] = "yes_no"
    stake: int = Field(..., gt=0)
    options: Optional[list[str]] = None
    creator_option_index: Optional[int] = Field(None, ge=0, le=5)
    arbiter_username: Optional[str] = None


class JoinBetIn(BaseModel):
    """Rejoindre un pari sur une option donnee."""
    option_id: int = Field(..., gt=0)


class VoteBetIn(BaseModel):
    """
    Vote communautaire sur la resolution. option_id = NULL = vote pour 'void'
    (refund de tous les participants).
    """
    option_id: Optional[int] = None


class ResolveBetIn(BaseModel):
    """
    Resolution arbitre ou admin. option_id = NULL = void.
    """
    option_id: Optional[int] = None


# ─── Casino ────────────────────────────────────────────

class CoinflipPlayIn(BaseModel):
    bet: int = Field(..., gt=0)
    choice: Literal["heads", "tails"]
    # Contribution aleatoire cote client (le user tape n'importe quoi, on
    # combine avec le secret serveur pour le tirage provably fair).
    client_seed: str = Field(..., min_length=1, max_length=128)


class RouletteBetIn(BaseModel):
    spot: str = Field(..., min_length=1, max_length=16)
    amount: int = Field(..., gt=0)


class RouletteSpinIn(BaseModel):
    bets: list[RouletteBetIn] = Field(..., min_length=1, max_length=50)
    client_seed: str = Field(..., min_length=1, max_length=128)


class SlotsSpinIn(BaseModel):
    bet: int = Field(..., gt=0)
    client_seed: str = Field(..., min_length=1, max_length=128)


# ─── App settings (admin) ──────────────────────────────

class SettingUpdateIn(BaseModel):
    value: str = Field(..., min_length=1, max_length=256)
