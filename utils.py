import requests
from datetime import datetime
import os, random, json


class Transaction:
    def __init__(
        self,
        addr: str,
        hash: str,
        index: int,
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


class Utils:
    def fetch_utxo(addr: str):
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
                else:
                    utxo.sellable = False
            else:
                utxo.sellable = False
        else:
            utxo.sellable = False
            utxo.refundable = False

    def sort_txn(txns: list):
        epoch_times = []
        for txn in txns:
            time = datetime.strptime(txn.time, "%Y-%m-%dT%H:%M:%S")
            epoch_time = time.strftime("%s")
            epoch_times.append(epoch_time)
        zipped = zip(epoch_times, txns)
        sorted_txns = [x for _, x in sorted(zipped)]
        return sorted_txns

    def generate_metadata(policyID: str, mint_amount: int):
        template_top = '{"721": {"' + policyID + '": {'
        template_bottom = "}}}"
        metadata_paths = []
        for x in range(mint_amount):
            metadata_paths.append(
                "metadata/"
                + random.choice(
                    os.listdir("/Users/archer/Documents/HIMA-dev/minter/metadata")
                )
            )

        metadatas = []
        for path in metadata_paths:
            with open(path) as metadata:
                metadatas.append(str(json.load(metadata))[1:-1])
        joined_metadata = ",".join(metadatas)
        final_metadata_str = f"{template_top}{joined_metadata}{template_bottom}"
        with open("./temp/temp.json", "w") as outfile:
            outfile.write(final_metadata_str.replace("'", '"'))

    # def build_mint_command(utxo:Transaction):
