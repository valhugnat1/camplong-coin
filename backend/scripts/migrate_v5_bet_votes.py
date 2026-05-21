"""
migrate_v5_bet_votes.py
─────────────────────────────────────────────────────────────────────
Migration v5 : resolution amiable des paris.

Ajoute deux colonnes a {schema}.bets :
  - creator_vote   VARCHAR(8) NULL  ('yes' | 'no' | 'void')
  - opponent_vote  VARCHAR(8) NULL

Quand creator_vote == opponent_vote, le pari est resolu automatiquement
sans arbitre ni admin (resolved_by = '__both_players__').

Idempotent (ADD COLUMN IF NOT EXISTS). Multi-schemas.

Usage :
  python scripts/migrate_v5_bet_votes.py            # test + prod
  python scripts/migrate_v5_bet_votes.py test
  python scripts/migrate_v5_bet_votes.py --dry-run
"""

import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from config import DATABASE_URL


DDL_STEPS = [
    ("1. Ajout des colonnes de vote sur bets", """
        ALTER TABLE {schema}.bets
            ADD COLUMN IF NOT EXISTS creator_vote VARCHAR(8) NULL;
        ALTER TABLE {schema}.bets
            ADD COLUMN IF NOT EXISTS opponent_vote VARCHAR(8) NULL;
    """),

    ("2. Contraintes CHECK sur les valeurs de vote", """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'bets_creator_vote_chk'
            ) THEN
                ALTER TABLE {schema}.bets
                    ADD CONSTRAINT bets_creator_vote_chk
                    CHECK (creator_vote IS NULL OR creator_vote IN ('yes','no','void'));
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'bets_opponent_vote_chk'
            ) THEN
                ALTER TABLE {schema}.bets
                    ADD CONSTRAINT bets_opponent_vote_chk
                    CHECK (opponent_vote IS NULL OR opponent_vote IN ('yes','no','void'));
            END IF;
        END$$;
    """),
]


def migrate_schema(engine, schema: str, dry_run: bool = False) -> None:
    print(f"\n{'='*64}")
    print(f"  Migration v5 — schema '{schema}'")
    print(f"{'='*64}")

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

    print(f"Migration v5 — Resolution amiable des paris")
    print(f"  Schemas : {schemas}")
    print(f"  Dry run : {dry_run}")

    engine = create_engine(DATABASE_URL, future=True)

    for schema in schemas:
        try:
            migrate_schema(engine, schema, dry_run=dry_run)
        except SQLAlchemyError as e:
            print(f"\n❌ Echec migration schema '{schema}' : {e}")
            sys.exit(1)

    print(f"\n{'='*64}")
    print(f"  Migration v5 terminee.")
    print(f"{'='*64}")


if __name__ == "__main__":
    main()
