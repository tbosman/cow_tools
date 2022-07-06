import requests
import aiohttp
from util.tokens import *
from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config
import json
import logging
from prefect import flow, task
from prefect.client import get_client
from prefect_dask.task_runners import DaskTaskRunner
from prefect.task_runners import RayTaskRunner

from threading import Thread

import time
import itertools
import asyncio

logging.getLogger().setLevel('INFO')

base_url = "https://api.cow.fi/mainnet/api/v1/"
addr = "0xf7f9C5ecAFd159271fe55A8FEdEDa95d7fcD0DCc"


@dataclass_json
@dataclass
class OrderQuoteResponse:
    sellToken: str
    buyToken: str
    sellAmount: str
    buyAmount: str
    validTo: int
    appData: str
    feeAmount: int
    kind: str
    partiallyFillable: bool
    sellTokenBalance: str
    buyTokenBalance: str


@dataclass_json
@dataclass
class OrderQuoteResponse:
    quote: OrderQuoteResponse
    fromAddress: str = field(metadata=config(field_name="from"))
    expiration: str
    id: int

def short(*tokens):
    return '-'.join(map(lambda x : x[:5] , tokens))

def get_quote(from_token, to_token, amount, from_addr=addr):
    logging.info(f'Sending quote for {short(from_token, to_token)}')
    json = {
            "sellToken": from_token,
            "buyToken": to_token,
            "from": from_addr,
            "receiver": from_addr,
            "kind": "sell",
            "sellAmountBeforeFee": str(int(amount)),
        }
    # async with aiohttp.ClientSession() as session:
    #     async  with aiohttp.request('post', base_url + "quote", json=json) as response:
    #         response_content = await response.text()
    # response_dict = {}
    #
    # def run_request(json):
    #     response_dict[ json.dumps(json) ] = requests.post(
    #         base_url + "quote",
    #         json=json,
    #     )
    # T = Thread(target=requests.post,
    #            args=json )
    #
    #
    # T.start()
    #
    # while True:
    #     asyncio.sleep(1)
    #     if not T.isAlive():
    #         break
    # response = response_dict(json.dumps(json))

    response = requests.post(

        base_url + "quote",
        json=json,
    )

    logging.info(f'Got response for {short(from_token, to_token)}: {response.content}')
    return response

    # try:
    #     return OrderQuoteResponse.from_dict(json.loads(response.content))
    # except Exception as e:
    #     logging.info(f'Exception: {e} \n content: {response.content}')
    #     return response

@task(tags=['quote'])
def get_quote_task(from_token, to_token, amount, from_addr=addr):
    return  get_quote(from_token, to_token, amount, from_addr=addr)



# STABLES = { USDT : 6, USDC : 6,  DAI : 18, FRAX : 18, LUSD: 18, USDI : 6 }
STABLES = { USDT : 6, USDC : 6,  DAI : 18}
@flow(task_runner=DaskTaskRunner())
def run_all():

    logging.info('--------------- STARTING  ')
    base_amount  =  7*10**3
    quotes = {(a,b)  :
         get_quote_task(a, b,  10 ** STABLES[a] * base_amount)

        for a, b in itertools.permutations(STABLES, 2)
    }


    prices = {
    }

    logging.info(quotes)
    # @task
    # async def gather_prices(quotes):
    #     asyncio.gather()

    # (res.wait() for res in quotes.values())


    for (a, b), res in quotes.items():
        logging.info(f'l: {a}{b}')
        try:
            quote = OrderQuoteResponse.from_json(res.result())
            buy_amount = int(quote.quote.buyAmount)
            price = base_amount/(buy_amount/10**STABLES[b])
            prices[a,b] = price
            logging.info(f'Price for {a}->{b} is {price}')
        except Exception as e:
            logging.info(f'Problem with quote for {a}->{b}. \n Exception: {e}')
    #
    return prices

async def set_concurrency(limit=1):
    await get_client().create_concurrency_limit(tag='quote', concurrency_limit=limit)

asyncio.run(set_concurrency(10))
# prices = run_all()

#
# prices = asyncio.run(main())
# prices
#
if __name__ == "__main__":
    prices = run_all()
    print(prices.result())
#
# print(base_url + f"markets/{USDC}-{USDT}/sell/{ 10**9 }")
#
#
#
get_quote(WETH, USDC, 10**18)