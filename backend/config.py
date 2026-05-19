import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]
DB_SCHEMA = os.environ.get("DB_SCHEMA", "test")

MASTER_KEY = os.environ["MASTER_KEY"].encode()
JWT_SECRET = os.environ["JWT_SECRET"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]

RPC_URL = os.environ["RPC_URL"]
CHAIN_ID = 84532  # Base Sepolia
CONTRACT_ADDRESS = os.environ["CONTRACT_ADDRESS"]
TREASURY_PRIVATE_KEY = os.environ["TREASURY_PRIVATE_KEY"]