import asyncio
import logging
import random

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import admin, users, bets, casino, milk, poker
from config import CONTRACT_ADDRESS
from database import DB_SCHEMA, SessionLocal
from models import MilkPool
from services import milk as milk_svc
from services import settings as settings_svc

logger = logging.getLogger(__name__)

router = FastAPI(title="CamplongCoin API")

router.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

router.include_router(admin.router)
router.include_router(users.router)
router.include_router(bets.router)
router.include_router(casino.router)
router.include_router(milk.router)
router.include_router(poker.router)


# ─── Chaos bot (Bourse du Lait) ────────────────────────
# Boucle asyncio en background. La frequence (tick_seconds) et la probabilite
# par tick (proba_pct) sont lues depuis app_settings A CHAQUE iteration, donc
# l'admin peut les changer a chaud depuis /admin/milk sans redeploiement.
# Les templates d'evenements sont aussi en DB (milk_chaos_templates).

CHAOS_TICK_MIN = 60          # 1 min plancher (anti-flood)
CHAOS_TICK_MAX = 24 * 3600   # 24h plafond


async def _chaos_loop():
    """Background loop : applique des chaos events periodiques sur les pools."""
    # Pause initiale pour laisser le serveur demarrer proprement
    await asyncio.sleep(60)
    while True:
        tick_seconds = 900  # fallback si lecture settings KO
        try:
            with SessionLocal() as db:
                tick_seconds = settings_svc.get_int(db, "milk_chaos_tick_seconds", 900)
                proba_pct = settings_svc.get_int(db, "milk_chaos_proba_pct", 25)
                # Clamp pour eviter qu'une mauvaise valeur ne fasse spam
                tick_seconds = max(CHAOS_TICK_MIN, min(CHAOS_TICK_MAX, tick_seconds))
                proba = max(0, min(100, proba_pct)) / 100.0

                if proba > 0:
                    pools = (
                        db.query(MilkPool)
                          .filter(MilkPool.status == "active",
                                  MilkPool.chaos_enabled == True)
                          .all()
                    )
                    applied = 0
                    for p in pools:
                        if random.random() > proba:
                            continue
                        event = milk_svc.apply_chaos(db, p, triggered_by="bot")
                        if event is not None:
                            applied += 1
                    if applied > 0:
                        db.commit()
                        logger.info(f"[chaos_bot] {applied} event(s) appliques")
        except Exception as e:
            logger.exception(f"[chaos_bot] erreur tick : {e}")
        await asyncio.sleep(tick_seconds)


@router.on_event("startup")
async def _start_chaos_bot():
    """Demarre la boucle chaos en background."""
    asyncio.create_task(_chaos_loop())


@router.get("/")
def root():
    return {
        "status": "ok",
        "chain": "Base Sepolia",
        "contract": CONTRACT_ADDRESS,
        "schema": DB_SCHEMA,
    }