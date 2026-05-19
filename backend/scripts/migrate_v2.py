"""
scripts/migrate_v2.py

Migration pour ajouter :
  - colonne `email` sur la table `users` (nullable)
  - table `market_orders`

A executer une fois par schema (test, puis prod) :
    DB_SCHEMA=test python scripts/migrate_v2.py
    DB_SCHEMA=prod python scripts/migrate_v2.py

Le script est idempotent : il check l'existence avant de creer/ajouter.
"""
import sys
import pathlib

# Permet d'importer depuis le parent (../backend)
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from database import engine, Base, DB_SCHEMA
from models import MarketOrder  # noqa: F401  (force l'import pour Base.metadata)


def column_exists(conn, table: str, column: str) -> bool:
    q = text("""
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = :schema
          AND table_name   = :table
          AND column_name  = :column
        LIMIT 1
    """)
    return conn.execute(q, {
        "schema": DB_SCHEMA, "table": table, "column": column
    }).scalar() is not None


def table_exists(conn, table: str) -> bool:
    q = text("""
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = :schema
          AND table_name   = :table
        LIMIT 1
    """)
    return conn.execute(q, {"schema": DB_SCHEMA, "table": table}).scalar() is not None


def main():
    print(f"=== Migration v2 sur le schema '{DB_SCHEMA}' ===\n")

    with engine.begin() as conn:
        # 1) Ajout colonne `email` sur users
        if column_exists(conn, "users", "email"):
            print("  [skip] users.email existe deja")
        else:
            print("  [ALTER] users : ajout colonne email (nullable)")
            conn.execute(text(f'ALTER TABLE "{DB_SCHEMA}".users ADD COLUMN email VARCHAR(256)'))
            print("    ok")

        # 2) Creation table market_orders via SQLAlchemy
        if table_exists(conn, "market_orders"):
            print("  [skip] market_orders existe deja")
        else:
            print("  [CREATE] market_orders")

    # create_all ne touche que les tables manquantes : safe
    Base.metadata.create_all(bind=engine, tables=[
        Base.metadata.tables[f"{DB_SCHEMA}.market_orders"]
    ])
    print("    ok\n")

    print("Migration terminee.")


if __name__ == "__main__":
    main()
