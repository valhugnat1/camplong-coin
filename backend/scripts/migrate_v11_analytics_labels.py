"""
migrate_v11_analytics_labels.py
─────────────────────────────────────────────────────────────────────
Migration v11 : table `analytics_tx_labels`.

Permet a l'admin de reclasser un mouvement de tresorerie pour le dashboard
/admin/stats : dire qu'un credit admin etait en fait la mise de depart d'un
joueur (donc pas une recharge), ou qu'une ligne doit etre ignoree.

SANS RISQUE POUR LES DONNEES EXISTANTES :
  - un seul CREATE TABLE IF NOT EXISTS, aucun ALTER / DROP / UPDATE
  - aucune table existante n'est touchee ; `transactions` reste le journal
    immuable des mouvements on-chain
  - le backend fonctionne AVANT que cette migration soit passee : il attrape
    l'erreur "table inexistante" et retombe sur la classification
    automatique (voir services/analytics.py::_labels)
  - rollback = DROP TABLE {schema}.analytics_tx_labels, on ne perd que les
    ajustements

Idempotent, multi-schemas.

⚠️ Rappel : la PROD tourne sur le schema `test`. Migrer les deux par defaut.

Usage :
    python scripts/migrate_v11_analytics_labels.py            # test + prod
    python scripts/migrate_v11_analytics_labels.py test       # un seul
    python scripts/migrate_v11_analytics_labels.py --dry-run
"""

import os
import sys

# Lance depuis backend/ (`python scripts/migrate_v11_analytics_labels.py`),
# c'est `scripts/` qui atterrit sur le sys.path, pas `backend/`. On ajoute le
# parent pour que `config` et le .env soient resolus.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text            # noqa: E402
from sqlalchemy.exc import SQLAlchemyError            # noqa: E402

from config import DATABASE_URL                       # noqa: E402


DDL = """
CREATE TABLE IF NOT EXISTS {schema}.analytics_tx_labels (
    tx_id       INTEGER PRIMARY KEY,
    label       VARCHAR(16) NOT NULL,
    note        VARCHAR(256) DEFAULT '',
    created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT analytics_label_chk CHECK (
        label IN ('onboarding','topup','withdrawal','ignore')
    )
);
"""

# Pas de FOREIGN KEY vers transactions a dessein : si une transaction etait un
# jour purgee, on ne veut pas que la suppression echoue a cause d'une etiquette
# de dashboard. Les orphelins sont ignores a la lecture (jointure par tx_id).

VERIFY = """
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = :schema AND table_name = 'analytics_tx_labels'
ORDER BY ordinal_position;
"""


def migrate_schema(engine, schema: str, dry_run: bool = False):
    print(f"\n── Schema '{schema}' ──")

    if dry_run:
        print(DDL.format(schema=schema))
        return

    with engine.begin() as conn:
        print("  → CREATE TABLE analytics_tx_labels ...", end=" ", flush=True)
        try:
            conn.execute(text(DDL.format(schema=schema)))
            print("ok")
        except SQLAlchemyError as e:
            print(f"FAIL\n     {e}")
            raise

        cols = conn.execute(text(VERIFY), {"schema": schema}).fetchall()
        print(f"  → colonnes : {', '.join(c[0] for c in cols)}")

        n = conn.execute(
            text(f"SELECT COUNT(*) FROM {schema}.analytics_tx_labels")
        ).scalar()
        print(f"  → {n} etiquette(s) existante(s) (conservees)")

    print(f"  Schema '{schema}' migre avec succes ✓")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry_run = "--dry-run" in sys.argv
    schemas = args if args else ["test", "prod"]

    print("Migration v11 — Analytics tx labels")
    print(f"  Schemas : {schemas}")
    print(f"  Dry run : {dry_run}")

    engine = create_engine(DATABASE_URL, future=True)
    for schema in schemas:
        try:
            migrate_schema(engine, schema, dry_run=dry_run)
        except SQLAlchemyError as e:
            print(f"\n❌ Echec schema '{schema}' : {e}")
            sys.exit(1)

    print("\nTermine. Aucune donnee existante n'a ete modifiee.")


if __name__ == "__main__":
    main()
