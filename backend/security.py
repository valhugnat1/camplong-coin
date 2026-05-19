import datetime
from typing import Optional
from fastapi import HTTPException, Depends, Header
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from config import JWT_SECRET, MASTER_KEY
from database import get_db
from models import User

fernet = Fernet(MASTER_KEY)
oauth2 = OAuth2PasswordBearer(tokenUrl="/login")

def require_admin(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Token manquant")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        if payload.get("role") != "admin":
            raise HTTPException(403, "Reserve admin")
    except (JWTError, KeyError):
        raise HTTPException(401, "Token invalide")
    return True

def current_user(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        username = payload["sub"]
    except (JWTError, KeyError):
        raise HTTPException(401, "Token invalide")
    u = db.get(User, username)
    if not u:
        raise HTTPException(401, "User inconnu")
    return u