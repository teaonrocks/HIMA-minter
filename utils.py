from urllib.request import HTTPDefaultErrorHandler
import requests
from datetime import datetime
import os, random, json
import subprocess
import sqlite3
from colorama import init
from termcolor import colored

init()
CARDANO_CLI_PATH = "cardano-cli"


def get_current_slot():
    response = requests.get("https://api.koios.rest/api/v0/tip").json()
    slot = int(response[0]["abs_slot"])
    return slot


class Transaction:
    def __init__(
        self,
        addr: str,
        stake_id: str,
        hash: str,
        index: str,
        time: str,
        lovelace: int,
        assets: list,
        mint_amount: int = 0,
        sellable: bool = False,
        refundable: bool = False,
    ):
        self.addr = addr
        self.stake_id = stake_id
        self.hash = hash
        self.index = index
        self.time = time
        self.lovelace = lovelace
        self.assets = assets
        self.mint_amount = mint_amount
        self.sellable = sellable
        self.refundable = refundable


def build_refund_command(utxo: Transaction, outfile: str, output: int = 1500000):
    command = [CARDANO_CLI_PATH, "transaction", "build", "--alonzo-era", "--mainnet"]
    command.append("--tx-in")
    command.append(f"{utxo.hash}#{utxo.index}")
    command.append("--tx-out")
    txn_output = f"{utxo.addr}+{output}"
    for asset in utxo.assets:
        txn_output += (
            f"+ {asset['quantity']} {asset['policy_id']}.{asset['asset_name']}"
        )
    command.append(txn_output)
    command.append("--change-address")
    command.append(utxo.addr)
    command.append("--out-file")
    command.append(f"{outfile}/matx.raw")
    return command


def build_mint_command(
    policyid: str,
    utxo: Transaction,
    full_metadata: str,
    real_token_names: list,
    profit_addr: str,
    script: str,
    outfile: str,
    output: int = 1500000,
):
    hex_token_names = [
        real_token_name.encode("utf-8").hex() for real_token_name in real_token_names
    ]
    command_draft_txn = [
        CARDANO_CLI_PATH,
        "transaction",
        "build",
        "--mainnet",
        "--alonzo-era",
    ]
    txn_input = f"{utxo.hash}#{utxo.index}"
    command_draft_txn.append("--tx-in")
    command_draft_txn.append(txn_input)

    txn_output = f"{utxo.addr}+{output}"
    for token in hex_token_names:
        txn_output += f"+1 {policyid}.{token}"
    command_draft_txn.append("--tx-out")
    command_draft_txn.append(txn_output)

    command_draft_txn.append("--change-address")
    command_draft_txn.append(profit_addr)

    mint = "--mint="
    for index, token in enumerate(hex_token_names):
        if index == 0:
            mint += f"1 {policyid}.{token}"
        else:
            mint += f"+ 1 {policyid}.{token}"
    command_draft_txn.append(mint)

    command_draft_txn.append("--minting-script-file")
    command_draft_txn.append(script)

    command_draft_txn.append("--metadata-json-file")
    command_draft_txn.append(full_metadata)

    command_draft_txn.append("--invalid-hereafter")
    current_slot = get_current_slot()
    slot = current_slot + 10800  # Current slot + 3hrs
    command_draft_txn.append(str(slot))

    command_draft_txn.append("--witness-override")
    command_draft_txn.append("2")
    command_draft_txn.append("--out-file")
    command_draft_txn.append(f"{outfile}/matx.raw")

    return command_draft_txn


class Utils:
    def fetch_utxo(addr: str):
        print(colored(f"Fetching utxos from {addr}\n", "green"))
        # Get all UTxOs from address, using Koios API
        response = requests.get(
            f"https://api.koios.rest/api/v0/address_info?_address={addr}"
        ).json()[0]
        utxos = response["utxo_set"]
        # Get all txn hash from UTxOs
        hashes = [utxo["tx_hash"] for utxo in utxos]
        # Build json body for API request below
        body = {"_tx_hashes": hashes}
        # Get inputs and outputs of UTxO, using koios API
        address_response = requests.post(
            f"https://api.koios.rest/api/v0/tx_utxos",
            json=body,
            headers={"Content-type": "application/json"},
        ).json()
        # Grab address, txn hash, txn index, block time, lovelace and asset list from json response
        processed_utxos = []
        amount = 0
        for utxo, address in zip(utxos, address_response):
            for lovelace in address["outputs"]:
                if lovelace["payment_addr"]["bech32"] == addr:
                    amount = int(lovelace["value"])
            buyer_addr = address["inputs"][0]["payment_addr"]["bech32"]
            # Grab stake id from Koios API
            stake_response = requests.get(
                f"https://api.koios.rest/api/v0/address_info?_address={buyer_addr}"
            ).json()[0]["stake_address"]
            processed_utxos.append(
                Transaction(
                    addr=buyer_addr,
                    stake_id=stake_response,
                    hash=utxo["tx_hash"],
                    index=utxo["tx_index"],
                    time=utxo["block_time"],
                    lovelace=amount,
                    assets=utxo["asset_list"],
                )
            )
        # Return list of Transaction object
        return processed_utxos

    def check_utxo(utxo: Transaction, mint_price: int, whitelist: bool = False):
        # Check if UTxO is refundable
        if utxo.lovelace > 2000000:
            utxo.refundable = True
            # Check if UTxO has assets
            if len(utxo.assets) == 0:
                amount = int(utxo.lovelace / mint_price)
                if (
                    utxo.lovelace % mint_price == 0
                    and amount != 0
                    and amount <= 10
                    and amount  # Check if sold out
                    <= len(
                        os.listdir("/Users/archer/Documents/HIMA-dev/minter/metadata")
                    )
                ):
                    utxo.mint_amount = amount
                    utxo.sellable = True

        print(
            colored(
                f"""hash: {utxo.hash}#{utxo.index}\n
                addr: {utxo.addr}\n
                mint amount: {utxo.mint_amount}\n
                sellable: {utxo.sellable}\n
                refundable: {utxo.refundable}\n""",
                "blue",
            )
        )

    def sort_txn(txns: list):
        epoch_times = [
            datetime.strptime(txn.time, "%Y-%m-%dT%H:%M:%S").strftime(
                "%s"
            )  # Convert block time to Epoch time
            for txn in txns
        ]
        zipped = zip(epoch_times, txns)
        sorted_txns = [x for _, x in sorted(zipped)]  # Sort by epoch time

        print(colored(f"{len(txns)} transactions sorted.\n", "green"))
        return sorted_txns

    def generate_metadata(policyID: str, mint_amount: int, outfile_path: str):
        template_top = '{"721": {"' + policyID + '": {'
        template_bottom = "}}}"

        metadata_paths = []
        for x in range(mint_amount):
            # Get random metadata from "./metadata" folder
            metadata = random.choice(
                os.listdir("/Users/archer/Documents/HIMA-dev/minter/metadata")
            )
            # Check for dupe, reroll if dupe
            while f"metadata/{metadata}" in metadata_paths:
                metadata = random.choice(
                    os.listdir("/Users/archer/Documents/HIMA-dev/minter/metadata")
                )
            metadata_paths.append("metadata/" + metadata)
        # Get json string from chosen file
        metadatas = []
        for metadata_path in metadata_paths:
            with open(metadata_path) as metadata:
                metadatas.append(str(json.load(metadata))[1:-1])
        # Combine json strings
        joined_metadata = ",".join(metadatas)
        # Building final json string
        final_metadata_str = f"{template_top}{joined_metadata}{template_bottom}"
        # Write string to json file
        with open(outfile_path, "w") as outfile:
            outfile.write(final_metadata_str.replace("'", '"'))
        print(colored(f"Metadata generated.\nPath: {outfile_path}\n", "green"))
        # Return paths of chosen files
        return metadata_paths

    def build_refund_txn(
        utxo: Transaction,
        outfile: str,
    ):
        # Build refund command
        command = build_refund_command(utxo=utxo, outfile=outfile)
        # Run refund command to get correct fee
        draft_txn = subprocess.Popen(command, stdout=subprocess.PIPE)
        output, error = draft_txn.communicate()
        if error:
            print("Error: ", error)
        # Get fee from terminal output
        fee = str(output).split("Lovelace ", 1)[1].split("\\", 1)[0]
        fee = 1500000 + int(fee)
        # Build refund command with correct fees
        command = build_refund_command(utxo=utxo, outfile=outfile, output=fee)
        # Run refund command to build correct transaction file
        draft_txn = subprocess.Popen(command, stdout=subprocess.PIPE)
        output, error = draft_txn.communicate()
        if error:
            print("Error: ", error)
        print(colored("Final refund transaction file built\n", "green"))

    def build_mint_txn(
        policyid: str,
        utxo: Transaction,
        full_metadata: str,
        real_token_names: list,
        profit_addr: str,
        script: str,
        outfile: str,
    ):
        # Build mint command
        command = build_mint_command(
            policyid=policyid,
            utxo=utxo,
            full_metadata=full_metadata,
            real_token_names=real_token_names,
            profit_addr=profit_addr,
            script=script,
            outfile=outfile,
        )
        # Run mint command to get correct fee
        draft_txn = subprocess.Popen(command, stdout=subprocess.PIPE)
        output, error = draft_txn.communicate()
        if error:
            print("Error: ", error)
        # Get fee from terminal output
        fee = str(output).split("Lovelace ", 1)[1].split("\\", 1)[0]
        # Build mint command with correct fee
        command = build_mint_command(
            policyid=policyid,
            utxo=utxo,
            full_metadata=full_metadata,
            real_token_names=real_token_names,
            profit_addr=profit_addr,
            script=script,
            outfile=outfile,
            output=int(fee) + (utxo.mint_amount * 1500000),
        )
        # Run mint command to build correct transaction file
        draft_txn = subprocess.Popen(command, stdout=subprocess.PIPE)
        output, error = draft_txn.communicate()
        if error:
            print("Error: ", error)
        print(colored("Final mint transaction file built\n", "green"))

    def sign_txn(
        sellable: bool, policy_skey: str, payment_skey: str, bodyfile: str, outfile: str
    ):
        if sellable:
            command = [
                CARDANO_CLI_PATH,
                "transaction",
                "sign",
                "--signing-key-file",
                f"{payment_skey}",
                "--signing-key-file",
                f"{policy_skey}",
                "--mainnet",
                "--tx-body-file",
                f"{bodyfile}",
                "--out-file",
                f"{outfile}/matx.signed",
            ]
            sign_txn = subprocess.Popen(command, stdout=subprocess.PIPE)
            output, error = sign_txn.communicate()
            if error:
                print("Error: ", error)
            print(colored("Mint transaction signed\n", "green"))
        else:
            print("Signing refund txn")
            command = [
                CARDANO_CLI_PATH,
                "transaction",
                "sign",
                "--signing-key-file",
                f"{payment_skey}",
                "--mainnet",
                "--tx-body-file",
                f"{bodyfile}",
                "--out-file",
                f"{outfile}/matx.signed",
            ]
            sign_txn = subprocess.Popen(command, stdout=subprocess.PIPE)
            output, error = sign_txn.communicate()
            if error:
                print("Error: ", error)
            print(colored("Refund transaction signed\n", "green"))

    def submit_txn(bodyfile: str):
        print("submitting txn")
        command = [
            CARDANO_CLI_PATH,
            "transaction",
            "submit",
            "--tx-file",
            f"{bodyfile}",
            "--mainnet",
        ]
        submit = subprocess.Popen(command, stdout=subprocess.PIPE)
        output, error = submit.communicate()
        if error:
            print("Error: ", error)
            return False
        output = str(output)
        if (
            output.split("'", 1)[1].split(".", 1)[0]
            != "Transaction successfully submitted"
        ):
            return False
        print(colored("Transaction submitted\n", "green"))
        return True

    def create_db():
        db = sqlite3.connect("db.sqlite", isolation_level=None)
        cursor = db.cursor()
        cursor.execute("DROP TABLE IF EXISTS main")
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS main
            (
                stake_ID TEXT,
                discounts_available INTEGER DEFAULT 0,
                discount_minted INTEGER DEFAULT 0,
                whitelist_available INTEGER DEFAULT 0,
                whitelist_minted INTEGER DEFAULT 0
            )
        """
        )

    def snapshot(policyid: str):
        response = requests.get(
            f"https://api.koios.rest/api/v0/asset_policy_info?_asset_policy={policyid}"
        ).json()
        asset_names = []
        for assets in response:
            asset_names.append(assets["asset_name"])
        del asset_names[0]
        holder_addrs = []
        for index, name in enumerate(asset_names):
            holder_addr = requests.get(
                f"https://api.koios.rest/api/v0/asset_address_list?_asset_policy={policyid}&_asset_name={name}"
            ).json()[0]["payment_address"]
            holder_addrs.append(holder_addr)
            print(f"{index+1}/350: {holder_addr}")
        for index, holder_addr in enumerate(holder_addrs):
            if (
                holder_addr
                == "addr1w999n67e86jn6xal07pzxtrmqynspgx0fwmcmpua4wc6yzsxpljz3"
            ):
                print(colored("skipping JPG wallet", "blue"))
                continue
            stake_response = requests.get(
                f"https://api.koios.rest/api/v0/address_info?_address={holder_addr}"
            )
            while stake_response.status_code != 200:
                stake_response = requests.get(
                    f"https://api.koios.rest/api/v0/address_info?_address={holder_addr}"
                )
            stake_id = stake_response.json()[0]["stake_address"]
            if (
                stake_id
                == "stake1uxqh9rn76n8nynsnyvf4ulndjv0srcc8jtvumut3989cqmgjt49h6"
            ):
                print(colored("skipping JPG wallet", "blue"))
                continue
            print(f"{index+1}/350: {stake_id}")
            db = sqlite3.connect("db.sqlite", isolation_level=None)
            cursor = db.cursor()
            cursor.execute(
                f"""
                SELECT DISTINCT stake_ID
                FROM main
                WHERE stake_ID = "{stake_id}"
            """
            )
            if cursor.fetchone():
                cursor.execute(
                    f"""
                    UPDATE main
                    SET discounts_available = discounts_available + 3
                    WHERE stake_ID = "{stake_id}"
                    """
                )
            else:
                cursor.execute(
                    f"""
                    INSERT INTO main (stake_ID, discounts_available)
                    VALUES ("{stake_id}", 3);
                    """
                )
        print(colored(f"snapshot of {policyid} completed", "green"))
