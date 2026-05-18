"""
migrate_from_json.py - One-shot : migre users.json + transactions.log vers la DB.

A lancer apres init_db.py. Idempotent : skip ce qui est deja en DB.

Usage :
    DB_SCHEMA=test python migrate_from_json.py
"""
import json
import datetime

from database import SessionLocal, DB_SCHEMA
from models import User, Transaction


def migrate_users(db):
    try:
        with open("users.json") as f:
            users_data = json.load(f)
    except FileNotFoundError:
        print("  [skip] users.json absent, rien a migrer")
        return

    n_added = 0
    for username, u in users_data.items():
        if db.get(User, username):
            print(f"  [skip] user '{username}' deja en DB")
            continue
        db.add(User(
            username=username,
            password_hash=u["password_hash"],
            address=u["address"],
            encrypted_private_key=u["encrypted_private_key"],
        ))
        n_added += 1
    db.commit()
    print(f"  [ok] {n_added} user(s) migre(s)")


def migrate_transactions(db):
    try:
        f = open("transactions.log")
    except FileNotFoundError:
        print("  [skip] transactions.log absent, rien a migrer")
        return

    n_added = 0
    with f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            t = json.loads(line)

            existing = db.query(Transaction).filter_by(tx_hash=t["tx_hash"]).first()
            if existing:
                continue

            ts_str = t["ts"].rstrip("Z")
            ts = datetime.datetime.fromisoformat(ts_str)

            db.add(Transaction(
                ts=ts,
                from_username=t["from"],
                to_username=t["to"],
                amount=t["amount"],
                note=t.get("note", ""),
                tx_hash=t["tx_hash"],
            ))
            n_added += 1
    db.commit()
    print(f"  [ok] {n_added} transaction(s) migree(s)")


def main():
    print(f"Migration vers schema '{DB_SCHEMA}'")
    db = SessionLocal()
    try:
        migrate_users(db)
        migrate_transactions(db)
    finally:
        db.close()
    print("Fini.")


if __name__ == "__main__":
    main()