"""
migrate_v8_bets_v2.py
─────────────────────────────────────────────────────────────────────
Migration v8 : refonte complete des paris.

L'ancien modele 1v1 (creator/opponent + cote odds_num:odds_den + creator_side
yes/no) est remplace par un modele communautaire :
  - Mise unique fixe (bet.stake) que tous les participants posent.
  - 2 options yes/no OU 2 a 6 options custom (multi_choice).
  - N'importe qui peut rejoindre une option, 1 mise par user par pari.
  - Resolution par arbitre designe, 2 votes communautaires concordants
    (n'importe quel user, 1 vote/pari), ou admin.

WIPE COMPLET : toutes les lignes de l'ancienne table bets sont supprimees.
Les paris non resolus (open/matched) doivent etre refundes manuellement
AVANT de lancer cette migration. Le script imprime la liste pour rappel.

Tables creees :
  - bet_options        : id, bet_id, label, position
  - bet_participations : id, bet_id, option_id, username, amount, tx_hash_*,
                         joined_at  (UNIQUE bet_id+username)
  - bet_votes          : id, bet_id, voter_username, option_id NULL=void,
                         voted_at   (UNIQUE bet_id+voter_username)

La table bets est recreee avec son nouveau schema (drop & create).

Idempotent : peut etre relance sans risque (DROP IF EXISTS + CREATE IF NOT EXISTS).
Multi-schemas : applique a 'test' ET 'prod' (ou au schema passe en arg).

Usage :
  python scripts/migrate_v8_bets_v2.py            # test + prod
  python scripts/migrate_v8_bets_v2.py test       # test uniquement
  python scripts/migrate_v8_bets_v2.py prod
  python scripts/migrate_v8_bets_v2.py --dry-run
"""

import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from config import DATABASE_URL


# ─── Etape 0 : audit des paris a refunder a la main ─────────────────

def audit_pending_bets(engine, schema: str) -> None:
    """Affiche les paris encore ouverts pour qu'Hugo refund avant le wipe."""
    print(f"\n  Audit schema '{schema}' — paris a refunder avant le wipe :")
    try:
        with engine.connect() as conn:
            conn.execute(text(f'SET search_path TO "{schema}", public'))
            # On query l'ancienne table (peut ne pas exister si fresh DB)
            rows = conn.execute(text(f"""
                SELECT id, creator_username, opponent_username, status,
                       stake_creator, stake_opponent
                  FROM {schema}.bets
                 WHERE status IN ('open', 'matched')
                 ORDER BY id
            """)).fetchall()
    except SQLAlchemyError:
        print("    (ancienne table bets absente ou incompatible, rien a auditer)")
        return

    if not rows:
        print("    aucun pari open/matched a refunder.")
        return

    print("    ⚠ Les paris suivants doivent etre refundes A LA MAIN avant le wipe :")
    for r in rows:
        bet_id, cu, ou, st, sc, so = r
        if st == "open":
            print(
                f"      #{bet_id} open : refund {cu} = {sc} CAMP depuis bets_escrow"
            )
        else:  # matched
            print(
                f"      #{bet_id} matched : refund {cu} = {sc} CAMP + "
                f"{ou} = {so} CAMP depuis bets_escrow"
            )
    print("    Annule (Ctrl+C) si tu n'as pas encore traite. Sinon ils seront")
    print("    perdus en DB mais les CAMP resteront bloques dans bets_escrow.")


# ─── DDL ────────────────────────────────────────────────────────────

DDL_STEPS = [
    # ─────────────────────────────────────────────────────────────────
    ("1. DROP des tables paris v1 (sera recree)", """
        DROP TABLE IF EXISTS {schema}.bet_votes CASCADE;
        DROP TABLE IF EXISTS {schema}.bet_participations CASCADE;
        DROP TABLE IF EXISTS {schema}.bet_options CASCADE;
        DROP TABLE IF EXISTS {schema}.bets CASCADE;
    """),

    # ─────────────────────────────────────────────────────────────────
    ("2. Bets (nouveau schema communautaire)", """
        CREATE TABLE {schema}.bets (
            id                    SERIAL PRIMARY KEY,
            creator_username      VARCHAR(64) NOT NULL
                REFERENCES {schema}.users(username),
            statement             VARCHAR(512) NOT NULL,
            deadline              TIMESTAMP NOT NULL,

            type                  VARCHAR(16) NOT NULL DEFAULT 'yes_no',
            stake                 BIGINT NOT NULL,

            arbiter_username      VARCHAR(64) NULL
                REFERENCES {schema}.users(username),

            status                VARCHAR(16) NOT NULL DEFAULT 'open',
            resolution_option_id  INTEGER NULL,
            resolution_void       BOOLEAN NOT NULL DEFAULT FALSE,
            resolved_at           TIMESTAMP NULL,
            resolved_by           VARCHAR(64) NULL,

            created_at            TIMESTAMP NOT NULL DEFAULT NOW(),

            CONSTRAINT bets_status_chk CHECK (
                status IN ('open','resolved','cancelled','expired')
            ),
            CONSTRAINT bets_type_chk CHECK (
                type IN ('yes_no','multi_choice')
            ),
            CONSTRAINT bets_stake_positive_chk CHECK (stake > 0)
        );
        CREATE INDEX idx_bets_status   ON {schema}.bets(status);
        CREATE INDEX idx_bets_creator  ON {schema}.bets(creator_username);
        CREATE INDEX idx_bets_arbiter  ON {schema}.bets(arbiter_username);
        CREATE INDEX idx_bets_deadline ON {schema}.bets(deadline)
            WHERE status = 'open';
    """),

    # ─────────────────────────────────────────────────────────────────
    ("3. Bet options (2 a 6 par pari)", """
        CREATE TABLE {schema}.bet_options (
            id        SERIAL PRIMARY KEY,
            bet_id    INTEGER NOT NULL
                REFERENCES {schema}.bets(id) ON DELETE CASCADE,
            label     VARCHAR(64) NOT NULL,
            position  INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX idx_bet_options_bet ON {schema}.bet_options(bet_id);
    """),

    # ─────────────────────────────────────────────────────────────────
    ("4. Bet participations (mises sur une option)", """
        CREATE TABLE {schema}.bet_participations (
            id              SERIAL PRIMARY KEY,
            bet_id          INTEGER NOT NULL
                REFERENCES {schema}.bets(id) ON DELETE CASCADE,
            option_id       INTEGER NOT NULL
                REFERENCES {schema}.bet_options(id),
            username        VARCHAR(64) NOT NULL
                REFERENCES {schema}.users(username),
            amount          BIGINT NOT NULL,
            tx_hash_lock    VARCHAR(66) NULL,
            tx_hash_payout  VARCHAR(66) NULL,
            joined_at       TIMESTAMP NOT NULL DEFAULT NOW(),

            CONSTRAINT bet_participations_amount_chk CHECK (amount > 0),
            CONSTRAINT bet_participations_unique UNIQUE (bet_id, username)
        );
        CREATE INDEX idx_bet_part_bet    ON {schema}.bet_participations(bet_id);
        CREATE INDEX idx_bet_part_option ON {schema}.bet_participations(option_id);
        CREATE INDEX idx_bet_part_user   ON {schema}.bet_participations(username);
    """),

    # ─────────────────────────────────────────────────────────────────
    ("5. Bet votes (resolution communautaire)", """
        CREATE TABLE {schema}.bet_votes (
            id              SERIAL PRIMARY KEY,
            bet_id          INTEGER NOT NULL
                REFERENCES {schema}.bets(id) ON DELETE CASCADE,
            voter_username  VARCHAR(64) NOT NULL
                REFERENCES {schema}.users(username),
            option_id       INTEGER NULL
                REFERENCES {schema}.bet_options(id),
            voted_at        TIMESTAMP NOT NULL DEFAULT NOW(),

            CONSTRAINT bet_votes_unique UNIQUE (bet_id, voter_username)
        );
        CREATE INDEX idx_bet_votes_bet ON {schema}.bet_votes(bet_id);
    """),
]


# ─── Driver ─────────────────────────────────────────────────────────

def migrate_schema(engine, schema: str, dry_run: bool = False) -> None:
    print(f"\n{'='*64}")
    print(f"  Migration v8 — schema '{schema}'")
    print(f"{'='*64}")

    if not dry_run:
        audit_pending_bets(engine, schema)

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

    print(f"Migration v8 — Refonte des paris (mises fixes + multi-options)")
    print(f"  Schemas : {schemas}")
    print(f"  Dry run : {dry_run}")
    print(f"\n  ⚠ Cette migration DROP la table bets actuelle.")
    print(f"     Les paris open/matched seront listes pour rappel,")
    print(f"     mais les CAMP locked dans bets_escrow resteront on-chain.")

    engine = create_engine(DATABASE_URL, future=True)

    for schema in schemas:
        try:
            migrate_schema(engine, schema, dry_run=dry_run)
        except SQLAlchemyError as e:
            print(f"\n❌ Echec migration schema '{schema}' : {e}")
            sys.exit(1)

    print(f"\n{'='*64}")
    print(f"  Migration v8 terminee.")
    print(f"{'='*64}")


if __name__ == "__main__":
    main()
