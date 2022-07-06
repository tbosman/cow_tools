import asyncio
import pandas as pd
from util.dbtools import get_postgres_engine
from util.web3tools import web3
from eth_account.messages import encode_defunct
import requests
import json
import pprint
from eip712_structs import make_domain
from eip712_structs import Address, Boolean, Bytes, String, Uint
from eip712_structs import EIP712Struct
import time
from datetime import datetime
from hexbytes import HexBytes
from util.tokens import *

with open("config/apikeys.json", "r") as f:
    apikeys = json.load(f)

base_url = "https://api.cow.fi/mainnet/api/v1/"
private_key = apikeys["eoa_key"]
public_address = apikeys["eoa_address"]
domain = make_domain(
    name="Gnosis Protocol",
    version="v2",
    chainId="1",
    verifyingContract="0x9008D19f58AAbD9eD0D60971565AA8510560ab41",
)  # Make a Domain Separator
stablecoins = {}


class Order(EIP712Struct):
    sellToken = Address()
    buyToken = Address()
    receiver = Address()
    sellAmount = Uint(256)
    buyAmount = Uint(256)
    validTo = Uint(32)
    appData = Bytes(32)
    feeAmount = Uint(256)
    kind = String()
    partiallyFillable = Boolean()
    sellTokenBalance = String()
    buyTokenBalance = String()


def placeOrder(myorder):

    my_bytes = myorder.signable_bytes(domain)
    hash = web3.keccak(my_bytes)
    message = encode_defunct(primitive=hash)

    signed_message = web3.eth.account.sign_message(
        message, private_key=private_key
    )
    # print(signed_message)

    json_str = (
        '''{
      "sellToken": "'''
        + str(myorder["sellToken"])
        + '''",
      "buyToken": "'''
        + str(myorder["buyToken"])
        + '''",
      "receiver": "'''
        + str(myorder["receiver"])
        + '''",
      "sellAmount": "'''
        + str(myorder["sellAmount"])
        + '''",
      "buyAmount": "'''
        + str(myorder["buyAmount"])
        + """",
      "validTo": """
        + str(myorder["validTo"])
        + ''',
      "appData": "'''
        + str(myorder["appData"].hex())
        + '''",
      "feeAmount": "'''
        + str(myorder["feeAmount"])
        + '''",
      "kind": "'''
        + str(myorder["kind"])
        + """",
      "partiallyFillable": """
        + str(myorder["partiallyFillable"]).lower()
        + ''',
      "signature": "'''
        + str(signed_message.signature.hex())
        + '''",
      "signingScheme": "ethsign",
      "sellTokenBalance": "'''
        + str(myorder["sellTokenBalance"])
        + '''",
      "buyTokenBalance": "'''
        + str(myorder["buyTokenBalance"])
        + '''",
      "from": "'''
        + public_address
        + """"
    }"""
    )

    print(json_str)
    """json_dict = {}
    json_dict["sellToken"] = sellToken
    json_dict["buyToken"] = buyToken
    json_dict["receiver"] = receiver
    json_dict["sellAmount"] = str(sellAmount)
    json_dict["buyAmount"] = str(buyAmount)
    json_dict["validTo"] = validTo
    json_dict["appData"] = appData
    json_dict["feeAmount"] = str(feeAmount)
    json_dict["kind"] = kind
    json_dict["partiallyFillable"] = str(partiallyFillable).lower()
    json_dict["signature"] = str(signed_message.signature.hex())
    json_dict["signingScheme"] = "ethsign"
    json_dict["sellTokenBalance"] = str(sellTokenBalance)
    json_dict["buyTokenBalance"] = str(buyTokenBalance)
    json_dict["from"] = public_address"""

    # print(json_str)
    j = json.loads(json_str)

    # pprint.pprint(j)

    r = requests.post(base_url + "orders", json=j)

    print("Status code: ", r.status_code)
    print(r.json())


def get_quote(from_token, to_token, amount, from_addr=public_address):
    json = {
        "sellToken": from_token,
        "buyToken": to_token,
        "from": from_addr,
        "receiver": from_addr,
        "kind": "sell",
        "sellAmountBeforeFee": str(int(amount)),
    }
    # logging.info(f'Sending quote for {short(from_token, to_token)}')
    res = requests.post(base_url + "quote", json=json)

    return res.content


def place_sell_order(sell_token, sell_amount_ex_fee, fee_amount, buy_token, buy_amount):
    print(sell_token)
    order = Order()
    order["sellToken"] = sell_token
    order["buyToken"] = buy_token
    order["receiver"] = public_address
    order["sellAmount"] = int(sell_amount_ex_fee)
    order["validTo"] = int(time.time()) + 60 * 5
    order["appData"] = HexBytes(
        "0x0000000000000000000000000000000000000000000000000000000000000000"
    )
    order["kind"] = "sell"
    order["buyAmount"] = int(buy_amount)
    order["feeAmount"] = int(fee_amount)
    order["partiallyFillable"] = False
    order["sellTokenBalance"] = "erc20"
    order["buyTokenBalance"] = "erc20"

    print(order.data_dict())

    placeOrder(order)


engine = get_postgres_engine()
median_rates = pd.read_sql(
    """
select
    pair,
--     expiry,
       percentile_cont(0.5) within group (order by price)
from cow.rates
where expiry::timestamp >= now() - interval '1 day'
group by pair;


""",
    engine,
)
# median_rates
# median_rates_dict = dict(
#     zip(median_rates["pair"], median_rates["percentile_cont"])
# )
#
# counter_rates = {
#     symbol: median_rates_dict[f"{symbol}-{sell_symbol}"]
#     for symbol in counter_tokens
# }
# counter_tokens = {'USDC':USDC, 'DAI': DAI, 'FRAX' : FRAX, 'FEI' : FEI, 'sUSD': sUSD}
counter_tokens = {
    "USDC": USDC,
    "DAI": DAI,
    "USDT": USDT,
    "FEI": FEI,
    "sUSD": sUSD,
}
decimals = {"USDC": 6, "DAI": 18, "FRAX": 18, "FEI": 18, "sUSD": 18, "USDT": 6,
            "USDI": 18}

sell_symbol = "USDI"
sell_token = USDI
sell_amount = 9000 * 10**decimals[sell_symbol]
buy_symbol = 'USDC'
sell_symbol = 'USDI'
while True:
    try:
        quote_response = get_quote(USDI, USDC, sell_amount)
        quote = json.loads(quote_response)["quote"]
        buy_amount = int(quote['buyAmount'])
        sell_amount_ex_fee = int(quote["sellAmount"])
        fee_amount = int(quote["feeAmount"])
        min_buy_amount = sell_amount*1.0012 * 10**(decimals[buy_symbol]-decimals[sell_symbol])
        print(f'Min buy amount: {min_buy_amount} ({min_buy_amount/10**decimals[buy_symbol]})')
        print(f'Buy amount: {buy_amount} ')
        if buy_amount >= min_buy_amount:
            place_sell_order(USDI, sell_amount_ex_fee, fee_amount, USDC, buy_amount)
            print(f"Submitted order for {USDC}. Sleeping for 5 minutes")
            time.sleep(60 * 5)
        print(f"Time: {datetime.fromtimestamp(time.time())}")
    except Exception as e:
        print(f"Problem: {e} \n Quote response: {quote_response}")

    sleep_secs = 15
    print(f"Sleeping for {sleep_secs} seconds")
    time.sleep(15)


# sell_amount = 90 * 10**decimals[sell_symbol]
# while True:
#     try:
#         for symbol, token in counter_tokens.items():
#             quote_response = get_quote(sell_token, token, sell_amount)
#             quote = json.loads(quote_response)["quote"]
#             # print(quote)
#             price = (
#                     (int(quote["sellAmount"]) + int(quote["feeAmount"]))
#                     / (int(quote["buyAmount"]))
#                     * 10 ** decimals[symbol]
#                     / 10**decimals[sell_symbol]
#             )
#             rprice = counter_rates[symbol]
#             print(
#                 f"{symbol}, sell {sell_symbol}. Current price { price :.4f}, median return price {rprice:.4f}. Expected arbitrage: {price*rprice:.5f}"
#             )
#
#             if price * rprice < 0.999:
#                 print(f"Found a good opportunity. ")
#                 sell_amount_ex_fee = int(quote["sellAmount"])
#                 fee_amount = int(quote["feeAmount"])
#                 buy_amount = min(
#                     int(quote["buyAmount"]),
#                     sell_amount
#                     * 10 ** (decimals[symbol] - decimals[sell_symbol]),
#                     )
#                 place_sell_order(
#                     sell_token,
#                     sell_amount_ex_fee, fee_amount, token, buy_amount
#                 )
#                 print(f"Submitted order for {symbol}. Sleeping for 5 minutes")
#                 time.sleep(60 * 5)
#         sleep_secs = 15
#         print(f"Sleeping for {sleep_secs} seconds")
#         time.sleep(15)
#         print(f"Time: {datetime.fromtimestamp(time.time())}")
#     except Exception as e:
#         print(f"Problem: {e} \n Quote response: {quote_response}")
