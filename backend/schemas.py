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


# ─── Milk (Bourse du Lait) ─────────────────────────────

class MilkSwapIn(BaseModel):
    """
    POST /milk/pools/{symbol}/swap.
    Pour un buy : amount = CAMP entrants.
    Pour un sell : amount = milli-bouteilles entrantes (multiple de 1000 conseille).
    """
    side: Literal["buy", "sell"]
    amount: int = Field(..., gt=0)
    expected_price: Optional[float] = Field(None, gt=0)
    max_slippage_pct: Optional[float] = Field(None, ge=0, le=100)


class AdminMilkCreatePoolIn(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=32)
    name: str = Field(..., min_length=1, max_length=64)
    initial_bottles: int = Field(..., gt=0)
    price_per_bottle: int = Field(..., gt=0)
    fee_pct: float = Field(0.5, ge=0, le=10)


class AdminMilkUpdatePoolIn(BaseModel):
    fee_pct: Optional[float] = Field(None, ge=0, le=10)
    chaos_enabled: Optional[bool] = None
    status: Optional[Literal["active", "paused"]] = None


class AdminMilkInjectIn(BaseModel):
    """Inject chaos manuelle : kind + delta en bouteilles (signe)."""
    kind: Literal["famine", "spoil", "overstock", "import"]
    bottles: int = Field(..., description="positif pour ajouter, negatif pour retirer")
    narrative: Optional[str] = Field(None, max_length=256)


class AdminMilkTemplateIn(BaseModel):
    """Creation d'un template chaos."""
    slug: str = Field(..., min_length=1, max_length=64,
                       pattern=r"^[a-z0-9_]+$")
    kind: Literal["famine", "spoil", "overstock", "import"]
    delta_type: Literal["pct", "bottles"]
    delta_min: float
    delta_max: float
    narrative: str = Field(..., min_length=1, max_length=512)
    weight: int = Field(1, ge=1, le=100)
    enabled: bool = True


class AdminMilkTemplateUpdateIn(BaseModel):
    """Update partielle d'un template chaos."""
    kind: Optional[Literal["famine", "spoil", "overstock", "import"]] = None
    delta_type: Optional[Literal["pct", "bottles"]] = None
    delta_min: Optional[float] = None
    delta_max: Optional[float] = None
    narrative: Optional[str] = Field(None, min_length=1, max_length=512)
    weight: Optional[int] = Field(None, ge=1, le=100)
    enabled: Optional[bool] = None


# ─── Poker ─────────────────────────────────────────────

class PokerSitIn(BaseModel):
    buyin: int = Field(..., gt=0)


class PokerActIn(BaseModel):
    """
    Une action a la table : fold/check/call/bet/raise.
    Pour bet : `amount` = montant misé (>= min_raise).
    Pour raise : `amount` = NOUVEAU total de mise visee (pas l'increment).
    Pour fold/check/call : `amount` est ignore.
    """
    move: Literal["fold", "check", "call", "bet", "raise"]
    amount: int = Field(0, ge=0)


class PokerCreateTableIn(BaseModel):
    """Creation d'une table cote joueur (et admin : meme payload)."""
    name: str = Field(..., min_length=1, max_length=64)
    blind_small: int = Field(..., gt=0)
    blind_big: int = Field(..., gt=0)
    min_buyin: int = Field(..., gt=0)
    max_buyin: int = Field(..., gt=0)
    max_players: int = Field(6, ge=2, le=10)


# Alias historique pour l'admin (meme schema). Conserve pour ne pas
# casser les imports existants.
AdminPokerCreateTableIn = PokerCreateTableIn


class AdminPokerUpdateTableIn(BaseModel):
    status: Optional[Literal["open", "closed"]] = None


# ─── App settings (admin) ──────────────────────────────

class SettingUpdateIn(BaseModel):
    value: str = Field(..., min_length=1, max_length=256)


class AnalyticsLabelIn(BaseModel):
    """
    Reclassification d'un mouvement de tresorerie pour le dashboard admin.
    `label=None` retire la correction manuelle (retour a la deduction auto).
    """
    label: Optional[str] = None   # 'onboarding'|'topup'|'withdrawal'|'ignore'|None
    note: Optional[str] = ""
