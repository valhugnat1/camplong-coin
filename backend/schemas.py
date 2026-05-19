from pydantic import BaseModel, Field

# --- Admin ---
class AdminLoginIn(BaseModel):
    password: str

class CreateUserIn(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    user_password: str = Field(..., min_length=1)
    initial_camp: int = Field(0, ge=0)

class AmountIn(BaseModel):
    username: str
    amount: int = Field(..., gt=0)
    note: str = ""

# --- Users ---
class LoginIn(BaseModel):
    username: str
    password: str

class TransferIn(BaseModel):
    to_username: str
    amount: int       # en CAMP entiers
    note: str = ""