"""
seed_system_accounts.py
─────────────────────────────────────────────────────────────────────
Cree les comptes systeme requis par les modules d'extension v4, ET la
ligne metier associee quand il y en a une (cas du pool de lait).

Comptes crees :
  - casino_bank       : banque maison pour coinflip + roulette
  - bets_escrow       : escrow des paris en cours
  - poker_bank        : stacks des joueurs en cours de partie
  - milk_pool_lait_entier : SEUL pool cree d'office (LAIT-ENTIER).
                            Les autres pools se creent depuis le
                            backoffice via POST /admin/milk/pools.

Pour chaque compte :
  - Genere un wallet Ethereum (eth_account.Account.create())
  - Chiffre la cle privee avec MASTER_KEY (Fernet)
  - Insere dans users avec account_type='system' et system_role=<role>
  - PAS de mot de passe, PAS d'email (le compte n'est pas connectable)

Pour le pool de lait, en plus :
  - Insere la ligne milk_pools avec les reserves d'amorcage
  - Statut 'paused' jusqu'a ce que l'admin l'active

A lancer APRES migrate_v4_extensions.py.

Caracteristiques :
  - Idempotent : compte deja present → skip. Pool deja present → skip.
  - Multi-schemas : par defaut test + prod
  - Affiche les adresses creees a la fin (pour le monitoring)

Usage :
  python scripts/seed_system_accounts.py                  # test + prod
  python scripts/seed_system_accounts.py test             # test seulement
  python scripts/seed_system_accounts.py prod             # prod seulement
  python scripts/seed_system_accounts.py --dry-run        # affiche sans creer

⚠ APRES LE SEED ⚠
Les comptes/pools sont crees mais VIDES en CAMP. A faire depuis le
backoffice :
  - casino_bank          : crediter 50 000 CAMP depuis la treasury
                           (10x le max_bet recommande, absorbe la variance)
  - bets_escrow          : rien a faire (se remplit par les locks)
  - poker_bank           : rien a faire (se remplit par les buyins)
  - milk_pool_lait_entier :
      1. Crediter le wallet __pool_lait_entier__ de 10 000 CAMP depuis
         la treasury (= reserve_camp d'amorcage)
      2. Activer le pool (passer status de 'paused' a 'active') via
         le backoffice. Tant qu'il est en 'paused', les swaps sont
         bloques.
"""

import sys
from sqlalchemy import create_engine, text
from eth_account import Account

from config import DATABASE_URL
from security import fernet


# ─── Definition des comptes a creer ────────────────────────────────
#
# Deux listes distinctes :
#   - SIMPLE_SYSTEM_ACCOUNTS : juste un wallet, pas d'objet metier
#     additionnel (casino_bank, bets_escrow, poker_bank).
#   - INITIAL_MILK_POOLS : wallet + ligne dans milk_pools avec les
#     parametres economiques d'amorcage.
#
# Convention : prefixe __ sur le username pour bien distinguer des
# vrais users.

SIMPLE_SYSTEM_ACCOUNTS = [
    ("casino_bank", "__casino_bank__",
     "Banque maison pour coinflip + roulette"),
    ("bets_escrow", "__bets_escrow__",
     "Escrow des mises des paris en cours"),
    ("poker_bank",  "__poker_bank__",
     "Stacks des joueurs assis aux tables de poker"),
]

# Pools de lait crees a l'amorcage du systeme.
#
# UN SEUL pool par defaut : LAIT-ENTIER. Tous les autres produits laitiers
# se creeront a la volee depuis le backoffice (POST /admin/milk/pools),
# qui creera son compte systeme + sa ligne milk_pools en cascade.
#
# Constantes economiques :
#   - Prix d'amorcage : 50 CAMP / bouteille
#   - Reserve initiale : 200 bouteilles → 10 000 CAMP de profondeur
#   - 1 bouteille en DB = 1000 milli-bouteilles (pour granularite des swaps)
#   - Frais sur swap : 0.5%
#
# Le pool est cree en statut 'paused'. L'admin doit ensuite :
#   1. Crediter le wallet du pool de 10 000 CAMP depuis la treasury
#   2. Passer le pool en 'active' depuis le backoffice
INITIAL_MILK_POOLS = [
    {
        "system_role":      "milk_pool_lait_entier",
        "username":         "__pool_lait_entier__",
        "symbol":           "LAIT-ENTIER",
        "name":             "Lait Entier 1L UHT",
        "initial_bottles":  200,
        "price_per_bottle": 50,    # CAMP par bouteille a t=0
        "fee_pct":          0.5,
    },
]


# ─── Logique ────────────────────────────────────────────────────────

def existing_role(conn, schema: str, role: str) -> dict | None:
    """Retourne le compte existant pour ce role (s'il y en a un)."""
    row = conn.execute(text(f"""
        SELECT username, address FROM "{schema}".users
        WHERE account_type = 'system' AND system_role = :role
    """), {"role": role}).first()
    return {"username": row[0], "address": row[1]} if row else None


def insert_system_account(conn, schema: str,
                           username: str, role: str,
                           address: str, encrypted_pk: str) -> None:
    conn.execute(text(f"""
        INSERT INTO "{schema}".users
            (username, password_hash, address, encrypted_private_key,
             email, account_type, system_role, created_at)
        VALUES
            (:username, NULL, :address, :enc_pk,
             NULL, 'system', :role, NOW())
    """), {
        "username": username,
        "address": address,
        "enc_pk": encrypted_pk,
        "role": role,
    })


def existing_pool(conn, schema: str, symbol: str) -> dict | None:
    """Retourne le pool existant pour ce symbole (s'il y en a un)."""
    row = conn.execute(text(f"""
        SELECT id, symbol, status, reserve_camp, reserve_milk
        FROM "{schema}".milk_pools
        WHERE symbol = :symbol
    """), {"symbol": symbol}).first()
    if not row:
        return None
    return {
        "id": row[0], "symbol": row[1], "status": row[2],
        "reserve_camp": row[3], "reserve_milk": row[4],
    }


def insert_milk_pool(conn, schema: str, pool_def: dict) -> tuple[int, int, int]:
    """
    Cree la ligne milk_pools avec les reserves d'amorcage.
    Statut 'paused' par defaut.

    Retourne (pool_id, reserve_camp, reserve_milk).
    """
    # 1 bouteille = 1000 milli-bouteilles en DB (granularite)
    reserve_milk = pool_def["initial_bottles"] * 1000
    # CAMP necessaires pour que prix = price_per_bottle au demarrage
    # (prix = reserve_camp / reserve_milk_en_bouteilles
    #       = reserve_camp / pool_def["initial_bottles"]
    #       = price_per_bottle)
    reserve_camp = pool_def["initial_bottles"] * pool_def["price_per_bottle"]

    row = conn.execute(text(f"""
        INSERT INTO "{schema}".milk_pools (
            symbol, name, system_role,
            reserve_camp, reserve_milk,
            fee_pct, status,
            initial_camp, initial_milk,
            chaos_enabled, created_at
        ) VALUES (
            :symbol, :name, :role,
            :reserve_camp, :reserve_milk,
            :fee_pct, 'paused',
            :reserve_camp, :reserve_milk,
            TRUE, NOW()
        ) RETURNING id
    """), {
        "symbol": pool_def["symbol"],
        "name": pool_def["name"],
        "role": pool_def["system_role"],
        "reserve_camp": reserve_camp,
        "reserve_milk": reserve_milk,
        "fee_pct": pool_def["fee_pct"],
    }).first()
    return row[0], reserve_camp, reserve_milk


def create_wallet_for_role(conn, schema: str,
                            username: str, role: str) -> str:
    """Genere un wallet Ethereum, chiffre la cle, insere le compte systeme.
    Retourne l'adresse publique."""
    acct = Account.create()
    enc_pk = fernet.encrypt(acct.key.hex().encode()).decode()
    insert_system_account(conn, schema, username, role, acct.address, enc_pk)
    return acct.address


def seed_schema(engine, schema: str, dry_run: bool = False) -> list[dict]:
    """Cree les comptes systeme + pools manquants dans le schema."""
    print(f"\n{'='*64}")
    print(f"  Seed schema : {schema}")
    print(f"{'='*64}")
    results = []

    with engine.begin() as conn:
        conn.execute(text(f'SET search_path TO "{schema}", public'))

        # ─── 1. Comptes systeme simples ───────────────────────────
        print(f"\n  [Comptes systeme simples]")
        for role, username, desc in SIMPLE_SYSTEM_ACCOUNTS:
            existing = existing_role(conn, schema, role)
            if existing:
                print(f"  • [{role:30s}] deja present → {existing['address']}")
                results.append({**existing, "role": role, "status": "exists"})
                continue
            if dry_run:
                print(f"  • [{role:30s}] serait cree (dry-run)")
                results.append({"role": role, "status": "would-create"})
                continue

            address = create_wallet_for_role(conn, schema, username, role)
            print(f"  ✓ [{role:30s}] cree → {address}")
            print(f"      username = {username}")
            print(f"      desc     = {desc}")
            results.append({
                "role": role, "username": username,
                "address": address, "status": "created",
            })

        # ─── 2. Pools de lait initiaux ────────────────────────────
        print(f"\n  [Pools de lait initiaux]")
        for pool_def in INITIAL_MILK_POOLS:
            role = pool_def["system_role"]
            username = pool_def["username"]
            symbol = pool_def["symbol"]

            existing_acc = existing_role(conn, schema, role)
            existing_pool_row = existing_pool(conn, schema, symbol)

            # Cas 1 : compte + pool deja la → skip total
            if existing_acc and existing_pool_row:
                print(f"  • [{role:30s}] deja present → {existing_acc['address']}")
                print(f"      pool '{symbol}' id={existing_pool_row['id']} "
                      f"status={existing_pool_row['status']}")
                results.append({
                    **existing_acc, "role": role, "status": "exists",
                    "symbol": symbol, "pool_status": existing_pool_row["status"],
                })
                continue

            if dry_run:
                action = []
                if not existing_acc: action.append("wallet")
                if not existing_pool_row: action.append("pool row")
                print(f"  • [{role:30s}] creerait : {', '.join(action)} (dry-run)")
                results.append({"role": role, "status": "would-create"})
                continue

            # Cas 2 : wallet manquant → on le cree
            if not existing_acc:
                address = create_wallet_for_role(conn, schema, username, role)
            else:
                address = existing_acc["address"]

            # Cas 3 : ligne milk_pools manquante → on la cree
            if not existing_pool_row:
                pool_id, reserve_camp, reserve_milk = insert_milk_pool(
                    conn, schema, pool_def
                )
                bottles = pool_def["initial_bottles"]
                price = pool_def["price_per_bottle"]
                print(f"  ✓ [{role:30s}] cree → {address}")
                print(f"      pool symbol  = {symbol} (id={pool_id})")
                print(f"      reserves     = {reserve_camp} CAMP / "
                      f"{bottles} bouteilles ({reserve_milk} milli)")
                print(f"      prix initial = {price} CAMP/bouteille")
                print(f"      status       = paused (a activer apres credit)")
                results.append({
                    "role": role, "username": username,
                    "address": address, "status": "created",
                    "symbol": symbol, "pool_id": pool_id,
                    "amorcage_camp": reserve_camp,
                })

    return results


def print_summary(by_schema: dict[str, list[dict]]) -> None:
    print(f"\n{'='*64}")
    print(f"  RECAPITULATIF")
    print(f"{'='*64}\n")

    for schema, accounts in by_schema.items():
        print(f"  Schema '{schema}':")
        for acc in accounts:
            status = acc.get("status")
            symbol_info = f" [{acc['symbol']}]" if acc.get("symbol") else ""
            if status == "created":
                print(f"    NEW    [{acc['role']:30s}]{symbol_info} {acc.get('address','')}")
            elif status == "exists":
                print(f"    EXIST  [{acc['role']:30s}]{symbol_info} {acc.get('address','')}")
            else:
                print(f"    DRYRUN [{acc['role']:30s}]")
        print()

    # Lister les pools crees qui ont besoin d'etre actives
    pools_to_fund = []
    for schema, accounts in by_schema.items():
        for acc in accounts:
            if acc.get("status") == "created" and acc.get("symbol"):
                pools_to_fund.append((schema, acc))

    print("  ──────────────────────────────────────────────────────")
    print("  ETAPES SUIVANTES (depuis le backoffice)")
    print("  ──────────────────────────────────────────────────────")
    print()
    print("  1. Capitaliser la banque casino :")
    print("       Crediter __casino_bank__ avec ~50 000 CAMP depuis la treasury")
    print("       (10x le max_bet recommande, absorbe la variance)")
    print()
    if pools_to_fund:
        print("  2. Amorcer les pools de lait crees :")
        for schema, acc in pools_to_fund:
            print(f"     [{schema}] {acc['symbol']}")
            print(f"       a. Crediter {acc['username']} avec {acc['amorcage_camp']} CAMP")
            print(f"       b. Passer le pool en 'active' (PATCH /admin/milk/pools/{acc['pool_id']})")
        print()
    print("  3. (Optionnel) Verifier l'audit comptable :")
    print("       python scripts/audit.py")
    print("       Doit conclure : treasury + system + users = total supply")
    print()
    print("  bets_escrow et poker_bank se remplissent automatiquement")
    print("  par les flows metier — rien a faire dessus.")
    print("  ──────────────────────────────────────────────────────\n")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry_run = "--dry-run" in sys.argv

    if args:
        schemas = args
    else:
        schemas = ["test", "prod"]

    print(f"Seed system accounts — CamplongCoin v4")
    print(f"  Database : {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else '(masked)'}")
    print(f"  Schemas  : {schemas}")
    print(f"  Dry run  : {dry_run}")

    engine = create_engine(DATABASE_URL, future=True)

    by_schema = {}
    for schema in schemas:
        try:
            by_schema[schema] = seed_schema(engine, schema, dry_run=dry_run)
        except Exception as e:
            print(f"\n❌ Echec seed schema '{schema}' : {e}")
            sys.exit(1)

    print_summary(by_schema)


if __name__ == "__main__":
    main()
