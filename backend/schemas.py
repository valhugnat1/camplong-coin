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
    statement: str = Field(..., min_length=1, max_length=512)
    category: Optional[str] = Field(None, max_length=32)
    deadline: datetime.datetime
    creator_side: Literal["yes", "no"]
    stake_creator: int = Field(..., gt=0)
    odds_num: int = Field(..., gt=0)
    odds_den: int = Field(..., gt=0)
    arbiter_username: Optional[str] = None
    arbiter_fee_pct: int = Field(0, ge=0, le=50)


class ResolveBetIn(BaseModel):
    resolution: Literal["yes", "no", "void"]


# ─── Casino ────────────────────────────────────────────

class CoinflipPlayIn(BaseModel):
    bet: int = Field(..., gt=0)
    choice: Literal["heads", "tails"]
    # Contribution aleatoire cote client (le user tape n'importe quoi, on
    # combine avec le secret serveur pour le tirage provably fair).
    client_seed: str = Field(..., min_length=1, max_length=128)


# ─── App settings (admin) ──────────────────────────────

class SettingUpdateIn(BaseModel):
    value: str = Field(..., min_length=1, max_length=256)
