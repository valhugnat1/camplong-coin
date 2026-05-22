"""
migrate_v7_slots.py
─────────────────────────────────────────────────────────────────────
Migration v7 : table slots_spins (machine a sous, 3 rouleaux,
single payline) + seed des nouvelles cles app_settings
(slots_min_bet / slots_max_bet).

Caracteristiques :
  - Idempotent : CREATE TABLE IF NOT EXISTS + INSERT ... ON CONFLICT
  - Multi-schemas (test + prod par defaut)
  - Ne touche pas a coinflip_rounds / roulette_spins / app_settings
    existants.

Usage :
  python scripts/migrate_v7_slots.py             # test + prod
  python scripts/migrate_v7_slots.py test        # test uniquement
  python scripts/migrate_v7_slots.py --dry-run   # affiche le SQL
"""

import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from config import DATABASE_URL


DDL = """
    CREATE TABLE IF NOT EXISTS {schema}.slots_spins (
        id              SERIAL PRIMARY KEY,
        username        VARCHAR(64) NOT NULL
            REFERENCES {schema}.users(username),
        bet_amount      BIGINT NOT NULL,
        payout          BIGINT NOT NULL DEFAULT 0,
        win             BOOLEAN NOT NULL DEFAULT FALSE,

        -- 3 symboles sortis sous forme '🍒|🍋|🍊' (un par rouleau, sep '|')
        reels           VARCHAR(32) NOT NULL,
        -- Code combo gagnant (ex '3xcherry') ou 'no_match' si perdu
        combo           VARCHAR(32) NOT NULL,
        -- Multiplicateur applique a la mise (ex 6 pour 3x cherry, 0 si perdu)
        multiplier      INTEGER NOT NULL DEFAULT 0,

        client_seed     VARCHAR(128) NOT NULL,
        rng_seed_id     INTEGER NOT NULL
            REFERENCES {schema}.rng_seeds(id),

        status          VARCHAR(16) NOT NULL DEFAULT 'settled',
        ts              TIMESTAMP NOT NULL DEFAULT NOW(),
        tx_hash_lock    VARCHAR(66) NULL,
        tx_hash_payout  VARCHAR(66) NULL,

        CONSTRAINT slots_status_chk CHECK (
            status IN ('committed','settled','failed')
        ),
        CONSTRAINT slots_bet_positive CHECK (bet_amount > 0)
    );
    CREATE INDEX IF NOT EXISTS idx_slots_user_ts
        ON {schema}.slots_spins(username, ts DESC);
"""

DEFAULT_SETTINGS = [
    (
        "slots_min_bet",
        "1",
        "Mise minimale autorisee sur un spin de machine a sous (en CAMP entiers).",
    ),
    (
        "slots_max_bet",
        "100",
        "Mise maximale autorisee sur un spin de machine a sous. Attention "
        "au plafond : un jackpot 7️⃣7️⃣7️⃣ paye 1000x → garder casino_bank "
        "capitalise en consequence.",
    ),
]


def migrate_schema(engine, schema: str, dry_run: bool = False) -> None:
    print(f"\n{'='*64}")
    print(f"  Migration schema : {schema}")
    print(f"{'='*64}")

    if dry_run:
        print("\n--- Table slots_spins ---")
        print(DDL.format(schema=schema))
        print("\n--- Seeds app_settings ---")
        for k, v, d in DEFAULT_SETTINGS:
            print(f"  {k} = {v!r}  ({d})")
        return

    with engine.begin() as conn:
        conn.execute(text(f'SET search_path TO "{schema}", public'))

        print("  → Creation table slots_spins ...", end=" ", flush=True)
        try:
            conn.execute(text(DDL.format(schema=schema)))
            print("ok")
        except SQLAlchemyError as e:
            print(f"FAIL\n     {e}")
            raise

        print("  → Seed des cles app_settings ...")
        for key, value, desc in DEFAULT_SETTINGS:
            existing = conn.execute(
                text(f'SELECT value FROM "{schema}".app_settings WHERE key = :k'),
                {"k": key},
            ).first()
            if existing:
                print(f"     • {key:30s} deja present (= {existing[0]})")
                continue
            conn.execute(
                text(
                    f'INSERT INTO "{schema}".app_settings (key, value, description) '
                    f"VALUES (:k, :v, :d)"
                ),
                {"k": key, "v": value, "d": desc},
            )
            print(f"     ✓ {key:30s} cree (= {value})")

    print(f"\n  Schema '{schema}' migre avec succes ✓")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry_run = "--dry-run" in sys.argv
    schemas = args if args else ["test", "prod"]

    print("Migration v7 — slots (machine a sous)")
    print(f"  Database : {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else '(masked)'}")
    print(f"  Schemas  : {schemas}")
    print(f"  Dry run  : {dry_run}")

    engine = create_engine(DATABASE_URL, future=True)

    for schema in schemas:
        try:
            migrate_schema(engine, schema, dry_run=dry_run)
        except SQLAlchemyError as e:
            print(f"\n❌ Echec migration schema '{schema}' : {e}")
            sys.exit(1)

    print(f"\n{'='*64}\n  Migration v7 terminee.\n{'='*64}")


if __name__ == "__main__":
    main()
