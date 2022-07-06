import aiohttp

from util.tokens import *
from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config
import logging
import traceback

from sqlalchemy import create_engine

import time
import itertools
import asyncio
import pandas as pd

logging.getLogger().setLevel('INFO')

base_url = "https://api.cow.fi/mainnet/api/v1/"
addr = "0xf7f9C5ecAFd159271fe55A8FEdEDa95d7fcD0DCc"


@dataclass_json
@dataclass
class OrderParameters:
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
    quote: OrderParameters
    fromAddress: str = field(metadata=config(field_name="from"))
    expiration: str
    id: int

def short(*tokens):
    return '-'.join(map(lambda x : x[:5] , tokens))


async def async_get_quote(from_token, to_token, amount,  sem: asyncio.Semaphore=asyncio.Semaphore(3), from_addr=addr):
    json = {
            "sellToken": from_token,
            "buyToken": to_token,
            "from": from_addr,
            "receiver": from_addr,
            "kind": "sell",
            "sellAmountBeforeFee": str(int(amount)),
        }
    async with sem:
        # logging.info(f'Sending quote for {short(from_token, to_token)}')
        async with aiohttp.ClientSession() as session:
            async with aiohttp.request('post', base_url + "quote", json=json) as response:
                response_text =  response.text()
                return await response_text

    # response_dict = {}

    # logging.info(f'Got response for {short(from_token, to_token)}: {response.content}')
    # return response


POSTGRES_URI = 'postgresql://postgres:cowdatabasepassword@' \
               'database-1.cluster-csh4afkcgphk.eu-west-2.rds.amazonaws.com:5432/postgres'


def write_quotes_to_db(quotes, decimals):
    to_float_cols = ['sellAmount', 'buyAmount', 'feeAmount']
    row_dicts = []

    timestamp = time.time()


    for quote in quotes:
        row_dict = quote.quote.to_dict()
        row_dict['expiry'] = quote.expiration
        for col in to_float_cols:
            row_dict[col] = float(row_dict[col])

        row_dict['sellAmount'] = row_dict['sellAmount']/10**decimals[row_dict['sellToken']]
        row_dict['feeAmount'] = row_dict['feeAmount']/10**decimals[row_dict['sellToken']]
        row_dict['buyAmount'] = row_dict['buyAmount']/10**decimals[row_dict['buyToken']]
        row_dict['timestamp'] = timestamp
        row_dicts.append(row_dict)
    pdf = pd.DataFrame(row_dicts)

    pdf.columns= [col.lower() for col in pdf.columns]


    try:
        engine = create_engine(POSTGRES_URI)
        pdf.to_sql('quotes', engine, if_exists='append', schema='cow')


        logging.info(f'Succesfully wrote {len(pdf)} rows to database')
    except Exception as e:
        logging.info(f'Something went wrong writing to database: {e}')





# STABLES = { USDT : 6, USDC : 6,  DAI : 18, FRAX : 18, LUSD: 18, USDI : 18 }
# STABLES = { USDT : 6, USDC : 6,  DAI : 18, FRAX : 18, LUSD: 18}
names = {USDT: 'USDT', USDC: 'USDC', DAI: 'DAI', FRAX: 'FRAX', LUSD: 'LUSD', USDI: 'USDI', sUSD: 'sUSD',
         FEI: 'FEI', BUSD:'BUSD'}
# STABLES = { USDT : 6, USDC : 6,  DAI : 18}
# STABLES = { USDT : 6, USDI : 18 }
STABLES = { USDT : 6, USDC : 6,  DAI : 18, FRAX : 18, LUSD: 18, USDI : 18 , sUSD: 18, FEI: 18, BUSD: 18}
async def run_all(base_amount=10**4):



    logging.info('--------------- STARTING  ')
    # quotes = {(a,b)  :
    #      asyncio.create_task(async_get_quote(a, b,  10 ** STABLES[a] * base_amount))
    #     for a, b in itertools.permutations(STABLES, 2)
    # }

    sem = asyncio.Semaphore(3)
    quotes = {(a,b)  :
                  asyncio.create_task(async_get_quote(a, b,  10 ** STABLES[a] * base_amount, sem=sem))
              for a, b in itertools.permutations(STABLES, 2)
              }
    await asyncio.wait((quotes.values()))
    # print(tasks)
    # quotes = dict(zip(quotes.keys(), tasks))



    prices = {
    }

    quotes_list = []

    for (a, b), res in quotes.items():
        try:
            result =  res.result()
            # result = await res
            # quote = OrderQuoteResponse.from_json(res.result())

            quote = OrderQuoteResponse.from_json(result)
            quotes_list.append(quote)
            buy_amount = int(quote.quote.buyAmount)
            buy_amount_scaled= (buy_amount/10**STABLES[b])
            price = base_amount/buy_amount_scaled
            prices[a,b] = price
            logging.info(f'Price for {names[a]}->{names[b]} is {price:.5f}. {base_amount} -> {buy_amount_scaled}')
        except Exception as e:
            logging.info(traceback.format_exc())
            logging.info(f'Problem with quote for {a}->{b}. \n Exception: {e} {result}')
    #
    write_quotes_to_db(quotes_list, STABLES)

    return prices, quotes_list


prices, quotes = asyncio.run(run_all())
# prices = run_all()
logger = logging.getLogger()
if len(logger.handlers):
    handler = logger.handlers[0]
else:
    handler = logging.StreamHandler()
formatter = logging.Formatter(
    "%(asctime)s %(name)s line %(lineno)d %(levelname)-4s  %(message)s",
    "%m-%d %H:%M:%S",
)
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


#
while True:
    prices, quotes = asyncio.run(run_all())

    pairs = []
    for a,b in itertools.combinations(STABLES, 2):
        if ( a,b  ) in prices and (b,a) in prices:
            output = (f'{names[a]}-{names[b]}: {prices[a,b]*prices[b,a]:.5f} from {prices[a,b]:.4f} {prices[b,a]:.4f}')
            gain = prices[a,b]*prices[b,a]
            pairs.append((gain, output))
    for _, output in sorted(pairs, reverse=True):
        logging.info(output)


    sleepsecs = 10
    logging.info(f'Sleeping for {sleepsecs} secs')
    time.sleep(sleepsecs)




#
# if __name__ == "__main__":
#     prices = run_all()
#     print(prices.result())
# #
# # print(base_url + f"markets/{USDC}-{USDT}/sell/{ 10**9 }")
# #
# #
# #
# get_quote(WETH, USDC, 10**18)
#
#
#
