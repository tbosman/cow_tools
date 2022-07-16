# Ingest a input + solution json
# deserializes
# gets objective value

import json
from models.batch_auction_model import SettledBatchAuction, Order
from util.web3tools import get_contract, web3
from eth_abi import encode_single
from util.defaultlogging import *
from util.dbtools import get_postgres_engine
import pandas as pd


GPV2_CONTRACT_ADDRESS = "0x9008D19f58AAbD9eD0D60971565AA8510560ab41"

sol_json = open(
    "/Users/tbosman/git_tree/1inch-solver/service/sol_9021.json", "r"
).read()
sol_json = open(
    "/Users/tbosman/git_tree/1inch-solver/service/recent_sol.json", "r"
).read()
pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 20)

engine = get_postgres_engine()


def get_order_spec(order, timestamp):
    kind = "sell" if order.is_sell_order else "buy"

    sql = f"""
    select  
    *
     from
    cow.orders
    where 
    validto >  0 --{timestamp}
    and 
    selltoken = '{order.sell_token}'
    and
    sellamount = '{order.sell_amount}'
    and 
    buytoken = '{order.buy_token}'
    and 
    buyamount = '{order.buy_amount}'
    and 
    kind = '{kind}'
    and isliquidityorder = {order.is_liquidity_order}
    
    order by timestamp desc
     limit 1
     
    
    """
    print(sql)

    pdf = pd.read_sql_query(sql, engine)
    print(pdf)
    if len(pdf):
        return pdf.to_dict(orient="records")[0]
    else:
        {}


def order_flags(order, order_spec):

    # let mut result = 0u8;
    # // The kind is encoded as 1 bit in position 0.
    # result |= match order.kind {
    #     OrderKind::Sell => 0b0,
    #                        OrderKind::Buy => 0b1,
    # };
    # // The order fill kind is encoded as 1 bit in position 1.
    # result |= (order.partially_fillable as u8) << 1;

    result = 0
    # The kind is encoded as 1 bit in position 0.
    result |= 0 if order.is_sell_order else 1
    # The order fill kind is encoded as 1 bit in position 1.
    result |= (order.allow_partial_fill) << 1
    # The order sell token balance is encoded as 2 bits in position 2.
    result |= (0) << 2  # only support erc for now
    # The order buy token balance is encoded as 1 bit in position 4.
    result |= (0) << 4  # only support erc for now
    # The signing scheme is encoded as a 2 bits in position 5.
    sign_flag = {
        "eip712": 0,
        "ethsign": 1,
        "eip1271": 2,
        "presign": 3,
    }
    result |= sign_flag[order_spec["signingscheme"]] << 5

    #
    return result


def order_to_data(order, tokens, order_spec):
    """
        struct Data {
        uint256 sellTokenIndex;
        uint256 buyTokenIndex;
        address receiver;
        uint256 sellAmount;
        uint256 buyAmount;
        uint32 validTo;
        bytes32 appData;
        uint256 feeAmount;
        uint256 flags;
        uint256 executedAmount;
        bytes signature;
    }"""

    sellTokenIndex = tokens.index(order.sell_token)
    buyTokenIndex = tokens.index(order.buy_token)
    receiver = order_spec["receiver"]
    sellAmount = order.sell_amount
    buyAmount = order.buy_amount
    validTo = order_spec["validto"]
    appData = order_spec["appdata"]
    feeAmount = order_spec["feeAmount"]
    flags = order_flags(order, order_spec)
    executedAmount = (
        order.exec_sell_amount if order.is_sell_order else order.exec_buy_amount
    )
    signature = order_spec["signature"]
    return encode_single(
        [
            "uint256",
            "uint256",
            "address",
            "uint256",
            "uint256",
            "uint32",
            "bytes32",
            "uint256",
            "uint256",
            "uint256",
            "bytes",
        ],
        [
            sellTokenIndex,
            buyTokenIndex,
            receiver,
            sellAmount,
            buyAmount,
            validTo,
            appData,
            feeAmount,
            flags,
            executedAmount,
            signature,
        ],
    )



def ingest_solution(sol_json, timestamp=None):

    timestamp = 1657975768

    settled_batch = SettledBatchAuction.from_json(sol_json)
    settled_batch.strint_to_num()
    settled_batch: SettledBatchAuction

    # replace exec_amounts
    prices = settled_batch.prices
    tokens, clearingPrices = zip(*prices.items())

    trades = []
    for i, o in settled_batch.orders.items():
        logging.info(o)
        sell_price = prices[o.sell_token]
        buy_price = prices[o.buy_token]
        if not o.is_liquidity_order:
            if o.is_sell_order:
                if not o.allow_partial_fill:
                    o.exec_sell_amount = o.sell_amount
                o.exec_buy_amount = o.exec_sell_amount * sell_price / buy_price
            else:
                if not o.allow_partial_fill:
                    o.exec_buy_amount = o.buy_amount
                o.exec_sell_amount = o.exec_buy_amount * buy_price / sell_price

        order_spec = get_order_spec(o, timestamp)
        if order_spec:
            data = order_to_data(o, tokens, order_spec)
            if data:
                trades.append(data)
        else:
            print(f'No order spec for {i} {o}')

    # trades =
    # def encode_trade(selltoken, buytoken, )
    # clearingPrices

    gc = get_contract(GPV2_CONTRACT_ADDRESS)
    gc.all_functions()

    tuple(zip((1, 2), (3, 4), (5, 6)))

    main_interactions = [
        encode_single(['address', 'value', 'callData'],
                      [i.target, i.value, i.call_data])
        for i in settled_batch.interaction_data
    ]
    interactions = [[], main_interactions, []]

    settle_func = gc.functions.settle(tokens, clearingPrices, trades, interactions)

    settle_func.estimateGas({'gasPrice': web3.eth.gas_price,
                      # 'nonce': nonce,
                      'from': '0x149d0f9282333681Ee41D30589824b2798E9fb47'
                      })

    # check limit

    # check prices


ingest_solution(sol_json)

time.time() - 3600