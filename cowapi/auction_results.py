import aiohttp
from datetime import datetime
from xml.etree import ElementTree as ET
import requests
import re
from util.dbtools import get_postgres_engine
import pandas as pd
import logging
import asyncio

logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s',
                    level=logging.INFO,
                    datefmt="%m-%d %H:%M:%S")



def get_new_ids(start_after):
    list_url = f'https://gnosis-europe-gpv2-solver.s3.eu-central-1.amazonaws.com/?list-type=2&delimiter=/&prefix=data/prod/&start-after={start_after}'

    response = requests.get(list_url).content
    root = ET.fromstring(response)

    prefixes = [el[0].text for el in root if 'CommonPrefixes' in el.tag]
    eth_prefixes = [p for p in prefixes if 'Mainnet' in p]


    return eth_prefixes



def extract_cols(prefix):
    datetime_raw = re.match(
        r'data/prod/([0-9]{4}/[0-9]{2}/[0-9]{2}/[0-9]{2}:[0-9]{2}:[0-9]{2})',
        prefix).group(1)
    timestamp = int(
        datetime.strptime(datetime_raw, '%Y/%m/%d/%H:%M:%S').timestamp())
    datetime_raw = re.sub('([0-9]{2})/([0-9]{2}:)', r'\1T\2', datetime_raw)
    datetime_raw = re.sub('/', '-', datetime_raw)
    auction_id = int(re.search(f'_([0-9]+)/$', prefix).group(1))
    return (prefix, auction_id, datetime_raw, timestamp)



async def get_auction_result(auction_id, sem):

    async with sem:
        async with aiohttp.ClientSession() as session:
            req_url = f'https://api.cow.fi/mainnet/api/v1/solver_competition/{auction_id}'
            async with aiohttp.request('get', req_url) as response:
                try:
                    # response_text = response.text()
                    await response.text()
                    return response
                except ConnectionRefusedError as e:
                    logging.info('Connection refused, sleeping for a bit ')
                    await asyncio.sleep(10)
                    return response

    #
    # try:
    #     r = requests.get(
    #         f'https://api.cow.fi/mainnet/api/v1/solver_competition/{auction_id}',
    #         timeout=15)
    #     logging.info(f'{r.status_code}: {r.content}')
    #     return r
    # except Exception as e:
    #     logging.info(f'Problem for {auction_id}. {r}, {e}')
    #     return None
    #

engine = get_postgres_engine()
def store_row(prefix, auction_id, datetime_raw,timestamp, solutions):
    pdf = pd.DataFrame([  ( prefix, auction_id, datetime_raw,timestamp, solutions)],
                       columns=['prefix', 'auction_id', 'date_str', 'timestamp', 'solutions'])
    pdf.to_sql('auction_ids', engine, if_exists='append', schema='cow')
    logging.info(f'Auction {auction_id}: 1 row written to db.')



async def download_and_store_auction(prefix, sem):
    global latest_prefix
    (prefix, auction_id, datetime_raw, timestamp) = extract_cols(prefix)
    max_retry = 10
    sleep_secs = 60
    for i in range(max_retry):
        r = await get_auction_result(auction_id, sem)
        if r is not None:
            if r.status == 200:
                logging.info(f'Found result for {auction_id}')
                store_row(prefix, auction_id, datetime_raw, timestamp, await r.text())
                break
            elif r.status == 404:
                logging.info(f'Auction {auction_id}: 404 result not found')
                if latest_prefix > prefix:
                    logging.info(f'Newer auction found {latest_prefix} > {prefix}, '
                                 f'assuming batch didnt settle.')
                    store_row(prefix, auction_id, datetime_raw, timestamp, '')
                    break
                else:
                    logging.info(f'No newer solution seen yet, retrying in {sleep_secs} seconds.')
            else:
                logging.info(f'Uknown status code for auction {auction_id}: {r.status} {r.text()}.'
                             f'Retrying.')
        else:
            logging.info(
                    f'Auction downloader returned none, retrying')
        if i +1 < max_retry:
            await asyncio.sleep(60)
        else:
            logging.info(f'Max retries ({max_retry}) reached, aborting auction {auction_id}.')



async def download_all():
    global latest_prefix
    cow_semaphore = asyncio.Semaphore(3)

    while True:
        prefixes = get_new_ids(latest_prefix)
        if prefixes:
            logging.info(f'Retrieved {len(prefixes)} prefixes')
            latest_prefix = sorted(prefixes)[-1]
            await asyncio.wait([asyncio.create_task(download_and_store_auction(prefix, cow_semaphore))
                              for prefix in prefixes])
        else:
            logging.info(f'No prefixes found after {latest_prefix}')
        logging.info(f'Sleeping S3 monitor')
        await asyncio.sleep(60)



# latest_prefix = 'data/prod/2022/07/06/08:00:39.313298594_UTC_Ethereum___Mainnet_1_420'
qry = '''
SELECT max(prefix) from cow.auction_ids
'''
pdf = pd.read_sql(qry, engine)
latest_prefix = pdf.iloc[0, 0]
asyncio.run(download_all())
