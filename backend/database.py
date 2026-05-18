"""
database.py - Connection a la DB Postgres (Scaleway Serverless ou local).

Le DB_SCHEMA env var ('test' ou 'prod') est applique de DEUX manieres
pour etre certain de toujours toucher le bon schema :
  1. SET search_path a chaque nouvelle connexion (pour les requetes textuelles)
  2. __table_args__ schema=DB_SCHEMA dans models.py (pour les requetes ORM)
"""
import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]
DB_SCHEMA = os.environ.get("DB_SCHEMA", "test")

if DB_SCHEMA not in ("test", "prod"):
    raise ValueError(f"DB_SCHEMA doit etre 'test' ou 'prod', recu : {DB_SCHEMA!r}")

# Scaleway donne parfois un URL en postgres:// ; SQLAlchemy veut postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)


@event.listens_for(engine, "connect")
def _set_search_path(dbapi_conn, _):
    """Force le search_path a chaque nouvelle connexion (ceinture)."""
    cursor = dbapi_conn.cursor()
    cursor.execute(f'SET search_path TO "{DB_SCHEMA}", public')
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db():
    """FastAPI dependency : ouvre une session, la ferme apres usage."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()