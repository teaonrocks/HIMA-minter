from utils import Utils
from dotenv import load_dotenv
import os

load_dotenv()
PAYMENT_ADDR = os.getenv("PAYMENT_ADDR")
POLICY_ID = os.getenv("POLICY_ID")
HALLPASS_POLICY_ID = os.getenv("HALLPASS_POLICY_ID")
worker = Utils

# Fetch transactions
utxos = worker.fetch_utxo(PAYMENT_ADDR)
# Check transctions
for utxo in utxos:
    worker.check_utxo(utxo, 5000000)

# Sort transactions by time received
sorted_utxos = worker.sort_txn(utxos)

for utxo in utxos:
    # generate metadata
    worker.generate_metadata(mint_amount=utxo.mint_amount, policyID=f"{POLICY_ID}")
    print(f"Generating metadata for {utxo.addr}")

# Snapshot holders of hallpass
# worker.snapshot(HALLPASS_POLICY_ID)
