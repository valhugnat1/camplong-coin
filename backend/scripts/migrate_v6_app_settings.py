"""
migrate_v6_app_settings.py
─────────────────────────────────────────────────────────────────────
Migration v6 : table generique app_settings (key/value) pour les
parametres modifiables a chaud depuis le backoffice.

Premier client : l'edge maison du coinflip (edge_pct, min_bet, max_bet).
A terme : autres parametres casino, parametres du bot lait, etc.

Caracteristiques :
  - Idempotent : peut etre relance sans risque (CREATE IF NOT EXISTS,
    ON CONFLICT DO NOTHING sur les seeds)
  - Multi-schemas : applique a 'test' ET 'prod' par defaut
  - Seed des valeurs par defaut a la creation (ne remplace pas l'existant)

Usage :
  python scripts/migrate_v6_app_settings.py            # test + prod
  python scripts/migrate_v6_app_settings.py test       # test uniquement
  python scripts/migrate_v6_app_settings.py prod       # prod uniquement
  python scripts/migrate_v6_app_settings.py --dry-run  # affiche le SQL
"""

import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from config import DATABASE_URL


DDL = """
    CREATE TABLE IF NOT EXISTS {schema}.app_settings (
        key          VARCHAR(64) PRIMARY KEY,
        value        VARCHAR(256) NOT NULL,
        description  TEXT NULL,
        updated_at   TIMESTAMP NOT NULL DEFAULT NOW()
    );
"""

# Valeurs par defaut. Inserees une seule fois ; l'admin peut les
# modifier ensuite depuis le backoffice sans toucher au code.
DEFAULT_SETTINGS = [
    (
        "coinflip_edge_pct",
        "2",
        "Edge maison sur le coinflip (en %). Payout gagnant = bet * 2 * (1 - edge/100).",
    ),
    (
        "coinflip_min_bet",
        "1",
        "Mise minimale autorisee sur un coinflip (en CAMP entiers).",
    ),
    (
        "coinflip_max_bet",
        "200",
        "Mise maximale autorisee sur un coinflip (en CAMP entiers).",
    ),
]


def migrate_schema(engine, schema: str, dry_run: bool = False) -> None:
    print(f"\n{'='*64}")
    print(f"  Migration schema : {schema}")
    print(f"{'='*64}")

    if dry_run:
        print("\n--- Table app_settings ---")
        print(DDL.format(schema=schema))
        print("\n--- Seeds ---")
        for k, v, d in DEFAULT_SETTINGS:
            print(f"  {k} = {v!r}  ({d})")
        return

    with engine.begin() as conn:
        conn.execute(text(f'SET search_path TO "{schema}", public'))

        print("  → Creation table app_settings ...", end=" ", flush=True)
        try:
            conn.execute(text(DDL.format(schema=schema)))
            print("ok")
        except SQLAlchemyError as e:
            print(f"FAIL\n     {e}")
            raise

        print("  → Seed valeurs par defaut ...")
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

    print("Migration v6 — app_settings (parametres dynamiques)")
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

    print(f"\n{'='*64}\n  Migration v6 terminee.\n{'='*64}")


if __name__ == "__main__":
    main()
