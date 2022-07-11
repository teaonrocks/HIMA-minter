import requests
from datetime import datetime
import os, random, json
from dotenv import load_dotenv
import subprocess

load_dotenv()
CARDANO_CLI_PATH = "cardano-cli"


def get_current_slot():
    response = requests.get("https://api.koios.rest/api/v0/tip").json()
    slot = int(response[0]["abs_slot"])
    return slot


class Transaction:
    def __init__(
        self,
        addr: str,
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
        print(f"Fetching utxos from {addr}")
        response = requests.get(
            f"https://api.koios.rest/api/v0/address_info?_address={addr}"
        ).json()[0]
        utxos = response["utxo_set"]
        hashes = []
        for utxo in utxos:
            hashes.append(utxo["tx_hash"])
        body = {"_tx_hashes": hashes}
        address_response = requests.post(
            f"https://api.koios.rest/api/v0/tx_utxos",
            json=body,
            headers={"Content-type": "application/json"},
        ).json()
        processed_utxos = []
        amount = 0
        for utxo, address in zip(utxos, address_response):
            for lovelace in address["outputs"]:
                if lovelace["payment_addr"]["bech32"] == addr:
                    amount = int(lovelace["value"])
            processed_utxos.append(
                Transaction(
                    addr=address["inputs"][0]["payment_addr"]["bech32"],
                    hash=utxo["tx_hash"],
                    index=utxo["tx_index"],
                    time=utxo["block_time"],
                    lovelace=amount,
                    assets=utxo["asset_list"],
                )
            )
        return processed_utxos

    def check_utxo(utxo, mint_price: int):
        if utxo.lovelace > 2000000:
            utxo.refundable = True
            if len(utxo.assets) == 0:
                if (
                    utxo.lovelace % mint_price == 0
                    and utxo.lovelace / mint_price != 0
                    and utxo.lovelace / mint_price <= 10
                ):
                    amount = int(utxo.lovelace / mint_price)
                    if amount <= len(
                        os.listdir("/Users/archer/Documents/HIMA-dev/minter/metadata")
                    ):
                        utxo.mint_amount = amount
                        utxo.sellable = True

        print(
            f"hash: {utxo.hash}#{utxo.index}\naddr: {utxo.addr}\nmint amount: {utxo.mint_amount}\nsellable: {utxo.sellable}\nrefundable: {utxo.refundable}"
        )

    def sort_txn(txns: list):
        epoch_times = []
        for txn in txns:
            time = datetime.strptime(txn.time, "%Y-%m-%dT%H:%M:%S")
            epoch_time = time.strftime("%s")
            epoch_times.append(epoch_time)
        zipped = zip(epoch_times, txns)
        sorted_txns = [x for _, x in sorted(zipped)]
        print(f"{len(txns)} transactions sorted.")
        return sorted_txns

    def generate_metadata(policyID: str, mint_amount: int, outfile_path: str):
        template_top = '{"721": {"' + policyID + '": {'
        template_bottom = "}}}"

        metadata_paths = []
        for x in range(mint_amount):
            metadata = random.choice(
                os.listdir("/Users/archer/Documents/HIMA-dev/minter/metadata")
            )
            while f"metadata/{metadata}" in metadata_paths:
                metadata = random.choice(
                    os.listdir("/Users/archer/Documents/HIMA-dev/minter/metadata")
                )
            metadata_paths.append("metadata/" + metadata)

        metadatas = []
        for metadata_path in metadata_paths:
            with open(metadata_path) as metadata:
                metadatas.append(str(json.load(metadata))[1:-1])
        joined_metadata = ",".join(metadatas)
        final_metadata_str = f"{template_top}{joined_metadata}{template_bottom}"
        with open(outfile_path, "w") as outfile:
            outfile.write(final_metadata_str.replace("'", '"'))
        print(f"Metadata generated.\npath: {outfile_path}")
        return metadata_paths

    def build_refund_txn(
        utxo: Transaction,
        outfile: str,
    ):
        command = build_refund_command(utxo=utxo, outfile=outfile)
        draft_txn = subprocess.Popen(command, stdout=subprocess.PIPE)
        output, error = draft_txn.communicate()
        if error:
            print("Error: ", error)
        fee = str(output).split("Lovelace ", 1)[1].split("\\", 1)[0]
        fee = 1500000 + int(fee)
        command = build_refund_command(utxo=utxo, outfile=outfile, output=fee)
        subprocess.Popen(command)

    def build_mint_txn(
        policyid: str,
        utxo: Transaction,
        full_metadata: str,
        real_token_names: list,
        profit_addr: str,
        script: str,
        outfile: str,
    ):
        command = build_mint_command(
            policyid=policyid,
            utxo=utxo,
            full_metadata=full_metadata,
            real_token_names=real_token_names,
            profit_addr=profit_addr,
            script=script,
            outfile=outfile,
        )
        draft_txn = subprocess.Popen(command, stdout=subprocess.PIPE)
        output, error = draft_txn.communicate()
        if error:
            print("Error: ", error)
        fee = (
            str(output).split("Lovelace ", 1)[1].split("\\", 1)[0]
        )  # Get fee from terminal output
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
        subprocess.Popen(command)

    def sign_txn(
        sellable: bool, policy_skey: str, payment_skey: str, bodyfile: str, outfile: str
    ):
        if sellable:
            print("Signing mint txn")
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
            subprocess.run(command)
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
            subprocess.run(command)

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
        return True

    def snapshot(policyid: str):
        response = requests.get(
            f"https://api.koios.rest/api/v0/asset_policy_info?_asset_policy={policyid}"
        ).json()
        asset_names = []
        for assets in response:
            asset_names.append(assets["asset_name"])
        del asset_names[0]
        holders = []
        for name in asset_names:
            holder_res = requests.get(
                f"https://api.koios.rest/api/v0/asset_address_list?_asset_policy={policyid}&_asset_name={name}"
            ).json()
            holders.append(holder_res[0])
        with open("./snapshot.json", "w") as outfile:
            outfile.write(json.dumps(holders))
        print(f"snapshot of {policyid} completed")
