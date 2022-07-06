import numpy as np
import requests
import json
from datetime import datetime
import argparse

with open("config/apikeys.json", "r") as f:
    apikeys = json.load(f)

ETHERSCAN_KEY = apikeys["etherscan"]


def get_transactions_from_etherscan(address, etherscan_key=ETHERSCAN_KEY):
    transactions_by_address_endpoint = (
        f"https://api.etherscan.io/api?"
        f"module=account&action=txlist"
        f"&address={address}"
        f"&startblock=0&endblock=999999999&page=1&offset=0&sort=desc&apikey={etherscan_key}"
    )

    return json.loads(requests.get(transactions_by_address_endpoint).text)[
        "result"
    ]


if __name__ == '__main__':

    parser = argparse.ArgumentParser("solver_monitor")
    parser.add_argument("--port", help="Port to run on.", type=int, default=7000)

    args = parser.parse_args()



txs = get_transactions_from_etherscan(
    "0x149d0f9282333681Ee41D30589824b2798E9fb47"
)
solver_addr = "0xdE1c59Bc25D806aD9DdCbe246c4B5e5505645718"
txs = get_transactions_from_etherscan(solver_addr)

txs
gpv2_addr = "0x9008d19f58aabd9ed0d60971565aa8510560ab41"
tx_cost_failed = int(
    np.mean(
        [
            (
                int(int(tx["gasUsed"]) * int(tx["gasPrice"]) / 10**9),
                int(tx["gasUsed"]),
            )
            for tx in txs
            if tx["isError"] != "0" and tx["to"] == gpv2_addr
        ]
    )
)
tx_cost_success = int(
    np.mean(
        [
            (
                int(int(tx["gasUsed"]) * int(tx["gasPrice"]) / 10**9),
                int(tx["gasUsed"]),
            )
            for tx in txs
            if tx["isError"] == "0" and tx["to"] == gpv2_addr
        ]
    )
)

print(f'Solver address: {solver_addr}')
print(f"Avg tx cost failed txs: { tx_cost_failed }")
print(f"Avg tx cost success txs: { tx_cost_success }")

