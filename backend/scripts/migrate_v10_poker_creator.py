"""
migrate_v10_poker_creator.py
─────────────────────────────────────────────────────────────────────
Migration v10 : ajoute `creator_username` sur poker_tables pour que
les joueurs puissent creer leurs propres tables (et eux seuls les
supprimer). NULL = table cree par l'admin (ou table existante avant
cette migration).

Idempotent + multi-schemas (test + prod par defaut).

Usage :
  python scripts/migrate_v10_poker_creator.py
  python scripts/migrate_v10_poker_creator.py test
  python scripts/migrate_v10_poker_creator.py --dry-run
"""
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from config import DATABASE_URL


DDL_STEPS = [
    ("Add creator_username to poker_tables", """
        ALTER TABLE {schema}.poker_tables
            ADD COLUMN IF NOT EXISTS creator_username VARCHAR(64) NULL;
        CREATE INDEX IF NOT EXISTS idx_poker_tables_creator
            ON {schema}.poker_tables(creator_username);
    """),
]


def migrate_schema(engine, schema: str, dry_run: bool = False) -> None:
    print(f"\n{'='*64}\n  Migration schema : {schema}\n{'='*64}")
    if dry_run:
        for label, sql in DDL_STEPS:
            print(f"\n--- {label} ---")
            print(sql.format(schema=schema))
        return
    with engine.begin() as conn:
        conn.execute(text(f'SET search_path TO "{schema}", public'))
        for label, sql in DDL_STEPS:
            print(f"  → {label} ...", end=" ", flush=True)
            try:
                conn.execute(text(sql.format(schema=schema)))
                print("ok")
            except SQLAlchemyError as e:
                print(f"FAIL\n     {e}")
                raise
    print(f"\n  Schema '{schema}' migre avec succes ✓")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry_run = "--dry-run" in sys.argv
    schemas = args if args else ["test", "prod"]
    print("Migration v10 — poker_tables.creator_username")
    print(f"  Schemas : {schemas}")
    print(f"  Dry run : {dry_run}")
    engine = create_engine(DATABASE_URL, future=True)
    for s in schemas:
        try:
            migrate_schema(engine, s, dry_run=dry_run)
        except SQLAlchemyError as e:
            print(f"\n❌ Echec migration '{s}' : {e}")
            sys.exit(1)
    print("\nMigration v10 terminee.")


if __name__ == "__main__":
    main()
