"""
init_db.py - Cree les 2 schemas (test, prod) puis cree les tables
dans le schema configure dans .env (DB_SCHEMA).

Affiche aussi un diagnostic en fin de course pour confirmer ou les
tables ont reellement ete creees.

Usage :
  DB_SCHEMA=test python init_db.py
  DB_SCHEMA=prod python init_db.py
"""
from sqlalchemy import text
from database import engine, Base, DB_SCHEMA
import models  # noqa: F401  -> enregistre les modeles dans Base.metadata


def main():
    print(f"=== Init DB (schema actif : {DB_SCHEMA}) ===\n")

    # 1. Creer les 2 schemas s'ils n'existent pas
    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS test"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS prod"))
        conn.commit()
    print("[ok] schemas 'test' et 'prod' presents")

    # 2. Creer les tables (le schema est dans __table_args__ des modeles)
    Base.metadata.create_all(engine)
    print(f"[ok] create_all() execute")

    # 3. Diagnostic : ou sont vraiment les tables ?
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_name IN ('users', 'transactions', 'nonces')
            ORDER BY table_schema, table_name
        """)).all()

    print("\n--- Diagnostic : tables existantes ---")
    if not rows:
        print("  AUCUNE table trouvee. Probleme de permissions ?")
        print("  Verifie que ton user Scaleway a 'CREATE' sur le schema.")
    else:
        for schema, name in rows:
            marker = " <-- schema actif" if schema == DB_SCHEMA else ""
            print(f"  {schema}.{name}{marker}")

    print("\nProchaines etapes :")
    print("  - python migrate_from_json.py   (si users.json existe)")
    print("  - python setup_users.py         (pour creer de nouveaux users)")


if __name__ == "__main__":
    main()