# Ingest a input + solution json
# deserializes
# gets objective value

import json
import asyncio
import web3.exceptions
from cow_tools.models.batch_auction_model import SettledBatchAuction, Order
from cow_tools.settlement.datastructures import SimulationRequest
from cow_tools.util.web3tools import get_contract, web3
from eth_abi import encode_abi, encode_single
from cow_tools.util.defaultlogging import *
from cow_tools.util.dbtools import get_postgres_engine
import pandas as pd
from datetime import datetime
from functools import lru_cache
import websockets


GPV2_CONTRACT_ADDRESS = "0x9008D19f58AAbD9eD0D60971565AA8510560ab41"
pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 20)

engine = get_postgres_engine()

logger = logging.getLogger(__name__)


def _get_order_spec(order):
    # Auction_id is only used for caching purposes (gets called for every auction_id)

    kind = "sell" if order.is_sell_order else "buy"

    sql = f"""
    select  
    *
     from
    cow.orders
    where 
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

    pdf = pd.read_sql_query(sql, engine)
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

    tokens = [token.lower() for token in tokens]
    sellTokenIndex = tokens.index(order.sell_token)
    buyTokenIndex = tokens.index(order.buy_token)
    receiver = web3.toChecksumAddress(order_spec["receiver"])
    sellAmount = order.sell_amount
    buyAmount = order.buy_amount
    validTo = order_spec["validto"]
    appData = order_spec["appdata"]
    feeAmount = order_spec["feeamount"]
    flags = order_flags(order, order_spec)
    executedAmount = (
        order.exec_sell_amount if order.is_sell_order else order.exec_buy_amount
    )
    signature =  order_spec["owner"] if order_spec['signingscheme'] == 3 else order_spec["signature"]
    return [
            sellTokenIndex,
            buyTokenIndex,
            receiver,
            sellAmount,
            buyAmount,
            validTo,
            web3.toBytes(hexstr=appData),
            int(feeAmount),
            flags,
            executedAmount,
            web3.toBytes(hexstr=signature),
        ]




class SettlementSimulator:
    '''
    Will hold a cache for retrieving order specs
    '''


    def __init__(self):
        self.get_order_spec = lru_cache()(self.get_order_spec)
        # This is not relevant anyway
        self.gas_price = web3.eth.gas_price * 10


    def get_order_spec(self, order):
        order_spec = _get_order_spec(order)
        logger.debug(f'Order spec retrieved: {order_spec}')
        return order_spec

    def get_settle_func_and_block(self, sol_json, estimate_block=True):

        settled_batch = SettledBatchAuction.from_json(sol_json)
        settled_batch.strint_to_num()
        settled_batch: SettledBatchAuction

        # replace exec_amounts
        prices = settled_batch.prices
        tokens, clearingPrices = zip(*prices.items())
        tokens = [web3.toChecksumAddress(token) for token in tokens]

        tgt_block = None
        trades = []
        for i, o in settled_batch.orders.items():
            logger.info(o)
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

            order_spec = self.get_order_spec(o)
            if order_spec:
                data = order_to_data(o, tokens, order_spec)
                tgt_block = order_spec['block']
                if data:
                    trades.append(data)
            else:
                logging.info(f'No order spec for {i} {o}')
                raise ValueError(f'No order spec found for order {i}: {o}')

        gc = get_contract(GPV2_CONTRACT_ADDRESS, web3=web3)

        main_interactions = [
            [web3.toChecksumAddress(i.target), i.value, i.call_data]
            for i in settled_batch.interaction_data]
        interactions = [[], main_interactions, []]

        logger.info(f'tgt block: {tgt_block}')

        settle_func = gc.functions.settle(list(tokens),
                                          list(clearingPrices), trades,
                                          interactions)

        return settle_func, tgt_block

    def simulate_gas(self, sol_json, estimate_block=False):
        result = {}
        try:
            settle_func, tgt_block = self.get_settle_func_and_block(sol_json, estimate_block)
            sim_block = tgt_block if estimate_block else None
            gas = settle_func.estimateGas({'gasPrice': self.gas_price,
                                           'from': '0x149d0f9282333681Ee41D30589824b2798E9fb47',
                                           'chainId' : 1,
                                           }, sim_block)
            logger.info(f'Estimated gas: {gas}')
            result['passed'] = True
            result['gas'] = gas
        except Exception as e:
            result['passed'] = False
            result['error'] = str(e)
            if 'reverted' in str(e):
                logger.info('Transaction reverted')
                result['reason'] = 'reverted'
            else:
                result['reason'] = 'unknown'
                logger.exception('Unknown problem estimating gas')
        finally:
            return result




def call_simulate_solution(sol_json):
    async def async_simulate_solution(sol_json):
        async with websockets.connect("wss://sim.plmsolver.link",
                                      ping_interval=10,
                                      ping_timeout=20) as websocket:
            msg = SimulationRequest(SettledBatchAuction.from_json(sol_json),
                                    False).to_json()

            await websocket.send(msg)
            response = await websocket.recv()
        return response

    return asyncio.run(async_simulate_solution(sol_json))

