from ntpath import join
import requests
from datetime import datetime
import os, random, json


class Transaction:
    def __init__(
        self,
        hash: str,
        index: int,
        time: str,
        assets: list,
        mint_amount: int,
        sellable: bool,
        refundable: bool,
    ):
        self.hash = hash
        self.index = index
        self.time = time
        self.assets = assets
        self.mint_amount = mint_amount
        self.sellable = sellable
        self.refundable = refundable


class Utils:
    def fetch_utxo(addr: str):
        response = requests.get(
            f"https://api.koios.rest/api/v0/address_info?_address={addr}"
        ).json()[0]
        return response["utxo_set"]

    def check_utxo(utxo, mint_price: int):
        if int(utxo["value"]) > 2000000:
            if (
                int(utxo["value"]) % mint_price == 0
                and int(utxo["value"]) / mint_price != 0
                and int(utxo["value"]) / mint_price <= 10
            ):
                amount = int(int(utxo["value"]) / mint_price)
                if amount < len(
                    os.listdir("/Users/archer/Documents/HIMA-dev/minter/metadata")
                ):
                    print(f"minting {amount} NFTs")
                    return Transaction(
                        hash=utxo["tx_hash"],
                        index=utxo["tx_index"],
                        time=utxo["block_time"],
                        assets=utxo["asset_list"],
                        mint_amount=amount,
                        sellable=True,
                        refundable=True,
                    )
            else:
                print("Invalid amount refundable")
                return Transaction(
                    hash=utxo["tx_hash"],
                    index=utxo["tx_index"],
                    time=utxo["block_time"],
                    assets=utxo["asset_list"],
                    mint_amount=amount,
                    sellable=False,
                    refundable=True,
                )
        else:
            print("Invalid amount un-refundable")
            return Transaction(
                hash=utxo["tx_hash"],
                index=utxo["tx_index"],
                time=utxo["block_time"],
                assets=utxo["asset_list"],
                mint_amount=amount,
                sellable=False,
                refundable=False,
            )

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
        print(final_metadata_str.replace("'", '"'))
        with open("./temp/testing.json", "w") as outfile:
            outfile.write(final_metadata_str.replace("'", '"'))
