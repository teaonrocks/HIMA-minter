from utils import Utils, updateDB
from dotenv import load_dotenv
import os
import shutil

load_dotenv()
PAYMENT_ADDR = os.getenv("PAYMENT_ADDR")
POLICY_ID = os.getenv("POLICY_ID")
HALLPASS_POLICY_ID = os.getenv("HALLPASS_POLICY_ID")
PROFIT_ADDR = os.getenv("PROFIT_ADDR")
ROOT_PATH = os.getenv("ROOT_PATH")
TXN_FILE_PATH = f"{ROOT_PATH}/transactions"
TEMP_METADATA_PATH = f"{ROOT_PATH}/temp/temp.json"
POLICY_SCRIPT_PATH = f"{ROOT_PATH}/policy/policy.script"
PAYMENT_SKEY = f"{ROOT_PATH}/keys/payment.skey"
POLICY_SKEY = f"{ROOT_PATH}/policy/policy.skey"
worker = Utils

# Create DB
# worker.create_db()

# Snapshot holders of hallpass
# worker.snapshot(HALLPASS_POLICY_ID)

# Fetch transactions
utxos = worker.fetch_utxo(PAYMENT_ADDR)

# Check transctions
for utxo in utxos:
    worker.check_utxo(
        utxo=utxo, mint_price=5000000, whitelist=True, discount_price=4000000
    )

# Sort transactions by time received
sorted_utxos = worker.sort_txn(txns=utxos)

for utxo in utxos:
    # generate metadata
    if utxo.sellable:
        metadata_paths = worker.generate_metadata(
            mint_amount=utxo.mint_amount,
            policyID=f"{POLICY_ID}",
            outfile_path=TEMP_METADATA_PATH,
        )
        real_token_names = [
            tokens.split("/", 1)[1].split(".")[0]
            for tokens in metadata_paths  # Getting file name from path
        ]

        # Build mint transaction
        worker.build_mint_txn(
            policyid=POLICY_ID,
            utxo=utxo,
            full_metadata=TEMP_METADATA_PATH,
            real_token_names=real_token_names,
            profit_addr=PROFIT_ADDR,
            script=POLICY_SCRIPT_PATH,
            outfile=TXN_FILE_PATH,
        )
    else:
        worker.build_refund_txn(utxo=utxo, outfile=TXN_FILE_PATH)

    # Sign transaction
    worker.sign_txn(
        sellable=utxo.sellable,
        policy_skey=POLICY_SKEY,
        payment_skey=PAYMENT_SKEY,
        bodyfile=f"{TXN_FILE_PATH}/matx.raw",
        outfile=TXN_FILE_PATH,
    )

    # Submit transaction
    submitted = worker.submit_txn(bodyfile=f"{TXN_FILE_PATH}/matx.signed")
    if submitted:
        if utxo.sellable:
            updateDB(stake_id=utxo.stake_id, col_name="discount_minted", col_value=1)
            for metadata in metadata_paths:
                filename = metadata.split("/", 1)[1]
                shutil.move(f"./{metadata}", f"./minted/{filename}")
