from utils import Utils, Transaction
from dotenv import load_dotenv
import os

load_dotenv()
PAYMENT_ADDR = os.getenv("PAYMENT_ADDR")
worker = Utils
# Fetch
utxos = worker.fetch_utxo(PAYMENT_ADDR)
txns = []
# Check transctions
for utxo in utxos:
    txn = worker.check_utxo(utxo, 5000000)
    txns.append(txn)
# Sort transactions
txns = worker.sort_txn(txns)
worker.generate_metadata(mint_amount=2, policyID="test")
