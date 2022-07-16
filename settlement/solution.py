# Ingest a input + solution json
# deserializes
# gets objective value

import json
from models.batch_auction_model import SettledBatchAuction, Order
from util.web3tools import get_contract, web3
from util.defaultlogging import *
from util.dbtools import get_postgres_engine
import pandas as pd

GPV2_CONTRACT_ADDRESS = '0x9008D19f58AAbD9eD0D60971565AA8510560ab41'

sol_json = open('/Users/tbosman/git_tree/1inch-solver/service/sol_9021.json',
                'r').read()


engine = get_postgres_engine()
def get_order_uid(order, timestamp):
    sql = f'''
    select  * from 
    cow.orders
    where 
    validTo > {timestamp}
    and 
    sellToken = '{order.sell_token}'
    and 
    sellAmount = '{order.sell_amount}'
    and 
    buyToken = '{order.buy_token}'
    and 
    buyAmount = '{order.buy_amount}'
    '''
    pdf = pd.read_sql_query(sql, engine)
    print(pdf)

sell_token ='0xdac17f958d2ee523a2206206994597c13d831ec7'
buy_token ='0x6b175474e89094c44da98b954eedeac495271d0f'
sell_amount = '10726300043'
buy_amount = '10731072630004299857920'

order = Order(sell_amount=sell_amount,
              buy_amount=buy_amount,
              sell_token=sell_token,
              buy_token=buy_token,
              allow_partial_fill=False,
              is_sell_order=True,
              fee=None,
              cost=None,
              is_liquidity_order=False,
              has_atomic_execution=True,
              )

timestamp = 1657973742 -10




def ingest_solution(sol_json, timestamp=None):
    settled_batch = SettledBatchAuction.from_json(sol_json)
    settled_batch.strint_to_num()
    settled_batch: SettledBatchAuction
    settled_batch.prices


    # replace exec_amounts
    prices = settled_batch.prices
    for i, o in settled_batch.orders.items():
        logging.info(o)
        sell_price = (prices[o.sell_token])
        buy_price = (prices[o.buy_token])
        if not o.is_liquidity_order:
            if o.is_sell_order:
                if not o.allow_partial_fill:
                    o.exec_sell_amount = o.sell_amount
                o.exec_buy_amount = o.exec_sell_amount*sell_price/buy_price
            else:
                if not o.allow_partial_fill:
                    o.exec_buy_amount = o.buy_amount
                o.exec_sell_amount = o.exec_buy_amount*buy_price/sell_price



    tokens, clearingPrices = zip(*prices.items())
    '''
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
    }'''
    a = list(123)
    # trades =
    # def encode_trade(selltoken, buytoken, )
    # clearingPrices

    gc = get_contract(GPV2_CONTRACT_ADDRESS)
    gc.all_functions()

    tuple(zip((1,2), (3,4), (5,6)))

    gc.settle()

    # check limit


    # check prices


ingest_solution(sol_json)


