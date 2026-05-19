"""
setup_users.py - Cree de nouveaux users directement en DB.

Usage :
    DB_SCHEMA=test python setup_users.py
    DB_SCHEMA=prod python setup_users.py

Idempotent : si un user existe deja en DB (meme username), il est skip.
"""
import os
import getpass

from dotenv import load_dotenv
from eth_account import Account
from cryptography.fernet import Fernet
import bcrypt

from database import SessionLocal, DB_SCHEMA
from models import User


# Liste des pseudos a creer (edite ici pour ajouter / changer)
USERS_TO_CREATE = ["Hugo", "Alice"]


def main():
    print(f"=== Setup CamplongCoin users (schema : {DB_SCHEMA}) ===\n")

    load_dotenv()

    if "MASTER_KEY" not in os.environ or not os.environ["MASTER_KEY"]:
        # Premier lancement : on en genere une
        new_key = Fernet.generate_key().decode()
        print("Aucune MASTER_KEY dans .env. En voici une fraiche :")
        print(f"  {new_key}\n")
        print("  -> COLLE-LA dans backend/.env (MASTER_KEY=...) AVANT de continuer.")
        print("  -> puis relance ce script.\n")
        return

    f = Fernet(os.environ["MASTER_KEY"].encode())
    db = SessionLocal()

    try:
        for username in USERS_TO_CREATE:
            if db.get(User, username):
                print(f"  [skip] user '{username}' existe deja en DB")
                continue

            print(f"--- {username} ---")
            acct = Account.create()
            enc_pk = f.encrypt(acct.key.hex().encode()).decode()

            pwd = getpass.getpass(f"  Mot de passe pour {username} : ")
            pwd_hash = bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()

            db.add(User(
                username=username,
                password_hash=pwd_hash,
                address=acct.address,
                encrypted_private_key=enc_pk,
            ))
            print(f"  -> address: {acct.address}\n")

        db.commit()
    finally:
        db.close()

    print("OK. Prochaines etapes :")
    print("  1. Funder chaque adresse avec ~0.01 ETH Sepolia (depuis MetaMask)")
    print("  2. Envoyer des CAMP a chaque adresse (depuis Remix)")


if __name__ == "__main__":
    main()