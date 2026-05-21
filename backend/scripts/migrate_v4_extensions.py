"""
migrate_v4_extensions.py
─────────────────────────────────────────────────────────────────────
Migration v4 : ajoute les tables et colonnes pour les modules
  - Comptes systeme (account_type, system_role sur users)
  - RNG verifiable (rng_seeds)
  - Paris (bets)
  - Casino : coinflip (coinflip_rounds), roulette (roulette_spins)
  - Casino : poker (poker_tables, poker_sessions, poker_hands, poker_hand_holes)
  - Bourse du lait (milk_pools, milk_positions, milk_trades,
                    milk_chaos_events, milk_price_history)

Caracteristiques :
  - Idempotent : peut etre relance sans risque (CREATE IF NOT EXISTS,
    ADD COLUMN IF NOT EXISTS, etc.)
  - Multi-schemas : applique a 'test' ET 'prod' (ou au schema passe en arg)
  - Transactionnel par schema : si ca casse a mi-chemin sur prod, test
    reste deja migre

Usage :
  python scripts/migrate_v4_extensions.py            # test + prod
  python scripts/migrate_v4_extensions.py test       # test uniquement
  python scripts/migrate_v4_extensions.py prod       # prod uniquement
  python scripts/migrate_v4_extensions.py --dry-run  # affiche le SQL sans executer

NB : ce script ne touche pas a la blockchain. Pour creer les wallets
des comptes systeme (treasury existante deja en .env, plus
casino_bank, bets_escrow, poker_bank, milk_pool_*), lance ensuite :
  python scripts/seed_system_accounts.py
"""

import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Importe ta config existante. Adapte si la structure du repo differe.
from config import DATABASE_URL


# ─── DDL ────────────────────────────────────────────────────────────
#
# Toutes les requetes SQL sont parametrees par {schema}. Chaque bloc
# correspond a une etape logique. Les blocs sont idempotents.
#
# Convention : tout est NULL-able par defaut sauf raison metier.
# Tout les BIGINT sont en CAMP entiers (le contrat ERC-20 utilise
# 18 decimals mais on travaille en unites entieres cote DB pour eviter
# les soucis de float).
#
# Pour milk : reserve_milk en "milli-bouteilles" (x1000) pour eviter
# d'avoir besoin de float et avoir de la granularite. 1 bouteille = 1000.

DDL_STEPS = [
    # ─────────────────────────────────────────────────────────────────
    ("1. Extend users with account_type + system_role", """
        ALTER TABLE {schema}.users
            ADD COLUMN IF NOT EXISTS account_type VARCHAR(16) NOT NULL DEFAULT 'user';
        ALTER TABLE {schema}.users
            ADD COLUMN IF NOT EXISTS system_role VARCHAR(64) NULL;

        -- password_hash et email deviennent nullables pour les comptes systeme
        ALTER TABLE {schema}.users ALTER COLUMN password_hash DROP NOT NULL;
        ALTER TABLE {schema}.users ALTER COLUMN email DROP NOT NULL;

        CREATE INDEX IF NOT EXISTS idx_users_account_type
            ON {schema}.users(account_type);

        -- Unicite du role systeme (un seul casino_bank, un seul bets_escrow, ...)
        CREATE UNIQUE INDEX IF NOT EXISTS uq_users_system_role
            ON {schema}.users(system_role)
            WHERE system_role IS NOT NULL;
    """),

    # ─────────────────────────────────────────────────────────────────
    ("2. RNG seeds (commit-reveal pour provably fair)", """
        CREATE TABLE IF NOT EXISTS {schema}.rng_seeds (
            id           SERIAL PRIMARY KEY,
            purpose      VARCHAR(32) NOT NULL,
            ref_id       INTEGER NULL,
            seed_hash    VARCHAR(64) NOT NULL,
            seed_secret  VARCHAR(64) NOT NULL,
            revealed     BOOLEAN NOT NULL DEFAULT FALSE,
            client_seed  VARCHAR(128) NULL,
            created_at   TIMESTAMP NOT NULL DEFAULT NOW(),
            revealed_at  TIMESTAMP NULL
        );
        CREATE INDEX IF NOT EXISTS idx_rng_purpose_ref
            ON {schema}.rng_seeds(purpose, ref_id);
        CREATE INDEX IF NOT EXISTS idx_rng_unrevealed
            ON {schema}.rng_seeds(revealed, created_at)
            WHERE revealed = FALSE;
    """),

    # ─────────────────────────────────────────────────────────────────
    ("3. Bets (paris P2P avec arbitre optionnel)", """
        CREATE TABLE IF NOT EXISTS {schema}.bets (
            id                       SERIAL PRIMARY KEY,
            creator_username         VARCHAR(64) NOT NULL
                REFERENCES {schema}.users(username),
            statement                VARCHAR(512) NOT NULL,
            category                 VARCHAR(32) NULL,
            deadline                 TIMESTAMP NOT NULL,

            stake_creator            BIGINT NOT NULL,
            stake_opponent           BIGINT NOT NULL,
            odds_num                 INTEGER NOT NULL,
            odds_den                 INTEGER NOT NULL,
            creator_side             VARCHAR(8) NOT NULL,

            opponent_username        VARCHAR(64) NULL
                REFERENCES {schema}.users(username),
            arbiter_username         VARCHAR(64) NULL
                REFERENCES {schema}.users(username),
            arbiter_fee_pct          INTEGER NOT NULL DEFAULT 0,

            status                   VARCHAR(16) NOT NULL DEFAULT 'open',
            resolution               VARCHAR(8) NULL,
            resolved_at              TIMESTAMP NULL,
            resolved_by              VARCHAR(64) NULL,

            created_at               TIMESTAMP NOT NULL DEFAULT NOW(),
            matched_at               TIMESTAMP NULL,

            tx_hash_lock_creator     VARCHAR(66) NULL,
            tx_hash_lock_opponent    VARCHAR(66) NULL,
            tx_hash_payout_winner    VARCHAR(66) NULL,
            tx_hash_payout_arbiter   VARCHAR(66) NULL,

            CONSTRAINT bets_status_chk CHECK (
                status IN ('open','matched','resolved','cancelled','expired')
            ),
            CONSTRAINT bets_resolution_chk CHECK (
                resolution IS NULL OR resolution IN ('yes','no','void')
            ),
            CONSTRAINT bets_creator_side_chk CHECK (
                creator_side IN ('yes','no')
            ),
            CONSTRAINT bets_stake_positive_chk CHECK (
                stake_creator > 0 AND stake_opponent > 0
            ),
            CONSTRAINT bets_odds_positive_chk CHECK (
                odds_num > 0 AND odds_den > 0
            ),
            CONSTRAINT bets_arbiter_fee_chk CHECK (
                arbiter_fee_pct BETWEEN 0 AND 50
            )
        );
        CREATE INDEX IF NOT EXISTS idx_bets_status     ON {schema}.bets(status);
        CREATE INDEX IF NOT EXISTS idx_bets_creator    ON {schema}.bets(creator_username);
        CREATE INDEX IF NOT EXISTS idx_bets_opponent   ON {schema}.bets(opponent_username);
        CREATE INDEX IF NOT EXISTS idx_bets_arbiter    ON {schema}.bets(arbiter_username);
        CREATE INDEX IF NOT EXISTS idx_bets_deadline   ON {schema}.bets(deadline)
            WHERE status IN ('open','matched');
    """),

    # ─────────────────────────────────────────────────────────────────
    ("4. Coinflip rounds", """
        CREATE TABLE IF NOT EXISTS {schema}.coinflip_rounds (
            id              SERIAL PRIMARY KEY,
            username        VARCHAR(64) NOT NULL
                REFERENCES {schema}.users(username),
            bet_amount      BIGINT NOT NULL,
            choice          VARCHAR(8) NOT NULL,
            outcome         VARCHAR(8) NULL,
            win             BOOLEAN NULL,
            payout          BIGINT NOT NULL DEFAULT 0,

            client_seed     VARCHAR(128) NOT NULL,
            rng_seed_id     INTEGER NOT NULL
                REFERENCES {schema}.rng_seeds(id),

            status          VARCHAR(16) NOT NULL DEFAULT 'committed',
            ts              TIMESTAMP NOT NULL DEFAULT NOW(),
            settled_at      TIMESTAMP NULL,
            tx_hash_lock    VARCHAR(66) NULL,
            tx_hash_payout  VARCHAR(66) NULL,

            CONSTRAINT coinflip_choice_chk CHECK (choice IN ('heads','tails')),
            CONSTRAINT coinflip_outcome_chk CHECK (
                outcome IS NULL OR outcome IN ('heads','tails')
            ),
            CONSTRAINT coinflip_status_chk CHECK (
                status IN ('committed','settled','failed')
            ),
            CONSTRAINT coinflip_bet_positive CHECK (bet_amount > 0)
        );
        CREATE INDEX IF NOT EXISTS idx_coinflip_user_ts
            ON {schema}.coinflip_rounds(username, ts DESC);
    """),

    # ─────────────────────────────────────────────────────────────────
    ("5. Roulette spins", """
        CREATE TABLE IF NOT EXISTS {schema}.roulette_spins (
            id               SERIAL PRIMARY KEY,
            username         VARCHAR(64) NOT NULL
                REFERENCES {schema}.users(username),
            total_bet        BIGINT NOT NULL,
            total_payout     BIGINT NOT NULL DEFAULT 0,
            net_pnl          BIGINT NOT NULL DEFAULT 0,

            bets_json        TEXT NOT NULL,
            outcome_number   INTEGER NULL,
            outcome_color    VARCHAR(8) NULL,

            client_seed      VARCHAR(128) NOT NULL,
            rng_seed_id      INTEGER NOT NULL
                REFERENCES {schema}.rng_seeds(id),

            status           VARCHAR(16) NOT NULL DEFAULT 'settled',
            ts               TIMESTAMP NOT NULL DEFAULT NOW(),
            tx_hash_lock     VARCHAR(66) NULL,
            tx_hash_payout   VARCHAR(66) NULL,

            CONSTRAINT roulette_outcome_chk CHECK (
                outcome_number IS NULL
                OR (outcome_number BETWEEN 0 AND 36)
            ),
            CONSTRAINT roulette_color_chk CHECK (
                outcome_color IS NULL
                OR outcome_color IN ('red','black','green')
            ),
            CONSTRAINT roulette_status_chk CHECK (
                status IN ('committed','settled','failed')
            ),
            CONSTRAINT roulette_total_positive CHECK (total_bet > 0)
        );
        CREATE INDEX IF NOT EXISTS idx_roulette_user_ts
            ON {schema}.roulette_spins(username, ts DESC);
    """),

    # ─────────────────────────────────────────────────────────────────
    ("6. Poker tables", """
        CREATE TABLE IF NOT EXISTS {schema}.poker_tables (
            id            SERIAL PRIMARY KEY,
            name          VARCHAR(64) NOT NULL,
            blind_small   INTEGER NOT NULL,
            blind_big     INTEGER NOT NULL,
            min_buyin     INTEGER NOT NULL,
            max_buyin     INTEGER NOT NULL,
            max_players   INTEGER NOT NULL DEFAULT 6,
            status        VARCHAR(16) NOT NULL DEFAULT 'open',
            created_at    TIMESTAMP NOT NULL DEFAULT NOW(),

            CONSTRAINT poker_tables_status_chk CHECK (status IN ('open','closed')),
            CONSTRAINT poker_tables_blinds_chk CHECK (
                blind_small > 0 AND blind_big >= blind_small
            ),
            CONSTRAINT poker_tables_buyin_chk CHECK (
                min_buyin >= blind_big AND max_buyin >= min_buyin
            ),
            CONSTRAINT poker_tables_players_chk CHECK (
                max_players BETWEEN 2 AND 10
            )
        );
        CREATE INDEX IF NOT EXISTS idx_poker_tables_status
            ON {schema}.poker_tables(status);
    """),

    # ─────────────────────────────────────────────────────────────────
    ("7. Poker sessions (un siege occupe)", """
        CREATE TABLE IF NOT EXISTS {schema}.poker_sessions (
            id               SERIAL PRIMARY KEY,
            table_id         INTEGER NOT NULL
                REFERENCES {schema}.poker_tables(id),
            username         VARCHAR(64) NOT NULL
                REFERENCES {schema}.users(username),
            seat             INTEGER NOT NULL,
            stack            BIGINT NOT NULL,
            initial_stack    BIGINT NOT NULL,
            joined_at        TIMESTAMP NOT NULL DEFAULT NOW(),
            left_at          TIMESTAMP NULL,
            tx_hash_buyin    VARCHAR(66) NULL,
            tx_hash_cashout  VARCHAR(66) NULL,

            CONSTRAINT poker_sessions_seat_chk CHECK (seat >= 0),
            CONSTRAINT poker_sessions_stack_chk CHECK (
                stack >= 0 AND initial_stack > 0
            )
        );
        -- Un seul user actif par siege a la fois (left_at IS NULL).
        -- L'historique des sieges quittes (left_at IS NOT NULL) est conserve.
        CREATE UNIQUE INDEX IF NOT EXISTS uq_poker_active_seat
            ON {schema}.poker_sessions(table_id, seat)
            WHERE left_at IS NULL;
        CREATE UNIQUE INDEX IF NOT EXISTS uq_poker_active_user
            ON {schema}.poker_sessions(table_id, username)
            WHERE left_at IS NULL;
        CREATE INDEX IF NOT EXISTS idx_poker_sessions_user
            ON {schema}.poker_sessions(username, joined_at DESC);
    """),

    # ─────────────────────────────────────────────────────────────────
    ("8. Poker hands (chaque main jouee)", """
        CREATE TABLE IF NOT EXISTS {schema}.poker_hands (
            id            SERIAL PRIMARY KEY,
            table_id      INTEGER NOT NULL
                REFERENCES {schema}.poker_tables(id),
            hand_number   INTEGER NOT NULL,
            dealer_seat   INTEGER NOT NULL,
            board_cards   VARCHAR(20) NULL,
            pot           BIGINT NOT NULL DEFAULT 0,
            winners_json  TEXT NULL,
            hand_log      TEXT NOT NULL DEFAULT '[]',
            rng_seed_id   INTEGER NOT NULL
                REFERENCES {schema}.rng_seeds(id),
            started_at    TIMESTAMP NOT NULL DEFAULT NOW(),
            ended_at      TIMESTAMP NULL,

            CONSTRAINT poker_hands_unique_number UNIQUE (table_id, hand_number)
        );
        CREATE INDEX IF NOT EXISTS idx_poker_hands_table
            ON {schema}.poker_hands(table_id, hand_number DESC);
    """),

    # ─────────────────────────────────────────────────────────────────
    ("9. Poker hand holes (cartes privees)", """
        CREATE TABLE IF NOT EXISTS {schema}.poker_hand_holes (
            hand_id      INTEGER NOT NULL
                REFERENCES {schema}.poker_hands(id) ON DELETE CASCADE,
            username     VARCHAR(64) NOT NULL,
            hole_cards   VARCHAR(8) NOT NULL,
            PRIMARY KEY (hand_id, username)
        );
    """),

    # ─────────────────────────────────────────────────────────────────
    ("10. Milk pools (AMM x*y=k, un pool par produit laitier)", """
        CREATE TABLE IF NOT EXISTS {schema}.milk_pools (
            id              SERIAL PRIMARY KEY,
            symbol          VARCHAR(32) NOT NULL UNIQUE,
            name            VARCHAR(64) NOT NULL,
            system_role     VARCHAR(64) NOT NULL,  -- pointe vers users.system_role
            reserve_camp    BIGINT NOT NULL,
            reserve_milk    BIGINT NOT NULL,  -- en milli-bouteilles (1 bouteille = 1000)
            fee_pct         DOUBLE PRECISION NOT NULL DEFAULT 0.5,
            status          VARCHAR(16) NOT NULL DEFAULT 'active',
            initial_camp    BIGINT NOT NULL,
            initial_milk    BIGINT NOT NULL,
            chaos_enabled   BOOLEAN NOT NULL DEFAULT TRUE,
            created_at      TIMESTAMP NOT NULL DEFAULT NOW(),

            CONSTRAINT milk_pools_status_chk CHECK (status IN ('active','paused')),
            CONSTRAINT milk_pools_reserves_chk CHECK (
                reserve_camp > 0 AND reserve_milk > 0
            ),
            CONSTRAINT milk_pools_fee_chk CHECK (fee_pct >= 0 AND fee_pct <= 10)
        );
        CREATE INDEX IF NOT EXISTS idx_milk_pools_status
            ON {schema}.milk_pools(status);
    """),

    # ─────────────────────────────────────────────────────────────────
    ("11. Milk positions (stock de lait par user/pool)", """
        CREATE TABLE IF NOT EXISTS {schema}.milk_positions (
            username       VARCHAR(64) NOT NULL
                REFERENCES {schema}.users(username),
            pool_id        INTEGER NOT NULL
                REFERENCES {schema}.milk_pools(id),
            balance_milk   BIGINT NOT NULL DEFAULT 0,
            avg_cost       DOUBLE PRECISION NOT NULL DEFAULT 0,
            updated_at     TIMESTAMP NOT NULL DEFAULT NOW(),
            PRIMARY KEY (username, pool_id),

            CONSTRAINT milk_positions_balance_chk CHECK (balance_milk >= 0)
        );
    """),

    # ─────────────────────────────────────────────────────────────────
    ("12. Milk trades (historique des swaps)", """
        CREATE TABLE IF NOT EXISTS {schema}.milk_trades (
            id               SERIAL PRIMARY KEY,
            pool_id          INTEGER NOT NULL
                REFERENCES {schema}.milk_pools(id),
            username         VARCHAR(64) NOT NULL
                REFERENCES {schema}.users(username),
            side             VARCHAR(4) NOT NULL,
            amount_camp_in   BIGINT NOT NULL DEFAULT 0,
            amount_milk_in   BIGINT NOT NULL DEFAULT 0,
            amount_camp_out  BIGINT NOT NULL DEFAULT 0,
            amount_milk_out  BIGINT NOT NULL DEFAULT 0,
            fee              BIGINT NOT NULL DEFAULT 0,
            price_before     DOUBLE PRECISION NOT NULL,
            price_after      DOUBLE PRECISION NOT NULL,
            ts               TIMESTAMP NOT NULL DEFAULT NOW(),
            tx_hash          VARCHAR(66) NULL,

            CONSTRAINT milk_trades_side_chk CHECK (side IN ('buy','sell'))
        );
        CREATE INDEX IF NOT EXISTS idx_milk_trades_pool_ts
            ON {schema}.milk_trades(pool_id, ts DESC);
        CREATE INDEX IF NOT EXISTS idx_milk_trades_user_ts
            ON {schema}.milk_trades(username, ts DESC);
    """),

    # ─────────────────────────────────────────────────────────────────
    ("13. Milk chaos events (bot dieu)", """
        CREATE TABLE IF NOT EXISTS {schema}.milk_chaos_events (
            id                    SERIAL PRIMARY KEY,
            pool_id               INTEGER NOT NULL
                REFERENCES {schema}.milk_pools(id),
            kind                  VARCHAR(32) NOT NULL,
            delta_milk            BIGINT NOT NULL,
            reserve_milk_before   BIGINT NOT NULL,
            reserve_milk_after    BIGINT NOT NULL,
            price_before          DOUBLE PRECISION NOT NULL,
            price_after           DOUBLE PRECISION NOT NULL,
            narrative             VARCHAR(256) NULL,
            triggered_by          VARCHAR(16) NOT NULL,
            ts                    TIMESTAMP NOT NULL DEFAULT NOW(),

            CONSTRAINT milk_chaos_triggered_chk CHECK (
                triggered_by IN ('bot','admin')
            )
        );
        CREATE INDEX IF NOT EXISTS idx_milk_chaos_pool_ts
            ON {schema}.milk_chaos_events(pool_id, ts DESC);
    """),

    # ─────────────────────────────────────────────────────────────────
    ("14. Milk price history (snapshots horaires pour graphique)", """
        CREATE TABLE IF NOT EXISTS {schema}.milk_price_history (
            pool_id        INTEGER NOT NULL
                REFERENCES {schema}.milk_pools(id),
            ts             TIMESTAMP NOT NULL,
            price          DOUBLE PRECISION NOT NULL,
            reserve_camp   BIGINT NOT NULL,
            reserve_milk   BIGINT NOT NULL,
            PRIMARY KEY (pool_id, ts)
        );
    """),
]


# ─── Driver ─────────────────────────────────────────────────────────

def migrate_schema(engine, schema: str, dry_run: bool = False) -> None:
    """Execute toutes les etapes DDL sur un schema donne."""
    print(f"\n{'='*64}")
    print(f"  Migration schema : {schema}")
    print(f"{'='*64}")

    if dry_run:
        for label, sql in DDL_STEPS:
            print(f"\n--- {label} ---")
            print(sql.format(schema=schema))
        return

    with engine.begin() as conn:
        # On fixe le search_path pour que les CREATE INDEX puissent trouver
        # les tables sans qualification redondante.
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


def verify_schema(engine, schema: str) -> None:
    """Verifie que toutes les tables attendues existent."""
    expected_tables = [
        "users", "transactions", "market_orders", "nonces",  # deja existantes
        "rng_seeds", "bets", "coinflip_rounds", "roulette_spins",
        "poker_tables", "poker_sessions", "poker_hands", "poker_hand_holes",
        "milk_pools", "milk_positions", "milk_trades",
        "milk_chaos_events", "milk_price_history",
    ]
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = :schema
        """), {"schema": schema}).fetchall()
        present = {r[0] for r in rows}

    missing = [t for t in expected_tables if t not in present]
    extra = sorted(present - set(expected_tables))

    print(f"\n  Verification schema '{schema}':")
    print(f"    {len(expected_tables) - len(missing)}/{len(expected_tables)} tables attendues presentes")
    if missing:
        print(f"    ⚠ Manquantes : {missing}")
    if extra:
        print(f"    ℹ Supplementaires : {extra}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry_run = "--dry-run" in sys.argv

    if args:
        schemas = args
    else:
        schemas = ["test", "prod"]

    print(f"Migration v4 — Extensions CamplongCoin")
    print(f"  Database : {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else '(masked)'}")
    print(f"  Schemas  : {schemas}")
    print(f"  Dry run  : {dry_run}")

    engine = create_engine(DATABASE_URL, future=True)

    for schema in schemas:
        try:
            migrate_schema(engine, schema, dry_run=dry_run)
            if not dry_run:
                verify_schema(engine, schema)
        except SQLAlchemyError as e:
            print(f"\n❌ Echec migration schema '{schema}' : {e}")
            print(f"   Les schemas precedents ont ete commitees.")
            sys.exit(1)

    print(f"\n{'='*64}")
    print(f"  Migration v4 terminee.")
    print(f"{'='*64}")
    if not dry_run:
        print("\n  Prochaine etape :")
        print("    python scripts/seed_system_accounts.py")
        print("  pour creer les wallets Ethereum des comptes systeme")
        print("  (casino_bank, bets_escrow, poker_bank, milk_pool_*).")


if __name__ == "__main__":
    main()
