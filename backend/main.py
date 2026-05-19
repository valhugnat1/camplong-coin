from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import admin, users
from config import CONTRACT_ADDRESS
from database import DB_SCHEMA

router = FastAPI(title="CamplongCoin API")

router.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

router.include_router(admin.router)
router.include_router(users.router)

@router.get("/")
def root():
    return {
        "status": "ok",
        "chain": "Base Sepolia",
        "contract": CONTRACT_ADDRESS,
        "schema": DB_SCHEMA,
    }