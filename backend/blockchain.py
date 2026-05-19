import json
from web3 import Web3
from eth_account import Account
from sqlalchemy.orm import Session
from fastapi import HTTPException

from config import RPC_URL, CONTRACT_ADDRESS, TREASURY_PRIVATE_KEY, CHAIN_ID
from models import Nonce

w3 = Web3(Web3.HTTPProvider(RPC_URL))
treasury = Account.from_key(TREASURY_PRIVATE_KEY)

ERC20_ABI = json.loads("""[
  {"constant":true,"inputs":[{"name":"_owner","type":"address"}],
   "name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"},
  {"constant":false,"inputs":[{"name":"_to","type":"address"},{"name":"_value","type":"uint256"}],
   "name":"transfer","outputs":[{"name":"","type":"bool"}],"type":"function"},
  {"constant":false,"inputs":[
     {"name":"from","type":"address"},
     {"name":"to","type":"address"},
     {"name":"amount","type":"uint256"}],
   "name":"adminTransfer","outputs":[],"type":"function"}
]""")

contract = w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=ERC20_ABI)

def reserve_next_nonce(db: Session, address: str) -> int:
    row = db.query(Nonce).filter_by(address=address).with_for_update().first()
    chain_nonce = w3.eth.get_transaction_count(address, "pending")

    if row is None:
        nonce_to_use = chain_nonce
        row = Nonce(address=address, next_nonce=nonce_to_use + 1)
        db.add(row)
        db.flush()
    else:
        nonce_to_use = max(row.next_nonce, chain_nonce)
        row.next_nonce = nonce_to_use + 1
    return nonce_to_use

def admin_transfer(db: Session, from_addr: str, to_addr: str, amount_camp: int) -> str:
    nonce = reserve_next_nonce(db, treasury.address)
    tx = contract.functions.adminTransfer(
        Web3.to_checksum_address(from_addr),
        Web3.to_checksum_address(to_addr),
        amount_camp * 10**18,
    ).build_transaction({
        "from": treasury.address,
        "nonce": nonce,
        "chainId": CHAIN_ID,
        "gas": 100_000,
        "maxFeePerGas": w3.to_wei(0.1, "gwei"),
        "maxPriorityFeePerGas": w3.to_wei(0.01, "gwei"),
    })
    signed = treasury.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction).hex()
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
    if receipt.status != 1:
        raise HTTPException(500, "adminTransfer a echoue on-chain")
    return tx_hash

def get_balance_camp(address: str) -> int:
    return contract.functions.balanceOf(address).call() // 10**18

def get_balance_eth(address: str) -> float:
    return float(w3.from_wei(w3.eth.get_balance(address), "ether"))