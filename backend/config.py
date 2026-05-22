import os
from dotenv import load_dotenv

load_dotenv()

# ─── DB ────────────────────────────────────────────────
DATABASE_URL = os.environ["DATABASE_URL"]
DB_SCHEMA = os.environ.get("DB_SCHEMA", "test")

# ─── Secrets ───────────────────────────────────────────
MASTER_KEY = os.environ["MASTER_KEY"].encode()
JWT_SECRET = os.environ["JWT_SECRET"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]

# ─── Blockchain ────────────────────────────────────────
RPC_URL = os.environ["RPC_URL"]
CHAIN_ID = 84532  # Base Sepolia
CONTRACT_ADDRESS = os.environ["CONTRACT_ADDRESS"]
TREASURY_PRIVATE_KEY = os.environ["TREASURY_PRIVATE_KEY"]

# ─── Email (notifs admin + users) ──────────────────────
# Tout est optionnel : si SMTP_HOST n'est pas defini, l'envoi est skip
# (l'app continue de fonctionner, juste sans emails).
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER)
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "hugo.philipp99@gmail.com")

# URL publique du front (pour les liens dans les emails)
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:8080")

# ─── Bets (paris communautaires) ───────────────────────
# Doit rester en sync avec frontend/src/config.js BETS.
BETS = {
    "min_stake": 1,
    "max_stake": 1000,
    "max_open_bets_per_user": 10,
    "min_options": 2,
    "max_options": 6,
}
